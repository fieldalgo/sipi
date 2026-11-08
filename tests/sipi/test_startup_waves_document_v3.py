# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Nested startup storage preserves underlying versions, budgets and wave output."""
from dataclasses import replace
import json

import numpy as np
import pytest
from sipi import (StartupPortWavesDocument, LosslessStartupDocument, RLGCLadderDocument,
    CoupledRLGCLadderDocument, MixedBoundaryRLGCLadderDocument,
    CapacitiveRLGCLadderDocument, ReactiveRLGCLadderDocument, NortonReactiveRLGCLadderDocument, MixedSourceRLGCLadderDocument, startup_port_waves)
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




def source(kind='mixed',pulse=False):
    if kind not in ['norton','mixed']:return source_document(kind,pulse)
    data=source_document('reactive',pulse).to_dict();voltage=np.array(data.pop('source_voltages_v'));data.pop('source_resistance_ohm')
    if kind=='norton':
        data.update(schema='sipi.norton-rlgc-startup/1',source_currents_a=(voltage*.02).tolist(),source_shunt_resistance_ohm=[None,37.])
        return NortonReactiveRLGCLadderDocument.from_dict(data)
    data.update(schema='sipi.mixed-rlgc-startup/1',sources=[dict(kind='voltage',voltage_v=voltage[:,0].tolist(),series_resistance_ohm=0.),dict(kind='current',current_a=(voltage[:,1]*.02).tolist(),shunt_resistance_ohm=None)])
    return MixedSourceRLGCLadderDocument.from_dict(data)


def document(kind='mixed',pulse=False):
    return StartupPortWavesDocument(source(kind,pulse),z_ref=[35.,75.] if kind in ['scalar','lossless'] else [35.,45.,55.,65.],version=3)


def forbidden(*a,**kw):pytest.fail('parsing or budget reached numerical propagation')


@pytest.mark.parametrize('kind',['lossless','scalar','coupled','mixed_boundary','capacitive','reactive','norton','mixed'])
@pytest.mark.parametrize('pulse',[False,True])
def test_v3_eight_nested_schemas_preserve_physical_and_prior_wave_versions(kind,pulse):
    # Original mixed-boundary voltage document and typed mixed sources are distinct.
    if kind=='mixed_boundary':
        nested=source_document('mixed',pulse);d=StartupPortWavesDocument(nested,z_ref=[35.,45.,55.,65.],version=3)
    else:nested=source(kind,pulse);d=document(kind,pulse)
    text=d.dumps();assert normalize_saved(text)==text and StartupPortWavesDocument.loads(text).dumps()==text
    assert d.to_dict()['schema']=='sipi.startup-port-waves/3' and d.to_dict()['startup']==nested.to_dict()
    expected=startup_port_waves(nested.analyze(max_evaluations=121),z_ref=d.to_dict()['z_ref_ohm']).to_dict()
    assert d.analyze(max_evaluations=121).to_dict()==expected
    out=execute_saved(text,max_evaluations=121);assert out['status']=='complete' and out['error'] is None and out['input']==d.to_dict() and out['result']==expected
    versions=[] if kind=='mixed' else [2] if kind=='norton' else [1,2]
    for version in versions:
        old=StartupPortWavesDocument(nested,z_ref=d.to_dict()['z_ref_ohm'],version=version)
        assert old.to_dict()['schema']==f'sipi.startup-port-waves/{version}' and normalize_saved(old.dumps())==old.dumps()
        assert old.analyze(max_evaluations=121).to_dict()==expected
    if kind=='mixed':
        r=nested.analyze(max_evaluations=121)
        np.testing.assert_allclose(np.array(expected['port_power_w'])[:,:2].sum(axis=1),r.source_power-r.source_series_resistor_loss-r.source_shunt_resistor_loss,rtol=1e-10,atol=1e-12)
    json.dumps(out,allow_nan=False)


def test_v3_no_propagation_parse_and_deep_copies(monkeypatch):
    monkeypatch.setattr(mixed_api,'lsim',forbidden);monkeypatch.setattr(module,'startup_port_waves',forbidden)
    nested=source();z=np.array([35.,45.,55.,65.]);d=StartupPortWavesDocument(nested,z_ref=z,version=3);text=d.dumps()
    assert normalize_saved(text)==text and 'sipi.startup-port-waves/3' in saved_schemas()
    nested._data['sources'][0]['voltage_v'].clear();z[:]=99
    data=d.to_dict();loaded=StartupPortWavesDocument.from_dict(data);data['startup']['sources'][1]['current_a'].clear()
    assert d.dumps()==text and loaded.dumps()==text


@pytest.mark.parametrize('version',[True,False,0,4,3.,'3',None])
def test_constructor_requires_explicit_supported_integer_version(version):
    with pytest.raises((ValueError,TypeError)):StartupPortWavesDocument(source(),z_ref=[35.,45.,55.,65.],version=version)


def test_default_v1_and_v2_reject_mixed_without_automatic_upgrade():
    for kwargs in [{},{'version':1},{'version':2}]:
        with pytest.raises(ValueError):StartupPortWavesDocument(source(),z_ref=[35.,45.,55.,65.],**kwargs)
    for version in [1,2]:
        data=document().to_dict();data['schema']=f'sipi.startup-port-waves/{version}'
        with pytest.raises(ValueError,match='nested startup'):StartupPortWavesDocument.from_dict(data)
        with pytest.raises(ValueError):normalize_saved(json.dumps(data))
    with pytest.raises(ValueError):StartupPortWavesDocument(source('norton'),z_ref=[35.,45.,55.,65.],version=1)


@pytest.mark.parametrize('mutate',[
    lambda d:d.update(schema=[]),lambda d:d.update(schema='sipi.startup-port-waves/999'),
    lambda d:d.update(extra=1),lambda d:d.pop('startup'),lambda d:d.pop('z_ref_ohm'),
    lambda d:d.update(startup=None),lambda d:d['startup'].update(schema=[]),
    lambda d:d['startup'].update(schema='sipi.startup-port-waves/1'),
    lambda d:d['startup'].update(schema='sipi.startup-port-waves/2'),
    lambda d:d['startup'].update(schema='sipi.startup-port-waves/3'),
    lambda d:d['startup'].update(schema='sipi.mixed-rlgc-startup/2'),
    lambda d:d['startup']['sources'][0].update(current_a=[0.]*121),
    lambda d:d['startup']['sources'][1].update(series_resistance_ohm=25.),
    lambda d:d['startup']['sources'][0].pop('voltage_v'),
    lambda d:d['startup'].update(source_voltages_v=[[0,0]]*121),
    lambda d:d.update(z_ref_ohm=[35.,45.]),lambda d:d.update(z_ref_ohm=[True,45.,55.,65.]),
])
def test_v3_rejects_recursion_wrong_units_or_shapes_without_propagation(mutate,monkeypatch):
    data=document().to_dict();mutate(data);monkeypatch.setattr(mixed_api,'lsim',forbidden)
    with pytest.raises((ValueError,TypeError)):StartupPortWavesDocument.from_dict(data)
    with pytest.raises((ValueError,TypeError)):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('kinds,resistance,load',[
    (['voltage','current'],[0.,None],[91.,None]),(['current','voltage'],[None,0.],[None,0.]),
    (['voltage','current'],[25.,37.],[91.,113.]),(['current','voltage'],[37.,25.],[91.,113.]),
    (['voltage','current'],[0.,0.],[0.,None]),(['current','voltage'],[0.,0.],[None,0.]),
    (['voltage','voltage'],[0.,37.],[91.,None]),(['current','current'],[None,37.],[91.,None]),
])
def test_v3_replays_mixed_boundaries_and_homogeneous_kind_limits(kinds,resistance,load):
    data=source().to_dict();t=np.array(data['time_s']);drive=np.column_stack((np.minimum(t/2e-9,1.),-.4*np.minimum(t/3e-9,1.)))
    data['sources']=[dict(kind=k,**{('voltage_v' if k=='voltage' else 'current_a'):(drive[:,j]*(1 if k=='voltage' else .02)).tolist(),('series_resistance_ohm' if k=='voltage' else 'shunt_resistance_ohm'):resistance[j]}) for j,k in enumerate(kinds)]
    data['load_resistance_ohm']=load;nested=MixedSourceRLGCLadderDocument.from_dict(data);d=StartupPortWavesDocument(nested,z_ref=[35.,45.,55.,65.],version=3)
    expected=startup_port_waves(nested.analyze(max_evaluations=121),z_ref=[35.,45.,55.,65.]).to_dict()
    assert execute_saved(d.dumps(),max_evaluations=121)['result']==expected


def test_v3_delegates_lossless_delay_terms_and_mixed_actual_time_rows(monkeypatch):
    data=source().to_dict();data.update(time_s=[0.,1e-9,2e-9],cells=128)
    data['sources'][0]['voltage_v']=[0.,1.,1.];data['sources'][1]['current_a']=[0.,.02,.02]
    d=StartupPortWavesDocument(MixedSourceRLGCLadderDocument.from_dict(data),z_ref=[35.,45.,55.,65.],version=3)
    assert execute_saved(d.dumps(),max_evaluations=3)['input']['startup']['cells']==128
    lossless=LosslessStartupDocument(np.linspace(0,10e-9,1001),source_times=[0.,1e-9],source_voltages=[0.,1.],z0_ohm=50.,delay_s=1e-9,source_resistance=50.,load_resistance=None,max_terms=100)
    dloss=StartupPortWavesDocument(lossless,z_ref=[50.,50.],version=3)
    out=execute_saved(dloss.dumps(),max_evaluations=2);assert len(out['result']['time_s'])==1001 and out['input']['startup']['max_terms']==100
    monkeypatch.setattr(mixed_api,'lsim',forbidden)
    with pytest.raises(ValueError,match='time samples exceed'):execute_saved(d.dumps(),max_evaluations=2)
    with pytest.raises(ValueError,match='max_input_bytes'):execute_saved(d.dumps(),max_input_bytes=2)
    with pytest.raises(ValueError,match='diagnostics'):execute_saved(d.dumps(),diagnostics=['modes'])


@pytest.mark.parametrize('field',['type','time','voltage','current','z_ref','port_names','source_kind','incident','reflected','port_power'])
def test_v3_output_identity_guards(field,monkeypatch):
    d=document();r=d.analyze()
    if field=='type':bad=None
    elif field=='port_names':bad=replace(r,port_names=tuple(reversed(r.port_names)))
    elif field=='source_kind':bad=replace(r,source_kind='other')
    elif field in ['time','voltage','current','z_ref']:bad=replace(r,**{field:getattr(r,field)+1.})
    else:bad=replace(r,**{field:np.zeros((121,2))})
    monkeypatch.setattr(module,'startup_port_waves',lambda *a,**kw:bad)
    with pytest.raises(ValueError,match='identity'):d.analyze()


def test_v3_retains_physical_and_wave_cancellation_exceptions():
    data=source().to_dict();data.update(L_h_per_m=(np.eye(2)*1e-300).tolist(),C_f_per_m=(np.eye(2)*1e-300).tolist(),length_m=1e-300)
    d=StartupPortWavesDocument(MixedSourceRLGCLadderDocument.from_dict(data),z_ref=[35.,45.,55.,65.],version=3)
    assert normalize_saved(d.dumps())==d.dumps()
    with pytest.raises(ValueError,match='finite scales'):execute_saved(d.dumps())
    d=StartupPortWavesDocument(source_document('lossless'),z_ref=[1e-30]*2,version=3)
    with pytest.raises(ValueError,match='reconstruction'):execute_saved(d.dumps(),max_evaluations=121)
