"""Synthetic bundle contract checks; actual Windows execution is a separate gate."""
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'desktop'))
import engine
import frozen_recording as candidate
from sipi import LumpedNetworkDocument
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    root = tmp_path/'bundle with space 한글'
    root.mkdir()
    (root/'ui').mkdir()
    (root/'python313.dll').write_bytes(b'synthetic DLL; not Windows execution evidence')
    (root/'program.exe').write_bytes(b'synthetic executable')
    (root/'ui/notices.txt').write_text('synthetic notice')
    build = dict(engine_commit='1'*40, workbench_commit='2'*40, shared_commit='3'*40,
        source_wheels=[dict(name=name, version=version, wheel=f'{name}-{version}-py3-none-any.whl',
                           sha256=str(i)*64, files_checked=10) for i, (name, version) in enumerate(
                               [('sipi', '0.1.0'), ('galerkin', '0.0.2'), ('meshine', '0.0.2')], 1)])
    (root/'ui/build-info.json').write_text(json.dumps(build))
    marker = SimpleNamespace(major=2, minor=8, micro=10, standalone=True, onefile=True)
    monkeypatch.setattr(candidate, '__compiled__', marker, raising=False)
    monkeypatch.setattr(candidate, '__file__', str(root/'frozen_recording.py'))
    # Keep global sys/platform unchanged for other tests and pytest itself.
    monkeypatch.setattr(candidate, 'sys', SimpleNamespace(platform='win32', executable=str(root/'program.exe')))
    monkeypatch.setattr(candidate, 'platform', SimpleNamespace(python_version=lambda: '3.13.17', machine=lambda: 'AMD64'))
    return root, build, marker


def prepared():
    return SavedExecutionRequest(LumpedNetworkDocument([0, 1e9], resistance=10).dumps(), max_input_bytes=200*1024)


def test_exact_all_files_no_source_wheel_artifact_and_location_independent(bundle, tmp_path, monkeypatch):
    root, build, marker = bundle
    out = candidate.capture_frozen_artifacts()
    manifest = json.loads(out['manifest_text'])
    assert manifest['schema'] == 'sipi.frozen-runtime/1'
    assert manifest['build'] == build and manifest['executable'] == 'program.exe'
    expected = [dict(path=p.relative_to(root).as_posix(), bytes=p.stat().st_size,
                     sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                for p in sorted(root.rglob('*')) if p.is_file()]
    assert manifest['files'] == expected
    assert [row['kind'] for row in out['artifacts']] == ['executable', 'runtime']
    assert out['artifacts'][0]['sha256'] == hashlib.sha256((root/'program.exe').read_bytes()).hexdigest()
    assert out['artifacts'][1]['sha256'] == hashlib.sha256(out['manifest_text'].encode()).hexdigest()
    assert str(root) not in out['manifest_text']
    moved = tmp_path/'renamed'
    root.rename(moved)
    monkeypatch.setattr(candidate, '__file__', str(moved/'frozen_recording.py'))
    candidate.sys.executable = str(moved/'program.exe')
    assert candidate.capture_frozen_artifacts() == out
    assert not (moved/'frozen_recording.py').exists()  # Compiled helper is in the EXE.


@pytest.mark.parametrize('problem', ['uncompiled', 'os', 'python', 'machine', 'compiler', 'onefile', 'standalone', 'executable', 'helper'])
def test_runtime_boundary_refuses(bundle, monkeypatch, problem):
    root, _, marker = bundle
    if problem == 'uncompiled': monkeypatch.delattr(candidate, '__compiled__')
    elif problem == 'os': candidate.sys.platform = 'linux'
    elif problem == 'python': candidate.platform.python_version = lambda: '3.12.14'
    elif problem == 'machine': candidate.platform.machine = lambda: 'ARM64'
    elif problem == 'compiler': marker.micro = 9
    elif problem in {'onefile', 'standalone'}: setattr(marker, problem, False)
    elif problem == 'executable': candidate.sys.executable = str(root.parent/'outside.exe')
    elif problem == 'helper': monkeypatch.setattr(candidate, '__file__', str(root/'nested/helper.py'))
    with pytest.raises(ValueError): candidate.capture_frozen_artifacts()


def test_same_resolved_payload_parent_accepts_a_lexical_alias(bundle):
    root, _, _ = bundle
    expected = candidate.capture_frozen_artifacts()
    (root/'nested').mkdir()
    candidate.sys.executable = str(root/'nested'/'..'/'program.exe')
    assert candidate.capture_frozen_artifacts() == expected


@pytest.mark.parametrize('name', ['program.exe', 'ui/build-info.json', 'ui/notices.txt'])
def test_required_payloads(bundle, name):
    (bundle[0]/name).unlink()
    with pytest.raises(ValueError, match='omits'): candidate.capture_frozen_artifacts()


@pytest.mark.parametrize('kwargs', [dict(max_entries=1), dict(max_bytes=1), dict(max_entries=True),
                                  dict(max_bytes=0), dict(max_entries=1.5)])
def test_snapshot_limits(bundle, kwargs):
    with pytest.raises(ValueError): candidate.capture_frozen_artifacts(**kwargs)


@pytest.mark.parametrize('problem', ['duplicate-key', 'nan', 'commit', 'missing', 'wheel-count', 'duplicate-wheel',
                                  'version', 'wheel-path', 'sha', 'files-bool', 'extra', 'large'])
def test_invalid_build_info(bundle, problem):
    root, build, _ = bundle
    if problem == 'duplicate-key': text = '{"engine_commit":"x","engine_commit":"y"}'
    elif problem == 'nan': text = '{"value":NaN}'
    elif problem == 'large': text = ' '* (1024*1024+1)
    else:
        if problem == 'commit': build['engine_commit'] = 'short'
        elif problem == 'missing': del build['source_wheels']
        elif problem == 'wheel-count': build['source_wheels'].pop()
        elif problem == 'duplicate-wheel': build['source_wheels'][1] = build['source_wheels'][0]
        elif problem == 'version':
            build['source_wheels'][0].update(version='99', wheel='sipi-99-py3-none-any.whl')
        elif problem == 'wheel-path': build['source_wheels'][0]['wheel'] = '../source.whl'
        elif problem == 'sha': build['source_wheels'][0]['sha256'] = 'x'*64
        elif problem == 'files-bool': build['source_wheels'][0]['files_checked'] = True
        elif problem == 'extra': build['unexpected'] = 1
        text = json.dumps(build)
    (root/'ui/build-info.json').write_text(text)
    with pytest.raises(ValueError): candidate.capture_frozen_artifacts()


def test_link_and_directory_link_refused(bundle, tmp_path):
    root = bundle[0]
    # Windows may disallow unprivileged symlink creation. Junction/reparse
    # attributes are tested independently without needing link privileges.
    if sys.platform == 'win32': return
    outside = tmp_path/'outside'; outside.mkdir(); (outside/'x').write_text('x')
    for target in [outside/'x', outside]:
        link = root/'link'; link.symlink_to(target, target_is_directory=target.is_dir())
        try:
            with pytest.raises(ValueError, match='links and reparse'): candidate.capture_frozen_artifacts()
        finally: link.unlink()


def test_windows_reparse_attribute_refused(bundle, monkeypatch):
    original = Path.lstat
    def info(path):
        result = original(path)
        return SimpleNamespace(st_mode=result.st_mode, st_file_attributes=0x400) if path.name == 'python313.dll' else result
    monkeypatch.setattr(Path, 'lstat', info)
    with pytest.raises(ValueError, match='links and reparse'): candidate.capture_frozen_artifacts()


def test_file_changes_during_hash_and_new_entry_during_scan(bundle, monkeypatch):
    root = bundle[0]
    original = candidate._regular
    calls = []
    def changing(path):
        if path.name == 'program.exe':
            calls.append(1)
            if len(calls) == 3: path.write_bytes(b'changed')
        return original(path)
    with monkeypatch.context() as patch:
        patch.setattr(candidate, '_regular', changing)
        with pytest.raises(ValueError, match='changed during capture'): candidate.capture_frozen_artifacts()
    snapshot = candidate._snapshot
    def adding(path, budget):
        row = snapshot(path, budget)
        (root/'new.dat').write_bytes(b'new')
        return row
    monkeypatch.setattr(candidate, '_snapshot', adding)
    with pytest.raises(ValueError, match='entries changed'): candidate.capture_frozen_artifacts()


def test_raw_record_identity_project_roundtrip_and_single_solve(bundle, monkeypatch):
    original = SavedExecutionRequest.run
    calls = []
    def run(self): calls.append('run'); return original(self)
    monkeypatch.setattr(SavedExecutionRequest, 'run', run)
    request = prepared()
    first = candidate.run_recorded_frozen(request)
    assert calls == ['run']
    a = SavedExecutionRecord.loads(first['record_text'])
    b = SavedExecutionRecord.loads(candidate.run_recorded_frozen(request)['record_text'])
    assert a.run_id != b.run_id and a.receipt == b.receipt
    assert a.prepare().source_text == request.source_text
    project = SavedProject(request, project_id='p', design_id='a', title='Test', label='A')
    out = engine.execute(dict(action='project-attach', project_text=project.dumps(), design_id='a',
                              record_text=a.dumps(), select=True))
    assert SavedProject.loads(out['project_text']).current_record('a').dumps() == a.dumps()


@pytest.mark.parametrize('mutation', ['payload', 'new-file', 'build'])
def test_changed_bundle_refuses_record_after_solve(bundle, monkeypatch, mutation):
    original = SavedExecutionRequest.run
    calls = []
    def run(self):
        calls.append('run'); result = original(self)
        path = {'payload': 'program.exe', 'new-file': 'new.dat', 'build': 'ui/build-info.json'}[mutation]
        with (bundle[0]/path).open('ab') as stream: stream.write(b' ')
        return result
    monkeypatch.setattr(SavedExecutionRequest, 'run', run)
    with pytest.raises(RuntimeError, match='no record'): candidate.run_recorded_frozen(prepared())
    assert calls == ['run']


def test_original_solver_exception_and_admission_before_capture(bundle, monkeypatch):
    original = ArithmeticError('original solver failure')
    def fail(self): raise original
    monkeypatch.setattr(SavedExecutionRequest, 'run', fail)
    with pytest.raises(ArithmeticError) as error: candidate.run_recorded_frozen(prepared())
    assert error.value is original
    monkeypatch.setattr(candidate, 'capture_frozen_artifacts', lambda: pytest.fail('capture before admission'))
    for value in [None, {}, SavedExecutionRequest(prepared().source_text, max_evaluations=129)]:
        with pytest.raises(ValueError): candidate.run_recorded_frozen(value)


def test_compiled_adapter_routes_only_host_context_and_never_falls_back(bundle, monkeypatch):
    monkeypatch.setattr(engine, '__compiled__', bundle[2], raising=False)
    text = prepared().source_text
    out = engine.execute(dict(action='saved-record', text=text))
    assert json.loads(out['runtime_manifest_text'])['schema'] == 'sipi.frozen-runtime/1'
    monkeypatch.delattr(candidate, '__compiled__')
    with pytest.raises(ValueError, match='onefile runtime'): engine.execute(dict(action='saved-record', text=text))
    for key in ['artifacts', 'run_id', 'runtime_manifest_text', 'record_provider']:
        with pytest.raises(ValueError, match='optional complete controls'): engine.execute(dict(action='saved-record', text=text, **{key: 'injected'}))
    assert engine.execute(dict(action='saved-analyze', text=text))['execution']['status'] == 'complete'


def test_external_smoke_checks_real_record_structure_and_independent_files(bundle):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'packaging'))
    from smoke import verify_recording
    request = prepared()
    result = candidate.run_recorded_frozen(request)
    expected = request.run()['execution']
    checked = verify_recording(result, bundle[0], bundle[1], expected)
    assert checked == dict(independently_checked_files=4, unpacked_executable='program.exe')
    (bundle[0]/'python313.dll').write_bytes(b'mutated externally')
    with pytest.raises(AssertionError): verify_recording(result, bundle[0], bundle[1], expected)


def test_output_growth_is_refused_without_truncating(bundle):
    text = prepared().source_text
    request = SavedExecutionRequest(text+' '*(199*1024-len(text.encode())), max_input_bytes=200*1024)
    with pytest.raises(ValueError, match='record.*byte|record.*limit|record.*large'):
        candidate.run_recorded_frozen(request)


def test_missing_payload_refuses_before_solve(bundle, monkeypatch):
    (bundle[0]/'program.exe').unlink()
    monkeypatch.setattr(SavedExecutionRequest, 'run', lambda self: pytest.fail('unidentified solve'))
    with pytest.raises(ValueError, match='omits'): candidate.run_recorded_frozen(prepared())
