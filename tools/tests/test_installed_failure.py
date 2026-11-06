"""A failed launch must not leave a previous run's successful report."""
from pathlib import Path
import json
import runpy
import shutil
import subprocess
import sys
import pytest


def test_failed_launch_removes_previous_success_xml(tmp_path, monkeypatch):
    root = tmp_path / 'candidate'
    (root / 'tools').mkdir(parents=True)
    for name in ('tests', 'integration', '.validation'):
        (root / name).mkdir()
    (root / 'pyproject.toml').write_text('[tool.pytest.ini_options]\n')
    xml = root / '.validation' / 'installed.xml'
    xml.write_text('<testsuite failures="0" tests="598"/>')
    tools = Path(__file__).resolve().parents[1]
    for source in tools.glob('*.py'):
        shutil.copy2(source, root / 'tools' / source.name)
    monkeypatch.syspath_prepend(str(root / 'tools'))
    monkeypatch.setattr(sys, 'argv', ['check_installed.py', '--wheels', str(tmp_path)])
    def failed(*args, **kwargs):
        raise OSError('simulated interpreter launch failure')
    monkeypatch.setattr(subprocess, 'run', failed)
    with pytest.raises((OSError, SystemExit)):
        runpy.run_path(str(root / 'tools' / 'check_installed.py'), run_name='__main__')
    assert not xml.exists(), 'stale success XML survived a failed validation run'

    report = json.loads((root / ".validation" / "installed.json").read_text())
    assert report["status"] == "failed"
    assert report["phase"] == "artifact-audit"
    assert "simulated interpreter launch failure" in report["error"]


def test_missing_artifacts_fail_before_pytest_and_record_error(tmp_path):
    root = tmp_path / 'candidate'
    (root / 'tools').mkdir(parents=True)
    (root / '.validation').mkdir()
    tools = Path(__file__).resolve().parents[1]
    for source in tools.glob('*.py'):
        shutil.copy2(source, root / 'tools' / source.name)
    xml = root / '.validation' / 'installed.xml'
    xml.write_text('<testsuite failures="0"/>')
    result = subprocess.run([sys.executable, str(root / 'tools/check_installed.py'),
                             '--wheels', str(tmp_path / 'missing')],
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert not xml.exists()
    report = json.loads((root / '.validation/installed.json').read_text())
    assert report['status'] == 'failed'
    assert report['phase'] == 'artifact-audit'
    assert 'expected exactly one wheel' in report['stderr']
