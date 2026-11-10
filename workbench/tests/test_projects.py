"""Project transport preserves exact inputs/history and never executes them."""
import json
from pathlib import Path
import sys

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'desktop'))
from engine import execute
from sipi import CrossSection, LumpedNetworkDocument
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject
from sipi.template_document import TemplateSectionDocument
from test_editable import parameters
from test_desktop import server, call, finish


def source(resistance=10):
    return LumpedNetworkDocument([0, 1e9], resistance=resistance,
                                 port_names=('입력', '출력')).dumps()


def create(text=None, **options):
    return dict(action='project-create', text=source() if text is None else text,
                project_id='project:1', design_id='a', title='선로 비교', label='기준', **options)


def saved(request):
    out = execute(request)
    assert set(out) == {'engine', 'project_text'}
    project = SavedProject.loads(out['project_text'])
    assert project.dumps() == out['project_text']
    return project


@pytest.mark.parametrize('template', ['microstrip', 'stripline', 'offset_stripline', 'coupled_microstrip', 'coupled_stripline',
                                      'grounded_coplanar', 'coupled_grounded_coplanar', 'coated_microstrip', 'coupled_coated_microstrip', 'coated_grounded_coplanar'])
def test_forms_create_copy_reopen_without_fields(template, monkeypatch):
    text = TemplateSectionDocument(template, parameters(template)).dumps()
    def forbidden(*a, **kw): raise AssertionError('project edits must not solve')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    monkeypatch.setattr(SavedExecutionRequest, 'run', forbidden)
    initial = saved(create(text))
    duplicate = saved(dict(action='project-duplicate', project_text=initial.dumps(),
                           source_id='a', design_id='b', label='대안'))
    restored = saved(dict(action='project-open', project_text=duplicate.dumps()))
    assert restored.dumps() == duplicate.dumps()
    assert restored.design_ids == ('a', 'b') and initial.design_ids == ('a',)
    for design in ('a', 'b'):
        assert restored.prepare(design).source_text == text
        assert restored.design(design)['records'] == []
        assert restored.current_record(design) is None


def test_existing_result_and_controls_survive_open_duplicate_and_formatting(monkeypatch):
    request = SavedExecutionRequest(source(), max_evaluations=72, max_input_bytes=180000)
    # Synthetic metadata for this test only, never installed-artifact evidence.
    record = SavedExecutionRecord(request, request.run(), run_id='run:1', artifacts=[
        dict(component='sipi', version='test-only', kind='wheel', sha256='1'*64)])
    original = SavedProject(request, project_id='p', design_id='a', title='Title',
                            label='A').attach_record('a', record, select=True)
    before = original.dumps()
    monkeypatch.setattr(SavedExecutionRequest, 'run', lambda *a: pytest.fail('edit executed input'))
    assert saved(dict(action='project-open', project_text=before)).dumps() == before
    copied = saved(dict(action='project-duplicate', project_text=before,
                        source_id='a', design_id='b', label='B'))
    assert copied.design('a') == original.design('a')
    assert copied.design('b')['records'] == [] and copied.current_record('b') is None
    assert copied.prepare('b').controls == request.controls
    formatted = json.dumps(json.loads(request.source_text), ensure_ascii=False, separators=(',', ':'))
    edited = saved(dict(action='project-update', project_text=before,
                        design_id='a', text=formatted, label='Renamed'))
    assert edited.prepare('a').source_text == formatted
    assert edited.prepare('a').controls == request.controls
    assert edited.current_record('a').dumps() == record.dumps()
    changed = saved(dict(action='project-update', project_text=edited.dumps(), design_id='a', text=source(20)))
    assert changed.current_record('a') is None
    assert changed.design('a')['records'] == [record.to_dict()]
    changed_control = saved(dict(action='project-update', project_text=before, design_id='a',
        text=request.source_text, controls={**request.controls, 'max_evaluations': 73}))
    assert changed_control.current_record('a') is None
    assert changed_control.design('a')['records'] == [record.to_dict()]
    assert original.dumps() == before


@pytest.mark.parametrize('bad', [None, True, 1, '{}', '{"schema":1,"schema":2}',
                                '{"a":NaN}', ' '*204801],
                         ids=['null','boolean','number','empty','duplicate','nonfinite','oversized'])
def test_invalid_raw_project_is_rejected(bad):
    with pytest.raises((ValueError, TypeError)):
        execute(dict(action='project-open', project_text=bad))


@pytest.mark.parametrize('operation', ['project-create','project-open','project-duplicate','project-update'])
def test_missing_and_unknown_request_keys(operation):
    with pytest.raises(ValueError, match='options'): execute(dict(action=operation))
    base = saved(create())
    request = {'project-create': create(),
        'project-open': dict(action=operation, project_text=base.dumps()),
        'project-duplicate': dict(action=operation, project_text=base.dumps(), source_id='a', design_id='b', label='B'),
        'project-update': dict(action=operation, project_text=base.dumps(), design_id='a', text=source())}[operation]
    request['ignored'] = True
    with pytest.raises(ValueError, match='options'): execute(request)


@pytest.mark.parametrize('controls', [None, {}, {'max_evaluations': 128},
    dict(max_input_bytes=204800, max_evaluations=True, diagnostics=[]),
    dict(max_input_bytes=204800, max_evaluations=128, diagnostics=[], extra=1)])
def test_controls_are_complete_and_never_silently_clamped(controls):
    with pytest.raises((ValueError, TypeError)): execute(create(controls=controls))


def test_utf8_project_and_encoded_request_exact_boundaries():
    text = saved(create()).dumps()
    raw = text + ' '*(204800-len(text.encode()))
    assert saved(dict(action='project-open', project_text=raw)).dumps() == text
    with pytest.raises(ValueError, match='max_project_bytes'):
        execute(dict(action='project-open', project_text=raw+' '))
    request = dict(action='project-open', project_text=text)
    size = len(json.dumps(request, ensure_ascii=False, separators=(',', ':')).encode())
    tabs, spaces = divmod(262144-size, 2)
    request['project_text'] += '\t'*tabs+' '*spaces
    assert len(json.dumps(request, ensure_ascii=False, separators=(',', ':')).encode()) == 262144
    assert saved(request).dumps() == text
    request['project_text'] += ' '
    with pytest.raises(ValueError, match='Encoded'): execute(request)


def test_growth_tamper_and_invalid_edits_leave_original_intact():
    base = saved(create(source()+' '*80000));before=base.dumps()
    twice = saved(dict(action='project-duplicate', project_text=before, source_id='a', design_id='b', label='B'))
    with pytest.raises(ValueError, match='max_project_bytes'):
        execute(dict(action='project-duplicate', project_text=twice.dumps(), source_id='a', design_id='c', label='C'))
    tampered = base.to_dict();tampered['title']='changed without rehash'
    with pytest.raises(ValueError, match='digest'):
        execute(dict(action='project-open', project_text=json.dumps(tampered)))
    invalid=json.loads(source());invalid['branch']['resistance_ohms']=-1
    for extra in [dict(design_id='missing'),dict(label=None),dict(text=' '*204801),dict(text=json.dumps(invalid))]:
        request=dict(action='project-update', project_text=before, design_id='a', text=source());request.update(extra)
        with pytest.raises((ValueError, TypeError)): execute(request)
    assert base.dumps()==before and base.design_ids==('a',)


def test_readable_core_input_without_a_form_is_preserved():
    text=TemplateSectionDocument('broadside_stripline',dict(width=.0005,gap=.0002,thickness=.000035,plane_spacing=.001,eps_r=4)).dumps()
    project=saved(create(text))
    assert project.prepare('a').source_text==text
    with pytest.raises(ValueError,match='no editable form'):
        execute(dict(action='template-open',text=project.prepare('a').source_text))


def test_real_spawned_project_roundtrip_and_error_recovery(server):
    def submit(request):
        assert call(server, 'POST', '/api/job', request)[0] == 202
        return finish(server)
    created=submit(create());assert created['status']=='complete'
    text=created['result']['project_text']
    copied=submit(dict(action='project-duplicate',project_text=text,source_id='a',design_id='b',label='B'))
    assert copied['status']=='complete'
    original=copied['result']['project_text']
    changed=submit(dict(action='project-update',project_text=original,design_id='b',text=source(20)))
    assert changed['status']=='complete'
    current=changed['result']['project_text']
    assert SavedProject.loads(current).prepare('a').source_text==source()
    assert SavedProject.loads(current).prepare('b').source_text==source(20)
    assert SavedProject.loads(original).prepare('b').source_text==source()
    bad=submit(dict(action='project-update',project_text=current,design_id='missing',text=source()))
    assert bad['status']=='error' and bad['type']=='ValueError'
    reopened=submit(dict(action='project-open',project_text=current))
    assert reopened['status']=='complete' and reopened['result']['project_text']==current
