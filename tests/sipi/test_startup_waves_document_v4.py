# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit saved wave v4 adds scalar Debye while preserving prior nested contracts."""
from dataclasses import replace
import json
import numpy as np
import pytest
from sipi import StartupPortWavesDocument, DebyeRLGCLadderDocument, LosslessStartupDocument, startup_port_waves
from sipi.execution import execute_saved,normalize_saved,saved_schemas
from test_startup_waves_document_v3 import source as previous_source, source_document
import sipi.startup_waves_document as module
import sipi.debye_startup as api


def source(kind='debye',pulse=False):
    if kind=='mixed_boundary':return source_document('mixed',pulse)
    if kind!='debye':return previous_source(kind,pulse)
    t=np.linspace(0,12e-9,121);d=np.minimum(t/2e-9,1.)
    if pulse:d-=np.minimum(np.maximum(t-5e-9,0)/2e-9,1.)
    return DebyeRLGCLadderDocument(t,d,R=20.,L=500e-9,G=.002,C_inf=200e-12,
        delta_C=[150e-12,50e-12],relaxation_hz=[1e9,1e8],length=.1,cells=16,
        source_resistance=25.,load_resistance=100.)


def document(kind='debye',pulse=False):
    return StartupPortWavesDocument(source(kind,pulse),z_ref=[35.,75.] if kind in ['debye','scalar','lossless'] else [35.,45.,55.,65.],version=4)


def forbidden(*a,**kw):pytest.fail('validation or budget reached propagation')


@pytest.mark.parametrize('kind',['lossless','scalar','coupled','mixed_boundary','capacitive','reactive','norton','mixed','debye'])
@pytest.mark.parametrize('pulse',[False,True])
def test_nine_nested_schemas_and_prior_versions_replay_exactly(kind,pulse):
    nested=source(kind,pulse);d=document(kind,pulse);text=d.dumps()
    assert normalize_saved(text)==text and StartupPortWavesDocument.loads(text).dumps()==text
    assert d.to_dict()['schema']=='sipi.startup-port-waves/4' and d.to_dict()['startup']==nested.to_dict()
    expected=startup_port_waves(nested.analyze(max_evaluations=121),z_ref=d.to_dict()['z_ref_ohm']).to_dict()
    assert d.analyze(max_evaluations=121).to_dict()==expected
    out=execute_saved(text,max_evaluations=121);assert out['status']=='complete' and out['error'] is None and out['input']==d.to_dict() and out['result']==expected
    versions=[] if kind=='debye' else [3] if kind=='mixed' else [2,3] if kind=='norton' else [1,2,3]
    for version in versions:
        old=StartupPortWavesDocument(nested,z_ref=d.to_dict()['z_ref_ohm'],version=version)
        assert old.to_dict()['schema']==f'sipi.startup-port-waves/{version}' and normalize_saved(old.dumps())==old.dumps()
        assert old.analyze(max_evaluations=121).to_dict()==expected
    if kind=='debye':
        r=nested.analyze(max_evaluations=121)
        np.testing.assert_allclose(np.array(expected['port_power_w']).sum(axis=1),r.total_energy_rate+r.series_loss+r.shunt_loss+r.relaxation_loss,rtol=1e-10,atol=1e-12)
    json.dumps(out,allow_nan=False)


def test_no_propagation_canonical_copies_and_unchanged_default(monkeypatch):
    monkeypatch.setattr(api,'lsim',forbidden);monkeypatch.setattr(module,'startup_port_waves',forbidden)
    nested=source();z=np.array([35.,75.]);d=StartupPortWavesDocument(nested,z_ref=z,version=4);text=d.dumps()
    assert normalize_saved(text)==text and 'sipi.startup-port-waves/4' in saved_schemas()
    nested._data['delta_C_f_per_m'].clear();z[:]=9;data=d.to_dict();loaded=StartupPortWavesDocument.from_dict(data);data['startup']['relaxation_hz'].clear()
    assert loaded.dumps()==text and d.dumps()==text
    assert StartupPortWavesDocument(source('scalar'),z_ref=[50.,50.]).to_dict()['schema']=='sipi.startup-port-waves/1'


@pytest.mark.parametrize('version',[True,False,0,999,4.,'4',None])
def test_explicit_integer_version_required(version):
    with pytest.raises((ValueError,TypeError)):StartupPortWavesDocument(source(),z_ref=[35.,75.],version=version)


@pytest.mark.parametrize('version',[1,2,3])
def test_old_versions_reject_debye_without_upgrade(version):
    with pytest.raises(ValueError):StartupPortWavesDocument(source(),z_ref=[35.,75.],version=version)
    d=document().to_dict();d['schema']=f'sipi.startup-port-waves/{version}'
    with pytest.raises(ValueError):normalize_saved(json.dumps(d))


@pytest.mark.parametrize('mutate',[
    lambda d:d.update(schema=[]),lambda d:d.update(schema='sipi.startup-port-waves/999'),
    lambda d:d.update(extra=1),lambda d:d.pop('startup'),lambda d:d.pop('z_ref_ohm'),
    lambda d:d.update(startup=None),lambda d:d['startup'].update(schema=[]),
    lambda d:d['startup'].update(schema='sipi.startup-port-waves/1'),
    lambda d:d['startup'].update(schema='sipi.startup-port-waves/2'),
    lambda d:d['startup'].update(schema='sipi.startup-port-waves/3'),
    lambda d:d['startup'].update(schema='sipi.startup-port-waves/4'),
    lambda d:d['startup'].update(schema='sipi.debye-rlgc-startup/2'),
    lambda d:d['startup'].update(C_f_per_m=200e-12),lambda d:d['startup'].update(delta_C=[150e-12,50e-12]),
    lambda d:d['startup'].update(delta_C_f_per_m=[-1.,0.]),lambda d:d['startup'].update(relaxation_hz=[0.,1e9]),
    lambda d:d.update(z_ref_ohm=[35.,45.,55.,65.]),lambda d:d.update(z_ref_ohm=[True,75.]),
])
def test_recursion_wrong_units_and_shapes_reject_before_propagation(mutate,monkeypatch):
    data=document().to_dict();mutate(data);monkeypatch.setattr(api,'lsim',forbidden)
    with pytest.raises((ValueError,TypeError)):StartupPortWavesDocument.from_dict(data)
    with pytest.raises((ValueError,TypeError)):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('rs,rl',[(0.,0.),(0.,None),(0.,100.),(25.,0.),(25.,None),(25.,100.)])
@pytest.mark.parametrize('strengths,poles',[([0.],[1e9]),([150e-12],[1e9]),([25e-12,75e-12,25e-12,75e-12],[1e8,1e9,1e8,1e9])])
def test_debye_boundaries_and_declared_poles_preserved(rs,rl,strengths,poles):
    data=source().to_dict();data.update(source_resistance_ohm=rs,load_resistance_ohm=rl,delta_C_f_per_m=strengths,relaxation_hz=poles)
    nested=DebyeRLGCLadderDocument.from_dict(data);d=StartupPortWavesDocument(nested,z_ref=[35.,75.],version=4)
    expected=startup_port_waves(nested.analyze(max_evaluations=121),z_ref=[35.,75.]).to_dict()
    out=execute_saved(d.dumps(),max_evaluations=121);assert out['result']==expected and out['input']['startup']==data


def test_actual_time_budget_is_separate_from_cells_poles_and_lossless_terms(monkeypatch):
    data=source().to_dict();data.update(time_s=[0.,1e-9,2e-9],source_voltages_v=[0.,1.,1.],cells=128)
    d=StartupPortWavesDocument(DebyeRLGCLadderDocument.from_dict(data),z_ref=[35.,75.],version=4)
    out=execute_saved(d.dumps(),max_evaluations=3);assert out['input']['startup']['cells']==128 and len(out['result']['time_s'])==3
    lossless=LosslessStartupDocument(np.linspace(0,10e-9,1001),source_times=[0.,1e-9],source_voltages=[0.,1.],z0_ohm=50.,delay_s=1e-9,source_resistance=50.,load_resistance=None,max_terms=100)
    old=StartupPortWavesDocument(lossless,z_ref=[50.,50.],version=4);assert len(execute_saved(old.dumps(),max_evaluations=2)['result']['time_s'])==1001
    monkeypatch.setattr(api,'lsim',forbidden)
    with pytest.raises(ValueError,match='time samples exceed'):execute_saved(d.dumps(),max_evaluations=2)
    with pytest.raises(ValueError,match='max_input_bytes'):execute_saved(d.dumps(),max_input_bytes=2)
    with pytest.raises(ValueError,match='diagnostics'):execute_saved(d.dumps(),diagnostics=['modes'])


@pytest.mark.parametrize('field',['type','time','voltage','current','z_ref','port_names','source_kind','incident','reflected','port_power'])
def test_output_identity_guards(field,monkeypatch):
    d=document();r=d.analyze()
    if field=='type':bad=None
    elif field=='port_names':bad=replace(r,port_names=tuple(reversed(r.port_names)))
    elif field=='source_kind':bad=replace(r,source_kind='other')
    elif field in ['time','voltage','current','z_ref']:bad=replace(r,**{field:getattr(r,field)+1.})
    else:bad=replace(r,**{field:np.zeros((121,4))})
    monkeypatch.setattr(module,'startup_port_waves',lambda *a,**kw:bad)
    with pytest.raises(ValueError,match='identity'):d.analyze()


def test_physical_and_cancellation_failures_propagate():
    data=source().to_dict();data.update(L_h_per_m=1e-300,C_inf_f_per_m=1e-300,length_m=1e-300)
    d=StartupPortWavesDocument(DebyeRLGCLadderDocument.from_dict(data),z_ref=[35.,75.],version=4);assert normalize_saved(d.dumps())==d.dumps()
    with pytest.raises(ValueError,match='finite scales'):execute_saved(d.dumps())
    d=StartupPortWavesDocument(source(),z_ref=[1e-30,1e-30],version=4)
    with pytest.raises(ValueError,match='reconstruction'):execute_saved(d.dumps(),max_evaluations=121)
