# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit signal count, SI storage, full-state replay and pre-solve budgets."""
from dataclasses import fields, replace
import json

import numpy as np
import pytest
from sipi import (MulticonductorDebyeCapacitiveLadderDocument, psd_multiconductor_debye_capacitive_ladder_response,
                  CoupledRLGCLadderDocument, RLGCLadderDocument, StartupPortWavesDocument)
from sipi.execution import execute_saved, normalize_saved, saved_schemas
from test_multiconductor_debye_capacitive_startup import modal_data
import sipi.multiconductor_debye_capacitive_startup as api
import sipi.multiconductor_debye_capacitive_startup_document as module


def arguments(signals=3,kind='coupled',pulse=False,**changes):
    _,_,_,_,matrices=modal_data(signals)
    if kind=='diagonal':
        for k in ['R','L','G','C_inf','load_capacitance']:matrices[k]=np.diag(np.diag(matrices[k]))
        matrices['delta_C']=np.array([np.diag(np.diag(v)) for v in matrices['delta_C']])
    if kind=='lossless':matrices['R']=np.zeros((signals,signals));matrices['G']=np.zeros((signals,signals))
    t=np.linspace(0,12e-9,121);drive=np.minimum(t/2e-9,1.)[:,None]*np.array([1.,-.4,.2,-.1])[:signals]
    if pulse:drive*=np.clip((6e-9-t)/2e-9,0,1)[:,None]
    args=dict(time=t,source_voltages=drive,signals=signals,**matrices,length=.1,cells=4,
        source_resistance=[25.]*signals,load_resistance=[100.]*signals)
    args.update(changes);return args


def document(signals=3,**kw):return MulticonductorDebyeCapacitiveLadderDocument(**arguments(signals,**kw))


def forbidden(*args,**kwargs):pytest.fail('validation or budget reached propagation')


@pytest.mark.parametrize('signals',[3,4])
def test_canonical_fifteen_keys_and_copies_without_propagation(monkeypatch,signals):
    monkeypatch.setattr(api,'lsim',forbidden);monkeypatch.setattr(module,'psd_multiconductor_debye_capacitive_ladder_response',forbidden)
    args=arguments(signals);d=MulticonductorDebyeCapacitiveLadderDocument(**args);text=d.dumps()
    assert normalize_saved(text)==text and MulticonductorDebyeCapacitiveLadderDocument.loads(text).dumps()==text
    assert 'sipi.multiconductor-debye-capacitive-startup/1' in saved_schemas() and d.samples==121
    assert set(d.to_dict())=={'schema','signals','time_s','source_voltages_v','R_ohm_per_m','L_h_per_m','G_s_per_m','C_inf_f_per_m','length_m','cells','source_resistance_ohm','load_resistance_ohm','delta_C_f_per_m','relaxation_hz','load_capacitance_f'}
    args['L'][:]=9;args['source_voltages'][:]=99;args['source_resistance'][0]=99;args['load_capacitance'][:]=99
    data=d.to_dict();data['R_ohm_per_m'][0][0]=999;data['time_s'].clear();data['signals']=99
    assert d.dumps()==text


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('key',['schema','signals','time_s','source_voltages_v','R_ohm_per_m','L_h_per_m','G_s_per_m','C_inf_f_per_m','length_m','cells','source_resistance_ohm','load_resistance_ohm','delta_C_f_per_m','relaxation_hz','load_capacitance_f'])
def test_every_key_required(signals,key,monkeypatch):
    data=document(signals).to_dict();data.pop(key);monkeypatch.setattr(api,'lsim',forbidden)
    with pytest.raises(ValueError):MulticonductorDebyeCapacitiveLadderDocument.from_dict(data)
    with pytest.raises(ValueError):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('key,value',[
    ('schema','sipi.multiconductor-debye-capacitive-startup/2'),('schema','sipi.coupled-rlgc-startup/1'),
    ('extra',1),('R_ohm',[[1.]]),('C_f',[[1.]]),('signals',None),('signals',True),('signals',3.),('signals',2),('signals',5),
    ('time_s',[]),('time_s',[0.]),('time_s',[1.,2.,3.]),('time_s',[0.,0.,1.]),('time_s',[0.,1.,3.]),
    ('time_s',[0.,True,2.]),('time_s',[[0.,1.,2.]]),('source_voltages_v',[0.,1.,1.]),
    ('R_ohm_per_m',-1),('G_s_per_m',[[[0.]]]),('L_h_per_m',[[1.,0.],[0.,1e-14]]),('C_inf_f_per_m',[[0.]]),
    ('length_m',0),('length_m',float('inf')),('cells',0),('cells',65),('cells',True),('cells',8.),
    ('source_resistance_ohm',25.),('source_resistance_ohm',[0.,25.,25.]),('source_resistance_ohm',[25.,25.]),
    ('load_resistance_ohm',None),('load_resistance_ohm',[100.,0.,100.]),('load_resistance_ohm',[True]*4)])
def test_strict_saved_inputs_reject_without_propagation(signals,key,value,monkeypatch):
    data=document(signals).to_dict();data[key]=value;monkeypatch.setattr(api,'lsim',forbidden)
    with pytest.raises((ValueError,TypeError)):MulticonductorDebyeCapacitiveLadderDocument.from_dict(data)
    with pytest.raises((ValueError,TypeError)):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('key',['R_ohm_per_m','L_h_per_m','G_s_per_m','C_inf_f_per_m'])
def test_psd_losses_and_spd_storage_with_exact_symmetry(signals,key):
    data=document(signals).to_dict();data[key]=np.diag([1.]*(signals-1)+[0.]).tolist()
    if key in ['R_ohm_per_m','G_s_per_m']:
        assert json.loads(normalize_saved(json.dumps(data)))[key]==data[key]
    else:
        with pytest.raises(ValueError):normalize_saved(json.dumps(data))
    data=document(signals).to_dict();data[key][0][1]=np.nextafter(data[key][1][0],np.inf)
    with pytest.raises(ValueError):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('text',['{"schema":"x","schema":"y"}',
    '{"schema":"sipi.multiconductor-debye-capacitive-startup/1","signals":3,"signals":4}',
    '{"schema":"sipi.multiconductor-debye-capacitive-startup/1","time_s":[NaN]}',
    '{"schema":"sipi.multiconductor-debye-capacitive-startup/1","R_ohm_per_m":[[1e999]]}',
    '[]','null'])
def test_duplicate_nonfinite_and_nonobject_reject(text):
    with pytest.raises(ValueError):MulticonductorDebyeCapacitiveLadderDocument.loads(text)
    with pytest.raises(ValueError):normalize_saved(text)


@pytest.mark.parametrize('signals',[3,4])
def test_actual_time_budget_independent_of_cells_and_signal_count(signals,monkeypatch):
    t=[0.,1e-9,2e-9];drive=np.zeros((3,signals));drive[1:,0]=1.
    d=document(signals,time=t,source_voltages=drive,cells=64);original=module.psd_multiconductor_debye_capacitive_ladder_response;observed=[]
    def spy(**kw):observed.append((len(kw['time']),kw['cells'],kw['signals'],np.shape(kw['source_voltages'])));return original(**kw)
    monkeypatch.setattr(module,'psd_multiconductor_debye_capacitive_ladder_response',spy)
    out=execute_saved(d.dumps(),max_evaluations=3)
    assert observed==[(3,64,signals,(3,signals))] and out['input']['cells']==64
    assert out['status']=='complete' and not out['result']['states_included'] and 'node_voltage_v' not in out['result']
    monkeypatch.setattr(module,'psd_multiconductor_debye_capacitive_ladder_response',forbidden)
    for d in [d,document(signals,time=t,source_voltages=drive,cells=1)]:
        with pytest.raises(ValueError,match='max_evaluations'):d.analyze(max_evaluations=2)
        with pytest.raises(ValueError,match='max_evaluations'):execute_saved(d.dumps(),max_evaluations=2)


def test_row_limit_and_source_initial_validation_without_propagation(monkeypatch):
    monkeypatch.setattr(api,'lsim',forbidden)
    for rows in [1,10001]:
        with pytest.raises(ValueError):document(time=np.linspace(0,1,rows),source_voltages=np.zeros((rows,3)))
    data=document().to_dict();data['source_voltages_v'][0][0]=1e-15
    with pytest.raises(ValueError):normalize_saved(json.dumps(data))
    data=document().to_dict();data['source_voltages_v'][1][0]=True
    with pytest.raises(ValueError):normalize_saved(json.dumps(data))


def test_byte_diagnostic_and_integer_budget_control_before_propagation(monkeypatch):
    d=document();monkeypatch.setattr(module,'psd_multiconductor_debye_capacitive_ladder_response',forbidden)
    with pytest.raises(ValueError,match='max_input_bytes'):execute_saved(d.dumps(),max_input_bytes=2)
    with pytest.raises(ValueError,match='diagnostics'):execute_saved(d.dumps(),diagnostics=['modes'])
    for budget in [True,1,10001,3.]:
        with pytest.raises((ValueError,TypeError)):d.analyze(max_evaluations=budget)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('kind',['coupled','diagonal','lossless'])
@pytest.mark.parametrize('pulse',[False,True])
def test_twelve_saved_direct_common_replays_preserve_full_states(signals,kind,pulse):
    args=arguments(signals,kind,pulse);expected=psd_multiconductor_debye_capacitive_ladder_response(**args)
    d=MulticonductorDebyeCapacitiveLadderDocument(**args);loaded=MulticonductorDebyeCapacitiveLadderDocument.loads(d.dumps())
    actual=loaded.analyze(max_evaluations=121)
    assert actual.to_dict(include_states=True)==expected.to_dict(include_states=True)
    out=execute_saved(loaded.dumps(),max_evaluations=121)
    assert out['status']=='complete' and out['error'] is None and out['result']==expected.to_dict()
    assert out['input']==d.to_dict();json.dumps(out,allow_nan=False)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('change',['inputs','time','drive','type','node_voltage','segment_current','voltage','current','energy','energy_rate','series_loss','shunt_loss','line_power','source_power','source_resistor_loss','load_resistor_loss','polarization_voltage','polarization_charge','polarization_current','polarization_energy','polarization_energy_rate','relaxation_loss','load_capacitor_current','load_capacitor_energy','load_capacitor_power'])
def test_solver_result_retains_identity_and_every_array_shape(signals,change,monkeypatch):
    d=document(signals);r=d.analyze(max_evaluations=121)
    if change=='inputs':
        data=r.inputs;data['signals']=3 if signals==4 else 4;bad=replace(r,input_json=json.dumps(data))
    elif change=='time':bad=replace(r,time=r.time*2)
    elif change=='drive':bad=replace(r,source_voltages=np.ones((121,signals)))
    elif change=='type':bad=None
    else:bad=replace(r,**{change:np.zeros((121,1))})
    monkeypatch.setattr(module,'psd_multiconductor_debye_capacitive_ladder_response',lambda **kw:bad)
    with pytest.raises(ValueError,match='changed saved'):d.analyze(max_evaluations=121)


@pytest.mark.parametrize('signals',[3,4])
def test_old_saved_inputs_and_all_prior_wave_versions_reject_new_kind(signals):
    d=document(signals)
    for cls in [CoupledRLGCLadderDocument,RLGCLadderDocument]:
        with pytest.raises(ValueError):cls.loads(d.dumps())
    for version in range(1,12):
        with pytest.raises(ValueError):StartupPortWavesDocument(d,z_ref=[50.]*(2*signals),version=version)
        data=dict(schema=f'sipi.startup-port-waves/{version}',startup=d.to_dict(),z_ref_ohm=[50.]*(2*signals))
        with pytest.raises(ValueError):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('signals',[3,4])
def test_runtime_unrepresentable_cell_failure_is_retained(signals):
    d=document(signals,L=np.eye(signals)*1e-300,C_inf=np.eye(signals)*1e-300,length=1e-300)
    assert normalize_saved(d.dumps())==d.dumps()
    with pytest.raises(ValueError,match='finite scales'):d.analyze(max_evaluations=121)
    with pytest.raises(ValueError,match='finite scales'):execute_saved(d.dumps(),max_evaluations=121)


def test_original_propagation_error_retained(monkeypatch):
    d=document()
    def fail(**kw):raise RuntimeError('deliberate saved propagation failure')
    monkeypatch.setattr(module,'psd_multiconductor_debye_capacitive_ladder_response',fail)
    with pytest.raises(RuntimeError,match='deliberate'):execute_saved(d.dumps(),max_evaluations=121)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('kind',['one','first-zero','all-zero','reordered'])
def test_declared_poles_preserved_across_saved_and_direct_paths(signals,kind):
    args=arguments(signals);d=args['delta_C'];p=args['relaxation_hz']
    if kind=='one':d=d[:1];p=p[:1]
    elif kind=='first-zero':d[0]=0
    elif kind=='all-zero':d[:]=0
    else:d=d[::-1];p=p[::-1]
    args.update(delta_C=d,relaxation_hz=p)
    saved=MulticonductorDebyeCapacitiveLadderDocument(**args)
    expected=psd_multiconductor_debye_capacitive_ladder_response(**args)
    actual=MulticonductorDebyeCapacitiveLadderDocument.loads(saved.dumps()).analyze(max_evaluations=121)
    assert actual.to_dict(include_states=True)==expected.to_dict(include_states=True)
    assert execute_saved(saved.dumps(),max_evaluations=121)['result']==expected.to_dict()
    assert actual.polarization_voltage.shape[2:]==(len(p),signals)
    data=saved.to_dict();data['delta_C_f_per_m'][0][0][0]=999;data['relaxation_hz'][0]=999
    assert saved.to_dict()['delta_C_f_per_m']==d.tolist() and saved.to_dict()['relaxation_hz']==p.tolist()


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('bad',['empty','many','shape','asymmetric','singular','negative','ratio','boolean','nonfinite'])
def test_saved_strength_contract_before_propagation(signals,bad,monkeypatch):
    data=document(signals).to_dict();v=np.asarray(data['delta_C_f_per_m'])
    if bad=='empty':v=v[:0]
    elif bad=='many':v=np.concatenate([v,v])
    elif bad=='shape':v=v[:,:,:-1]
    elif bad=='asymmetric':v[0,0,1]=np.nextafter(v[0,1,0],np.inf)
    elif bad=='singular':v[0]=np.diag([1.]*(signals-1)+[0.])
    elif bad=='negative':v[0]=-np.eye(signals)
    elif bad=='ratio':v[0]=np.diag([1.]*(signals-1)+[1e-13])
    elif bad=='boolean':v=v.astype(bool)
    else:v[0,0,0]=np.inf
    data['delta_C_f_per_m']=v.tolist();monkeypatch.setattr(api,'lsim',forbidden)
    if bad in ('singular','ratio'):
        assert MulticonductorDebyeCapacitiveLadderDocument.from_dict(data).to_dict()==data
        assert json.loads(normalize_saved(json.dumps(data)))==data
    else:
        with pytest.raises(ValueError):MulticonductorDebyeCapacitiveLadderDocument.from_dict(data)
        with pytest.raises(ValueError):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('value',[[],[1.],[1.,2.,3.],[-1.,1.],[0.,1.],[1.,np.inf],[True,False],[[1.,2.]]])
def test_saved_pole_contract_before_propagation(signals,value,monkeypatch):
    data=document(signals).to_dict();data['relaxation_hz']=value;monkeypatch.setattr(api,'lsim',forbidden)
    with pytest.raises(ValueError):MulticonductorDebyeCapacitiveLadderDocument.from_dict(data)
    with pytest.raises(ValueError):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('signals',[3,4])
def test_pole_order_and_cinf_input_identity_guard(signals,monkeypatch):
    d=document(signals);result=d.analyze(max_evaluations=121)
    for key in ['delta_C_f_per_m','relaxation_hz','C_inf_f_per_m','load_capacitance_f']:
        data=result.inputs;data[key]=data[key][::-1]
        bad=replace(result,input_json=json.dumps(data));monkeypatch.setattr(module,'psd_multiconductor_debye_capacitive_ladder_response',lambda **kw:bad)
        with pytest.raises(ValueError,match='changed saved'):d.analyze(max_evaluations=121)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('tiny',[0.,1e-13,1e-20])
def test_nearzero_strength_values_and_null_charge_replayed_without_rank_threshold(signals,tiny):
    delta=np.array([np.diag([150e-12]+[150e-12*tiny]*(signals-1))])
    args=arguments(signals,delta_C=delta,relaxation_hz=[8e7]);d=MulticonductorDebyeCapacitiveLadderDocument(**args)
    text=d.dumps();assert normalize_saved(text)==text
    r=d.analyze(max_evaluations=121);expected=psd_multiconductor_debye_capacitive_ladder_response(**args)
    assert r.to_dict(include_states=True)==expected.to_dict(include_states=True)
    assert execute_saved(text,max_evaluations=121)['result']==expected.to_dict()
    assert r.inputs['delta_C_f_per_m']==delta.tolist()
    assert np.any(r.polarization_voltage[:,:,:,1:])
    if tiny==0:assert not np.any(r.polarization_charge[:,:,:,1:])
    else:assert np.any(r.polarization_charge[:,:,:,1:])


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('pulse',[False,True])
def test_rankone_loss_matrices_retained_in_common_and_full_state_execution(signals,pulse):
    r=np.zeros((signals,signals));r[:2,:2]=[[20.,-20.],[-20.,20.]]
    g=np.zeros_like(r);g[1:3,1:3]=[[.002,.002],[.002,.002]]
    args=arguments(signals,pulse=pulse,R=r,G=g);d=MulticonductorDebyeCapacitiveLadderDocument(**args)
    expected=psd_multiconductor_debye_capacitive_ladder_response(**args)
    assert d.analyze(max_evaluations=121).to_dict(include_states=True)==expected.to_dict(include_states=True)
    out=execute_saved(d.dumps(),max_evaluations=121)
    assert out['result']==expected.to_dict() and out['input']['R_ohm_per_m']==r.tolist() and out['input']['G_s_per_m']==g.tolist()


@pytest.mark.parametrize('signals',[3,4])
def test_null_only_drive_has_zero_polarization_charge_energy_loss_after_reload(signals):
    args=arguments(signals);args['source_voltages'][:,:-1]=0
    args.update(R=np.eye(signals)*20,L=np.eye(signals)*450e-9,G=np.eye(signals)*.002,
        C_inf=np.eye(signals)*210e-12,delta_C=np.array([np.diag([150e-12]+[0.]*(signals-1))]),relaxation_hz=[8e7])
    d=MulticonductorDebyeCapacitiveLadderDocument(**args);r=MulticonductorDebyeCapacitiveLadderDocument.loads(d.dumps()).analyze()
    assert np.any(r.polarization_voltage[:,:,:,-1])
    for name in ['polarization_charge','polarization_current','polarization_energy','polarization_energy_rate','relaxation_loss']:
        assert not np.any(getattr(r,name))


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('bad',['none','scalar','vector','shape','asymmetric','negative','tiny-negative','boolean','string','nonfinite'])
def test_external_capacitance_rejected_before_propagation(signals,bad,monkeypatch):
    data=document(signals).to_dict();v=np.eye(signals)*30e-12
    if bad=='none':v=None
    elif bad=='scalar':v=30e-12
    elif bad=='vector':v=[30e-12]*signals
    elif bad=='shape':v=np.eye(signals+1)
    elif bad=='asymmetric':v[0,1]=np.nextafter(v[1,0],np.inf)
    elif bad=='negative':v[-1,-1]=-30e-12
    elif bad=='tiny-negative':v[-1,-1]=-30e-32
    elif bad=='boolean':v=v.astype(bool)
    elif bad=='string':v=v.astype(str)
    else:v[0,0]=np.inf
    data['load_capacitance_f']=v.tolist() if isinstance(v,np.ndarray) else v
    monkeypatch.setattr(api,'lsim',forbidden)
    with pytest.raises(ValueError):MulticonductorDebyeCapacitiveLadderDocument.from_dict(data)
    with pytest.raises(ValueError):normalize_saved(json.dumps(data))

@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('kind',['zero','rank-one','near13','near20'])
@pytest.mark.parametrize('pulse',[False,True])
def test_external_capacitance_full_state_replay_and_partition(signals,kind,pulse):
    cap=np.zeros((signals,signals))
    if kind=='rank-one':cap[:2,:2]=np.array([[30.,-30.],[-30.,30.]])*1e-12
    elif kind.startswith('near'):cap=np.diag([30e-12]+[30e-12*10**(-int(kind[4:]))]*(signals-1))
    args=arguments(signals,pulse=pulse,load_capacitance=cap);d=MulticonductorDebyeCapacitiveLadderDocument(**args)
    assert normalize_saved(d.dumps())==d.dumps()
    expected=psd_multiconductor_debye_capacitive_ladder_response(**args)
    a=MulticonductorDebyeCapacitiveLadderDocument.loads(d.dumps()).analyze(max_evaluations=121)
    assert a.to_dict(include_states=True)==expected.to_dict(include_states=True)
    assert execute_saved(d.dumps(),max_evaluations=121)['result']==expected.to_dict()
    assert a.inputs['load_capacitance_f']==cap.tolist()
    np.testing.assert_array_equal(a.total_energy,a.line_energy+a.load_capacitor_energy)
    np.testing.assert_array_equal(a.total_energy_rate,a.line_energy_rate+a.load_capacitor_power)
    np.testing.assert_allclose(a.current[:,signals:],-a.voltage[:,signals:]/100-a.load_capacitor_current,rtol=1e-10,atol=1e-12)
    if kind=='zero':assert not np.any(a.load_capacitor_current) and not np.any(a.load_capacitor_energy)
    if kind.startswith('near'):assert np.any(a.load_capacitor_current[:,1:])
    if pulse and kind!='zero':assert np.any(a.load_capacitor_power<0)

@pytest.mark.parametrize('signals',[3,4])
def test_old_psd_document_rejects_new_namespace_and_external_field(signals):
    from sipi import PSDMulticonductorDebyeRLGCLadderDocument as Old
    data=document(signals).to_dict()
    with pytest.raises(ValueError):Old.from_dict(data)
    data['schema']='sipi.psd-multiconductor-debye-rlgc-startup/1'
    with pytest.raises(ValueError):Old.from_dict(data)
    data.pop('load_capacitance_f');assert Old.from_dict(data).to_dict()==data
