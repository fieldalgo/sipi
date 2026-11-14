# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Actual saved three-mesh history and explicitly replayed receipt semantics."""
import json
import pytest
from sipi.fem_shape_line import FEMShapeLineError,FEMShapeTransmissionLineDocument
from sipi.fem_shape_conductor import FEMShapeCurrentError
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject
from test_fem_shape_adaptive_document import document,Document
from test_fem_shape_line_physical import independent
from test_execution_record import ARTIFACTS
from test_project import project


@pytest.fixture(scope='module')
def observed():
    doc=document();return doc,doc.analyze()


def test_actual_saved_three_mesh_history_matches_independent_relations(observed,record_property):
    doc,result=observed
    record_property('fem_adaptive_resolution',json.dumps(result.to_dict(),allow_nan=False))
    assert result.completed and not result.accepted and result.stop_reason=='mesh-unaccepted'
    assert result.selected_evaluation is None and len(result.evaluations)==3
    for row in result.evaluations:independent(row.result)


@pytest.mark.parametrize('state',['level-limited','budget','partial-current','later-field'])
@pytest.mark.parametrize('version',['sipi.execution-record/1','sipi.execution-record/2'])
def test_replayed_receipts_retain_mesh_budget_and_typed_failures(observed,monkeypatch,state,version):
    doc,result=observed;raw=doc.to_dict();values={row.input_json:row.result for row in result.evaluations}
    if state=='budget':raw['max_levels']=4;raw['max_solves']=8
    request_doc=Document.from_dict(raw);failed=result.evaluations[2];cur=failed.result.current_factors
    cause=FEMShapeCurrentError('original partial',stage='capacitance-differences',base=cur.base,
        extension_parts=cur.extension_parts,samples=cur.samples[:1],request=(0,0,0,1,cur.step_m)) if state=='partial-current' else ValueError('later field refusal')
    error=FEMShapeLineError(cause,stage='current' if state=='partial-current' else 'dielectric',input_json=failed.input_json,
        factors=None if state=='partial-current' else cur,mesh_observation=failed.result.mesh_observation)
    calls=[]
    def analyze(self):
        calls.append(self.dumps())
        if state in ('partial-current','later-field') and self.dumps()==failed.input_json:raise error
        return values[self.dumps()]
    monkeypatch.setattr(FEMShapeTransmissionLineDocument,'analyze',analyze)
    request=SavedExecutionRequest(request_doc.dumps(),max_evaluations=5);receipt=request.run();out=receipt['execution']
    assert len(calls)==3 and not out['result']['accepted'] and out['result']['selected_evaluation_index'] is None
    if state=='level-limited':
        assert out['status']=='complete' and out['error'] is None and out['result']==result.to_dict()
    else:
        assert out['status']=='failed' and not out['result']['completed']
        if state=='budget':
            assert out['result']['failure'] is None and out['result']['stop_reason']=='budget-exhausted'
            assert out['error']['kind']=='ResolutionBudgetExceeded' and out['error']['input']==request_doc.to_dict()
            assert len(out['result']['evaluations'])==3 and out['error']['details'] is None
        else:
            assert out['error']==out['result']['failure'] and out['error']['details']==error.to_dict()
            assert len(out['result']['evaluations'])==2
    if state!='level-limited' and version=='sipi.execution-record/1':
        with pytest.raises(ValueError,match='null result'):
            SavedExecutionRecord(request,receipt,run_id='fem-adaptive:'+state,artifacts=ARTIFACTS,schema=version)
        return
    saved=SavedExecutionRecord(request,receipt,run_id='fem-adaptive:'+state,artifacts=ARTIFACTS,schema=version)
    assert SavedExecutionRecord.loads(saved.dumps()).receipt==receipt
    attached=project(request).attach_record('a',saved,select=True)
    assert SavedProject.loads(attached.dumps()).current_record('a').receipt==receipt


@pytest.mark.parametrize('kind',['line','adaptive'])
def test_fixed_and_adaptive_fem_v2_generic_failure_contract_remains_bound(monkeypatch,kind):
    from test_fem_shape_resolution_document import document as fixed
    doc=fixed() if kind=='line' else document()
    def fail(self):raise ValueError('original refusal')
    monkeypatch.setattr(FEMShapeTransmissionLineDocument,'analyze',fail)
    request=SavedExecutionRequest(doc.dumps());receipt=request.run();out=receipt['execution']
    assert out['result']['failure']==out['error'] and out['error']['details'] is None
    saved=SavedExecutionRecord(request,receipt,run_id='fem:generic',artifacts=ARTIFACTS,schema='sipi.execution-record/2')
    assert SavedExecutionRecord.loads(saved.dumps()).receipt==receipt
    out['error']['details']={'type':'ValueError'};out['result']['failure']=json.loads(json.dumps(out['error']))
    with pytest.raises(ValueError):SavedExecutionRecord(request,receipt,run_id='fem:corrupt',artifacts=ARTIFACTS,schema='sipi.execution-record/2')
