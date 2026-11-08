# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Mixed coupled boundaries: mutual capacitance, exact limits and independent ODE."""
import importlib.metadata as metadata
import json

import numpy as np
import pytest
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import coupled_boundary_ladder_response, coupled_rlgc_ladder_response, rlgc_ladder_response, lossless_line_response
import sipi.coupled_boundary_startup as module

R=np.array([[20.,3.],[3.,20.]])
L=np.array([[500.,100.],[100.,500.]])*1e-9
G=np.array([[.002,-.0003],[-.0003,.002]])
C=np.array([[220.,-40.],[-40.,220.]])*1e-12
Q=np.array([[1.,1.],[1.,-1.]])/np.sqrt(2)


def run(time=None,drive=None,**changes):
    time=np.linspace(0,12e-9,121) if time is None else time
    drive=np.column_stack((np.minimum(np.asarray(time)/2e-9,1.),np.zeros(len(time)))) if drive is None else drive
    args=dict(R=R,L=L,G=G,C=C,length=.1,cells=16,source_resistance=[0.,25.],load_resistance=[None,0.])
    args.update(changes);return coupled_boundary_ladder_response(time,drive,**args)


def power_checks(r):
    assert np.min(r.energy)>=0 and np.min(r.series_loss)>=0 and np.min(r.shunt_loss)>=0
    assert r.power_balance_relative_error<=1e-10
    np.testing.assert_allclose(r.energy_rate,r.line_power-r.series_loss-r.shunt_loss,rtol=1e-10,atol=1e-14)
    np.testing.assert_allclose(r.source_power,r.source_resistor_loss+r.load_resistor_loss+r.line_power,rtol=1e-10,atol=1e-14)


def test_positive_boundary_reproduces_existing_coupled_circuit():
    t=np.linspace(0,12e-9,1201);drive=np.column_stack((np.minimum(t/2e-9,1.),np.zeros(len(t))))
    kw=dict(R=R,L=L,G=G,C=C,length=.1,cells=32,source_resistance=[25.,25.],load_resistance=[100.,100.])
    old=coupled_rlgc_ladder_response(t,drive,**kw);r=coupled_boundary_ladder_response(t,drive,**kw)
    assert np.max(abs(r.voltage-old.voltage))<=1e-10 and np.max(abs(r.current-old.current))<=1e-12
    np.testing.assert_allclose(r.node_voltage,old.node_voltage,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(r.segment_current,old.segment_current,rtol=1e-10,atol=1e-14)
    power_checks(r)


@pytest.mark.parametrize('rs,rl',[(0.,0.),(0.,None),(0.,100.),(25.,0.),(25.,None),(25.,100.)])
def test_six_modal_continuum_boundaries_refine(rs,rl):
    t=np.linspace(0,12e-9,1201);modes=[];currents=[]
    for m in range(2):
        lm=(Q.T@L@Q)[m,m];cm=(Q.T@C@Q)[m,m]
        s=lossless_line_response(t,source_times=[0.,2e-9],source_voltages=[0.,Q[0,m]],
            z0_ohm=np.sqrt(lm/cm),delay_s=.1*np.sqrt(lm*cm),source_resistance=rs,load_resistance=rl)
        modes.append(s.voltage);currents.append(s.current)
    v=(np.stack(modes,axis=-1)@Q.T).reshape(len(t),4);i=(np.stack(currents,axis=-1)@Q.T).reshape(len(t),4)
    ev=[];ei=[]
    for n in [32,64,128]:
        r=run(t,R=np.zeros((2,2)),G=np.zeros((2,2)),cells=n,source_resistance=[rs,rs],load_resistance=[rl,rl])
        ev.append(float(np.max(abs(r.voltage-v))));ei.append(float(np.max(abs(r.current-i))));power_checks(r)
    assert ev[-1]<=.02 and ei[-1]<=.0005
    assert max(ev)<1e-14 or ev[2]<ev[1]<ev[0]
    assert ei[2]<ei[1]<ei[0]
    print('mixed coupled modal refinement',rs,rl,ev,ei)


def test_single_cell_exact_coupled_rl_ramp_with_full_endpoint_capacitance():
    t=np.linspace(0,4,401);drive=np.minimum(t,1.)[:,None]*np.array([1.,-.4])
    rmat=np.array([[2.,.5],[.5,2.]]);lmat=np.array([[1.,.2],[.2,1.]]);cmat=np.array([[.4,-.1],[-.1,.4]])
    r=run(t,drive,R=rmat,L=lmat,G=np.zeros((2,2)),C=cmat,length=1.,cells=1,
          source_resistance=[0.,0.],load_resistance=[0.,0.])
    modal=[];amplitude=np.array([1.,-.4])@Q
    for j in range(2):
        rr=(Q.T@rmat@Q)[j,j];ll=(Q.T@lmat@Q)[j,j];tau=ll/rr
        before=amplitude[j]/rr*(t+tau*np.expm1(-t/tau))
        at_one=amplitude[j]/rr*(1+tau*np.expm1(-1/tau))
        after=amplitude[j]/rr+(at_one-amplitude[j]/rr)*np.exp(-(t-1)/tau)
        modal.append(np.where(t<=1,before,after))
    exact=np.stack(modal,axis=-1)@Q.T;slope=np.vstack((np.diff(drive,axis=0)/np.diff(t)[:,None],[0.,0.]))
    np.testing.assert_allclose(r.segment_current[:,0],exact,rtol=1e-11,atol=1e-14)
    np.testing.assert_allclose(r.current[:,:2],exact+.5*slope@cmat.T,rtol=1e-11,atol=1e-14)
    np.testing.assert_allclose(r.current[:,2:],-exact,rtol=1e-11,atol=1e-14)
    energy=.5*np.einsum('ti,ij,tj->t',exact,lmat,exact)+.25*np.einsum('ti,ij,tj->t',drive,cmat,drive)
    np.testing.assert_allclose(r.energy,energy,rtol=1e-11,atol=1e-14);power_checks(r)


def test_partial_ideal_initial_current_uses_schur_capacitance():
    c=np.array([[230.,-30.],[-30.,190.]])*1e-12
    r=run(C=c,cells=16,source_resistance=[0.,37.],load_resistance=[0.,None])
    slope=1/(2e-9);exact=(c[0,0]-c[0,1]*c[1,0]/c[1,1])*(.1/16)/2*slope
    assert r.current[0,0]==pytest.approx(exact,rel=1e-12)
    assert r.current[0,1]==0 and r.current[0,2]==0 and r.current[0,3]==0
    assert not np.isclose(exact,c[0,0]*(.1/16)/2*slope,rtol=1e-3,atol=0)
    power_checks(r)


def test_independent_asymmetric_node_kcl_with_ideal_short_and_open():
    require_tool('scipy');from scipy.integrate import solve_ivp
    clock=Stopwatch();n=16;dx=.1/n;nv=2*(n+1)
    rmat=np.array([[25.,2.],[2.,17.]]);l=np.array([[510.,70.],[70.,430.]])*1e-9
    g=np.array([[.003,-.0002],[-.0002,.0015]]);c=np.array([[230.,-30.],[-30.,190.]])*1e-12
    u=np.linspace(0,12,241);free=np.array([j for j in range(4*n+2) if j not in [0,2*n]])
    def drive(t):return np.array([np.interp(t,[0,2],[0,1]),np.interp(t,[0,3],[0,-.4])])
    def dynamics(t,xf,all_states=False):
        x=np.zeros(4*n+2);x[free]=xf;x[0]=drive(t)[0]
        v=x[:nv].reshape(n+1,2);i=x[nv:].reshape(n,2);dv=np.zeros_like(v)
        flow=np.zeros_like(v);flow[:-1]-=i;flow[1:]+=i;flow[0,1]+=(drive(t)[1]-v[0,1])/37.
        dv[1:-1]=np.linalg.solve(c,(flow[1:-1]/dx-v[1:-1]@g.T).T).T
        dv[0,0]=.5/1e-9 if t<2 else 0.
        dv[0,1]=(flow[0,1]/(dx*.5)-g[1]@v[0]-c[1,0]*dv[0,0])/c[1,1]
        dv[-1,1]=(flow[-1,1]/(dx*.5)-g[1]@v[-1])/c[1,1]
        di=np.linalg.solve(l,((v[:-1]-v[1:])/dx-i@rmat.T).T).T
        derivative=np.r_[dv.ravel(),di.ravel()]
        return (x,derivative) if all_states else 1e-9*derivative[free]
    ce,cu=np.linalg.eigh(c);cs=(cu*np.sqrt(ce))@cu.T;min_tau=float(.1*np.sqrt(np.linalg.eigvalsh(cs@l@cs)[0])/1e-9)
    with clock('reference'):
        ref=solve_ivp(dynamics,[0,12],np.zeros(len(free)),method='DOP853',t_eval=u,rtol=1e-10,atol=1e-12,max_step=min_tau/(5*n))
        assert ref.success
        pairs=[dynamics(t,xf,True) for t,xf in zip(u,ref.y.T)]
        full=np.array([x[0] for x in pairs]);deriv=np.array([x[1] for x in pairs])
        v=full[:,:nv].reshape(len(u),n+1,2);ii=full[:,nv:].reshape(len(u),n,2);dv=deriv[:,:nv].reshape(v.shape)
        ev=v[:,[0,n],:].reshape(len(u),4);ei=np.zeros_like(ev)
        ei[:,0]=(dv[:,0]@c[0]+v[:,0]@g[0])*dx*.5+ii[:,0,0]
        ei[:,1]=(np.array([drive(t)[1] for t in u])-v[:,0,1])/37.
        ei[:,2]=(dv[:,-1]@c[0]+v[:,-1]@g[0])*dx*.5-ii[:,-1,0]
    with clock('openphysics'):
        r=run(u*1e-9,np.array([drive(t) for t in u]),R=rmat,L=l,G=g,C=c,cells=n,source_resistance=[0.,37.],load_resistance=[0.,None])
    verror=float(np.max(abs(r.voltage-ev)));ierror=float(np.max(abs(r.current-ei)));power_checks(r)
    record=make_record(case='sipi-coupled-mixed-boundary-ode',physics='asymmetric passive finite RLGC with mixed ends',
        api='sipi.coupled_boundary_ladder_response',discretization='mass-matrix state transform with PWL matrix propagation',
        tool='scipy',tool_discretization='separate per-node KCL with explicit mutual-C fixed-voltage derivative, DOP853',
        matched=['same16cells,asymmetric matrices,Rs[0,37],RL[0,open],two ramps,zero initial energy'],
        not_matched=['different propagation algorithms in same library and same finite circuit, not independent spatial discretizations'],
        observables=[observable('four port voltage','V','maximum absolute error',verror,1e-8),observable('four port current','A','maximum absolute error',ierror,1e-9)],
        analytical_acceptance='exact coupled1cell RL and initial Schur-capacitance current, six modal continuum refinements',stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    assert verror<=1e-8 and ierror<=1e-9


@pytest.mark.parametrize('source,load',[([0.,0.],[0.,None]),([0.,37.],[100.,0.]),([23.,0.],[None,80.]),([23.,37.],[0.,None])])
def test_decoupled_mixed_ends_match_two_scalar_circuits(source,load):
    t=np.linspace(0,12e-9,121);drive=np.column_stack((np.minimum(t/2e-9,1.),-.4*np.minimum(t/3e-9,1.)))
    arrays=[np.diag(x) for x in [[20.,0.],[500e-9,400e-9],[.002,0.],[200e-12,250e-12]]]
    r=run(t,drive,R=arrays[0],L=arrays[1],G=arrays[2],C=arrays[3],cells=8,source_resistance=source,load_resistance=load)
    for j in range(2):
        s=rlgc_ladder_response(t,drive[:,j],R=arrays[0][j,j],L=arrays[1][j,j],G=arrays[2][j,j],C=arrays[3][j,j],length=.1,cells=8,source_resistance=source[j],load_resistance=load[j])
        np.testing.assert_allclose(r.voltage[:,[j,j+2]],s.voltage,rtol=1e-10,atol=1e-12)
        np.testing.assert_allclose(r.current[:,[j,j+2]],s.current,rtol=1e-10,atol=1e-14)
    power_checks(r)


def test_mixed_permutation_time_impedance_scaling_and_copies():
    t=np.linspace(0,12e-9,121);drive=np.column_stack((np.minimum(t/2e-9,1.),-.4*np.minimum(t/3e-9,1.)))
    l=L.copy();l[0,0]+=50e-9;c=C.copy();c[0,0]+=30e-12
    kw=dict(L=l,C=c,cells=8,source_resistance=[0.,37.],load_resistance=[0.,None]);r=run(t,drive,**kw)
    swapped=run(t,drive[:,::-1],R=R[::-1,::-1],L=l[::-1,::-1],G=G[::-1,::-1],C=c[::-1,::-1],cells=8,source_resistance=[37.,0.],load_resistance=[None,0.])
    np.testing.assert_allclose(swapped.voltage,r.voltage[:,[1,0,3,2]],rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(swapped.current,r.current[:,[1,0,3,2]],rtol=1e-10,atol=1e-14)
    scaled=run(t*1e6,drive,**dict(kw,L=l*1e6,C=c*1e6))
    np.testing.assert_allclose(scaled.voltage,r.voltage,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(scaled.energy/1e6,r.energy,rtol=1e-10,atol=1e-23)
    z=run(t,drive,R=R*1e3,G=G/1e3,**dict(kw,L=l*1e3,C=c/1e3,source_resistance=[0.,37e3]))
    np.testing.assert_allclose(z.voltage,r.voltage,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(z.current*1e3,r.current,rtol=1e-10,atol=1e-14)
    saved=r.to_dict();full=r.to_dict(include_states=True)
    t[:]=9;drive[:]=9;l[:]=9;c[:]=9;full['input']['load_resistance_ohm'][1]=999
    assert saved==r.to_dict() and r.inputs['load_resistance_ohm']==[0.,None]
    assert saved['scope']=='finite-passive-two-signal-mixed-boundary-rlgc-startup'
    assert np.shape(full['node_voltage_v'])==(121,9,2)
    for value in r.__dict__.values():
        if isinstance(value,np.ndarray):assert not value.flags.writeable
    json.dumps(saved,allow_nan=False)
    with pytest.raises(ValueError):r.to_dict(include_states=1)
    for value in [r,swapped,scaled,z]:power_checks(value)


def test_zero_drive_and_negative_return_power():
    zero=run([0.,1e-9],[[0.,0.],[0.,0.]],cells=1,source_resistance=[0.,0.],load_resistance=[None,None])
    assert zero.power_balance_relative_error==0 and np.all(zero.energy==0)
    t=np.linspace(0,20e-9,401);pulse=np.interp(t,[0,2e-9,4e-9,6e-9],[0,1,1,0])
    r=run(t,np.column_stack((pulse,-.3*pulse)),R=np.zeros((2,2)),G=np.zeros((2,2)),cells=8,source_resistance=[25.,25.],load_resistance=[None,0.])
    assert np.min(r.line_power[t>=6e-9]) < -1e-4
    power_checks(r)


@pytest.mark.parametrize('changes',[
    dict(source_resistance=0.),dict(source_resistance=None),dict(source_resistance=[0.,None]),
    dict(source_resistance=[-1.,25.]),dict(source_resistance=[True,25.]),dict(source_resistance=[np.inf,25.]),
    dict(load_resistance=None),dict(load_resistance=100.),dict(load_resistance=[None]),
    dict(load_resistance=[None,None,None]),dict(load_resistance=[-1.,None]),dict(load_resistance=[True,None]),
    dict(load_resistance=[np.inf,None]),dict(load_resistance=[1j,None]),dict(load_resistance=['open',None]),
    dict(R=-np.eye(2)),dict(C=np.zeros((2,2))),dict(cells=0),dict(cells=129),
    dict(L=np.eye(2)*1e-300,C=np.eye(2)*1e-300,length=1e-300),dict(source_resistance=[1e-320,1.]),
])
def test_invalid_control_or_coefficients_precede_propagation(changes,monkeypatch):
    monkeypatch.setattr(module,'lsim',lambda *a,**k:pytest.fail('invalid input reached propagation'))
    with pytest.raises((ValueError,TypeError)):run(**changes)


@pytest.mark.parametrize('time,drive',[
    ([0.],[[0.,0.]]),([0.,True],[[0.,0.],[1.,0.]]),([0.,1.,3.],[[0.,0.],[1.,0.],[1.,0.]]),
    ([0.,1.],[[1.,0.],[1.,0.]]),([0.,1.],[[0.,0.],[1.,True]]),
    ([0.,1.,2.],[[0.,0.],[1.7e308,0.],[-1.7e308,0.]]),
])
def test_invalid_drive_or_grid_precedes_propagation(time,drive,monkeypatch):
    monkeypatch.setattr(module,'lsim',lambda *a,**k:pytest.fail('invalid input reached propagation'))
    with pytest.raises((ValueError,TypeError)):run(time,drive)


@pytest.mark.parametrize('kind',['shape','nonfinite'])
def test_invalid_state_is_rejected(kind,monkeypatch):
    def fake(system,drive,time,**kw):
        x=np.zeros((len(time),1 if kind=='shape' else system[0].shape[0]))
        if kind=='nonfinite':x[0,0]=np.nan
        return time,np.zeros(len(time)),x
    monkeypatch.setattr(module,'lsim',fake)
    with pytest.raises(ValueError,match='state propagation'):run(cells=1)
