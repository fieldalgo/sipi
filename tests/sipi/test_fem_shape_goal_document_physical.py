# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Actual saved inverse calculations and complete/failed execution receipts."""
import json
import pytest
from sipi.fem_shape_line import FEMShapeLineError
from sipi.fem_shape_conductor import FEMShapeCurrentError
from sipi.fem_shape_goal import FEMShapeLineQuantityGoalError,_decorate
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject
from test_fem_shape_goal_document import document,Document
from test_fem_shape_study_physical import independent
from test_execution_record import ARTIFACTS
from test_project import project


@pytest.fixture(scope='module')
def observed():return [(document(paired),document(paired).solve()) for paired in (False,True)]


def test_actual_saved_scalar_and_pair_goals_keep_fields_and_criteria(observed,record_property):
    rows={}
    for doc,result in observed:
        quantity=doc.study.to_dict()['quantity'];assert result.quantity==quantity
        assert abs(result.residual)<=doc.to_dict()['tolerance'] and abs(result.refined_residual)<=doc.to_dict()['tolerance']
        assert abs(result.mesh_change)/result.refined_value<=.005 and len(result.history)==4
        for line,value in ((result.result,result.value),(result.refined_result,result.refined_value)):
            assert value==pytest.approx(independent(line,quantity),rel=1e-10,abs=0)
        rows[quantity]=dict(design=result.to_dict(),selected={k:getattr(result.result,k).tolist() for k in ('R','L','G','C')},
            refined={k:getattr(result.refined_result,k).tolist() for k in ('R','L','G','C')})
    record_property('fem_saved_goals',json.dumps(rows,allow_nan=False))


@pytest.mark.parametrize('paired',[False,True])
@pytest.mark.parametrize('version',['sipi.execution-record/1','sipi.execution-record/2'])
def test_observed_goal_receipt_record_and_project(observed,monkeypatch,paired,version):
    doc,result=observed[int(paired)];calls=[]
    def solve(value):calls.append(value.dumps());assert value.dumps()==doc.dumps();return result
    monkeypatch.setattr(Document,'solve',solve)
    request=SavedExecutionRequest(doc.dumps());receipt=request.run();out=receipt['execution']
    assert calls==[doc.dumps()] and out['status']=='complete' and out['error'] is None
    assert out['result']==result.to_dict()
    saved=SavedExecutionRecord(request,receipt,run_id='fem-goal:complete',artifacts=ARTIFACTS,schema=version)
    assert SavedExecutionRecord.loads(saved.dumps()).receipt==receipt
    attached=project(request).attach_record('a',saved,select=True)
    assert SavedProject.loads(attached.dumps()).current_record('a').receipt==receipt


@pytest.mark.parametrize('partial',[False,True])
@pytest.mark.parametrize('version',['sipi.execution-record/1','sipi.execution-record/2'])
def test_typed_goal_failure_preserves_attempt_history_and_fields(observed,monkeypatch,partial,version):
    doc,result=observed[1];cur=result.result.current_factors;text=result.history[1].input_json
    cause=FEMShapeCurrentError('original partial',stage='capacitance-differences',base=cur.base,
        extension_parts=cur.extension_parts,samples=cur.samples[:1],request=(0,0,0,1,cur.step_m)) if partial else ValueError('dielectric failed')
    line_error=FEMShapeLineError(cause,stage='current' if partial else 'dielectric',input_json=text,
        factors=None if partial else cur,mesh_observation=result.result.mesh_observation)
    error=FEMShapeLineQuantityGoalError('search/extraction failed',result.history[:1],attempts=2,
        quantity=result.quantity,failed_parameter=.00041,stage='search/extraction',
        cause_type='FEMShapeLineError',input_json=text)
    _decorate(error,line_error,None)
    def solve(value):raise error from line_error
    monkeypatch.setattr(Document,'solve',solve)
    request=SavedExecutionRequest(doc.dumps());receipt=request.run();out=receipt['execution']
    assert out['status']=='failed' and out['result'] is None and out['error']==error.to_dict()
    assert out['error']['attempts']==2 and len(out['error']['history'])==1
    details=out['error']['cause_details'];assert details==line_error.to_dict()
    if partial:assert len(details['partial_current']['samples'])==1 and details['current_solver'] is None
    else:assert details['current_solver']==result.result.current_record()
    saved=SavedExecutionRecord(request,receipt,run_id='fem-goal:failed',artifacts=ARTIFACTS,schema=version)
    assert SavedExecutionRecord.loads(saved.dumps()).receipt==receipt
    attached=project(request).attach_record('a',saved,select=True)
    assert SavedProject.loads(attached.dumps()).current_record('a').receipt==receipt


def test_interruption_is_not_a_saved_failed_result(monkeypatch):
    def stop(value):raise KeyboardInterrupt('cancelled')
    monkeypatch.setattr(Document,'solve',stop)
    with pytest.raises(KeyboardInterrupt):SavedExecutionRequest(document().dumps()).run()
