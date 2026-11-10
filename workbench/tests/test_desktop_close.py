"""Real TCP rejections retain their response under backpressure and bounded cleanup."""
import http.client
import json
from pathlib import Path
import queue
import socket
import sys
import threading
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'desktop'))
from main import Server


@pytest.fixture
def server():
    class ObservedServer(Server):
        def __init__(self):
            self.finished = queue.Queue()
            super().__init__(Path(__file__).resolve().parents[1] / 'ui')

        def process_request_thread(self, request, address):
            try:
                super().process_request_thread(request, address)
            finally:
                self.finished.put(True)

    instance = ObservedServer()
    thread = threading.Thread(target=instance.serve_forever,
                              kwargs={'poll_interval': .05}, daemon=True)
    thread.start()
    yield instance
    instance.job.cancel()
    instance.shutdown()
    instance.server_close()
    thread.join(timeout=3)
    assert not thread.is_alive()


def exchange(server, method='GET', data=None, headers=None, send_buffer=4096):
    conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
    conn.connect()
    conn.sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, send_buffer)
    hdr = {'Authorization': 'Bearer ' + server.token, 'Content-Type': 'application/json'}
    hdr.update(headers or {})
    try:
        conn.request(method, '/api/job', data, hdr)
        reply = conn.getresponse()
        return reply.status, json.loads(reply.read())
    finally:
        conn.close()


@pytest.mark.parametrize('send_buffer', [1024, 4096, 32768])
def test_oversized_request_response_survives_backpressure(server, send_buffer):
    body = json.dumps({'x': 'x' * 270000})
    for _ in range(3):
        status, reply = exchange(server, 'POST', body, send_buffer=send_buffer)
        assert status == 413 and '256 KiB' in reply['message']
    status, reply = exchange(server)
    assert status == 200 and reply['status'] == 'idle'


@pytest.mark.parametrize('headers,status', [
    ({'Authorization': 'Bearer incorrect'}, 403),
    ({'Origin': 'https://invalid.example'}, 403),
    ({'Host': 'invalid.example'}, 403),
    ({'Transfer-Encoding': 'chunked'}, 400),
    ({'Content-Type': 'text/plain'}, 415),
    ({'Content-Length': 'invalid'}, 413),
    ({'Content-Length': '0'}, 413),
], ids=['authorization', 'origin', 'host', 'transfer', 'media', 'length-invalid', 'length-zero'])
def test_early_rejections_with_unread_payload_still_deliver_status(server, headers, status):
    received, reply = exchange(server, 'POST', 'x' * 131072, headers)
    assert received == status and isinstance(reply['message'], str)
    assert exchange(server)[0] == 200


def open_headers_only(server):
    peer = socket.create_connection(('127.0.0.1', server.server_port), timeout=5)
    request = (f'POST /api/job HTTP/1.0\r\nHost: 127.0.0.1:{server.server_port}\r\n'
               f'Authorization: Bearer {server.token}\r\nContent-Type: application/json\r\n'
               'Content-Length: 999999999999\r\n\r\n')
    peer.sendall(request.encode('ascii'))
    return peer


def read_early_response(peer):
    wire = bytearray()
    while True:
        block = peer.recv(4096)
        if not block:
            break
        wire.extend(block)
    header, body = bytes(wire).split(b'\r\n\r\n', 1)
    assert header.startswith(b'HTTP/1.0 413 ')
    assert '256 KiB' in json.loads(body)['message']


def test_stalled_rejected_peer_gets_complete_response_and_bounded_handler_exit(server):
    peer = open_headers_only(server)
    try:
        read_early_response(peer)
        # Keep the sending side open: cleanup must not wait indefinitely for EOF
        # or for the enormous declared body. The queue observes handler exit.
        assert server.finished.get(timeout=3) is True
        assert exchange(server)[0] == 200
    finally:
        peer.close()


def test_continuously_sending_rejected_peer_cannot_hold_handler(server):
    peer = open_headers_only(server)
    try:
        read_early_response(peer)
        started = time.monotonic()
        sent = 0
        try:
            while sent < 8 * 1024 * 1024:
                peer.sendall(b'x' * 65536)
                sent += 65536
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        assert server.finished.get(timeout=3) is True
        assert sent < 8 * 1024 * 1024
        assert time.monotonic() - started < 3
        assert exchange(server)[0] == 200
    finally:
        peer.close()


def test_aborted_rejected_peer_does_not_prevent_followup(server):
    peer = open_headers_only(server)
    read_early_response(peer)
    peer.close()
    assert server.finished.get(timeout=3) is True
    assert exchange(server)[0] == 200


def test_portable_smoke_checks_rejection_against_real_host(server):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'packaging'))
    from smoke import check_rejected_request
    result = check_rejected_request(server.origin, server.token)
    assert result == dict(body_bytes=270009, requested_send_buffer=4096,
                          statuses=[413, 413, 413])
    assert exchange(server)[1]['status'] == 'idle'
