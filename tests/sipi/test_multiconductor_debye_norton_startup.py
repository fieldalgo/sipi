# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit Norton source circuits and separately qualified continuum comparisons."""
import json
import importlib.metadata as metadata
from dataclasses import replace
import numpy as np
import pytest
from scipy.integrate import solve_ivp
from crosscheck import Stopwatch,emit,make_record,observable,require_tool
from sipi import (startup_port_waves,psd_multiconductor_debye_reactive_ladder_response,
    coupled_norton_reactive_ladder_response,NortonMulticonductorDebyeReactiveLadderResponse,
    psd_multiconductor_debye_norton_reactive_ladder_response as response)
import sipi.multiconductor_debye_norton_startup as module
def symmetric(a):return np.triu(a)+np.triu(a,1).T
def amp(signals):return np.array([1.,-.4,.2,-.1])[:signals]
def modal_data(signals):
    j=np.arange(signals);q=np.eye(signals);q[:2,:2]=np.array([[1.,1.],[1.,-1.]])/np.sqrt(2)
    if signals==4:q[2:,2:]=q[:2,:2]
    diag=dict(R=17.+3*j,L=(400.+50*j)*1e-9,G=.001+.0005*j,C_inf=(180.+20*j)*1e-12)
    delta=np.zeros((2,signals));delta[0,0]=300e-12;delta[1,1]=80e-12
    if signals==4:delta[1,2]=120e-12
    cl=(20.+5*j)*1e-12;poles=np.array([8e7,7e8])
    mats={k:symmetric((q*d)@q.T) for k,d in diag.items()}
    mats.update(delta_C=np.array([symmetric((q*d)@q.T) for d in delta]),relaxation_hz=poles,load_capacitance=symmetric((q*cl)@q.T))
    rb=35.+5*j;lb=(180.+20*j)*1e-9
    mats.update(load_branch_resistance=symmetric((q*rb)@q.T),load_branch_inductance=symmetric((q*lb)@q.T))
    return q,diag,delta,cl,rb,lb,mats

def power_checks(a):
    assert max(a.power_balance_relative_error,a.total_power_balance_relative_error)<=1e-10
    np.testing.assert_allclose(a.line_energy_rate,a.line_power-a.series_loss-a.shunt_loss-a.relaxation_loss,rtol=1e-10,atol=1e-15)
    np.testing.assert_allclose(a.total_energy_rate,a.source_power-a.source_shunt_resistor_loss-a.load_resistor_loss-a.load_branch_resistor_loss-a.series_loss-a.shunt_loss-a.relaxation_loss,rtol=1e-10,atol=1e-15)
    for name in ['energy','polarization_energy','load_capacitor_energy','series_loss','shunt_loss','relaxation_loss','source_shunt_resistor_loss','load_resistor_loss','load_branch_energy','load_branch_resistor_loss']:
        assert np.all(getattr(a,name)>=0),name

def call(t,drive,n,signals,mats,gs=None,rl=None,length=.1):
    a=response(t,drive,signals=signals,**mats,length=length,cells=n,
        source_shunt_conductance=np.zeros(signals) if gs is None else gs,
        load_resistance=np.full(signals,100.) if rl is None else rl)
    power_checks(a);return a

def frequency_reference(f,signals,n=None):
    q,diag,delta,cl,rb,lb,mats=modal_data(signals);modes=[]
    for j in range(signals):
        z=diag['R'][j]+2j*np.pi*f*diag['L'][j]
        cap=diag['C_inf'][j]+sum(d[j]/(1+1j*f/p) for d,p in zip(delta,mats['relaxation_hz']))
        y=diag['G'][j]+2j*np.pi*f*cap;yl=1/100+2j*np.pi*f*cl[j]+1/(rb[j]+2j*np.pi*f*lb[j])
        if n is None:
            medium=require_tool("scikit-rf").media.DefinedGammaZ0(frequency=require_tool("scikit-rf").Frequency.from_f([f],unit='hz'),z0_port=50.,z0=np.sqrt(z/y),gamma=np.sqrt(z*y))
            aa,bb,cc,dd=medium.line(.1,unit='m').a[0].ravel();far=1/(cc+dd*yl);modes.append([(aa+bb*yl)*far,far])
        else:
            dx=.1/n;weights=np.ones(n+1);weights[[0,-1]]=.5;k=np.diag(y*dx*weights).astype(complex);inj=np.zeros(n+1,complex)
            inj[0]=1.;k[-1,-1]+=yl
            for m in range(n):k[m,m]+=1/(z*dx);k[m+1,m+1]+=1/(z*dx);k[m,m+1]-=1/(z*dx);k[m+1,m]-=1/(z*dx)
            modes.append(np.linalg.solve(k,inj)[[0,n]])
    modes=np.array(modes);amplitudes=q.T@(.02*amp(signals))
    return np.r_[q@(amplitudes*modes[:,0]),q@(amplitudes*modes[:,1])]

def phasor(f,n,cycles,samples,signals):
    *_,mats=modal_data(signals);t=np.arange(cycles*samples+1)/(f*samples);drive=.02*np.sin(2*np.pi*f*t)[:,None]*amp(signals)
    a=call(t,drive,n,signals,mats);last=slice(-4*samples-1,-1);phase=np.exp(-2j*np.pi*f*t[last])
    return 2/len(phase)*(phase@a.voltage[last])/(-1j),a

def record_check(case,clock,observables,tool_discretization,acceptance):
    record=make_record(case=case,physics='finite passive current-driven multiconductor Debye circuit',
        api='sipi.psd_multiconductor_debye_norton_reactive_ladder_response',
        discretization='finite pi cells, auxiliary polarization voltages, external capacitor and branch inductor, zero-state PWL',
        tool='scikit-rf',tool_discretization=tool_discretization,
        matched=['explicit matrices, length, source conductance, parallel and branch loads, declared waveform'],
        not_matched=['continuum versus finite circuit stated separately; no measured data'],
        observables=observables,analytical_acceptance=acceptance,stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)

@pytest.mark.parametrize('signals',[3,4])
def test_thevenin_constant_blocks_independent_charge_kcl_and_short_rl(signals):
    require_tool('scipy');require_tool('scikit-rf');clock=Stopwatch()
    item=dict(signals=signals);q,diag,delta,cl,rb,lb,mats=modal_data(signals)
    t=np.linspace(0,12e-9,121);drive=.02*np.minimum(t/2e-9,1.)[:,None]*amp(signals)
    gs_positive=np.array([.04,.02,.01,.03])[:signals]
    with clock("openphysics"):result=call(t,drive,8,signals,mats,gs=gs_positive)
    with clock("reference"):equivalent=psd_multiconductor_debye_reactive_ladder_response(t,drive/gs_positive,
        signals=signals,**mats,length=.1,cells=8,source_resistance=1/gs_positive,load_resistance=[100.]*signals)
    ev=float(np.max(abs(result.voltage-equivalent.voltage)));ei=float(np.max(abs(result.current-equivalent.current)))
    item['positive_conductance_thevenin']=dict(voltage_error=ev,current_error=ei)
    assert ev<=1e-10 and ei<=1e-12
    for name in ['node_voltage','segment_current','polarization_voltage','polarization_charge','polarization_current','energy','energy_rate','polarization_energy','polarization_energy_rate','relaxation_loss','load_capacitor_current','load_capacitor_energy','load_capacitor_power','load_branch_current','load_branch_energy','load_branch_energy_rate','load_branch_resistor_loss']:
        np.testing.assert_allclose(getattr(result,name),getattr(equivalent,name),rtol=1e-10,atol=1e-22 if name in ['energy','polarization_energy','load_capacitor_energy','load_branch_energy','polarization_charge'] else 1e-15 if name in ['energy_rate','polarization_energy_rate','relaxation_loss','load_capacitor_power','load_branch_energy_rate','load_branch_resistor_loss'] else 1e-12)
    np.testing.assert_allclose(result.source_power-result.source_shunt_resistor_loss,
        equivalent.source_power-equivalent.source_resistor_loss,rtol=1e-10,atol=1e-12)
    gs_block=np.array([.04,.02,0.,0.])[:signals]
    # Block-diagonal inputs: 2+1 or2+2; the one active channel uses an
    # uncoupled, unexcited second channel in the existing two-signal API.
    block={k:np.diag(d) for k,d in diag.items()};block.update(delta_C=np.zeros((2,signals,signals)),relaxation_hz=mats['relaxation_hz'],load_capacitance=np.diag(cl),load_branch_resistance=np.diag(rb),load_branch_inductance=np.diag(lb))
    vv=np.zeros((len(t),2*signals));ii=np.zeros_like(vv)
    for lo,hi in [(0,2),(2,signals)]:
        count=hi-lo
        if count==2:
            for key,cross in dict(R=2.,L=60e-9,G=-.0001,C_inf=-20e-12).items():block[key][lo,lo+1]=block[key][lo+1,lo]=cross
            block['load_capacitance'][lo:hi,lo:hi]=np.array([[30.,-5.],[-5.,40.]])*1e-12
            block['load_branch_resistance'][lo,lo+1]=block['load_branch_resistance'][lo+1,lo]=-5.
            block['load_branch_inductance'][lo,lo+1]=block['load_branch_inductance'][lo+1,lo]=20e-9
            args={k:block[k][lo:hi,lo:hi] for k in [*diag,'load_capacitance','load_branch_resistance','load_branch_inductance']};args['delta_C']=block['delta_C'][:,lo:hi,lo:hi];dd=drive[:,lo:hi]
        else:
            args={k:np.diag([block[k][lo,lo],dummy]) for k,dummy in dict(R=0.,L=1e-9,G=0.,C_inf=1e-12,load_capacitance=0.,load_branch_resistance=1.,load_branch_inductance=1e-9).items()}
            args['delta_C']=np.array([np.diag([d[lo,lo],0.]) for d in block['delta_C']]);dd=np.c_[drive[:,lo],np.zeros(len(t))]
        args.pop('delta_C');args['C']=args.pop('C_inf')
        shunts=[None if g==0 else 1/g for g in gs_block[lo:hi]]
        if count==1:shunts.append(1.)
        with clock("reference"):ref=coupled_norton_reactive_ladder_response(t,dd,**args,length=.1,cells=8,source_shunt_resistance=shunts,load_resistance=[100.,100.])
        vv[:,lo:hi]=ref.voltage[:,:count];vv[:,signals+lo:signals+hi]=ref.voltage[:,2:2+count]
        ii[:,lo:hi]=ref.current[:,:count];ii[:,signals+lo:signals+hi]=ref.current[:,2:2+count]
    with clock("openphysics"):result=call(t,drive,8,signals,block,gs=gs_block);ev=float(np.max(abs(result.voltage-vv)));ei=float(np.max(abs(result.current-ii)))
    item['block_limits']=dict(voltage_error=ev,current_error=ei);assert ev<=1e-10 and ei<=1e-12
    with clock("openphysics"):ideal=call(t,drive,8,signals,mats);errors=[]
    for conductance in [1e-3,1e-4,1e-5]:
        with clock("openphysics"):result=call(t,drive,8,signals,mats,gs=np.full(signals,conductance))
        errors.append(float(np.max(abs(result.voltage-ideal.voltage))))
    item['ideal_current_limit']=errors;assert errors[2]<errors[1]<errors[0] and errors[2]<=1e-3
    # Independent charge-state KCL, including external C in the far node.
    j=np.arange(signals);off=np.eye(signals,k=1)+np.eye(signals,k=-1)
    r=np.zeros((signals,signals));r[:2,:2]=[[20.,-20.],[-20.,20.]]
    g=np.zeros_like(r);g[1:3,1:3]=[[.002,.002],[.002,.002]]
    l=(np.diag(450.+20*j)+60*off)*1e-9;c=(np.diag(210.+10*j)-20*off)*1e-12
    ds=np.zeros((2,signals,signals));ds[0,:2,:2]=np.array([[80.,-40.],[-40.,20.]])*1e-12;ds[1,1:3,1:3]=np.array([[32.,32.],[32.,32.]])*1e-12
    br=np.zeros((signals,signals));br[:2,:2]=[[30.,-30.],[-30.,30.]]
    bl=(np.diag(180.+20*j)+15*off)*1e-9
    load=(np.diag(20.+4*j)-3*off)*1e-12;gs=np.array([0.,.02,0.,.01])[:signals];rl=91.+11*j;poles=mats['relaxation_hz'];tau=1/(2*np.pi*poles)
    n=8;dx=.1/n;weights=np.ones(n+1);weights[[0,-1]]=.5;nv=signals*(n+1);base=nv+signals*n;branch=base+2*nv;u=np.linspace(0,12,241)
    def drive_u(x):return .02*min(x/2.,1.)*amp(signals)
    def dynamics(x,state):
        v=state[:nv].reshape(n+1,signals);i=state[nv:base].reshape(n,signals);charge=state[base:branch].reshape(n+1,2,signals);bi=state[branch:];dq=np.empty_like(charge)
        for p,mat in enumerate(ds):dq[:,p]=(v@mat.T-charge[:,p])/tau[p]
        flow=np.zeros_like(v);flow[:-1]-=i;flow[1:]+=i;flow[0]+=drive_u(x)-v[0]*gs;flow[-1]-=v[-1]/rl+bi
        dv=np.linalg.solve(c,(flow/(dx*weights[:,None])-v@g.T-dq.sum(axis=1)).T).T
        dv[-1]=np.linalg.solve(dx*weights[-1]*c+load,flow[-1]-dx*weights[-1]*(v[-1]@g.T+dq[-1].sum(axis=0)))
        di=np.linalg.solve(l,((v[:-1]-v[1:])/dx-i@r.T).T).T
        dbi=np.linalg.solve(bl,v[-1]-br@bi)
        return 1e-9*np.r_[dv.ravel(),di.ravel(),dq.ravel(),dbi]
    state=np.zeros(branch+signals);values=np.zeros((len(u),len(state)))
    for left,right in [(0.,2.),(2.,12.)]:
        idx=np.flatnonzero((u>left)&(u<=right))
        with clock("reference"):sol=solve_ivp(dynamics,[left,right],state,method='DOP853',t_eval=u[idx],rtol=1e-11,atol=1e-15,max_step=.005)
        assert sol.success;values[idx]=sol.y.T;state=sol.y[:,-1]
    v=values[:,:nv].reshape(len(u),n+1,signals);dd=np.array([drive_u(x) for x in u]);vv=np.concatenate((v[:,0],v[:,-1]),axis=1)
    derivative=np.array([dynamics(x,y) for x,y in zip(u,values)])/1e-9;dv=derivative[:,:nv].reshape(v.shape)
    ii=np.concatenate((dd-v[:,0]*gs,-v[:,-1]/rl-dv[:,-1]@load.T-values[:,branch:]),axis=1)
    with clock("openphysics"):result=call(u*1e-9,dd,n,signals,dict(R=r,L=l,G=g,C_inf=c,delta_C=ds,relaxation_hz=poles,load_capacitance=load,load_branch_resistance=br,load_branch_inductance=bl),gs,rl)
    ev=float(np.max(abs(result.voltage-vv)));ei=float(np.max(abs(result.current-ii)))
    item['independent_kcl']=dict(voltage_error=ev,current_error=ei,power_error=result.power_balance_relative_error,total_power_error=result.total_power_balance_relative_error)
    eb=float(np.max(abs(result.load_branch_current-values[:,branch:])));item['independent_kcl']['branch_current_error']=eb
    print('kcl',signals,item['independent_kcl'],flush=True);assert ev<=1e-8 and ei<=1e-9 and eb<=1e-9
    # Closed-form PWL lumped RL limit as line length tends to zero, CL=0.
    br=35.+5*j;bl=(180.+20*j)*1e-9;tr=2e-9;t=np.linspace(0,12e-9,121);dd=.01*np.minimum(t/tr,1.)[:,None]*amp(signals);tau_rl=bl/(100+br)
    def ramp(x):x=np.maximum(x,0)[:,None];return x+tau_rl*np.expm1(-x/tau_rl)
    ib=100/(100+br)/tr*(ramp(t)-ramp(t-tr))*(.01*amp(signals));expected=100*(dd-ib);errors=[]
    lump=dict(R=np.zeros((signals,signals)),L=np.eye(signals)*450e-9,G=np.zeros((signals,signals)),C_inf=np.eye(signals)*210e-12,delta_C=np.zeros((1,signals,signals)),relaxation_hz=[8e7],load_capacitance=np.zeros((signals,signals)),load_branch_resistance=np.diag(br),load_branch_inductance=np.diag(bl))
    for length in [.01,.001,.0001]:
        with clock("openphysics"):result=call(t,dd,4,signals,lump,length=length);error=float(np.max(abs(result.voltage-np.c_[expected,expected])));errors.append(error)
    item['lumped_rl_length_limit']=errors;print('RL',signals,errors,flush=True);assert errors[2]<errors[1]<errors[0] and errors[2]<=1e-3

    record_check(f'multiconductor-norton-physical-{signals}',clock,
        [observable('voltage','V','charge-KCL maximum',item['independent_kcl']['voltage_error'],1e-8),
         observable('current','A','charge-KCL maximum',item['independent_kcl']['current_error'],1e-9),
         observable('branch current','A','charge-KCL maximum',item['independent_kcl']['branch_current_error'],1e-9)],
        'Independent noncommuting charge/branch-KCL DOP853; analytical lumped RL and Thevenin equivalents',
        'Original Thevenin, constant two-signal block, ideal-current and short-length limits; spectral qualifications separate')
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
            aa,bb,cc,dd=medium.line(.1,unit='m').a[0].ravel();far=1/(cc+dd*yl);modes.append([(aa+bb*yl)*far,far])
        else:
            dx=.1/n;weights=np.ones(n+1);weights[[0,-1]]=.5;k=np.diag(y*dx*weights).astype(complex);inj=np.zeros(n+1,complex)
            inj[0]=1.;k[-1,-1]+=yl
            for m in range(n):k[m,m]+=1/(z*dx);k[m+1,m+1]+=1/(z*dx);k[m,m+1]-=1/(z*dx);k[m+1,m]-=1/(z*dx)
            modes.append(np.linalg.solve(k,inj)[[0,n]])
    modes=np.array(modes);amplitudes=q.T@(.02*amp(signals))
    return np.r_[q@(amplitudes*modes[:,0]),q@(amplitudes*modes[:,1])]


def damped_phasor(f,n,cycles,samples,signals):
    *_,mats=damped_modal_data(signals);t=np.arange(cycles*samples+1)/(f*samples);drive=.02*np.sin(2*np.pi*f*t)[:,None]*amp(signals)
    a=call(t,drive,n,signals,mats);last=slice(-4*samples-1,-1);phase=np.exp(-2j*np.pi*f*t[last])
    return 2/len(phase)*(phase@a.voltage[last])/(-1j),a


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
   far=1/(cc+dd*yl);h=np.c_[(aa+bb*yl)*far,far][inverse];h[k<0]=h[k<0].conj()
   for z,cutoff in enumerate(cutoffs):
    mask=np.abs(aliases)<=cutoff;totals[z,j]=(totals[z,j]+(weights[mask,None]*h[mask]).sum(axis=0))
 amplitudes=q.T@(.02*amp(signals))
 values=np.array([np.r_[q@(amplitudes*row[:,0]),q@(amplitudes*row[:,1])] for row in totals])
 return values,coeff


def finite_reference(f,samples,signals,n,cutoffs=(16,32,64,128),*,modal_factory=modal_data):
 q,d,delta,cl,rb,lb,m=modal_factory(signals);aliases=np.arange(-max(cutoffs),max(cutoffs)+1);ks=1+samples*aliases;freq=abs(ks)*f
 weights=(np.sin(np.pi/samples)/(np.pi*(aliases+1/samples)))**2;totals=np.zeros((len(cutoffs),signals,2),complex)
 for j in range(signals):
  w=2j*np.pi*freq;z=d['R'][j]+w*d['L'][j];cap=d['C_inf'][j]+sum(v[j]/(1+1j*freq/p) for v,p in zip(delta,m['relaxation_hz']))
  y=d['G'][j]+w*cap;yl=1/100+w*cl[j]+1/(rb[j]+w*lb[j]);dx=.1/n;edge=1/(z*dx);off=-edge
  cprime=[];dprime=[]
  for node in range(n+1):
   diag=y*dx*(.5 if node in [0,n] else 1)+(edge if node in [0,n] else 2*edge)+(yl if node==n else 0)
   den=diag if node==0 else diag-off*cprime[-1]
   cprime.append(off/den if node<n else np.zeros_like(den));dprime.append((np.ones_like(den) if node==0 else -off*dprime[-1])/den)
  far=dprime[-1];near=far.copy()
  for node in range(n-1,-1,-1):near=dprime[node]-cprime[node]*near
  h=np.c_[near,far];h[ks<0]=h[ks<0].conj()
  for z,cutoff in enumerate(cutoffs):
   mask=abs(aliases)<=cutoff;totals[z,j]=(weights[mask,None]*h[mask]).sum(axis=0)
 amplitude=q.T@(.02*amp(signals));return np.array([np.r_[q@(amplitude*x[:,0]),q@(amplitude*x[:,1])] for x in totals])



@pytest.mark.parametrize('signals',[3,4])
def test_qualified_damped_pwl_horizon_input_and_spatial_refinement(signals):
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
    record_check(f'multiconductor-norton-qualified-pwl-{signals}',clock,
        [observable('voltage','V','finest spatial error',max(x['errors'][-1] for x in row['spatial']),1e-3),
         observable('voltage','V','horizon change',max(max(x['differences']) for x in row['horizon']),1e-8),
         observable('voltage','V','finite PWL control',max(z['voltage_error'] for x in row['spatial'] for z in x['finite_pwl_controls']),1e-8)],
        'scikit-rf continuum ABCD with same periodic-PWL aliases; independent finite-pi tridiagonal KCL',
        'R/Gx10 spectral fixture, qualified19cycle512sample100MHz and76cycle128sample500MHz; original low-loss/short-horizon failures remain unqualified')

@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('frequency',[1e8,5e8])
def test_original_pure_frequency_operator_spatial_convergence(signals,frequency):
    require_tool('scikit-rf');clock=Stopwatch()
    with clock('reference'):
        ref=frequency_reference(frequency,signals)
        errors=[float(np.max(abs(frequency_reference(frequency,signals,n)-ref))) for n in [16,32,64]]
    assert errors[2]<errors[1]<errors[0] and errors[2]<=1e-3
    # This compares two reference operators without a product solve, so it is
    # a convergence diagnostic rather than a product/reference timing record.
    print(json.dumps(dict(role='reference-operator spatial convergence; no product execution',
        signals=signals,frequency_hz=frequency,cells=[16,32,64],voltage_errors=errors,
        final_gate_v=1e-3,strict_decrease=True,reference='scikit-rf continuum ABCD and independent finite-pi KCL',
        reference_version=metadata.version('scikit-rf'),reference_wall_time_s=clock.seconds['reference'],
        limit='No candidate transient or original low-loss PWL spatial acceptance')))

@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('cells',[16,32,64])
def test_original_finite_pwl_circuit_control(signals,cells):
    require_tool('scikit-rf');clock=Stopwatch()
    with clock('reference'):refs=finite_reference(1e8,128,signals,cells)
    diff=[float(np.max(abs(refs[j+1]-refs[j]))) for j in range(3)]
    with clock('openphysics'):ph,a=phasor(1e8,cells,72,128,signals)
    err=float(np.max(abs(ph-refs[-1])))
    assert max(diff[-2:])<=1e-10 and err<=1e-8
    record_check(f'multiconductor-norton-finite-pwl-{signals}-{cells}',clock,
        [observable('voltage','V','same finite-circuit PWL error',err,1e-8)],
        'Independent modal tridiagonal KCL with periodic PWL harmonic aliases16/32/64/128',
        'Finite circuit only; original low-loss128sample continuous-line spatial convergence remains unqualified')

def run(signals,t=None,d=None,**changes):
    t=np.linspace(0,12e-9,121) if t is None else t
    d=np.minimum(t/2e-9,1.)[:,None]*amp(signals) if d is None else d
    *_,m=modal_data(signals)
    kw=dict(signals=signals,**m,length=.1,cells=4,source_shunt_conductance=np.zeros(signals),load_resistance=[100.]*signals)
    kw.update(changes);return response(t,d,**kw)

@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('tiny',[0.,1e-13,1e-20])
@pytest.mark.parametrize('pulse',[False,True])
def test_external_storage_current_partition_and_no_rank_clipping(signals,tiny,pulse):
    cap=np.diag([30e-12]+[30e-12*tiny]*(signals-1));t=np.linspace(0,12e-9,121)
    d=np.minimum(t/2e-9,1.)
    if pulse:d-=np.minimum(np.maximum(t-5e-9,0)/2e-9,1.)
    a=run(signals,t,d[:,None]*amp(signals),load_capacitance=cap);power_checks(a);far=a.voltage[:,signals:]
    assert a.inputs['load_capacitance_f']==cap.tolist()
    np.testing.assert_allclose(a.current[:,signals:],-far/100-a.load_capacitor_current-a.load_branch_current,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(a.load_resistor_loss,np.sum(far**2/100,axis=1),rtol=1e-10,atol=1e-15)
    np.testing.assert_allclose(a.load_capacitor_energy,.5*np.einsum('ti,ij,tj->t',far,cap,far),rtol=1e-10,atol=1e-22)
    np.testing.assert_allclose(a.load_capacitor_power,np.sum(far*a.load_capacitor_current,axis=1),rtol=1e-10,atol=1e-15)
    np.testing.assert_array_equal(a.total_energy,a.line_energy+a.load_capacitor_energy+a.load_branch_energy)
    np.testing.assert_array_equal(a.total_energy_rate,a.line_energy_rate+a.load_capacitor_power+a.load_branch_energy_rate)
    if tiny==0:assert not np.any(a.load_capacitor_current[:,1:])
    else:assert np.any(a.load_capacitor_current[:,1:])
    if pulse:assert np.any(a.load_capacitor_power<0)

@pytest.mark.parametrize('signals',[3,4])
def test_linear_time_impedance_pole_and_signal_permutations(signals):
    t=np.linspace(0,12e-9,121);d=np.minimum(t/2e-9,1.)[:,None]*amp(signals);*_,m=modal_data(signals);a=run(signals,t,d)
    linear=run(signals,t,-2*d)
    timed=run(signals,3*t,d,L=3*m['L'],C_inf=3*m['C_inf'],delta_C=3*m['delta_C'],relaxation_hz=m['relaxation_hz']/3,load_capacitance=3*m['load_capacitance'],load_branch_inductance=3*m['load_branch_inductance'])
    scaled=run(signals,t,d,R=3*m['R'],L=3*m['L'],G=m['G']/3,C_inf=m['C_inf']/3,delta_C=m['delta_C']/3,load_capacitance=m['load_capacitance']/3,source_shunt_conductance=np.zeros(signals),load_resistance=[300.]*signals,load_branch_resistance=3*m['load_branch_resistance'],load_branch_inductance=3*m['load_branch_inductance'])
    poles=run(signals,t,d,delta_C=m['delta_C'][::-1],relaxation_hz=m['relaxation_hz'][::-1])
    for b,vs,cs,es in [(linear,-2,-2,4),(timed,1,1,3),(scaled,3,1,3),(poles,1,1,1)]:
        np.testing.assert_allclose(b.voltage,vs*a.voltage,rtol=1e-10,atol=1e-12)
        np.testing.assert_allclose(b.current,cs*a.current,rtol=1e-10,atol=1e-12)
        np.testing.assert_allclose(b.total_energy,es*a.total_energy,rtol=1e-10,atol=1e-22);power_checks(b)
    mm={k:(v if k=='relaxation_hz' else v[:,::-1,::-1] if k=='delta_C' else v[::-1,::-1]) for k,v in m.items()}
    b=run(signals,t,d[:,::-1],**mm);order=np.r_[np.arange(signals)[::-1],signals+np.arange(signals)[::-1]]
    np.testing.assert_allclose(b.voltage,a.voltage[:,order],rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(b.current,a.current[:,order],rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(poles.polarization_charge,a.polarization_charge[:,:,::-1],rtol=1e-10,atol=1e-22)

@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('mode',['one','two','zero-first','all-zero'])
def test_declared_poles_and_separate_export_contract(signals,mode):
    *_,m=modal_data(signals);delta=m['delta_C'].copy();poles=m['relaxation_hz'].copy()
    if mode=='one':delta=delta[:1];poles=poles[:1]
    if mode=='zero-first':delta[0]=0
    if mode=='all-zero':delta[:]=0
    cap=m['load_capacitance'].copy();a=run(signals,delta_C=delta,relaxation_hz=poles,load_capacitance=cap);power_checks(a)
    assert type(a) is NortonMulticonductorDebyeReactiveLadderResponse
    assert a.polarization_voltage.shape==(121,5,len(poles),signals)
    weights=np.ones(5);weights[[0,-1]]=.5
    for p,mat in enumerate(delta):
        np.testing.assert_allclose(a.polarization_charge[:,:,p],.1/4*weights[None,:,None]*(a.polarization_voltage[:,:,p]@mat.T),rtol=1e-14,atol=0)
        if not np.any(mat):assert not np.any(a.polarization_voltage[:,:,p])
    saved=a.inputs;delta[:]=9;cap[:]=9;poles[:]=9;assert a.inputs==saved
    for name,value in a.__dict__.items():
        if isinstance(value,np.ndarray):assert not value.flags.writeable
    out=a.to_dict(include_states=True);json.dumps(out,allow_nan=False)
    assert out['scope']=='finite-passive-multiconductor-psd-debye-norton-reactive-startup'
    assert out['port_names']==[f'{end}_{j}' for end in ['near','far'] for j in range(signals)]
    out['input']['load_capacitance_f'][0][0]=9;assert a.inputs==saved
    with pytest.raises(ValueError):a.to_dict(include_states=1)
    assert startup_port_waves(a,z_ref=[50.]*(2*signals)).incident.shape==(121,2*signals)

@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('bad',['none','scalar','vector','shape','boolean','complex','string','asymmetric','negative','tiny-negative','nan','inf'])
def test_external_capacitance_strict_contract(signals,bad):
    cap=np.eye(signals)*30e-12
    if bad=='none':cap=None
    elif bad=='scalar':cap=30e-12
    elif bad=='vector':cap=[30e-12]*signals
    elif bad=='shape':cap=np.eye(signals+1)
    elif bad=='boolean':cap=np.eye(signals,dtype=bool)
    elif bad=='complex':cap=cap.astype(complex)
    elif bad=='string':cap=cap.astype(str)
    elif bad=='asymmetric':cap[0,1]=1e-12
    elif bad in ('negative','tiny-negative'):cap[-1,-1]=-30e-12*(1 if bad=='negative' else 1e-20)
    elif bad=='nan':cap[-1,-1]=np.nan
    elif bad=='inf':cap[-1,-1]=np.inf
    with pytest.raises(ValueError):run(signals,load_capacitance=cap)

@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('key,value',[('cells',0),('cells',65),('cells',True),('cells',1.5),('length',0),('signals',2),('signals',5),('signals',True),('relaxation_hz',[0.,7e8]),('source_shunt_conductance',.04),('load_resistance',[0.,0.,0.])])
def test_original_resource_boundary_contracts(signals,key,value):
    *_,m=modal_data(signals);t=np.linspace(0,12e-9,121);d=np.minimum(t/2e-9,1.)[:,None]*amp(signals)
    kw=dict(signals=signals,**m,length=.1,cells=4,source_shunt_conductance=np.zeros(signals),load_resistance=[100.]*signals);kw[key]=value
    with pytest.raises(ValueError):response(t,d,**kw)

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
    with pytest.raises(RuntimeError if bad=='exception' else ValueError):run(signals)

@pytest.mark.parametrize('signals',[3,4])
def test_zero_drive_and_nonfinite_storage_failures(signals):
    a=run(signals,d=np.zeros((121,signals)));power_checks(a)
    assert not np.any(a.total_energy) and a.power_balance_relative_error==a.total_power_balance_relative_error==0
    with pytest.raises(ValueError):replace(a,load_capacitor_energy=np.full(121,np.nan))
    with pytest.raises(ValueError):run(signals,C_inf=np.eye(signals)*1e308,load_capacitance=np.eye(signals)*1e308,length=10.)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('kind',['zero','rankone','near13','near20'])
@pytest.mark.parametrize('pulse',[False,True])
def test_branch_current_storage_resistance_and_total_power_partition(signals,kind,pulse):
    rb=np.zeros((signals,signals))
    if kind=='rankone':rb[:2,:2]=[[30.,-30.],[-30.,30.]]
    elif kind.startswith('near'):rb=np.diag([30.]+[30.*10**(-int(kind[4:]))]*(signals-1))
    t=np.linspace(0,12e-9,121);d=np.minimum(t/2e-9,1.)
    if pulse:d-=np.minimum(np.maximum(t-5e-9,0)/2e-9,1.)
    a=run(signals,t,d[:,None]*amp(signals),load_branch_resistance=rb);power_checks(a)
    far=a.voltage[:,signals:];bi=a.load_branch_current;lb=np.asarray(a.inputs['load_branch_inductance_h'])
    assert a.inputs['load_branch_resistance_ohm']==rb.tolist()
    np.testing.assert_allclose(a.current[:,signals:],-far/100-a.load_capacitor_current-bi,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(a.load_branch_energy,.5*np.einsum('ti,ij,tj->t',bi,lb,bi),rtol=1e-10,atol=1e-22)
    np.testing.assert_allclose(a.load_branch_resistor_loss,np.einsum('ti,ij,tj->t',bi,rb,bi),rtol=1e-10,atol=1e-15)
    np.testing.assert_allclose(a.load_branch_energy_rate,np.sum(far*bi,axis=1)-a.load_branch_resistor_loss,rtol=1e-10,atol=1e-15)
    np.testing.assert_array_equal(a.total_energy,a.line_energy+a.load_capacitor_energy+a.load_branch_energy)
    np.testing.assert_array_equal(a.total_energy_rate,a.line_energy_rate+a.load_capacitor_power+a.load_branch_energy_rate)
    if kind=='zero':assert not np.any(a.load_branch_resistor_loss)
    if pulse:assert np.any(a.load_branch_energy_rate<0)
    for name in ['load_branch_current','load_branch_energy','load_branch_energy_rate','load_branch_resistor_loss']:
        assert not getattr(a,name).flags.writeable
    assert a.to_dict()['load_branch_current_a']==bi.tolist()


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('name',['load_branch_resistance','load_branch_inductance'])
@pytest.mark.parametrize('bad',['none','scalar','vector','shape','boolean','complex','string','asymmetric','negative','tiny-negative','nan','inf'])
def test_explicit_branch_matrix_contract(signals,name,bad):
    value=np.eye(signals)*(30. if name=='load_branch_resistance' else 180e-9)
    if bad=='none':value=None
    elif bad=='scalar':value=1.
    elif bad=='vector':value=[1.]*signals
    elif bad=='shape':value=np.eye(signals+1)
    elif bad=='boolean':value=value.astype(bool)
    elif bad=='complex':value=value.astype(complex)
    elif bad=='string':value=value.astype(str)
    elif bad=='asymmetric':value[0,1]=np.nextafter(0.,1.)
    elif bad=='negative':value[-1,-1]=-1.
    elif bad=='tiny-negative':value[-1,-1]=-1e-30
    elif bad=='nan':value[-1,-1]=np.nan
    else:value[-1,-1]=np.inf
    with pytest.raises(ValueError):run(signals,**{name:value})


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('kind',['zero','singular','below-ratio'])
def test_branch_inductance_cannot_be_missing_or_singular(signals,kind):
    value=np.eye(signals)*180e-9
    if kind=='zero':value[:]=0
    elif kind=='singular':value[-1,-1]=0
    else:value[-1,-1]*=1e-13
    with pytest.raises(ValueError,match='SPD'):run(signals,load_branch_inductance=value)


@pytest.mark.parametrize('signals',[3,4])
def test_branch_inputs_are_copied_and_unrepresentable_branch_rejected(signals):
    rb=np.eye(signals)*30.;lb=np.eye(signals)*180e-9
    a=run(signals,load_branch_resistance=rb,load_branch_inductance=lb);before=a.inputs
    rb[:]=9;lb[:]=9;out=a.to_dict();out['input']['load_branch_inductance_h'][0][0]=9
    assert a.inputs==before
    for name in ['load_branch_current','load_branch_energy','load_branch_energy_rate','load_branch_resistor_loss']:
        with pytest.raises(ValueError):replace(a,**{name:np.full_like(getattr(a,name),np.nan)})
    with pytest.raises(ValueError):run(signals,load_branch_inductance=np.eye(signals)*1e-320)

@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('kind',['ideal','mixed','positive','near13','near20'])
@pytest.mark.parametrize('pulse',[False,True])
def test_current_source_shunt_and_power_are_explicit(signals,kind,pulse):
    gs=np.zeros(signals)
    if kind=='mixed':gs[1]=.02
    elif kind=='positive':gs[:]=.02
    elif kind.startswith('near'):gs[:]=.02*10**(-int(kind[4:]));gs[0]=.02
    t=np.linspace(0,12e-9,121);d=.02*np.minimum(t/2e-9,1.)
    if pulse:d-=.02*np.minimum(np.maximum(t-5e-9,0)/2e-9,1.)
    drive=d[:,None]*amp(signals);a=run(signals,t,drive,source_shunt_conductance=gs);power_checks(a)
    near=a.voltage[:,:signals]
    np.testing.assert_allclose(a.current[:,:signals],drive-near*gs,rtol=1e-13,atol=1e-15)
    np.testing.assert_allclose(a.source_power,np.sum(drive*near,axis=1),rtol=1e-13,atol=1e-15)
    np.testing.assert_allclose(a.source_shunt_resistor_loss,np.sum(gs*near**2,axis=1),rtol=1e-13,atol=0)
    np.testing.assert_allclose(a.source_power-a.source_shunt_resistor_loss,np.sum(near*a.current[:,:signals],axis=1),rtol=1e-10,atol=1e-15)
    if kind=='ideal':assert not np.any(a.source_shunt_resistor_loss)
    assert a.inputs['source_shunt_conductance_s']==gs.tolist()
    assert a.inputs['source_currents_a']==drive.tolist()
    assert 'source_voltages_v' not in a.inputs and 'source_resistance_ohm' not in a.inputs
    assert not hasattr(a,'source_voltages') and not hasattr(a,'source_resistor_loss')
    assert not a.source_currents.flags.writeable
    saved=a.inputs;gs[:]=9;drive[:]=9
    assert a.inputs==saved
    out=a.to_dict(include_states=True)
    assert 'source_resistor_loss_w' not in out
    assert out['source_shunt_resistor_loss_w']==a.source_shunt_resistor_loss.tolist()
    out['input']['source_currents_a'][1][0]=9;assert a.inputs==saved

@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('bad',['none','scalar','shape','matrix','bool','complex','string','negative','tiny-negative','nan','inf'])
def test_source_shunt_conductance_requires_finite_nonnegative_vector(signals,bad):
    gs=np.full(signals,.02)
    if bad=='none':gs=None
    elif bad=='scalar':gs=.02
    elif bad=='shape':gs=gs[:-1]
    elif bad=='matrix':gs=gs[:,None]
    elif bad=='bool':gs=gs.astype(bool)
    elif bad=='complex':gs=gs.astype(complex)
    elif bad=='string':gs=gs.astype(str)
    elif bad=='negative':gs[-1]=-.02
    elif bad=='tiny-negative':gs[-1]=-1e-300
    elif bad=='nan':gs[-1]=np.nan
    elif bad=='inf':gs[-1]=np.inf
    with pytest.raises(ValueError):run(signals,source_shunt_conductance=gs)

@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('bad',['initial','shape','scalar','bool','complex','string','nan','inf','time-initial','time-order','time-nonuniform','time-one','time-budget'])
def test_explicit_current_and_time_contract(signals,bad):
    t=np.linspace(0,12e-9,121);d=.02*np.minimum(t/2e-9,1.)[:,None]*amp(signals)
    if bad=='initial':d[0,0]=1e-20
    elif bad=='shape':d=d[:,:-1]
    elif bad=='scalar':d=.02
    elif bad=='bool':d=d.astype(bool)
    elif bad=='complex':d=d.astype(complex)
    elif bad=='string':d=d.astype(str)
    elif bad=='nan':d[-1,0]=np.nan
    elif bad=='inf':d[-1,0]=np.inf
    elif bad=='time-initial':t+=1e-9
    elif bad=='time-order':t=t[::-1]
    elif bad=='time-nonuniform':t[2]*=1.001
    elif bad=='time-one':t=t[:1];d=d[:1]
    elif bad=='time-budget':t=np.linspace(0,12e-9,10001);d=np.zeros((10001,signals))
    with pytest.raises(ValueError):run(signals,t,d)
