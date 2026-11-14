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


def test_partition_runner_keeps_external_import_environment_and_fresh_reports(tmp_path, monkeypatch):
    root = tmp_path / 'candidate'
    (root / 'tools').mkdir(parents=True)
    for name in ('tests', 'integration'):
        (root / name).mkdir()
    (root / 'pyproject.toml').write_text('[tool.pytest.ini_options]\n')
    tools = Path(__file__).resolve().parents[1]
    for name in ('check_installed.py', 'verify_install.py', 'pytest_shard.py'):
        shutil.copy2(tools / name, root / 'tools' / name)
    monkeypatch.setenv('PYTHONPATH', str(root / 'poison-source'))
    monkeypatch.setattr(sys, 'argv', ['check_installed.py', '--wheels', str(tmp_path),
                                    '--shard-index', '1', '--shard-count', '3'])
    calls = []
    def observe(command, *, cwd, env, **kwargs):
        calls.append(command)
        assert cwd != root and root not in cwd.parents
        assert 'PYTHONPATH' not in env
        assert env['OPENPHYSICS_REQUIRE_CROSSCHECK'] == '1'
        if len(calls) == 1:
            return subprocess.CompletedProcess(command, 0, stdout='[]')
        assert (cwd / 'tools/pytest_shard.py').read_bytes() == (tools / 'pytest_shard.py').read_bytes()
        assert (cwd / 'tests').is_dir() and (cwd / 'integration').is_dir()
        assert '-p' in command and 'tools.pytest_shard' in command
        assert '--sipi-shard-index=1' in command and '--sipi-shard-count=3' in command
        assert '--sipi-shard-report=' + str(root / '.validation/installed-shard.json') in command
        # Preserve an actual failing subprocess's status; successful audit is not regression success.
        raise subprocess.CalledProcessError(1, command)
    monkeypatch.setattr(subprocess, 'run', observe)
    with pytest.raises(subprocess.CalledProcessError):
        runpy.run_path(str(root / 'tools/check_installed.py'), run_name='__main__')
    report = json.loads((root / '.validation/installed.json').read_text())
    assert len(calls) == 2 and report['status'] == 'failed' and report['phase'] == 'regression'
    assert report['partition'] == {'index': 1, 'count': 3}


@pytest.mark.parametrize('options', [['--shard-index=0'], ['--shard-count=3'],
                                   ['--shard-index=3', '--shard-count=3']])
def test_invalid_installed_partition_options_do_not_launch(tmp_path, options):
    result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'check_installed.py'),
                             '--wheels', str(tmp_path), *options], capture_output=True, text=True)
    assert result.returncode == 2 and 'provide 0 <= shard-index' in result.stderr
