# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit saved wave v6 adds PSD coupled Debye while preserving prior nested contracts."""
from dataclasses import replace
import json
import numpy as np
import pytest
from sipi import StartupPortWavesDocument, PSDCoupledDebyeRLGCLadderDocument, LosslessStartupDocument, startup_port_waves
from sipi.execution import execute_saved,normalize_saved,saved_schemas
from test_startup_waves_document_v5 import source as previous_source
from test_psd_debye_startup_waves import arguments
import sipi.startup_waves_document as module
import sipi.psd_debye_startup as api


def source(kind='psd_debye',pulse=False):
    if kind!='psd_debye':return previous_source(kind,pulse)
    return PSDCoupledDebyeRLGCLadderDocument(**arguments('noncommuting',pulse))


def document(kind='psd_debye',pulse=False):
    return StartupPortWavesDocument(source(kind,pulse),z_ref=[35.,75.] if kind in ['debye','scalar','lossless'] else [35.,45.,55.,65.],version=6)


def forbidden(*a,**kw):pytest.fail('validation or budget reached propagation')


@pytest.mark.parametrize('kind',['lossless','scalar','coupled','mixed_boundary','capacitive','reactive','norton','mixed','debye','coupled_debye','psd_debye'])
@pytest.mark.parametrize('pulse',[False,True])
def test_eleven_nested_schemas_and_prior_versions_replay_exactly(kind,pulse):
    nested=source(kind,pulse);d=document(kind,pulse);text=d.dumps()
    assert normalize_saved(text)==text and StartupPortWavesDocument.loads(text).dumps()==text
    assert d.to_dict()['schema']=='sipi.startup-port-waves/6' and d.to_dict()['startup']==nested.to_dict()
    expected=startup_port_waves(nested.analyze(max_evaluations=121),z_ref=d.to_dict()['z_ref_ohm']).to_dict()
    assert d.analyze(max_evaluations=121).to_dict()==expected
    out=execute_saved(text,max_evaluations=121);assert out['status']=='complete' and out['error'] is None and out['input']==d.to_dict() and out['result']==expected
    versions=[] if kind=='psd_debye' else [5] if kind=='coupled_debye' else [4,5] if kind=='debye' else [3,4,5] if kind=='mixed' else [2,3,4,5] if kind=='norton' else [1,2,3,4,5]
    for version in versions:
        old=StartupPortWavesDocument(nested,z_ref=d.to_dict()['z_ref_ohm'],version=version)
        assert old.to_dict()['schema']==f'sipi.startup-port-waves/{version}' and normalize_saved(old.dumps())==old.dumps()
        assert old.analyze(max_evaluations=121).to_dict()==expected
    if kind=='psd_debye':
        r=nested.analyze(max_evaluations=121)
        np.testing.assert_allclose(np.array(expected['port_power_w']).sum(axis=1),r.total_energy_rate+r.series_loss+r.shunt_loss+r.relaxation_loss,rtol=1e-10,atol=1e-12)
    json.dumps(out,allow_nan=False)


def test_no_propagation_canonical_copies_and_unchanged_default(monkeypatch):
    monkeypatch.setattr(api,'lsim',forbidden);monkeypatch.setattr(module,'startup_port_waves',forbidden)
    nested=source();z=np.array([35.,45.,55.,65.]);d=StartupPortWavesDocument(nested,z_ref=z,version=6);text=d.dumps()
    assert normalize_saved(text)==text and 'sipi.startup-port-waves/6' in saved_schemas()
    nested._data['delta_C_f_per_m'].clear();z[:]=9;data=d.to_dict();loaded=StartupPortWavesDocument.from_dict(data);data['startup']['relaxation_hz'].clear()
    assert loaded.dumps()==text and d.dumps()==text
    assert StartupPortWavesDocument(source('scalar'),z_ref=[50.,50.]).to_dict()['schema']=='sipi.startup-port-waves/1'


@pytest.mark.parametrize('version',[True,False,0,999,6.,'6',None])
def test_explicit_integer_version_required(version):
    with pytest.raises((ValueError,TypeError)):StartupPortWavesDocument(source(),z_ref=[35.,45.,55.,65.],version=version)


@pytest.mark.parametrize('version',[1,2,3,4,5])
def test_old_versions_reject_psd_debye_without_upgrade(version):
    with pytest.raises(ValueError):StartupPortWavesDocument(source(),z_ref=[35.,45.,55.,65.],version=version)
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
    lambda d:d['startup'].update(schema='sipi.startup-port-waves/5'),
    lambda d:d['startup'].update(schema='sipi.startup-port-waves/6'),
    lambda d:d['startup'].update(schema='sipi.psd-coupled-debye-rlgc-startup/2'),
    lambda d:d['startup'].update(C_f_per_m=200e-12),lambda d:d['startup'].update(delta_C=[150e-12,50e-12]),
    lambda d:d['startup'].update(delta_C_f_per_m=[-1.,0.]),lambda d:d['startup'].update(relaxation_hz=[0.,1e9]),
    lambda d:d.update(z_ref_ohm=[35.,75.]),lambda d:d.update(z_ref_ohm=[True,75.]),
])
def test_recursion_wrong_units_and_shapes_reject_before_propagation(mutate,monkeypatch):
    data=document().to_dict();mutate(data);monkeypatch.setattr(api,'lsim',forbidden)
    with pytest.raises((ValueError,TypeError)):StartupPortWavesDocument.from_dict(data)
    with pytest.raises((ValueError,TypeError)):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('kind',['diagonal','exchange','noncommuting'])
@pytest.mark.parametrize('case',['single','zero','repeated','reversed'])
def test_matrix_inputs_and_declared_poles_preserved(kind,case):
    a=arguments(kind)
    if case=='single':a['delta_C']=a['delta_C'][:1];a['relaxation_hz']=a['relaxation_hz'][:1]
    if case=='zero':a['delta_C'][:]=0
    if case=='repeated':a['relaxation_hz'][:]=1e9
    if case=='reversed':a['delta_C']=a['delta_C'][::-1];a['relaxation_hz']=a['relaxation_hz'][::-1]
    nested=PSDCoupledDebyeRLGCLadderDocument(**a);d=StartupPortWavesDocument(nested,z_ref=[35.,45.,55.,65.],version=6)
    expected=startup_port_waves(nested.analyze(max_evaluations=121),z_ref=[35.,45.,55.,65.]).to_dict()
    out=execute_saved(d.dumps(),max_evaluations=121);assert out['result']==expected and out['input']['startup']==nested.to_dict()


def test_actual_time_budget_is_separate_from_cells_poles_and_lossless_terms(monkeypatch):
    data=source().to_dict();data.update(time_s=[0.,1e-9,2e-9],source_voltages_v=[[0.,0.],[1.,-.4],[1.,-.4]],cells=128)
    d=StartupPortWavesDocument(PSDCoupledDebyeRLGCLadderDocument.from_dict(data),z_ref=[35.,45.,55.,65.],version=6)
    out=execute_saved(d.dumps(),max_evaluations=3);assert out['input']['startup']['cells']==128 and len(out['result']['time_s'])==3
    lossless=LosslessStartupDocument(np.linspace(0,10e-9,1001),source_times=[0.,1e-9],source_voltages=[0.,1.],z0_ohm=50.,delay_s=1e-9,source_resistance=50.,load_resistance=None,max_terms=100)
    old=StartupPortWavesDocument(lossless,z_ref=[50.,50.],version=6);assert len(execute_saved(old.dumps(),max_evaluations=2)['result']['time_s'])==1001
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
    else:bad=replace(r,**{field:np.zeros((121,2))})
    monkeypatch.setattr(module,'startup_port_waves',lambda *a,**kw:bad)
    with pytest.raises(ValueError,match='identity'):d.analyze()


def test_physical_and_cancellation_failures_propagate():
    data=source().to_dict();data.update(L_h_per_m=(np.eye(2)*1e-300).tolist(),C_inf_f_per_m=(np.eye(2)*1e-300).tolist(),length_m=1e-300)
    d=StartupPortWavesDocument(PSDCoupledDebyeRLGCLadderDocument.from_dict(data),z_ref=[35.,45.,55.,65.],version=6);assert normalize_saved(d.dumps())==d.dumps()
    with pytest.raises(ValueError,match='finite scales'):execute_saved(d.dumps())
    d=StartupPortWavesDocument(source(),z_ref=[1e-30]*4,version=6)
    with pytest.raises(ValueError,match='reconstruction'):execute_saved(d.dumps(),max_evaluations=121)


@pytest.mark.parametrize('tiny',[0.,1e-13,1e-20])
def test_near_singular_null_mode_saved_waves_preserve_original_input(tiny):
    a=arguments('diagonal');a['delta_C']=np.array([np.diag([150e-12,150e-12*tiny])]);a['relaxation_hz']=[1e9];a['source_voltages'][:,0]=0
    nested=PSDCoupledDebyeRLGCLadderDocument(**a);d=StartupPortWavesDocument(nested,z_ref=[35.,45.,55.,65.],version=6)
    expected=startup_port_waves(nested.analyze(max_evaluations=121),z_ref=[35.,45.,55.,65.]).to_dict();out=execute_saved(d.dumps(),max_evaluations=121)
    assert out['result']==expected and out['input']['startup']['delta_C_f_per_m']==a['delta_C'].tolist()
