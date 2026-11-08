# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict finite-circuit saved inputs, sample budgets and actual replay."""
from dataclasses import replace
import json

import numpy as np
import pytest
from sipi import DebyeRLGCLadderDocument, debye_rlgc_ladder_response
from sipi.execution import execute_saved, normalize_saved, saved_schemas
import sipi.debye_startup as api
import sipi.debye_startup_document as module


def document(**changes):
    args=dict(time=[0.,1e-9,2e-9],source_voltages=[0.,1.,1.],
        R=20.,L=500e-9,G=.002,C_inf=200e-12,delta_C=[150e-12,50e-12],relaxation_hz=[1e9,1e8],length=.1,cells=8,
        source_resistance=25.,load_resistance=100.)
    args.update(changes);return DebyeRLGCLadderDocument(**args)


def forbidden(*args,**kwargs):pytest.fail('validation or budget reached state propagation')


def test_canonical_registry_and_copies_without_propagation(monkeypatch):
    monkeypatch.setattr(api,'lsim',forbidden)
    monkeypatch.setattr(module,'debye_rlgc_ladder_response',forbidden)
    t=np.array([0.,1e-9,2e-9]);v=np.array([0.,1.,1.])
    d=document(time=t,source_voltages=v);text=d.dumps()
    assert normalize_saved(text)==text and DebyeRLGCLadderDocument.loads(text).dumps()==text
    assert 'sipi.debye-rlgc-startup/1' in saved_schemas() and d.samples==3
    t[:]=9;v[:]=9;out=d.to_dict();out['time_s'].clear();out['cells']=1
    assert d.dumps()==text


@pytest.mark.parametrize('mutate',[
    lambda d:d.update(schema='sipi.debye-rlgc-startup/999'),lambda d:d.update(extra=1),
    lambda d:d.pop('load_resistance_ohm'),lambda d:d.pop('cells'),
    lambda d:d.update(time_s=[]),lambda d:d.update(time_s=[0.]),
    lambda d:d.update(time_s=[1.,2.,3.]),lambda d:d.update(time_s=[0.,0.,1.]),
    lambda d:d.update(time_s=[0.,2.,1.]),lambda d:d.update(time_s=[0.,1.,3.]),
    lambda d:d.update(time_s=[0.,True,2.]),lambda d:d.update(time_s=[[0.,1.,2.]]),
    lambda d:d.update(source_voltages_v=[1.,1.,1.]),lambda d:d.update(source_voltages_v=[0.,1.]),
    lambda d:d.update(source_voltages_v=[0.,True,1.]),lambda d:d.update(source_voltages_v=0.),
    lambda d:d.update(R_ohm_per_m=-1),lambda d:d.update(R_ohm_per_m=True),
    lambda d:d.update(L_h_per_m=0),lambda d:d.update(G_s_per_m=-1),lambda d:d.update(C_inf_f_per_m=0),
    lambda d:d.update(length_m=0),lambda d:d.update(cells=0),lambda d:d.update(cells=129),
    lambda d:d.update(cells=True),lambda d:d.update(cells=8.),
    lambda d:d.update(source_resistance_ohm=-1),lambda d:d.update(source_resistance_ohm=True),
    lambda d:d.update(load_resistance_ohm='open'),lambda d:d.update(load_resistance_ohm=True),
    lambda d:d.update(time_s=np.linspace(0.,1.,10001).tolist(),source_voltages_v=[0.]*10001),
])
def test_strict_inputs_reject_without_propagation(mutate,monkeypatch):
    data=document().to_dict();mutate(data)
    monkeypatch.setattr(api,'lsim',forbidden)
    with pytest.raises((ValueError,TypeError)):DebyeRLGCLadderDocument.from_dict(data)
    with pytest.raises((ValueError,TypeError)):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('text',['{"schema":"x","schema":"y"}',
    '{"schema":"sipi.debye-rlgc-startup/1","time_s":[NaN]}',
    '{"schema":"sipi.debye-rlgc-startup/1","load_resistance_ohm":1e999}',
    '[]','null'])
def test_duplicate_nonfinite_nonobject_reject(text):
    with pytest.raises(ValueError):DebyeRLGCLadderDocument.loads(text)
    with pytest.raises(ValueError):normalize_saved(text)


def test_budget_counts_samples_preserves_cells_and_boundary(monkeypatch):
    d=document(cells=128);original=module.debye_rlgc_ladder_response;observed=[]
    def spy(**kwargs):observed.append((len(kwargs['time']),kwargs['cells']));return original(**kwargs)
    monkeypatch.setattr(module,'debye_rlgc_ladder_response',spy)
    out=execute_saved(d.dumps(),max_evaluations=3)
    assert out['status']=='complete' and observed==[(3,128)]
    assert out['input']['cells']==128 and out['result']['input']['cells']==128
    assert not out['result']['states_included'] and 'node_voltage_v' not in out['result']
    monkeypatch.setattr(module,'debye_rlgc_ladder_response',forbidden)
    for item in [d,document(cells=1)]:
        with pytest.raises(ValueError,match='max_evaluations'):item.analyze(max_evaluations=2)
        with pytest.raises(ValueError,match='max_evaluations'):execute_saved(item.dumps(),max_evaluations=2)


def test_byte_diagnostics_and_budget_validation_precede_propagation(monkeypatch):
    d=document();monkeypatch.setattr(module,'debye_rlgc_ladder_response',forbidden)
    with pytest.raises(ValueError,match='max_input_bytes'):execute_saved(d.dumps(),max_input_bytes=2)
    with pytest.raises(ValueError,match='diagnostics'):execute_saved(d.dumps(),diagnostics=['modes'])
    for budget in [True,1,10001,3.]:
        with pytest.raises((ValueError,TypeError)):d.analyze(max_evaluations=budget)


@pytest.mark.parametrize('rs,rl',[(0.,0.),(0.,None),(0.,50.),(25.,0.),(25.,None),(25.,100.)])
@pytest.mark.parametrize('pulse',[False,True])
def test_saved_loaded_and_common_execution_replay_actual_circuit(rs,rl,pulse):
    t=np.linspace(0.,12e-9,121)
    drive=np.interp(t,[0.,2e-9,5e-9,8e-9],[0.,1.,-1.,0.]) if pulse else np.minimum(t/2e-9,1.)
    args=dict(time=t,source_voltages=drive,R=20.,L=500e-9,G=.002,C_inf=200e-12,
        delta_C=[150e-12,50e-12],relaxation_hz=[1e9,1e8],length=.1,cells=16,source_resistance=rs,load_resistance=rl)
    expected=debye_rlgc_ladder_response(**args);d=DebyeRLGCLadderDocument(**args)
    loaded=DebyeRLGCLadderDocument.loads(d.dumps());actual=loaded.analyze(max_evaluations=121)
    assert actual.to_dict(include_states=True)==expected.to_dict(include_states=True)
    out=execute_saved(loaded.dumps(),max_evaluations=121)
    assert out['status']=='complete' and out['error'] is None and out['result']==expected.to_dict()
    assert out['input']==d.to_dict();json.dumps(out,allow_nan=False)


@pytest.mark.parametrize('change',['inputs','time','drive','node_shape','segment_shape','type'])
def test_solver_cannot_change_saved_inputs_times_or_cells(change,monkeypatch):
    d=document();r=d.analyze()
    if change=='inputs':
        data=r.inputs;data['cells']=9;bad=replace(r,input_json=json.dumps(data))
    elif change=='time':bad=replace(r,time=np.array([0.,1.,2.]))
    elif change=='drive':bad=replace(r,source_voltages=np.array([0.,2.,2.]))
    elif change=='node_shape':bad=replace(r,node_voltage=np.zeros((3,8)))
    elif change=='segment_shape':bad=replace(r,segment_current=np.zeros((3,9)))
    else:bad=None
    monkeypatch.setattr(module,'debye_rlgc_ladder_response',lambda **kwargs:bad)
    with pytest.raises(ValueError,match='changed saved'):d.analyze()


def test_runtime_finite_scale_failure_keeps_original_exception_without_partial_success():
    d=document(L=1e-320,C_inf=1e-320,length=1e-320)
    assert normalize_saved(d.dumps())==d.dumps()
    with pytest.raises(ValueError,match='finite scales'):d.analyze()
    with pytest.raises(ValueError,match='finite scales'):execute_saved(d.dumps())


@pytest.mark.parametrize('key', ['schema',*module._NAMES])
def test_every_root_key_is_required(key,monkeypatch):
    data=document().to_dict();data.pop(key);monkeypatch.setattr(api,'lsim',forbidden)
    with pytest.raises(ValueError):DebyeRLGCLadderDocument.from_dict(data)


@pytest.mark.parametrize('mutate',[
    lambda d:d.update(delta_C_f_per_m=[]),lambda d:d.update(delta_C_f_per_m=[True,0.]),
    lambda d:d.update(delta_C_f_per_m=[-1.,0.]),lambda d:d.update(delta_C_f_per_m=[[1.,0.]]),
    lambda d:d.update(delta_C_f_per_m=[1e-12]*5,relaxation_hz=[1e9]*5),
    lambda d:d.update(delta_C_f_per_m=[1e-12]),lambda d:d.update(delta_C_f_per_m=[1e999,0.]),
    lambda d:d.update(relaxation_hz=[0.,1e8]),lambda d:d.update(relaxation_hz=[True,1e8]),
    lambda d:d.update(relaxation_hz=[-1.,1e8]),lambda d:d.update(relaxation_hz=['1',1e8]),
    lambda d:d.update(relaxation_hz=[1e9]),lambda d:d.update(relaxation_hz=[[1e9,1e8]]),
    lambda d:d.update(delta_C=[1e-12,0.]),lambda d:d.update(C_f_per_m=200e-12),
    lambda d:d.update(schema='sipi.rlgc-startup/1'),
])
def test_strict_pole_units_shapes_and_version(mutate,monkeypatch):
    data=document().to_dict();mutate(data);monkeypatch.setattr(api,'lsim',forbidden)
    with pytest.raises((ValueError,TypeError)):DebyeRLGCLadderDocument.from_dict(data)
    with pytest.raises((ValueError,TypeError)):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('strengths,poles',[
    ([0.],[1e9]),([150e-12],[1e9]),([0.,0.],[2e8,1e9]),
    ([50e-12,75e-12,25e-12,50e-12],[1e8,1e9,1e9,3e8]),
    ([0.,75e-12,75e-12,50e-12],[2e9,1e9,1e9,1e8])])
def test_explicit_poles_order_zero_columns_and_exact_replay(strengths,poles):
    d=document(delta_C=strengths,relaxation_hz=poles,cells=1,source_resistance=0.,load_resistance=0.)
    saved=DebyeRLGCLadderDocument.loads(d.dumps());out=saved.analyze(max_evaluations=3)
    assert out.inputs['delta_C_f_per_m']==strengths and out.inputs['relaxation_hz']==poles
    assert out.polarization_charge.shape==(3,2,len(poles))
    assert execute_saved(saved.dumps(),max_evaluations=3)['result']==out.to_dict()
    zero=np.flatnonzero(np.array(strengths)==0)
    assert not np.any(out.polarization_voltage[:,:,zero])


@pytest.mark.parametrize('field', ['voltage','current','polarization_voltage','polarization_charge','polarization_current',
    'energy','energy_rate','series_loss','shunt_loss','line_power','source_power','source_resistor_loss',
    'load_resistor_loss','polarization_energy','polarization_energy_rate','relaxation_loss'])
def test_all_response_state_and_diagnostic_shapes_guarded(field,monkeypatch):
    d=document();r=d.analyze();bad=replace(r,**{field:np.zeros((3,1))})
    monkeypatch.setattr(module,'debye_rlgc_ladder_response',lambda **kwargs:bad)
    with pytest.raises(ValueError,match='changed saved'):d.analyze()


@pytest.mark.parametrize('version',[1,2,3])
def test_existing_wave_schemas_do_not_implicitly_accept_debye(version):
    from sipi import StartupPortWavesDocument
    d=document()
    with pytest.raises(ValueError):StartupPortWavesDocument(d,z_ref=[50.,50.],version=version)
    data=dict(schema=f'sipi.startup-port-waves/{version}',startup=d.to_dict(),z_ref_ohm=[50.,50.])
    with pytest.raises(ValueError):StartupPortWavesDocument.from_dict(data)
    with pytest.raises(ValueError):normalize_saved(json.dumps(data))


def test_pole_arrays_and_canonical_inputs_are_detached(monkeypatch):
    strengths=np.array([150e-12,50e-12]);poles=np.array([1e9,1e8]);d=document(delta_C=strengths,relaxation_hz=poles)
    text=d.dumps();strengths[:]=0.;poles[:]=1.;data=d.to_dict();data['delta_C_f_per_m'][0]=7
    assert d.dumps()==text;monkeypatch.setattr(api,'lsim',forbidden)
    assert normalize_saved(text)==text


def test_original_runtime_exception_propagates(monkeypatch):
    d=document()
    def fail(**kwargs):raise RuntimeError('Debye integration failed')
    monkeypatch.setattr(module,'debye_rlgc_ladder_response',fail)
    with pytest.raises(RuntimeError,match='Debye integration failed'):d.analyze()
    with pytest.raises(RuntimeError,match='Debye integration failed'):execute_saved(d.dumps())
