# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Three/four-signal startup: independent KCL, modal ABCD and strict contracts."""
import json
import importlib.metadata as metadata
from dataclasses import replace
import numpy as np
import pytest
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import (multiconductor_rlgc_ladder_response, MulticonductorRLGCLadderResponse,
                  rlgc_ladder_response, coupled_rlgc_ladder_response, startup_port_waves)
import sipi.multiconductor_startup as module


def circuit(time, drive, cells, *, signals, R, L, G, C, length=.1, rs=None, rl=None):
    a=multiconductor_rlgc_ladder_response(time,drive,signals=signals,R=R,L=L,G=G,C=C,
        length=length,cells=cells,source_resistance=rs,load_resistance=rl)
    power_checks(a)
    return dict(v=a.voltage,i=a.current,energy=a.energy,power_error=a.power_balance_relative_error,
                total_power_error=a.total_power_balance_relative_error)


def power_checks(a):
    for value in (a.energy,a.series_loss,a.shunt_loss,a.source_resistor_loss,a.load_resistor_loss):
        assert np.all(np.isfinite(value)) and np.all(value>=0)
    assert a.power_balance_relative_error<=1e-10 and a.total_power_balance_relative_error<=1e-10
    np.testing.assert_allclose(a.energy_rate,a.line_power-a.series_loss-a.shunt_loss,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(a.energy_rate,a.source_power-a.source_resistor_loss-a.load_resistor_loss-a.series_loss-a.shunt_loss,rtol=1e-10,atol=1e-12)


def modal_data(signals):
    j=np.arange(1,signals+1);q=np.sqrt(2/(signals+1))*np.sin(np.pi*np.outer(j,j)/(signals+1))
    diagonals=dict(R=17.+3*np.arange(signals),L=(400.+50*np.arange(signals))*1e-9,G=.001+.0005*np.arange(signals),C=(180.+20*np.arange(signals))*1e-12)
    matrices={}
    for name,diag in diagonals.items():
        raw=(q*diag)@q.T;upper=np.triu(raw);matrices[name]=upper+np.triu(raw,1).T
    return q,diagonals,matrices


def drive(t,signals):return np.minimum(t/2e-9,1.)[:,None]*np.array([1.,-.4,.2,-.1])[:signals]

def frequency_reference(f,signals,n=None):
    q,diags,mats=modal_data(signals);modes=[]
    for j in range(signals):
        z=diags['R'][j]+2j*np.pi*f*diags['L'][j];y=diags['G'][j]+2j*np.pi*f*diags['C'][j]
        if n is None:
            gamma=np.sqrt(z*y);zc=np.sqrt(z/y);skrf=require_tool("scikit-rf");m=skrf.media.DefinedGammaZ0(frequency=skrf.Frequency.from_f([f],unit='hz'),z0_port=50.,z0=zc,gamma=gamma);aa,bb,cc,dd=m.line(.1,unit='m').a[0].ravel();far=1/(aa+bb/100+25*(cc+dd/100));modes.append([(aa+bb/100)*far,far])
        else:
            dx=.1/n;weights=np.ones(n+1);weights[[0,-1]]=.5;k=np.diag(y*dx*weights).astype(complex);inj=np.zeros(n+1,complex);k[0,0]+=1/25;inj[0]=1/25;k[-1,-1]+=1/100
            for m in range(n):k[m,m]+=1/(z*dx);k[m+1,m+1]+=1/(z*dx);k[m,m+1]-=1/(z*dx);k[m+1,m]-=1/(z*dx)
            modes.append(np.linalg.solve(k,inj)[[0,n]])
    modes=np.array(modes);amplitudes=q.T@np.array([1.,-.4,.2,-.1])[:signals]
    return np.r_[q@(amplitudes*modes[:,0]),q@(amplitudes*modes[:,1])]

def phasor(f,n,cycles,samples,signals):
    _,_,mats=modal_data(signals);t=np.arange(cycles*samples+1)/(f*samples);d=np.sin(2*np.pi*f*t)[:,None]*np.array([1.,-.4,.2,-.1])[:signals]
    a=circuit(t,d,n,signals=signals,**mats,rs=[25.]*signals,rl=[100.]*signals);last=slice(-4*samples-1,-1);phase=np.exp(-2j*np.pi*f*t[last]);return 2/len(phase)*(phase@a['v'][last])/(-1j),a
@pytest.mark.parametrize('signals',[3,4])
def test_independent_limits_kcl_and_time_space_convergence(signals):
    clock=Stopwatch()
    def timed_phasor(*args):
        with clock('openphysics'):
            return phasor(*args)
    def timed_reference(*args):
        with clock('reference'):
            return frequency_reference(*args)
    item={'signals':signals};t=np.linspace(0,12e-9,121);d=drive(t,signals);_,diags,mats=modal_data(signals)
    limits=[]
    for lossless in [False,True]:
        diagonal={k:np.diag(v) for k,v in diags.items()}
        if lossless:diagonal['R'][:]=0;diagonal['G'][:]=0
        a=circuit(t,d,16,signals=signals,**diagonal,rs=[25.]*signals,rl=[100.]*signals)
        refs=[rlgc_ladder_response(t,d[:,j],**{k:v[j,j] for k,v in diagonal.items()},length=.1,cells=16,source_resistance=25.,load_resistance=100.) for j in range(signals)]
        ev=float(np.max(abs(a['v']-np.concatenate((np.column_stack([x.voltage[:,0] for x in refs]),np.column_stack([x.voltage[:,1] for x in refs])),axis=1))));ei=float(np.max(abs(a['i']-np.concatenate((np.column_stack([x.current[:,0] for x in refs]),np.column_stack([x.current[:,1] for x in refs])),axis=1))))
        limits.append(dict(lossless=lossless,voltage_error=ev,current_error=ei));assert ev<=1e-10 and ei<=1e-12
    item['scalar_limits']=limits
    # Independent original 2+1 or 2+2 block decomposition.
    block={k:np.diag(v) for k,v in diags.items()};cross=dict(R=2.,L=60e-9,G=-.0001,C=-20e-12)
    groups=[(0,2),(2,signals)]
    for lo,hi in groups:
        if hi-lo==2:
            for key in block:block[key][lo,lo+1]=block[key][lo+1,lo]=cross[key]
    a=circuit(t,d,16,signals=signals,**block,rs=[25.]*signals,rl=[100.]*signals);vv=np.zeros_like(a['v']);ii=np.zeros_like(a['i'])
    for lo,hi in groups:
        count=hi-lo
        if count==2:ref=coupled_rlgc_ladder_response(t,d[:,lo:hi],**{k:v[lo:hi,lo:hi] for k,v in block.items()},length=.1,cells=16,source_resistance=[25.,25.],load_resistance=[100.,100.])
        else:ref=rlgc_ladder_response(t,d[:,lo],**{k:v[lo,lo] for k,v in block.items()},length=.1,cells=16,source_resistance=25.,load_resistance=100.)
        vv[:,lo:hi]=ref.voltage[:,:count];vv[:,signals+lo:signals+hi]=ref.voltage[:,count:];ii[:,lo:hi]=ref.current[:,:count];ii[:,signals+lo:signals+hi]=ref.current[:,count:]
    ev=float(np.max(abs(a['v']-vv)));ei=float(np.max(abs(a['i']-ii)));item['block_limits']=dict(voltage_error=ev,current_error=ei);assert ev<=1e-10 and ei<=1e-12
    # Independent noncommuting node KCL and segment voltage equations.
    j=np.arange(signals);r=np.diag(20.+3*j)+2*(np.eye(signals,k=1)+np.eye(signals,k=-1));l=(np.diag(450.+20*j)+60*(np.eye(signals,k=1)+np.eye(signals,k=-1)))*1e-9;g=np.diag(.002+.0002*j)-.0002*(np.eye(signals,k=1)+np.eye(signals,k=-1));c=(np.diag(210.+10*j)-20*(np.eye(signals,k=1)+np.eye(signals,k=-1)))*1e-12
    rs=23.+7*j;rl=91.+11*j;n=16;dx=.1/n;weights=np.ones(n+1);weights[[0,-1]]=.5;nv=signals*(n+1);size=signals*(2*n+1);u=np.linspace(0,12,241);amp=np.array([1.,-.4,.2,-.1])[:signals]
    def drive_u(x):return min(x/2.,1.)*amp
    def dynamics(x,state):
        v=state[:nv].reshape(n+1,signals);i=state[nv:].reshape(n,signals);flow=np.zeros_like(v);flow[:-1]-=i;flow[1:]+=i;flow[0]+=(drive_u(x)-v[0])/rs;flow[-1]-=v[-1]/rl
        dv=np.linalg.solve(c,(flow/(dx*weights[:,None])-v@g.T).T).T;di=np.linalg.solve(l,((v[:-1]-v[1:])/dx-i@r.T).T).T
        return 1e-9*np.r_[dv.ravel(),di.ravel()]
    state=np.zeros(size);values=np.zeros((len(u),size))
    for left,right in [(0.,2.),(2.,12.)]:
        idx=np.flatnonzero((u>left)&(u<=right));sol=require_tool('scipy').integrate.solve_ivp(dynamics,[left,right],state,method='DOP853',t_eval=u[idx],rtol=1e-11,atol=1e-15,max_step=.005);assert sol.success;values[idx]=sol.y.T;state=sol.y[:,-1]
    v=values[:,:nv].reshape(len(u),n+1,signals);dd=np.array([drive_u(x) for x in u]);vv=np.concatenate((v[:,0],v[:,-1]),axis=1);ii=np.concatenate(((dd-v[:,0])/rs,-v[:,-1]/rl),axis=1)
    a=circuit(u*1e-9,dd,n,signals=signals,R=r,L=l,G=g,C=c,rs=rs,rl=rl);ev=float(np.max(abs(a['v']-vv)));ei=float(np.max(abs(a['i']-ii)));item['independent_kcl']=dict(voltage_error=ev,current_error=ei,power_error=a['power_error'],total_power_error=a['total_power_error']);assert ev<=1e-8 and ei<=1e-9;print('kcl',signals,item['independent_kcl'],flush=True)
    errors=[]
    for samples in [256,512,1024]:
        ph,a=timed_phasor(1e8,128,8,samples,signals);err=float(np.max(abs(ph-timed_reference(1e8,signals,128))));errors.append(err);print('time',signals,samples,err,flush=True)
    item['time_refinement']=errors;assert errors[2]<errors[1]<errors[0]
    phases=[timed_phasor(1e8,128,cycles,1024,signals)[0] for cycles in [7,8,9]];diff=[float(np.max(abs(phases[j+1]-phases[j]))) for j in range(2)];item['horizon_differences']=diff;assert max(diff)<=1e-8
    rows=[];item['continuous_spatial']=rows
    for f,cycles,samples in [(1e8,8,1024),(5e8,20,256),(1e9,20,256)]:
        ref=timed_reference(f,signals);cases=[]
        for n in [32,64,128]:
            ph,a=timed_phasor(f,n,cycles,samples,signals);err=float(np.max(abs(ph-ref)));cases.append(dict(cells=n,voltage_error=err,power_error=a['power_error'],total_power_error=a['total_power_error']));print('space',signals,f,n,err,flush=True)
        rows.append(dict(frequency=f,cycles=cycles,samples=samples,cases=cases));assert cases[2]['voltage_error']<cases[1]['voltage_error']<cases[0]['voltage_error'] and cases[2]['voltage_error']<=.001
    result=make_record(case=f'sipi-multiconductor-startup-{signals}',physics='constant passive multiconductor circuit',
        api='sipi.multiconductor_rlgc_ladder_response',discretization='finite pi cells;PWL voltage drive',
        tool='scikit-rf',tool_discretization='scalar modal continuous ABCD;timings cover modal propagation/reference calls;separate untimed scipy DOP853 node KCL',
        matched=['explicit matrices,geometry length,source/load resistances,time drive'],
        not_matched=['continuous modal reference versus finite cells;ODE versus state-space propagation;no measured data'],
        observables=[observable('terminal phasor','V','maximum finest-cell error',max(x['cases'][-1]['voltage_error'] for x in rows),.001),
                     observable('KCL terminal voltage','V','maximum absolute error',item['independent_kcl']['voltage_error'],1e-8),
                     observable('KCL terminal current','A','maximum absolute error',item['independent_kcl']['current_error'],1e-9)],
        analytical_acceptance='scalar and original two-signal block limits;power conservation',stopwatch=clock)
    result['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(result)


def run(signals=3,time=None,source=None,**changes):
    time=np.linspace(0,12e-9,121) if time is None else time
    source=drive(time,signals) if source is None else source
    _,_,mats=modal_data(signals)
    kw=dict(signals=signals,**mats,length=.1,cells=8,source_resistance=[25.]*signals,load_resistance=[100.]*signals)
    kw.update(changes)
    return multiconductor_rlgc_ladder_response(time,source,**kw)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('pulse',[False,True])
@pytest.mark.parametrize('lossless',[False,True])
def test_states_boundaries_copy_and_passivity(signals,pulse,lossless):
    t=np.linspace(0,12e-9,121);d=drive(t,signals)
    if pulse:d*=np.clip((6e-9-t)/2e-9,0,1)[:,None]
    kw=dict(R=np.zeros((signals,signals)),G=np.zeros((signals,signals))) if lossless else {}
    a=run(signals,t,d,**kw);power_checks(a)
    assert type(a) is MulticonductorRLGCLadderResponse
    assert a.port_names==tuple(f'{end}_{j}' for end in ('near','far') for j in range(signals))
    assert a.node_voltage.shape==(121,9,signals) and a.segment_current.shape==(121,8,signals)
    assert a.voltage.shape==a.current.shape==(121,2*signals)
    assert np.all(a.node_voltage[0]==0) and np.all(a.segment_current[0]==0)
    np.testing.assert_allclose(a.current[:,:signals],(d-a.voltage[:,:signals])/25)
    np.testing.assert_allclose(a.current[:,signals:],-a.voltage[:,signals:]/100)
    original=a.to_dict(include_states=True);json.dumps(original,allow_nan=False)
    assert 'node_voltage_v' not in a.to_dict()
    t[:]=4;d[:]=5;assert a.to_dict(include_states=True)==original
    inputs=a.inputs;inputs['signals']=99;assert a.inputs['signals']==signals
    for name in ['time','source_voltages','node_voltage','segment_current','voltage','current','energy','energy_rate','series_loss','shunt_loss','line_power','source_power','source_resistor_loss','load_resistor_loss']:
        value=getattr(a,name);assert not value.flags.writeable
        changed=np.array(value);b=replace(a,**{name:changed});changed[:]=9;np.testing.assert_array_equal(getattr(b,name),value)
    with pytest.raises(ValueError):a.to_dict(include_states=1)
    assert startup_port_waves(a,z_ref=[50.]*(2*signals)).incident.shape==(121,2*signals)


@pytest.mark.parametrize('signals',[3,4])
def test_zero_and_input_scaling_permutation_invariants(signals):
    t=np.linspace(0,12e-9,121);d=drive(t,signals);a=run(signals,t,d);_,_,m=modal_data(signals)
    zero=run(signals,t,np.zeros_like(d))
    for name in ['voltage','current','energy','energy_rate','series_loss','shunt_loss','source_power']:
        assert np.all(getattr(zero,name)==0)
    amp=run(signals,t,-2*d)
    for name in ['voltage','current','node_voltage','segment_current']:np.testing.assert_allclose(getattr(amp,name),-2*getattr(a,name),rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(amp.energy,4*a.energy,rtol=1e-10,atol=1e-22)
    stretched=run(signals,3*t,d,L=3*m['L'],C=3*m['C'])
    np.testing.assert_allclose(stretched.voltage,a.voltage,rtol=1e-9,atol=1e-11)
    np.testing.assert_allclose(stretched.energy,3*a.energy,rtol=1e-9,atol=1e-22)
    impedance=run(signals,t,d,R=3*m['R'],L=3*m['L'],G=m['G']/3,C=m['C']/3,source_resistance=[75.]*signals,load_resistance=[300.]*signals)
    np.testing.assert_allclose(impedance.voltage,a.voltage,rtol=1e-9,atol=1e-11)
    np.testing.assert_allclose(impedance.current,a.current/3,rtol=1e-9,atol=1e-12)
    p=np.arange(signals)[::-1];perm=run(signals,t,d[:,p],**{k:v[np.ix_(p,p)] for k,v in m.items()})
    cols=np.r_[p,signals+p]
    np.testing.assert_allclose(perm.voltage,a.voltage[:,cols],rtol=1e-9,atol=1e-11)
    np.testing.assert_allclose(perm.current,a.current[:,cols],rtol=1e-9,atol=1e-12)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('name',['R','L','G','C'])
@pytest.mark.parametrize('bad',['shape','asymmetric','negative','singular','ratio','complex','boolean','nan','inf'])
def test_strict_matrices(signals,name,bad):
    _,_,m=modal_data(signals);v=m[name].copy()
    if bad=='shape':v=v[:-1]
    elif bad=='asymmetric':v[0,1]=np.nextafter(v[1,0],np.inf)
    elif bad=='negative':v=-np.eye(signals)
    elif bad=='singular':v=np.diag([1.]*(signals-1)+[0.])
    elif bad=='ratio':v=np.diag([1.]*(signals-1)+[1e-13])
    elif bad=='complex':v=v.astype(complex)
    elif bad=='boolean':v=v.astype(bool)
    elif bad=='nan':v[0,0]=np.nan
    else:v[0,0]=np.inf
    with pytest.raises(ValueError):run(signals,**{name:v})


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('key,value',[
    ('cells',0),('cells',129),('cells',1.5),('cells',True),('length',0),('length',-1),('length',np.inf),
    ('source_resistance',25.),('load_resistance',None),('source_resistance',[0.,25.,25.]),
    ('load_resistance',[100.,100.]),('source_resistance',[np.inf]*3),('load_resistance',[-1.]*4)])
def test_strict_sizes_and_terminal_vectors(signals,key,value):
    with pytest.raises(ValueError):run(signals,**{key:value})


@pytest.mark.parametrize('signals',[None,True,2,5,3.0,'3'])
def test_explicit_signal_count(signals):
    _,_,m=modal_data(3)
    with pytest.raises(ValueError):multiconductor_rlgc_ladder_response([0.,1e-9],np.zeros((2,3)),signals=signals,**m,length=.1,cells=1,source_resistance=[25.]*3,load_resistance=[100.]*3)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('bad',['one','many','start','descending','nonuniform','nonfinite','shape','initial','complex','boolean'])
def test_time_and_drive_validation(signals,bad):
    t=np.linspace(0,12e-9,121);d=drive(t,signals)
    if bad=='one':t=t[:1];d=d[:1]
    elif bad=='many':t=np.linspace(0,12e-9,10001);d=drive(t,signals)
    elif bad=='start':t+=1e-12
    elif bad=='descending':t=t[::-1]
    elif bad=='nonuniform':t[2]+=1e-12
    elif bad=='nonfinite':t[-1]=np.inf
    elif bad=='shape':d=d[:,:-1]
    elif bad=='initial':d[0,0]=1e-15
    elif bad=='complex':d=d.astype(complex)
    else:d=d.astype(bool)
    with pytest.raises(ValueError):run(signals,t,d)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('bad',['shape','nan','initial'])
def test_propagator_state_guard(monkeypatch,signals,bad):
    original=module.lsim
    def faulty(*args,**kwargs):
        t,y,x=original(*args,**kwargs);x=x.copy()
        if bad=='shape':x=x[:,:-1]
        elif bad=='nan':x[-1,0]=np.nan
        else:x[0,0]=1e-12
        return t,y,x
    monkeypatch.setattr(module,'lsim',faulty)
    with pytest.raises(ValueError,match='state propagation'):run(signals)


def test_original_propagator_failure_retained(monkeypatch):
    def fail(*args,**kwargs):raise RuntimeError('deliberate propagation failure')
    monkeypatch.setattr(module,'lsim',fail)
    with pytest.raises(RuntimeError,match='deliberate'):run()


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('key,value',[('length',1e-320),('L',1e-320),('C',1e-320),('R',1e308),('G',1e308)])
def test_finite_scale_guards(signals,key,value):
    kw={key:value if key=='length' else value*np.eye(signals)}
    with pytest.raises((ValueError,np.linalg.LinAlgError)):run(signals,**kw)
