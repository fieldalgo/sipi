# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Nested startup storage preserves underlying versions, budgets and wave output."""
from dataclasses import replace
import json

import numpy as np
import pytest
from sipi import (StartupPortWavesDocument, LosslessStartupDocument, RLGCLadderDocument,
    CoupledRLGCLadderDocument, MixedBoundaryRLGCLadderDocument,
    CapacitiveRLGCLadderDocument, ReactiveRLGCLadderDocument, startup_port_waves)
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


def document(kind='reactive',pulse=False):
    return StartupPortWavesDocument(source_document(kind,pulse),z_ref=[35.,75.] if kind in ['scalar','lossless'] else [35.,45.,55.,65.])


def forbidden(*a,**kw):pytest.fail('validation/budget reached numerical work')


def no_solve(monkeypatch):
    monkeypatch.setattr(lossless_api,'_drive',forbidden)
    for api in [scalar_api,coupled_api,mixed_api]:monkeypatch.setattr(api,'lsim',forbidden)
    monkeypatch.setattr(module,'startup_port_waves',forbidden)


@pytest.mark.parametrize('kind',['lossless','scalar','coupled','mixed','capacitive','reactive'])
def test_normalization_preserves_nested_version_without_propagation(kind,monkeypatch):
    no_solve(monkeypatch);source=source_document(kind);d=document(kind);text=d.dumps()
    assert normalize_saved(text)==text and StartupPortWavesDocument.loads(text).dumps()==text
    assert normalize_saved(source.dumps())==source.dumps()
    assert d.to_dict()['startup']==source.to_dict()
    assert 'sipi.startup-port-waves/1' in saved_schemas()


def test_nested_copies_from_object_dictionary_and_reference():
    source=source_document();z=np.array([35.,45.,55.,65.]);d=StartupPortWavesDocument(source,z_ref=z);text=d.dumps()
    source._data['load_branch_inductance_h'][0][0]=99;z[:]=99
    data=d.to_dict();loaded=StartupPortWavesDocument.from_dict(data)
    data['startup']['time_s'].clear();data['z_ref_ohm'][0]=99
    assert d.dumps()==text and loaded.dumps()==text


@pytest.mark.parametrize('kind',['lossless','scalar','coupled','mixed','capacitive','reactive'])
@pytest.mark.parametrize('pulse',[False,True])
def test_direct_nested_and_common_wave_replay(kind,pulse):
    d=document(kind,pulse);source=source_document(kind,pulse)
    expected=startup_port_waves(source.analyze(max_evaluations=121),z_ref=d.to_dict()['z_ref_ohm'])
    loaded=StartupPortWavesDocument.loads(d.dumps());actual=loaded.analyze(max_evaluations=121)
    assert actual.to_dict()==expected.to_dict()
    out=execute_saved(loaded.dumps(),max_evaluations=121)
    assert out['status']=='complete' and out['error'] is None and out['result']==expected.to_dict()
    assert out['input']==d.to_dict();json.dumps(out,allow_nan=False)


@pytest.mark.parametrize('mutate',[
    lambda d:d.update(schema='sipi.startup-port-waves/999'),lambda d:d.update(extra=1),
    lambda d:d.pop('startup'),lambda d:d.pop('z_ref_ohm'),lambda d:d.update(startup=[]),
    lambda d:d.update(startup=None),lambda d:d['startup'].update(schema=[]),
    lambda d:d['startup'].update(schema='sipi.startup-port-waves/1'),
    lambda d:d['startup'].update(schema='sipi.coupled-rlgc-startup/999'),
    lambda d:d['startup'].update(schema='sipi.transmission-line/1'),
    lambda d:d['startup'].update(extra=1),lambda d:d['startup'].pop('load_branch_inductance_h'),
    lambda d:d['startup'].update(load_branch_inductance_h=[[0,0],[0,0]]),
    lambda d:d['startup'].update(load_capacitance_f=[[1,0],[0,-1e-30]]),
    lambda d:d['startup'].update(time_s=[0.,1.,3.]),
    lambda d:d['startup'].update(cells=True),lambda d:d.update(z_ref_ohm=50.),
    lambda d:d.update(z_ref_ohm=[50.,50.]),lambda d:d.update(z_ref_ohm=[[50.,50.,50.,50.]]),
    lambda d:d.update(z_ref_ohm=[0.,50.,50.,50.]),lambda d:d.update(z_ref_ohm=[True,50.,50.,50.]),
    lambda d:d.update(z_ref_ohm=[np.inf,50.,50.,50.]),
])
def test_invalid_root_nested_or_reference_rejects_without_propagation(mutate,monkeypatch):
    data=document().to_dict();mutate(data);no_solve(monkeypatch)
    with pytest.raises((ValueError,TypeError)):StartupPortWavesDocument.from_dict(data)
    with pytest.raises((ValueError,TypeError)):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('text',['[]','null','{"schema":"x","schema":"y"}',
    '{"schema":"sipi.startup-port-waves/1","startup":{"schema":"x","schema":"y"},"z_ref_ohm":[50,50]}',
    '{"schema":"sipi.startup-port-waves/1","startup":{},"z_ref_ohm":[NaN,50]}'])
def test_strict_duplicate_nonfinite_and_nonobject_json(text):
    with pytest.raises(ValueError):StartupPortWavesDocument.loads(text)
    with pytest.raises(ValueError):normalize_saved(text)


def test_constructor_rejects_raw_or_unsupported_objects():
    for source in [object(),None,source_document().to_dict()]:
        with pytest.raises(ValueError):StartupPortWavesDocument(source,z_ref=[35.,45.,55.,65.])
    with pytest.raises(ValueError):StartupPortWavesDocument(source_document(),z_ref=[35.+0j]*4)


def test_lossless_budget_counts_actual_delay_terms_not_time_rows(monkeypatch):
    source=LosslessStartupDocument(np.linspace(0,10e-9,1001),source_times=[0.,1e-9],source_voltages=[0.,1.],
        z0_ohm=50.,delay_s=1e-9,source_resistance=50.,load_resistance=None,max_terms=100)
    d=StartupPortWavesDocument(source,z_ref=[50.,50.]);out=execute_saved(d.dumps(),max_evaluations=2)
    assert len(out['result']['time_s'])==1001 and out['input']['startup']['max_terms']==100
    data=source.to_dict();data['source_resistance_ohm']=25.;long=LosslessStartupDocument.from_dict(data)
    assert long.required_terms>2
    d=StartupPortWavesDocument(long,z_ref=[50.,50.]);no_solve(monkeypatch)
    with pytest.raises(ValueError,match='terms exceed'):d.analyze(max_evaluations=2)
    with pytest.raises(ValueError,match='terms exceed'):execute_saved(d.dumps(),max_evaluations=2)


def test_finite_budget_counts_rows_not_cells_or_port_waves(monkeypatch):
    data=source_document().to_dict();data['time_s']=[0.,1e-9,2e-9];data['source_voltages_v']=[[0.,0.],[1.,0.],[1.,0.]];data['cells']=128
    source=ReactiveRLGCLadderDocument.from_dict(data);d=StartupPortWavesDocument(source,z_ref=[35.,45.,55.,65.])
    out=execute_saved(d.dumps(),max_evaluations=3)
    assert len(out['result']['time_s'])==3 and out['input']['startup']['cells']==128
    no_solve(monkeypatch)
    with pytest.raises(ValueError,match='time samples exceed'):d.analyze(max_evaluations=2)
    with pytest.raises(ValueError,match='time samples exceed'):execute_saved(d.dumps(),max_evaluations=2)


def test_original_byte_diagnostic_and_integer_budget_guards(monkeypatch):
    d=document();no_solve(monkeypatch)
    with pytest.raises(ValueError,match='max_input_bytes'):execute_saved(d.dumps(),max_input_bytes=2)
    with pytest.raises(ValueError,match='diagnostics'):execute_saved(d.dumps(),diagnostics=['modes'])
    for budget in [True,1,10001,3.]:
        with pytest.raises((ValueError,TypeError)):d.analyze(max_evaluations=budget)


@pytest.mark.parametrize('change',['type','time','voltage','current','z_ref','port_names','source_kind','incident','reflected','port_power'])
def test_diagnostic_result_must_preserve_source_and_reference_identity(change,monkeypatch):
    d=document();r=d.analyze()
    if change=='type':bad=None
    elif change=='port_names':bad=replace(r,port_names=tuple(reversed(r.port_names)))
    elif change=='source_kind':bad=replace(r,source_kind='other')
    elif change=='time':bad=replace(r,time=r.time+1.)
    elif change=='z_ref':bad=replace(r,z_ref=r.z_ref+1.)
    elif change in ['voltage','current']:bad=replace(r,**{change:getattr(r,change)+1.})
    else:bad=replace(r,**{change:np.zeros((121,2))})
    monkeypatch.setattr(module,'startup_port_waves',lambda *a,**k:bad)
    with pytest.raises(ValueError,match='identity'):d.analyze()


def test_original_propagation_and_wave_cancellation_failures_remain_exceptions():
    data=source_document().to_dict();data['L_h_per_m']=(np.eye(2)*1e-300).tolist();data['C_f_per_m']=(np.eye(2)*1e-300).tolist();data['length_m']=1e-300
    bad=StartupPortWavesDocument(ReactiveRLGCLadderDocument.from_dict(data),z_ref=[35.,45.,55.,65.])
    assert normalize_saved(bad.dumps())==bad.dumps()
    with pytest.raises(ValueError,match='finite scales'):bad.analyze()
    with pytest.raises(ValueError,match='finite scales'):execute_saved(bad.dumps())
    bad=StartupPortWavesDocument(source_document('lossless'),z_ref=[1e-30,1e-30])
    assert normalize_saved(bad.dumps())==bad.dumps()
    with pytest.raises(ValueError,match='reconstruction'):bad.analyze()
    with pytest.raises(ValueError,match='reconstruction'):execute_saved(bad.dumps())
