# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit UI or saved-input execution; importing this module starts no host."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile


class _OutputError(OSError):
    def __init__(self, message, *, published=False):
        super().__init__(message)
        self.published = published


def _input_limit(value):
    number = int(value)
    if not 1 <= number <= 64 * 1024 * 1024:
        raise argparse.ArgumentTypeError('input limit must be 1..67108864 bytes')
    return number


def _read_input(path, limit):
    if path == '-':
        data = sys.stdin.buffer.read(limit + 1)
    else:
        with open(path, 'rb') as stream:
            data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError('saved input exceeds max_input_bytes')
    return data.decode('utf-8')


def _write_output(path, text):
    data = text.encode('utf-8')
    if path == '-':
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
        return
    target = Path(path)
    temporary = None
    published = False
    failure = None
    try:
        # Exclusive publication never truncates a previous result, including
        # a symlink or a destination created by another process during a solve.
        with tempfile.NamedTemporaryFile(mode='wb', dir=target.parent,
                prefix='.sipi-result-', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, target)
        published = True
    except (OSError, KeyboardInterrupt) as exc:
        failure = exc
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except OSError as exc:
                if failure is None:
                    failure = exc
    if failure is not None:
        if isinstance(failure, KeyboardInterrupt):
            raise failure
        suffix = ' Result was published; reopen it before retrying.' if published else ' No result was published by this invocation.'
        raise _OutputError(str(failure) + suffix, published=published) from failure


def _parser():
    from . import __version__
    parser = argparse.ArgumentParser(prog='sipi', description='Open the local SIPI UI, or validate/run saved calculation inputs.')
    parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)
    subcommands = parser.add_subparsers(dest='command')
    gui = subcommands.add_parser('gui', help='Open the installed local UI (the default without a subcommand).')
    gui.add_argument('--no-browser', action='store_true', help='Print the local URL without opening a browser.')
    gui.add_argument('--port', type=_port, default=0, help='Loopback port, 0 selects an available port.')
    for name, help_text in [('run', 'Run an input and write an execution receipt.'),
                            ('validate', 'Validate and write canonical input without a field solve.')]:
        command = subcommands.add_parser(name, help=help_text)
        command.add_argument('input', help='Input JSON path, or - for UTF-8 standard input.')
        command.add_argument('--output', default='-', help='New output path, or - for UTF-8 standard output; existing paths are never overwritten.')
        command.add_argument('--max-input-bytes', type=_input_limit, default=262144)
        if name == 'run':
            command.add_argument('--max-evaluations', type=int, default=128)
            command.add_argument('--diagnostic', action='append', default=[], choices=['characteristic', 'modes'])
    return parser


def _port(value):
    number = int(value)
    if not 0 <= number <= 65535:
        raise argparse.ArgumentTypeError('port must be 0..65535')
    return number


def _launch_gui(args):
    try:
        from ._workbench.main import main as host_main
    except ModuleNotFoundError as exc:
        if exc.name != 'sipi._workbench.main':
            raise
        print('sipi: UI assets are unavailable. Install a built SIPI wheel; a source checkout can use workbench/desktop/main.py.', file=sys.stderr)
        return 1
    options = [] if args.command is None else ['--port', str(args.port)]
    if args.command == 'gui' and args.no_browser:
        options.append('--no-browser')
    try:
        host_main(options)
    except (OSError, ValueError) as exc:
        print('sipi: UI: ' + str(exc), file=sys.stderr)
        return 1
    return 0


def main(argv=None):
    """Return a documented exit code; argparse handles usage and help exits."""
    args = _parser().parse_args(argv)
    try:
        if args.command in (None, 'gui'):
            return _launch_gui(args)
        if args.output != '-' and os.path.lexists(args.output):
            print('sipi: output already exists; choose a new path.', file=sys.stderr)
            return 3
        try:
            text = _read_input(args.input, args.max_input_bytes)
            if args.command == 'validate':
                from .execution import normalize_saved
                output = normalize_saved(text, max_input_bytes=args.max_input_bytes) + '\n'
                status = 0
            else:
                from .execution_request import SavedExecutionRequest
                request = SavedExecutionRequest(text, max_input_bytes=args.max_input_bytes,
                    max_evaluations=args.max_evaluations, diagnostics=args.diagnostic)
        except (OSError, ValueError, TypeError) as exc:
            print('sipi: input: ' + str(exc), file=sys.stderr)
            return 2
        if args.command == 'run':
            try:
                receipt = request.run()
                output = json.dumps(receipt, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
                status = 0 if receipt['execution']['status'] == 'complete' else 1
            except Exception as exc:
                print('sipi: calculation: ' + str(exc), file=sys.stderr)
                return 1
        try:
            _write_output(args.output, output)
        except BrokenPipeError as exc:
            # Python flushes stdout again during shutdown. Redirect its broken
            # descriptor so that shutdown cannot replace exit 3 with exit 120.
            try:
                with open(os.devnull, 'wb') as sink:
                    os.dup2(sink.fileno(), sys.stdout.fileno())
            except (OSError, ValueError):
                pass
            print('sipi: output: ' + str(exc), file=sys.stderr)
            return 3
        except OSError as exc:
            print('sipi: output: ' + str(exc), file=sys.stderr)
            return 3
        return status
    except KeyboardInterrupt:
        print('sipi: interrupted; inspect any output path before retrying.', file=sys.stderr)
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
