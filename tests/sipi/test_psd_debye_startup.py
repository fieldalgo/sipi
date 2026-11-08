# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""PSD coupled Debye: independent scalar modes, charge KCL and continuous references."""
import json
import importlib.metadata as metadata
from dataclasses import replace
import numpy as np
import pytest
from crosscheck import Stopwatch,emit,make_record,observable,require_tool
from sipi import (debye_rlgc_ladder_response,coupled_rlgc_ladder_response,
    psd_coupled_debye_rlgc_ladder_response,startup_port_waves)
import sipi.psd_debye_startup as module
R=np.array([[20.,3.],[3.,20.]])
L=np.array([[500.,100.],[100.,500.]])*1e-9
G=np.array([[.002,-.0003],[-.0003,.002]])
C=np.array([[220.,-40.],[-40.,220.]])*1e-12
D=np.array([[[150.,-150.],[-150.,150.]],[[50.,50.],[50.,50.]]])*1e-12
F=np.array([1e9,1e8])

Q=np.array([[1.,1.],[1.,-1.]])/np.sqrt(2)


def run(t=None,drive=None,**changes):
    t=np.linspace(0,12e-9,121) if t is None else t
    drive=np.minimum(t/2e-9,1.)[:,None]*[1.,-.4] if drive is None else drive
    kw=dict(R=R,L=L,G=G,C_inf=C,delta_C=D,relaxation_hz=F,length=.1,cells=16,
        source_resistance=[25.,25.],load_resistance=[100.,100.]);kw.update(changes)
    return psd_coupled_debye_rlgc_ladder_response(t,drive,**kw)


def power_checks(a):
    for x in [a.energy,a.polarization_energy,a.total_energy,a.series_loss,a.shunt_loss,a.relaxation_loss,a.source_resistor_loss,a.load_resistor_loss]:
        assert np.all(np.isfinite(x)) and np.min(x)>=0
    assert a.power_balance_relative_error<=1e-10 and a.total_power_balance_relative_error<=1e-10
    np.testing.assert_allclose(a.total_energy_rate,a.line_power-a.series_loss-a.shunt_loss-a.relaxation_loss,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(a.total_energy_rate,a.source_power-a.source_resistor_loss-a.load_resistor_loss-a.series_loss-a.shunt_loss-a.relaxation_loss,rtol=1e-10,atol=1e-12)


def circuit(t,drive,n,*,r=R,l=L,g=G,c=C,delta=D,poles=F,length=.1,rs=(25.,25.),rl=(100.,100.)):
    a=run(t,drive,R=r,L=l,G=g,C_inf=c,delta_C=delta,relaxation_hz=poles,length=length,cells=n,source_resistance=rs,load_resistance=rl);power_checks(a)
    return dict(v=a.voltage,i=a.current,nodev=a.node_voltage,segmenti=a.segment_current,w=a.polarization_voltage,
        energy=a.energy,polarization_energy=a.polarization_energy,relaxation_loss=a.relaxation_loss,
        power_error=a.power_balance_relative_error,total_power_error=a.total_power_balance_relative_error)


def record(clock,case,tool,description,values):
    result=make_record(case=case+'-psd',physics='zero-state passive two-signal Debye circuit',api='sipi.psd_coupled_debye_rlgc_ladder_response',
        discretization='explicit finite pi cells;voltage auxiliary matrix states and PWL propagation',tool=tool,
        tool_discretization=description,matched=['same explicit2x2 RLGCinf/strengths/poles/source/load andtime input'],
        not_matched=['charge-form time integration or continuous distributed modal frequency reference;not measured data'],
        observables=values,analytical_acceptance='decoupled andexchange scalar limits;zero-strength originalcoupled limit',stopwatch=clock)
    result['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(result)

def scalar(t,drive,n,r,l,g,c,delta,poles,rs=25.,rl=100.):
 return debye_rlgc_ladder_response(t,drive,R=r,L=l,G=g,C_inf=c,delta_C=delta,relaxation_hz=poles,length=.1,cells=n,source_resistance=rs,load_resistance=rl)
def frequency_reference(f,n=None):
 modes=[]
 for mode in range(2):
  pick=lambda a:float((Q.T@a@Q)[mode,mode]);om=2*np.pi*f;cap=pick(C)+sum(pick(mat)/(1+1j*f/pole) for mat,pole in zip(D,F));y=pick(G)+1j*om*cap;z=pick(R)+1j*om*pick(L)
  if n is None:
   gamma=np.sqrt(z*y);zc=np.sqrt(z/y);skrf=require_tool("scikit-rf");m=skrf.media.DefinedGammaZ0(frequency=skrf.Frequency.from_f([f],unit='hz'),z0_port=50.,z0=zc,gamma=gamma);aa,bb,cc,dd=m.line(.1,unit='m').a[0].ravel();far=1/(aa+bb/100+25*(cc+dd/100));modes.append([(aa+bb/100)*far,far])
  else:
   dx=.1/n;weights=np.ones(n+1);weights[[0,-1]]=.5;k=np.diag(y*dx*weights).astype(complex);inj=np.zeros(n+1,complex);k[0,0]+=1/25;inj[0]=1/25;k[-1,-1]+=1/100
   for j in range(n):k[j,j]+=1/(z*dx);k[j+1,j+1]+=1/(z*dx);k[j,j+1]-=1/(z*dx);k[j+1,j]-=1/(z*dx)
   modes.append(np.linalg.solve(k,inj)[[0,n]])
 modes=np.array(modes);amplitudes=Q.T@np.array([1.,-.4]);near=Q@(amplitudes*modes[:,0]);far=Q@(amplitudes*modes[:,1]);return np.r_[near,far]
def phasor(f,n,cycles,samples):
 t=np.arange(cycles*samples+1)/(f*samples);drive=np.sin(2*np.pi*f*t)[:,None]*[1.,-.4];a=circuit(t,drive,n);last=slice(-4*samples-1,-1);phase=np.exp(-2j*np.pi*f*t[last]);return 2/len(phase)*(phase@a['v'][last])/(-1j),a

def test_independent_scalar_mode_and_zero_strength_limits():
 report={}
 t=np.linspace(0,12e-9,121);drive=np.minimum(t/2e-9,1.)[:,None]*[1.,-.4];cases=[]
 for basis in [np.eye(2),Q]:
  matrices=[np.diag(np.diag(m)) if np.array_equal(basis,np.eye(2)) else m for m in [R,L,G,C,*D]];r,l,g,c,*delta=matrices;delta=[np.diag([150e-12,0.]),np.diag([0.,50e-12])] if np.array_equal(basis,np.eye(2)) else delta;a=circuit(t,drive,16,r=r,l=l,g=g,c=c,delta=delta);mode_drive=drive@basis;v=[];i=[]
  for mode in range(2):
   pick=lambda m:float((basis.T@m@basis)[mode,mode]);ref=scalar(t,mode_drive[:,mode],16,pick(r),pick(l),pick(g),pick(c),[pick(d) for d in delta],F);v.append(ref.voltage);i.append(ref.current)
  vv=np.stack(v,axis=2)@basis.T;ii=np.stack(i,axis=2)@basis.T;vv=np.concatenate((vv[:,0],vv[:,1]),axis=1);ii=np.concatenate((ii[:,0],ii[:,1]),axis=1)
  ev=float(max(abs(a['v']-vv).ravel()));ei=float(max(abs(a['i']-ii).ravel()));cases.append(dict(basis='diagonal' if np.array_equal(basis,np.eye(2)) else 'exchange',voltage_error=ev,current_error=ei));print('scalar',cases[-1],flush=True);assert ev<=1e-10 and ei<=1e-12
 report['scalar_limits']=cases
 a=circuit(t,drive,16,delta=np.zeros_like(D));ref=coupled_rlgc_ladder_response(t,drive,R=R,L=L,G=G,C=C,length=.1,cells=16,source_resistance=[25.,25.],load_resistance=[100.,100.]);ev=float(max(abs(a['v']-ref.voltage).ravel()));ei=float(max(abs(a['i']-ref.current).ravel()));report['zero_strength']=dict(voltage_error=ev,current_error=ei);assert ev<=1e-10 and ei<=1e-12

def test_independent_noncommuting_charge_kcl():
 require_tool("scipy");from scipy.integrate import solve_ivp
 report={};clock=Stopwatch()
 # Independent noncommuting charge-state equations, no candidate mass/stiffness.
 r=np.array([[25.,2.],[2.,17.]]);l=np.array([[510.,70.],[70.,430.]])*1e-9;g=np.array([[.003,-.0002],[-.0002,.0015]]);c=np.array([[230.,-30.],[-30.,190.]])*1e-12;delta=np.array([[[80.,-40.],[-40.,20.]],[[32.,32.],[32.,32.]]])*1e-12
 rs=np.array([23.,37.]);rl=np.array([91.,113.]);tau=1/(2*np.pi*F);n=16;dx=.1/n;nv=2*(n+1);base=nv+2*n;weights=np.ones(n+1);weights[[0,-1]]=.5;u=np.linspace(0,12,241)
 def drive_u(x):return min(x/2.,1.)*np.array([1.,-.4])
 def dynamics(x,y):
  v=y[:nv].reshape(n+1,2);i=y[nv:base].reshape(n,2);q=y[base:].reshape(n+1,2,2)
  dq=np.empty_like(q)
  for pole,mat in enumerate(delta):dq[:,pole,:]=(v@mat.T-q[:,pole,:])/tau[pole]
  flow=np.zeros_like(v);flow[:-1]-=i;flow[1:]+=i;flow[0]+=(drive_u(x)-v[0])/rs;flow[-1]-=v[-1]/rl
  dv=np.linalg.solve(c,(flow/(dx*weights[:,None])-v@g.T-dq.sum(axis=1)).T).T
  di=np.linalg.solve(l,((v[:-1]-v[1:])/dx-i@r.T).T).T
  return 1e-9*np.r_[dv.ravel(),di.ravel(),dq.ravel()]
 y=np.zeros(base+(n+1)*4);values=np.zeros((len(u),len(y)))
 for left,right in [(0.,2.),(2.,12.)]:
  idx=np.flatnonzero((u>left)&(u<=right))
  with clock('reference'):sol=solve_ivp(dynamics,[left,right],y,method='DOP853',t_eval=u[idx],rtol=1e-11,atol=1e-15,max_step=.005)
  assert sol.success;values[idx]=sol.y.T;y=sol.y[:,-1]
 v=values[:,:nv].reshape(len(u),n+1,2);vv=np.concatenate((v[:,0],v[:,-1]),axis=1);drive=np.array([drive_u(x) for x in u]);ii=np.concatenate(((drive-v[:,0])/rs,-v[:,-1]/rl),axis=1)
 with clock('openphysics'):a=circuit(u*1e-9,drive,n,r=r,l=l,g=g,c=c,delta=delta,rs=rs,rl=rl)
 ev=float(max(abs(a['v']-vv).ravel()));ei=float(max(abs(a['i']-ii).ravel()));report['independent_charge_kcl']=dict(voltage_error=ev,current_error=ei,power_error=a['power_error'],total_power_error=a['total_power_error']);print('kcl',report['independent_charge_kcl'],flush=True);assert ev<=1e-8 and ei<=1e-9
 record(clock,"sipi-coupled-debye-charge-kcl","scipy","separate noncommuting charge-form nodeKCL integrated with DOP853",[observable("terminal voltage","V","maximum absolute error",ev,1e-8),observable("terminal current","A","maximum absolute error",ei,1e-9)])

def test_independent_time_horizon_and_continuous_modal_refinement():
 report={};clock=Stopwatch()
 def measured_phasor(*args):
  with clock('openphysics'):return phasor(*args)
 def measured_reference(*args):
  with clock('reference'):return frequency_reference(*args)
 errors=[]
 for samples in [256,512,1024]:
  ph,a=measured_phasor(1e8,128,8,samples);err=float(max(abs(ph-measured_reference(1e8,128))));errors.append(err);print('time',samples,err,flush=True)
 report['time_refinement']=errors;assert errors[2]<errors[1]<errors[0]
 values=[]
 for cycles in [7,8,9]:ph,a=measured_phasor(1e8,128,cycles,1024);values.append(ph)
 differences=[float(max(abs(values[j+1]-values[j]))) for j in range(2)];report['horizon_differences']=differences;print('horizon',differences,flush=True);assert max(differences)<=1e-8
 rows=[]
 for f,cycles,samples in [(1e8,8,1024),(5e8,20,256),(1e9,20,256)]:
  cases=[];ref=measured_reference(f)
  for n in [32,64,128]:
   ph,a=measured_phasor(f,n,cycles,samples);err=float(max(abs(ph-ref)));cases.append(dict(cells=n,voltage_error=err,power_error=a['power_error'],total_power_error=a['total_power_error']));print('space',f,cases[-1],flush=True)
  rows.append(dict(frequency=f,cycles=cycles,samples=samples,cases=cases));report['continuous_spatial']=rows
  assert cases[2]['voltage_error']<cases[1]['voltage_error']<cases[0]['voltage_error'] and cases[2]['voltage_error']<=.001
 record(clock,"sipi-coupled-debye-modal-continuous","scikit-rf","independent scalar modalABCD andfinitepi frequency solution",[observable("terminal phasor","V","maximum finest-cell error",max(x["cases"][-1]["voltage_error"] for x in rows),.001)])


@pytest.mark.parametrize('strengths,poles',[(D[:1],F[:1]),(np.array([np.zeros((2,2)),D[0]]),F),(D[::-1],F[::-1])])
@pytest.mark.parametrize('rankone_loss',[False,True])
def test_declared_poles_zero_columns_pulse_and_psd_loss(strengths,poles,rankone_loss):
    t=np.linspace(0,12e-9,121);d=(np.minimum(t/2e-9,1.)-np.minimum(np.maximum(t-5e-9,0)/2e-9,1.))[:,None]*[1.,-.4]
    loss=np.array([[1.,-1.],[-1.,1.]]) if rankone_loss else np.zeros((2,2))
    a=run(t,d,R=loss*20,G=loss*.002,delta_C=strengths,relaxation_hz=poles);power_checks(a)
    assert a.polarization_voltage.shape==(121,17,len(poles),2)
    for p,mat in enumerate(strengths):
        if not np.any(mat):assert not np.any(a.polarization_voltage[:,:,p]) and not np.any(a.polarization_charge[:,:,p])
    assert np.any(a.polarization_energy_rate<0)


def test_linear_time_impedance_conductor_and_pole_invariants():
    t=np.linspace(0,12e-9,121);d=np.minimum(t/2e-9,1.)[:,None]*[1.,-.4];a=run(t,d)
    linear=run(t,-2*d);timed=run(3*t,d,L=3*L,C_inf=3*C,delta_C=3*D,relaxation_hz=F/3)
    impedance=run(t,d,R=3*R,L=3*L,G=G/3,C_inf=C/3,delta_C=D/3,source_resistance=[75.,75.],load_resistance=[300.,300.])
    permute=run(t,d,delta_C=D[::-1],relaxation_hz=F[::-1])
    for b,vs,cs,es in [(linear,-2,-2,4),(timed,1,1,3),(impedance,1,1/3,1/3),(permute,1,1,1)]:
        np.testing.assert_allclose(b.voltage,vs*a.voltage,rtol=1e-10,atol=1e-12)
        np.testing.assert_allclose(b.current,cs*a.current,rtol=1e-10,atol=1e-12)
        np.testing.assert_allclose(b.total_energy,es*a.total_energy,rtol=1e-10,atol=1e-22);power_checks(b)
    swapped=run(t,d[:,::-1],R=R[::-1,::-1],L=L[::-1,::-1],G=G[::-1,::-1],C_inf=C[::-1,::-1],delta_C=D[:,::-1,::-1])
    np.testing.assert_allclose(swapped.voltage,a.voltage[:,[1,0,3,2]],rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(permute.polarization_charge,a.polarization_charge[:,:,::-1],rtol=1e-10,atol=1e-22)


def test_detached_readonly_lumped_charge_units_zero_and_no_implicit_wave_admission():
    delta=D.copy();poles=F.copy();t=np.linspace(0,12e-9,121);d=np.minimum(t/2e-9,1.)[:,None]*[1.,-.4]
    a=run(t,d,delta_C=delta,relaxation_hz=poles);delta[:]=0;poles[:]=1;t[:]=9;d[:]=9
    assert a.inputs['delta_C_f_per_m']==D.tolist() and a.inputs['relaxation_hz']==F.tolist() and a.time[0]==0
    for name in ['time','source_voltages','node_voltage','segment_current','voltage','current','polarization_voltage','polarization_charge','polarization_current','total_energy','total_energy_rate']:
        assert not getattr(a,name).flags.writeable
    weights=np.ones(17);weights[[0,-1]]=.5
    for p,mat in enumerate(D):np.testing.assert_allclose(a.polarization_charge[:,:,p],.1/16*weights[None,:,None]*(a.polarization_voltage[:,:,p]@mat.T),rtol=1e-14,atol=0)
    original=a.to_dict();assert original['scope']=='finite-passive-two-signal-psd-debye-ladder-startup'
    assert original['port_names']==['near_0','near_1','far_0','far_1'] and 'polarization_charge_c' not in original
    states=a.to_dict(include_states=True);assert np.array(states['polarization_charge_c']).shape==(121,17,2,2);json.dumps(states,allow_nan=False)
    states['input']['delta_C_f_per_m'][0][0][0]=9;assert a.inputs['delta_C_f_per_m']==D.tolist()
    with pytest.raises(ValueError):a.to_dict(include_states=1)
    with pytest.raises(ValueError):startup_port_waves(a,z_ref=[50.]*4)
    z=run(drive=np.zeros((121,2)));assert not np.any(z.total_energy) and z.power_balance_relative_error==0 and z.total_power_balance_relative_error==0
    with pytest.raises(ValueError):replace(a,polarization_voltage=np.full((121,17,2,2),np.nan))


@pytest.mark.parametrize('kwargs',[
    {'delta_C':[]},{'delta_C':D[0]},{'delta_C':np.array([np.eye(2)]*3)},
    {'delta_C':np.array([[[True,False],[False,True]]])},
    {'delta_C':[[[1.,2.],[2.,1.]]],'relaxation_hz':[1e9]},
    {'delta_C':[[[1.,1.],[0.,1.]]],'relaxation_hz':[1e9]},
    {'delta_C':[[[np.nan,0.],[0.,1.]]],'relaxation_hz':[1e9]},
    {'delta_C':[[['1',0.],[0.,1.]]],'relaxation_hz':[1e9]},
    {'relaxation_hz':[1e9]},{'relaxation_hz':[0.,1e8]},
    {'relaxation_hz':[True,1e8]},{'relaxation_hz':[[1e9,1e8]]},{'relaxation_hz':[np.inf,1e8]},
    {'C_inf':np.zeros((2,2))},{'L':[[1.,1.],[1.,1.]]},
    {'R':[[-1.,0.],[0.,1.]]},{'G':[[1.,2.],[2.,1.]]},
    {'source_resistance':[0.,25.]},{'source_resistance':[None,25.]},
    {'load_resistance':[0.,100.]},{'load_resistance':[None,100.]},
    {'source_resistance':25.},{'load_resistance':[True,100.]},
    {'cells':0},{'cells':129},{'cells':True},{'cells':1.5},{'length':0.},
    {'relaxation_hz':[1e308,1e8]},{'relaxation_hz':[1e-320,1e8]},
    {'C_inf':np.eye(2)*1e-320,'length':1e-100},
    {'delta_C':np.array([np.eye(2)*1e-320]),'relaxation_hz':[1e9],'length':1e-100},
    {'source_resistance':[1e-320,25.]},{'load_resistance':[1e-320,100.]},
])
def test_strict_matrix_pole_boundary_and_finite_scale_contract(kwargs):
    with pytest.raises(ValueError):run(**kwargs)


@pytest.mark.parametrize('t,d',[
    ([0.],[[0.,0.]]),([1.,2.],[[0.,0.],[1.,0.]]),
    ([0.,1.,3.],[[0.,0.],[1.,0.],[1.,0.]]),([0.,1.],[[1.,0.],[1.,0.]]),
    ([0.,1.],[[0.,0.],[True,0.]]),([0.,1.],[0.,1.]),
    (np.linspace(0,1,10001),np.zeros((10001,2))),
])
def test_strict_time_drive_contract(t,d):
    with pytest.raises(ValueError):run(t,d)


@pytest.mark.parametrize('bad',['shape','nan','initial'])
def test_invalid_propagator_output_rejected(monkeypatch,bad):
    original=module.lsim
    def corrupt(*args,**kwargs):
        t,y,x=original(*args,**kwargs)
        if bad=='shape':x=x[:-1]
        elif bad=='nan':x[:]=np.nan
        else:x[0]=1.
        return t,y,x
    monkeypatch.setattr(module,'lsim',corrupt)
    with pytest.raises(ValueError):run()


def test_original_propagation_exception_retained(monkeypatch):
    def fail(*args,**kwargs):raise RuntimeError('matrix propagation failed')
    monkeypatch.setattr(module,'lsim',fail)
    with pytest.raises(RuntimeError,match='matrix propagation failed'):run()


@pytest.mark.parametrize('tiny',[0.,1e-13,1e-20])
def test_rank_one_and_nearly_singular_strength_without_rank_clipping(tiny):
    delta=np.array([np.diag([150e-12,150e-12*tiny])]);a=run(delta_C=delta,relaxation_hz=[1e9]);power_checks(a)
    assert a.inputs['delta_C_f_per_m']==delta.tolist()
    assert np.any(a.polarization_voltage[:,:,:,1])
    if tiny==0:
        assert not np.any(a.polarization_charge[:,:,:,1]) and not np.any(a.polarization_current[:,:,:,1])
    else:
        assert np.any(a.polarization_charge[:,:,:,1]) and np.any(a.polarization_current[:,:,:,1])
    weights=np.ones(17);weights[[0,-1]]=.5
    expected=.1/16*weights[None,:,None]*(a.polarization_voltage[:,:,0]@delta[0].T)
    np.testing.assert_array_equal(a.polarization_charge[:,:,0],expected)


def test_null_mode_auxiliary_voltage_has_no_polarization_energy_or_loss():
    t=np.linspace(0,12e-9,121);d=np.minimum(t/2e-9,1.)[:,None]*[0.,1.]
    delta=np.array([np.diag([150e-12,0.])])
    a=run(t,d,R=np.diag([20.,20.]),L=np.diag([500e-9]*2),G=np.diag([.002]*2),C_inf=np.diag([200e-12]*2),delta_C=delta,relaxation_hz=[1e9])
    assert np.any(a.polarization_voltage[:,:,:,1])
    for name in ['polarization_charge','polarization_current','polarization_energy','polarization_energy_rate','relaxation_loss']:
        assert not np.any(getattr(a,name))
    power_checks(a)


@pytest.mark.parametrize('pulse',[False,True])
def test_positive_strength_limit_matches_original_strict_api_full_states(pulse):
    from sipi import coupled_debye_rlgc_ladder_response as strict
    t=np.linspace(0,12e-9,121);d=np.minimum(t/2e-9,1.)
    if pulse:d-=np.minimum(np.maximum(t-5e-9,0)/2e-9,1.)
    drive=d[:,None]*[1.,-.4];delta=np.array([[[150.,-25.],[-25.,150.]],[[50.,-10.],[-10.,50.]]])*1e-12
    a=run(t,drive,delta_C=delta);b=strict(t,drive,R=R,L=L,G=G,C_inf=C,delta_C=delta,relaxation_hz=F,length=.1,cells=16,source_resistance=[25.,25.],load_resistance=[100.,100.])
    # Voltage/current states use the declared V/A gate; C/J diagnostics use their own scale.
    for name in ['voltage','current','node_voltage','segment_current','polarization_voltage','polarization_current']:
        np.testing.assert_allclose(getattr(a,name),getattr(b,name),rtol=1e-10,atol=1e-12)
    for name in ['polarization_charge','energy','polarization_energy','total_energy']:
        np.testing.assert_allclose(getattr(a,name),getattr(b,name),rtol=1e-10,atol=1e-22)
    assert a.inputs==b.inputs
    from sipi import CoupledDebyeRLGCLadderResponse,PSDCoupledDebyeRLGCLadderResponse
    assert type(a) is PSDCoupledDebyeRLGCLadderResponse and not isinstance(a,CoupledDebyeRLGCLadderResponse)


def test_strict_original_api_still_rejects_rank_one_strength():
    from sipi import coupled_debye_rlgc_ladder_response as strict
    with pytest.raises(ValueError,match='SPD'):
        strict([0.,1e-9],[[0.,0.],[1.,0.]],R=R,L=L,G=G,C_inf=C,delta_C=D,relaxation_hz=F,length=.1,cells=16,source_resistance=[25.,25.],load_resistance=[100.,100.])


@pytest.mark.parametrize('negative',[-1e-13,-1e-20])
def test_negative_strength_is_not_repaired_even_at_tiny_ratio(negative):
    with pytest.raises(ValueError,match='positive semidefinite'):
        run(delta_C=[np.diag([150e-12,150e-12*negative])],relaxation_hz=[1e9])
