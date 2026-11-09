"""Independent miniature installed inventories exercise snapshot contracts."""
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'desktop'))
import artifacts


@pytest.fixture
def inventory(tmp_path, monkeypatch):
    files = {'demo/__init__.py': b'value = 1\n', 'demo/solver.py': b'result = 2\n',
             'demo.libs/library.so': b'fixture native bytes',
             'demo-1.2.dist-info/METADATA': b'Name: demo\nVersion: 1.2\n',
             'demo-1.2.dist-info/RECORD': b'installer paths',
             'demo-1.2.dist-info/direct_url.json': b'{"url":"local-only"}',
             'demo/__pycache__/solver.pyc': b'cache'}
    for name, content in files.items():
        path = tmp_path/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    dist = SimpleNamespace(version='1.2', files=list(reversed(files)),
                           locate_file=lambda value: tmp_path/value)
    module = SimpleNamespace(__file__=str(tmp_path/'demo/__init__.py'))
    monkeypatch.setattr(artifacts, 'COMPONENTS', (('demo', 'demo'),))
    monkeypatch.setattr(artifacts.metadata, 'distribution', lambda name: dist)
    monkeypatch.setattr(artifacts.importlib, 'import_module', lambda name: module)
    return tmp_path, dist, module, files


def test_independent_exact_manifest_and_digest(inventory):
    root, dist, module, files = inventory
    result = artifacts.capture_installed_artifacts()
    manifest = json.loads(result['manifest_text'])
    expected = dict(schema='sipi.installed-component/1', policy='distribution-files/1',
        component='demo', version='1.2', import_path='demo/__init__.py', files=[
            dict(path=name, bytes=len(files[name]), sha256=hashlib.sha256(files[name]).hexdigest())
            for name in sorted(['demo/__init__.py', 'demo/solver.py', 'demo.libs/library.so',
                                'demo-1.2.dist-info/METADATA'])])
    assert manifest['components'] == [expected]
    encoded = json.dumps(expected, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    assert result['artifacts'] == [dict(component='demo', version='1.2', kind='runtime',
                                       sha256=hashlib.sha256(encoded.encode()).hexdigest())]
    assert str(root) not in result['manifest_text'] and 'local-only' not in result['manifest_text']
    dist.files.reverse()
    assert artifacts.capture_installed_artifacts() == result
    (root/'demo-1.2.dist-info/RECORD').write_bytes(b'other install')
    (root/'demo/__pycache__/solver.pyc').write_bytes(b'new cache')
    dist.files.append('../../../bin/demo')  # Excluded external console wrapper is not read.
    assert artifacts.capture_installed_artifacts() == result


def test_actual_payload_mutation_changes_only_its_fingerprint(inventory):
    root, dist, module, files = inventory
    before = artifacts.capture_installed_artifacts()
    (root/'demo/solver.py').write_bytes(b'result = 3\n')
    after = artifacts.capture_installed_artifacts()
    assert before['artifacts'] != after['artifacts']
    a = json.loads(before['manifest_text'])['components'][0]['files']
    b = json.loads(after['manifest_text'])['components'][0]['files']
    assert [left['path'] for left, right in zip(a,b) if left != right] == ['demo/solver.py']


@pytest.mark.parametrize('bad', ['', '/absolute.py', 'C:/module.py', 'demo\\solver.py',
                                 './demo/solver.py', 'demo//solver.py', 'demo/solver.py'])
def test_bad_or_duplicate_paths_reject(inventory, bad):
    root, dist, module, files = inventory
    dist.files.append(bad)
    with pytest.raises(ValueError, match='paths'):
        artifacts.capture_installed_artifacts()


@pytest.mark.parametrize('name', ['demo/solver.py', 'demo.libs/library.so'])
def test_missing_payload_rejects(inventory, name):
    root, dist, module, files = inventory
    (root/name).unlink()
    with pytest.raises(OSError):
        artifacts.capture_installed_artifacts()


@pytest.mark.parametrize('suffix', ['.py', '.so', '.pyd', '.dll', '.dylib'])
def test_unlisted_package_module_rejects(inventory, suffix):
    root, dist, module, files = inventory
    (root/('demo/extra'+suffix)).write_bytes(b'extra payload')
    with pytest.raises(ValueError, match='unlisted'):
        artifacts.capture_installed_artifacts()


def test_source_shadow_and_missing_inventory_reject(inventory):
    root, dist, module, files = inventory
    module.__file__ = str(root/'other/__init__.py')
    with pytest.raises(ValueError, match='Imported module'):
        artifacts.capture_installed_artifacts()
    module.__file__ = None
    with pytest.raises(ValueError, match='origin'):
        artifacts.capture_installed_artifacts()
    dist.files = None
    with pytest.raises(ValueError, match='no distribution'):
        artifacts.capture_installed_artifacts()


@pytest.mark.parametrize('values', [dict(max_files=True), dict(max_files=0), dict(max_files=2.0),
                                    dict(max_bytes=False), dict(max_bytes=-1)])
def test_invalid_limits_reject(inventory, values):
    with pytest.raises(ValueError, match='positive integer'):
        artifacts.capture_installed_artifacts(**values)


def test_exact_limits_and_refusal(inventory):
    root, dist, module, files = inventory
    included = [k for k in files if '__pycache__' not in k and not k.endswith(('RECORD','direct_url.json'))]
    size = sum(len(files[k]) for k in included)
    result = artifacts.capture_installed_artifacts(max_files=len(dist.files), max_bytes=size)
    assert result['artifacts']
    with pytest.raises(ValueError, match='byte limit'):
        artifacts.capture_installed_artifacts(max_bytes=size-1)
    with pytest.raises(ValueError, match='file limit'):
        artifacts.capture_installed_artifacts(max_files=len(dist.files)-1)


def test_package_scan_is_bounded(inventory):
    root, dist, module, files = inventory
    for index in range(10):
        (root/f'demo/extra{index}.txt').write_bytes(b'data')
    with pytest.raises(ValueError, match='scan exceeds'):
        artifacts.capture_installed_artifacts(max_files=len(dist.files))


def test_changed_file_during_read_rejects(inventory, monkeypatch):
    root, dist, module, files = inventory
    target = root/'demo/solver.py'
    original = Path.open
    class ChangingReader:
        def __init__(self, stream): self.stream, self.changed = stream, False
        def __enter__(self): return self
        def __exit__(self, *args): self.stream.close()
        def read(self, size):
            data = self.stream.read(size)
            if data and not self.changed:
                self.changed = True
                with original(target, 'ab') as output: output.write(b'changed')
            return data
    def open_file(path, *args, **kwargs):
        stream = original(path, *args, **kwargs)
        return ChangingReader(stream) if path == target and args == ('rb',) else stream
    monkeypatch.setattr(Path, 'open', open_file)
    with pytest.raises(ValueError, match='changed|byte limit'):
        artifacts.capture_installed_artifacts(max_bytes=1000)


@pytest.mark.parametrize('version', ['', 'with space', '../source', None])
def test_invalid_version_rejects(inventory, version):
    root, dist, module, files = inventory
    dist.version = version
    with pytest.raises(ValueError, match='version'):
        artifacts.capture_installed_artifacts()
