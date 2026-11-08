# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict original typed sources, full-state replay and pre-solve budgets."""
from dataclasses import fields,replace
import json,copy
import numpy as np
import pytest
from sipi import (MixedSourceMulticonductorDebyeReactiveLadderDocument,
    psd_multiconductor_debye_mixed_reactive_ladder_response,
    CoupledRLGCLadderDocument,RLGCLadderDocument,StartupPortWavesDocument)
from sipi.execution import execute_saved,normalize_saved,saved_schemas
from test_multiconductor_debye_norton_startup_document import arguments as norton_arguments
import sipi.multiconductor_debye_mixed_startup as api
import sipi.multiconductor_debye_mixed_startup_document as module


def arguments(signals=3,kind='coupled',pulse=False,**changes):
    a=norton_arguments(signals,kind,pulse,**changes);drive=a.pop('source_currents');gs=a.pop('source_shunt_conductance')
    a['sources']=[dict(kind='voltage',voltage_v=(drive[:,j]/gs[j]).tolist(),series_resistance_ohm=float(1/gs[j])) if j%2 else dict(kind='current',current_a=drive[:,j].tolist(),shunt_conductance_s=float(gs[j])) for j in range(signals)]
    return a


def document(signals=3,**kw):return MixedSourceMulticonductorDebyeReactiveLadderDocument(**arguments(signals,**kw))


def forbidden(*args,**kwargs):pytest.fail('validation or budget reached propagation')


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
    '{"schema":"sipi.multiconductor-debye-mixed-startup/1","signals":3,"signals":4}',
    '{"schema":"sipi.multiconductor-debye-mixed-startup/1","time_s":[NaN]}',
    '{"schema":"sipi.multiconductor-debye-mixed-startup/1","R_ohm_per_m":[[1e999]]}',
    '[]','null'])
def test_duplicate_nonfinite_and_nonobject_reject(text):
    with pytest.raises(ValueError):MixedSourceMulticonductorDebyeReactiveLadderDocument.loads(text)
    with pytest.raises(ValueError):normalize_saved(text)



def test_byte_diagnostic_and_integer_budget_control_before_propagation(monkeypatch):
    d=document();monkeypatch.setattr(module,'psd_multiconductor_debye_mixed_reactive_ladder_response',forbidden)
    with pytest.raises(ValueError,match='max_input_bytes'):execute_saved(d.dumps(),max_input_bytes=2)
    with pytest.raises(ValueError,match='diagnostics'):execute_saved(d.dumps(),diagnostics=['modes'])
    for budget in [True,1,10001,3.]:
        with pytest.raises((ValueError,TypeError)):d.analyze(max_evaluations=budget)



@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('kind',['coupled','diagonal','lossless'])
@pytest.mark.parametrize('pulse',[False,True])
def test_twelve_saved_direct_common_replays_preserve_full_states(signals,kind,pulse):
    args=arguments(signals,kind,pulse);expected=psd_multiconductor_debye_mixed_reactive_ladder_response(**args)
    d=MixedSourceMulticonductorDebyeReactiveLadderDocument(**args);loaded=MixedSourceMulticonductorDebyeReactiveLadderDocument.loads(d.dumps())
    actual=loaded.analyze(max_evaluations=121)
    assert actual.to_dict(include_states=True)==expected.to_dict(include_states=True)
    out=execute_saved(loaded.dumps(),max_evaluations=121)
    assert out['status']=='complete' and out['error'] is None and out['result']==expected.to_dict()
    assert out['input']==d.to_dict();json.dumps(out,allow_nan=False)



@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('change',['inputs','time','drive','type','node_voltage','segment_current','voltage','current','energy','energy_rate','series_loss','shunt_loss','line_power','source_power','source_series_resistor_loss','source_shunt_resistor_loss','load_resistor_loss','polarization_voltage','polarization_charge','polarization_current','polarization_energy','polarization_energy_rate','relaxation_loss','load_capacitor_current','load_capacitor_energy','load_capacitor_power','load_branch_current','load_branch_energy','load_branch_energy_rate','load_branch_resistor_loss'])
def test_solver_result_retains_identity_and_every_array_shape(signals,change,monkeypatch):
    d=document(signals);r=d.analyze(max_evaluations=121)
    if change=='inputs':
        data=r.inputs;data['signals']=3 if signals==4 else 4;bad=replace(r,input_json=json.dumps(data))
    elif change=='time':bad=replace(r,time=r.time*2)
    elif change=='drive':bad=replace(r,source_values=np.ones((121,signals)))
    elif change=='type':bad=None
    else:bad=replace(r,**{change:np.zeros((121,1))})
    monkeypatch.setattr(module,'psd_multiconductor_debye_mixed_reactive_ladder_response',lambda **kw:bad)
    with pytest.raises(ValueError,match='changed saved'):d.analyze(max_evaluations=121)



@pytest.mark.parametrize('signals',[3,4])
def test_old_saved_inputs_and_all_prior_wave_versions_reject_new_kind(signals):
    d=document(signals)
    for cls in [CoupledRLGCLadderDocument,RLGCLadderDocument]:
        with pytest.raises(ValueError):cls.loads(d.dumps())
    for version in range(1,15):
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
    monkeypatch.setattr(module,'psd_multiconductor_debye_mixed_reactive_ladder_response',fail)
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
    saved=MixedSourceMulticonductorDebyeReactiveLadderDocument(**args)
    expected=psd_multiconductor_debye_mixed_reactive_ladder_response(**args)
    actual=MixedSourceMulticonductorDebyeReactiveLadderDocument.loads(saved.dumps()).analyze(max_evaluations=121)
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
        assert MixedSourceMulticonductorDebyeReactiveLadderDocument.from_dict(data).to_dict()==data
        assert json.loads(normalize_saved(json.dumps(data)))==data
    else:
        with pytest.raises(ValueError):MixedSourceMulticonductorDebyeReactiveLadderDocument.from_dict(data)
        with pytest.raises(ValueError):normalize_saved(json.dumps(data))



@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('value',[[],[1.],[1.,2.,3.],[-1.,1.],[0.,1.],[1.,np.inf],[True,False],[[1.,2.]]])
def test_saved_pole_contract_before_propagation(signals,value,monkeypatch):
    data=document(signals).to_dict();data['relaxation_hz']=value;monkeypatch.setattr(api,'lsim',forbidden)
    with pytest.raises(ValueError):MixedSourceMulticonductorDebyeReactiveLadderDocument.from_dict(data)
    with pytest.raises(ValueError):normalize_saved(json.dumps(data))



@pytest.mark.parametrize('signals',[3,4])
def test_pole_order_and_cinf_input_identity_guard(signals,monkeypatch):
    d=document(signals);result=d.analyze(max_evaluations=121)
    for key in ['delta_C_f_per_m','relaxation_hz','C_inf_f_per_m','load_capacitance_f','load_branch_resistance_ohm','load_branch_inductance_h']:
        data=result.inputs;data[key]=data[key][::-1]
        bad=replace(result,input_json=json.dumps(data));monkeypatch.setattr(module,'psd_multiconductor_debye_mixed_reactive_ladder_response',lambda **kw:bad)
        with pytest.raises(ValueError,match='changed saved'):d.analyze(max_evaluations=121)



@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('tiny',[0.,1e-13,1e-20])
def test_nearzero_strength_values_and_null_charge_replayed_without_rank_threshold(signals,tiny):
    delta=np.array([np.diag([150e-12]+[150e-12*tiny]*(signals-1))])
    args=arguments(signals,delta_C=delta,relaxation_hz=[8e7]);d=MixedSourceMulticonductorDebyeReactiveLadderDocument(**args)
    text=d.dumps();assert normalize_saved(text)==text
    r=d.analyze(max_evaluations=121);expected=psd_multiconductor_debye_mixed_reactive_ladder_response(**args)
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
    args=arguments(signals,pulse=pulse,R=r,G=g);d=MixedSourceMulticonductorDebyeReactiveLadderDocument(**args)
    expected=psd_multiconductor_debye_mixed_reactive_ladder_response(**args)
    assert d.analyze(max_evaluations=121).to_dict(include_states=True)==expected.to_dict(include_states=True)
    out=execute_saved(d.dumps(),max_evaluations=121)
    assert out['result']==expected.to_dict() and out['input']['R_ohm_per_m']==r.tolist() and out['input']['G_s_per_m']==g.tolist()



@pytest.mark.parametrize('signals',[3,4])
def test_null_only_drive_has_zero_polarization_charge_energy_loss_after_reload(signals):
    args=arguments(signals)
    for source in args['sources'][:-1]:source['voltage_v' if source['kind']=='voltage' else 'current_a']=[0.]*121
    args.update(R=np.eye(signals)*20,L=np.eye(signals)*450e-9,G=np.eye(signals)*.002,
        C_inf=np.eye(signals)*210e-12,delta_C=np.array([np.diag([150e-12]+[0.]*(signals-1))]),relaxation_hz=[8e7])
    d=MixedSourceMulticonductorDebyeReactiveLadderDocument(**args);r=MixedSourceMulticonductorDebyeReactiveLadderDocument.loads(d.dumps()).analyze()
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
    with pytest.raises(ValueError):MixedSourceMulticonductorDebyeReactiveLadderDocument.from_dict(data)
    with pytest.raises(ValueError):normalize_saved(json.dumps(data))



@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('kind',['zero','rank-one','near13','near20'])
@pytest.mark.parametrize('pulse',[False,True])
def test_external_capacitance_full_state_replay_and_partition(signals,kind,pulse):
    cap=np.zeros((signals,signals))
    if kind=='rank-one':cap[:2,:2]=np.array([[30.,-30.],[-30.,30.]])*1e-12
    elif kind.startswith('near'):cap=np.diag([30e-12]+[30e-12*10**(-int(kind[4:]))]*(signals-1))
    args=arguments(signals,pulse=pulse,load_capacitance=cap);d=MixedSourceMulticonductorDebyeReactiveLadderDocument(**args)
    assert normalize_saved(d.dumps())==d.dumps()
    expected=psd_multiconductor_debye_mixed_reactive_ladder_response(**args)
    a=MixedSourceMulticonductorDebyeReactiveLadderDocument.loads(d.dumps()).analyze(max_evaluations=121)
    assert a.to_dict(include_states=True)==expected.to_dict(include_states=True)
    assert execute_saved(d.dumps(),max_evaluations=121)['result']==expected.to_dict()
    assert a.inputs['load_capacitance_f']==cap.tolist()
    np.testing.assert_array_equal(a.total_energy,a.line_energy+a.load_capacitor_energy+a.load_branch_energy)
    np.testing.assert_array_equal(a.total_energy_rate,a.line_energy_rate+a.load_capacitor_power+a.load_branch_energy_rate)
    np.testing.assert_allclose(a.current[:,signals:],-a.voltage[:,signals:]/100-a.load_capacitor_current-a.load_branch_current,rtol=1e-10,atol=1e-12)
    if kind=='zero':assert not np.any(a.load_capacitor_current) and not np.any(a.load_capacitor_energy)
    if kind.startswith('near'):assert np.any(a.load_capacitor_current[:,1:])
    if pulse and kind!='zero':assert np.any(a.load_capacitor_power<0)



@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('key',['load_branch_resistance_ohm','load_branch_inductance_h'])
@pytest.mark.parametrize('bad',['none','scalar','vector','shape','asymmetric','negative','tiny-negative','boolean','string','nonfinite','zero','singular','ratio'])
def test_explicit_branch_admission_without_propagation(signals,key,bad,monkeypatch):
    data=document(signals).to_dict();v=np.eye(signals)
    if bad=='none':v=None
    elif bad=='scalar':v=30.
    elif bad=='vector':v=[30.]*signals
    elif bad=='shape':v=np.eye(signals+1)
    elif bad=='asymmetric':v[0,1]=np.nextafter(v[1,0],np.inf)
    elif bad=='negative':v[-1,-1]=-1.
    elif bad=='tiny-negative':v[-1,-1]=-1e-20
    elif bad=='boolean':v=v.astype(bool)
    elif bad=='string':v=v.astype(str)
    elif bad=='nonfinite':v[0,0]=np.inf
    elif bad=='zero':v[:]=0.
    elif bad=='singular':v[-1,-1]=0.
    elif bad=='ratio':v[-1,-1]=1e-13
    data[key]=v.tolist() if isinstance(v,np.ndarray) else v
    monkeypatch.setattr(api,'lsim',forbidden)
    if key=='load_branch_resistance_ohm' and bad in ['zero','singular','ratio']:
        assert MixedSourceMulticonductorDebyeReactiveLadderDocument.from_dict(data).to_dict()==data
        assert json.loads(normalize_saved(json.dumps(data)))==data
    else:
        with pytest.raises(ValueError):MixedSourceMulticonductorDebyeReactiveLadderDocument.from_dict(data)
        with pytest.raises(ValueError):normalize_saved(json.dumps(data))



@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('kind',['zero','rank-one','near13','near20'])
@pytest.mark.parametrize('pulse',[False,True])
def test_branch_resistance_full_state_replay_and_partition(signals,kind,pulse):
    rb=np.zeros((signals,signals))
    if kind=='rank-one':rb[:2,:2]=[[30.,-30.],[-30.,30.]]
    elif kind.startswith('near'):rb=np.diag([30.]+[30.*10**(-int(kind[4:]))]*(signals-1))
    args=arguments(signals,pulse=pulse,load_branch_resistance=rb)
    d=MixedSourceMulticonductorDebyeReactiveLadderDocument(**args);expected=psd_multiconductor_debye_mixed_reactive_ladder_response(**args)
    a=MixedSourceMulticonductorDebyeReactiveLadderDocument.loads(d.dumps()).analyze(max_evaluations=121)
    assert normalize_saved(d.dumps())==d.dumps()
    assert a.to_dict(include_states=True)==expected.to_dict(include_states=True)
    assert execute_saved(d.dumps(),max_evaluations=121)['result']==expected.to_dict()
    assert a.inputs['load_branch_resistance_ohm']==rb.tolist()
    np.testing.assert_allclose(a.load_branch_resistor_loss,np.einsum('ti,ij,tj->t',a.load_branch_current,rb,a.load_branch_current),rtol=1e-10,atol=1e-15)
    lb=args['load_branch_inductance']
    np.testing.assert_allclose(a.load_branch_energy,.5*np.einsum('ti,ij,tj->t',a.load_branch_current,lb,a.load_branch_current),rtol=1e-10,atol=1e-22)
    np.testing.assert_array_equal(a.total_energy,a.line_energy+a.load_capacitor_energy+a.load_branch_energy)
    np.testing.assert_array_equal(a.total_energy_rate,a.line_energy_rate+a.load_capacitor_power+a.load_branch_energy_rate)
    np.testing.assert_allclose(a.current[:,signals:],-a.voltage[:,signals:]/100-a.load_capacitor_current-a.load_branch_current,rtol=1e-10,atol=1e-12)
    if kind=='zero':assert not np.any(a.load_branch_resistor_loss)


@pytest.mark.parametrize('signals',[3,4])
def test_canonical_sixteen_keys_copies_and_no_parse_propagation(signals,monkeypatch):
    monkeypatch.setattr(api,'lsim',forbidden);monkeypatch.setattr(module,'psd_multiconductor_debye_mixed_reactive_ladder_response',forbidden)
    a=arguments(signals);d=MixedSourceMulticonductorDebyeReactiveLadderDocument(**a);text=d.dumps()
    assert normalize_saved(text)==text and MixedSourceMulticonductorDebyeReactiveLadderDocument.loads(text).dumps()==text
    assert set(d.to_dict())=={'schema','time_s','sources','signals','R_ohm_per_m','L_h_per_m','G_s_per_m','C_inf_f_per_m','length_m','cells','load_resistance_ohm','delta_C_f_per_m','relaxation_hz','load_capacitance_f','load_branch_resistance_ohm','load_branch_inductance_h'}
    assert d.to_dict()['sources']==a['sources'] and d.samples==121
    assert 'sipi.multiconductor-debye-mixed-startup/1' in saved_schemas()
    a['sources'][0]['current_a'][1]=99;a['sources'][1]['series_resistance_ohm']=99;a['L'][:]=99
    data=d.to_dict();data['sources'][0]['current_a'].clear();data['sources'][1]['kind']='current';data['time_s'].clear()
    assert d.dumps()==text


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('key',['schema','time_s','sources','signals','R_ohm_per_m','L_h_per_m','G_s_per_m','C_inf_f_per_m','length_m','cells','load_resistance_ohm','delta_C_f_per_m','relaxation_hz','load_capacitance_f','load_branch_resistance_ohm','load_branch_inductance_h'])
def test_every_key_required_before_propagation(signals,key,monkeypatch):
    data=document(signals).to_dict();data.pop(key);monkeypatch.setattr(api,'lsim',forbidden)
    with pytest.raises(ValueError):MixedSourceMulticonductorDebyeReactiveLadderDocument.from_dict(data)
    with pytest.raises(ValueError):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('key,value',[
    ('schema','sipi.multiconductor-debye-mixed-startup/2'),('schema','sipi.multiconductor-debye-norton-startup/1'),
    ('extra',1),('R_ohm',[[1.]]),('C_f',[[1.]]),('signals',None),('signals',True),('signals',3.),('signals',2),('signals',5),
    ('time_s',[]),('time_s',[0.]),('time_s',[1.,2.,3.]),('time_s',[0.,0.,1.]),('time_s',[0.,1.,3.]),
    ('time_s',[0.,True,2.]),('time_s',[[0.,1.,2.]]),('sources',None),('sources',[]),('sources',{}),
    ('R_ohm_per_m',-1),('G_s_per_m',[[[0.]]]),('L_h_per_m',[[1.,0.],[0.,1e-14]]),('C_inf_f_per_m',[[0.]]),
    ('length_m',0),('length_m',float('inf')),('cells',0),('cells',65),('cells',True),('cells',8.),
    ('source_currents_a',[1.]),('source_voltages_v',[1.]),('source_shunt_conductance_s',[.02]*3),('source_resistance_ohm',[50.]*3),
    ('load_resistance_ohm',None),('load_resistance_ohm',[100.,0.,100.])])
def test_strict_root_source_alias_and_resource_rejection(signals,key,value,monkeypatch):
    data=document(signals).to_dict();data[key]=value;monkeypatch.setattr(api,'lsim',forbidden)
    with pytest.raises((ValueError,TypeError)):MixedSourceMulticonductorDebyeReactiveLadderDocument.from_dict(data)
    with pytest.raises((ValueError,TypeError)):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('kind',['voltage','current'])
@pytest.mark.parametrize('bad',['missing-kind','wrong-kind','list-kind','bool-kind','extra','missing-value','missing-parameter','alias','scalar-value','short-value','bool-value','initial-value','none-parameter','bool-parameter','negative-parameter','tiny-negative-parameter','infinite-parameter','string-parameter'])
def test_nested_typed_sources_reject_without_propagation(signals,kind,bad,monkeypatch):
    data=document(signals).to_dict();j=1 if kind=='voltage' else 0;s=data['sources'][j]
    value_key='voltage_v' if kind=='voltage' else 'current_a';param_key='series_resistance_ohm' if kind=='voltage' else 'shunt_conductance_s'
    if bad=='missing-kind':s.pop('kind')
    elif bad=='wrong-kind':s['kind']='Voltage'
    elif bad=='list-kind':s['kind']=[kind]
    elif bad=='bool-kind':s['kind']=True
    elif bad=='extra':s['extra']=1
    elif bad=='missing-value':s.pop(value_key)
    elif bad=='missing-parameter':s.pop(param_key)
    elif bad=='alias':s['drive']=s.pop(value_key)
    elif bad=='scalar-value':s[value_key]=1.
    elif bad=='short-value':s[value_key].pop()
    elif bad=='bool-value':s[value_key][1]=True
    elif bad=='initial-value':s[value_key][0]=1e-30
    elif bad=='none-parameter':s[param_key]=None
    elif bad=='bool-parameter':s[param_key]=True
    elif bad=='negative-parameter':s[param_key]=-1.
    elif bad=='tiny-negative-parameter':s[param_key]=-1e-300
    elif bad=='infinite-parameter':s[param_key]=np.inf
    else:s[param_key]='1'
    monkeypatch.setattr(api,'lsim',forbidden)
    with pytest.raises((ValueError,TypeError)):MixedSourceMulticonductorDebyeReactiveLadderDocument.from_dict(data)
    with pytest.raises((ValueError,TypeError)):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('bad',['voltage-zero','reciprocal-overflow','drive-overflow','drive-underflow'])
def test_voltage_boundary_transformation_limits_survive_saved_validation(signals,bad,monkeypatch):
    data=document(signals).to_dict();s=data['sources'][1]
    if bad=='voltage-zero':s['series_resistance_ohm']=0.
    elif bad=='reciprocal-overflow':s['series_resistance_ohm']=1e-320
    elif bad=='drive-overflow':s['series_resistance_ohm']=1e-200;s['voltage_v'][1]=1e200
    else:s['series_resistance_ohm']=1e300;s['voltage_v'][1]=1e-300
    monkeypatch.setattr(api,'lsim',forbidden)
    with pytest.raises(ValueError):MixedSourceMulticonductorDebyeReactiveLadderDocument.from_dict(data)
    with pytest.raises(ValueError):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('signals',[3,4])
def test_actual_row_budget_and_exactly_one_api_call(signals,monkeypatch):
    a=arguments(signals,time=[0.,1e-9,2e-9],source_currents=np.r_[np.zeros((1,signals)),np.full((2,signals),.01)],cells=64)
    d=MixedSourceMulticonductorDebyeReactiveLadderDocument(**a);original=module.psd_multiconductor_debye_mixed_reactive_ladder_response;calls=[]
    def spy(**kw):calls.append((len(kw['time']),kw['cells'],kw['signals'],kw['sources']));return original(**kw)
    monkeypatch.setattr(module,'psd_multiconductor_debye_mixed_reactive_ladder_response',spy)
    text=d.dumps();assert normalize_saved(text)==text and calls==[]
    out=execute_saved(text,max_evaluations=3)
    assert calls==[(3,64,signals,a['sources'])] and out['input']==d.to_dict()
    assert out['status']=='complete' and not out['result']['states_included'] and len(out['result']['time_s'])==3
    monkeypatch.setattr(module,'psd_multiconductor_debye_mixed_reactive_ladder_response',forbidden)
    with pytest.raises(ValueError,match='max_evaluations'):execute_saved(text,max_evaluations=2)
    for count in [1,10001]:
        with pytest.raises(ValueError):document(signals,time=np.linspace(0,1,count),source_currents=np.zeros((count,signals)))


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('pulse',[False,True])
def test_all_source_kind_masks_full_state_roundtrip(signals,pulse):
    a=arguments(signals,pulse=pulse);sources=a.pop('sources');drive=np.column_stack([s['voltage_v'] if s['kind']=='voltage' else s['current_a'] for s in sources])
    for bits in range(2**signals):
        typed=[dict(kind='voltage',voltage_v=drive[:,j].tolist(),series_resistance_ohm=50.) if bits&(1<<j) else dict(kind='current',current_a=(drive[:,j]*.02).tolist(),shunt_conductance_s=0. if j%2==0 else .02) for j in range(signals)]
        d=MixedSourceMulticonductorDebyeReactiveLadderDocument(**a,sources=typed);text=d.dumps();expected=psd_multiconductor_debye_mixed_reactive_ladder_response(**a,sources=typed)
        assert normalize_saved(text)==text and d.to_dict()['sources']==typed
        actual=MixedSourceMulticonductorDebyeReactiveLadderDocument.loads(text).analyze(max_evaluations=121)
        assert actual.to_dict(include_states=True)==expected.to_dict(include_states=True)
        out=execute_saved(text,max_evaluations=121);assert out['result']==expected.to_dict() and out['input']==d.to_dict()
        assert out['result']['source_units']==['V' if s['kind']=='voltage' else 'A' for s in typed]


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('tiny',[0.,1e-13,1e-20])
def test_small_current_shunts_preserved_exactly(signals,tiny):
    a=arguments(signals);a['sources'][0]['shunt_conductance_s']=tiny;d=MixedSourceMulticonductorDebyeReactiveLadderDocument(**a)
    assert normalize_saved(d.dumps())==d.dumps()
    assert d.analyze(max_evaluations=121).inputs['sources'][0]['shunt_conductance_s']==tiny
    assert execute_saved(d.dumps(),max_evaluations=121)['input']['sources']==a['sources']


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('change',['kind','voltage','current','series','shunt'])
def test_typed_input_identity_corruption_guard(signals,change,monkeypatch):
    d=document(signals);result=d.analyze(max_evaluations=121);data=result.inputs
    if change=='kind':data['sources'][0]['kind']='voltage'
    elif change=='voltage':data['sources'][1]['voltage_v'][1]+=.001
    elif change=='current':data['sources'][0]['current_a'][1]+=.001
    elif change=='series':data['sources'][1]['series_resistance_ohm']+=1.
    else:data['sources'][0]['shunt_conductance_s']+=.001
    bad=replace(result,input_json=json.dumps(data));monkeypatch.setattr(module,'psd_multiconductor_debye_mixed_reactive_ladder_response',lambda **kw:bad)
    with pytest.raises(ValueError,match='changed saved'):d.analyze(max_evaluations=121)


@pytest.mark.parametrize('signals',[3,4])
def test_no_implicit_voltage_or_current_schema_migration(signals):
    from sipi import NortonMulticonductorDebyeReactiveLadderDocument,MulticonductorDebyeReactiveLadderDocument
    d=document(signals)
    for cls,schema in [(NortonMulticonductorDebyeReactiveLadderDocument,'sipi.multiconductor-debye-norton-startup/1'),(MulticonductorDebyeReactiveLadderDocument,'sipi.multiconductor-debye-reactive-startup/1')]:
        with pytest.raises(ValueError):cls.loads(d.dumps())
        data=d.to_dict();data['schema']=schema
        with pytest.raises(ValueError):cls.from_dict(data)
    text=d.dumps();text=text.replace('"kind": "current"','"kind": "current", "kind": "current"',1)
    with pytest.raises(ValueError,match='duplicate'):normalize_saved(text)
