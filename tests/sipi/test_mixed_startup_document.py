# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Typed mixed-source saved inputs, exact replay and original budget semantics."""
import json
from dataclasses import replace
from copy import copy
import numpy as np
import pytest
from sipi import (MixedSourceRLGCLadderDocument, coupled_mixed_source_ladder_response,
    NortonReactiveRLGCLadderDocument, ReactiveRLGCLadderDocument, StartupPortWavesDocument)
from sipi.execution import execute_saved,normalize_saved,saved_schemas
import sipi.mixed_startup_document as module
import sipi.coupled_boundary_startup as core


def arguments(**changes):
    a=dict(time=[0.,1e-9,2e-9],sources=[dict(kind='voltage',voltage_v=[0.,1.,1.],series_resistance_ohm=0.),
        dict(kind='current',current_a=[0.,-.008,-.008],shunt_resistance_ohm=None)],
        R=[[25.,2.],[2.,17.]],L=np.array([[510.,70.],[70.,430.]])*1e-9,
        G=[[.003,-.0002],[-.0002,.0015]],C=np.array([[230.,-30.],[-30.,190.]])*1e-12,
        length=.1,cells=8,load_resistance=[91.,None],load_capacitance=np.array([[20.,-4.],[-4.,30.]])*1e-12,
        load_branch_resistance=[[13.,1.],[1.,9.]],load_branch_inductance=np.array([[12.,2.],[2.,8.]])*1e-9)
    a.update(changes);return a


def document(**changes):return MixedSourceRLGCLadderDocument(**arguments(**changes))


def forbidden(*args,**kwargs):pytest.fail('parsing or budget reached propagation')


def test_nested_typed_sources_copy_and_normalize_without_solving(monkeypatch):
    monkeypatch.setattr(core,'lsim',forbidden);monkeypatch.setattr(module,'coupled_mixed_source_ladder_response',forbidden)
    a=arguments();d=MixedSourceRLGCLadderDocument(**a);text=d.dumps()
    assert normalize_saved(text)==text and MixedSourceRLGCLadderDocument.loads(text).dumps()==text
    assert 'sipi.mixed-rlgc-startup/1' in saved_schemas() and d.samples==3
    a['sources'][0]['voltage_v'][1]=99;a['sources'][1]['kind']='voltage';a['L'][:]=99
    data=d.to_dict();loaded=MixedSourceRLGCLadderDocument.from_dict(data)
    data['sources'][0]['voltage_v'].clear();data['time_s'].clear()
    assert d.dumps()==text and loaded.dumps()==text


@pytest.mark.parametrize('key',['schema','time_s','sources','R_ohm_per_m','L_h_per_m','G_s_per_m','C_f_per_m','length_m','cells','load_resistance_ohm','load_capacitance_f','load_branch_resistance_ohm','load_branch_inductance_h'])
def test_all_thirteen_root_keys_are_required(key,monkeypatch):
    data=document().to_dict();data.pop(key);monkeypatch.setattr(core,'lsim',forbidden)
    with pytest.raises(ValueError):MixedSourceRLGCLadderDocument.from_dict(data)
    with pytest.raises(ValueError):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('mutate',[
    lambda d:d.update(schema='sipi.mixed-rlgc-startup/2'),lambda d:d.update(extra=1),lambda d:d.update(sources=[]),
    lambda d:d['sources'][0].update(kind='unknown'),lambda d:d['sources'][0].update(current_a=[0.,1.,1.]),
    lambda d:d['sources'][1].update(voltage_v=[0.,1.,1.]),lambda d:d['sources'][0].pop('voltage_v'),
    lambda d:d['sources'][0].update(series_resistance_ohm=None),lambda d:d['sources'][0].update(shunt_resistance_ohm=25.),
    lambda d:d['sources'][1].update(series_resistance_ohm=25.),lambda d:d['sources'][1].update(shunt_resistance_ohm=np.inf),
    lambda d:d['sources'][0].update(voltage_v=[0.,True,True]),lambda d:d['sources'][1].update(current_a=[0.,1.]),
    lambda d:d['sources'][1].update(current_a=[1.,1.,1.]),lambda d:d.update(time_s=[0.,1.,3.]),
    lambda d:d.update(cells=129),lambda d:d.update(cells=True),lambda d:d.update(load_resistance_ohm=[-1,None]),
    lambda d:d.update(load_capacitance_f=[[1,0],[0,-1e-30]]),lambda d:d.update(load_branch_inductance_h=[[1,0],[0,1e-14]]),
    lambda d:d.update(load_branch_resistance_ohm=[[1,1e-15],[0,1]]),lambda d:d.update(L_h_per_m=[[0,0],[0,0]]),
])
def test_strict_source_units_and_shared_physical_inputs_reject_before_solving(mutate,monkeypatch):
    data=document().to_dict();mutate(data);monkeypatch.setattr(core,'lsim',forbidden)
    with pytest.raises((ValueError,TypeError)):MixedSourceRLGCLadderDocument.from_dict(data)
    with pytest.raises((ValueError,TypeError)):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('text',['null','[]','{"schema":"x","schema":"y"}',
    '{"schema":"sipi.mixed-rlgc-startup/1","sources":[{"kind":"voltage","kind":"current"}]}',
    '{"schema":"sipi.mixed-rlgc-startup/1","time_s":[NaN]}',
    '{"schema":"sipi.mixed-rlgc-startup/1","time_s":[1e999]}'])
def test_duplicate_nonfinite_and_nonobject_json_reject(text):
    with pytest.raises(ValueError):MixedSourceRLGCLadderDocument.loads(text)
    with pytest.raises(ValueError):normalize_saved(text)


@pytest.mark.parametrize('kind',['asymmetric','exchange','decoupled'])
@pytest.mark.parametrize('pulse',[False,True])
def test_actual_matrix_ramp_pulse_replays_complete_physical_states(kind,pulse):
    t=np.linspace(0,12e-9,121);v=np.interp(t,[0,2e-9,4e-9,6e-9],[0,1,1,0]) if pulse else np.minimum(t/2e-9,1.)
    a=arguments(time=t,sources=[dict(kind='voltage',voltage_v=v,series_resistance_ohm=0.),
        dict(kind='current',current_a=-.008*np.minimum(t/3e-9,1.),shunt_resistance_ohm=None)])
    if kind=='exchange':a.update(R=[[20.,3.],[3.,20.]],L=np.array([[500.,100.],[100.,500.]])*1e-9,G=[[.002,-.0003],[-.0003,.002]],C=np.array([[220.,-40.],[-40.,220.]])*1e-12)
    if kind=='decoupled':
        for field in ['R','L','G','C']:a[field]=np.diag(np.diag(a[field]))
    expected=coupled_mixed_source_ladder_response(**a);d=MixedSourceRLGCLadderDocument(**a);loaded=MixedSourceRLGCLadderDocument.loads(d.dumps())
    assert loaded.analyze(max_evaluations=121).to_dict(include_states=True)==expected.to_dict(include_states=True)
    out=execute_saved(d.dumps(),max_evaluations=121)
    assert out['input']==d.to_dict() and out['status']=='complete' and out['error'] is None
    assert out['result']==expected.to_dict();json.dumps(out,allow_nan=False)
    assert out['result']['source_kinds']==['voltage','current'] and out['result']['source_units']==['V','A']


@pytest.mark.parametrize('kinds,resistance,load',[
    (['voltage','current'],[0.,None],[91.,None]),(['current','voltage'],[None,0.],[None,0.]),
    (['voltage','current'],[25.,37.],[91.,113.]),(['current','voltage'],[37.,25.],[91.,113.]),
    (['voltage','current'],[0.,0.],[0.,None]),(['current','voltage'],[0.,0.],[None,0.]),
    (['voltage','voltage'],[0.,37.],[91.,None]),(['current','current'],[None,37.],[91.,None]),
])
def test_actual_source_kind_and_boundary_combinations_replay(kinds,resistance,load):
    src=[dict(kind=k,**{('voltage_v' if k=='voltage' else 'current_a'):[0.,1.,1.] if k=='voltage' else [0.,.02,.02],
        ('series_resistance_ohm' if k=='voltage' else 'shunt_resistance_ohm'):resistance[j]}) for j,k in enumerate(kinds)]
    a=arguments(sources=src,load_resistance=load);d=MixedSourceRLGCLadderDocument(**a)
    assert execute_saved(d.dumps())['result']==coupled_mixed_source_ladder_response(**a).to_dict()


def test_row_budget_is_independent_of_cells_and_source_kinds(monkeypatch):
    d=document(cells=128);out=execute_saved(d.dumps(),max_evaluations=3)
    assert len(out['result']['time_s'])==3 and out['input']['cells']==128
    monkeypatch.setattr(module,'coupled_mixed_source_ladder_response',forbidden)
    for small in [d,document(cells=1)]:
        with pytest.raises(ValueError,match='time samples exceed'):small.analyze(max_evaluations=2)
        with pytest.raises(ValueError,match='time samples exceed'):execute_saved(small.dumps(),max_evaluations=2)
    with pytest.raises(ValueError,match='max_input_bytes'):execute_saved(d.dumps(),max_input_bytes=2)
    with pytest.raises(ValueError,match='diagnostics'):execute_saved(d.dumps(),diagnostics=['modes'])
    for budget in [True,1,10001,3.]:
        with pytest.raises((ValueError,TypeError)):d.analyze(max_evaluations=budget)


@pytest.mark.parametrize('field',['type','inputs','time','source_values','node_voltage','segment_current','voltage','current',
    'source_series_resistor_loss','source_shunt_resistor_loss','load_capacitor_current','load_capacitor_energy','load_capacitor_power',
    'load_branch_current','load_branch_energy','load_branch_energy_rate','load_branch_resistor_loss'])
def test_bad_solver_identity_or_shape_rejects(field,monkeypatch):
    d=document();r=d.analyze()
    if field=='type':bad=None
    elif field=='inputs':
        data=r.inputs;data['sources'][0]['series_resistance_ohm']=25.;bad=replace(r,input_json=json.dumps(data))
    elif field in ['time','source_values']:bad=replace(r,**{field:getattr(r,field)+1.})
    else:
        bad=copy(r);object.__setattr__(bad,field,np.zeros((3,1)) if getattr(r,field).ndim>1 else np.zeros(2))
    monkeypatch.setattr(module,'coupled_mixed_source_ladder_response',lambda **kw:bad)
    with pytest.raises(ValueError,match='changed saved'):d.analyze()


def test_prior_homogeneous_schemas_and_wave_wrappers_reject_mixed_without_upgrade():
    d=document();a=arguments();a.pop('sources');voltage=ReactiveRLGCLadderDocument(source_voltages=[[0,0],[1,0],[1,0]],source_resistance=[0,37],**a)
    current=NortonReactiveRLGCLadderDocument(source_currents=[[0,0],[.02,0],[.02,0]],source_shunt_resistance=[None,37],**a)
    for old in [voltage,current]:
        assert normalize_saved(old.dumps())==old.dumps()
        with pytest.raises(ValueError):type(old).loads(d.dumps())
        with pytest.raises(ValueError):MixedSourceRLGCLadderDocument.loads(old.dumps())
    for version in [1,2]:
        with pytest.raises(ValueError):StartupPortWavesDocument(d,z_ref=[35.,45.,55.,65.],version=version)
        data=dict(schema=f'sipi.startup-port-waves/{version}',startup=d.to_dict(),z_ref_ohm=[35.,45.,55.,65.])
        with pytest.raises(ValueError):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('rankone',[False,True])
def test_zero_rankone_load_and_readonly_source_units_are_preserved(rankone):
    mat=np.array([[1.,-1.],[-1.,1.]]) if rankone else np.zeros((2,2));a=arguments(load_capacitance=mat*20e-12,load_branch_resistance=mat)
    d=MixedSourceRLGCLadderDocument(**a);r=d.analyze();assert r.to_dict()==coupled_mixed_source_ladder_response(**a).to_dict()
    for field in ['source_values','source_series_resistor_loss','source_shunt_resistor_loss','load_branch_energy']:assert not getattr(r,field).flags.writeable


def test_original_runtime_failure_is_not_partial_success():
    d=document(L=np.eye(2)*1e-300,C=np.eye(2)*1e-300,length=1e-300)
    assert normalize_saved(d.dumps())==d.dumps()
    with pytest.raises(ValueError,match='finite scales'):d.analyze()
    with pytest.raises(ValueError,match='finite scales'):execute_saved(d.dumps())
