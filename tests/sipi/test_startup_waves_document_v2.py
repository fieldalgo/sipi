# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Nested startup storage preserves underlying versions, budgets and wave output."""
from dataclasses import replace
import json

import numpy as np
import pytest
from sipi import (StartupPortWavesDocument, LosslessStartupDocument, RLGCLadderDocument,
    CoupledRLGCLadderDocument, MixedBoundaryRLGCLadderDocument,
    CapacitiveRLGCLadderDocument, ReactiveRLGCLadderDocument, NortonReactiveRLGCLadderDocument, startup_port_waves)
from sipi.execution import execute_saved, normalize_saved, saved_schemas
import sipi.startup_waves_document as module
import sipi.startup as lossless_api
import sipi.rlgc_startup as scalar_api
import sipi.coupled_startup as coupled_api
import sipi.coupled_boundary_startup as mixed_api


def source_document(kind='reactive',pulse=False):
    t=np.linspace(0,12e-9,121)
    drive=np.interp(t,[0,2e-9,4e-9,6e-9],[0,1,1,0]) if pulse else np.minimum(t/2e-9,1.)
    if kind=='lossless':return LosslessStartupDocument(t,source_times=[0.,2e-9,4e-9,6e-9],
        source_voltages=[0.,1.,1.,0.] if pulse else [0.,1.,1.,1.],z0_ohm=50.,delay_s=1e-9,
        source_resistance=25.,load_resistance=100.,max_terms=100)
    if kind=='scalar':return RLGCLadderDocument(t,drive,R=20.,L=500e-9,G=.002,C=220e-12,
        length=.1,cells=8,source_resistance=25.,load_resistance=100.)
    kw=dict(R=[[25.,2.],[2.,17.]],L=np.array([[510.,70.],[70.,430.]])*1e-9,
        G=[[.003,-.0002],[-.0002,.0015]],C=np.array([[230.,-30.],[-30.,190.]])*1e-12,
        length=.1,cells=8,source_resistance=[23.,37.],load_resistance=[91.,113.])
    cls={'coupled':CoupledRLGCLadderDocument,'mixed':MixedBoundaryRLGCLadderDocument,
         'capacitive':CapacitiveRLGCLadderDocument,'reactive':ReactiveRLGCLadderDocument}[kind]
    if kind!='coupled':kw.update(source_resistance=[0.,37.],load_resistance=[0.,None])
    if kind in ['capacitive','reactive']:kw['load_capacitance']=np.array([[20.,-4.],[-4.,30.]])*1e-12
    if kind=='reactive':kw.update(load_branch_resistance=[[13.,1.],[1.,9.]],load_branch_inductance=np.array([[12.,2.],[2.,8.]])*1e-9)
    return cls(t,np.column_stack((drive,-.4*np.minimum(t/3e-9,1.))),**kw)



def source(kind='norton',pulse=False):
    if kind!='norton':return source_document(kind,pulse)
    data=source_document('reactive',pulse).to_dict()
    data['schema']='sipi.norton-rlgc-startup/1'
    data['source_currents_a']=(np.array(data.pop('source_voltages_v'))*.02).tolist()
    data['source_shunt_resistance_ohm']=[None,37.];data.pop('source_resistance_ohm')
    return NortonReactiveRLGCLadderDocument.from_dict(data)


def document(kind='norton',pulse=False):
    return StartupPortWavesDocument(source(kind,pulse),z_ref=[35.,75.] if kind in ['scalar','lossless'] else [35.,45.,55.,65.],version=2)


def forbidden(*a,**kw):pytest.fail('parsing or budget reached propagation')


@pytest.mark.parametrize('kind',['lossless','scalar','coupled','mixed','capacitive','reactive','norton'])
@pytest.mark.parametrize('pulse',[False,True])
def test_explicit_v2_seven_nested_schemas_replay_and_preserve_original_inputs(kind,pulse):
    d=document(kind,pulse);text=d.dumps();nested=source(kind,pulse)
    assert d.to_dict()['schema']=='sipi.startup-port-waves/2'
    assert normalize_saved(text)==text and StartupPortWavesDocument.loads(text).dumps()==text
    assert d.to_dict()['startup']==nested.to_dict()
    expected=startup_port_waves(nested.analyze(max_evaluations=121),z_ref=d.to_dict()['z_ref_ohm'])
    assert d.analyze(max_evaluations=121).to_dict()==expected.to_dict()
    out=execute_saved(text,max_evaluations=121)
    assert out['status']=='complete' and out['error'] is None and out['input']==d.to_dict()
    assert out['result']==expected.to_dict();json.dumps(out,allow_nan=False)
    if kind!='norton':
        original=StartupPortWavesDocument(nested,z_ref=d.to_dict()['z_ref_ohm'])
        assert original.to_dict()['schema']=='sipi.startup-port-waves/1'
        assert normalize_saved(original.dumps())==original.dumps()
        assert original.analyze(max_evaluations=121).to_dict()==out['result']
    else:
        r=nested.analyze(max_evaluations=121)
        np.testing.assert_allclose(np.array(out['result']['port_power_w'])[:,:2].sum(axis=1),r.source_power-r.source_shunt_resistor_loss,rtol=1e-10,atol=1e-12)


@pytest.mark.parametrize('kind',['lossless','scalar','coupled','mixed','capacitive','reactive','norton'])
def test_v2_parsing_is_no_propagation_and_copies_nested_values(kind,monkeypatch):
    for api in [scalar_api,coupled_api,mixed_api]:monkeypatch.setattr(api,'lsim',forbidden)
    monkeypatch.setattr(lossless_api,'_drive',forbidden);monkeypatch.setattr(module,'startup_port_waves',forbidden)
    nested=source(kind);z=[35.,75.] if kind in ['scalar','lossless'] else [35.,45.,55.,65.]
    d=StartupPortWavesDocument(nested,z_ref=z,version=2);text=d.dumps()
    assert normalize_saved(text)==text and 'sipi.startup-port-waves/2' in saved_schemas()
    nested._data['time_s'].clear();z[0]=99
    data=d.to_dict();loaded=StartupPortWavesDocument.from_dict(data);data['startup']['time_s'].clear()
    assert d.dumps()==text and loaded.dumps()==text


@pytest.mark.parametrize('version',[True,False,0,3,2.,'2',None])
def test_constructor_version_must_be_explicit_supported_integer(version):
    with pytest.raises((ValueError,TypeError)):StartupPortWavesDocument(source(),z_ref=[35.,45.,55.,65.],version=version)


def test_default_and_explicit_v1_reject_norton_without_upgrading():
    for kwargs in [{},{'version':1}]:
        with pytest.raises(ValueError):StartupPortWavesDocument(source(),z_ref=[35.,45.,55.,65.],**kwargs)
    data=document().to_dict();data['schema']='sipi.startup-port-waves/1'
    with pytest.raises(ValueError,match='nested startup'):StartupPortWavesDocument.from_dict(data)
    with pytest.raises(ValueError):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('mutate',[
    lambda d:d.update(schema=[]),lambda d:d.update(schema='sipi.startup-port-waves/999'),
    lambda d:d.update(extra=1),lambda d:d.pop('startup'),lambda d:d.pop('z_ref_ohm'),
    lambda d:d.update(startup=None),lambda d:d['startup'].update(schema=[]),
    lambda d:d['startup'].update(schema='sipi.startup-port-waves/1'),
    lambda d:d['startup'].update(schema='sipi.startup-port-waves/2'),
    lambda d:d['startup'].update(schema='sipi.norton-rlgc-startup/2'),
    lambda d:d['startup'].update(source_voltages_v=[[0,0]]*121),
    lambda d:d['startup'].update(source_resistance_ohm=[25,37]),
    lambda d:d['startup'].pop('source_currents_a'),lambda d:d['startup'].update(source_shunt_resistance_ohm=[-1,37]),
    lambda d:d.update(z_ref_ohm=[35.,45.]),lambda d:d.update(z_ref_ohm=[True,45.,55.,65.]),
])
def test_v2_rejects_recursive_wrong_unit_or_ambiguous_inputs_before_solving(mutate,monkeypatch):
    data=document().to_dict();mutate(data);monkeypatch.setattr(mixed_api,'lsim',forbidden)
    with pytest.raises((ValueError,TypeError)):StartupPortWavesDocument.from_dict(data)
    with pytest.raises((ValueError,TypeError)):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('shunt,load',[
    ([None,None],[None,None]),([0.,0.],[0.,0.]),([None,37.],[None,0.]),
    ([23.,0.],[0.,None]),([23.,37.],[None,100.]),([23.,37.],[91.,113.]),
])
def test_v2_mixed_norton_boundaries_replay_terminal_waves(shunt,load):
    data=source().to_dict();data['source_shunt_resistance_ohm']=shunt;data['load_resistance_ohm']=load
    nested=NortonReactiveRLGCLadderDocument.from_dict(data);d=StartupPortWavesDocument(nested,z_ref=[35.,45.,55.,65.],version=2)
    expected=startup_port_waves(nested.analyze(max_evaluations=121),z_ref=[35.,45.,55.,65.]).to_dict()
    assert execute_saved(d.dumps(),max_evaluations=121)['result']==expected


def test_v2_delegates_distinct_norton_time_rows_and_lossless_delay_terms(monkeypatch):
    data=source().to_dict();data.update(time_s=[0.,1e-9,2e-9],source_currents_a=[[0.,0.],[.02,0.],[.02,0.]],cells=128)
    d=StartupPortWavesDocument(NortonReactiveRLGCLadderDocument.from_dict(data),z_ref=[35.,45.,55.,65.],version=2)
    out=execute_saved(d.dumps(),max_evaluations=3);assert len(out['result']['time_s'])==3 and out['input']['startup']['cells']==128
    lossless=LosslessStartupDocument(np.linspace(0,10e-9,1001),source_times=[0.,1e-9],source_voltages=[0.,1.],z0_ohm=50.,delay_s=1e-9,source_resistance=50.,load_resistance=None,max_terms=100)
    delay=StartupPortWavesDocument(lossless,z_ref=[50.,50.],version=2)
    assert len(execute_saved(delay.dumps(),max_evaluations=2)['result']['time_s'])==1001
    monkeypatch.setattr(mixed_api,'lsim',forbidden)
    with pytest.raises(ValueError,match='time samples exceed'):execute_saved(d.dumps(),max_evaluations=2)
    with pytest.raises(ValueError,match='max_input_bytes'):execute_saved(d.dumps(),max_input_bytes=2)
    with pytest.raises(ValueError,match='diagnostics'):execute_saved(d.dumps(),diagnostics=['modes'])


@pytest.mark.parametrize('change',['type','time','voltage','current','z_ref','port_names','source_kind','incident','reflected','port_power'])
def test_v2_result_identity_is_guarded(change,monkeypatch):
    d=document();r=d.analyze()
    if change=='type':bad=None
    elif change=='port_names':bad=replace(r,port_names=tuple(reversed(r.port_names)))
    elif change=='source_kind':bad=replace(r,source_kind='other')
    elif change in ['time','voltage','current','z_ref']:bad=replace(r,**{change:getattr(r,change)+1.})
    else:bad=replace(r,**{change:np.zeros((121,2))})
    monkeypatch.setattr(module,'startup_port_waves',lambda *a,**k:bad)
    with pytest.raises(ValueError,match='identity'):d.analyze()


def test_v2_preserves_runtime_physical_failure():
    data=source().to_dict();data.update(L_h_per_m=(np.eye(2)*1e-300).tolist(),C_f_per_m=(np.eye(2)*1e-300).tolist(),length_m=1e-300)
    d=StartupPortWavesDocument(NortonReactiveRLGCLadderDocument.from_dict(data),z_ref=[35.,45.,55.,65.],version=2)
    assert normalize_saved(d.dumps())==d.dumps()
    with pytest.raises(ValueError,match='finite scales'):execute_saved(d.dumps())
