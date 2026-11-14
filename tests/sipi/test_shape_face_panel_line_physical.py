# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Actual face-metal lines, independent laws and complete failure transport."""
import json
from types import SimpleNamespace
import numpy as np
import pytest
from scipy.linalg import expm
from sipi import CrossSection
from sipi.constants import mu_0,epsilon_0
from sipi.execution import execute_saved
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject
from sipi.shape_face_panel_line import ShapeFacePanelLineError as ShapePanelLineError,shape_face_current_record as shape_current_record
from sipi.shape_panel_line import _sample_record,shape_current_record as whole_current_record
from sipi.panel_shape_conductor import PanelShapeCurrentError
from sipi.panel_shape_face_conductor import PanelShapeFaceCurrentError
import sipi.panel_shape_face_conductor as face_current
import sipi.shape_face_panel_line as implementation
import sipi.shape_face_conductor as loss_module
import sipi.panel_shape_conductor as current
from test_shape_face_panel_line import document,Document
from test_shape_face_conductor_physical import snapshot
from test_shape_reference_conductor_physical import relative
from test_layered_metal import transfer
from test_execution import network_equal
from test_execution_record import ARTIFACTS
from test_project import project


@pytest.fixture(scope='module')
def observed():
    return [(document(panels=n),document(panels=n).analyze()) for n in (32,64)]


def replay(monkeypatch,observed):
    table={doc.current_options['panels_per_edge']:(doc,r) for doc,r in observed};calls=[]
    def extract(section,**options):
        doc,r=table[options['panels_per_edge']]
        assert section.width==doc.cross_section.section.width
        assert options==doc.current_options
        calls.append(options);return r.current_factors
    monkeypatch.setattr(loss_module,'panel_shape_face_current_factors',extract)
    return calls


def independent(result):
    f=result.frequency;Q=result.current_factors;shape=result.C.shape
    np.testing.assert_allclose(result.C,4.*np.broadcast_to(Q.C0,shape),rtol=1e-12,atol=0)
    assert np.all(result.G==0.)
    np.testing.assert_allclose(result.dielectric.L@Q.C0,epsilon_0*mu_0*np.eye(2),rtol=1e-10,atol=1e-28)
    sigmas=[58e6,58e6,35e6,20e6]+[45e6]*4+[48e6,30e6,40e6,50e6,60e6]
    zs=np.sqrt(2j*np.pi*f[:,None]*mu_0/np.array(sigmas));zs[:,1]=[transfer(x) for x in f]
    expected=sum(zs[:,b,None,None]*result.conductor.boundary_parts[b] for b in range(13))
    np.testing.assert_allclose(result.R+2j*np.pi*f[:,None,None]*result.conductor.L_internal,expected,rtol=1e-12,atol=0)
    errors=[]
    for i,frequency in enumerate(f):
        z=result.R[i]+2j*np.pi*frequency*result.L[i];y=result.G[i]+2j*np.pi*frequency*result.C[i]
        t=expm(np.block([[np.zeros((2,2)),z],[y,np.zeros((2,2))]])*.02)
        a,b,c,d=t[:2,:2],t[:2,2:],t[2:,:2],t[2:,2:];eye=np.eye(2)
        s=np.linalg.solve(np.block([[eye,-a-b/50],[-eye,-50*c-d]]),np.block([[-eye,a-b/50],[-eye,50*c-d]]))
        errors.append(float(np.max(abs(s-result.network.s[i]))))
    assert max(errors)<1e-10
    assert np.linalg.svd(result.network.s,compute_uv=False).max()<=1+1e-10
    np.testing.assert_allclose(result.network.s,result.network.s.swapaxes(-1,-2),atol=1e-10,rtol=0)
    return errors


def test_actual_matched_lines_and_separate_panel_refinement(observed,record_property):
    rows=[]
    for doc,r in observed:
        errors=independent(r)
        assert r.input_json==doc.dumps() and len(r.current_factors.samples)==48
        rows.append(dict(input=doc.to_dict(),loss=snapshot(r.conductor,doc.cross_section.section),
            matrices={k:getattr(r,k).tolist() for k in ('R','L','C','G')},network_errors=errors))
    changes=[]
    for (_,a),(_,b) in zip(observed,observed[1:]):
        changes.append({k:relative(getattr(a,k),getattr(b,k)) for k in ('R','L','C')})
    record_property('face_saved_lines',json.dumps(rows,allow_nan=False))
    record_property('face_saved_panel_changes',json.dumps(changes))
    assert max(changes[-1].values())<=1e-3


def test_coated_face_reuses_identical_currents_and_mesh_refinement(observed,monkeypatch,record_property):
    calls=replay(monkeypatch,observed);doc=document(32);r=doc.analyze();errors=independent(r)
    raw=doc.to_dict();mesh=raw['cross_section']['mesh']
    mesh.update(edge_size=mesh['edge_size']/2,far_size=mesh['far_size']/2,grade=mesh['grade']/2)
    fine=Document.from_dict(raw).analyze();independent(fine)
    assert len(calls)==2
    for k in ('R','L','C','G'):np.testing.assert_array_equal(getattr(r,k),getattr(fine,k))
    record_property('face_saved_coated',json.dumps(dict(input=doc.to_dict(),loss=snapshot(r.conductor,doc.cross_section.section),
        network_errors=errors,refined_input=raw),allow_nan=False))


def test_finite_outer_observation_is_not_an_accuracy_certificate(observed,record_property):
    doc,r=observed[1];raw=doc.to_dict();raw['cross_section']['box']['width']*=2
    raw['cross_section']['layers'][0]['thickness']*=2
    outer=Document.from_dict(raw).analyze();errors=independent(outer)
    changes={k:relative(getattr(r,k),getattr(outer,k)) for k in ('R','L','C')}
    assert all(np.isfinite(list(changes.values())))
    record_property('face_saved_outer_observation',json.dumps(dict(input=raw,loss=snapshot(outer.conductor,Document.from_dict(raw).cross_section.section),
        changes=changes,network_errors=errors,qualified=False),allow_nan=False))


@pytest.mark.parametrize('version',['sipi.execution-record/1','sipi.execution-record/2'])
def test_actual_common_execution_receipt_project_and_boundaries(observed,monkeypatch,record_property,version):
    doc,r=observed[1];monkeypatch.setattr(Document,'analyze',lambda self:r)
    request=SavedExecutionRequest(doc.dumps(),diagnostics=['characteristic','modes']);receipt=request.run();out=receipt['execution']
    assert out['status']=='complete' and out['error'] is None
    network_equal(out['result']['network'],r.network)
    assert out['result']['current_solver']==shape_current_record(r.current_factors,r.panel_settings)
    parts=out['result']['conductor_boundaries'];assert parts['labels']==list(r.conductor.boundary_labels)
    np.testing.assert_array_equal(parts['surface_current_factors_per_m'],r.conductor.boundary_parts)
    np.testing.assert_array_equal(parts['resistance_ohm_per_m'],r.conductor.resistance_parts)
    saved=SavedExecutionRecord(request,receipt,run_id='reference:example',artifacts=ARTIFACTS,schema=version)
    assert SavedExecutionRecord.loads(saved.dumps()).receipt==receipt
    p=project(request).attach_record('a',saved,select=True)
    assert SavedProject.loads(p.dumps()).current_record('a').receipt==receipt
    record_property('face_saved_execution',json.dumps(out,sort_keys=True,allow_nan=False))


@pytest.mark.parametrize('stage',['material-admission','conductor-admission','current','mesh','dielectric','network'])
@pytest.mark.parametrize('version',['sipi.execution-record/1','sipi.execution-record/2'])
def test_each_failure_preserves_exact_input_and_completed_current(observed,monkeypatch,stage,version):
    doc,r=observed[1];monkeypatch.setattr(implementation,'panel_shape_conductor_loss_by_face',lambda *a,**k:r.conductor)
    def fail(*a,**k):raise ValueError('original reference-line failure')
    targets={'material-admission':(implementation,'_material_samples'),
        'conductor-admission':(implementation,'_shape_face_samples'),
        'current':(implementation,'panel_shape_conductor_loss_by_face'),
        'mesh':(CrossSection,'mesh'),'dielectric':(implementation,'_dispersive_from_mesh'),
        'network':(implementation,'rlgc_network')}
    # Freeze normalization before injecting a runtime failure.
    request=SavedExecutionRequest(doc.dumps());import sipi.execution as execution
    monkeypatch.setattr(execution,'_load',lambda *a,**k:doc)
    owner,name=targets[stage];monkeypatch.setattr(owner,name,fail)
    with pytest.raises(ShapePanelLineError) as caught:doc.analyze()
    receipt=request.run();out=receipt['execution'];assert out['status']=='failed' and out['result'] is None
    assert out['error']==caught.value.to_dict() and out['error']['input']==doc.to_dict()
    assert out['error']['stage']==stage and out['error']['cause_type']=='ValueError'
    expected=None if stage in ('material-admission','conductor-admission','current') else shape_current_record(r.current_factors,r.panel_settings)
    assert out['error']['current_solver']==expected
    # Restore normalizer dependencies before record validation, retaining receipt.
    monkeypatch.undo()
    saved=SavedExecutionRecord(request,receipt,run_id='reference:failed',artifacts=ARTIFACTS,schema=version)
    assert SavedExecutionRecord.loads(saved.dumps()).receipt==receipt


@pytest.mark.parametrize('kind',['whole','faces'])
@pytest.mark.parametrize('index',[0,4,16])
def test_partial_current_requests_and_completed_whole_evidence_survive(observed,monkeypatch,kind,index):
    doc,r=observed[1];factors=r.current_factors;calls=[]
    if kind=='faces':
        monkeypatch.setattr(face_current,'panel_shape_current_factors',lambda *a,**k:factors.base)
        samples=factors.samples;module=face_current
    else:samples=factors.base.samples;module=current
    def solve(**kwargs):
        n=len(calls);calls.append(kwargs)
        if n==index:raise ValueError('original saved face-line current failure')
        sample=samples[n]
        return SimpleNamespace(capacitance_per_permittivity=sample.capacitance_per_permittivity,
            current_integrals=factors.base.current_integrals,**dict(sample.diagnostics))
    monkeypatch.setattr(module,'_panel_solver',lambda:solve)
    request=SavedExecutionRequest(doc.dumps());receipt=request.run();out=receipt['execution'];error=out['error'];partial=error['partial_current']
    assert out['status']=='failed' and out['result'] is None and error['stage']=='current'
    assert error['current_solver'] is None and partial['kind']==kind and partial['cause_type']=='ValueError'
    assert partial['failed_request']['request']==calls[-1]
    assert partial['samples']==[_sample_record(s) for s in samples[:index]]
    if kind=='faces':assert partial['whole_current']==whole_current_record(factors.base,doc.current_options)
    else:assert 'whole_current' not in partial
    saved=SavedExecutionRecord(request,receipt,run_id='faces:partial',artifacts=ARTIFACTS,schema='sipi.execution-record/2')
    assert SavedExecutionRecord.loads(saved.dumps()).receipt==receipt


def test_complete_face_derivative_refusal_keeps_both_steps(observed,monkeypatch):
    doc,r=observed[1];factors=r.current_factors
    original=PanelShapeFaceCurrentError('original face step refusal',base=factors.base,samples=factors.samples,step_parts=factors.step_parts)
    def fail(*a,**k):raise original
    monkeypatch.setattr(loss_module,'panel_shape_face_current_factors',fail)
    out=execute_saved(doc.dumps());partial=out['error']['partial_current']
    assert out['status']=='failed' and partial['kind']=='faces' and partial['failed_request'] is None
    assert partial['step_factors_per_m']==factors.step_parts.tolist()
    assert partial['whole_current']==whole_current_record(factors.base,doc.current_options)


@pytest.mark.parametrize('stage',['current','mesh','network'])
def test_interrupt_is_not_a_saved_failure(observed,monkeypatch,stage):
    doc,r=observed[1];monkeypatch.setattr(implementation,'panel_shape_conductor_loss_by_face',lambda *a,**k:r.conductor)
    def interrupt(*a,**k):raise KeyboardInterrupt()
    owner,name={'current':(implementation,'panel_shape_conductor_loss_by_face'),
        'mesh':(CrossSection,'mesh'),'network':(implementation,'rlgc_network')}[stage]
    monkeypatch.setattr(owner,name,interrupt)
    with pytest.raises(KeyboardInterrupt):execute_saved(doc.dumps())
