# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved tensor fitting, strict admission and pre-optimizer transport budgets."""
import json
import numpy as np
import pytest
from sipi import CrossSection,CrossSectionDocument,coupled_microstrip
from sipi.dielectric import TensorDebyeDielectric,dielectric_from_dict
from sipi.tensor_dielectric_fit import fit_tensor_debye
from sipi.tensor_dielectric_fit_document import TensorDebyeFitDocument
from sipi.execution import execute_saved,normalize_saved,saved_schemas
from sipi.execution_request import SavedExecutionRequest
from sipi.line_model import TransmissionLineDocument

F=np.geomspace(1e6,1e12,17)
MODEL=TensorDebyeDielectric([2,3],[[4,.5],[.25,3]],[1e8,1e10],[0,.7],.31)


def document(mismatch=False,weights=None):
    eps=MODEL.permittivity(F)
    return TensorDebyeFitDocument(F,eps_real=eps.real,
        eps_loss=-eps.imag+(.01*np.eye(2) if mismatch else 0),
        relaxation_hz=MODEL.relaxation_hz,angles_rad=MODEL.angles_rad,
        eps_inf_angle_rad=MODEL.eps_inf_angle_rad,max_error=1e-8,weights=weights)


@pytest.mark.parametrize('mismatch',[False,True])
def test_exact_direct_result_and_separate_completed_sample_acceptance(mismatch):
    doc=document(mismatch,weights=np.geomspace(.5,3,len(F)));raw=doc.to_dict()
    direct=fit_tensor_debye(F,eps_real=raw['eps_real'],eps_loss=raw['eps_loss'],
        relaxation_hz=raw['relaxation_hz'],angles_rad=raw['angles_rad'],
        eps_inf_angle_rad=raw['eps_inf_angle_rad'],weights=raw['weights'],max_error=raw['max_error'])
    output=execute_saved(doc.dumps(),max_evaluations=len(F))
    assert output['status']=='complete' and output['error'] is None
    assert output['input']==raw and output['result']==direct.to_dict()
    assert output['result']['accepted'] is (not mismatch)
    assert len(output['result']['residual']['real'])==len(F)
    json.dumps(output,allow_nan=False)
    request=SavedExecutionRequest(doc.dumps(),max_evaluations=len(F))
    receipt=request.run()
    assert receipt['execution']==output and receipt['request']['request_id']==request.request_id
    assert receipt['request']['input']==raw


def test_nine_keys_detached_roundtrip_and_default_resolution():
    eps=MODEL.permittivity(F);f=F.copy();real=eps.real.copy();loss=-eps.imag.copy()
    poles=np.array(MODEL.relaxation_hz);angles=np.array(MODEL.angles_rad)
    doc=TensorDebyeFitDocument(f,eps_real=real,eps_loss=loss,relaxation_hz=poles,angles_rad=angles,max_error=1e-8)
    saved=doc.dumps();raw=doc.to_dict()
    assert set(raw)=={'schema','frequency_hz','eps_real','eps_loss','relaxation_hz','angles_rad','eps_inf_angle_rad','weights','max_error'}
    assert raw['weights']==[1.]*len(F) and raw['eps_inf_angle_rad']==0.
    f[:]=0;real[:]=1;loss[:]=0;poles[:]=1;angles[:]=0
    raw['eps_real'][0][0][0]=99;raw['weights'][0]=-1
    assert doc.dumps()==saved==TensorDebyeFitDocument.loads(saved).dumps()==normalize_saved(saved)
    assert TensorDebyeFitDocument.loads(saved).analyze().to_dict()==doc.analyze().to_dict()
    assert 'sipi.tensor-dielectric-fit/1' in saved_schemas()


def test_normalize_and_prepare_do_not_fit_or_mesh(monkeypatch):
    import sipi.tensor_dielectric_fit as implementation
    raw=document().to_dict()
    def forbidden(*a,**k):pytest.fail('parsing/preparation reached SVD, optimizer or fields')
    monkeypatch.setattr(implementation.np.linalg,'svd',forbidden)
    monkeypatch.setattr(implementation,'nnls',forbidden)
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    doc=TensorDebyeFitDocument.from_dict(raw)
    assert normalize_saved(doc.dumps())==doc.dumps()
    assert SavedExecutionRequest(doc.dumps()).input_json==doc.dumps()


def test_frequency_budget_boundary_precedes_svd_optimizer_and_calls_once(monkeypatch):
    import sipi.tensor_dielectric_fit as implementation
    doc=document();original=implementation.nnls;calls=[]
    with monkeypatch.context() as context:
        def forbidden(*a,**k):pytest.fail('over-budget fit reached numerical work')
        context.setattr(implementation.np.linalg,'svd',forbidden);context.setattr(implementation,'nnls',forbidden)
        with pytest.raises(ValueError,match='frequency count'):execute_saved(doc.dumps(),max_evaluations=len(F)-1)
        with pytest.raises(ValueError,match='frequency count'):SavedExecutionRequest(doc.dumps(),max_evaluations=len(F)-1).run()
    def counted(*a,**k):calls.append(k['maxiter']);return original(*a,**k)
    monkeypatch.setattr(implementation,'nnls',counted)
    result=execute_saved(doc.dumps(),max_evaluations=len(F))
    assert result['result']['accepted'] and calls==[10*2*(len(MODEL.relaxation_hz)+1)]


def test_input_byte_cap_and_controls_preserve_exact_request_identity(monkeypatch):
    import sipi.tensor_dielectric_fit as implementation
    text=document().dumps();size=len(text.encode('utf-8'))
    request=SavedExecutionRequest(text,max_input_bytes=size,max_evaluations=len(F))
    compact=json.dumps(json.loads(text))
    assert SavedExecutionRequest(compact,max_input_bytes=size,max_evaluations=len(F)).request_id==request.request_id
    assert SavedExecutionRequest(text,max_input_bytes=size+1,max_evaluations=len(F)).request_id!=request.request_id
    assert request.run()['execution']['status']=='complete'
    def forbidden(*a,**k):pytest.fail('oversized input reached optimizer')
    monkeypatch.setattr(implementation,'nnls',forbidden)
    with pytest.raises(ValueError):execute_saved(text,max_input_bytes=size-1)
    with pytest.raises(ValueError):SavedExecutionRequest(text,max_input_bytes=size-1)
    with pytest.raises(ValueError,match='diagnostics'):SavedExecutionRequest(text,diagnostics=['modes'])


def test_unidentifiable_and_optimizer_failures_keep_exceptions(monkeypatch):
    import sipi.tensor_dielectric_fit as implementation
    raw=document().to_dict();raw['relaxation_hz']=[1e-300,2e-300];raw['angles_rad']=[0,0]
    doc=TensorDebyeFitDocument.from_dict(raw);assert normalize_saved(doc.dumps())==doc.dumps()
    def failed(*a,**k):raise RuntimeError('retained tensor optimizer failure')
    monkeypatch.setattr(implementation,'nnls',failed)
    with pytest.raises(ValueError,match='full rank'):execute_saved(doc.dumps())
    with pytest.raises(RuntimeError,match='retained tensor optimizer failure'):execute_saved(document().dumps())
    with pytest.raises(RuntimeError,match='retained tensor optimizer failure'):SavedExecutionRequest(document().dumps()).run()


def test_fitted_model_reuses_saved_line_contract_without_implicit_fields(monkeypatch):
    output=execute_saved(document().dumps());model=dielectric_from_dict(output['result']['model'])
    np.testing.assert_array_equal(model.permittivity(F).real,output['result']['predicted']['real'])
    section=coupled_microstrip(width=.5e-3,gap=.3e-3,substrate_height=.5e-3,eps_r=4,
        thickness=35e-6,box_width=8e-3,air_height=4e-3)
    def forbidden(*a,**k):pytest.fail('saved line normalization performed fields')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    line=TransmissionLineDocument(CrossSectionDocument(section),[1e6,1e8,1e10],
        materials={'substrate':model},conductor={'kind':'perfect'},length=.01)
    assert normalize_saved(line.dumps())==line.dumps()
    assert line.to_dict()['materials']['substrate']==output['result']['model']


@pytest.mark.parametrize('missing',['schema','frequency_hz','eps_real','eps_loss','relaxation_hz','angles_rad','eps_inf_angle_rad','weights','max_error'])
def test_every_missing_key_rejects(missing):
    raw=document().to_dict();raw.pop(missing)
    with pytest.raises(ValueError):TensorDebyeFitDocument.from_dict(raw)


@pytest.mark.parametrize('kind',['future','extra','null_weights','null_angles','null_high','bool_frequency','bool_pole','bool_angle','bool_high','bool_limit',
 'bool_weight','duplicate_frequency','duplicate_poles','negative_pole','real_shape','loss_shape','real_boolean','loss_complex','real_asymmetric','loss_indefinite','below_one',
 'weight_shape','zero_weight','zero_limit','nonfinite_real','extra_nested'])
def test_strict_saved_input_rejects_before_fitting(monkeypatch,kind):
    import sipi.tensor_dielectric_fit as implementation
    raw=document().to_dict()
    if kind=='future':raw['schema']='sipi.tensor-dielectric-fit/2'
    if kind=='extra':raw['extra']=0
    if kind=='null_weights':raw['weights']=None
    if kind=='null_angles':raw['angles_rad']=None
    if kind=='null_high':raw['eps_inf_angle_rad']=None
    if kind=='bool_frequency':raw['frequency_hz'][0]=True
    if kind=='bool_pole':raw['relaxation_hz'][0]=True
    if kind=='bool_angle':raw['angles_rad'][0]=False
    if kind=='bool_high':raw['eps_inf_angle_rad']=False
    if kind=='bool_limit':raw['max_error']=True
    if kind=='bool_weight':raw['weights'][0]=True
    if kind=='duplicate_frequency':raw['frequency_hz'][1]=raw['frequency_hz'][0]
    if kind=='duplicate_poles':raw['relaxation_hz'][1]=raw['relaxation_hz'][0]
    if kind=='negative_pole':raw['relaxation_hz'][0]=-1
    if kind=='real_shape':raw['eps_real']=[[[1,0],[0,1]]]
    if kind=='loss_shape':raw['eps_loss']=[[1,0],[0,1]]
    if kind=='real_boolean':raw['eps_real'][0][0][0]=True
    if kind=='loss_complex':raw['eps_loss'][0][0][0]=1j
    if kind=='real_asymmetric':raw['eps_real'][0][0][1]+=.1
    if kind=='loss_indefinite':raw['eps_loss'][0]=[[-1,0],[0,1]]
    if kind=='below_one':raw['eps_real'][0]=[[.9,0],[0,.9]]
    if kind=='weight_shape':raw['weights']=[1]
    if kind=='zero_weight':raw['weights'][0]=0
    if kind=='zero_limit':raw['max_error']=0
    if kind=='nonfinite_real':raw['eps_real'][0][0][0]=float('inf')
    if kind=='extra_nested':raw['eps_real'][0]=dict(xx=1,yy=1)
    def forbidden(*a,**k):pytest.fail('invalid input reached optimizer')
    monkeypatch.setattr(implementation,'nnls',forbidden)
    with pytest.raises(ValueError):TensorDebyeFitDocument.from_dict(raw)


@pytest.mark.parametrize('token',['NaN','Infinity','-Infinity'])
def test_nonstandard_json_numbers_reject(token):
    text=document().dumps().replace('"max_error": 1e-08','"max_error": '+token)
    assert token in text
    with pytest.raises(ValueError):TensorDebyeFitDocument.loads(text)
    with pytest.raises(ValueError):normalize_saved(text)


def test_duplicate_keys_reject_before_values_can_override():
    text=document().dumps().replace('"schema":','"schema": "sipi.tensor-dielectric-fit/1", "schema":',1)
    with pytest.raises(ValueError):TensorDebyeFitDocument.loads(text)
    with pytest.raises(ValueError):normalize_saved(text)
