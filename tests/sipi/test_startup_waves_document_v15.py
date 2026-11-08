# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit wave v15: typed-source reactive Debye multiconductor inputs and legacy saved-wave replay."""
from dataclasses import replace
import json
import numpy as np
import pytest
from sipi import (StartupPortWavesDocument, MixedSourceMulticonductorDebyeReactiveLadderDocument,
                  LosslessStartupDocument, startup_port_waves)
from sipi.execution import execute_saved,normalize_saved,saved_schemas
from test_startup_waves_document_v14 import source as previous_source
from test_multiconductor_debye_mixed_startup_waves import arguments,typed_sources,equivalent
import sipi.startup_waves_document as module
import sipi.multiconductor_debye_mixed_startup as api


def source(kind='mixed_multi3',pulse=False):
    if kind.startswith('mixed_multi'):
        return MixedSourceMulticonductorDebyeReactiveLadderDocument(**arguments(int(kind[-1]),pulse=pulse))
    return previous_source(kind,pulse)


def references(nested):
    data=nested.to_dict()
    if data['schema'] in ('sipi.multiconductor-rlgc-startup/1','sipi.multiconductor-debye-rlgc-startup/1','sipi.psd-multiconductor-debye-rlgc-startup/1','sipi.multiconductor-debye-capacitive-startup/1','sipi.multiconductor-debye-reactive-startup/1','sipi.multiconductor-debye-norton-startup/1','sipi.multiconductor-debye-mixed-startup/1'):return np.linspace(35.,85.,2*data['signals']).tolist()
    return [35.,75.] if data['schema'] in ['sipi.lossless-startup/1','sipi.rlgc-startup/1','sipi.debye-rlgc-startup/1'] else [35.,45.,55.,65.]


def document(kind='mixed_multi3',pulse=False):
    nested=source(kind,pulse);return StartupPortWavesDocument(nested,z_ref=references(nested),version=15)


def forbidden(*a,**kw):pytest.fail('validation or budget reached propagation')


@pytest.mark.parametrize('kind',['lossless','scalar','coupled','mixed_boundary','capacitive','reactive','norton','mixed','debye','coupled_debye','psd_debye','debye_capacitive','debye_reactive','multi3','multi4','debye_multi3','debye_multi4','psd_multi3','psd_multi4','cap_multi3','cap_multi4','rl_multi3','rl_multi4','norton_multi3','norton_multi4','mixed_multi3','mixed_multi4'])
@pytest.mark.parametrize('pulse',[False,True])
def test_twenty_schemas_twenty_seven_variants_replay_exactly_and_preserve_prior_versions(kind,pulse):
    nested=source(kind,pulse);d=document(kind,pulse);text=d.dumps()
    assert normalize_saved(text)==text and StartupPortWavesDocument.loads(text).dumps()==text
    assert d.to_dict()['schema']=='sipi.startup-port-waves/15' and d.to_dict()['startup']==nested.to_dict()
    expected=startup_port_waves(nested.analyze(max_evaluations=121),z_ref=references(nested)).to_dict()
    assert d.analyze(max_evaluations=121).to_dict()==expected
    out=execute_saved(text,max_evaluations=121)
    assert out['status']=='complete' and out['error'] is None and out['input']==d.to_dict() and out['result']==expected
    if not kind.startswith('mixed_multi'):
        first={'norton':2,'mixed':3,'debye':4,'coupled_debye':5,'psd_debye':6,'debye_capacitive':7,'debye_reactive':8,'multi3':9,'multi4':9,'debye_multi3':10,'debye_multi4':10,'psd_multi3':11,'psd_multi4':11,'cap_multi3':12,'cap_multi4':12,'rl_multi3':13,'rl_multi4':13,'norton_multi3':14,'norton_multi4':14}.get(kind,1)
        for version in range(first,15):
            old=StartupPortWavesDocument(nested,z_ref=references(nested),version=version)
            assert old.to_dict()['schema']==f'sipi.startup-port-waves/{version}'
            assert normalize_saved(old.dumps())==old.dumps() and old.analyze(max_evaluations=121).to_dict()==expected
    json.dumps(out,allow_nan=False)


@pytest.mark.parametrize('signals',[3,4])
def test_canonical_copies_without_propagation_and_unchanged_default(signals,monkeypatch):
    monkeypatch.setattr(api,'lsim',forbidden);monkeypatch.setattr(module,'startup_port_waves',forbidden)
    nested=source(f'mixed_multi{signals}');z=np.array(references(nested));d=StartupPortWavesDocument(nested,z_ref=z,version=15);text=d.dumps()
    assert normalize_saved(text)==text and 'sipi.startup-port-waves/15' in saved_schemas()
    assert set(d.to_dict())=={'schema','startup','z_ref_ohm'}
    nested._data['signals']=99;z[:]=9;data=d.to_dict();loaded=StartupPortWavesDocument.from_dict(data);data['startup']['time_s'].clear()
    assert loaded.dumps()==text and d.dumps()==text
    assert StartupPortWavesDocument(source('scalar'),z_ref=[50.,50.]).to_dict()['schema']=='sipi.startup-port-waves/1'


@pytest.mark.parametrize('version',[True,False,0,999,15.,'15',None])
def test_explicit_integer_version_required(version):
    nested=source()
    with pytest.raises((ValueError,TypeError)):StartupPortWavesDocument(nested,z_ref=references(nested),version=version)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('version',range(1,15))
def test_old_versions_reject_multiconductor_without_upgrade(signals,version):
    nested=source(f'mixed_multi{signals}')
    with pytest.raises(ValueError):StartupPortWavesDocument(nested,z_ref=references(nested),version=version)
    data=document(f'mixed_multi{signals}').to_dict();data['schema']=f'sipi.startup-port-waves/{version}'
    with pytest.raises(ValueError):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('version',range(1,16))
def test_every_recursive_wave_kind_rejected(version,monkeypatch):
    data=document().to_dict();data['startup']=dict(schema=f'sipi.startup-port-waves/{version}',startup=data['startup'],z_ref_ohm=data['z_ref_ohm'])
    monkeypatch.setattr(api,'lsim',forbidden)
    with pytest.raises(ValueError):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('key,value',[
    ('signals',None),('signals',True),('signals',3.),('signals',2),('signals',5),
    ('schema','sipi.multiconductor-debye-mixed-startup/2'),('extra',1),('R_ohm',[[1.]]),('C_f',[[1.]]),
    ('R_ohm_per_m',[[1.]]),('G_s_per_m',-1),('L_h_per_m',[[1.,0.],[0.,1e-14]]),
    ('cells',0),('cells',65),('source_shunt_conductance_s',25.),('load_resistance_ohm',None),
    ('source_currents_a',[0.,1.,1.]),('time_s',[0.,1.,3.])])
def test_nested_signals_units_and_physical_inputs_reject_before_propagation(signals,key,value,monkeypatch):
    data=document(f'mixed_multi{signals}').to_dict();data['startup'][key]=value;monkeypatch.setattr(api,'lsim',forbidden)
    with pytest.raises((ValueError,TypeError)):StartupPortWavesDocument.from_dict(data)
    with pytest.raises((ValueError,TypeError)):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('kind',['scalar','two','four','other-count','zero','negative','bool','inf','complex','matrix'])
def test_reference_count_comes_from_explicit_validated_signals(signals,kind):
    nested=source(f'mixed_multi{signals}');z=references(nested)
    if kind=='scalar':z=50.
    elif kind=='two':z=[50.]*2
    elif kind=='four':z=[50.]*4
    elif kind=='other-count':z=[50.]*(8 if signals==3 else 6)
    elif kind=='matrix':z=np.diag(z)
    else:z[0]={'zero':0.,'negative':-1.,'bool':True,'inf':np.inf,'complex':50.+0j}[kind]
    with pytest.raises((ValueError,TypeError)):StartupPortWavesDocument(nested,z_ref=z,version=15)


@pytest.mark.parametrize('mutate',[
    lambda d:d.update(schema=[]),lambda d:d.update(schema='sipi.startup-port-waves/1599'),
    lambda d:d.update(extra=1),lambda d:d.pop('startup'),lambda d:d.pop('z_ref_ohm'),
    lambda d:d.update(startup=None),lambda d:d['startup'].pop('signals'),
    lambda d:d['startup'].update(schema=[]),lambda d:d['startup'].update(source_values=d['startup'].pop('sources'))])
def test_closed_root_and_nested_contract(mutate,monkeypatch):
    data=document().to_dict();mutate(data);monkeypatch.setattr(api,'lsim',forbidden)
    with pytest.raises((ValueError,TypeError)):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('text',['{"schema":"x","schema":"y"}',
    '{"schema":"sipi.startup-port-waves/15","startup":{},"z_ref_ohm":[NaN]}',
    '{"schema":"sipi.startup-port-waves/15","startup":{},"z_ref_ohm":[1e999]}','[]','null'])
def test_duplicate_nonfinite_and_nonobject_json(text):
    with pytest.raises(ValueError):StartupPortWavesDocument.loads(text)
    with pytest.raises(ValueError):normalize_saved(text)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('kind',['coupled','diagonal','lossless'])
@pytest.mark.parametrize('pulse',[False,True])
def test_multiconductor_input_and_every_terminal_power_partition(signals,kind,pulse):
    nested=MixedSourceMulticonductorDebyeReactiveLadderDocument(**arguments(signals,kind,pulse));z=references(nested)
    d=StartupPortWavesDocument(nested,z_ref=z,version=15);physical=nested.analyze(max_evaluations=121)
    expected=startup_port_waves(physical,z_ref=z).to_dict();out=execute_saved(d.dumps(),max_evaluations=121)
    assert out['result']==expected and out['input']['startup']==nested.to_dict()
    power=np.array(out['result']['port_power_w'])
    np.testing.assert_allclose(power[:,:signals].sum(axis=1),physical.source_power-physical.source_series_resistor_loss-physical.source_shunt_resistor_loss,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(power[:,signals:].sum(axis=1),-physical.load_resistor_loss-physical.load_capacitor_power-physical.load_branch_energy_rate-physical.load_branch_resistor_loss,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(power.sum(axis=1),physical.line_energy_rate+physical.series_loss+physical.shunt_loss+physical.relaxation_loss,rtol=1e-10,atol=1e-12)


@pytest.mark.parametrize('signals',[3,4])
def test_actual_time_budget_separate_from_cells_signals_and_lossless_terms(signals,monkeypatch):
    data=source(f'mixed_multi{signals}').to_dict();data.update(time_s=[0.,1e-9,2e-9],cells=64)
    for item in data['sources']:item['voltage_v' if item['kind']=='voltage' else 'current_a']=[0.,1.,1.] if item['kind']=='voltage' else [0.,.02,.02]
    nested=MixedSourceMulticonductorDebyeReactiveLadderDocument.from_dict(data);d=StartupPortWavesDocument(nested,z_ref=references(nested),version=15)
    out=execute_saved(d.dumps(),max_evaluations=3);assert out['input']['startup']['cells']==64 and len(out['result']['time_s'])==3
    lossless=LosslessStartupDocument(np.linspace(0,10e-9,1001),source_times=[0.,1e-9],source_voltages=[0.,1.],z0_ohm=50.,delay_s=1e-9,source_resistance=50.,load_resistance=None,max_terms=100)
    old=StartupPortWavesDocument(lossless,z_ref=[50.,50.],version=15);assert len(execute_saved(old.dumps(),max_evaluations=2)['result']['time_s'])==1001
    monkeypatch.setattr(api,'lsim',forbidden)
    with pytest.raises(ValueError,match='time samples exceed'):execute_saved(d.dumps(),max_evaluations=2)
    with pytest.raises(ValueError,match='max_input_bytes'):execute_saved(d.dumps(),max_input_bytes=2)
    with pytest.raises(ValueError,match='diagnostics'):execute_saved(d.dumps(),diagnostics=['modes'])


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('field',['type','time','voltage','current','z_ref','port_names','source_kind','incident','reflected','port_power'])
def test_output_identity_guards(signals,field,monkeypatch):
    d=document(f'mixed_multi{signals}');r=d.analyze()
    if field=='type':bad=None
    elif field=='port_names':bad=replace(r,port_names=tuple(reversed(r.port_names)))
    elif field=='source_kind':bad=replace(r,source_kind='other')
    elif field in ['time','voltage','current','z_ref']:bad=replace(r,**{field:getattr(r,field)+1.})
    else:bad=replace(r,**{field:np.zeros((121,4))})
    monkeypatch.setattr(module,'startup_port_waves',lambda *a,**kw:bad)
    with pytest.raises(ValueError,match='identity'):d.analyze()


@pytest.mark.parametrize('signals',[3,4])
def test_original_physical_and_wave_failures_retained(signals):
    data=source(f'mixed_multi{signals}').to_dict();data.update(L_h_per_m=(np.eye(signals)*1e-300).tolist(),C_inf_f_per_m=(np.eye(signals)*1e-300).tolist(),length_m=1e-300)
    nested=MixedSourceMulticonductorDebyeReactiveLadderDocument.from_dict(data);d=StartupPortWavesDocument(nested,z_ref=references(nested),version=15)
    assert normalize_saved(d.dumps())==d.dumps()
    with pytest.raises(ValueError,match='finite scales'):execute_saved(d.dumps())
    d=StartupPortWavesDocument(source(f'mixed_multi{signals}'),z_ref=[1e-30]*(2*signals),version=15)
    with pytest.raises(ValueError,match='reconstruction'):execute_saved(d.dumps(),max_evaluations=121)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('pole_case',['one','first-zero','all-zero','reordered'])
def test_declared_poles_preserved_and_engine_wave_called_once(signals,pole_case,monkeypatch):
    a=arguments(signals);delta=a['delta_C'].copy();poles=a['relaxation_hz'].copy()
    if pole_case=='one':delta=delta[:1];poles=poles[:1]
    elif pole_case=='first-zero':delta[0]=0
    elif pole_case=='all-zero':delta[:]=0
    else:delta=delta[::-1];poles=poles[::-1]
    a.update(delta_C=delta,relaxation_hz=poles)
    nested=MixedSourceMulticonductorDebyeReactiveLadderDocument(**a);d=StartupPortWavesDocument(nested,z_ref=references(nested),version=15)
    expected=startup_port_waves(nested.analyze(),z_ref=references(nested)).to_dict()
    import sipi.multiconductor_debye_mixed_startup_document as saved
    original=saved.psd_multiconductor_debye_mixed_reactive_ladder_response;wave=module.startup_port_waves;calls=[]
    def engine(*a,**kw):calls.append('engine');return original(*a,**kw)
    def convert(*a,**kw):calls.append('wave');return wave(*a,**kw)
    monkeypatch.setattr(saved,'psd_multiconductor_debye_mixed_reactive_ladder_response',engine)
    monkeypatch.setattr(module,'startup_port_waves',convert)
    text=d.dumps();assert normalize_saved(text)==text and calls==[]
    out=execute_saved(text,max_evaluations=121)
    assert out['result']==expected and calls==['engine','wave']
    assert out['input']['startup']==nested.to_dict()


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('key,value',[
    ('C_inf_f_per_m',[]),('delta_C_f_per_m',[]),('delta_C_f_per_m',[[1.]]),
    ('relaxation_hz',[]),('relaxation_hz',[0.,1.]),('relaxation_hz',[True,1.]),
    ('relaxation_hz',[float('inf'),1.]),('relaxation_hz',[1.]),
    ('C_inf_f_per_m',None),('delta_C_f_per_m',None)])
def test_debye_nested_contract_before_engine(signals,key,value,monkeypatch):
    data=document(f'mixed_multi{signals}').to_dict();data['startup'][key]=value
    import sipi.multiconductor_debye_mixed_startup_document as saved
    monkeypatch.setattr(saved,'psd_multiconductor_debye_mixed_reactive_ladder_response',forbidden)
    with pytest.raises((ValueError,TypeError)):StartupPortWavesDocument.from_dict(data)


@pytest.mark.parametrize('signals',[3,4])
def test_duplicate_nested_keys_are_rejected(signals):
    text=document(f'mixed_multi{signals}').dumps()
    text=text.replace('"signals": '+str(signals), '"signals": '+str(signals)+', "signals": '+str(signals))
    with pytest.raises(ValueError,match='duplicate'):normalize_saved(text)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('tiny',[0.,1e-13,1e-20])
def test_psd_nearzero_strength_and_rankone_loss_saved_waves_preserve_inputs(signals,tiny):
    a=arguments(signals);r=np.zeros((signals,signals));r[:2,:2]=[[20.,-20.],[-20.,20.]]
    g=np.zeros_like(r);g[1:3,1:3]=[[.002,.002],[.002,.002]]
    delta=np.array([np.diag([150e-12]+[150e-12*tiny]*(signals-1))]);a.update(R=r,G=g,delta_C=delta,relaxation_hz=[8e7])
    nested=MixedSourceMulticonductorDebyeReactiveLadderDocument(**a);d=StartupPortWavesDocument(nested,z_ref=references(nested),version=15)
    expected=startup_port_waves(nested.analyze(),z_ref=references(nested)).to_dict()
    text=d.dumps();assert normalize_saved(text)==text
    out=execute_saved(text,max_evaluations=121)
    assert out['result']==expected and out['input']['startup']==nested.to_dict()
    assert out['input']['startup']['delta_C_f_per_m']==delta.tolist()


@pytest.mark.parametrize('signals',[3,4])
def test_null_only_saved_terminal_waves_retain_zero_polarization_power(signals):
    a=arguments(signals)
    for source in a['sources'][:-1]:source['voltage_v' if source['kind']=='voltage' else 'current_a']=[0.]*len(a['time'])
    a.update(R=np.eye(signals)*20,L=np.eye(signals)*450e-9,G=np.eye(signals)*.002,
        C_inf=np.eye(signals)*210e-12,delta_C=np.array([np.diag([150e-12]+[0.]*(signals-1))]),relaxation_hz=[8e7])
    nested=MixedSourceMulticonductorDebyeReactiveLadderDocument(**a);physical=nested.analyze();z=references(nested)
    assert np.any(physical.polarization_voltage[:,:,:,-1])
    assert not np.any(physical.polarization_charge) and not np.any(physical.relaxation_loss)
    d=StartupPortWavesDocument(nested,z_ref=z,version=15);out=execute_saved(d.dumps(),max_evaluations=121)
    assert out['result']==startup_port_waves(physical,z_ref=z).to_dict()
    np.testing.assert_allclose(np.array(out['result']['port_power_w']).sum(axis=1),
        physical.energy_rate+physical.series_loss+physical.shunt_loss,rtol=1e-10,atol=1e-12)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('kind',['zero','rankone','near13','near20'])
@pytest.mark.parametrize('pulse',[False,True])
def test_external_capacitance_values_and_terminal_power_survive_saved_wave_replay(signals,kind,pulse):
    a=arguments(signals,pulse=pulse);cap=np.zeros((signals,signals))
    if kind=='rankone':cap[:2,:2]=np.array([[30.,-30.],[-30.,30.]])*1e-12
    elif kind.startswith('near'):cap=np.diag([30e-12]+[30e-12*10**(-int(kind[4:]))]*(signals-1))
    a['load_capacitance']=cap;nested=MixedSourceMulticonductorDebyeReactiveLadderDocument(**a)
    physical=nested.analyze();z=references(nested);d=StartupPortWavesDocument(nested,z_ref=z,version=15)
    expected=startup_port_waves(physical,z_ref=z).to_dict();text=d.dumps()
    assert normalize_saved(text)==text
    out=execute_saved(text,max_evaluations=121)
    assert out['result']==expected and out['input']['startup']['load_capacitance_f']==cap.tolist()
    power=np.asarray(out['result']['port_power_w'])
    np.testing.assert_allclose(power[:,signals:].sum(axis=1),-physical.load_resistor_loss-physical.load_capacitor_power-physical.load_branch_energy_rate-physical.load_branch_resistor_loss,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(power.sum(axis=1),physical.line_energy_rate+physical.series_loss+physical.shunt_loss+physical.relaxation_loss,rtol=1e-10,atol=1e-12)
    if pulse and kind!='zero':assert np.any(physical.load_capacitor_power<0)

@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('bad',['missing','shape','asymmetric','negative','tiny-negative','boolean','nonfinite'])
def test_nested_external_capacitance_rejects_before_engine(signals,bad,monkeypatch):
    data=document(f'mixed_multi{signals}').to_dict();cap=np.eye(signals)*30e-12
    if bad=='missing':data['startup'].pop('load_capacitance_f')
    else:
        if bad=='shape':cap=np.eye(signals+1)
        elif bad=='asymmetric':cap[0,1]=np.nextafter(0.,1.)
        elif bad=='negative':cap[-1,-1]=-30e-12
        elif bad=='tiny-negative':cap[-1,-1]=-30e-32
        elif bad=='boolean':cap=cap.astype(bool)
        else:cap[0,0]=np.inf
        data['startup']['load_capacitance_f']=cap.tolist()
    monkeypatch.setattr(api,'lsim',forbidden)
    with pytest.raises(ValueError):StartupPortWavesDocument.from_dict(data)
    with pytest.raises(ValueError):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('kind',['zero','rankone','near13','near20'])
@pytest.mark.parametrize('pulse',[False,True])
def test_branch_resistance_entries_and_terminal_power_survive_saved_wave_replay(signals,kind,pulse):
    a=arguments(signals,pulse=pulse);rb=np.zeros((signals,signals))
    if kind=='rankone':rb[:2,:2]=[[30.,-30.],[-30.,30.]]
    elif kind.startswith('near'):rb=np.diag([30.]+[30.*10**(-int(kind[4:]))]*(signals-1))
    a['load_branch_resistance']=rb;nested=MixedSourceMulticonductorDebyeReactiveLadderDocument(**a)
    physical=nested.analyze();z=references(nested);d=StartupPortWavesDocument(nested,z_ref=z,version=15)
    expected=startup_port_waves(physical,z_ref=z).to_dict();text=d.dumps()
    assert normalize_saved(text)==text
    out=execute_saved(text,max_evaluations=121)
    assert out['result']==expected and out['input']['startup']['load_branch_resistance_ohm']==rb.tolist()
    power=np.asarray(out['result']['port_power_w'])
    np.testing.assert_allclose(power[:,signals:].sum(axis=1),-physical.load_resistor_loss-physical.load_capacitor_power-physical.load_branch_energy_rate-physical.load_branch_resistor_loss,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(power.sum(axis=1),physical.line_energy_rate+physical.series_loss+physical.shunt_loss+physical.relaxation_loss,rtol=1e-10,atol=1e-12)
    if kind=='zero':assert not np.any(physical.load_branch_resistor_loss)

@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('key',['load_branch_resistance_ohm','load_branch_inductance_h'])
@pytest.mark.parametrize('bad',['missing','shape','asymmetric','negative','tiny-negative','boolean','nonfinite','zero','singular','ratio'])
def test_nested_branch_matrices_keep_physical_contract_before_engine(signals,key,bad,monkeypatch):
    data=document(f'mixed_multi{signals}').to_dict();v=np.eye(signals)
    if bad=='missing':data['startup'].pop(key)
    else:
        if bad=='shape':v=np.eye(signals+1)
        elif bad=='asymmetric':v[0,1]=np.nextafter(0.,1.)
        elif bad=='negative':v[-1,-1]=-1.
        elif bad=='tiny-negative':v[-1,-1]=-1e-20
        elif bad=='boolean':v=v.astype(bool)
        elif bad=='nonfinite':v[0,0]=np.inf
        elif bad=='zero':v[:]=0.
        elif bad=='singular':v[-1,-1]=0.
        elif bad=='ratio':v[-1,-1]=1e-13
        data['startup'][key]=v.tolist()
    monkeypatch.setattr(api,'lsim',forbidden)
    if key=='load_branch_resistance_ohm' and bad in ['zero','singular','ratio']:
        assert StartupPortWavesDocument.from_dict(data).to_dict()==data
        assert json.loads(normalize_saved(json.dumps(data)))==data
    else:
        with pytest.raises(ValueError):StartupPortWavesDocument.from_dict(data)
        with pytest.raises(ValueError):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('kind',['ideal','mixed','positive','near13','near20'])
@pytest.mark.parametrize('pulse',[False,True])
def test_typed_values_and_both_source_losses_survive_saved_wave_replay(signals,kind,pulse):
    a=arguments(signals,pulse=pulse);drive,_=equivalent(a['sources']);gs=np.zeros(signals)
    mask=0 if kind=='ideal' else sum(1<<j for j in range(signals) if j%2)
    for j in range(signals):
        if mask&(1<<j):gs[j]=.02
        elif kind=='positive':gs[j]=.03
        elif kind.startswith('near'):gs[j]=.02*10**(-int(kind[4:]))
    a['sources']=typed_sources(drive,gs,mask);nested=MixedSourceMulticonductorDebyeReactiveLadderDocument(**a)
    physical=nested.analyze();z=references(nested);d=StartupPortWavesDocument(nested,z_ref=z,version=15)
    text=d.dumps();assert normalize_saved(text)==text
    out=execute_saved(text,max_evaluations=121)
    assert out['result']==startup_port_waves(physical,z_ref=z).to_dict()
    assert out['input']['startup']['sources']==a['sources'] and len(out['input']['startup'])==16
    assert not {'source_voltages_v','source_currents_a','source_resistance_ohm','source_shunt_conductance_s'}&out['input']['startup'].keys()
    power=np.asarray(out['result']['port_power_w'])
    np.testing.assert_allclose(power[:,:signals].sum(axis=1),physical.source_power-physical.source_series_resistor_loss-physical.source_shunt_resistor_loss,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(physical.current[:,:signals],drive-physical.voltage[:,:signals]*gs,rtol=1e-13,atol=1e-15)
    if kind=='ideal':assert not np.any(physical.source_shunt_resistor_loss) and not np.any(physical.source_series_resistor_loss)
    else:assert np.any(physical.source_series_resistor_loss)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('bad',['missing','nondict','shape','kind','kind-bool','extra','voltage-alias','current-alias','resistance-alias','conductance-alias','voltage-zero-r','negative-g','boolean','nonfinite','initial','wave-shape','overflow','underflow'])
def test_nested_typed_source_contract_rejected_without_propagation(signals,bad,monkeypatch):
    data=document(f'mixed_multi{signals}').to_dict();nested=data['startup'];sources=nested['sources'];v=sources[1];i=sources[0]
    if bad=='missing':nested.pop('sources')
    elif bad=='nondict':sources[1]=[]
    elif bad=='shape':sources.pop()
    elif bad=='kind':v['kind']='Voltage'
    elif bad=='kind-bool':v['kind']=True
    elif bad=='extra':v['extra']=1
    elif bad=='voltage-alias':v['voltage']=v.pop('voltage_v')
    elif bad=='current-alias':i['current']=i.pop('current_a')
    elif bad=='resistance-alias':v['resistance_ohm']=v.pop('series_resistance_ohm')
    elif bad=='conductance-alias':i['shunt_resistance_ohm']=i.pop('shunt_conductance_s')
    elif bad=='voltage-zero-r':v['series_resistance_ohm']=0.
    elif bad=='negative-g':i['shunt_conductance_s']=-1e-30
    elif bad=='boolean':v['voltage_v'][1]=True
    elif bad=='nonfinite':i['current_a'][1]=float('inf')
    elif bad=='initial':v['voltage_v'][0]=1e-30
    elif bad=='wave-shape':i['current_a']=[i['current_a']]
    elif bad=='overflow':v['series_resistance_ohm']=1e-320
    else:v['series_resistance_ohm']=1e300;v['voltage_v'][1]=1e-300
    monkeypatch.setattr(api,'lsim',forbidden)
    with pytest.raises((ValueError,TypeError)):StartupPortWavesDocument.from_dict(data)
    with pytest.raises((ValueError,TypeError)):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('pulse',[False,True])
def test_all_typed_masks_original_units_and_saved_waves(signals,pulse):
    a=arguments(signals,pulse=pulse);drive,_=equivalent(a['sources']);gs=np.array([.04,.02,.01,.03])[:signals]
    for mask in range(1<<signals):
        a['sources']=typed_sources(drive,gs,mask);nested=MixedSourceMulticonductorDebyeReactiveLadderDocument(**a)
        physical=nested.analyze();z=references(nested);d=StartupPortWavesDocument(nested,z_ref=z,version=15)
        out=execute_saved(d.dumps(),max_evaluations=121)
        assert normalize_saved(d.dumps())==d.dumps()
        assert out['input']['startup']['sources']==a['sources']
        assert physical.source_units==tuple('V' if mask&(1<<j) else 'A' for j in range(signals))
        assert out['result']==startup_port_waves(physical,z_ref=z).to_dict()
