# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Finite ladder analytic circuits, continuum limits and independent tools."""
import importlib.metadata as metadata
import json

import numpy as np
import pytest
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import rlgc_ladder_response, lossless_line_response
import sipi.rlgc_startup as module

TAU=1e-9


def run(time=None,drive=None,**changes):
    time=np.linspace(0,12*TAU,1201) if time is None else time
    drive=np.interp(time,[0.,2*TAU],[0.,1.],left=0,right=1.) if drive is None else drive
    args=dict(R=20.,L=500e-9,G=.002,C=200e-12,length=.1,cells=32,
              source_resistance=25.,load_resistance=100.)
    args.update(changes);return rlgc_ladder_response(time,drive,**args)


def power_checks(r):
    assert np.min(r.energy)>=0 and np.min(r.series_loss)>=0 and np.min(r.shunt_loss)>=0
    assert r.power_balance_relative_error<=1e-10
    np.testing.assert_allclose(r.energy_rate,r.line_power-r.series_loss-r.shunt_loss,rtol=1e-10,atol=1e-14)
    np.testing.assert_allclose(r.source_power,r.source_resistor_loss+r.load_resistor_loss+r.line_power,
                               rtol=1e-10,atol=1e-14)


def test_single_cell_ideal_source_short_exact_rl_ramp_and_end_capacitor():
    t=np.linspace(0,4,401);drive=np.minimum(t,1.)
    r=run(t,drive,R=2.,L=1.,G=0.,C=.4,length=1.,cells=1,
          source_resistance=0.,load_resistance=0.)
    before=.5*(t+.5*np.expm1(-2*t));at_one=.5*(1+.5*np.expm1(-2))
    exact=np.where(t<=1,before,.5+(at_one-.5)*np.exp(-2*(t-1)))
    slope=np.r_[np.diff(drive)/np.diff(t),0.]
    np.testing.assert_allclose(r.segment_current[:,0],exact,rtol=1e-12,atol=1e-14)
    np.testing.assert_allclose(r.current[:,0],exact+.2*slope,rtol=1e-12,atol=1e-14)
    np.testing.assert_allclose(r.current[:,1],-exact,rtol=1e-12,atol=1e-14)
    np.testing.assert_allclose(r.energy,.5*exact**2+.1*drive**2,rtol=1e-12,atol=1e-14)
    np.testing.assert_allclose(r.series_loss,2*exact**2,rtol=1e-12,atol=1e-14)
    assert r.current[-1,0]==pytest.approx(exact[-1],rel=1e-12)
    power_checks(r)


def test_single_cell_ideal_source_open_exact_lc_ramp_oscillation():
    t=np.linspace(0,4,401);drive=np.minimum(t,1.);w=np.sqrt(5.)
    r=run(t,drive,R=0.,L=1.,G=0.,C=.4,length=1.,cells=1,
          source_resistance=0.,load_resistance=None)
    before=t-np.sin(w*t)/w;dv_before=1-np.cos(w*t)
    shift=t-1;a=-np.sin(w)/w;b=(1-np.cos(w))/w
    after=1+a*np.cos(w*shift)+b*np.sin(w*shift)
    dv_after=-a*w*np.sin(w*shift)+b*w*np.cos(w*shift)
    voltage=np.where(t<=1,before,after);current=.2*np.where(t<=1,dv_before,dv_after)
    np.testing.assert_allclose(r.voltage[:,1],voltage,rtol=1e-11,atol=1e-14)
    np.testing.assert_allclose(r.segment_current[:,0],current,rtol=1e-11,atol=1e-14)
    np.testing.assert_array_equal(r.current[:,1],np.zeros(len(t)))
    np.testing.assert_allclose(r.energy,.5*current**2+.1*(drive**2+voltage**2),rtol=1e-11,atol=1e-14)
    assert np.any(r.line_power<0)  # Return of energy must not be clamped.
    power_checks(r)


@pytest.mark.parametrize('rs,rl',[(25.,100.),(0.,0.),(0.,None),(0.,50.),(25.,0.),(25.,None)])
def test_lossless_continuum_refinement_and_resistive_ideal_open_short_boundaries(rs,rl):
    t=np.linspace(0,12*TAU,1201);exact=lossless_line_response(t,
        source_times=[0.,2*TAU],source_voltages=[0.,1.],z0_ohm=50.,delay_s=TAU,
        source_resistance=rs,load_resistance=rl)
    counts=[64,128,256] if rs==0 and rl is None else [32,64,128]
    ev=[];ei=[]
    for n in counts:
        r=run(t,R=0.,G=0.,cells=n,source_resistance=rs,load_resistance=rl)
        ev.append(float(np.max(abs(r.voltage-exact.voltage))))
        ei.append(float(np.max(abs(r.current-exact.current))))
        power_checks(r)
        power_checks(run(t,cells=n,source_resistance=rs,load_resistance=rl))
    assert ev[-1]<=.02 and ei[-1]<=.0005
    assert max(ev)<1e-14 or ev[2]<ev[1]<ev[0]
    assert ei[2]<ei[1]<ei[0]
    print('ladder boundary refinement',rs,rl,counts,ev,ei)


def test_independent_same_circuit_dop853_with_separate_kcl_equations():
    require_tool('scipy');from scipy.integrate import solve_ivp
    clock=Stopwatch();u=np.linspace(0,12,1201);n=32
    with clock('openphysics'):actual=run(u*TAU,R=0.,G=0.,cells=n)
    def rhs(t,y):
        v=y[:n+1];j=y[n+1:];dv=np.empty(n+1)
        drive=np.interp(t,[0.,2.],[0.,1.],left=0,right=1)
        dv[1:-1]=n*(j[:-1]-j[1:]);dv[0]=2*n*(2*(drive-v[0])-j[0])
        dv[-1]=2*n*(j[-1]-.5*v[-1]);dj=n*(v[:-1]-v[1:])
        return np.r_[dv,dj]
    with clock('reference'):
        ref=solve_ivp(rhs,[0,12],np.zeros(2*n+1),method='DOP853',t_eval=u,
                      rtol=1e-10,atol=1e-12,max_step=.2/n)
    assert ref.success
    error=float(np.max(abs(ref.y[[0,n],:].T-actual.voltage)))
    record=make_record(case='sipi-rlgc-startup-ode',physics='zero-state finite LC circuit',
        api='sipi.rlgc_ladder_response',discretization='32-cell PWL state-space matrix propagation',
        tool='scipy',tool_discretization='separate normalized KCL/inductor equations integrated with DOP853',
        matched=['same32 cells, half-end capacitors,50ohm/1ns,Rs25/RL100 and2ns ramp'],
        not_matched=['different time propagation algorithms in same library, not independent spatial discretizations'],
        observables=[observable('source/load voltage','V','maximum absolute difference',error,1e-8)],
        analytical_acceptance='single-cell exact RL/LC; continuum and distributed-frequency checks separate',stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    assert error<=1e-8


def test_independent_skrf_lossy_distributed_frequency_limit_with_pwl_drive():
    skrf=require_tool('scikit-rf');clock=Stopwatch()
    f=500e6;w=2*np.pi*f;t=np.arange(20*256+1)/(f*256);drive=np.sin(w*t)
    gamma=np.sqrt((20+1j*w*500e-9)*(.002+1j*w*200e-12))
    zc=np.sqrt((20+1j*w*500e-9)/(.002+1j*w*200e-12))
    with clock('reference'):
        media=skrf.media.DefinedGammaZ0(frequency=skrf.Frequency.from_f([f],unit='hz'),z0_port=50.,z0=zc,gamma=gamma)
        a,b,c,d=media.line(.1,unit='m').a[0].ravel()
        vl=1/(a+b/100+25*(c+d/100));expected=np.array([(a+b/100)*vl,vl])
    last=slice(-4*256-1,-1);phasor=np.exp(-1j*w*t[last]);errors=[]
    for n in [32,64,128]:
        with clock('openphysics'):r=run(t,drive,cells=n)
        actual=(2/len(phasor))*(phasor@r.voltage[last])/(-1j)
        errors.append(float(np.max(abs(actual-expected))));power_checks(r)
    record=make_record(case='sipi-rlgc-startup-distributed-limit',physics='constant passive scalar RLGC line',
        api='sipi.rlgc_ladder_response',discretization='32/64/128 finite circuit cells, PWL time propagation',
        tool='scikit-rf',tool_discretization='continuous DefinedGammaZ0 ABCD at500MHz with Thevenin/load equations',
        matched=['R20ohm/m,L500nH/m,G.002S/m,C200pF/m,length.1m,Rs25/RL100',
                 'final4cycles of20cycles,256 samples/cycle,unit sinusoidal ideal source'],
        not_matched=['finite spatial circuit and PWL drive approximation; no correction for interpolation error'],
        observables=[observable('source/load complex voltage','V','max absolute128-cell phasor error',errors[-1],1e-3)],
        analytical_acceptance='single-cell exact RL/LC and separate lossless continuum refinement',stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    print('RLGC distributed phasor errors V',errors)
    assert errors[-1]<=1e-3 and errors[2]<errors[1]<errors[0]


def test_time_impedance_scaling_copies_and_optional_state_serialization():
    t=np.linspace(0,12*TAU,121);drive=np.minimum(t/(2*TAU),1.)
    r=run(t,drive,cells=8)
    time_scaled=run(t*1e6,drive,L=500e-9*1e6,C=200e-12*1e6,cells=8)
    np.testing.assert_allclose(time_scaled.voltage,r.voltage,rtol=1e-11,atol=1e-14)
    np.testing.assert_allclose(time_scaled.current,r.current,rtol=1e-11,atol=1e-14)
    np.testing.assert_allclose(time_scaled.energy/1e6,r.energy,rtol=1e-11,atol=1e-25)
    z_scaled=run(t,drive,R=20e3,L=500e-6,G=.002/1000,C=200e-15,
                 source_resistance=25e3,load_resistance=100e3,cells=8)
    np.testing.assert_allclose(z_scaled.voltage,r.voltage,rtol=1e-11,atol=1e-14)
    np.testing.assert_allclose(z_scaled.current*1000,r.current,rtol=1e-11,atol=1e-14)
    before=r.to_dict();t[:]=1;drive[:]=9
    assert r.to_dict()==before and not before['states_included'] and 'node_voltage_v' not in before
    full=r.to_dict(include_states=True);assert np.shape(full['node_voltage_v'])==(121,9)
    assert np.shape(full['segment_current_a'])==(121,8)
    assert full['node_positions_m'][0]==0 and full['node_positions_m'][-1]==.1
    full['input']['cells']=99;full['node_voltage_v'][0][0]=999
    assert r.inputs['cells']==8 and r.node_voltage[0,0]==0
    for name,value in r.__dict__.items():
        if isinstance(value,np.ndarray):assert not value.flags.writeable,name
    for bad in [1,None,'yes']:
        with pytest.raises(ValueError):r.to_dict(include_states=bad)
    json.dumps(r.to_dict(include_states=True),allow_nan=False)


def test_zero_drive_has_zero_states_powers_and_relative_residual():
    r=run(np.linspace(0,TAU,5),np.zeros(5),cells=1,source_resistance=0.,load_resistance=0.)
    for name in ['node_voltage','segment_current','voltage','current','energy','energy_rate','line_power']:
        np.testing.assert_array_equal(getattr(r,name),np.zeros_like(getattr(r,name)))
    assert r.power_balance_relative_error==0


@pytest.mark.parametrize('changes',[
    dict(R=-1),dict(R=True),dict(L=0),dict(L=np.inf),dict(G=-1),dict(G=1j),dict(C=0),dict(C=np.nan),
    dict(length=0),dict(length=True),dict(cells=0),dict(cells=257),dict(cells=True),dict(cells=1.),
    dict(source_resistance=-1),dict(source_resistance=None),dict(source_resistance=True),
    dict(load_resistance=-1),dict(load_resistance=np.inf),dict(load_resistance=True),
    dict(L=1e-320,C=1e-320,length=1e-320),dict(L=1e-320),
])
def test_invalid_scalars_or_cell_scales_precede_state_propagation(changes,monkeypatch):
    monkeypatch.setattr(module,'lsim',lambda *a,**k:pytest.fail('invalid input reached propagation'))
    with pytest.raises((ValueError,TypeError)):run(**changes)


@pytest.mark.parametrize('time,drive',[
    ([],[]),([0.],[0.]),([1.,2.],[0.,1.]),([0.,0.],[0.,1.]),([0.,2.,1.],[0.,1.,1.]),
    ([0.,1.,3.],[0.,1.,1.]),([0.,True],[0.,1.]),([0.,np.inf],[0.,1.]),
    ([0.,1.],[1.,1.]),([0.,1.],[0.]),([0.,1.],[0.,True]),([0.,1.],[0.,1j]),
    ([0.,1.],[0.,np.nan]),([0.,1.,2.],[0.,1.7e308,-1.7e308]),
    (np.linspace(0.,1.,10001),np.zeros(10001)),
])
def test_invalid_time_or_source_precedes_state_propagation(time,drive,monkeypatch):
    monkeypatch.setattr(module,'lsim',lambda *a,**k:pytest.fail('invalid samples reached propagation'))
    with pytest.raises((ValueError,TypeError)):run(time,drive)


@pytest.mark.parametrize('kind',['shape','nonfinite'])
def test_invalid_propagator_result_is_rejected(kind,monkeypatch):
    def fake(system,drive,time,**kwargs):
        state=np.zeros((len(time),1 if kind=='shape' else system[0].shape[0]))
        if kind=='nonfinite':state[0,0]=np.nan
        return time,np.zeros(len(time)),state
    monkeypatch.setattr(module,'lsim',fake)
    with pytest.raises(ValueError,match='state propagation'):run(cells=2)
