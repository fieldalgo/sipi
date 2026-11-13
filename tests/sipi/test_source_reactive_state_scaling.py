# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Current/mixed boundaries preserve independently integrated branch-free flux."""
import pytest
from scipy.integrate import simpson
from sipi import psd_multiconductor_debye_norton_reactive_ladder_response as norton
from sipi import psd_multiconductor_debye_mixed_reactive_ladder_response as mixed
from sipi import psd_multiconductor_debye_capacitive_ladder_response as capacitive
import numpy as np
from scipy.integrate import solve_ivp
from test_multiconductor_debye_reactive_startup import modal_data,amp

def inputs(signals,kind,pulse):
 *_,m=modal_data(signals)
 m['load_capacitance']=np.zeros((signals,signals));m['load_branch_resistance']=np.zeros((signals,signals))
 t=np.linspace(0,12e-9,481);d=wave(t,pulse)[:,None]*amp(signals)
 opts=dict(signals=signals,length=.1,cells=16,load_resistance=np.full(signals,100.))
 gs=np.full(signals,.04)
 if kind.endswith('zero'):gs[:]=0
 if kind.startswith('mixed'):gs[1::2]=.04
 return t,d,m,opts,gs

def wave(t,pulse):
 v=np.minimum(t/2e-9,1.)
 if pulse:v=v-np.minimum(np.maximum(t-5e-9,0)/2e-9,1.)
 return v

def branch_call(function,t,d,m,opts,gs,kind):
 if kind.startswith('norton'):return function(t,.04*d,**m,**opts,source_shunt_conductance=gs)
 sources=[dict(kind='voltage',voltage_v=d[:,j],series_resistance_ohm=25.) if j%2 else dict(kind='current',current_a=.04*d[:,j],shunt_conductance_s=gs[j]) for j in range(opts['signals'])]
 return function(t,sources,**m,**opts)

def flux_reference(signals,m,opts,gs,pulse,rtol):
 # Independently assemble a branch-free finite-pi circuit in physical
 # equations; integrate using DOP853 in ns with 50-ohm current scaling.
 n=opts['cells'];dx=opts['length']/n;nv=(n+1)*signals;ni=n*signals
 weights=np.full(n+1,dx);weights[[0,-1]]*=.5
 cinv=np.linalg.inv(m['C_inf']);linv=np.linalg.inv(m['L']*dx)
 tau=1/(2*np.pi*m['relaxation_hz']);poles=len(tau)
 base=nv+ni;size=base+poles*nv+signals
 def derivative(tns,y):
  v=y[:nv].reshape(n+1,signals);i=y[nv:base].reshape(n,signals)/50
  w=y[base:base+poles*nv].reshape(poles,n+1,signals)
  out=-weights[:,None]*(v@m['G'].T)
  out[:-1]-=i;out[1:]+=i
  out[0]+=.04*wave(tns*1e-9,pulse)*amp(signals)-gs*v[0]
  out[-1]-=v[-1]/opts['load_resistance']
  wd=(v[None,:,:]-w)/tau[:,None,None]
  for k in range(poles):out-=weights[:,None]*(wd[k]@m['delta_C'][k].T)
  vd=(out@cinv.T)/weights[:,None]
  ider=(v[:-1]-v[1:]-dx*(i@m['R'].T))@linv.T
  return np.r_[vd.ravel()*1e-9,ider.ravel()*50e-9,wd.ravel()*1e-9,v[-1]]
 y=np.zeros(size);points=[0.,2.,5.,7.,12.] if pulse else [0.,2.,12.]
 evaluations=0
 for lo,hi in zip(points[:-1],points[1:]):
  sol=solve_ivp(derivative,(lo,hi),y,method='DOP853',rtol=rtol,atol=rtol*.01)
  assert sol.success;assert np.all(np.isfinite(sol.y));y=sol.y[:,-1];evaluations+=sol.nfev
 return y[-signals:]*1e-9,evaluations


@pytest.fixture(scope='module',params=[(n,k,p) for n in [3,4] for k in ['norton-positive','norton-zero','mixed-positive','mixed-zero'] for p in [False,True]],ids=lambda p:f'{p[0]}-{p[1]}-{"pulse" if p[2] else "ramp"}')
def reference_case(request):
 n,kind,pulse=request.param;t,d,m,opts,gs=inputs(n,kind,pulse)
 coarse,_=flux_reference(n,m,opts,gs,pulse,1e-9)
 flux,_=flux_reference(n,m,opts,gs,pulse,1e-11)
 np.testing.assert_allclose(coarse,flux,rtol=1e-7,atol=0)
 if kind.endswith('positive'):
  ref=capacitive(t,d,**{k:v for k,v in m.items() if not k.startswith('load_branch_')},**opts,source_resistance=np.full(n,25.))
  integrated=simpson(ref.voltage[:,n:],x=t,axis=0)
  np.testing.assert_allclose(integrated,flux,rtol=1e-5,atol=0)
 return t,d,m,opts,gs,kind,flux


@pytest.mark.parametrize('inductance',[1e6,1e7,1e8])
def test_large_inductance_against_independent_branch_free_ode(reference_case,inductance,record_property):
 t,d,m,opts,gs,kind,flux=reference_case;n=opts['signals']
 a=branch_call(norton if kind.startswith('norton') else mixed,t,d,{**m,'load_branch_inductance':np.eye(n)*inductance},opts,gs,kind)
 actual=inductance*a.load_branch_current[-1];energy=np.dot(flux,flux)/(2*inductance)
 record_property('flux_and_energy',str(dict(signals=n,kind=kind,inductance=inductance,expected_flux=flux.tolist(),actual_flux=actual.tolist(),expected_energy=float(energy),actual_energy=float(a.load_branch_energy[-1]))))
 np.testing.assert_allclose(actual,flux,rtol=1e-5,atol=0)
 assert abs(a.load_branch_energy[-1]/energy-1)<=1e-5
 assert a.power_balance_relative_error<=1e-10 and a.total_power_balance_relative_error<=1e-10
 assert np.all(np.isfinite(a.load_branch_current)) and np.all(a.load_branch_energy>=0)
