# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
import json
import numpy as np
import pytest

from sipi import CrossSection
from sipi.execution import normalize_saved, execute_saved
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.shape_panel_line import ShapePanelTransmissionLineDocument, ShapePanelLineError
from sipi.panel_shape_conductor import PanelShapeCurrentError
from sipi.shape_panel_resolution_document import ShapePanelResolutionDocument
from sipi.line_resolution import ResolutionTolerance
from sipi.shape_panel_resolution import assess_shape_panel_line_resolution
from test_shape_panel_resolution import inputs, FINE, TOLERANCES, replay
from test_execution_record import ARTIFACTS


def document(coated=True):
    line,outer=inputs(coated)
    return ShapePanelResolutionDocument(line,refined_panel_options=FINE,
        outer_documents=outer,tolerances=TOLERANCES,max_solves=5)


@pytest.mark.parametrize('coated',[False,True])
def test_normalization_is_field_free_and_isolated(monkeypatch,coated):
    forbidden=lambda *a,**k:pytest.fail('normalization reached fields')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',forbidden)
    doc=document(coated);text=doc.dumps()
    assert normalize_saved(text)==text==ShapePanelResolutionDocument.loads(text).dumps()
    data=doc.to_dict();data['line']['step_fraction']=.01;data['refined_panel']['panels_per_edge']=64
    data['outer_lines'][0]['line']['line']['length_m']=3
    assert doc.dumps()==text
    with pytest.raises(ValueError):ShapePanelTransmissionLineDocument.loads(text)


@pytest.mark.parametrize('where',['root','line','panel-line','panel','transmission','conductor','coating','refined','tolerance','outer'])
@pytest.mark.parametrize('kind',['missing','extra'])
def test_strict_keys_at_every_nested_level(where,kind):
    data=document().to_dict();line=data['line']['line']['line']
    target={'root':data,'line':data['line'],'panel-line':data['line']['line'],
        'panel':data['line']['line']['panel'],'transmission':line,'conductor':line['conductor'],
        'coating':line['conductor']['reference']['coatings'][0],'refined':data['refined_panel'],
        'tolerance':data['tolerances']['C0_f_per_m'],'outer':data['outer_lines'][0]}[where]
    if kind=='missing':target.pop(next(iter(target)))
    else:target['unexpected']=0
    with pytest.raises(ValueError):ShapePanelResolutionDocument.from_dict(data)


@pytest.mark.parametrize('kind',['schema','duplicate','nonfinite','outer-empty','outer-type','si','budget','budget-bool','factor','step','physics','nested-type'])
def test_invalid_contracts_before_fields(monkeypatch,kind):
    doc=document();data=doc.to_dict();text=doc.dumps()
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('invalid input reached fields'))
    if kind=='schema':data['schema']='sipi.shape-panel-resolution/2'
    if kind=='duplicate':text=text.replace('"max_solves": 5','"max_solves": 5, "max_solves": 5')
    if kind=='nonfinite':text=text.replace('"refinement_factor": 0.5','"refinement_factor": NaN')
    if kind=='outer-empty':data['outer_lines']=[]
    if kind=='outer-type':data['outer_lines']={}
    if kind=='si':data['tolerances']={'C0':{'relative':.1,'absolute':0.}}
    if kind=='budget':data['max_solves']=4
    if kind=='budget-bool':data['max_solves']=True
    if kind=='factor':data['refinement_factor']=1.
    if kind=='step':data['outer_lines'][0]['step_fraction']*=.5
    if kind=='physics':data['outer_lines'][0]['line']['line']['reference_ohms']=75.
    if kind=='nested-type':data['line']=data['line']['line']
    if kind not in ('duplicate','nonfinite'):text=json.dumps(data)
    with pytest.raises((ValueError,TypeError)):ShapePanelResolutionDocument.loads(text)


def test_caller_budget_and_unsupported_diagnostics_precede_fields(monkeypatch):
    doc=document();monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('budget reached fields'))
    with pytest.raises(ValueError,match='before any field solve'):doc.analyze(max_evaluations=4)
    with pytest.raises(ValueError,match='before any field solve'):execute_saved(doc.dumps(),max_evaluations=4)
    with pytest.raises(ValueError,match='diagnostics'):SavedExecutionRequest(doc.dumps(),diagnostics=['modes'])


@pytest.fixture(scope='module',params=[False,True],ids=['legacy','coated'])
def actual(request):
    doc=document(request.param)
    return doc,doc.analyze(max_evaluations=5)


def test_actual_saved_fields_and_direct_record_are_exact(actual,monkeypatch,record_property):
    doc,result=actual;assert result.completed and result.accepted and len(result.evaluations)==5
    calls=replay(monkeypatch,result)
    data=doc.to_dict()
    direct=assess_shape_panel_line_resolution(ShapePanelTransmissionLineDocument.from_dict(data['line']),
        refined_panel_options=data['refined_panel'],
        outer_documents=[ShapePanelTransmissionLineDocument.from_dict(v) for v in data['outer_lines']],
        tolerances=TOLERANCES,max_solves=5)
    assert direct.to_dict()==result.to_dict() and len(calls)==5
    record_property('saved_shape_resolution',json.dumps(result.to_dict(),sort_keys=True))


@pytest.mark.parametrize('accepted',[True,False])
def test_complete_and_unaccepted_receipts_preserve_every_current_sample(actual,monkeypatch,accepted):
    doc,previous=actual;data=doc.to_dict()
    if not accepted:data['tolerances']={'R_ohm_per_m':{'relative':.005,'absolute':0.}}
    selected=ShapePanelResolutionDocument.from_dict(data);calls=replay(monkeypatch,previous)
    request=SavedExecutionRequest(selected.dumps(),max_evaluations=5);receipt=request.run();out=receipt['execution']
    assert out['status']=='complete' and out['error'] is None and out['result']['accepted'] is accepted
    assert len(calls)==5 and out['result']['completed']
    for row,old in zip(out['result']['evaluations'],previous.to_dict()['evaluations']):
        assert row==old
    saved=SavedExecutionRecord(request,receipt,run_id='shape-resolution:example',artifacts=ARTIFACTS)
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('restore replayed fields'))
    restored=SavedExecutionRecord.loads(saved.dumps())
    assert restored.receipt==receipt and restored.prepare().to_dict()==request.to_dict()


@pytest.mark.parametrize('index',range(5))
def test_partial_failure_receipt_keeps_original_completed_work(actual,monkeypatch,index):
    doc,previous=actual;row=previous.evaluations[index];r=row.result
    error=ShapePanelLineError(ValueError('original mesh refusal'),stage='mesh',input_json=row.input_json,
        factors=r.current_factors,settings=r.panel_settings)
    calls=replay(monkeypatch,previous,row.input_json,error)
    request=SavedExecutionRequest(doc.dumps(),max_evaluations=5);receipt=request.run();out=receipt['execution']
    assert out['status']=='failed' and out['result'] is None and len(calls)==index+1
    failure=out['error'];partial=failure['partial_assessment']
    assert failure['type']=='ShapePanelResolutionFailure' and failure['stage']==row.stage
    assert failure['cause_type']=='ShapePanelLineError' and failure['input']==json.loads(row.input_json)
    assert not partial['completed'] and not partial['accepted']
    assert partial['evaluations']==previous.to_dict()['evaluations'][:index]
    assert partial['failure']['details']==error.to_dict()
    saved=SavedExecutionRecord(request,receipt,run_id='shape-resolution:failed',artifacts=ARTIFACTS)
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('restore replayed fields'))
    restored=SavedExecutionRecord.loads(saved.dumps())
    assert restored.receipt==receipt and restored.prepare().to_dict()==request.to_dict()


@pytest.mark.parametrize('step_failure',[False,True])
def test_nested_partial_current_evidence_survives_receipt(actual,monkeypatch,step_failure):
    doc,previous=actual;row=previous.evaluations[2];r=row.result;factors=r.current_factors
    if step_failure:
        cause=PanelShapeCurrentError('original step disagreement',samples=factors.samples,
            step_parts=factors.step_parts,boundary_step_parts=factors.boundary_step_parts)
    else:
        cause=PanelShapeCurrentError('original shared solve refusal',samples=factors.samples[:3],request=factors.samples[3].request)
        cause.__cause__=ValueError('original quadrature refusal')
    error=ShapePanelLineError(cause,stage='current',input_json=row.input_json,factors=None,settings=r.panel_settings)
    replay(monkeypatch,previous,row.input_json,error)
    request=SavedExecutionRequest(doc.dumps(),max_evaluations=5);receipt=request.run()
    saved=SavedExecutionRecord(request,receipt,run_id='shape-resolution:partial-current',artifacts=ARTIFACTS)
    restored=SavedExecutionRecord.loads(saved.dumps())
    details=restored.receipt['execution']['error']['partial_assessment']['failure']['details']
    assert details==error.to_dict()
    partial=details['partial_current']
    if step_failure:
        np.testing.assert_array_equal(partial['step_factors_per_m'],factors.step_parts)
        assert len(partial['samples'])==13 and partial['failed_request'] is None
    else:
        assert partial['cause_type']=='ValueError' and len(partial['samples'])==3
        assert partial['failed_request']['request']==factors.samples[3].request.arguments()


@pytest.mark.parametrize('index',range(5))
def test_every_interrupt_propagates_without_failed_receipt(actual,monkeypatch,index):
    doc,previous=actual;calls=replay(monkeypatch,previous,previous.evaluations[index].input_json,KeyboardInterrupt())
    with pytest.raises(KeyboardInterrupt):SavedExecutionRequest(doc.dumps(),max_evaluations=5).run()
    assert len(calls)==index+1
