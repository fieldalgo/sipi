# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit Debye states: analytical relaxation, charge KCL and continuous lines."""
import json
import importlib.metadata as metadata
from dataclasses import replace
import numpy as np
import pytest
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import debye_rlgc_ladder_response, rlgc_ladder_response, startup_port_waves
from sipi.dielectric import DebyeDielectric
import sipi.debye_startup as module


def run(t=None,drive=None,**changes):
    t=np.linspace(0.,12e-9,121) if t is None else t
    drive=np.minimum(t/2e-9,1.) if drive is None else drive
    kwargs=dict(R=20.,L=500e-9,G=.002,C_inf=200e-12,delta_C=[150e-12,50e-12],
        relaxation_hz=[1e9,1e8],length=.1,cells=16,source_resistance=25.,load_resistance=100.)
    kwargs.update(changes)
    return debye_rlgc_ladder_response(t,drive,**kwargs)


def power_checks(a):
    for x in (a.energy,a.polarization_energy,a.total_energy,a.series_loss,a.shunt_loss,a.relaxation_loss,a.source_resistor_loss,a.load_resistor_loss):
        assert np.min(x)>=0 and np.all(np.isfinite(x))
    assert a.power_balance_relative_error<=1e-10 and a.total_power_balance_relative_error<=1e-10
    np.testing.assert_allclose(a.total_energy_rate,a.line_power-a.series_loss-a.shunt_loss-a.relaxation_loss,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(a.total_energy_rate,a.source_power-a.source_resistor_loss-a.load_resistor_loss-a.series_loss-a.shunt_loss-a.relaxation_loss,rtol=1e-10,atol=1e-12)


def circuit(t,drive,n,*,r=20.,l=500e-9,g=.002,cinf=200e-12,strengths=(150e-12,50e-12),poles=(1e9,1e8),length=.1,rs=25.,rl=100.):
    a=run(t,drive,R=r,L=l,G=g,C_inf=cinf,delta_C=strengths,relaxation_hz=poles,length=length,cells=n,source_resistance=rs,load_resistance=rl)
    power_checks(a)
    return dict(v=a.voltage,i=a.current,nodev=a.node_voltage,segmenti=a.segment_current,w=a.polarization_voltage,
        energy=a.energy,polarization_energy=a.polarization_energy,polarization_rate=a.polarization_energy_rate,
        relaxation_loss=a.relaxation_loss,power_error=a.power_balance_relative_error,total_power_error=a.total_power_balance_relative_error)


def record(clock,case,tool,description,values):
    result=make_record(case=case,physics='zero-state passive scalar Debye line circuit',api='sipi.debye_rlgc_ladder_response',
        discretization='explicit finite pi cells; voltage auxiliary states and PWL matrix propagation',tool=tool,
        tool_discretization=description,matched=['same explicit R/L/G/Cinf/strengths/poles/length/source/load'],
        not_matched=['independent charge KCL or continuous distributed frequency model; no measured material claim'],
        observables=values,analytical_acceptance='single-cell exact relaxation and series L; zero-strength constant-RLGC limit',stopwatch=clock)
    result['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(result)


def test_independent_analytic():
 report={}
 t=np.linspace(0.,4.,801);drive=np.minimum(t,1.);delta=.3;tau=.4;shift=np.maximum(t-1,0.)
 a=circuit(t,drive,1,r=0.,l=1.,g=0.,cinf=.4,strengths=[0.,.6,0.],poles=[1.,1/(2*np.pi*tau),2.],length=1.,rs=0.,rl=0.)
 q=delta*(t-tau*(1-np.exp(-t/tau))-shift+tau*(1-np.exp(-shift/tau)));dq=delta*(np.exp(-shift/tau)-np.exp(-t/tau));iline=.5*(t*t-shift*shift);dv=np.where(t<1.,1.,0.)
 vv=np.column_stack((drive,np.zeros(len(t))));ii=np.column_stack((.2*dv+dq+iline,-iline));energy=.2*drive**2/2+.5*iline**2;pe=.5*q*q/delta;loss=tau/delta*dq*dq
 for actual,expected in [(a['v'],vv),(a['i'],ii),(a['energy'],energy),(a['polarization_energy'],pe),(a['relaxation_loss'],loss)]:np.testing.assert_allclose(actual,expected,rtol=1e-10,atol=1e-12)
 assert not np.any(a['w'][:,:,[0,2]])
 report['analytic']=dict(voltage_error=float(np.max(abs(a['v']-vv))),current_error=float(np.max(abs(a['i']-ii))),power_error=a['power_error'],total_power_error=a['total_power_error']);print('analytic',report['analytic'],flush=True)

def test_independent_zero():
 report={}
 t=np.linspace(0.,12e-9,121);drive=np.minimum(t/2e-9,1.);zero=[]
 for rs,rl in [(25.,100.),(0.,None),(0.,0.)]:
  a=circuit(t,drive,16,strengths=[0.,0.],rs=rs,rl=rl);ref=rlgc_ladder_response(t,drive,R=20.,L=500e-9,G=.002,C=200e-12,length=.1,cells=16,source_resistance=rs,load_resistance=rl)
  ev=float(np.max(abs(a['v']-ref.voltage)));ei=float(np.max(abs(a['i']-ref.current)));assert ev<=1e-10 and ei<=1e-12
  assert not np.any(a['polarization_energy']) and not np.any(a['relaxation_loss']);zero.append(dict(source=rs,load=rl,voltage_error=ev,current_error=ei))
 report['zero_strength']=zero;print('zero',zero,flush=True)

def test_independent_kcl():
 report={}
 require_tool("scipy");from scipy.integrate import solve_ivp
 clock=Stopwatch()
 # Independent charge-form node KCL; does not use candidate mass/stiffness.
 n=16;dx=.1/n;nv=n+1;weights=np.ones(nv);weights[[0,-1]]=.5;u=np.linspace(0.,12.,241);rows=[]
 for strengths,poles,rs,rl in [([150e-12],[1e9],0.,0.),([150e-12,50e-12],[1e9,1e8],25.,100.),([150e-12,50e-12],[1e9,1e8],0.,None)]:
  strengths=np.array(strengths);tau=1/(2*np.pi*np.array(poles));npoles=len(strengths);fixed=([0] if rs==0 else [])+([n] if rl==0 else []);free=np.array([j for j in range(nv) if j not in fixed]);nf=len(free)
  def drive_u(x):return min(x/2.,1.)
  def decode(x,y):
   v=np.zeros(nv);v[free]=y[:nf]
   if rs==0:v[0]=drive_u(x)
   return v,y[nf:nf+n],y[nf+n:].reshape(nv,npoles)
  def dynamics(x,y,full=False):
   v,i,q=decode(x,y);dq=(v[:,None]*strengths[None,:]-q)/tau[None,:]
   flow=np.zeros(nv);flow[:-1]-=i;flow[1:]+=i
   if rs>0:flow[0]+=(drive_u(x)-v[0])/rs
   if rl is not None and rl>0:flow[-1]-=v[-1]/rl
   dv=(flow/(dx*weights)-.002*v-dq.sum(axis=1))/200e-12
   if rs==0:dv[0]=.5e9 if x<2. else 0.
   if rl==0:dv[-1]=0.
   di=((v[:-1]-v[1:])/dx-20*i)/500e-9
   if full:return v,i,q,dv,dq,di
   return 1e-9*np.r_[dv[free],di,dq.ravel()]
  y=np.zeros(nf+n+nv*npoles);values=np.zeros((len(u),len(y)))
  for left,right in [(0.,2.),(2.,12.)]:
   idx=np.flatnonzero((u>left)&(u<=right))
   with clock('reference'):sol=solve_ivp(dynamics,[left,right],y,method='DOP853',t_eval=u[idx],rtol=1e-11,atol=1e-15,max_step=.005)
   assert sol.success;values[idx]=sol.y.T;y=sol.y[:,-1]
  full=[dynamics(x,y,True) for x,y in zip(u,values)];v=np.array([z[0] for z in full]);ii=np.array([z[1] for z in full]);dv=np.array([z[3] for z in full]);dq=np.array([z[4] for z in full])
  near=dx*.5*(200e-12*dv[:,0]+.002*v[:,0]+dq[:,0].sum(axis=1))+ii[:,0];far=dx*.5*(200e-12*dv[:,-1]+.002*v[:,-1]+dq[:,-1].sum(axis=1))-ii[:,-1]
  with clock('openphysics'):a=circuit(u*1e-9,np.array([drive_u(x) for x in u]),n,strengths=strengths,poles=poles,rs=rs,rl=rl)
  ev=float(np.max(abs(a['v']-v[:,[0,n]])));ei=float(np.max(abs(a['i']-np.column_stack((near,far)))))
  row=dict(poles=len(strengths),source=rs,load=rl,voltage_error=ev,current_error=ei,power_error=a['power_error'],total_power_error=a['total_power_error']);rows.append(row);report['independent_kcl']=rows;print('kcl',row,flush=True);assert ev<=1e-8 and ei<=1e-9
 record(clock,"sipi-debye-startup-kcl","scipy","separate node KCL with polarization charge and DOP853",[observable("terminal voltage","V","maximum absolute difference",max(x["voltage_error"] for x in rows),1e-8),observable("terminal current","A","maximum absolute difference",max(x["current_error"] for x in rows),1e-9)])

def test_independent_material():
 report={}
 # Same causal capacitance as the qualified frequency-only material formula.
 material=DebyeDielectric(2.,(1.5,.5),(1e9,1e8));frequencies=np.array([0.,1e8,5e8,1e9]);direct=200e-12+sum(d/(1+1j*frequencies/fp) for d,fp in zip([150e-12,50e-12],[1e9,1e8]))
 np.testing.assert_allclose(100e-12*material.permittivity(frequencies),direct,rtol=1e-13,atol=0.);report['material_capacitance_error_f_per_m']=float(np.max(abs(100e-12*material.permittivity(frequencies)-direct)))

def frequency_reference(f,n=None):
 om=2*np.pi*f;cap=200e-12+150e-12/(1+1j*f/1e9)+50e-12/(1+1j*f/1e8);y=.002+1j*om*cap;z=20+1j*om*500e-9
 if n is not None:
  dx=.1/n;weights=np.ones(n+1);weights[[0,-1]]=.5;k=np.diag(y*dx*weights).astype(complex);inj=np.zeros(n+1,complex);k[0,0]+=1/25;inj[0]=1/25;k[-1,-1]+=1/100
  for j in range(n):k[j,j]+=1/(z*dx);k[j+1,j+1]+=1/(z*dx);k[j,j+1]-=1/(z*dx);k[j+1,j]-=1/(z*dx)
  return np.linalg.solve(k,inj)[[0,n]]
 gamma=np.sqrt(z*y);zc=np.sqrt(z/y);skrf=require_tool("scikit-rf");media=skrf.media.DefinedGammaZ0(frequency=skrf.Frequency.from_f([f],unit='hz'),z0_port=50.,z0=zc,gamma=gamma);aa,bb,cc,dd=media.line(.1,unit='m').a[0].ravel();vl=1/(aa+bb/100+25*(cc+dd/100));return np.array([(aa+bb/100)*vl,vl])
def phasor_run(f,n,cycles,samples):
 t=np.arange(cycles*samples+1)/(f*samples);a=circuit(t,np.sin(2*np.pi*f*t),n);last=slice(-4*samples-1,-1);phase=np.exp(-2j*np.pi*f*t[last]);return 2/len(phase)*(phase@a['v'][last])/(-1j),a

def test_independent_time_horizon_and_continuous_space_refinement():
 report={};clock=Stopwatch()
 def measured_run(*args):
  with clock('openphysics'):return phasor_run(*args)
 def measured_reference(*args):
  with clock('reference'):return frequency_reference(*args)
 # Sample refinement against independent finite circuit; separate from spatial criterion.
 vals=[]
 for samples in [256,512,1024]:
  ph,a=measured_run(1e8,128,8,samples);err=float(max(abs(ph-measured_reference(1e8,128))));vals.append(err);print('sample',samples,err,flush=True)
 assert vals[2]<vals[1]<vals[0];report['sample_refinement_finite_circuit']=dict(samples=[256,512,1024],errors=vals)
 vals=[]
 for cycles in [7,8,9]:
  ph,a=measured_run(1e8,128,cycles,1024);vals.append(ph);print('horizon',cycles,ph,flush=True)
 diff=[float(max(abs(vals[j+1]-vals[j]))) for j in range(2)];report['horizon_stability']=dict(cycles=[7,8,9],maximum_voltage_differences=diff,gate_v=1e-8);print('horizon differences',diff,flush=True);assert max(diff)<=1e-8
 rows=[]
 for f,cycles,samples in [(1e8,8,1024),(5e8,20,256),(1e9,20,256)]:
  cases=[];ref=measured_reference(f)
  for n in [32,64,128]:
   ph,a=measured_run(f,n,cycles,samples);err=float(max(abs(ph-ref)));ferr=float(max(abs(measured_reference(f,n)-ref)));cases.append(dict(cells=n,voltage_error=err,independent_finite_circuit_error=ferr,power_error=a['power_error'],total_power_error=a['total_power_error']));print('space',f,cases[-1],flush=True)
  rows.append(dict(frequency=f,cycles=cycles,samples=samples,cases=cases));report['continuous_spatial']=rows
  assert cases[2]['voltage_error']<cases[1]['voltage_error']<cases[0]['voltage_error'] and cases[2]['voltage_error']<=.001
  assert cases[2]['independent_finite_circuit_error']<cases[1]['independent_finite_circuit_error']<cases[0]['independent_finite_circuit_error']
 record(clock,"sipi-debye-startup-continuous","scikit-rf","continuous distributed Debye ABCD with explicit source interpolation and independent finite nodal reference",[observable("terminal phasor","V","maximum finest-cell error",max(x["cases"][-1]["voltage_error"] for x in rows),.001)])


@pytest.mark.parametrize('rs,rl',[(0.,0.),(0.,None),(0.,100.),(25.,0.),(25.,None),(25.,100.)])
@pytest.mark.parametrize('pulse',[False,True])
def test_boundaries_four_poles_and_energy(rs,rl,pulse):
    t=np.linspace(0,12e-9,241);d=np.minimum(t/2e-9,1.)
    if pulse:d-=np.minimum(np.maximum(t-5e-9,0)/2e-9,1.)
    a=run(t,d,delta_C=[0.,75e-12,75e-12,50e-12],relaxation_hz=[2e9,1e9,1e9,1e8],source_resistance=rs,load_resistance=rl)
    b=run(t,d,source_resistance=rs,load_resistance=rl)
    np.testing.assert_allclose(a.voltage,b.voltage,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(a.current,b.current,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(a.total_energy,b.total_energy,rtol=1e-10,atol=1e-22)
    assert not np.any(a.polarization_voltage[:,:,0]);power_checks(a)
    if rs==0:np.testing.assert_array_equal(a.voltage[:,0],d)
    if rl==0:assert not np.any(a.voltage[:,1])
    if rl is None:assert not np.any(a.current[:,1])


def test_linear_time_impedance_and_pole_permutation_invariants():
    t=np.linspace(0,12e-9,121);d=np.minimum(t/2e-9,1.);a=run(t,d)
    linear=run(t,-2*d);shift=run(3*t,d,L=1500e-9,C_inf=600e-12,delta_C=[450e-12,150e-12],relaxation_hz=[1e9/3,1e8/3])
    impedance=run(t,d,R=60.,L=1500e-9,G=.002/3,C_inf=200e-12/3,delta_C=[50e-12,50e-12/3],source_resistance=75.,load_resistance=300.)
    permute=run(t,d,delta_C=[50e-12,150e-12],relaxation_hz=[1e8,1e9])
    for b,vs,cs,es in [(linear,-2,-2,4),(shift,1,1,3),(impedance,1,1/3,1/3),(permute,1,1,1)]:
        np.testing.assert_allclose(b.voltage,vs*a.voltage,rtol=1e-10,atol=1e-12)
        np.testing.assert_allclose(b.current,cs*a.current,rtol=1e-10,atol=1e-12)
        np.testing.assert_allclose(b.total_energy,es*a.total_energy,rtol=1e-10,atol=1e-22);power_checks(b)
    np.testing.assert_allclose(permute.polarization_charge,a.polarization_charge[:,:,::-1],rtol=1e-10,atol=1e-22)


def test_copies_units_json_zero_and_explicit_wave_admission():
    t=np.linspace(0,12e-9,121);d=np.minimum(t/2e-9,1.);delta=np.array([150e-12,50e-12]);f=np.array([1e9,1e8]);a=run(t,d,delta_C=delta,relaxation_hz=f)
    t[:]=7;d[:]=7;delta[:]=7;f[:]=7
    assert a.inputs['delta_C_f_per_m']==[150e-12,50e-12] and a.time[0]==0
    for name in ('time','source_voltages','node_voltage','segment_current','voltage','current','energy','polarization_voltage','polarization_charge','polarization_current','total_energy','total_energy_rate'):
        assert not getattr(a,name).flags.writeable
    copy=a.inputs;copy['delta_C_f_per_m'][0]=7;assert a.inputs['delta_C_f_per_m'][0]==150e-12
    out=a.to_dict();assert 'polarization_charge_c' not in out
    states=a.to_dict(include_states=True);assert np.array(states['polarization_charge_c']).shape==(121,17,2)
    dx=.1/16;weights=np.ones(17);weights[[0,-1]]=.5
    np.testing.assert_allclose(a.polarization_charge,a.polarization_voltage*dx*weights[None,:,None]*np.array([150e-12,50e-12]),rtol=1e-14,atol=0)
    json.dumps(states,allow_nan=False)
    with pytest.raises(ValueError):a.to_dict(include_states=1)
    assert startup_port_waves(a,z_ref=[50.,50.]).source_kind=='DebyeRLGCLadderResponse'
    z=run(drive=np.zeros(121));assert not np.any(z.total_energy) and z.power_balance_relative_error==0
    assert z.total_power_balance_relative_error==0
    with pytest.raises(ValueError):replace(a,polarization_voltage=np.full((121,17,2),np.nan))


@pytest.mark.parametrize('kwargs',[
    {'delta_C':[]},{'delta_C':[1e-12]*5,'relaxation_hz':[1e9]*5},
    {'delta_C':[-1e-12,0.]},{'delta_C':[True,0.]},{'delta_C':['1',0.]},
    {'delta_C':[np.nan,0.]},{'delta_C':[[1e-12,0.]]},{'delta_C':1e-12},
    {'relaxation_hz':[0.,1e8]},{'relaxation_hz':[-1.,1e8]},
    {'relaxation_hz':[np.inf,1e8]},{'relaxation_hz':[True,1e8]},
    {'relaxation_hz':[1e9]},{'relaxation_hz':[[1e9,1e8]]},
    {'C_inf':0.},{'C_inf':True},{'G':-1.},{'R':-1.},{'L':0.},
    {'cells':0},{'cells':129},{'cells':True},{'cells':1.5},
    {'length':0.},{'source_resistance':None},{'source_resistance':-1.},
    {'load_resistance':np.inf},{'load_resistance':-1.},
    {'delta_C':[1e308,1.]},{'relaxation_hz':[1e308,1e8]},
    {'relaxation_hz':[1e-320,1e8]},{'C_inf':1e-320,'length':1e-100},
    {'delta_C':[1e-320,0.],'length':1e-100},
    {'source_resistance':1e-320},{'load_resistance':1e-320}])
def test_strict_inputs_and_finite_coefficients(kwargs):
    with pytest.raises(ValueError):run(**kwargs)


@pytest.mark.parametrize('t,d',[
    ([0.],[0.]),([1.,2.],[0.,1.]),([0.,1.,3.],[0.,1.,1.]),
    ([0.,1.],[1.,1.]),([0.,1.],[0.,np.nan]),([0.,1.],[0.,True]),
    ([0.,1.],[[0.],[1.]]),(np.linspace(0,1,10001),np.zeros(10001))])
def test_strict_time_and_drive(t,d):
    with pytest.raises(ValueError):run(t,d)


@pytest.mark.parametrize('bad',['shape','nan','initial-state'])
def test_propagation_failures_are_rejected(monkeypatch,bad):
    original=module.lsim
    def corrupt(*args,**kwargs):
        t,y,x=original(*args,**kwargs)
        if bad=='shape':x=x[:-1]
        elif bad=='nan':x[:]=np.nan
        else:x[:]=0.;x[0]=1.
        return t,y,x
    monkeypatch.setattr(module,'lsim',corrupt)
    with pytest.raises(ValueError):run()


def test_propagation_exception_is_not_replaced(monkeypatch):
    def fail(*args,**kwargs):raise RuntimeError('propagation failed')
    monkeypatch.setattr(module,'lsim',fail)
    with pytest.raises(RuntimeError,match='propagation failed'):run()
