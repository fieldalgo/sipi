"""A failed executable launch must retain evidence without passing the smoke gate."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys


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
