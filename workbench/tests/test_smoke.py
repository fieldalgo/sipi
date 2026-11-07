"""A failed executable launch must retain evidence without passing the smoke gate."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import importlib.util
import queue
import threading


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
