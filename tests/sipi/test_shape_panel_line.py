# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
import json
from types import SimpleNamespace
import numpy as np
import pytest
from scipy.linalg import expm

from sipi import CrossSection
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.line_model import TransmissionLineDocument
from sipi.shape_panel_line import ShapePanelTransmissionLineDocument, ShapePanelLineError
import sipi.shape_panel_line as candidate
import sipi.panel_shape_conductor as current
from sipi.execution import normalize_saved, execute_saved
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.constants import epsilon_0, mu_0
from test_panel_line import base
from test_layered_panel_goal import material
from test_layered_metal import transfer
from test_execution import network_equal
from test_execution_record import ARTIFACTS


def document(coated=False, *, perfect=False):
    line=base(perfect)
    if coated:
        raw=line.to_dict();raw['schema']='sipi.transmission-line/7'
        if not perfect:
            raw['conductor']['conductors']={name:material() for name in raw['conductor']['conductors']}
            raw['conductor']['reference']=material()
        line=TransmissionLineDocument.from_dict(raw)
    panel=PanelTransmissionLineDocument(line,panels_per_edge=16,ground_modes=512,interpolation_degree=16,
        schema='sipi.panel-transmission-line/2' if coated else 'sipi.panel-transmission-line/1')
    return ShapePanelTransmissionLineDocument(panel)


@pytest.mark.parametrize('coated',[False,True])
def test_field_free_canonical_snapshot_and_explicit_method(monkeypatch,coated):
    forbidden=lambda *a,**k:pytest.fail('normalization reached fields')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    monkeypatch.setattr(current,'_panel_solver',forbidden)
    doc=document(coated);text=doc.dumps()
    assert text==normalize_saved(text)==ShapePanelTransmissionLineDocument.loads(text).dumps()
    raw=doc.to_dict();raw['line']['panel']['panels_per_edge']=256
    raw['line']['line']['conductor']['reference']['conductivity']=1.
    options=doc.current_options;options['step_fraction']=.01
    assert doc.dumps()==text and doc.line.to_dict()==doc.to_dict()['line']
    with pytest.raises(ValueError):PanelTransmissionLineDocument.loads(text)


@pytest.mark.parametrize('where',['root','panel-line','panel','line','conductor','coating'])
@pytest.mark.parametrize('kind',['missing','extra'])
def test_strict_nested_contracts(where,kind):
    data=document(True).to_dict();nested=data['line'];line=nested['line']
    target={'root':data,'panel-line':nested,'panel':nested['panel'],'line':line,
        'conductor':line['conductor'],'coating':line['conductor']['reference']['coatings'][0]}[where]
    if kind=='missing':target.pop(next(iter(target)))
    else:target['unexpected']=0
    with pytest.raises(ValueError):ShapePanelTransmissionLineDocument.from_dict(data)


@pytest.mark.parametrize('value',[None,True,0.,1e-6,.1,'0.001',float('nan'),float('inf')])
def test_invalid_step_is_field_free(monkeypatch,value):
    monkeypatch.setattr(current,'_panel_solver',lambda:pytest.fail('invalid step reached fields'))
    raw=document().to_dict();raw['step_fraction']=value
    with pytest.raises(ValueError):ShapePanelTransmissionLineDocument.from_dict(raw)


@pytest.mark.parametrize('kind',['schema','duplicate','nonfinite','nested','zero','wrong-type'])
def test_invalid_inputs(kind):
    doc=document();text=doc.dumps()
    if kind=='schema':text=text.replace('sipi.shape-panel-transmission-line/1','sipi.shape-panel-transmission-line/2')
    if kind=='duplicate':text=text.replace('"step_fraction": 0.001','"step_fraction": 0.001, "step_fraction": 0.001')
    if kind=='nonfinite':text=text.replace('"step_fraction": 0.001','"step_fraction": NaN')
    if kind=='nested':text=text.replace('sipi.panel-transmission-line/1','sipi.panel-transmission-line/2')
    if kind=='zero':
        raw=doc.to_dict();raw['line']['line']['cross_section']['traces'][0]['thickness']=0.;text=json.dumps(raw)
    if kind=='wrong-type':
        with pytest.raises(TypeError):ShapePanelTransmissionLineDocument(base())
        return
    with pytest.raises(ValueError):ShapePanelTransmissionLineDocument.loads(text)


def test_frequency_budget_precedes_any_field_solve(monkeypatch):
    raw=document().to_dict();raw['line']['line']['frequency_hz']=[1e9,2e9,4e9]
    doc=ShapePanelTransmissionLineDocument.from_dict(raw)
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',lambda self:pytest.fail('budget reached fields'))
    with pytest.raises(ValueError,match='before any field solve'):execute_saved(doc.dumps(),max_evaluations=2)


@pytest.fixture(scope='module',params=[False,True],ids=['legacy','coated'])
def extracted(request):
    doc=document(request.param)
    return doc,doc.analyze()


def test_uniform_dielectric_and_independent_metal_network(extracted,record_property):
    doc,result=extracted;factors=result.current_factors;f=result.frequency
    np.testing.assert_allclose(result.C,4.2*np.broadcast_to(factors.C0,result.C.shape),rtol=1e-12,atol=0)
    np.testing.assert_allclose(result.G,2*np.pi*f[:,None,None]*.02*result.C,rtol=1e-12,atol=0)
    np.testing.assert_allclose(result.dielectric.L@factors.C0,epsilon_0*mu_0*np.eye(2),atol=1e-28,rtol=1e-10)
    coated=doc.line.to_dict()['schema'].endswith('/2')
    expected=np.zeros_like(result.R,dtype=complex)
    for b,sigma in enumerate((58e6,35e6,45e6)):
        z=np.array([transfer(x) for x in f]) if coated else np.sqrt(2j*np.pi*f*mu_0/sigma)
        expected+=z[:,None,None]*factors.parts[b]
    np.testing.assert_allclose(result.R+2j*np.pi*f[:,None,None]*result.conductor.L_internal,expected,rtol=1e-10,atol=0)
    errors=[]
    for i,frequency in enumerate(f):
        omega=2*np.pi*frequency;z=result.R[i]+1j*omega*result.L[i];y=result.G[i]+1j*omega*result.C[i]
        generator=np.block([[np.zeros((2,2)),z],[y,np.zeros((2,2))]])
        t=expm(generator*.02);a,b,c,d=t[:2,:2],t[:2,2:],t[2:,:2],t[2:,2:];eye=np.eye(2)
        expected_s=np.linalg.solve(np.block([[eye,-a-b/50],[-eye,-50*c-d]]),np.block([[-eye,a-b/50],[-eye,50*c-d]]))
        errors.append(float(np.max(abs(result.network.s[i]-expected_s))))
    assert max(errors)<1e-10
    assert result.input_json==doc.dumps() and dict(result.panel_settings)==doc.current_options
    assert len(factors.samples)==13
    record_property('shape_line_fields',json.dumps(dict(input=doc.to_dict(),
        quantities={k:getattr(result,k).tolist() for k in ('R','L','C','G')},C0=factors.C0.tolist(),
        current=candidate.shape_current_record(factors,result.panel_settings),network_errors=errors),sort_keys=True))


def test_actual_common_replay_and_saved_record(extracted,monkeypatch,record_property):
    doc,result=extracted;calls=[];original=CrossSection.mesh
    def mesh(self,**options):calls.append(options);return original(self,**options)
    monkeypatch.setattr(CrossSection,'mesh',mesh)
    request=SavedExecutionRequest(doc.dumps(),diagnostics=['characteristic','modes'])
    receipt=request.run();out=receipt['execution']
    saved_record=SavedExecutionRecord(request,receipt,run_id='shape:example',artifacts=ARTIFACTS)
    restored=SavedExecutionRecord.loads(saved_record.dumps())
    assert restored.receipt==receipt and restored.prepare().to_dict()==request.to_dict()
    assert out['status']=='complete' and out['error'] is None and out['input']==doc.to_dict()
    assert calls==[doc.line.line.cross_section.mesh_options]
    network_equal(out['result']['network'],result.network)
    saved=out['result']['current_solver']
    assert saved==candidate.shape_current_record(result.current_factors,result.panel_settings)
    assert saved['kind']=='grounded-rectangle-capacitance-shape'
    for key,unit in [('R','R_ohm_per_m'),('L','L_h_per_m'),('C','C_f_per_m'),('G','G_s_per_m')]:
        np.testing.assert_array_equal(out['result'][unit],getattr(result,key))
    record_property('saved_shape_current',json.dumps(saved,sort_keys=True))


def test_perfect_line_has_zero_loss_and_same_matched_fields(extracted,monkeypatch):
    doc,result=extracted;raw=doc.to_dict();raw['line']['line']['conductor']={'kind':'perfect'}
    perfect=ShapePanelTransmissionLineDocument.from_dict(raw)
    monkeypatch.setattr(candidate,'panel_shape_current_factors',lambda *a,**k:result.current_factors)
    r=perfect.analyze();assert r.conductor is None and np.all(r.R==0)
    np.testing.assert_array_equal(r.C,result.C);np.testing.assert_array_equal(r.G,result.G)
    np.testing.assert_array_equal(r.L,np.broadcast_to(result.dielectric.L,result.C.shape))


def test_separate_panel_and_outer_observations(extracted,record_property):
    doc,base_result=extracted;results=[base_result];inputs=[doc.to_dict()]
    for width,height,modes in ((.004,.002,512),(.006,.003,768),(.008,.004,1024)):
        raw=doc.to_dict();raw['line']['panel'].update(panels_per_edge=32,ground_modes=modes)
        cross=raw['line']['line']['cross_section'];cross['box']['width']=width;cross['layers'][0]['thickness']=height
        candidate_doc=ShapePanelTransmissionLineDocument.from_dict(raw);results.append(candidate_doc.analyze());inputs.append(raw)
    changes=[]
    for before,after in zip(results,results[1:]):
        row={}
        for key in ('R','L','C','G'):
            a,b=getattr(before,key),getattr(after,key)
            row[key]=float(np.max(abs(a-b))/np.max(abs(b)))
        changes.append(row)
    record_property('shape_line_resolution_observations',json.dumps(dict(inputs=inputs,
        matrices=[{k:getattr(r,k).tolist() for k in ('R','L','C','G')} for r in results],changes=changes),sort_keys=True))
    # Report finite outer observations; they are not a replacement convergence gate.
    assert all(np.isfinite(v) for row in changes for v in row.values())
    assert max(changes[0].values())<=1e-3


@pytest.mark.parametrize('stage',['material-admission','conductor-admission','mesh','dielectric','network'])
def test_each_line_failure_preserves_completed_currents(extracted,monkeypatch,stage):
    doc,result=extracted
    monkeypatch.setattr(candidate,'panel_shape_conductor_loss_by_boundary',lambda *a,**k:result.conductor)
    def fail(*a,**k):raise ValueError('original staged failure')
    targets={'material-admission':(candidate,'_material_samples'),'conductor-admission':(candidate,'_conductor'),
        'mesh':(CrossSection,'mesh'),'dielectric':(candidate,'_dispersive_from_mesh'),'network':(candidate,'rlgc_network')}
    owner,name=targets[stage];monkeypatch.setattr(owner,name,fail)
    with pytest.raises(ShapePanelLineError) as caught:doc.analyze()
    error=caught.value;assert error.stage==stage and error.cause_type=='ValueError'
    out=execute_saved(doc.dumps());assert out['status']=='failed' and out['result'] is None
    assert out['error']==error.to_dict() and out['error']['input']==doc.to_dict()
    current_record=out['error']['current_solver']
    if stage.endswith('admission'):assert current_record is None
    else:assert current_record==candidate.shape_current_record(result.current_factors,result.panel_settings)
    out['error']['stage']='changed';assert error.to_dict()['stage']==stage


@pytest.mark.parametrize('index',[0,3,12])
def test_current_failure_keeps_exact_partial_requests(extracted,monkeypatch,index):
    doc,result=extracted;calls=[]
    def solve(**kwargs):
        n=len(calls);calls.append(kwargs)
        if n==index:raise ValueError('original current failure')
        sample=result.current_factors.samples[n]
        return SimpleNamespace(capacitance_per_permittivity=sample.capacitance_per_permittivity,
            current_integrals=result.current_factors.current_integrals,**dict(sample.diagnostics))
    monkeypatch.setattr(current,'_panel_solver',lambda:solve)
    out=execute_saved(doc.dumps());error=out['error']
    assert out['status']=='failed' and error['stage']=='current'
    assert error['current_solver'] is None and error['cause_type']=='PanelShapeCurrentError'
    partial=error['partial_current'];assert len(partial['samples'])==index
    assert partial['cause_type']=='ValueError'
    saved=dict(calls[-1]);saved['width'],saved['height']=saved.pop('box_size')  # saved records keep width/height
    assert partial['failed_request']['request']==saved
    assert partial['samples']==[candidate._sample_record(s) for s in result.current_factors.samples[:index]]


@pytest.mark.parametrize('stage',['current','mesh','network'])
def test_interrupt_propagates(extracted,monkeypatch,stage):
    doc,result=extracted
    monkeypatch.setattr(candidate,'panel_shape_conductor_loss_by_boundary',lambda *a,**k:result.conductor)
    def interrupt(*a,**k):raise KeyboardInterrupt()
    owner,name={'current':(candidate,'panel_shape_conductor_loss_by_boundary'),
        'mesh':(CrossSection,'mesh'),'network':(candidate,'rlgc_network')}[stage]
    monkeypatch.setattr(owner,name,interrupt)
    with pytest.raises(KeyboardInterrupt):execute_saved(doc.dumps())
