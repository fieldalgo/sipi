# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Actual saved fields, independent networks and preserved partial execution."""
import json
import numpy as np
import pytest
from scipy.linalg import expm
from sipi import CrossSection
from sipi.project import SavedProject
from sipi.constants import epsilon_0,mu_0
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.dielectric import DebyeDielectric,dielectric_to_dict
import sipi.fem_shape_line as api
from test_fem_shape_line import document,Document
from test_fem_shape_loss_physical import snapshot
from test_layered_metal import transfer
from test_execution import network_equal
from test_execution_record import ARTIFACTS
from test_project import project


@pytest.fixture(scope='module')
def observed():return [(document(factor),document(factor).analyze()) for factor in (1.,.5)]


def independent(result):
    f=result.frequency;cur=result.current_factors
    np.testing.assert_allclose(result.C,4*np.broadcast_to(cur.C0,result.C.shape),rtol=1e-12,atol=0)
    assert np.all(result.G==0.)
    np.testing.assert_allclose(result.dielectric.L@cur.C0,mu_0*epsilon_0*np.eye(2),rtol=1e-10,atol=1e-28)
    zs=np.array([[transfer(x),np.sqrt(2j*np.pi*x*mu_0/35e6),np.sqrt(2j*np.pi*x*mu_0/58e6)] for x in f])
    np.testing.assert_allclose(result.R+2j*np.pi*f[:,None,None]*result.conductor.L_internal,np.einsum('fb,bij->fij',zs,cur.parts),rtol=1e-10,atol=0)
    errors=[]
    for i,x in enumerate(f):
        z=result.R[i]+2j*np.pi*x*result.L[i];y=result.G[i]+2j*np.pi*x*result.C[i]
        t=expm(np.block([[np.zeros((2,2)),z],[y,np.zeros((2,2))]])*.02)
        a,b,c,d=t[:2,:2],t[:2,2:],t[2:,:2],t[2:,2:];eye=np.eye(2)
        s=np.linalg.solve(np.block([[eye,-a-b/50],[-eye,-50*c-d]]),np.block([[-eye,a-b/50],[-eye,50*c-d]]))
        errors.append(float(np.max(abs(s-result.network.s[i]))))
    assert max(errors)<=1e-10 and np.linalg.svd(result.network.s,compute_uv=False).max()<=1+1e-10
    return errors


def test_actual_matched_mesh_lines_and_refinement(observed,record_property):
    rows=[]
    for doc,result in observed:
        rows.append(dict(input=doc.to_dict(),loss=snapshot(result.conductor),current=result.current_record(),network_errors=independent(result)))
        assert result.input_json==doc.dumps()
        mesh=result.mesh_observation;mesh['nodes']=0;assert result.mesh_observation['nodes']>0
    changes={key:float(np.max(abs(getattr(observed[0][1],key)-getattr(observed[1][1],key)))/np.max(abs(getattr(observed[1][1],key)))) for key in ('R','L','C')}
    record_property('fem_saved_lines',json.dumps(rows,allow_nan=False));record_property('fem_saved_mesh_changes',json.dumps(changes))
    assert max(changes.values())<=.01


@pytest.fixture(scope='module')
def common(observed):
    request=SavedExecutionRequest(observed[0][0].dumps(),diagnostics=('characteristic','modes'))
    return request,request.run()


@pytest.mark.parametrize('version',['sipi.execution-record/1','sipi.execution-record/2'])
def test_actual_common_execution_record_and_project(observed,common,version,record_property):
    request,receipt=common;result=observed[0][1];out=receipt['execution']
    assert out['status']=='complete' and out['error'] is None
    assert out['result']['current_solver']==result.current_record()
    network_equal(out['result']['network'],result.network)
    np.testing.assert_array_equal(out['result']['conductor_boundaries']['resistance_ohm_per_m'],result.conductor.resistance_parts)
    saved=SavedExecutionRecord(request,receipt,run_id='fem:example',artifacts=ARTIFACTS,schema=version)
    assert SavedExecutionRecord.loads(saved.dumps()).receipt==receipt
    attached=project(request).attach_record('a',saved,select=True)
    assert SavedProject.loads(attached.dumps()).current_record('a').receipt==receipt
    record_property('fem_saved_execution',json.dumps(out,sort_keys=True,allow_nan=False))


def test_one_mesh_is_shared_with_dispersive_dielectric(observed,monkeypatch,record_property):
    doc,result=observed[-1];raw=doc.to_dict();model=DebyeDielectric(2.,(2.,),(1e9,))
    raw['materials']={layer.name:dielectric_to_dict(model) for layer in doc.cross_section.section.materials}
    changed=Document.from_dict(raw);meshes=[];real=CrossSection.mesh
    def mesh(self,**options):
        value=real(self,**options);meshes.append(value);return value
    def current(mesh,signals,ground):
        assert mesh is meshes[-1].mesh and signals is meshes[-1].signals and ground is meshes[-1].ground
        return result.current_factors
    real_dielectric=api._dispersive_from_mesh
    def dielectric(field,*a,**kw):
        assert field is meshes[-1]
        return real_dielectric(field,*a,**kw)
    monkeypatch.setattr(CrossSection,'mesh',mesh);monkeypatch.setattr(api,'fem_shape_current_factors',current);monkeypatch.setattr(api,'_dispersive_from_mesh',dielectric)
    actual=changed.analyze();eps=2+2/(1+1j*actual.frequency/1e9)
    assert len(meshes)==1 and actual.current_factors is result.current_factors
    np.testing.assert_allclose(actual.C,eps.real[:,None,None]*result.current_factors.C0,rtol=1e-12,atol=0)
    np.testing.assert_allclose(actual.G,-2*np.pi*actual.frequency[:,None,None]*eps.imag[:,None,None]*result.current_factors.C0,rtol=1e-12,atol=0)
    record_property('fem_saved_dispersive',json.dumps(dict(C=actual.C.tolist(),G=actual.G.tolist(),mesh=actual.mesh_observation)))


@pytest.mark.parametrize('stage',['material-admission','conductor-admission','mesh','current','conductor','dielectric','network'])
def test_stage_errors_preserve_input_and_complete_current(observed,monkeypatch,stage):
    doc,result=observed[0];field=doc.cross_section.section.mesh(**doc.cross_section.mesh_options)
    request=SavedExecutionRequest(doc.dumps());import sipi.execution as execution
    monkeypatch.setattr(execution,'_load',lambda *a,**kw:doc)
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**kw:field)
    monkeypatch.setattr(api,'fem_shape_current_factors',lambda *a:result.current_factors)
    def fail(*a,**kw):raise ValueError('original staged failure')
    owner,name={'material-admission':(api,'_material_samples'),'conductor-admission':(api,'_boundary_samples'),
        'mesh':(CrossSection,'mesh'),'current':(api,'fem_shape_current_factors'),
        'conductor':(api,'_boundary_from_factors'),'dielectric':(api,'_dispersive_from_mesh'),'network':(api,'rlgc_network')}[stage]
    monkeypatch.setattr(owner,name,fail)
    with pytest.raises(api.FEMShapeLineError) as caught:doc.analyze()
    receipt=request.run();out=receipt['execution'];assert out['status']=='failed' and out['result'] is None
    assert out['error']==caught.value.to_dict() and out['error']['stage']==stage and out['error']['input']==doc.to_dict()
    expected=None if stage in ('material-admission','conductor-admission','mesh','current') else result.current_record()
    assert out['error']['current_solver']==expected
    monkeypatch.undo()
    saved=SavedExecutionRecord(request,receipt,run_id='fem:failed',artifacts=ARTIFACTS,schema='sipi.execution-record/2')
    assert SavedExecutionRecord.loads(saved.dumps()).receipt==receipt


@pytest.mark.parametrize('version',['sipi.execution-record/1','sipi.execution-record/2'])
def test_typed_partial_current_and_request_survive_common_execution(observed,monkeypatch,version):
    doc,result=observed[0];cur=result.current_factors;request=SavedExecutionRequest(doc.dumps())
    error=api.FEMShapeCurrentError('offset solve',stage='capacitance-differences',base=cur.base,
        extension_parts=cur.extension_parts,samples=cur.samples[:1],request=(0,0,0,1,cur.step_m))
    def fail(*a):raise error
    monkeypatch.setattr(api,'fem_shape_current_factors',fail)
    receipt=request.run();out=receipt['execution'];partial=out['error']['partial_current']
    assert out['status']=='failed' and out['result'] is None and out['error']['current_solver'] is None
    assert partial['stage']==error.stage and partial['failed_request']==list(error.request)
    assert len(partial['samples'])==1 and partial['finite_difference_factors_per_m'] is None
    np.testing.assert_array_equal(partial['extension_factors_per_m'],cur.extension_parts)
    np.testing.assert_array_equal(partial['original_gradient']['surface_current_factors_per_m'],cur.base.parts)
    monkeypatch.undo();saved=SavedExecutionRecord(request,receipt,run_id='fem:partial',artifacts=ARTIFACTS,schema=version)
    assert SavedExecutionRecord.loads(saved.dumps()).receipt==receipt


def test_current_interrupt_propagates(observed,monkeypatch):
    def stop(*a):raise KeyboardInterrupt('cancelled')
    monkeypatch.setattr(api,'fem_shape_current_factors',stop)
    with pytest.raises(KeyboardInterrupt):observed[0][0].analyze()
