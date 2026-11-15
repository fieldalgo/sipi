# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict plans and caller-bound partial histories preserve adaptive control flow."""
import json
import numpy as np
import pytest
from sipi import CrossSection
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument as Line
from sipi.adaptive_two_ground_face_resolution_document import AdaptiveTwoGroundFaceResolutionDocument as Document
from sipi.line_resolution import ResolutionTolerance
from sipi.execution import normalize_saved,execute_saved
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord as Record
from sipi.project import SavedProject
from test_execution_record import ARTIFACTS
from test_adaptive_two_ground_face_resolution import inputs,fake,physical_inputs


def document(levels=2,physical=False):
    line,steps=physical_inputs('scalar') if physical else inputs(levels=levels)
    return Document(line,refinements=steps,
        tolerances={key:ResolutionTolerance(.01,0.) for key in
                    (('R','L_internal','L_external','C','G','C0') if physical else ('C',))},
        refinement_factor=.75 if physical else .5,max_solves=9 if physical else 16)


def make_record(request,receipt,schema='sipi.execution-record/2'):
    return Record(request,receipt,run_id='adaptive-face:run',artifacts=ARTIFACTS,schema=schema)


def test_field_free_canonical_plan_and_detached_snapshots(monkeypatch):
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('normalization solved'))
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('normalization meshed'))
    doc=document();text=doc.dumps();assert text==normalize_saved(text)==Document.loads(text).dumps()
    raw=doc.to_dict();raw['refinements'][0]['outer_lines'].clear();raw['line']['conductors'].clear()
    assert doc.dumps()==text and doc.to_dict()['refinements'][0]['outer_lines']


@pytest.mark.parametrize('where',['root','line','step','outer','panel','tolerance','face'])
@pytest.mark.parametrize('change',['missing','extra'])
def test_strict_nested_keys(where,change):
    raw=document().to_dict();target={'root':raw,'line':raw['line'],'step':raw['refinements'][0],
        'outer':raw['refinements'][0]['outer_lines'][0],'panel':raw['refinements'][0]['refined_panel'],
        'tolerance':raw['tolerances']['C_f_per_m'],'face':raw['line']['conductors']['left']['bottom']}[where]
    if change=='missing':target.pop(next(iter(target)))
    else:target['unexpected']=1
    with pytest.raises((ValueError,TypeError)):Document.from_dict(raw)


@pytest.mark.parametrize('change',['schema','source','duplicate','nonfinite','one-level','too-many','budget','outer','mesh','metal','tolerance'])
def test_invalid_plan_stops_before_fields(monkeypatch,change):
    raw=document().to_dict();text=None
    if change=='schema':raw['schema']+='/future'
    if change=='source':raw['line']['schema']='sipi.two-ground-panel-transmission-line/1'
    if change=='duplicate':text=json.dumps(raw).replace('"max_solves": 16','"max_solves": 16, "max_solves": 16')
    if change=='nonfinite':text=json.dumps(raw).replace('"refinement_factor": 0.5','"refinement_factor": NaN')
    if change=='one-level':raw['refinements']=raw['refinements'][:1]
    if change=='too-many':raw['refinements']*=3
    if change=='budget':raw['max_solves']=7
    if change=='outer':raw['refinements'][1]['outer_lines'][0]['cross_section']['box']['width']*=2
    if change=='mesh':raw['refinements'][1]['outer_lines'][0]['cross_section']['mesh']['grade']*=2
    if change=='metal':raw['refinements'][1]['outer_lines'][0]['conductors']['left']['bottom']['conductivity']*=.9
    if change=='tolerance':raw['tolerances']['C_f_per_m']['absolute']=-1
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('invalid plan solved'))
    with pytest.raises((ValueError,TypeError)):Document.loads(text or json.dumps(raw))


@pytest.mark.parametrize('attempt',range(1,9))
@pytest.mark.parametrize('typed',[False,True])
def test_every_failed_operation_reopens_exact_plan_prefix(monkeypatch,attempt,typed):
    calls=fake(monkeypatch,fail=attempt,shape_error=typed)
    request=SavedExecutionRequest(document().dumps(),max_evaluations=8);receipt=request.run();out=receipt['execution']
    assert out['status']=='failed' and len(calls)==attempt
    assert out['result']['failure']==out['error'] and len(out['result']['evaluations'])==attempt-1
    record=make_record(request,receipt)
    with pytest.raises(ValueError):make_record(request,receipt,'sipi.execution-record/1')
    project=SavedProject(request,project_id='adaptive-face',design_id='a',title='Adaptive',label='Plan')
    project=project.attach_record('a',record,select=True)
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('reopen solved'))
    assert Record.loads(record.dumps()).receipt==receipt
    assert SavedProject.loads(project.dumps()).current_record('a').receipt==receipt


def test_comparison_failure_keeps_completed_current_and_mesh(monkeypatch):
    calls=fake(monkeypatch);original=Line.analyze
    def changed(self):
        result=original(self)
        if len(calls)==4:result.names=('wrong','right')
        return result
    monkeypatch.setattr(Line,'analyze',changed)
    request=SavedExecutionRequest(document().dumps(),max_evaluations=8);receipt=request.run()
    assert receipt['execution']['status']=='failed' and len(calls)==4
    assert len(receipt['execution']['result']['evaluations'])==4
    assert make_record(request,receipt).receipt==receipt


def budget_receipt(monkeypatch):
    calls=fake(monkeypatch,{(1,1):2.,(2,2):3.})
    request=SavedExecutionRequest(document(levels=4).dumps(),max_evaluations=8)
    return request,request.run(),calls


def test_caller_budget_exhaustion_keeps_complete_prior_levels(monkeypatch):
    request,receipt,calls=budget_receipt(monkeypatch);out=receipt['execution'];result=out['result']
    assert out['status']=='failed' and result['stop_reason']=='budget-exhausted' and len(calls)==7
    assert result['refinement_levels']==2 and result['selected_evaluation_index'] is None
    assert make_record(request,receipt).receipt==receipt


@pytest.mark.parametrize('change',['level','outer-count','scope','selection','prefix','input','compare-index',
    'compare-order','compare-count','evidence','cause','cause-input','cause-message','untyped-details','extra-evaluation'])
def test_partial_field_history_cannot_be_relabelled(monkeypatch,change):
    fake(monkeypatch,fail=5,shape_error=True)
    request=SavedExecutionRequest(document().dumps(),max_evaluations=8);receipt=request.run()
    result=receipt['execution']['result'];error=receipt['execution']['error']
    if change=='level':result['refinement_levels']=1
    if change=='outer-count':result['expected_outer_evaluations']=2
    if change=='scope':result['scope']='changed'
    if change=='selection':result['selected_evaluation_index']=3
    if change=='prefix':result['evaluations'][0]['stage']='level:1:joint'
    if change=='input':result['evaluations'][0]['input']['length_m']=1.
    if change=='compare-index':result['comparisons'][0]['reference_index']=1
    if change=='compare-order':result['comparisons'].reverse()
    if change=='compare-count':result['comparisons'].pop()
    if change=='evidence':result['evaluations'][0]['dielectric_mesh']=None
    if change=='cause':error['details']['type']='ArithmeticError'
    if change=='cause-input':error['details']['input']['length_m']=2.
    if change=='cause-message':error['details']['message']='changed'
    if change=='untyped-details':error['kind']='ArithmeticError'
    if change=='extra-evaluation':result['evaluations'].append(result['evaluations'][-1])
    result['failure']=json.loads(json.dumps(error))
    with pytest.raises(ValueError):make_record(request,receipt)


@pytest.mark.parametrize('change',['level','count','next-fits','early-accepted','stop','failure','message-kind','source'])
def test_budget_history_must_match_the_original_reservation(monkeypatch,change):
    request,receipt,_=budget_receipt(monkeypatch);result=receipt['execution']['result'];error=receipt['execution']['error']
    if change=='level':result['refinement_levels']=3
    if change=='count':result['evaluations'].pop()
    if change=='next-fits':
        request=SavedExecutionRequest(document(levels=4).dumps(),max_evaluations=16)
        receipt['request']=request.to_dict()
    if change=='early-accepted':
        for row in result['comparisons']:row['accepted']=True
    if change=='stop':result['stop_reason']='field-failed'
    if change=='failure':result['failure']=error
    if change=='message-kind':error['kind']='ValueError'
    if change=='source':error['input']['max_solves']=8
    with pytest.raises(ValueError):make_record(request,receipt)


@pytest.mark.parametrize('mode',['accepted','outer','levels'])
def test_completed_agreement_and_disagreement_remain_distinct(monkeypatch,mode):
    calls=fake(monkeypatch,values={(1,1):2.,(2,2):3.} if mode=='levels' else None,outer=2. if mode=='outer' else 1.)
    request=SavedExecutionRequest(document().dumps(),max_evaluations=8);receipt=request.run();out=receipt['execution']
    assert out['status']=='complete' and out['error'] is None
    assert out['result']['accepted']==(mode=='accepted') and out['result']['completed']
    assert len(calls)==(7 if mode=='levels' else 8)
    assert make_record(request,receipt).receipt==receipt


@pytest.mark.parametrize('options',[dict(max_evaluations=7),dict(max_input_bytes=16),dict(diagnostics=['characteristic'])])
def test_host_limits_precede_fields(monkeypatch,options):
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('rejected request solved'))
    with pytest.raises(ValueError):execute_saved(document().dumps(),**options)


def test_interrupt_propagates_without_a_saved_partial_result(monkeypatch):
    calls=fake(monkeypatch,fail=5,interrupt=True)
    with pytest.raises(KeyboardInterrupt):execute_saved(document().dumps(),max_evaluations=8)
    assert len(calls)==5


def test_actual_saved_scalar_matches_full_direct_plan(record_property):
    from scipy.linalg import sqrtm
    doc=document(physical=True);request=SavedExecutionRequest(doc.dumps(),max_evaluations=9)
    receipt=request.run();record_property('two_ground_face_adaptive_saved_scalar',json.dumps(receipt,sort_keys=True))
    out=receipt['execution'];assert out['status']=='complete' and out['result']['accepted']
    assert len(out['result']['evaluations'])==9 and len(out['result']['comparisons'])==10
    assert make_record(request,receipt).receipt==receipt
    for row in out['result']['evaluations']:
        q=row['quantities']
        for i,f in enumerate(row['frequency_hz']):
            z=np.array(q['R_ohm_per_m'][i])+2j*np.pi*f*(np.array(q['L_internal_h_per_m'][i])+np.array(q['L_external_h_per_m'][i]))
            y=np.array(q['G_s_per_m'][i])+2j*np.pi*f*np.array(q['C_f_per_m'][i])
            np.testing.assert_allclose(np.linalg.solve(np.asarray(sqrtm(z@y),dtype=complex),z)[0,0],np.sqrt(z[0,0]/y[0,0]),rtol=1e-10,atol=0)


def test_partial_field_failure_cannot_claim_an_unreserved_later_level(monkeypatch):
    calls=fake(monkeypatch,{(1,1):2.,(2,2):3.},fail=8,shape_error=True)
    source=document(levels=4).dumps()
    request=SavedExecutionRequest(source,max_evaluations=16);receipt=request.run()
    assert len(calls)==8 and receipt['execution']['result']['refinement_levels']==3
    assert make_record(request,receipt).receipt==receipt
    tighter=SavedExecutionRequest(source,max_evaluations=8);receipt['request']=tighter.to_dict()
    with pytest.raises(ValueError):make_record(tighter,receipt)
