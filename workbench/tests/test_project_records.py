"""Raw result records stay immutable; selection is explicit and input-bound."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'desktop'))
from engine import execute
from sipi import LumpedNetworkDocument
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject
from test_desktop import server, call, finish


def prepared(resistance=10, padding=0):
    raw = LumpedNetworkDocument([0, 1e9], resistance=resistance).dumps() + ' '*padding
    return SavedExecutionRequest(raw, max_input_bytes=200*1024)


def record(request, run_id='run:1'):
    # Synthetic host declaration for fixtures only, not a measured installed artifact.
    return SavedExecutionRecord(request, request.run(), run_id=run_id, artifacts=[
        dict(component='sipi', version='test-only', kind='runtime', sha256='1'*64)])


def project(request):
    return SavedProject(request, project_id='p', design_id='a', title='Comparison', label='A')


def attach(p, r, *, select=False, design_id='a'):
    return dict(action='project-attach', project_text=p.dumps(), design_id=design_id,
                record_text=r.dumps(), select=select)


def transformed(payload):
    out = execute(payload)
    assert set(out) == {'engine', 'project_text'}
    result = SavedProject.loads(out['project_text'])
    assert result.dumps() == out['project_text']
    return result


def test_attach_select_clear_remove_preserve_exact_record_without_running(monkeypatch):
    request = prepared()
    p = project(request)
    r = record(request)
    monkeypatch.setattr(SavedExecutionRequest, 'run', lambda *a: pytest.fail('record operation executed'))
    original = p.dumps()
    added = transformed(attach(p, r))
    assert added.design('a')['records'] == [r.to_dict()]
    assert added.current_record('a') is None and p.dumps() == original
    selected = transformed(dict(action='project-select', project_text=added.dumps(), design_id='a', run_id=r.run_id))
    assert selected.current_record('a').dumps() == r.dumps()
    assert selected.current_record('a').artifacts['verification'] == 'host-declared'
    cleared = transformed(dict(action='project-select', project_text=selected.dumps(), design_id='a', run_id=None))
    assert cleared.current_record('a') is None and cleared.design('a')['records'] == [r.to_dict()]
    removed = transformed(dict(action='project-remove-record', project_text=selected.dumps(), design_id='a', run_id=r.run_id))
    assert removed.current_record('a') is None and removed.design('a')['records'] == []
    assert added.current_record('a') is None and selected.current_record('a').dumps() == r.dumps()


def test_same_input_repeated_runs_need_distinct_ids_and_explicit_selection():
    request = prepared()
    a, b = record(request), record(request, 'run:2')
    assert a.receipt == b.receipt
    initial = transformed(attach(project(request), a, select=True))
    added = transformed(attach(initial, b))
    assert added.current_record('a').run_id == a.run_id
    with pytest.raises(ValueError):
        transformed(attach(added, b))
    selected = transformed(dict(action='project-select', project_text=added.dumps(), design_id='a', run_id=b.run_id))
    assert selected.current_record('a').run_id == b.run_id


@pytest.mark.parametrize('change', ['input', 'controls'])
def test_historical_input_can_be_retained_but_not_selected(change):
    old = prepared()
    new = prepared(20) if change == 'input' else SavedExecutionRequest(old.source_text, max_input_bytes=200*1024, max_evaluations=72)
    p, r = project(new), record(old)
    history = transformed(attach(p, r))
    assert history.design('a')['records'] == [r.to_dict()] and history.current_record('a') is None
    with pytest.raises(ValueError):
        transformed(attach(p, r, select=True))
    with pytest.raises(ValueError):
        transformed(dict(action='project-select', project_text=history.dumps(), design_id='a', run_id=r.run_id))
    assert p.design('a')['records'] == []


def test_semantic_edit_clears_selection_and_copy_has_no_records():
    request = prepared()
    p = transformed(attach(project(request), record(request), select=True))
    updated = transformed(dict(action='project-update', project_text=p.dumps(), design_id='a', text=prepared(20).source_text))
    assert updated.current_record('a') is None and updated.design('a')['records'] == p.design('a')['records']
    duplicate = transformed(dict(action='project-duplicate', project_text=p.dumps(), source_id='a', design_id='b', label='B'))
    assert duplicate.design('b')['records'] == [] and duplicate.current_record('b') is None
    assert duplicate.current_record('a').dumps() == p.current_record('a').dumps()


@pytest.mark.parametrize('select', [None, 0, 1, 'yes', []])
def test_selection_requires_boolean(select):
    request = prepared()
    with pytest.raises(ValueError):
        transformed(attach(project(request), record(request), select=select))


@pytest.mark.parametrize('action', ['project-attach', 'project-select', 'project-remove-record'])
def test_strict_keys_missing_targets_and_unknown_runs(action):
    request = prepared()
    p, r = project(request), record(request)
    payload = attach(p, r) if action == 'project-attach' else dict(action=action, project_text=p.dumps(), design_id='a', run_id='absent')
    with pytest.raises(ValueError):
        execute({**payload, 'extra': True})
    with pytest.raises(ValueError):
        execute({k:v for k,v in payload.items() if k != 'design_id'})
    with pytest.raises(ValueError):
        execute({**payload, 'design_id': 'absent'})
    if action != 'project-attach':
        with pytest.raises(ValueError):
            execute(payload)


@pytest.mark.parametrize('bad', ['{}', 'null', '{"schema":NaN}', '{"schema":1,"schema":1}', None])
def test_malformed_record_never_changes_project(bad):
    request = prepared()
    p, r = project(request), record(request)
    before = p.dumps()
    with pytest.raises(ValueError):
        execute({**attach(p, r), 'record_text': bad})
    assert p.dumps() == before


def test_tampering_and_numeric_reserialization_reject():
    request = prepared()
    p, r = project(request), record(request)
    data = r.to_dict()
    data['run_id'] = 'changed'
    with pytest.raises(ValueError, match='digest'):
        execute({**attach(p, r), 'record_text': json.dumps(data)})
    # JavaScript-like integer float reserialization must not silently bless a new digest.
    def reserialize(value):
        if isinstance(value, float) and value.is_integer(): return int(value)
        if isinstance(value, dict): return {k:reserialize(v) for k,v in value.items()}
        if isinstance(value, list): return [reserialize(v) for v in value]
        return value
    changed = json.dumps(reserialize(r.to_dict()))
    with pytest.raises(ValueError, match='digest'):
        execute({**attach(p, r), 'record_text': changed})
    assert transformed(attach(p, r, select=True)).current_record('a').dumps() == r.dumps()


def test_record_raw_boundary_and_combined_project_growth():
    request = prepared()
    p, r = project(request), record(request)
    padded = r.dumps() + ' '*(200*1024-len(r.dumps().encode('utf-8')))
    assert transformed({**attach(p, r), 'record_text': padded}).design('a')['records'] == [r.to_dict()]
    with pytest.raises(ValueError, match='max_record_bytes'):
        execute({**attach(p, r), 'record_text': padded+' '})
    large_project = project(prepared(padding=120000))
    large_record = record(prepared(padding=90000))
    value = attach(large_project, large_record)
    assert len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8')) < 256*1024
    before = large_project.dumps()
    with pytest.raises(ValueError, match='max_project_bytes'):
        execute(value)
    assert large_project.dumps() == before


def test_actual_spawned_record_operations(server):
    request = prepared()
    p, r = project(request), record(request)
    assert call(server, 'POST', '/api/job', attach(p, r, select=True))[0] == 202
    result = finish(server)
    assert result['status'] == 'complete'
    text = result['result']['project_text']
    assert SavedProject.loads(text).current_record('a').dumps() == r.dumps()
    assert call(server, 'POST', '/api/job', dict(action='project-select', project_text=text, design_id='a', run_id='absent'))[0] == 202
    assert finish(server)['status'] == 'error'
    assert call(server, 'POST', '/api/job', dict(action='project-remove-record', project_text=text, design_id='a', run_id=r.run_id))[0] == 202
    result = finish(server)
    assert result['status'] == 'complete'
    assert SavedProject.loads(result['result']['project_text']).design('a')['records'] == []
