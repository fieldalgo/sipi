"""Loopback-only offline workbench. Run directly or as a one-file executable."""

import argparse
import json
import mimetypes
import multiprocessing
from pathlib import Path
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import webbrowser

if __package__:
    from .engine import worker
else:
    from engine import worker

MAX_BODY = 256 * 1024
MAX_SECONDS = 300
STATIC = {'/': 'index.html', '/app.js': 'app.js', '/model.js': 'model.js',
          '/saved.html': 'saved.html', '/saved.js': 'saved.js',
          '/saved.css': 'saved.css',
          '/build-info.json': 'build-info.json',
          '/transport.js': 'transport.js', '/styles.css': 'styles.css',
          '/browser-transport.js': 'browser-transport.js',
          '/notices.txt': 'notices.txt'}


class Job:
    def __init__(self):
        self.lock = threading.RLock()
        self.process = self.connection = None
        self.started = None
        self.state = {'status': 'idle'}

    def read(self):
        with self.lock:
            if self.process is not None:
                if self.connection.poll():
                    try:
                        self.state = self.connection.recv()
                    except EOFError:
                        self.state = {'status': 'error', 'message': 'Calculation process stopped unexpectedly.'}
                    self._stop()
                elif time.monotonic() - self.started > MAX_SECONDS:
                    self.state = {'status': 'error', 'message': 'Calculation exceeded the five-minute limit.'}
                    self._stop()
                elif not self.process.is_alive():
                    self.state = {'status': 'error', 'message': 'Calculation process stopped unexpectedly.'}
                    self._stop()
            return dict(self.state)

    def start(self, request):
        with self.lock:
            if self.read()['status'] == 'running':
                raise RuntimeError('A calculation is already running.')
            context = multiprocessing.get_context('spawn')
            self.connection, child = context.Pipe(duplex=False)
            self.process = context.Process(target=worker, args=(request, child), daemon=True)
            self.state = {'status': 'running'}
            self.started = time.monotonic()
            try:
                self.process.start()
            except Exception:
                self.connection.close()
                self.process = self.connection = None
                self.state = {'status': 'error', 'message': 'Could not start the calculation process.'}
                raise
            finally:
                child.close()
            return self.state

    def _stop(self):
        if self.process is not None:
            self.process.join(timeout=0.1)
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(timeout=2)
            self.process.close()
            self.connection.close()
            self.process = self.connection = None

    def cancel(self):
        with self.lock:
            self._stop()
            self.state = {'status': 'cancelled'}
            return self.state


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, ui, port=0):
        super().__init__(('127.0.0.1', port), Handler)
        self.ui = Path(ui).resolve()
        self.token = secrets.token_urlsafe(32)
        self.origin = f'http://127.0.0.1:{self.server_port}'
        self.job = Job()

    def service_actions(self):
        self.job.read()  # Enforce the limit even after the browser is closed.


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass  # Do not log tokens or user input.

    def respond(self, value, status=200):
        body = json.dumps(value, allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.headers_out('application/json', len(body))
        self.wfile.write(body)

    def headers_out(self, content_type, size):
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(size))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.end_headers()

    def allowed(self, api=False):
        if self.headers.get('Host') != urlsplit(self.server.origin).netloc:
            self.respond({'message': 'Invalid host.'}, 403)
            return False
        origin = self.headers.get('Origin')
        if origin is not None and origin != self.server.origin:
            self.respond({'message': 'Invalid origin.'}, 403)
            return False
        if api and not secrets.compare_digest(
                self.headers.get('Authorization', ''), 'Bearer '+self.server.token):
            self.respond({'message': 'Open the workbench from its launch URL.'}, 403)
            return False
        return True

    def do_GET(self):
        path = urlsplit(self.path).path
        if not self.allowed(api=path.startswith('/api/')):
            return
        if path == '/api/job':
            self.respond(self.server.job.read())
            return
        if path not in STATIC:
            self.respond({'message': 'Not found.'}, 404)
            return
        target = self.server.ui / STATIC[path]
        if path == '/notices.txt' and not target.is_file():
            body = b'Development checkout. The Windows build collects exact dependency licenses and notices into this page. See workbench/THIRD_PARTY.md for the source inventory.\n'
            self.send_response(200)
            self.headers_out('text/plain; charset=utf-8', len(body))
            self.wfile.write(body)
            return
        if not target.is_file():
            self.respond({'message': 'Application asset is missing.'}, 404)
            return
        body = target.read_bytes()
        self.send_response(200)
        content_type = 'text/javascript' if target.suffix == '.js' else mimetypes.guess_type(target.name)[0]
        self.headers_out(content_type or 'application/octet-stream', len(body))
        self.wfile.write(body)

    def do_POST(self):
        if not self.allowed(api=True):
            return
        if self.headers.get('Transfer-Encoding') is not None:
            self.respond({'message': 'Transfer encoding is not supported.'}, 400)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            length = -1
        if not 0 < length <= MAX_BODY:
            self.respond({'message': 'Input exceeds the 256 KiB limit or is empty.'}, 413)
            return
        if self.headers.get_content_type() != 'application/json':
            self.respond({'message': 'JSON input required.'}, 415)
            return
        self.connection.settimeout(5)
        try:
            def reject(value):
                raise ValueError('Nonfinite JSON number: '+value)
            request = json.loads(self.rfile.read(length), parse_constant=reject)
            if not isinstance(request, dict):
                raise ValueError('Input must be a JSON object.')
        except (ValueError, TimeoutError) as exc:
            self.respond({'message': str(exc)}, 400)
            return
        path = urlsplit(self.path).path
        if path == '/api/job':
            try:
                self.respond(self.server.job.start(request), 202)
            except RuntimeError as exc:
                self.respond({'message': str(exc)}, 409)
        elif path == '/api/cancel':
            self.respond(self.server.job.cancel())
        elif path == '/api/shutdown':
            self.server.job.cancel()
            self.respond({'status': 'closed'})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
        else:
            self.respond({'message': 'Not found.'}, 404)


def main(argv=None):
    parser = argparse.ArgumentParser(description='SIPI offline workbench')
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--port', type=int, default=0)
    args = parser.parse_args(argv)
    ui = Path(__file__).resolve().parent / 'ui'
    if not ui.is_dir():
        ui = Path(__file__).resolve().parent.parent / 'ui'
    server = Server(ui, args.port)
    url = server.origin+'/#token='+server.token
    print('SIPI offline workbench: '+url, flush=True)
    print('Use Exit in the workbench or Ctrl+C here to stop.', flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.job.cancel()
        server.server_close()


if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()
