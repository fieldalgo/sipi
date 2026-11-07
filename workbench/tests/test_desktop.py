"""Real loopback lifecycle, input contract, engine equality and process cancellation."""

import http.client
import json
from pathlib import Path
import sys
import threading
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'desktop'))
from engine import execute
from main import Server
import sipi

UI = Path(__file__).resolve().parents[1] / 'ui'
INPUT = {'action': 'analyze', 'template': 'stripline',
         'parameters': {'width': .5e-3, 'plane_spacing': 1e-3, 'eps_r': 4}}


@pytest.fixture
def server():
    server = Server(UI)
    thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .05}, daemon=True)
    thread.start()
    yield server
    server.job.cancel()
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)


def call(server, method, path, value=None, *, authenticated=True, headers=None):
    conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=10)
    data = None if value is None else json.dumps(value)
    hdr = {'Content-Type': 'application/json'}
    if authenticated:
        hdr['Authorization'] = 'Bearer ' + server.token
    hdr.update(headers or {})
    conn.request(method, path, data, hdr)
    response = conn.getresponse()
    body = response.read()
    status = response.status
    conn.close()
    return status, json.loads(body) if body.startswith(b'{') else body


def finish(server):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        code, value = call(server, 'GET', '/api/job')
        assert code == 200
        if value['status'] != 'running':
            return value
        time.sleep(.1)
    pytest.fail('Calculation did not finish within 60 seconds')


def test_local_assets_and_api_authorization(server):
    assert call(server, 'GET', '/', authenticated=False)[0] == 200
    for path in ('/api/job', '/api/cancel', '/api/shutdown'):
        method = 'GET' if path == '/api/job' else 'POST'
        assert call(server, method, path, {} if method == 'POST' else None, authenticated=False)[0] == 403
    assert call(server, 'GET', '/', headers={'Host': 'evil.example'})[0] == 403
    assert call(server, 'POST', '/api/job', INPUT, headers={'Origin': 'https://evil.example'})[0] == 403
    assert call(server, 'POST', '/api/job', INPUT, headers={'Origin': 'null'})[0] == 403
    assert call(server, 'GET', '/../desktop/main.py')[0] == 404
    assert call(server, 'POST', '/api/job', {'x': 'x' * 270000})[0] == 413


def test_spawned_calculation_matches_native_and_roundtrips(server):
    assert call(server, 'POST', '/api/job', INPUT)[0] == 202
    assert call(server, 'POST', '/api/job', INPUT)[0] == 409
    completed = finish(server)
    assert completed['status'] == 'complete', completed
    result = completed['result']
    expected = sipi.stripline(**INPUT['parameters']).analyze()
    assert result['line']['z0'] == pytest.approx(expected.z0, rel=1e-12)
    assert result['line']['C'] == expected.C.tolist()
    assert set(result['document']['mesh']) == {'edge_size', 'far_size', 'grade', 'min_angle'}
    restored = execute({'action': 'analyze', 'document_text': json.dumps(result['document'])})
    assert restored['line'] == result['line']


def test_invalid_input_has_error_state_and_can_recover(server):
    bad = {**INPUT, 'parameters': {**INPUT['parameters'], 'width': -1}}
    assert call(server, 'POST', '/api/job', bad)[0] == 202
    result = finish(server)
    assert result['status'] == 'error'
    assert result['type'] == 'ValueError'
    assert call(server, 'POST', '/api/job', {**INPUT, 'action': 'document'})[0] == 202
    assert finish(server)['status'] == 'complete'


def test_cancellation_reaps_process_and_allows_another_job(server):
    assert call(server, 'POST', '/api/job', INPUT)[0] == 202
    process = server.job.process
    pid = process.pid
    assert pid is not None
    assert call(server, 'POST', '/api/cancel', {})[1]['status'] == 'cancelled'
    assert server.job.process is None
    with pytest.raises(ValueError, match='closed'):
        process.is_alive()
    assert call(server, 'POST', '/api/job', {**INPUT, 'action': 'document'})[0] == 202
    assert finish(server)['status'] == 'complete'


def test_import_rejects_duplicate_keys_and_nonfinite_values():
    for raw in ('{"schema":1,"schema":2}', '{"schema":NaN}'):
        with pytest.raises(ValueError):
            execute({'action': 'document', 'document_text': raw})


@pytest.mark.parametrize('name,parameters', [
    ('microstrip', {'width': .5e-3, 'substrate_height': 1e-3, 'eps_r': 4}),
    ('coupled_microstrip', {'width': .5e-3, 'gap': .2e-3, 'substrate_height': 1e-3, 'eps_r': 4}),
    ('grounded_coplanar', {'width': .5e-3, 'gap': .2e-3, 'ground_width': 1e-3, 'substrate_height': 1e-3, 'eps_r': 4}),
])
def test_adapter_templates_match_native(name, parameters):
    options = dict(edge_size=5e-6, far_size=.5e-3, grade=.2)
    result = execute({'action': 'analyze', 'template': name, 'parameters': parameters, 'mesh': options})
    native = getattr(sipi, name)(**parameters).analyze(**options)
    assert result['line']['C'] == native.C.tolist()
    assert result['line']['L'] == native.L.tolist()
