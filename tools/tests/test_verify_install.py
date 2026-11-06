"""Reject stale same-version artifacts, missing files, and leftover modules."""
import importlib.util
from pathlib import Path
import zipfile
import pytest

spec = importlib.util.spec_from_file_location('verify_install', Path(__file__).resolve().parents[1] / 'verify_install.py')
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


@pytest.fixture
def installation(tmp_path):
    root = tmp_path / 'installed'
    root.mkdir()
    wheel = tmp_path / 'sample-0.1.0-py3-none-any.whl'
    files = {'sample/__init__.py': b'VALUE = 42\n',
             'sample-0.1.0.dist-info/METADATA': b'Name: sample\nVersion: 0.1.0\n',
             'sample-0.1.0.dist-info/RECORD': b'wheel record'}
    with zipfile.ZipFile(wheel, 'w') as z:
        for path, data in files.items():
            z.writestr(path, data)
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    (root / 'sample-0.1.0.dist-info/RECORD').write_text('installer rewrote record')
    return wheel, root


def check(pair):
    return verify.compare_payload(*pair, name='sample', version='0.1.0')


def test_exact_payload_with_installer_record(installation):
    assert check(installation) == 2


def test_old_code_with_identical_version_is_rejected(installation):
    (installation[1] / 'sample/__init__.py').write_text('VALUE = 41\n')
    with pytest.raises(ValueError, match='payload differs'):
        check(installation)


def test_missing_file_is_rejected(installation):
    (installation[1] / 'sample/__init__.py').unlink()
    with pytest.raises(ValueError, match='payload differs'):
        check(installation)


def test_leftover_module_is_rejected(installation):
    (installation[1] / 'sample/obsolete.py').write_text('VALUE = 0\n')
    with pytest.raises(ValueError, match='unexpected installed Python'):
        check(installation)


def test_different_version_is_rejected(installation):
    with pytest.raises(ValueError, match='name/version'):
        verify.compare_payload(*installation, name='sample', version='0.2.0')


def test_shadowed_import_is_rejected(installation, monkeypatch):
    from types import SimpleNamespace
    wheel, root = installation
    monkeypatch.setattr(verify, 'PACKAGES', ('sample',))
    monkeypatch.setattr(verify.sys, 'prefix', str(root.parent))
    monkeypatch.setattr(verify.metadata, 'distribution', lambda name: SimpleNamespace(
        version='0.1.0', locate_file=lambda path: root / path))
    monkeypatch.setattr(verify.importlib, 'import_module', lambda name: SimpleNamespace(
        __file__=str(root.parent / 'checkout' / 'sample' / '__init__.py')))
    with pytest.raises(ValueError, match='shadowed'):
        verify.audit(wheel.parent)


def test_multiple_same_name_wheels_are_rejected(installation, monkeypatch):
    wheel, root = installation
    (wheel.parent / 'sample-0.2.0-py3-none-any.whl').write_bytes(wheel.read_bytes())
    monkeypatch.setattr(verify, 'PACKAGES', ('sample',))
    with pytest.raises(ValueError, match='exactly one wheel'):
        verify.audit(wheel.parent)
