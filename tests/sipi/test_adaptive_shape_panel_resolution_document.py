# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict plans preserve finite observations and every partial execution state."""
import json
import pytest
from sipi import CrossSection
from sipi.shape_panel_line import ShapePanelTransmissionLineDocument
from sipi.adaptive_shape_panel_resolution import refine_shape_panel_line_resolution
from sipi.adaptive_shape_panel_resolution_document import AdaptiveShapePanelResolutionDocument as Document
from sipi.execution import execute_saved,normalize_saved
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord as Record
from sipi.project import SavedProject
from test_execution_record import ARTIFACTS
from test_adaptive_shape_panel_resolution import inputs,TOLERANCES,fake


def document(coated=True,levels=2):
    line,steps=inputs(coated,levels)
    return Document(line,refinements=steps,tolerances=TOLERANCES)


@pytest.mark.parametrize('coated',[False,True])
def test_normalization_is_field_free_and_snapshots_are_isolated(monkeypatch,coated):
    forbidden=lambda *a,**k:pytest.fail('normalization reached fields')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',forbidden)
    doc=document(coated);text=doc.dumps()
    assert text==normalize_saved(text)==Document.loads(text).dumps()
    raw=doc.to_dict();raw['refinements'][-1]['refined_panel']['panels_per_edge']=128
    raw['line']['step_fraction']=.002
    assert doc.dumps()==text


@pytest.mark.parametrize('where',['root','step','line','outer','panel','tolerance','nested-metal'])
@pytest.mark.parametrize('change',['missing','unknown'])
def test_exact_saved_keys(where,change):
    raw=document().to_dict()
    target={'root':raw,'step':raw['refinements'][0],'line':raw['line'],
        'outer':raw['refinements'][0]['outer_lines'][0],'panel':raw['refinements'][0]['refined_panel'],
        'tolerance':raw['tolerances']['C0_f_per_m'],
        'nested-metal':raw['line']['line']['line']['conductor']['reference']['coatings'][0]}[where]
    if change=='unknown':target['unexpected']=1
    else:target.pop(next(iter(target)))
    with pytest.raises((ValueError,TypeError)):Document.from_dict(raw)


@pytest.mark.parametrize('change',['future','old-line','wrong-unit','duplicate','nan','short','long',
    'steps-tuple','outers-tuple','late-size','late-physics','late-mesh','late-panel','stored-budget','step'])
def test_invalid_whole_plan_precedes_fields(monkeypatch,change):
    raw=document().to_dict();outer=raw['refinements'][-1]['outer_lines'][0]
    if change=='future':raw['schema']='sipi.adaptive-shape-panel-resolution/2'
    if change=='old-line':raw['line']=raw['line']['line']
    if change=='wrong-unit':raw['tolerances']['C_pf_per_mm']=raw['tolerances'].pop('C0_f_per_m')
    if change=='short':raw['refinements']=raw['refinements'][:1]
    if change=='long':raw['refinements']*=3
    if change=='steps-tuple':raw['refinements']=tuple(raw['refinements'])
    if change=='outers-tuple':raw['refinements'][0]['outer_lines']=tuple(raw['refinements'][0]['outer_lines'])
    if change=='late-size':
        outer['line']['line']['cross_section']['box']['width']*=2
        outer['line']['line']['cross_section']['layers'][-1]['thickness']*=2
    if change=='late-physics':outer['line']['line']['conductor']['reference']['coatings'][0]['conductivity']*=.9
    if change=='late-mesh':outer['line']['line']['cross_section']['mesh']['grade']*=2
    if change=='late-panel':outer['line']['panel']['panels_per_edge']=32
    if change=='stored-budget':raw['max_solves']=7
    if change=='step':outer['step_fraction']=.002
    text=json.dumps(raw)
    if change=='duplicate':text=text.replace('"step_fraction": 0.001','"step_fraction": 0.001, "step_fraction": 0.001')
    if change=='nan':text=text.replace('"step_fraction": 0.001','"step_fraction": NaN')
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('invalid input solved'))
    with pytest.raises((ValueError,TypeError)):
        if change in ('steps-tuple','outers-tuple'):Document.from_dict(raw)
        else:Document.loads(text)


def save_restore(request,receipt,version,monkeypatch):
    saved=Record(request,receipt,run_id='adaptive-shape:1',artifacts=ARTIFACTS,schema=f'sipi.execution-record/{version}')
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('restore solved'))
    restored=Record.loads(saved.dumps());assert restored.receipt==receipt
    assert restored.prepare().to_dict()==request.to_dict()
    changed=saved.to_dict();changed['receipt']['execution']['input']['max_solves']=32
    with pytest.raises(ValueError):Record.from_dict(changed)
    return saved


@pytest.mark.parametrize('version',[1,2])
@pytest.mark.parametrize('attempt',range(1,9))
def test_each_partial_current_failure_keeps_exact_history_and_receipt(monkeypatch,version,attempt):
    calls=fake(monkeypatch,fail=attempt,shape_error=True);doc=document()
    request=SavedExecutionRequest(doc.dumps(),max_evaluations=8);receipt=request.run();out=receipt['execution']
    assert out['status']=='failed' and out['result'] is None
    error=out['error'];report=error['partial_assessment']
    assert error['type']=='ShapePanelResolutionFailure' and error['cause_type']=='ShapePanelLineError'
    assert report['stop_reason']=='field-failed' and not report['completed'] and not report['accepted']
    assert len(report['evaluations'])==attempt-1 and len(calls)==attempt
    assert error['input']==report['failure']['input']==json.loads(calls[-1])
    assert error['stage']==report['failure']['stage']
    details=report['failure']['details'];assert details['partial_current']['samples']==[]
    assert details['message']=='original adaptive current refusal'
    assert report['selected_evaluation_index'] is None
    save_restore(request,receipt,version,monkeypatch)


@pytest.mark.parametrize('version',[1,2])
@pytest.mark.parametrize('state',['accepted','level-limit','outer','budget'])
def test_terminal_states_and_whole_batch_budget_are_preserved(monkeypatch,version,state):
    raw=document(levels=4 if state=='budget' else 2).to_dict()
    raw['tolerances']={'C_f_per_m':dict(relative=.01,absolute=0.)}
    values={(1,1):2.,(2,2):3.} if state in ('level-limit','budget') else None
    calls=fake(monkeypatch,values=values,outer=2. if state=='outer' else 1.)
    request=SavedExecutionRequest(json.dumps(raw),max_evaluations=8);receipt=request.run();out=receipt['execution']
    r=out['error']['partial_assessment'] if state=='budget' else out['result']
    expected={'accepted':'accepted','level-limit':'resolution-unaccepted','outer':'outer-unaccepted','budget':'budget-exhausted'}[state]
    assert r['stop_reason']==expected and r['accepted']==(state=='accepted')
    assert out['status']==('failed' if state=='budget' else 'complete')
    assert r['completed']==(state!='budget') and len(calls)==(7 if state in ('budget','level-limit') else 8)
    if state=='budget':assert out['result'] is None and out['error']['type']=='ResolutionBudgetExceeded' and r['failure'] is None
    else:assert out['error'] is None
    if state!='accepted':assert r['selected_evaluation_index'] is None
    saved=save_restore(request,receipt,version,monkeypatch)
    project=SavedProject(request,project_id='adaptive-shape:1',design_id='a',title='Finite comparison',label='Original')
    project=project.attach_record('a',saved,select=True)
    assert SavedProject.loads(project.dumps()).to_dict()==project.to_dict()


@pytest.mark.parametrize('options',[dict(max_evaluations=7),dict(diagnostics=['characteristic']),dict(max_input_bytes=16)])
def test_caller_admission_precedes_any_fields(monkeypatch,options):
    calls=fake(monkeypatch);doc=document()
    with pytest.raises(ValueError):execute_saved(doc.dumps(),**options)
    assert not calls


@pytest.mark.parametrize('attempt',[1,4,7,8])
def test_interruption_is_not_serialized_as_failure(monkeypatch,attempt):
    calls=fake(monkeypatch,fail=attempt,interrupt=True)
    with pytest.raises(KeyboardInterrupt):execute_saved(document().dumps(),max_evaluations=8)
    assert len(calls)==attempt


def test_ordinary_field_error_has_no_invented_current_details(monkeypatch):
    fake(monkeypatch,fail=3);out=execute_saved(document().dumps(),max_evaluations=8)
    assert out['result'] is None and out['error']['cause_type']=='ValueError'
    assert out['error']['partial_assessment']['failure']['details'] is None


def test_completed_saved_plan_matches_direct_report(monkeypatch):
    fake(monkeypatch);doc=document();line,steps=inputs(True)
    direct=refine_shape_panel_line_resolution(line,refinements=steps,tolerances=TOLERANCES)
    assert doc.analyze().to_dict()==direct.to_dict()
    assert execute_saved(doc.dumps())['result']==direct.to_dict()
