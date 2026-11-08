# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Port-wave direction, independent phasors, power and numerical contracts."""
from dataclasses import replace
import importlib.metadata as metadata
import json

import numpy as np
import pytest
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import (startup_port_waves, lossless_line_response, rlgc_ladder_response,
    coupled_rlgc_ladder_response, coupled_boundary_ladder_response,
    coupled_capacitive_ladder_response, coupled_reactive_ladder_response)


def lossless(load=100.,source=50.,ramp=False):
    t=np.linspace(0,8e-9,801)
    return lossless_line_response(t,source_times=[0.,1e-9],source_voltages=[0.,1.] if ramp else [1.,1.],
        z0_ohm=50.,delay_s=1e-9,source_resistance=source,load_resistance=load,max_terms=100)


def checks(r):
    assert max(r.voltage_reconstruction_relative_error,r.current_reconstruction_relative_error,r.power_balance_relative_error)<=1e-10
    root=np.sqrt(r.z_ref)
    np.testing.assert_allclose(root*(r.incident+r.reflected),r.voltage,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose((r.incident-r.reflected)/root,r.current,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(r.incident**2-r.reflected**2,r.port_power,rtol=1e-10,atol=1e-12)


@pytest.mark.parametrize('load,gamma',[(50.,0.),(100.,1/3),(0.,-1.),(None,1.)])
@pytest.mark.parametrize('ramp',[False,True])
def test_matched_source_independent_delayed_reflections_and_far_direction(load,gamma,ramp):
    response=lossless(load,ramp=ramp);r=startup_port_waves(response,z_ref=[50.,50.]);t=response.time
    def shifted(delay):
        x=t-delay
        return np.where(x>=0,np.minimum(np.maximum(x/1e-9,0),1.) if ramp else 1.,0.)
    gain=.5/np.sqrt(50.)
    expected_a=np.column_stack((gain*shifted(0),gamma*gain*shifted(1e-9)))
    expected_b=np.column_stack((gamma*gain*shifted(2e-9),gain*shifted(1e-9)))
    np.testing.assert_allclose(r.incident,expected_a,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(r.reflected,expected_b,rtol=1e-10,atol=1e-12)
    # Into-line currents reverse the forward/backward labeling at the far port.
    np.testing.assert_allclose(r.incident[:,0]*np.sqrt(50),response.forward_voltage[:,0],rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(r.incident[:,1]*np.sqrt(50),response.backward_voltage[:,1],rtol=1e-10,atol=1e-12)
    checks(r)


def test_unmatched_source_independent_finite_reflection_series():
    response=lossless(100.,25.,True);t=response.time;gs=-1/3;gl=1/3;gain=2/3/np.sqrt(50)
    def ramp(delay):return np.minimum(np.maximum((t-delay)/1e-9,0),1.)
    near_a=sum(gain*(gs*gl)**k*ramp(2*k*1e-9) for k in range(5))
    near_b=sum(gain*gl*(gs*gl)**k*ramp((2*k+2)*1e-9) for k in range(4))
    far_b=sum(gain*(gs*gl)**k*ramp((2*k+1)*1e-9) for k in range(4));far_a=gl*far_b
    r=startup_port_waves(response,z_ref=[50.,50.]);checks(r)
    np.testing.assert_allclose(r.incident,np.column_stack((near_a,far_a)),rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(r.reflected,np.column_stack((near_b,far_b)),rtol=1e-10,atol=1e-12)


def ladder(kind):
    t=np.linspace(0,12e-9,121);drive=np.minimum(t/2e-9,1.)
    if kind=='scalar':return rlgc_ladder_response(t,drive,R=20.,L=500e-9,G=.002,C=220e-12,
        length=.1,cells=8,source_resistance=25.,load_resistance=100.)
    kw=dict(R=[[25.,2.],[2.,17.]],L=np.array([[510.,70.],[70.,430.]])*1e-9,
        G=[[.003,-.0002],[-.0002,.0015]],C=np.array([[230.,-30.],[-30.,190.]])*1e-12,
        length=.1,cells=8,source_resistance=[23.,37.],load_resistance=[91.,113.])
    f={'coupled':coupled_rlgc_ladder_response,'mixed':coupled_boundary_ladder_response,
       'capacitive':coupled_capacitive_ladder_response,'reactive':coupled_reactive_ladder_response}[kind]
    if kind!='coupled':kw.update(source_resistance=[0.,37.],load_resistance=[0.,None])
    if kind in ['capacitive','reactive']:kw['load_capacitance']=np.array([[20.,-4.],[-4.,30.]])*1e-12
    if kind=='reactive':kw.update(load_branch_resistance=[[13.,1.],[1.,9.]],load_branch_inductance=np.array([[12.,2.],[2.,8.]])*1e-9)
    return f(t,np.column_stack((drive,-.4*np.minimum(t/3e-9,1.))),**kw)


@pytest.mark.parametrize('kind',['scalar','coupled','mixed','capacitive','reactive'])
def test_all_ladder_subtypes_preserve_port_order_time_power_and_explicit_references(kind):
    source=ladder(kind);count=len(source.port_names);reference=np.linspace(40.,80.,count)
    r=startup_port_waves(source,z_ref=reference);checks(r)
    assert r.port_names==source.port_names and r.source_kind==type(source).__name__
    np.testing.assert_array_equal(r.time,source.time);np.testing.assert_array_equal(r.voltage,source.voltage)
    np.testing.assert_array_equal(r.current,source.current);np.testing.assert_array_equal(r.z_ref,reference)
    np.testing.assert_allclose(np.sum(r.port_power,axis=1),source.line_power,rtol=1e-10,atol=1e-14)
    changed=startup_port_waves(source,z_ref=reference*2);checks(changed)
    np.testing.assert_array_equal(changed.voltage,r.voltage);np.testing.assert_array_equal(changed.current,r.current)
    np.testing.assert_array_equal(changed.port_power,r.port_power)
    assert np.max(abs(changed.incident-r.incident))>0


@pytest.mark.parametrize('ports',[2,4])
def test_independent_skrf_real_reference_phasor_conversion(ports):
    require_tool('scikit-rf');from skrf.network import z2s
    clock=Stopwatch();t=np.linspace(0,8e-9,801);freq=500e6;reference=np.linspace(35.,85.,ports)
    # Known passive impedance matrix and imposed incident phasor; solve V=ZI
    # independently, then compare real-time waves with scikit-rf Z->S.
    impedance=np.diag(np.linspace(50.,90.,ports))+5.*np.ones((ports,ports))
    impedance=impedance+1j*(np.diag(np.linspace(20.,40.,ports))+3.*np.ones((ports,ports)))
    incident=np.linspace(.2,.5,ports)+1j*np.linspace(-.3,.1,ports)
    with clock('reference'):
        scattering=z2s(impedance[None,:,:],z0=reference,s_def='power')[0]
        outgoing=scattering@incident
        current=np.linalg.solve(impedance+np.diag(reference),2*np.sqrt(reference)*incident)
        voltage=impedance@current
        phase=np.exp(2j*np.pi*freq*t)[:,None]
        v=np.real(phase*voltage);i=np.real(phase*current)
        expected_a=np.real(phase*incident);expected_b=np.real(phase*outgoing)
    # Explicit sample-only fixture; no claim that this impedance is a line.
    source=lossless() if ports==2 else ladder('coupled')
    source=replace(source,time=t,voltage=v,current=i)
    with clock('openphysics'):actual=startup_port_waves(source,z_ref=reference)
    error=float(max(np.max(abs(actual.incident-expected_a)),np.max(abs(actual.reflected-expected_b))))
    record=make_record(case=f'sipi-startup-waves-{ports}-port',physics='real-reference port power-wave conversion',
        api='sipi.startup_port_waves',discretization='explicit real V/I samples,constant real diagonal reference',
        tool='scikit-rf',tool_discretization='power-wave Z-to-S of passive matrix and independent V=ZI current solve',
        matched=['500MHz complex phasors,positive real per-port references,same into-port current convention'],
        not_matched=['synthetic sampled impedance fixture is not a propagated line or startup solution'],
        observables=[observable('incident/reflected wave','sqrt(W)','maximum real-time absolute error',error,1e-10)],
        analytical_acceptance='independent delayed scalar reflections,voltage/current reconstruction and power balance',stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    assert error<=1e-10;checks(actual)


def test_zero_single_sample_and_nonuniform_observation_times():
    source=lossless_line_response([0.,.7e-9,2e-9,9e-9],source_times=[0.,1e-9],source_voltages=[0.,0.],
        z0_ohm=50.,delay_s=1e-9,source_resistance=50.,load_resistance=None)
    r=startup_port_waves(source,z_ref=[35.,75.]);checks(r)
    assert np.all(r.incident==0) and np.all(r.reflected==0)
    source=replace(source,time=source.time[:1],voltage=source.voltage[:1],current=source.current[:1])
    r=startup_port_waves(source,z_ref=[35.,75.]);assert r.incident.shape==(1,2);checks(r)


def test_copy_readonly_and_finite_json():
    source=ladder('reactive');z=np.array([35.,45.,55.,65.]);r=startup_port_waves(source,z_ref=z)
    text=json.dumps(r.to_dict(),sort_keys=True,allow_nan=False);z[:]=99
    for name in ['time','voltage','current','z_ref','incident','reflected','port_power']:
        a=getattr(r,name);assert not a.flags.writeable
        assert not np.shares_memory(a,getattr(source,name,np.empty(0)))
    out=r.to_dict();out['voltage_v'][0][0]=99;out['z_ref_ohm'][0]=99
    assert json.dumps(r.to_dict(),sort_keys=True,allow_nan=False)==text
    assert r.to_dict()['basis']=='single-ended' and r.to_dict()['scope']=='explicit-real-reference-startup-port-waves'


def test_linear_combination_reference_permutation_and_voltage_current_unit_scaling():
    source=lossless();r=startup_port_waves(source,z_ref=[35.,75.]);factor=-.4
    scaled=startup_port_waves(replace(source,voltage=source.voltage*factor,current=source.current*factor),z_ref=[35.,75.])
    np.testing.assert_allclose(scaled.incident,r.incident*factor,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(scaled.reflected,r.reflected*factor,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(scaled.port_power,r.port_power*factor**2,rtol=1e-10,atol=1e-12)
    swapped=startup_port_waves(replace(source,voltage=source.voltage[:,::-1],current=source.current[:,::-1]),z_ref=[75.,35.])
    np.testing.assert_allclose(swapped.incident,r.incident[:,::-1],rtol=1e-10,atol=1e-12)
    other=replace(source,voltage=source.voltage[:,::-1],current=source.current[:,::-1])
    rw=startup_port_waves(other,z_ref=[35.,75.])
    combined=startup_port_waves(replace(source,voltage=source.voltage+other.voltage,current=source.current+other.current),z_ref=[35.,75.])
    np.testing.assert_allclose(combined.incident,r.incident+rw.incident,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(combined.reflected,r.reflected+rw.reflected,rtol=1e-10,atol=1e-12)
    zscale=4.;transformed=startup_port_waves(replace(source,voltage=source.voltage*np.sqrt(zscale),current=source.current/np.sqrt(zscale)),z_ref=np.array([35.,75.])*zscale)
    np.testing.assert_allclose(transformed.incident,r.incident,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(transformed.reflected,r.reflected,rtol=1e-10,atol=1e-12)


@pytest.mark.parametrize('z',[50.,[50.],[50.,50.,50.],[[50.,50.]],[0.,50.],[-1.,50.],
    [True,50.],[np.nan,50.],[np.inf,50.],[50.+0j,50.+0j]])
def test_invalid_explicit_reference_rejects(z):
    with pytest.raises(ValueError):startup_port_waves(lossless(),z_ref=z)


@pytest.mark.parametrize('field,value',[
    ('time',[0.,0.]),('time',[-1.,0.]),('time',[]),('time',[0.,True]),
    ('voltage',np.zeros((801,3))),('current',np.zeros((801,1))),
    ('voltage',np.full((801,2),np.nan)),('current',np.full((801,2),np.inf)),
])
def test_malformed_response_fields_reject(field,value):
    # Bypass response construction intentionally to exercise the consumer guard.
    from copy import copy
    source=copy(lossless());object.__setattr__(source,field,value)
    with pytest.raises(ValueError):startup_port_waves(source,z_ref=[50.,50.])


def test_unsupported_object_rejects():
    with pytest.raises(ValueError,match='startup response'):startup_port_waves(object(),z_ref=[50.,50.])


def test_balanced_extreme_references_keep_finite_power():
    source=lossless();v=np.full_like(source.voltage,1e100);i=np.full_like(source.current,1e-100)
    r=startup_port_waves(replace(source,voltage=v,current=i),z_ref=[1e200,1e200])
    np.testing.assert_allclose(r.incident,1.,rtol=1e-14,atol=0);assert np.all(r.reflected==0)
    np.testing.assert_allclose(r.port_power,1.,rtol=1e-14,atol=0);checks(r)


def test_unrepresentable_reconstruction_and_power_reject_without_clipping():
    source=lossless();v=np.ones_like(source.voltage);i=v*1e-30
    with pytest.raises(ValueError,match='reconstruction'):startup_port_waves(replace(source,voltage=v,current=i),z_ref=[1.,1.])
    with pytest.raises(ValueError,match='finite scales'):startup_port_waves(replace(source,voltage=v*1e300,current=v),z_ref=[1.,1.])
