"""Browser record declarations require a checked, matching source manifest."""
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'desktop'))
import browser_recording as candidate
from engine import execute
from sipi import LumpedNetworkDocument
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord

VERSIONS = {'sipi':'0.1.0', 'galerkin':'0.0.2', 'meshine':'0.0.2', 'array-api-compat':'1.16.0',
            'numpy':'2.2.5', 'scipy':'1.14.1', 'shapely':'2.0.7'}


@pytest.fixture
def manifest(monkeypatch):
    # Synthetic source descriptors only; actual downloads are covered in browser acceptance.
    monkeypatch.setattr(candidate.platform, 'python_version', lambda: '3.13.2')
    monkeypatch.setattr(candidate.metadata, 'version', lambda name: VERSIONS[name])
    files = {}
    def add(path, data=b'fixture'):
        files[path] = dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), source='test-only')
    for name in ('engine.py','artifacts.py','recording.py','browser_recording.py'):
        add(name, (Path(candidate.__file__).parent/name).read_bytes())
    for name in ('pyodide.js','pyodide.asm.js','pyodide.asm.wasm','python_stdlib.zip',
                 'pyodide-lock.json','LICENSE-PYODIDE.txt','LICENSE-PYTHON.txt'):
        add('runtime/'+name)
    add('notices.txt')
    wheels = []
    for name in ('sipi','galerkin','meshine','array-api-compat'):
        path = 'wheels/'+name.replace('-','_')+'-'+VERSIONS[name]+'-py3-none-any.whl'
        add(path);wheels.append(path)
    packages = {}
    for name in ('numpy','scipy','shapely'):
        filename = name+'-'+VERSIONS[name]+'-cp313-cp313-pyemscripten_2025_0_wasm32.whl'
        add('runtime/'+filename)
        packages[name] = dict(version=VERSIONS[name], file_name=filename,
                              sha256=files['runtime/'+filename]['sha256'], native_files=[])
    return dict(pyodide='0.29.5', engine_commit='1'*40, shared_commit='2'*40, files=files,
        wheels=wheels, packages=packages,
        python_abi=dict(abi_version='2025_0', arch='wasm32', platform='emscripten_4_0_9', python='3.13.2'))


def prepared():
    return SavedExecutionRequest(LumpedNetworkDocument([0,1e9], resistance=10).dumps(), max_input_bytes=200*1024)


def test_raw_manifest_declarations_and_unique_records(manifest):
    text = json.dumps(manifest, indent=2)
    provider = candidate.BrowserSourceRecorder(text)
    request = prepared()
    first = provider(request)
    a = SavedExecutionRecord.loads(first['record_text'])
    b = SavedExecutionRecord.loads(provider(request)['record_text'])
    assert a.receipt == b.receipt == request.run() and a.run_id != b.run_id
    assert first['runtime_manifest_text'] == text
    items = {row['component']:row for row in a.artifacts['items']}
    assert set(items) == set(VERSIONS) | {'sipi-browser-runtime'}
    for name, row in items.items():
        if name == 'sipi-browser-runtime':
            assert row == dict(component=name, version='0.29.5', kind='runtime', sha256=hashlib.sha256(text.encode()).hexdigest())
        else:
            assert row['kind'] == 'wheel' and row['version'] == VERSIONS[name]
    before = provider(request)['runtime_manifest_text']
    manifest['engine_commit'] = '3'*40
    assert provider(request)['runtime_manifest_text'] == before
    with pytest.raises(FrozenInstanceError): provider._manifest_text = '{}'


def test_host_provider_only_and_single_execution(manifest, monkeypatch):
    provider = candidate.BrowserSourceRecorder(json.dumps(manifest))
    text = prepared().source_text
    original = SavedExecutionRequest.run
    calls = []
    def run(self): calls.append(self.request_id); return original(self)
    monkeypatch.setattr(SavedExecutionRequest, 'run', run)
    out = execute(dict(action='saved-record', text=text), record_provider=provider)
    assert len(calls) == 1 and SavedExecutionRecord.loads(out['record_text']).prepare().source_text == text
    with pytest.raises(ValueError): execute(dict(action='saved-record', text=text, record_provider={}))
    with pytest.raises(ValueError, match='callable'): execute(dict(action='saved-record', text=text), record_provider={})


@pytest.mark.parametrize('bad', ['{}', 'null', '{"files":{},"files":{}}', '{"x":NaN}', '{"x":1e999}', None])
def test_malformed_manifest_rejects(bad):
    with pytest.raises(ValueError): candidate.BrowserSourceRecorder(bad)


@pytest.mark.parametrize('problem', ['runtime-version','short-commit','abi','missing-helper','missing-runtime',
    'path','size','digest','duplicate-wheel','missing-wheel','loaded-version','package-hash',
    'package-version','helper-hash','extra-package','total-size'])
def test_mismatched_manifest_refused_before_execution(manifest, monkeypatch, problem):
    if problem == 'runtime-version': manifest['pyodide'] = '0.0.0'
    elif problem == 'short-commit': manifest['engine_commit'] = '123'
    elif problem == 'abi': manifest['python_abi']['python'] = '3.13.1'
    elif problem == 'missing-helper': del manifest['files']['recording.py']
    elif problem == 'missing-runtime': del manifest['files']['runtime/pyodide.asm.wasm']
    elif problem == 'path': manifest['files']['../outside.py'] = manifest['files']['engine.py']
    elif problem == 'size': manifest['files']['engine.py']['bytes'] = True
    elif problem == 'digest': manifest['files']['engine.py']['sha256'] = 'z'*64
    elif problem == 'duplicate-wheel': manifest['wheels'][1] = manifest['wheels'][0]
    elif problem == 'missing-wheel': manifest['wheels'].pop()
    elif problem == 'loaded-version': monkeypatch.setattr(candidate.metadata, 'version', lambda name:'0.0.0')
    elif problem == 'package-hash': manifest['packages']['numpy']['sha256'] = '0'*64
    elif problem == 'package-version': manifest['packages']['numpy']['version'] = '2.5.4'
    elif problem == 'helper-hash': manifest['files']['engine.py']['sha256'] = '0'*64
    elif problem == 'extra-package': manifest['packages']['other'] = {}
    elif problem == 'total-size':
        for row in manifest['files'].values(): row['bytes'] = 64*1024*1024
    monkeypatch.setattr(SavedExecutionRequest, 'run', lambda *args: pytest.fail('invalid manifest executed'))
    with pytest.raises(ValueError): candidate.BrowserSourceRecorder(json.dumps(manifest))


def test_helper_change_during_execution_refuses_record(manifest, monkeypatch):
    provider = candidate.BrowserSourceRecorder(json.dumps(manifest))
    original = SavedExecutionRequest.run
    def changed(self):
        out = original(self)
        monkeypatch.setattr(candidate, '_helpers', lambda files: (_ for _ in ()).throw(ValueError('changed helper')))
        return out
    monkeypatch.setattr(SavedExecutionRequest, 'run', changed)
    with pytest.raises(ValueError, match='changed helper'): provider(prepared())


def test_oversized_manifest_refuses():
    with pytest.raises(ValueError, match='1 MiB'):
        candidate.BrowserSourceRecorder(' '*(1024*1024+1))
