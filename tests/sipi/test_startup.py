# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Lossless startup: causality, reflections, boundaries and independent LC ODE."""
import importlib.metadata as metadata
import json

import numpy as np
import pytest
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import lossless_line_response
import sipi.startup as module


def run(time=None, **changes):
    args=dict(source_times=[0.],source_voltages=[1.],z0_ohm=50.,delay_s=1.,
              source_resistance=50.,load_resistance=50.)
    args.update(changes)
    return lossless_line_response([0.,.5,1.,1.5,2.,2.5,3.,4.] if time is None else time,**args)


@pytest.mark.parametrize('load',[50.,None,0.])
def test_exact_matched_open_short_first_arrival_and_return(load):
    r=run(load_resistance=load,max_terms=1);t=r.time
    gl={50.:0.,None:1.,0.:-1.}[load]
    np.testing.assert_array_equal(r.voltage[:,0],.5*(1+gl*(t>=2)))
    np.testing.assert_array_equal(r.current[:,0],.01*(1-gl*(t>=2)))
    np.testing.assert_array_equal(r.voltage[:,1],.5*(1+gl)*(t>=1))
    np.testing.assert_array_equal(r.current[:,1],-.01*(1-gl)*(t>=1))
    assert r.terms==1 and r.port_names==('source','load')


def test_mismatched_reflection_levels_and_resistive_steady_limit():
    r=run([0.,1.,2.,3.,60.],source_resistance=25.,load_resistance=100.)
    np.testing.assert_allclose(r.voltage[:4,0],[2/3,2/3,22/27,22/27],rtol=1e-14)
    np.testing.assert_allclose(r.voltage[:4,1],[0,8/9,8/9,64/81],rtol=1e-14,atol=0)
    np.testing.assert_allclose(r.voltage[-1],[.8,.8],rtol=1e-14)
    np.testing.assert_allclose(r.current[-1],[.008,-.008],rtol=1e-14)
    np.testing.assert_allclose(r.drive_voltage-r.voltage[:,0],25*r.current[:,0],atol=1e-15)
    np.testing.assert_allclose(r.voltage[:,1],-100*r.current[:,1],atol=1e-15)


@pytest.mark.parametrize('load',[50.,None,0.])
def test_port_power_integrates_to_exact_final_electric_or_magnetic_energy(load):
    t=np.array([0.,.25,.75,1.,1.5,2.,3.]);r=run(t,load_resistance=load)
    power=np.sum(r.voltage*r.current,axis=1)
    # Right-continuous step levels are constant between these exact arrivals.
    energy=np.r_[0.,np.cumsum(np.diff(t)*power[:-1])]
    arrival=1. if load==50. else 2.
    np.testing.assert_allclose(energy,.005*np.minimum(t,arrival),rtol=1e-14,atol=0)
    # Total L=Z0*tau, C=tau/Z0. Matched has equal electric/magnetic halves;
    # settled open is purely electric, settled short purely magnetic.
    final=(.5*(1/50)*.5**2+.5*50*.01**2 if load==50. else
           .5*(1/50)*1.**2 if load is None else .5*50*.02**2)
    assert energy[-1]==pytest.approx(final,rel=1e-14)
    source_power=r.drive_voltage*r.current[:,0]
    np.testing.assert_allclose(source_power,50*r.current[:,0]**2+r.voltage[:,0]*r.current[:,0],
                               rtol=1e-14,atol=0)


@pytest.mark.parametrize('load',[None,0.])
def test_ideal_source_undamped_horizon_sum_and_exact_budget(load,monkeypatch):
    t=np.array([0.,.5,1.,2.,3.,4.,5.,6.]);r=run(t,source_resistance=0.,load_resistance=load,max_terms=4)
    np.testing.assert_array_equal(r.voltage[:,0],np.ones(len(t)))
    count=np.floor(t/2).astype(int)
    if load is None:
        np.testing.assert_allclose(r.current[:,0],(-1.)**count/50,rtol=1e-15)
    else:
        np.testing.assert_allclose(r.current[:,0],(2*count+1)/50,rtol=1e-15)
        np.testing.assert_array_equal(r.voltage[:,1],np.zeros(len(t)))
    assert r.terms==4
    monkeypatch.setattr(module,'_drive',lambda *a:pytest.fail('budget exceeded after waveform evaluation'))
    with pytest.raises(ValueError,match='max_terms'):run(t,source_resistance=0.,load_resistance=load,max_terms=3)


def test_delayed_pwl_pulse_has_zero_prehistory_and_no_wrap():
    time=np.array([0.,.5,1.,1.25,1.5,2.,2.5,3.,4.,5.])
    r=run(time,source_times=[1.,1.5,2.],source_voltages=[0.,2.,0.])
    expected=np.interp(time,[1.,1.5,2.],[0.,2.,0.],left=0,right=0)
    delayed=np.interp(time,[2.,2.5,3.],[0.,2.,0.],left=0,right=0)
    np.testing.assert_array_equal(r.voltage[:,0],.5*expected)
    np.testing.assert_array_equal(r.voltage[:,1],.5*delayed)
    assert run([0.],source_times=[1.],source_voltages=[2.]).terms==0
    np.testing.assert_array_equal(run([0.],source_times=[1.],source_voltages=[2.]).voltage,[[0.,0.]])


def test_superposition_time_scale_impedance_scale_and_input_isolation():
    t=np.linspace(0,12,121);knots=np.array([0.,.7,2.,5.]);v=np.array([0.,2.,-1.,.5])
    kwargs=dict(source_times=knots,source_voltages=v,source_resistance=25.,load_resistance=100.)
    base=run(t,**kwargs)
    scaled=run(t*1e-9,**dict(kwargs,source_times=knots*1e-9,delay_s=1e-9))
    np.testing.assert_allclose(scaled.voltage,base.voltage,rtol=1e-12,atol=1e-14)
    scaled_z=run(t,**dict(kwargs,z0_ohm=500.,source_resistance=250.,load_resistance=1000.))
    np.testing.assert_allclose(scaled_z.voltage,base.voltage,rtol=1e-14,atol=0)
    np.testing.assert_allclose(scaled_z.current*10,base.current,rtol=1e-14,atol=1e-16)
    second=run(t,**dict(kwargs,source_voltages=[1.,-.5,.25,0.]))
    combined=run(t,**dict(kwargs,source_voltages=v+np.array([1.,-.5,.25,0.])))
    np.testing.assert_allclose(combined.voltage,base.voltage+second.voltage,rtol=1e-12,atol=1e-14)
    before=base.to_dict();t[:]=1;knots[:]=1;v[:]=1
    assert base.to_dict()==before
    for name in ['time','source_times','source_voltages','drive_voltage','voltage','current','forward_voltage','backward_voltage']:
        assert not getattr(base,name).flags.writeable
    before['voltage_v'][0][0]=999;assert base.to_dict()!=before
    json.dumps(base.to_dict(),allow_nan=False)


def test_extreme_finite_resistance_preserves_load_current_and_boundaries():
    r=run([1.,2.,3.],load_resistance=1e200)
    assert np.all(r.current[:,1]<0)
    np.testing.assert_allclose(r.voltage[:,1],-1e200*r.current[:,1],rtol=1e-14)
    source=run([0.,1.,2.],source_resistance=1e200)
    assert np.all(source.current[:,0]>0)
    np.testing.assert_allclose(source.voltage[:,0]+1e200*source.current[:,0],1.,rtol=1e-14)
    tiny=run([1.],z0_ohm=5e-309,source_resistance=5e-309,load_resistance=5e-309,source_voltages=[1e-300])
    np.testing.assert_allclose(tiny.current,[[1e8,-1e8]],rtol=1e-14)


def test_pwl_opposite_large_values_uses_finite_convex_blend():
    r=run([.5],source_times=[0.,1.],source_voltages=[1.5e308,-1.5e308])
    np.testing.assert_array_equal(r.drive_voltage,[0.])


@pytest.mark.parametrize('changes',[
    dict(z0_ohm=0),dict(z0_ohm=True),dict(delay_s=-1),dict(delay_s=np.inf),
    dict(source_resistance=-1),dict(source_resistance=np.nan),dict(load_resistance=np.inf),dict(load_resistance=True),
    dict(max_terms=0),dict(max_terms=10001),dict(max_terms=True),dict(max_terms=1.),
    dict(source_times=[]),dict(source_times=[1.,0.]),dict(source_times=[0.,0.]),
    dict(source_times=[-1.]),dict(source_times=[True]),dict(source_times=[[0.]]),
    dict(source_voltages=[1.,2.]),dict(source_voltages=[True]),dict(source_voltages=[np.nan]),dict(source_voltages=[1j]),
])
def test_invalid_controls_reject_before_waveforms(changes,monkeypatch):
    monkeypatch.setattr(module,'_drive',lambda *a:pytest.fail('invalid controls evaluated a waveform'))
    with pytest.raises((ValueError,TypeError)):run(**changes)


@pytest.mark.parametrize('time',[[],[-1.],[True],[np.inf],[1.,1.],[1.,0.],[[0.]]])
def test_invalid_output_times(time):
    with pytest.raises(ValueError):run(time)


def test_unresolved_shifted_knots_and_nonfinite_results_fail_explicitly():
    with pytest.raises(ValueError,match='resolution'):
        run([1e20],delay_s=1e20,source_times=[0.,1.],source_voltages=[0.,1.])
    with pytest.raises(ValueError,match='finite'):
        run([1.],source_voltages=[1.7e308],source_resistance=0.,load_resistance=None)


def test_independent_lc_ladder_refinement_against_actual_startup():
    scipy=require_tool('scipy');from scipy.integrate import solve_ivp
    clock=Stopwatch();u=np.linspace(0,12,1201);z=50.;rs=25.;rl=100.
    with clock('openphysics'):
        actual=run(u*1e-9,delay_s=1e-9,source_times=[0.,2e-9],source_voltages=[0.,1.],
                   source_resistance=rs,load_resistance=rl)
    errors=[]
    for n in [32,64,128]:
        def rhs(t,y):
            v=y[:n+1];j=y[n+1:];dv=np.empty(n+1)
            drive=np.interp(t,[0.,2.],[0.,1.],left=0,right=1)
            dv[1:-1]=n*(j[:-1]-j[1:]);dv[0]=2*n*((z/rs)*(drive-v[0])-j[0])
            dv[-1]=2*n*(j[-1]-(z/rl)*v[-1]);dj=n*(v[:-1]-v[1:])
            return np.r_[dv,dj]
        with clock('reference'):
            solved=solve_ivp(rhs,[0,12],np.zeros(2*n+1),method='DOP853',t_eval=u,
                rtol=1e-10,atol=1e-12,max_step=.2/n)
        assert solved.success
        errors.append(float(np.max(abs(solved.y[[0,n],:].T-actual.voltage))))
    record=make_record(case='sipi-lossless-startup-ladder',physics='initially unenergized scalar lossless line',
        api='sipi.lossless_line_response',discretization='finite exact round-trip voltage delay sum',
        tool='scipy',tool_discretization='DOP853 ODE of series L and endpoint half-C ladder, 32/64/128 cells',
        matched=['Z0=50ohm, tau=1ns, Rs25/RL100ohm, 2ns ramp, 0..12ns outputs, zero initial energy'],
        not_matched=['ladder spatial discretization; explicitly refined','actual materials, loss or reactive terminations'],
        observables=[observable('source/load voltage','V','maximum absolute difference at128 cells',errors[-1],.02)],
        analytical_acceptance='matched/open/short arrival levels, boundary equations and undamped finite horizon',stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    print('startup LC 32/64/128 max errors V',errors)
    assert errors[-1]<=.02 and errors[2]<errors[1]<errors[0]
