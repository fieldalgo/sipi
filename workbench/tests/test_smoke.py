"""A failed executable launch must retain evidence without passing the smoke gate."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import importlib.util
import queue
import threading
from types import SimpleNamespace

import pytest


def smoke_module():
    path = Path(__file__).resolve().parents[1] / 'packaging' / 'smoke.py'
    spec = importlib.util.spec_from_file_location('sipi_candidate_smoke_cleanup', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_cleanup_preserves_primary_failure_but_fails_an_otherwise_successful_run(monkeypatch):
    module = smoke_module()
    def cleanup():
        raise PermissionError('locked synthetic payload')
    monkeypatch.setattr(module.tempfile, 'TemporaryDirectory', lambda **kw: SimpleNamespace(name='synthetic', cleanup=cleanup))
    report = {}
    with pytest.raises(AssertionError, match='original recording failure'):
        with module.candidate_directory(report):
            raise AssertionError('original recording failure')
    assert report['directory_cleanup_error'] == {'type':'PermissionError', 'message':'locked synthetic payload'}
    with pytest.raises(PermissionError, match='locked synthetic payload'):
        with module.candidate_directory({}):
            pass


def test_failure_teardown_requests_shutdown_before_any_process_kill(monkeypatch):
    module = smoke_module(); calls=[]
    process = SimpleNamespace(returncode=None, pid=123)
    process.poll = lambda: process.returncode
    def wait(timeout):
        assert calls == [('/api/shutdown', {})]
        process.returncode=0
    process.wait=wait
    process.kill=lambda: pytest.fail('graceful shutdown must not kill')
    monkeypatch.setattr(module.subprocess, 'run', lambda *a, **k: pytest.fail('must not kill process tree'))
    report={};module.stop_candidate(process, lambda *a: calls.append(a), report)
    assert report == {'failure_shutdown':'graceful'} and process.returncode == 0


@pytest.mark.parametrize('available', [True, False])
def test_unresponsive_windows_candidate_stops_only_its_owned_tree(monkeypatch, available):
    module=smoke_module();calls=[];process=SimpleNamespace(returncode=None,pid=456)
    process.poll=lambda: process.returncode
    process.kill=lambda: pytest.fail('outer-only kill leaves child DLL locks')
    def request(*args):
        raise OSError('shutdown unavailable')
    def run(command, **kwargs):
        calls.append((command,kwargs));process.returncode=1
        return SimpleNamespace(returncode=0)
    process.wait=lambda timeout: 1
    monkeypatch.setattr(module,'sys',SimpleNamespace(platform='win32'))
    monkeypatch.setattr(module.subprocess,'run',run)
    report={};module.stop_candidate(process,request if available else None,report)
    assert calls == [(['taskkill','/PID','456','/T','/F'], {'capture_output':True,'timeout':20})]
    assert report['failure_tree_stop_returncode'] == 0
    assert ('shutdown_error' in report) is available


def test_already_exited_candidate_does_not_target_a_reused_pid():
    module=smoke_module()
    module.stop_candidate(SimpleNamespace(poll=lambda: 0), lambda *a: pytest.fail('already exited'), {})


def test_rejected_executable_writes_failed_report(tmp_path):
    # Both Windows and POSIX reject this non-executable image. Exercise the real
    # copy/OS-launch/failure path without relying on an installed app's runtime.
    executable = tmp_path / 'invalid-program.exe'
    executable.write_bytes(b'This is intentionally not an executable image.\n')
    executable.chmod(0o700)
    script = Path(__file__).resolve().parents[1] / 'packaging' / 'smoke.py'
    completed = subprocess.run([sys.executable, str(script), str(executable)],
                               capture_output=True, text=True, timeout=30)
    assert completed.returncode != 0
    report = json.loads(executable.with_name('smoke.json').read_text(encoding='utf-8'))
    assert report['status'] == 'failed'
    assert report['phase'] == 'startup'
    assert report['error']['type'] == 'OSError'
    assert report['error']['message']
    assert 'process_returncode' not in report
    assert report['cases'] == []
    assert 'startup_seconds' not in report
    assert report['bytes'] == executable.stat().st_size
    assert report['executable_sha256'] == hashlib.sha256(executable.read_bytes()).hexdigest()


def test_early_process_failure_retains_bounded_redacted_diagnostics():
    path = Path(__file__).resolve().parents[1] / 'packaging' / 'smoke.py'
    spec = importlib.util.spec_from_file_location('sipi_candidate_smoke', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    child = subprocess.Popen([sys.executable, '-c',
        'import sys;print("http://127.0.0.1:12345/#token=secret-session");'
        'print("ModuleNotFoundError: startup diagnostic",file=sys.stderr);'
        'print("x"*70000);sys.exit(7)'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding='utf-8')
    ready, report = queue.Queue(), {}
    reader = threading.Thread(target=module.capture_output,args=(child.stdout,ready,report))
    reader.start(); child.wait(timeout=15); reader.join(timeout=5)
    assert not reader.is_alive() and child.returncode == 7
    child.stdout.close()
    assert 'ModuleNotFoundError: startup diagnostic' in report['process_output']
    assert 'secret-session' not in report['process_output']
    assert '#token=[redacted]' in report['process_output']
    assert report['process_output_truncated'] and len(report['process_output'])==65536
    assert 'secret-session' in ready.get_nowait()


def test_width_goal_helper_uses_real_host_and_retains_refinement():
    import http.client
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'desktop'))
    from main import Server
    module = smoke_module()
    server = Server(Path(__file__).resolve().parents[1] / 'ui')
    thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .05}, daemon=True)
    thread.start()
    def request(path, data=None):
        conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=30)
        payload = None if data is None else json.dumps(data)
        try:
            conn.request('GET' if data is None else 'POST', path, payload,
                {'Authorization': 'Bearer '+server.token, 'Content-Type': 'application/json'})
            response = conn.getresponse()
            assert response.status == (200 if data is None else 202)
            return response.read()
        finally:
            conn.close()
    try:
        result = module.check_width_goal(request)
        assert result['design']['history'][-1]['stage'] == 'refinement'
        assert result['design']['width'] == .5e-3
        assert abs(result['line']['z0']-50.216) < .6
    finally:
        server.job.cancel()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_unequal_pair_helper_uses_real_host_and_preserves_selected_geometry():
    import http.client
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'desktop'))
    from main import Server
    module = smoke_module()
    server = Server(Path(__file__).resolve().parents[1] / 'ui')
    thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .05}, daemon=True)
    thread.start()
    def request(path, data=None):
        conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=30)
        try:
            conn.request('GET' if data is None else 'POST', path,
                None if data is None else json.dumps(data),
                {'Authorization': 'Bearer '+server.token, 'Content-Type': 'application/json'})
            response = conn.getresponse()
            assert response.status == (200 if data is None else 202)
            return response.read()
        finally:
            conn.close()
    try:
        cases = module.check_unequal_pair_goals(request)
        assert [(x['template'], x['variable']) for x in cases] == [
            ('asymmetric_coupled_microstrip', 'left_width'),
            ('asymmetric_coupled_stripline', 'right_width')]
        assert all(x['selected_reanalysis_exact'] for x in cases)
    finally:
        server.job.cancel()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
