"""Recorded execution binds one solve to unchanged installed-file evidence."""
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'desktop'))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tests' / 'sipi'))
import recording
from engine import execute
from sipi import LumpedNetworkDocument
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject


def prepared():
    return SavedExecutionRequest(LumpedNetworkDocument([0, 1e9], resistance=10).dumps(),
                                 max_input_bytes=200*1024)


@pytest.fixture
def capture(monkeypatch):
    # Explicit synthetic metadata for sequencing tests, not installed-file evidence.
    helper_hash = hashlib.sha256(Path(recording.__file__).read_bytes()).hexdigest()
    manifest = dict(components=[dict(component='sipi', files=[
        dict(path='sipi/_workbench/recording.py', sha256=helper_hash)])])
    value = dict(manifest_text=json.dumps(manifest), artifacts=[
        dict(component='sipi', version='test-only', kind='runtime', sha256='1'*64)])
    calls = []
    def snapshot():
        calls.append('snapshot')
        return json.loads(json.dumps(value))
    monkeypatch.setattr(recording, 'capture_installed_artifacts', snapshot)
    return value, calls


def test_single_solve_raw_record_and_repeated_run_ids(capture, monkeypatch):
    value, calls = capture
    request = prepared()
    original = SavedExecutionRequest.run
    def run(self):
        calls.append('solve')
        return original(self)
    monkeypatch.setattr(SavedExecutionRequest, 'run', run)
    first = recording.run_recorded(request)
    assert calls == ['snapshot', 'solve', 'snapshot']
    assert set(first) == {'record_text', 'runtime_manifest_text'}
    a = SavedExecutionRecord.loads(first['record_text'])
    b = SavedExecutionRecord.loads(recording.run_recorded(request)['record_text'])
    assert a.run_id != b.run_id and a.receipt == b.receipt
    assert a.prepare().source_text == request.source_text
    assert first['runtime_manifest_text'] == value['manifest_text']
    project = SavedProject(request, project_id='p', design_id='a', title='Test', label='A')
    out = execute(dict(action='project-attach', project_text=project.dumps(), design_id='a',
                       record_text=first['record_text'], select=True))
    assert SavedProject.loads(out['project_text']).current_record('a').dumps() == a.dumps()


def test_adapter_keeps_receipt_path_and_rejects_external_provenance(capture):
    value, calls = capture
    text = prepared().source_text
    result = execute(dict(action='saved-record', text=text))
    assert set(result) == {'engine', 'record_text', 'runtime_manifest_text'}
    record = SavedExecutionRecord.loads(result['record_text'])
    assert record.receipt == execute(dict(action='saved-receipt', text=text))['receipt']
    assert calls == ['snapshot', 'snapshot']
    for extra in [dict(artifacts=[]), dict(run_id='caller'), dict(project_text='{}')]:
        with pytest.raises(ValueError):
            execute(dict(action='saved-record', text=text, **extra))


@pytest.mark.parametrize('value', [None, 'text', {}])
def test_non_request_rejects_before_capture(capture, value):
    with pytest.raises(ValueError, match='prepared'):
        recording.run_recorded(value)
    assert capture[1] == []


@pytest.mark.parametrize('kind', ['bytes', 'evaluations'])
def test_direct_limits_before_capture(capture, kind):
    request = prepared()
    large = SavedExecutionRequest(request.source_text+' '*204800) if kind == 'bytes' else SavedExecutionRequest(request.source_text, max_evaluations=129)
    with pytest.raises(ValueError, match='200 KiB and 128'):
        recording.run_recorded(large)
    assert capture[1] == []


def test_capture_failure_and_uninstalled_helper_do_not_execute(capture, monkeypatch):
    request = prepared()
    monkeypatch.setattr(SavedExecutionRequest, 'run', lambda *a: pytest.fail('unprovenanced solve'))
    value, calls = capture
    value['manifest_text'] = json.dumps(dict(components=[dict(component='sipi', files=[])]))
    with pytest.raises(ValueError, match='helper'):
        recording.run_recorded(request)
    original = OSError('missing installed payload')
    def failed(): raise original
    monkeypatch.setattr(recording, 'capture_installed_artifacts', failed)
    with pytest.raises(OSError) as error:
        recording.run_recorded(request)
    assert error.value is original


def test_changed_snapshot_refuses_record_after_one_solve(capture, monkeypatch):
    value, calls = capture
    original = SavedExecutionRequest.run
    def changed(self):
        calls.append('solve')
        result = original(self)
        value['artifacts'][0]['sha256'] = '2'*64
        return result
    monkeypatch.setattr(SavedExecutionRequest, 'run', changed)
    with pytest.raises(RuntimeError, match='no record'):
        recording.run_recorded(prepared())
    assert calls == ['snapshot', 'solve', 'snapshot']


def test_original_solver_error_remains_unwrapped(capture, monkeypatch):
    original = ArithmeticError('original solver failure')
    def failed(self): raise original
    monkeypatch.setattr(SavedExecutionRequest, 'run', failed)
    with pytest.raises(ArithmeticError) as error:
        recording.run_recorded(prepared())
    assert error.value is original and capture[1] == ['snapshot']


@pytest.mark.parametrize('fail_at', [None, 2])
def test_study_status_and_history_are_preserved(capture, monkeypatch, fail_at):
    from test_sampled_panel_pair_yield import random_document
    from test_sampled_panel_pair_goal import synthetic
    request = SavedExecutionRequest(random_document().dumps(), max_input_bytes=200*1024, max_evaluations=4)
    synthetic(monkeypatch, fail_at=fail_at)
    expected = request.run()
    synthetic(monkeypatch, fail_at=fail_at)
    result = SavedExecutionRecord.loads(recording.run_recorded(request)['record_text'])
    assert result.receipt == expected
    assert result.receipt['execution']['status'] == ('incomplete' if fail_at else 'complete')


def test_failed_goal_record_keeps_original_attempts(capture, monkeypatch):
    from test_sampled_panel_pair_goal_document import document, Document
    from test_sampled_panel_pair_goal import synthetic
    raw = document().to_dict()
    raw['initial'] = [1.35*.3e-3, .8*.2e-3]
    raw['max_evaluations'] = 4
    request = SavedExecutionRequest(Document.from_dict(raw).dumps(), max_input_bytes=200*1024, max_evaluations=4)
    synthetic(monkeypatch, fail_at=2)
    expected = request.run()
    synthetic(monkeypatch, fail_at=2)
    record = SavedExecutionRecord.loads(recording.run_recorded(request)['record_text'])
    assert record.receipt == expected and record.receipt['execution']['status'] == 'failed'
    assert record.receipt['execution']['error']['attempts'] == 2


def test_record_growth_refuses_without_partial_output(capture):
    request = prepared()
    padded = SavedExecutionRequest(request.source_text+' '*(200*1024-len(request.source_text.encode('utf-8'))), max_input_bytes=200*1024)
    with pytest.raises(ValueError, match='max_record_bytes'):
        recording.run_recorded(padded)


@pytest.mark.parametrize('payload', [dict(action='saved-record'),
    dict(action='saved-record', text='{}'), dict(action='saved-record', text=None),
    dict(action='saved-record', text='{}', controls={})])
def test_invalid_adapter_requests_never_capture(capture, payload):
    with pytest.raises(ValueError):
        execute(payload)
    assert capture[1] == []
