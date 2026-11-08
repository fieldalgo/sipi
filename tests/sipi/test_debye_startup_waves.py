# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Debye terminal waves with independent relaxation and net energy diagnostics."""
from copy import copy
import json
import numpy as np
import pytest
from sipi import debye_rlgc_ladder_response, rlgc_ladder_response, startup_port_waves


def arguments(rs=25.,rl=100.,pulse=False):
    t=np.linspace(0.,12e-9,121);d=np.minimum(t/2e-9,1.)
    if pulse:d-=np.minimum(np.maximum(t-5e-9,0)/2e-9,1.)
    return dict(time=t,source_voltages=d,R=20.,L=500e-9,G=.002,C_inf=200e-12,
        delta_C=[150e-12,50e-12],relaxation_hz=[1e9,1e8],length=.1,cells=16,
        source_resistance=rs,load_resistance=rl)


def checks(r,z=(35.,75.)):
    w=startup_port_waves(r,z_ref=z);assert w.source_kind=='DebyeRLGCLadderResponse'
    assert w.port_names==('source','load')
    for name in ['time','voltage','current']:np.testing.assert_array_equal(getattr(w,name),getattr(r,name))
    root=np.sqrt(w.z_ref);power=w.incident**2-w.reflected**2
    np.testing.assert_allclose(root*(w.incident+w.reflected),r.voltage,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose((w.incident-w.reflected)/root,r.current,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(power,r.voltage*r.current,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(power[:,0],r.source_power-r.source_resistor_loss,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(power[:,1],-r.load_resistor_loss,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(power.sum(axis=1),r.total_energy_rate+r.series_loss+r.shunt_loss+r.relaxation_loss,rtol=1e-10,atol=1e-12)
    assert max(w.voltage_reconstruction_relative_error,w.current_reconstruction_relative_error,w.power_balance_relative_error)<=1e-10
    return w


@pytest.mark.parametrize('rs,rl',[(0.,0.),(0.,None),(0.,100.),(25.,0.),(25.,None),(25.,100.)])
@pytest.mark.parametrize('pulse',[False,True])
def test_six_boundaries_and_pulse_preserve_terminal_and_polarization_power(rs,rl,pulse):
    r=debye_rlgc_ladder_response(**arguments(rs,rl,pulse));w=checks(r);other=checks(r,[70.,150.])
    np.testing.assert_array_equal(other.port_power,w.port_power)
    if rl==0:np.testing.assert_array_equal(w.incident[:,1],-w.reflected[:,1])
    if rl is None:np.testing.assert_array_equal(w.incident[:,1],w.reflected[:,1])
    if rs==0:np.testing.assert_allclose((w.incident[:,0]+w.reflected[:,0])*np.sqrt(35),r.source_voltages,rtol=1e-10,atol=1e-12)
    assert np.max(r.relaxation_loss)>0 and np.max(r.polarization_energy)>0


def test_independent_ideal_source_short_relaxation_and_inductor_analytic_waves():
    t=np.linspace(0.,4.,801);d=np.minimum(t,1.);tau=.4;shift=np.maximum(t-1.,0.)
    r=debye_rlgc_ladder_response(t,d,R=0.,L=1.,G=0.,C_inf=.4,delta_C=[.6],relaxation_hz=[1/(2*np.pi*tau)],length=1.,cells=1,source_resistance=0.,load_resistance=0.)
    w=checks(r,[2.,3.]);q=.3*(t-tau*(1-np.exp(-t/tau))-shift+tau*(1-np.exp(-shift/tau)))
    dq=.3*(np.exp(-shift/tau)-np.exp(-t/tau));iline=.5*(t*t-shift*shift)
    voltage=np.column_stack((d,np.zeros(len(t))));current=np.column_stack((.2*np.where(t<1.,1.,0.)+dq+iline,-iline))
    np.testing.assert_allclose(w.incident,(voltage/np.sqrt([2.,3.])+current*np.sqrt([2.,3.]))/2,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(w.reflected,(voltage/np.sqrt([2.,3.])-current*np.sqrt([2.,3.]))/2,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(r.polarization_energy,.5*q*q/.3,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(r.relaxation_loss,tau/.3*dq*dq,rtol=1e-10,atol=1e-12)


@pytest.mark.parametrize('pulse',[False,True])
def test_zero_strength_recovers_original_constant_rlgc_waves(pulse):
    a=arguments(pulse=pulse);a['delta_C']=[0.,0.];r=debye_rlgc_ladder_response(**a);w=checks(r)
    a['C']=a.pop('C_inf');a.pop('delta_C');a.pop('relaxation_hz');other=startup_port_waves(rlgc_ladder_response(**a),z_ref=w.z_ref)
    for name in ['incident','reflected','port_power']:np.testing.assert_allclose(getattr(w,name),getattr(other,name),rtol=1e-10,atol=1e-12)


def test_four_pole_splitting_and_reordering_preserve_waves():
    a=arguments();original=checks(debye_rlgc_ladder_response(**a))
    a.update(delta_C=[25e-12,75e-12,25e-12,75e-12],relaxation_hz=[1e8,1e9,1e8,1e9]);r=debye_rlgc_ladder_response(**a);w=checks(r)
    for name in ['incident','reflected','port_power']:np.testing.assert_allclose(getattr(w,name),getattr(original,name),rtol=1e-10,atol=1e-12)


def test_zero_drive_and_detached_finite_readonly_json():
    a=arguments();a['source_voltages'][:]=0;r=debye_rlgc_ladder_response(**a);w=checks(r)
    assert not np.any(w.incident) and not np.any(w.reflected)
    r=debye_rlgc_ladder_response(**arguments());z=np.array([35.,75.]);w=checks(r,z);before=json.dumps(w.to_dict(),sort_keys=True,allow_nan=False);z[:]=9
    for name in ['time','voltage','current','z_ref','incident','reflected','port_power']:
        assert not getattr(w,name).flags.writeable and not np.shares_memory(getattr(w,name),getattr(r,name,np.empty(0)))
    out=w.to_dict();out['port_power_w'][0][0]=9;assert json.dumps(w.to_dict(),sort_keys=True,allow_nan=False)==before


@pytest.mark.parametrize('z',[50.,[50.],[50.,50.,50.],[0.,50.],[-1.,50.],[True,50.],[np.inf,50.],[50+0j,50.]])
def test_explicit_positive_real_references(z):
    with pytest.raises(ValueError):startup_port_waves(debye_rlgc_ladder_response(**arguments()),z_ref=z)


@pytest.mark.parametrize('replacement',['drive','polarization-current'])
def test_internal_arrays_cannot_replace_terminal_current(replacement):
    r=copy(debye_rlgc_ladder_response(**arguments()));value=r.source_voltages if replacement=='drive' else r.polarization_current
    object.__setattr__(r,'current',value)
    with pytest.raises(ValueError,match='shapes'):startup_port_waves(r,z_ref=[35.,75.])
