# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Actual FEM samples, independent propagation and complete saved failure rows."""
import json
import statistics
import numpy as np
import pytest
from scipy.linalg import sqrtm
from sipi.fem_shape_line import FEMShapeTransmissionLineDocument,FEMShapeLineError
from sipi.fem_shape_conductor import FEMShapeCurrentError
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject
import sipi.fem_shape_study as api
from test_fem_shape_study import document,Document
from test_execution_record import ARTIFACTS
from test_project import project


@pytest.fixture(scope='module')
def observed():
    return {quantity:[(document(quantity,factor),document(quantity,factor).analyze()) for factor in (1.,.5)]
            for quantity in ('impedance_real','differential_forward_impedance_real')}


def independent(line,quantity):
    w=2*np.pi*line.frequency[0];z=line.R[0]+1j*w*line.L[0];y=line.G[0]+1j*w*line.C[0]
    if len(line.names)==1:
        return float((np.sqrt(z[0,0]/y[0,0]) if quantity=='impedance_real' else np.sqrt(z[0,0]*y[0,0])).real)
    gamma=np.asarray(sqrtm(z@y),dtype=complex);zc=np.linalg.solve(gamma,z)
    voltage=np.array([[1.,-1.],[.5,.5]]);mixed=voltage@zc@voltage.T
    return float(mixed[1 if quantity=='common_forward_impedance_real' else 0,
                       1 if quantity=='common_forward_impedance_real' else 0].real)


def serialized(result):
    return dict(result=result.to_dict(),fields=[dict(R=row.result.R.tolist(),L=row.result.L.tolist(),
        G=row.result.G.tolist(),C=row.result.C.tolist()) for row in result.rows])


def test_real_geometry_samples_independent_characteristics_and_mesh(observed,record_property):
    rows={};changes={}
    for quantity,pairs in observed.items():
        rows[quantity]=[]
        for doc,result in pairs:
            assert not result.failed and len(result.rows)==2 and result.input_json==doc.dumps()
            np.testing.assert_array_equal([row.sample_values for row in result.rows],doc.samples())
            for row in result.rows:
                assert row.value==pytest.approx(independent(row.result,quantity),rel=1e-10,abs=0)
                assert row.input_json==FEMShapeTransmissionLineDocument.loads(row.input_json).dumps()
                assert row.to_dict()['current_solver']==row.result.current_record()
            assert result.summary['mean']==pytest.approx(statistics.mean(row.value for row in result.rows),rel=1e-12)
            assert result.summary['sample_std']==pytest.approx(statistics.stdev(row.value for row in result.rows),rel=1e-12)
            rows[quantity].append(serialized(result))
        delta=[]
        for coarse,fine in zip(pairs[0][1].rows,pairs[1][1].rows):
            delta.append(dict(quantity=abs(coarse.value-fine.value)/fine.value,**{
                key:float(np.max(abs(getattr(coarse.result,key)-getattr(fine.result,key)))/np.max(abs(getattr(fine.result,key))))
                for key in ('R','L','C')}))
        changes[quantity]=delta
    record_property('fem_study_geometry',json.dumps(rows,allow_nan=False))
    record_property('fem_study_mesh',json.dumps(changes,allow_nan=False))
    assert max(value for group in changes.values() for row in group for value in row.values())<=.01


@pytest.mark.parametrize('quantity',['attenuation','common_forward_impedance_real'])
def test_remaining_quantities_reuse_exact_extracted_fields(observed,monkeypatch,quantity):
    parent='impedance_real' if quantity=='attenuation' else 'differential_forward_impedance_real'
    original=observed[parent][0][1];by_input={row.input_json:row.result for row in original.rows};calls=[]
    def analyze(doc):calls.append(doc.dumps());return by_input[doc.dumps()]
    monkeypatch.setattr(FEMShapeTransmissionLineDocument,'analyze',analyze)
    result=document(quantity).analyze();assert not result.failed and len(calls)==2
    for row in result.rows:assert row.value==pytest.approx(independent(row.result,quantity),rel=1e-10,abs=0)


def test_actual_material_samples_keep_inputs_and_independent_attenuation(record_property):
    doc=document('attenuation',material=True);result=doc.analyze();assert not result.failed
    for row,loss in zip(result.rows,(.01,.03)):
        assert row.to_dict()['material_evaluation']['materials']['dielectric']['parameters']['tan_delta']==loss
        assert row.value==pytest.approx(independent(row.result,'attenuation'),rel=1e-10,abs=0)
        np.testing.assert_allclose(row.result.G,2*np.pi*2e9*loss*row.result.C,rtol=1e-12,atol=0)
    record_property('fem_study_material',json.dumps(serialized(result),allow_nan=False))


@pytest.mark.parametrize('version',['sipi.execution-record/1','sipi.execution-record/2'])
def test_complete_common_records_and_projects_use_observed_fields(observed,monkeypatch,version):
    doc,result=observed['differential_forward_impedance_real'][0]
    by_input={row.input_json:row.result for row in result.rows}
    monkeypatch.setattr(FEMShapeTransmissionLineDocument,'analyze',lambda value:by_input[value.dumps()])
    request=SavedExecutionRequest(doc.dumps());receipt=request.run()
    assert receipt['execution']['status']=='complete' and receipt['execution']['result']==result.to_dict()
    saved=SavedExecutionRecord(request,receipt,run_id='fem-study:complete',artifacts=ARTIFACTS,schema=version)
    assert SavedExecutionRecord.loads(saved.dumps()).receipt==receipt
    attached=project(request).attach_record('a',saved,select=True)
    assert SavedProject.loads(attached.dumps()).current_record('a').receipt==receipt


@pytest.mark.parametrize('partial',[False,True])
def test_failed_middle_row_keeps_evidence_and_later_rows_run(observed,monkeypatch,partial):
    doc,results=observed['differential_forward_impedance_real'][0];current=results.rows[0].result.current_factors
    inputs=[row.input_json for row in results.rows];by_input={row.input_json:row.result for row in results.rows}
    samples=np.array([doc.samples()[0],doc.samples()[0],doc.samples()[1]])
    monkeypatch.setattr(Document,'samples',lambda self:samples.copy());calls=[]
    def analyze(value):
        index=len(calls);calls.append(value.dumps())
        if index==1:
            cause=FEMShapeCurrentError('sample failed',stage='capacitance-differences',base=current.base,
                extension_parts=current.extension_parts,samples=current.samples[:1],request=(0,0,0,1,current.step_m)) if partial else ValueError('dielectric failed')
            raise FEMShapeLineError(cause,stage='current' if partial else 'dielectric',input_json=value.dumps(),
                factors=None if partial else current,mesh_observation=results.rows[0].result.mesh_observation)
        return by_input[value.dumps()]
    monkeypatch.setattr(FEMShapeTransmissionLineDocument,'analyze',analyze)
    request=SavedExecutionRequest(doc.dumps());receipt=request.run();out=receipt['execution'];rows=out['result']['rows']
    assert out['status']=='incomplete' and out['error'] is None and out['result']['summary'] is None
    assert calls==[inputs[0],inputs[0],inputs[1]] and rows[2]['phase']=='complete'
    assert rows[1]['phase']=='extraction' and rows[1]['current_solver'] is None and rows[1]['value'] is None
    details=rows[1]['cause_details'];assert details['input']==json.loads(inputs[0])
    if partial:
        assert details['current_solver'] is None and len(details['partial_current']['samples'])==1
        assert details['partial_current']['finite_difference_factors_per_m'] is None
    else:assert details['current_solver']==results.rows[0].result.current_record()
    saved=SavedExecutionRecord(request,receipt,run_id='fem-study:partial',artifacts=ARTIFACTS,schema='sipi.execution-record/2')
    assert SavedExecutionRecord.loads(saved.dumps()).receipt==receipt


def test_diagnostic_failure_retains_complete_extraction(observed,monkeypatch):
    doc,result=observed['impedance_real'][0];by_input={row.input_json:row.result for row in result.rows}
    monkeypatch.setattr(FEMShapeTransmissionLineDocument,'analyze',lambda value:by_input[value.dumps()])
    def fail(*args):raise ValueError('diagnostic failed')
    monkeypatch.setattr(api,'_quantity',fail);failed=doc.analyze()
    assert failed.failed==2 and failed.summary is None
    for original,row in zip(result.rows,failed.rows):
        assert row.phase=='diagnostic' and row.result is original.result
        assert row.to_dict()['current_solver']==original.result.current_record() and row.cause_details is None
