# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit wave v10: Debye multiconductor inputs and legacy saved-wave replay."""
from dataclasses import replace
import json
import numpy as np
import pytest
from sipi import (StartupPortWavesDocument, MulticonductorDebyeRLGCLadderDocument,
                  LosslessStartupDocument, startup_port_waves)
from sipi.execution import execute_saved,normalize_saved,saved_schemas
from test_startup_waves_document_v9 import source as previous_source
from test_multiconductor_debye_startup_waves import arguments
import sipi.startup_waves_document as module
import sipi.multiconductor_debye_startup as api


def source(kind='debye_multi3',pulse=False):
    if kind.startswith('debye_multi'):
        return MulticonductorDebyeRLGCLadderDocument(**arguments(int(kind[-1]),pulse=pulse))
    return previous_source(kind,pulse)


def references(nested):
    data=nested.to_dict()
    if data['schema'] in ('sipi.multiconductor-rlgc-startup/1','sipi.multiconductor-debye-rlgc-startup/1'):return np.linspace(35.,85.,2*data['signals']).tolist()
    return [35.,75.] if data['schema'] in ['sipi.lossless-startup/1','sipi.rlgc-startup/1','sipi.debye-rlgc-startup/1'] else [35.,45.,55.,65.]


def document(kind='debye_multi3',pulse=False):
    nested=source(kind,pulse);return StartupPortWavesDocument(nested,z_ref=references(nested),version=10)


def forbidden(*a,**kw):pytest.fail('validation or budget reached propagation')


@pytest.mark.parametrize('kind',['lossless','scalar','coupled','mixed_boundary','capacitive','reactive','norton','mixed','debye','coupled_debye','psd_debye','debye_capacitive','debye_reactive','multi3','multi4','debye_multi3','debye_multi4'])
@pytest.mark.parametrize('pulse',[False,True])
def test_fifteen_schemas_seventeen_variants_replay_exactly_and_preserve_prior_versions(kind,pulse):
    nested=source(kind,pulse);d=document(kind,pulse);text=d.dumps()
    assert normalize_saved(text)==text and StartupPortWavesDocument.loads(text).dumps()==text
    assert d.to_dict()['schema']=='sipi.startup-port-waves/10' and d.to_dict()['startup']==nested.to_dict()
    expected=startup_port_waves(nested.analyze(max_evaluations=121),z_ref=references(nested)).to_dict()
    assert d.analyze(max_evaluations=121).to_dict()==expected
    out=execute_saved(text,max_evaluations=121)
    assert out['status']=='complete' and out['error'] is None and out['input']==d.to_dict() and out['result']==expected
    if not kind.startswith('debye_multi'):
        first={'norton':2,'mixed':3,'debye':4,'coupled_debye':5,'psd_debye':6,'debye_capacitive':7,'debye_reactive':8,'multi3':9,'multi4':9}.get(kind,1)
        for version in range(first,10):
            old=StartupPortWavesDocument(nested,z_ref=references(nested),version=version)
            assert old.to_dict()['schema']==f'sipi.startup-port-waves/{version}'
            assert normalize_saved(old.dumps())==old.dumps() and old.analyze(max_evaluations=121).to_dict()==expected
    json.dumps(out,allow_nan=False)


@pytest.mark.parametrize('signals',[3,4])
def test_canonical_copies_without_propagation_and_unchanged_default(signals,monkeypatch):
    monkeypatch.setattr(api,'lsim',forbidden);monkeypatch.setattr(module,'startup_port_waves',forbidden)
    nested=source(f'debye_multi{signals}');z=np.array(references(nested));d=StartupPortWavesDocument(nested,z_ref=z,version=10);text=d.dumps()
    assert normalize_saved(text)==text and 'sipi.startup-port-waves/10' in saved_schemas()
    assert set(d.to_dict())=={'schema','startup','z_ref_ohm'}
    nested._data['signals']=99;z[:]=9;data=d.to_dict();loaded=StartupPortWavesDocument.from_dict(data);data['startup']['time_s'].clear()
    assert loaded.dumps()==text and d.dumps()==text
    assert StartupPortWavesDocument(source('scalar'),z_ref=[50.,50.]).to_dict()['schema']=='sipi.startup-port-waves/1'


@pytest.mark.parametrize('version',[True,False,0,999,10.,'10',None])
def test_explicit_integer_version_required(version):
    nested=source()
    with pytest.raises((ValueError,TypeError)):StartupPortWavesDocument(nested,z_ref=references(nested),version=version)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('version',range(1,10))
def test_old_versions_reject_multiconductor_without_upgrade(signals,version):
    nested=source(f'debye_multi{signals}')
    with pytest.raises(ValueError):StartupPortWavesDocument(nested,z_ref=references(nested),version=version)
    data=document(f'debye_multi{signals}').to_dict();data['schema']=f'sipi.startup-port-waves/{version}'
    with pytest.raises(ValueError):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('version',range(1,11))
def test_every_recursive_wave_kind_rejected(version,monkeypatch):
    data=document().to_dict();data['startup']=dict(schema=f'sipi.startup-port-waves/{version}',startup=data['startup'],z_ref_ohm=data['z_ref_ohm'])
    monkeypatch.setattr(api,'lsim',forbidden)
    with pytest.raises(ValueError):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('key,value',[
    ('signals',None),('signals',True),('signals',3.),('signals',2),('signals',5),
    ('schema','sipi.multiconductor-debye-rlgc-startup/2'),('extra',1),('R_ohm',[[1.]]),('C_f',[[1.]]),
    ('R_ohm_per_m',[[1.]]),('G_s_per_m',-1),('L_h_per_m',[[1.,0.],[0.,1e-14]]),
    ('cells',0),('cells',65),('source_resistance_ohm',25.),('load_resistance_ohm',None),
    ('source_voltages_v',[0.,1.,1.]),('time_s',[0.,1.,3.])])
def test_nested_signals_units_and_physical_inputs_reject_before_propagation(signals,key,value,monkeypatch):
    data=document(f'debye_multi{signals}').to_dict();data['startup'][key]=value;monkeypatch.setattr(api,'lsim',forbidden)
    with pytest.raises((ValueError,TypeError)):StartupPortWavesDocument.from_dict(data)
    with pytest.raises((ValueError,TypeError)):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('kind',['scalar','two','four','other-count','zero','negative','bool','inf','complex','matrix'])
def test_reference_count_comes_from_explicit_validated_signals(signals,kind):
    nested=source(f'debye_multi{signals}');z=references(nested)
    if kind=='scalar':z=50.
    elif kind=='two':z=[50.]*2
    elif kind=='four':z=[50.]*4
    elif kind=='other-count':z=[50.]*(8 if signals==3 else 6)
    elif kind=='matrix':z=np.diag(z)
    else:z[0]={'zero':0.,'negative':-1.,'bool':True,'inf':np.inf,'complex':50.+0j}[kind]
    with pytest.raises((ValueError,TypeError)):StartupPortWavesDocument(nested,z_ref=z,version=10)


@pytest.mark.parametrize('mutate',[
    lambda d:d.update(schema=[]),lambda d:d.update(schema='sipi.startup-port-waves/1099'),
    lambda d:d.update(extra=1),lambda d:d.pop('startup'),lambda d:d.pop('z_ref_ohm'),
    lambda d:d.update(startup=None),lambda d:d['startup'].pop('signals'),
    lambda d:d['startup'].update(schema=[]),lambda d:d['startup'].update(source_resistance_ohm_per_m=d['startup'].pop('source_resistance_ohm'))])
def test_closed_root_and_nested_contract(mutate,monkeypatch):
    data=document().to_dict();mutate(data);monkeypatch.setattr(api,'lsim',forbidden)
    with pytest.raises((ValueError,TypeError)):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('text',['{"schema":"x","schema":"y"}',
    '{"schema":"sipi.startup-port-waves/10","startup":{},"z_ref_ohm":[NaN]}',
    '{"schema":"sipi.startup-port-waves/10","startup":{},"z_ref_ohm":[1e999]}','[]','null'])
def test_duplicate_nonfinite_and_nonobject_json(text):
    with pytest.raises(ValueError):StartupPortWavesDocument.loads(text)
    with pytest.raises(ValueError):normalize_saved(text)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('kind',['coupled','diagonal','lossless'])
@pytest.mark.parametrize('pulse',[False,True])
def test_multiconductor_input_and_every_terminal_power_partition(signals,kind,pulse):
    nested=MulticonductorDebyeRLGCLadderDocument(**arguments(signals,kind,pulse));z=references(nested)
    d=StartupPortWavesDocument(nested,z_ref=z,version=10);physical=nested.analyze(max_evaluations=121)
    expected=startup_port_waves(physical,z_ref=z).to_dict();out=execute_saved(d.dumps(),max_evaluations=121)
    assert out['result']==expected and out['input']['startup']==nested.to_dict()
    power=np.array(out['result']['port_power_w'])
    np.testing.assert_allclose(power[:,:signals].sum(axis=1),physical.source_power-physical.source_resistor_loss,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(power[:,signals:].sum(axis=1),-physical.load_resistor_loss,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(power.sum(axis=1),physical.total_energy_rate+physical.series_loss+physical.shunt_loss+physical.relaxation_loss,rtol=1e-10,atol=1e-12)


@pytest.mark.parametrize('signals',[3,4])
def test_actual_time_budget_separate_from_cells_signals_and_lossless_terms(signals,monkeypatch):
    data=source(f'debye_multi{signals}').to_dict();data.update(time_s=[0.,1e-9,2e-9],source_voltages_v=[[0.]*signals,[1.]*signals,[1.]*signals],cells=64)
    nested=MulticonductorDebyeRLGCLadderDocument.from_dict(data);d=StartupPortWavesDocument(nested,z_ref=references(nested),version=10)
    out=execute_saved(d.dumps(),max_evaluations=3);assert out['input']['startup']['cells']==64 and len(out['result']['time_s'])==3
    lossless=LosslessStartupDocument(np.linspace(0,10e-9,1001),source_times=[0.,1e-9],source_voltages=[0.,1.],z0_ohm=50.,delay_s=1e-9,source_resistance=50.,load_resistance=None,max_terms=100)
    old=StartupPortWavesDocument(lossless,z_ref=[50.,50.],version=10);assert len(execute_saved(old.dumps(),max_evaluations=2)['result']['time_s'])==1001
    monkeypatch.setattr(api,'lsim',forbidden)
    with pytest.raises(ValueError,match='time samples exceed'):execute_saved(d.dumps(),max_evaluations=2)
    with pytest.raises(ValueError,match='max_input_bytes'):execute_saved(d.dumps(),max_input_bytes=2)
    with pytest.raises(ValueError,match='diagnostics'):execute_saved(d.dumps(),diagnostics=['modes'])


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('field',['type','time','voltage','current','z_ref','port_names','source_kind','incident','reflected','port_power'])
def test_output_identity_guards(signals,field,monkeypatch):
    d=document(f'debye_multi{signals}');r=d.analyze()
    if field=='type':bad=None
    elif field=='port_names':bad=replace(r,port_names=tuple(reversed(r.port_names)))
    elif field=='source_kind':bad=replace(r,source_kind='other')
    elif field in ['time','voltage','current','z_ref']:bad=replace(r,**{field:getattr(r,field)+1.})
    else:bad=replace(r,**{field:np.zeros((121,4))})
    monkeypatch.setattr(module,'startup_port_waves',lambda *a,**kw:bad)
    with pytest.raises(ValueError,match='identity'):d.analyze()


@pytest.mark.parametrize('signals',[3,4])
def test_original_physical_and_wave_failures_retained(signals):
    data=source(f'debye_multi{signals}').to_dict();data.update(L_h_per_m=(np.eye(signals)*1e-300).tolist(),C_inf_f_per_m=(np.eye(signals)*1e-300).tolist(),length_m=1e-300)
    nested=MulticonductorDebyeRLGCLadderDocument.from_dict(data);d=StartupPortWavesDocument(nested,z_ref=references(nested),version=10)
    assert normalize_saved(d.dumps())==d.dumps()
    with pytest.raises(ValueError,match='finite scales'):execute_saved(d.dumps())
    d=StartupPortWavesDocument(source(f'debye_multi{signals}'),z_ref=[1e-30]*(2*signals),version=10)
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
    nested=MulticonductorDebyeRLGCLadderDocument(**a);d=StartupPortWavesDocument(nested,z_ref=references(nested),version=10)
    expected=startup_port_waves(nested.analyze(),z_ref=references(nested)).to_dict()
    import sipi.multiconductor_debye_startup_document as saved
    original=saved.multiconductor_debye_rlgc_ladder_response;wave=module.startup_port_waves;calls=[]
    def engine(*a,**kw):calls.append('engine');return original(*a,**kw)
    def convert(*a,**kw):calls.append('wave');return wave(*a,**kw)
    monkeypatch.setattr(saved,'multiconductor_debye_rlgc_ladder_response',engine)
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
    data=document(f'debye_multi{signals}').to_dict();data['startup'][key]=value
    import sipi.multiconductor_debye_startup_document as saved
    monkeypatch.setattr(saved,'multiconductor_debye_rlgc_ladder_response',forbidden)
    with pytest.raises((ValueError,TypeError)):StartupPortWavesDocument.from_dict(data)


@pytest.mark.parametrize('signals',[3,4])
def test_duplicate_nested_keys_are_rejected(signals):
    text=document(f'debye_multi{signals}').dumps()
    text=text.replace('"signals": '+str(signals), '"signals": '+str(signals)+', "signals": '+str(signals))
    with pytest.raises(ValueError,match='duplicate'):normalize_saved(text)
