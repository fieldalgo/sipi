# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Coupled startup modal/independent limits, invariants and passive controls."""
import importlib.metadata as metadata
import json

import numpy as np
import pytest
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import coupled_rlgc_ladder_response, rlgc_ladder_response, lossless_line_response
import sipi.coupled_startup as module

R=np.array([[20.,3.],[3.,20.]])
L=np.array([[500.,100.],[100.,500.]])*1e-9
G=np.array([[.002,-.0003],[-.0003,.002]])
C=np.array([[220.,-40.],[-40.,220.]])*1e-12
Q=np.array([[1.,1.],[1.,-1.]])/np.sqrt(2)


def run(time=None,drive=None,**changes):
    time=np.linspace(0,12e-9,121) if time is None else time
    drive=np.column_stack((np.minimum(np.asarray(time)/2e-9,1.),np.zeros(len(time)))) if drive is None else drive
    args=dict(R=R,L=L,G=G,C=C,length=.1,cells=16,source_resistance=[25.,25.],load_resistance=[100.,100.])
    args.update(changes);return coupled_rlgc_ladder_response(time,drive,**args)


def power_checks(r):
    assert np.min(r.energy)>=0 and np.min(r.series_loss)>=0 and np.min(r.shunt_loss)>=0
    assert r.power_balance_relative_error<=1e-10
    np.testing.assert_allclose(r.energy_rate,r.line_power-r.series_loss-r.shunt_loss,rtol=1e-10,atol=1e-14)
    np.testing.assert_allclose(r.source_power,r.source_resistor_loss+r.load_resistor_loss+r.line_power,rtol=1e-10,atol=1e-14)


def test_lossless_modal_continuum_refinement():
    t=np.linspace(0,12e-9,1201);modal_v=[];modal_i=[]
    for m in range(2):
        lm=(Q.T@L@Q)[m,m];cm=(Q.T@C@Q)[m,m]
        mode=lossless_line_response(t,source_times=[0.,2e-9],source_voltages=[0.,Q[0,m]],
            z0_ohm=np.sqrt(lm/cm),delay_s=.1*np.sqrt(lm*cm),source_resistance=25.,load_resistance=100.)
        modal_v.append(mode.voltage);modal_i.append(mode.current)
    v=(np.stack(modal_v,axis=-1)@Q.T).reshape(len(t),4)
    i=(np.stack(modal_i,axis=-1)@Q.T).reshape(len(t),4);ev=[];ei=[]
    for n in [32,64,128]:
        r=run(t,R=np.zeros((2,2)),G=np.zeros((2,2)),cells=n)
        ev.append(float(np.max(abs(r.voltage-v))));ei.append(float(np.max(abs(r.current-i))));power_checks(r)
    print('coupled lossless modal refinement',ev,ei)
    assert ev[-1]<=.02 and ei[-1]<=.0005
    assert ev[2]<ev[1]<ev[0] and ei[2]<ei[1]<ei[0]


def test_independent_skrf_modal_distributed_frequency_refinement():
    skrf=require_tool('scikit-rf');clock=Stopwatch();f=500e6;w=2*np.pi*f
    t=np.arange(20*256+1)/(f*256);drive=np.column_stack((np.sin(w*t),np.zeros_like(t)));modal=[]
    with clock('reference'):
        for m in range(2):
            rm,lm,gm,cm=[(Q.T@a@Q)[m,m] for a in [R,L,G,C]]
            gamma=np.sqrt((rm+1j*w*lm)*(gm+1j*w*cm));zc=np.sqrt((rm+1j*w*lm)/(gm+1j*w*cm))
            media=skrf.media.DefinedGammaZ0(frequency=skrf.Frequency.from_f([f],unit='hz'),z0_port=50.,z0=zc,gamma=gamma)
            a,b,c,d=media.line(.1,unit='m').a[0].ravel();vl=Q[0,m]/(a+b/100+25*(c+d/100))
            modal.append(np.array([(a+b/100)*vl,vl]))
        expected=(np.stack(modal,axis=-1)@Q.T).ravel()
    last=slice(-4*256-1,-1);phase=np.exp(-1j*w*t[last]);errors=[]
    for n in [32,64,128]:
        with clock('openphysics'):r=run(t,drive,cells=n)
        actual=2/len(phase)*(phase@r.voltage[last])/(-1j)
        errors.append(float(np.max(abs(actual-expected))));power_checks(r)
    record=make_record(case='sipi-coupled-startup-modal-distributed',physics='passive two-signal RLGC circuit',
        api='sipi.coupled_rlgc_ladder_response',discretization='32/64/128 finite cells with full2x2 matrices',
        tool='scikit-rf',tool_discretization='independent modal continuous DefinedGammaZ0/ABCD and orthogonal recombination',
        matched=['exchange-symmetric RLGC,0.1m,Rs25/RL100 each,first conductor unit500MHz sinusoid',
                 '20cycles,256 samples/cycle,final4-cycle phasor'],
        not_matched=['finite cells and PWL source versus continuous modal frequency line; no interpolation correction'],
        observables=[observable('four port voltage','V','max128-cell complex phasor error',errors[-1],.001)],
        analytical_acceptance='lossless modal delay refinement and decoupled scalar limits',stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    print('coupled distributed phasor refinement',errors)
    assert errors[-1]<=.001 and errors[2]<errors[1]<errors[0]


def test_independent_asymmetric_circuit_dop853_kcl():
    require_tool('scipy');from scipy.integrate import solve_ivp
    clock=Stopwatch();n=16;dx=.1/n;weights=np.ones(n+1);weights[[0,-1]]=.5
    r=np.array([[25.,2.],[2.,17.]]);l=np.array([[510.,70.],[70.,430.]])*1e-9
    g=np.array([[.003,-.0002],[-.0002,.0015]]);c=np.array([[230.,-30.],[-30.,190.]])*1e-12
    source=np.array([23.,37.]);load=np.array([91.,113.]);u=np.linspace(0,12,241)
    def drive(t):return np.array([np.interp(t,[0,2],[0,1]),np.interp(t,[0,3],[0,-.4])])
    def rhs(t,x):
        v=x[:2*(n+1)].reshape(n+1,2);i=x[2*(n+1):].reshape(n,2)
        flow=np.zeros_like(v);flow[:-1]-=i;flow[1:]+=i
        flow[0]+=(drive(t)-v[0])/source;flow[-1]-=v[-1]/load
        dv=np.linalg.solve(c,(flow/(dx*weights[:,None])-v@g.T).T).T
        di=np.linalg.solve(l,((v[:-1]-v[1:])/dx-i@r.T).T).T
        return 1e-9*np.r_[dv.ravel(),di.ravel()]
    ce,cu=np.linalg.eigh(c);cs=(cu*np.sqrt(ce))@cu.T
    min_tau=float(.1*np.sqrt(np.linalg.eigvalsh(cs@l@cs)[0])/1e-9)
    with clock('reference'):
        ref=solve_ivp(rhs,[0,12],np.zeros(4*n+2),method='DOP853',t_eval=u,rtol=1e-10,atol=1e-12,max_step=min_tau/(5*n))
    assert ref.success
    with clock('openphysics'):
        actual=run(u*1e-9,np.array([drive(t) for t in u]),R=r,L=l,G=g,C=c,cells=n,source_resistance=source,load_resistance=load)
    expected=ref.y[:2*(n+1)].T.reshape(len(u),n+1,2)[:,[0,n],:].reshape(len(u),4)
    error=float(np.max(abs(expected-actual.voltage)));power_checks(actual)
    record=make_record(case='sipi-coupled-startup-asymmetric-ode',physics='passive asymmetric two-signal finite circuit',
        api='sipi.coupled_rlgc_ladder_response',discretization='16-cell PWL state-space matrix propagation',
        tool='scipy',tool_discretization='separate normalized KCL/inductor equations with DOP853',
        matched=['same16cells,full asymmetric SPD/PSD matrices,unequal resistive ends,two ramps'],
        not_matched=['different propagation algorithms in same library, not independent spatial discretizations'],
        observables=[observable('four port voltage','V','maximum absolute error',error,1e-8)],
        analytical_acceptance='separate modal continuum and scalar limits',stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    assert error<=1e-8


def test_zero_coupling_reduces_to_two_different_scalar_circuits():
    t=np.linspace(0,12e-9,121);drive=np.column_stack((np.minimum(t/2e-9,1.),-.3*np.minimum(t/3e-9,1.)))
    arrays=[np.diag(x) for x in [[20.,0.],[500e-9,400e-9],[.002,0.],[200e-12,250e-12]]]
    source=[25.,37.];load=[100.,80.]
    actual=run(t,drive,R=arrays[0],L=arrays[1],G=arrays[2],C=arrays[3],cells=8,source_resistance=source,load_resistance=load)
    exact=[]
    for k in range(2):
        s=rlgc_ladder_response(t,drive[:,k],R=arrays[0][k,k],L=arrays[1][k,k],G=arrays[2][k,k],C=arrays[3][k,k],length=.1,cells=8,source_resistance=source[k],load_resistance=load[k])
        exact.append(s)
        np.testing.assert_allclose(actual.voltage[:,[k,k+2]],s.voltage,rtol=1e-10,atol=1e-13)
        np.testing.assert_allclose(actual.current[:,[k,k+2]],s.current,rtol=1e-10,atol=1e-15)
    np.testing.assert_allclose(actual.energy,exact[0].energy+exact[1].energy,rtol=1e-10,atol=1e-24)
    power_checks(actual)


def test_dc_resistive_matrix_limit():
    t=np.linspace(0,200e-9,1001);drive=np.column_stack((np.minimum(t/2e-9,1.),-.4*np.minimum(t/2e-9,1.)))
    source=np.array([23.,37.]);load=np.array([91.,113.]);r=run(t,drive,G=np.zeros((2,2)),source_resistance=source,load_resistance=load,cells=8)
    exact_i=np.linalg.solve(np.diag(source+load)+.1*R,drive[-1])
    np.testing.assert_allclose(r.voltage[-1],np.r_[drive[-1]-source*exact_i,load*exact_i],rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(r.current[-1],np.r_[exact_i,-exact_i],rtol=1e-10,atol=1e-14)
    power_checks(r)


def test_permutation_superposition_time_and_impedance_scaling():
    t=np.linspace(0,12e-9,121);a=np.column_stack((np.minimum(t/2e-9,1.),np.zeros(len(t))))
    b=np.column_stack((np.zeros(len(t)),-.4*np.minimum(t/3e-9,1.)))
    source=np.array([23.,37.]);load=np.array([91.,113.]);kw=dict(cells=8,source_resistance=source,load_resistance=load)
    r=run(t,a+b,**kw);ra=run(t,a,**kw);rb=run(t,b,**kw)
    np.testing.assert_allclose(r.voltage,ra.voltage+rb.voltage,rtol=1e-10,atol=1e-13)
    perm=run(t,(a+b)[:,::-1],R=R[::-1,::-1],L=L[::-1,::-1],G=G[::-1,::-1],C=C[::-1,::-1],cells=8,source_resistance=source[::-1],load_resistance=load[::-1])
    np.testing.assert_allclose(perm.voltage,r.voltage[:,[1,0,3,2]],rtol=1e-10,atol=1e-13)
    scaled=run(t*1e6,a+b,L=L*1e6,C=C*1e6,**kw)
    np.testing.assert_allclose(scaled.voltage,r.voltage,rtol=1e-10,atol=1e-13)
    np.testing.assert_allclose(scaled.energy/1e6,r.energy,rtol=1e-10,atol=1e-24)
    z=run(t,a+b,R=R*1e3,L=L*1e3,G=G/1e3,C=C/1e3,cells=8,source_resistance=source*1e3,load_resistance=load*1e3)
    np.testing.assert_allclose(z.voltage,r.voltage,rtol=1e-10,atol=1e-13)
    np.testing.assert_allclose(z.current*1e3,r.current,rtol=1e-10,atol=1e-15)
    power_checks(r);power_checks(perm);power_checks(scaled);power_checks(z)


def test_rank_one_loss_zero_drive_and_readonly_serialization():
    t=np.linspace(0,12e-9,121);drive=np.column_stack((np.minimum(t/2e-9,1.),np.zeros(len(t))))
    r=run(t,drive,R=np.array([[20.,20.],[20.,20.]]),G=np.array([[.002,-.002],[-.002,.002]]),cells=1)
    power_checks(r);saved=r.to_dict();full=r.to_dict(include_states=True)
    assert r.port_names==('near_0','near_1','far_0','far_1')
    assert saved['scope']=='finite-passive-two-signal-rlgc-ladder-startup'
    assert np.shape(full['node_voltage_v'])==(121,2,2) and np.shape(full['segment_current_a'])==(121,1,2)
    assert 'node_voltage_v' not in saved and full['states_included']
    t[:]=9;drive[:]=9;full['input']['cells']=99;full['node_voltage_v'][0][0][0]=99
    assert r.to_dict()==saved and r.node_voltage[0,0,0]==0
    for value in r.__dict__.values():
        if isinstance(value,np.ndarray):assert not value.flags.writeable
    json.dumps(r.to_dict(include_states=True),allow_nan=False)
    with pytest.raises(ValueError):r.to_dict(include_states=1)
    zero=run([0.,1e-9],[[0.,0.],[0.,0.]],cells=1)
    assert zero.power_balance_relative_error==0 and np.all(zero.energy==0) and np.all(zero.voltage==0)


@pytest.mark.parametrize('changes',[
    dict(R=-1),dict(R=[[True,0],[0,1]]),dict(R=[[1,0],[0,-1e-30]]),dict(R=[[1,1e-15],[0,1]]),
    dict(R=np.zeros((3,3))),dict(R=np.array([[1,0],[0,1j]])),dict(R=[[np.inf,0],[0,1]]),
    dict(L=np.zeros((2,2))),dict(L=np.diag([1.,1e-14])),dict(C=np.diag([1.,-1.])),dict(G=-np.eye(2)),
    dict(length=0),dict(length=True),dict(cells=0),dict(cells=129),dict(cells=True),dict(cells=2.),
    dict(source_resistance=[0.,25.]),dict(source_resistance=25.),dict(source_resistance=[True,25.]),
    dict(load_resistance=[-1.,100.]),dict(load_resistance=[None,100.]),dict(load_resistance=[np.inf,100.]),
    dict(load_resistance=[100.,100.,100.]),dict(L=np.eye(2)*1e-320),
    dict(L=np.eye(2)*1e-300,C=np.eye(2)*1e-300,length=1e-300),
])
def test_invalid_matrices_boundaries_or_scales_precede_propagation(changes,monkeypatch):
    monkeypatch.setattr(module,'lsim',lambda *a,**k:pytest.fail('invalid input reached state propagation'))
    with pytest.raises((ValueError,TypeError,np.linalg.LinAlgError)):run(**changes)


@pytest.mark.parametrize('time,drive',[
    ([],[]),([0.],[[0.,0.]]),([1.,2.],[[0.,0.],[1.,0.]]),([0.,0.],[[0.,0.],[1.,0.]]),
    ([0.,1.,3.],[[0.,0.],[1.,0.],[1.,0.]]),([0.,True],[[0.,0.],[1.,0.]]),
    ([0.,1.],[0.,1.]),([0.,1.],[[0.,0.],[1.,True]]),([0.,1.],[[1.,0.],[1.,0.]]),
    ([0.,1.],[[0.,0.],[np.nan,0.]]),([0.,1.,2.],[[0.,0.],[1.7e308,0.],[-1.7e308,0.]]),
    (np.linspace(0,1,10001),np.zeros((10001,2))),
])
def test_invalid_time_drive_precedes_propagation(time,drive,monkeypatch):
    monkeypatch.setattr(module,'lsim',lambda *a,**k:pytest.fail('invalid input reached state propagation'))
    with pytest.raises((ValueError,TypeError)):run(time,drive)


@pytest.mark.parametrize('kind',['shape','nonfinite'])
def test_invalid_state_output_rejected(kind,monkeypatch):
    def fake(system,drive,time,**kw):
        x=np.zeros((len(time),1 if kind=='shape' else system[0].shape[0]))
        if kind=='nonfinite':x[0,0]=np.nan
        return time,np.zeros(len(time)),x
    monkeypatch.setattr(module,'lsim',fake)
    with pytest.raises(ValueError,match='state propagation'):run(cells=1)


def test_pulse_returns_energy_without_clamping_port_power():
    t=np.linspace(0,20e-9,401);pulse=np.interp(t,[0,2e-9,4e-9,6e-9],[0,1,1,0])
    r=run(t,np.column_stack((pulse,-.3*pulse)),R=np.zeros((2,2)),G=np.zeros((2,2)),cells=8)
    tail=t>=6e-9
    assert np.min(r.line_power[tail]) < -1e-4
    assert np.all(r.source_power[tail]==0)
    np.testing.assert_allclose(r.line_power[tail],-r.source_resistor_loss[tail]-r.load_resistor_loss[tail],rtol=1e-12,atol=1e-20)
    assert r.energy[-1]<r.energy[np.flatnonzero(tail)[0]]
    power_checks(r)
