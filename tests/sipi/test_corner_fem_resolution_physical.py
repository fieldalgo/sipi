# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Actual saved four-line assessment; transport replay preserves all evidence."""
import json
import pytest
from sipi.fem_shape_line import FEMShapeLineError
from sipi.corner_fem_line import CornerFEMShapeTransmissionLineDocument
from sipi.fem_shape_conductor import FEMShapeCurrentError
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject
from test_corner_fem_resolution_document import document,Document
from test_fem_shape_line_physical import independent
from test_execution_record import ARTIFACTS
from test_project import project


@pytest.fixture(scope='module')
def observed():
    doc=document();return doc,doc.analyze()


def test_actual_saved_resolution_and_independent_relations(observed,record_property):
    doc,result=observed;record_property('corner_fem_resolution',json.dumps(result.to_dict(),allow_nan=False))
    assert result.completed and not result.accepted and result.failure is None
    assert len(result.evaluations)==4 and len(result.comparisons)==3
    for row in result.evaluations:independent(row.result)


@pytest.mark.parametrize('state',['original','selected-capacitance','exact-disagreement','partial-failure','complete-current-failure'])
@pytest.mark.parametrize('version',['sipi.execution-record/1','sipi.execution-record/2'])
def test_observed_assessment_record_project_and_failure(observed,monkeypatch,state,version):
    doc,result=observed;raw=doc.to_dict();values={r.input_json:r.result for r in result.evaluations}
    calls=[];failed=result.evaluations[2];cur=failed.result.current_factors
    partial=FEMShapeCurrentError('original partial',stage='capacitance-differences',base=cur.base,
        extension_parts=cur.extension_parts,samples=cur.samples[:1],request=(0,0,0,1,cur.step_m))
    error=FEMShapeLineError(partial if state=='partial-failure' else ValueError('later failure'),
        stage='current' if state=='partial-failure' else 'dielectric',input_json=failed.input_json,
        factors=None if state=='partial-failure' else cur,mesh_observation=failed.result.mesh_observation)
    if state=='selected-capacitance':raw['tolerances']={k:v for k,v in raw['tolerances'].items() if k in ('C_f_per_m','G_s_per_m')}
    if state=='exact-disagreement':raw['tolerances']['R_ohm_per_m']=dict(relative=0.,absolute=0.)
    request_doc=Document.from_dict(raw)
    def analyze(self):
        calls.append(self.dumps())
        if state.endswith('failure') and self.dumps()==failed.input_json:raise error
        return values[self.dumps()]
    monkeypatch.setattr(CornerFEMShapeTransmissionLineDocument,'analyze',analyze)
    request=SavedExecutionRequest(request_doc.dumps());receipt=request.run();out=receipt['execution']
    if state.endswith('failure'):
        assert len(calls)==3 and out['status']=='failed' and not out['result']['completed']
        assert out['error']==out['result']['failure'] and out['error']['details']==error.to_dict()
        assert len(out['result']['evaluations'])==2 and not out['result']['accepted']
        details=out['error']['details']
        if state=='partial-failure':assert len(details['partial_current']['samples'])==1 and details['current_solver'] is None
        else:assert details['current_solver']==failed.result.current_record()
    else:
        assert len(calls)==4 and out['status']=='complete' and out['error'] is None
        assert out['result']['completed'] and out['result']['accepted']==(state=='selected-capacitance')
        if state=='original':assert out['result']==result.to_dict()
    if state.endswith('failure') and version=='sipi.execution-record/1':
        with pytest.raises(ValueError,match='failed execution needs null result'):
            SavedExecutionRecord(request,receipt,run_id='fem-resolution:'+state,artifacts=ARTIFACTS,schema=version)
        return
    saved=SavedExecutionRecord(request,receipt,run_id='fem-resolution:'+state,artifacts=ARTIFACTS,schema=version)
    assert SavedExecutionRecord.loads(saved.dumps()).receipt==receipt
    attached=project(request).attach_record('a',saved,select=True)
    assert SavedProject.loads(attached.dumps()).current_record('a').receipt==receipt


@pytest.mark.parametrize('change',['missing-details','wrong-type','wrong-input','wrong-message','extra-details','untyped-details'])
def test_failed_v2_binds_typed_details_to_original_error(observed,monkeypatch,change):
    doc,result=observed;failed=result.evaluations[0]
    error=FEMShapeLineError(ValueError('preserved'),stage='dielectric',input_json=failed.input_json,
        factors=failed.result.current_factors,mesh_observation=failed.result.mesh_observation)
    def fail(self):raise error
    monkeypatch.setattr(CornerFEMShapeTransmissionLineDocument,'analyze',fail)
    request=SavedExecutionRequest(doc.dumps());receipt=request.run();out=receipt['execution'];cause=out['error']
    if change=='missing-details':cause.pop('details')
    if change=='wrong-type':cause['details']['type']='other'
    if change=='wrong-input':cause['details']['input']['length_m']=1.
    if change=='wrong-message':cause['details']['message']='replaced'
    if change=='extra-details':cause['details']['other']=1
    if change=='untyped-details':cause['kind']='ValueError'
    out['result']['failure']=json.loads(json.dumps(cause))
    with pytest.raises(ValueError):SavedExecutionRecord(request,receipt,run_id='fem-resolution:corrupt',artifacts=ARTIFACTS,schema='sipi.execution-record/2')


def test_actual_smaller_corner_four_stages_keep_original_allowances(record_property):
    from test_corner_fem_resolution import inputs,TOLERANCES
    from sipi import assess_corner_fem_shape_line_resolution
    base,outer=inputs(.5)
    report=assess_corner_fem_shape_line_resolution(base,outer_documents=outer,tolerances=TOLERANCES)
    record_property('corner_fem_resolution_half',json.dumps(report.to_dict(),allow_nan=False))
    assert report.completed and report.failure is None and len(report.evaluations)==4
    assert [row.reference_index for row in report.comparisons]==[0,1,1]
    for row in report.evaluations:
        independent(row.result)
        saved=CornerFEMShapeTransmissionLineDocument.loads(row.input_json)
        assert saved.corner_size==(2.5e-6 if row.stage=='base' else 1.25e-6)
    for comparison in report.comparisons:
        assert set(comparison.allowances)==set(TOLERANCES)
        assert all(t.absolute==0 and t.relative==.01 for t in report.tolerances.values())
