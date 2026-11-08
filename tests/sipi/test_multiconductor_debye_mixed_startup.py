# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Typed boundaries, independent charge KCL and explicitly qualified PWL refinement."""
from dataclasses import fields,replace
import json,copy
from importlib import metadata
from scipy.integrate import solve_ivp
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
import numpy as np
import pytest
import sipi.multiconductor_debye_mixed_startup as module
from sipi import psd_multiconductor_debye_mixed_reactive_ladder_response as response
from sipi import psd_multiconductor_debye_norton_reactive_ladder_response as norton_api, psd_multiconductor_debye_reactive_ladder_response as voltage_api, coupled_mixed_source_ladder_response
api=response
from test_multiconductor_debye_norton_startup_waves import arguments
from sipi import startup_port_waves


def args(n=3,pulse=False):
 a=arguments(n,pulse=pulse);d=a.pop('source_currents');a.pop('source_shunt_conductance')
 a['sources']=[dict(kind='voltage',voltage_v=(d[:,j]*50).tolist(),series_resistance_ohm=50.) if j%2 else dict(kind='current',current_a=d[:,j].tolist(),shunt_conductance_s=0.) for j in range(n)]
 return a


def forbid(*a,**kw):pytest.fail('invalid source reached propagation')


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('bad',['none','dict','short','long','nondict','kind-missing','kind-wrong','kind-bool','extra','mixed-keys','missing-values','missing-parameter','resistance-alias','voltage-short'])
def test_closed_typed_source_contract(signals,bad,monkeypatch):
 a=args(signals);s=a['sources'];i=1
 if bad=='none':a['sources']=None
 elif bad=='dict':a['sources']={j:v for j,v in enumerate(s)}
 elif bad=='short':s.pop()
 elif bad=='long':s.append(s[0])
 elif bad=='nondict':s[i]=[]
 elif bad=='kind-missing':s[i].pop('kind')
 elif bad=='kind-wrong':s[i]['kind']='Voltage'
 elif bad=='kind-bool':s[i]['kind']=True
 elif bad=='extra':s[i]['extra']=1
 elif bad=='mixed-keys':s[i]['current_a']=s[i].pop('voltage_v')
 elif bad=='missing-values':s[i].pop('voltage_v')
 elif bad=='missing-parameter':s[i].pop('series_resistance_ohm')
 elif bad=='resistance-alias':s[0]['shunt_resistance_ohm']=s[0].pop('shunt_conductance_s')
 else:s[i]['series_resistance_ohm']=0.
 monkeypatch.setattr(module,'lsim',forbid)
 with pytest.raises((ValueError,TypeError)):response(**a)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('kind',['voltage','current'])
@pytest.mark.parametrize('bad',['none','scalar','shape','short','long','bool','complex','str','nan','inf','initial'])
def test_typed_waveform_shape_and_real_zero_first(signals,kind,bad,monkeypatch):
 a=args(signals);j=1 if kind=='voltage' else 0;key='voltage_v' if j else 'current_a';v=a['sources'][j][key]
 if bad=='none':v=None
 elif bad=='scalar':v=1.
 elif bad=='shape':v=np.array(v)[:,None]
 elif bad=='short':v=v[:-1]
 elif bad=='long':v=v+[1.]
 elif bad=='bool':v[1]=True
 elif bad=='complex':v=np.array(v,dtype=complex)
 elif bad=='str':v[1]='1'
 elif bad=='nan':v[1]=np.nan
 elif bad=='inf':v[1]=np.inf
 else:v[0]=1e-30
 a['sources'][j][key]=v;monkeypatch.setattr(module,'lsim',forbid)
 with pytest.raises((ValueError,TypeError)):response(**a)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('kind',['voltage','current'])
@pytest.mark.parametrize('bad',[None,True,-1.,-1e-300,np.inf,np.nan,1+0j,'1',[1.]])
def test_strict_finite_scalar_source_parameter(signals,kind,bad,monkeypatch):
 a=args(signals);j=1 if kind=='voltage' else 0;key='series_resistance_ohm' if j else 'shunt_conductance_s'
 a['sources'][j][key]=bad;monkeypatch.setattr(module,'lsim',forbid)
 with pytest.raises((ValueError,TypeError)):response(**a)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('bad',['reciprocal-overflow','injection-overflow','injection-underflow'])
def test_unrepresentable_voltage_conversion_rejected_before_propagation(signals,bad,monkeypatch):
 a=args(signals);s=a['sources'][1]
 if bad=='reciprocal-overflow':s['series_resistance_ohm']=1e-320
 elif bad=='injection-overflow':s['series_resistance_ohm']=1e-200;s['voltage_v'][1]=1e200
 else:s['series_resistance_ohm']=1e300;s['voltage_v'][1]=1e-300
 monkeypatch.setattr(module,'lsim',forbid)
 with pytest.raises(ValueError,match='source transformation'):response(**a)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('tiny',[0.,1e-13,1e-20])
@pytest.mark.parametrize('pulse',[False,True])
def test_original_typed_values_and_small_current_shunts_are_preserved(signals,tiny,pulse):
 a=args(signals,pulse);a['sources'][0]['shunt_conductance_s']=tiny;original=copy.deepcopy(a['sources']);r=response(**a)
 assert r.inputs['sources']==original and r.inputs['signals']==signals
 assert len(r.inputs)==15 and 'source_currents_a' not in r.inputs and 'source_voltages_v' not in r.inputs
 assert not hasattr(r,'source_currents') and not hasattr(r,'source_voltages')
 assert not hasattr(r,'source_resistor_loss')
 np.testing.assert_array_equal(r.source_values,np.column_stack([s['voltage_v'] if s['kind']=='voltage' else s['current_a'] for s in original]))
 np.testing.assert_allclose(r.source_power-r.source_series_resistor_loss-r.source_shunt_resistor_loss,
  np.sum(r.voltage[:,:signals]*r.current[:,:signals],axis=1),rtol=1e-10,atol=1e-12)
 assert r.total_power_balance_relative_error<=1e-10 and r.power_balance_relative_error<=1e-10
 assert not np.any(r.source_series_resistor_loss<0) and not np.any(r.source_shunt_resistor_loss<0)
 assert startup_port_waves(r,z_ref=[50.]*(2*signals)).incident.shape==(121,2*signals)


@pytest.mark.parametrize('signals',[3,4])
def test_detached_readonly_export_and_zero(signals):
 a=args(signals);r=response(**a);snapshot=json.dumps(r.to_dict(include_states=True),sort_keys=True,allow_nan=False)
 a['sources'][0]['current_a'][1]=99;a['L'][:]=99
 for f in fields(r):
  if isinstance(getattr(r,f.name),np.ndarray):assert not getattr(r,f.name).flags.writeable
 out=r.to_dict(include_states=True);out['input']['sources'][0]['current_a'][1]=99;out['source_units'][0]='V'
 assert json.dumps(r.to_dict(include_states=True),sort_keys=True,allow_nan=False)==snapshot
 with pytest.raises(ValueError):r.to_dict(include_states=1)
 with pytest.raises(ValueError):replace(r,source_series_resistor_loss=np.full(121,np.inf))
 a=args(signals)
 for source in a['sources']:source['voltage_v' if source['kind']=='voltage' else 'current_a']=[0.]*121
 z=response(**a);assert not np.any(z.voltage) and not np.any(z.total_energy)
 assert z.power_balance_relative_error==z.total_power_balance_relative_error==0.


@pytest.mark.parametrize('signals',[3,4])
def test_linearity_time_impedance_permutation_and_pole_order(signals):
 a=args(signals);base=response(**a);scaled=copy.deepcopy(a)
 for s in scaled['sources']:
  key='voltage_v' if s['kind']=='voltage' else 'current_a';s[key]=(np.array(s[key])*3).tolist()
 other=response(**scaled)
 np.testing.assert_allclose(other.voltage,base.voltage*3,rtol=1e-10,atol=1e-12)
 np.testing.assert_allclose(other.current,base.current*3,rtol=1e-10,atol=1e-12)
 for key in ['source_power','source_series_resistor_loss','source_shunt_resistor_loss','total_energy']:
  np.testing.assert_allclose(getattr(other,key),getattr(base,key)*9,rtol=1e-10,atol=1e-22 if 'energy' in key else 1e-12)
 scaled=copy.deepcopy(a);scaled['time']*=2;scaled['relaxation_hz']/=2
 for k in ['L','C_inf','delta_C','load_capacitance','load_branch_inductance']:scaled[k]*=2
 other=response(**scaled);np.testing.assert_allclose(other.voltage,base.voltage,rtol=1e-10,atol=1e-12);np.testing.assert_allclose(other.current,base.current,rtol=1e-10,atol=1e-12)
 scaled=copy.deepcopy(a)
 for k in ['R','L','load_branch_resistance','load_branch_inductance']:scaled[k]*=2
 scaled['load_resistance']=np.array(scaled['load_resistance'])*2
 for k in ['G','C_inf','delta_C','load_capacitance']:scaled[k]/=2
 for s in scaled['sources']:
  if s['kind']=='voltage':s['voltage_v']=(np.array(s['voltage_v'])*2).tolist();s['series_resistance_ohm']*=2
  else:s['shunt_conductance_s']/=2
 other=response(**scaled);np.testing.assert_allclose(other.voltage,base.voltage*2,rtol=1e-10,atol=1e-12);np.testing.assert_allclose(other.current,base.current,rtol=1e-10,atol=1e-12)
 p=np.arange(signals)[::-1];scaled=copy.deepcopy(a)
 for k in ['R','L','G','C_inf','load_capacitance','load_branch_resistance','load_branch_inductance']:scaled[k]=scaled[k][np.ix_(p,p)]
 scaled['delta_C']=scaled['delta_C'][:,p][:,:,p];scaled['sources']=[scaled['sources'][i] for i in p];scaled['load_resistance']=np.asarray(scaled['load_resistance'])[p]
 other=response(**scaled);order=np.r_[p,signals+p]
 np.testing.assert_allclose(other.voltage,base.voltage[:,order],rtol=1e-10,atol=1e-12);np.testing.assert_allclose(other.current,base.current[:,order],rtol=1e-10,atol=1e-12)
 scaled=copy.deepcopy(a);scaled['delta_C']=scaled['delta_C'][::-1];scaled['relaxation_hz']=scaled['relaxation_hz'][::-1]
 other=response(**scaled);np.testing.assert_allclose(other.voltage,base.voltage,rtol=1e-10,atol=1e-12)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('bad',['shape','nan','initial','exception'])
def test_original_propagation_failures(signals,bad,monkeypatch):
 original=module.lsim
 def corrupt(*args,**kwargs):
  if bad=='exception':raise RuntimeError('matrix propagation failed')
  t,y,x=original(*args,**kwargs)
  if bad=='shape':x=x[:-1]
  elif bad=='nan':x[:]=np.nan
  else:x[0]=1.
  return t,y,x
 monkeypatch.setattr(module,'lsim',corrupt)
 with pytest.raises(RuntimeError if bad=='exception' else ValueError):response(**args(signals))


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('key,value',[('cells',0),('cells',65),('signals',2),('signals',5),('length',0),('relaxation_hz',[0.,7e8])])
def test_original_resource_contract_before_propagation(signals,key,value,monkeypatch):
 a=args(signals);a[key]=value;monkeypatch.setattr(module,'lsim',forbid)
 with pytest.raises(ValueError):response(**a)


def typed(drive,gs,mask=None):
 n=drive.shape[1]
 if mask is None:mask=np.arange(n)%2==1
 return [dict(kind='voltage',voltage_v=(drive[:,j]/gs[j]).tolist(),series_resistance_ohm=float(1/gs[j])) if mask[j] else dict(kind='current',current_a=drive[:,j].tolist(),shunt_conductance_s=float(gs[j])) for j in range(n)]

def call(t,drive,n,signals,mats,gs=None,rl=None,length=.1,mask=None):
 gs=np.full(signals,.02) if gs is None else np.asarray(gs)
 return api(t,typed(drive,gs,mask),signals=signals,**mats,length=length,cells=n,load_resistance=np.full(signals,100.) if rl is None else rl)

def symmetric(a):return np.triu(a)+np.triu(a,1).T

def amp(signals):return np.array([1.,-.4,.2,-.1])[:signals]

def damped_modal_data(signals):
    j=np.arange(signals);q=np.eye(signals);q[:2,:2]=np.array([[1.,1.],[1.,-1.]])/np.sqrt(2)
    if signals==4:q[2:,2:]=q[:2,:2]
    diag=dict(R=17.+3*j,L=(400.+50*j)*1e-9,G=.001+.0005*j,C_inf=(180.+20*j)*1e-12)
    diag['R']*=10;diag['G']*=10
    delta=np.zeros((2,signals));delta[0,0]=300e-12;delta[1,1]=80e-12
    if signals==4:delta[1,2]=120e-12
    cl=(20.+5*j)*1e-12;poles=np.array([8e7,7e8])
    mats={k:symmetric((q*d)@q.T) for k,d in diag.items()}
    mats.update(delta_C=np.array([symmetric((q*d)@q.T) for d in delta]),relaxation_hz=poles,load_capacitance=symmetric((q*cl)@q.T))
    rb=35.+5*j;lb=(180.+20*j)*1e-9
    mats.update(load_branch_resistance=symmetric((q*rb)@q.T),load_branch_inductance=symmetric((q*lb)@q.T))
    return q,diag,delta,cl,rb,lb,mats

def damped_frequency_reference(f,signals,n=None):
    q,diag,delta,cl,rb,lb,mats=damped_modal_data(signals);modes=[]
    for j in range(signals):
        z=diag['R'][j]+2j*np.pi*f*diag['L'][j]
        cap=diag['C_inf'][j]+sum(d[j]/(1+1j*f/p) for d,p in zip(delta,mats['relaxation_hz']))
        y=diag['G'][j]+2j*np.pi*f*cap;yl=1/100+2j*np.pi*f*cl[j]+1/(rb[j]+2j*np.pi*f*lb[j])
        if n is None:
            medium=require_tool("scikit-rf").media.DefinedGammaZ0(frequency=require_tool("scikit-rf").Frequency.from_f([f],unit='hz'),z0_port=50.,z0=np.sqrt(z/y),gamma=np.sqrt(z*y))
            aa,bb,cc,dd=medium.line(.1,unit='m').a[0].ravel();far=1/(cc+dd*yl+.02*(aa+bb*yl));modes.append([(aa+bb*yl)*far,far])
        else:
            dx=.1/n;weights=np.ones(n+1);weights[[0,-1]]=.5;k=np.diag(y*dx*weights).astype(complex);inj=np.zeros(n+1,complex)
            inj[0]=1.;k[0,0]+=.02;k[-1,-1]+=yl
            for m in range(n):k[m,m]+=1/(z*dx);k[m+1,m+1]+=1/(z*dx);k[m,m+1]-=1/(z*dx);k[m+1,m]-=1/(z*dx)
            modes.append(np.linalg.solve(k,inj)[[0,n]])
    modes=np.array(modes);amplitudes=q.T@(.02*amp(signals))
    return np.r_[q@(amplitudes*modes[:,0]),q@(amplitudes*modes[:,1])]

def pwl_reference(f,samples,signals,cutoffs=(8192,16384,32768)):
 q,d,delta,cl,rb,lb,m=damped_modal_data(signals);totals=np.zeros((len(cutoffs),signals,2),complex);coeff=np.zeros(len(cutoffs))
 maximum=max(cutoffs)
 for left in range(-maximum,maximum+1,4096):
  aliases=np.arange(left,min(left+4096,maximum+1));k=1+samples*aliases
  weights=(np.sin(np.pi/samples)/(np.pi*(aliases+1/samples)))**2
  positive=np.abs(k)*f;order=np.argsort(positive);inverse=np.argsort(order);frequencies=positive[order]
  for z,cutoff in enumerate(cutoffs):coeff[z]+=weights[np.abs(aliases)<=cutoff].sum()
  for j in range(signals):
   w=2j*np.pi*frequencies;zline=d['R'][j]+w*d['L'][j]
   cap=d['C_inf'][j]+sum(v[j]/(1+1j*frequencies/p) for v,p in zip(delta,m['relaxation_hz']))
   yline=d['G'][j]+w*cap;yl=1/100+w*cl[j]+1/(rb[j]+w*lb[j])
   medium=require_tool("scikit-rf").media.DefinedGammaZ0(frequency=require_tool("scikit-rf").Frequency.from_f(frequencies,unit='hz'),z0_port=50.,z0=np.sqrt(zline/yline),gamma=np.sqrt(zline*yline))
   matrix=medium.line(.1,unit='m').a;aa=matrix[:,0,0];bb=matrix[:,0,1];cc=matrix[:,1,0];dd=matrix[:,1,1]
   far=1/(cc+dd*yl+.02*(aa+bb*yl));h=np.c_[(aa+bb*yl)*far,far][inverse];h[k<0]=h[k<0].conj()
   for z,cutoff in enumerate(cutoffs):
    mask=np.abs(aliases)<=cutoff;totals[z,j]=(totals[z,j]+(weights[mask,None]*h[mask]).sum(axis=0))
 amplitudes=q.T@(.02*amp(signals))
 values=np.array([np.r_[q@(amplitudes*row[:,0]),q@(amplitudes*row[:,1])] for row in totals])
 return values,coeff

def finite_reference(f,samples,signals,n,cutoffs=(16,32,64,128),*,modal_factory=damped_modal_data):
 q,d,delta,cl,rb,lb,m=modal_factory(signals);aliases=np.arange(-max(cutoffs),max(cutoffs)+1);ks=1+samples*aliases;freq=abs(ks)*f
 weights=(np.sin(np.pi/samples)/(np.pi*(aliases+1/samples)))**2;totals=np.zeros((len(cutoffs),signals,2),complex)
 for j in range(signals):
  w=2j*np.pi*freq;z=d['R'][j]+w*d['L'][j];cap=d['C_inf'][j]+sum(v[j]/(1+1j*freq/p) for v,p in zip(delta,m['relaxation_hz']))
  y=d['G'][j]+w*cap;yl=1/100+w*cl[j]+1/(rb[j]+w*lb[j]);dx=.1/n;edge=1/(z*dx);off=-edge
  cprime=[];dprime=[]
  for node in range(n+1):
   diag=y*dx*(.5 if node in [0,n] else 1)+(edge if node in [0,n] else 2*edge)+(yl if node==n else 0)+(.02 if node==0 else 0)
   den=diag if node==0 else diag-off*cprime[-1]
   cprime.append(off/den if node<n else np.zeros_like(den));dprime.append((np.ones_like(den) if node==0 else -off*dprime[-1])/den)
  far=dprime[-1];near=far.copy()
  for node in range(n-1,-1,-1):near=dprime[node]-cprime[node]*near
  h=np.c_[near,far];h[ks<0]=h[ks<0].conj()
  for z,cutoff in enumerate(cutoffs):
   mask=abs(aliases)<=cutoff;totals[z,j]=(weights[mask,None]*h[mask]).sum(axis=0)
 amplitude=q.T@(.02*amp(signals));return np.array([np.r_[q@(amplitude*x[:,0]),q@(amplitude*x[:,1])] for x in totals])

def damped_phasor(f,n,cycles,samples,signals):
    *_,mats=damped_modal_data(signals);t=np.arange(cycles*samples+1)/(f*samples);drive=.02*np.sin(2*np.pi*f*t)[:,None]*amp(signals)
    a=call(t,drive,n,signals,mats);last=slice(-4*samples-1,-1);phase=np.exp(-2j*np.pi*f*t[last])
    return 2/len(phase)*(phase@a.voltage[last])/(-1j),a



def record_check(case,clock,observables,tool,reference,acceptance):
    record=make_record(case=case,physics='finite passive typed-source multiconductor Debye circuit',
        api='sipi.psd_multiconductor_debye_mixed_reactive_ladder_response',
        discretization='finite pi cells, auxiliary polarization voltages, external C/RL, zero-state PWL',
        tool=tool,tool_discretization=reference,
        matched=['explicit matrices,length,typed source voltage/current units and terminations,declared waveform'],
        not_matched=['finite circuit and qualified continuum comparisons are separately scoped; no measured data'],
        observables=observables,analytical_acceptance=acceptance,stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)


@pytest.mark.parametrize('signals',[3,4])
def test_all_typed_masks_and_independent_charge_kcl(signals):
    require_tool('scipy');clock=Stopwatch();rows=[]
    a=arguments(signals);drive=a.pop('source_currents');a.pop('source_shunt_conductance');gs=np.array([.04,.02,.01,.03])[:signals]
    with clock('reference'):old=norton_api(**a,source_currents=drive,source_shunt_conductance=gs)
    with clock('reference'):v=voltage_api(**a,source_voltages=drive/gs,source_resistance=1/gs)
    maxv=maxi=0.
    for bits in range(2**signals):
     mask=np.array([bool(bits&(1<<j)) for j in range(signals)])
     with clock('openphysics'):out=api(**a,sources=typed(drive,gs,mask))
     maxv=max(maxv,float(np.max(abs(out.voltage-v.voltage))));maxi=max(maxi,float(np.max(abs(out.current-v.current))))
     for name in ['node_voltage','segment_current','polarization_voltage','polarization_charge','polarization_current','load_capacitor_current','load_branch_current','energy','polarization_energy','load_capacitor_energy','load_branch_energy']:
      np.testing.assert_allclose(getattr(out,name),getattr(old,name),rtol=1e-10,atol=1e-22 if 'energy' in name or 'charge' in name else 1e-12)
     near=out.voltage[:,:signals];current=out.current[:,:signals]
     ps=np.sum((drive/gs)[:,mask]*current[:,mask],axis=1)+np.sum(drive[:,~mask]*near[:,~mask],axis=1)
     np.testing.assert_allclose(out.source_power,ps,rtol=1e-13,atol=1e-15)
     np.testing.assert_allclose(out.source_series_resistor_loss,np.sum(current[:,mask]**2/gs[mask],axis=1),rtol=1e-13,atol=1e-15)
     np.testing.assert_allclose(out.source_shunt_resistor_loss,np.sum(near[:,~mask]**2*gs[~mask],axis=1),rtol=1e-13,atol=1e-15)
     assert out.source_units==tuple('V' if k else 'A' for k in mask)
     assert out.total_power_balance_relative_error<=1e-10
    assert maxv<=1e-10 and maxi<=1e-12
    rows.append(dict(signals=signals,kind='all_masks',cases=2**signals,max_voltage_error=maxv,max_current_error=maxi))
    print(rows[-1],flush=True)
    # Independent charge KCL uses mixed ideal current and finite voltage boundaries.
    # Independent charge-state KCL, including external C in the far node.
    j=np.arange(signals);off=np.eye(signals,k=1)+np.eye(signals,k=-1)
    r=np.zeros((signals,signals));r[:2,:2]=[[20.,-20.],[-20.,20.]]
    g=np.zeros_like(r);g[1:3,1:3]=[[.002,.002],[.002,.002]]
    l=(np.diag(450.+20*j)+60*off)*1e-9;c=(np.diag(210.+10*j)-20*off)*1e-12
    ds=np.zeros((2,signals,signals));ds[0,:2,:2]=np.array([[80.,-40.],[-40.,20.]])*1e-12;ds[1,1:3,1:3]=np.array([[32.,32.],[32.,32.]])*1e-12
    br=np.zeros((signals,signals));br[:2,:2]=[[30.,-30.],[-30.,30.]]
    bl=(np.diag(180.+20*j)+15*off)*1e-9
    load=(np.diag(20.+4*j)-3*off)*1e-12;gs=np.array([0.,.02,0.,.01])[:signals];rl=91.+11*j;poles=np.array([8e7,7e8]);tau=1/(2*np.pi*poles)
    n=8;dx=.1/n;weights=np.ones(n+1);weights[[0,-1]]=.5;nv=signals*(n+1);base=nv+signals*n;branch=base+2*nv;u=np.linspace(0,12,241)
    def drive_u(x):return .02*min(x/2.,1.)*amp(signals)
    def dynamics(x,state):
        v=state[:nv].reshape(n+1,signals);i=state[nv:base].reshape(n,signals);charge=state[base:branch].reshape(n+1,2,signals);bi=state[branch:];dq=np.empty_like(charge)
        for p,mat in enumerate(ds):dq[:,p]=(v@mat.T-charge[:,p])/tau[p]
        flow=np.zeros_like(v);flow[:-1]-=i;flow[1:]+=i;near_injection=drive_u(x).copy();near_injection[1::2]=(drive_u(x)[1::2]/gs[1::2])/(1/gs[1::2]);flow[0]+=near_injection-v[0]*gs;flow[-1]-=v[-1]/rl+bi
        dv=np.linalg.solve(c,(flow/(dx*weights[:,None])-v@g.T-dq.sum(axis=1)).T).T
        dv[-1]=np.linalg.solve(dx*weights[-1]*c+load,flow[-1]-dx*weights[-1]*(v[-1]@g.T+dq[-1].sum(axis=0)))
        di=np.linalg.solve(l,((v[:-1]-v[1:])/dx-i@r.T).T).T
        dbi=np.linalg.solve(bl,v[-1]-br@bi)
        return 1e-9*np.r_[dv.ravel(),di.ravel(),dq.ravel(),dbi]
    state=np.zeros(branch+signals);values=np.zeros((len(u),len(state)))
    for left,right in [(0.,2.),(2.,12.)]:
        idx=np.flatnonzero((u>left)&(u<=right))
        with clock('reference'):sol=solve_ivp(dynamics,[left,right],state,method='DOP853',t_eval=u[idx],rtol=1e-11,atol=1e-15,max_step=.005)
        assert sol.success;values[idx]=sol.y.T;state=sol.y[:,-1]
    v=values[:,:nv].reshape(len(u),n+1,signals);dd=np.array([drive_u(x) for x in u]);vv=np.concatenate((v[:,0],v[:,-1]),axis=1)
    derivative=np.array([dynamics(x,y) for x,y in zip(u,values)])/1e-9;dv=derivative[:,:nv].reshape(v.shape)
    ii=np.concatenate((dd-v[:,0]*gs,-v[:,-1]/rl-dv[:,-1]@load.T-values[:,branch:]),axis=1)
    with clock('openphysics'):result=call(u*1e-9,dd,n,signals,dict(R=r,L=l,G=g,C_inf=c,delta_C=ds,relaxation_hz=poles,load_capacitance=load,load_branch_resistance=br,load_branch_inductance=bl),gs,rl)
    ev=float(np.max(abs(result.voltage-vv)));ei=float(np.max(abs(result.current-ii)))
    entry=dict(signals=signals,kind='independent_kcl',voltage_error=ev,current_error=ei,power_error=result.power_balance_relative_error,total_power_error=result.total_power_balance_relative_error)
    eb=float(np.max(abs(result.load_branch_current-values[:,branch:])));entry['branch_current_error']=eb
    print('kcl',signals,entry,flush=True);assert ev<=1e-8 and ei<=1e-9 and eb<=1e-9
    rows.append(entry)

    record_check(f'multiconductor-mixed-charge-kcl-{signals}',clock,
        [observable('voltage','V','independent charge-KCL maximum',entry['voltage_error'],1e-8),
         observable('current','A','independent charge-KCL maximum',entry['current_error'],1e-9),
         observable('branch current','A','independent charge-KCL maximum',entry['branch_current_error'],1e-9)],
        'scipy','DOP853 integration of independent charge/branch KCL, explicit typed boundary forcing',
        'All typed source masks preserve homogeneous Thevenin/Norton states; line and source power partitions distinct')


@pytest.mark.parametrize('signals',[3,4])
def test_qualified_mixed_damped_pwl_horizon_input_and_spatial_refinement(signals):
    require_tool('scikit-rf');clock=Stopwatch()
    def measured_phasor(*args):
        with clock('openphysics'):return damped_phasor(*args)
    def measured_frequency(*args):
        with clock('reference'):return damped_frequency_reference(*args)
    def measured_continuum(*args):
        with clock('reference'):return pwl_reference(*args)
    def measured_finite(*args,**kwargs):
        with clock('reference'):return finite_reference(*args,**kwargs,modal_factory=damped_modal_data)
    row=dict(signals=signals,horizon=[],spatial=[])
    for f,cycles,samples in [(1e8,[16,18,19],512),(5e8,[64,72,76],128)]:
     phases=[measured_phasor(f,64,c,samples,signals)[0] for c in cycles];diff=[float(np.max(abs(phases[k+1]-phases[k]))) for k in range(2)]
     row['horizon'].append(dict(frequency=f,cycles=cycles,samples=samples,differences=diff,accepted=max(diff)<=1e-8));print('horizon',signals,row['horizon'][-1],flush=True)
    errs=[float(np.max(abs(measured_phasor(1e8,64,16,s,signals)[0]-measured_frequency(1e8,signals,64)))) for s in [128,256,512]]
    row['input_refinement']=dict(errors=errs,accepted=errs[2]<errs[1]<errs[0]);print('input',signals,errs,flush=True)
    for f,cycles,samples in [(1e8,19,512),(5e8,76,128)]:
     refs,coeff=measured_continuum(f,samples,signals);diff=[float(np.max(abs(refs[j+1]-refs[j]))) for j in range(len(refs)-1)]
     phases=[measured_phasor(f,n,cycles,samples,signals)[0] for n in [16,32,64]]
     errors=[float(np.max(abs(ph-refs[-1]))) for ph in phases];finite_controls=[]
     for n,ph in zip([16,32,64],phases):
      finite=measured_finite(f,samples,signals,n,cutoffs=(32,64,128));fd=[float(np.max(abs(finite[j+1]-finite[j]))) for j in range(2)];fe=float(np.max(abs(ph-finite[-1])))
      finite_controls.append(dict(cells=n,reference_differences=fd,voltage_error=fe,accepted=max(fd)<=1e-8 and fe<=1e-8))
     case=dict(frequency=f,cycles=cycles,samples=samples,reference_refinement=diff,coefficient_error=(1-coeff).tolist(),errors=errors,finite_pwl_controls=finite_controls,accepted=all(x["accepted"] for x in finite_controls) and max(diff)<=1e-8 and abs(1-coeff[-1])<=1e-8 and errors[2]<errors[1]<errors[0] and errors[2]<=1e-3)
     row['spatial'].append(case);print('space',signals,case,flush=True)
    row['accepted']=all(x['accepted'] for x in row['horizon']+row['spatial']) and row['input_refinement']['accepted']

    assert row['accepted'],row
    record_check(f'multiconductor-mixed-qualified-pwl-{signals}',clock,
        [observable('voltage','V','finest spatial error',max(x['errors'][-1] for x in row['spatial']),1e-3),
         observable('voltage','V','horizon change',max(max(x['differences']) for x in row['horizon']),1e-8),
         observable('voltage','V','finite PWL control',max(z['voltage_error'] for x in row['spatial'] for z in x['finite_pwl_controls']),1e-8)],
        'scikit-rf','scikit-rf continuum ABCD with same periodic-PWL aliases; independent finite-pi tridiagonal KCL',
        'UniformGs.02 typed mixed sources and R/Gx10 spectral fixture, qualified19cycle512sample100MHz and76cycle128sample500MHz; original low-loss/short-horizon failures remain unqualified')


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('pulse',[False,True])
def test_zero_strength_constant_mixed_block_limits(signals,pulse):
    rows=[]
    a=arguments(signals,'diagonal',pulse);drive=a.pop('source_currents');a.pop('source_shunt_conductance')
    a['delta_C'][:]=0.;gs=np.array([0.,.02,0.,.02])[:signals]
    # Two independent coupled blocks; a final singleton is padded by an unexcited channel.
    for lo,hi in [(0,2),(2,signals)]:
     if hi-lo==2:
      for key,cross in dict(R=2.,L=60e-9,G=-.0001,C_inf=-20e-12,load_capacitance=-3e-12,load_branch_resistance=-5.,load_branch_inductance=15e-9).items():
       a[key][lo,lo+1]=a[key][lo+1,lo]=cross
    out=api(**a,sources=typed(drive,gs));vv=np.zeros_like(out.voltage);ii=np.zeros_like(vv);ps=np.zeros(len(drive));sl=ps.copy();sh=ps.copy()
    for lo,hi in [(0,2),(2,signals)]:
     count=hi-lo
     keys=['R','L','G','C_inf','load_capacitance','load_branch_resistance','load_branch_inductance']
     if count==2:local={k:a[k][lo:hi,lo:hi] for k in keys};sources=typed(drive[:,lo:hi],gs[lo:hi]);load=np.asarray(a['load_resistance'])[lo:hi]
     else:
      local={k:np.diag([a[k][lo,lo],v]) for k,v in dict(R=0.,L=1e-9,G=0.,C_inf=1e-12,load_capacitance=0.,load_branch_resistance=1.,load_branch_inductance=1e-9).items()}
      sources=[dict(kind='current',current_a=drive[:,lo].tolist(),shunt_conductance_s=0.),dict(kind='current',current_a=np.zeros(len(drive)).tolist(),shunt_conductance_s=0.)];load=[a['load_resistance'][lo],100.]
     local['C']=local.pop('C_inf')
     for source in sources:
      if source['kind']=='current':g=source.pop('shunt_conductance_s');source['shunt_resistance_ohm']=None if g==0 else 1/g
     ref=coupled_mixed_source_ladder_response(a['time'],sources,**local,length=a['length'],cells=a['cells'],load_resistance=load)
     vv[:,lo:hi]=ref.voltage[:,:count];vv[:,signals+lo:signals+hi]=ref.voltage[:,2:2+count]
     ii[:,lo:hi]=ref.current[:,:count];ii[:,signals+lo:signals+hi]=ref.current[:,2:2+count]
     ps+=ref.source_power;sl+=ref.source_series_resistor_loss;sh+=ref.source_shunt_resistor_loss
    ev=float(np.max(abs(out.voltage-vv)));ei=float(np.max(abs(out.current-ii)))
    assert ev<=1e-10 and ei<=1e-12
    for actual,expected in [(out.source_power,ps),(out.source_series_resistor_loss,sl),(out.source_shunt_resistor_loss,sh)]:np.testing.assert_allclose(actual,expected,rtol=1e-10,atol=1e-12)
    rows.append(dict(signals=signals,pulse=pulse,voltage_error=ev,current_error=ei));print(rows[-1],flush=True)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('kind',['voltage','current'])
@pytest.mark.parametrize('shape',['scalar','vector'])
def test_source_kind_arrays_reject_before_propagation(signals,kind,shape,monkeypatch):
    a=args(signals);j=1 if kind=='voltage' else 0
    a['sources'][j]['kind']=np.array(kind if shape=='scalar' else [kind])
    monkeypatch.setattr(module,'lsim',forbid)
    with pytest.raises(ValueError,match='explicit voltage or current kind'):response(**a)
