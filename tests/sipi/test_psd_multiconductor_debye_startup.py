# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit PSD multi-signal Debye circuits: null directions and independent equations."""
from dataclasses import replace
import importlib.metadata as metadata
import json
import numpy as np
import pytest
from scipy.integrate import solve_ivp
from crosscheck import Stopwatch,emit,make_record,observable,require_tool
from sipi import (debye_rlgc_ladder_response,psd_coupled_debye_rlgc_ladder_response,
    multiconductor_rlgc_ladder_response,PSDMulticonductorDebyeRLGCLadderResponse,
    psd_multiconductor_debye_rlgc_ladder_response,startup_port_waves)
import sipi.psd_multiconductor_debye_startup as module
response=psd_multiconductor_debye_rlgc_ladder_response

def symmetric(a):return np.triu(a)+np.triu(a,1).T
def modal_data(signals):
    j=np.arange(signals);q=np.eye(signals);q[:2,:2]=np.array([[1.,1.],[1.,-1.]])/np.sqrt(2)
    if signals==4:q[2:,2:]=q[:2,:2]
    diag=dict(R=17.+3*j,L=(400.+50*j)*1e-9,G=.001+.0005*j,C_inf=(180.+20*j)*1e-12)
    delta=np.zeros((2,signals));delta[0,0]=300e-12;delta[1,1]=80e-12
    if signals==4:delta[1,2]=120e-12
    poles=np.array([8e7,7e8])
    matrices={k:symmetric((q*d)@q.T) for k,d in diag.items()}
    matrices['delta_C']=np.array([symmetric((q*d)@q.T) for d in delta]);matrices['relaxation_hz']=poles
    return q,diag,delta,matrices
def amp(signals):return np.array([1.,-.4,.2,-.1])[:signals]
def call(t,drive,n,signals,matrices,rs=None,rl=None):
    return response(t,drive,signals=signals,**matrices,length=.1,cells=n,
        source_resistance=np.full(signals,25.) if rs is None else rs,
        load_resistance=np.full(signals,100.) if rl is None else rl)
def frequency_reference(f,signals,n=None):
    q,diag,delta,mats=modal_data(signals);modes=[]
    for j in range(signals):
        z=diag['R'][j]+2j*np.pi*f*diag['L'][j]
        cap=diag['C_inf'][j]+sum(d[j]/(1+1j*f/p) for d,p in zip(delta,mats['relaxation_hz']))
        y=diag['G'][j]+2j*np.pi*f*cap
        if n is None:
            medium=require_tool('scikit-rf').media.DefinedGammaZ0(frequency=require_tool('scikit-rf').Frequency.from_f([f],unit='hz'),z0_port=50.,z0=np.sqrt(z/y),gamma=np.sqrt(z*y))
            aa,bb,cc,dd=medium.line(.1,unit='m').a[0].ravel();far=1/(aa+bb/100+25*(cc+dd/100));modes.append([(aa+bb/100)*far,far])
        else:
            dx=.1/n;weights=np.ones(n+1);weights[[0,-1]]=.5;k=np.diag(y*dx*weights).astype(complex);inj=np.zeros(n+1,complex)
            k[0,0]+=1/25;inj[0]=1/25;k[-1,-1]+=1/100
            for m in range(n):k[m,m]+=1/(z*dx);k[m+1,m+1]+=1/(z*dx);k[m,m+1]-=1/(z*dx);k[m+1,m]-=1/(z*dx)
            modes.append(np.linalg.solve(k,inj)[[0,n]])
    modes=np.array(modes);amplitudes=q.T@amp(signals)
    return np.r_[q@(amplitudes*modes[:,0]),q@(amplitudes*modes[:,1])]
def phasor(f,n,cycles,samples,signals):
    _,_,_,mats=modal_data(signals);t=np.arange(cycles*samples+1)/(f*samples);drive=np.sin(2*np.pi*f*t)[:,None]*amp(signals)
    a=call(t,drive,n,signals,mats);last=slice(-4*samples-1,-1);phase=np.exp(-2j*np.pi*f*t[last])
    return 2/len(phase)*(phase@a.voltage[last])/(-1j),a


def record_kcl(clock,signals,values):
    result=make_record(case=f'psd-multiconductor-debye-charge-kcl-{signals}',physics='finite passive multiconductor Debye ladder',api='psd_multiconductor_debye_rlgc_ladder_response',
        discretization='PWL lsim mass equations with polarization voltage',tool='scipy',tool_discretization='independent charge-state node KCL DOP853 across source breakpoints',
        matched=['R/L/G/Cinf/DeltaC/poles','cell topology','drive','positive resistive ends','zero initial state'],
        not_matched=['state coordinates','assembly','propagation method'],
        observables=[observable('voltage','V','max_absolute',values['voltage_error'],1e-8),observable('current','A','max_absolute',values['current_error'],1e-9)],
        analytical_acceptance='Scalar/modal/block/zero-strength limits and both relative1e-10 power balances; no field extraction.',stopwatch=clock)
    result['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(result)


def record_space(clock,signals,f,cases):
    result=make_record(case=f'psd-multiconductor-debye-continuous-{signals}-{f}',physics='commuting multiconductor Debye line',api='psd_multiconductor_debye_rlgc_ladder_response',
        discretization='finite pi ladders16/32/64; PWL sine; final-four-cycle phasor',tool='scikit-rf',tool_discretization='independent modal DefinedGammaZ0 distributed ABCD at explicit Debye capacitance',
        matched=['modal R/L/G/Cinf/strengths/poles','frequency','length','source/load resistance','source amplitudes'],
        not_matched=['finite cells versus continuous line','finite-time PWL versus sinusoidal steady state'],
        observables=[observable('voltage','V','max_absolute',cases[-1]['voltage_error'],1e-3)],
        analytical_acceptance='Strictly decreasing cell error plus separate time128/256/512 and horizon8/9/10 checks; no arbitrary-band guarantee.',stopwatch=clock)
    result['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(result)


@pytest.mark.parametrize('signals',[3,4])
def test_independent_limits_kcl_and_time_space_convergence(signals):
    clock=Stopwatch()
    item=dict(signals=signals);q,diag,delta,mats=modal_data(signals)
    t=np.linspace(0,12e-9,121);drive=np.minimum(t/2e-9,1.)[:,None]*amp(signals)
    limits=[];item['scalar_limits']=limits
    for basis in [np.eye(signals),q]:
        matrices={k:symmetric((basis*d)@basis.T) for k,d in diag.items()};matrices.update(delta_C=np.array([symmetric((basis*d)@basis.T) for d in delta]),relaxation_hz=mats['relaxation_hz'])
        result=call(t,drive,8,signals,matrices);modal_drive=drive@basis
        refs=[debye_rlgc_ladder_response(t,modal_drive[:,j],**{k:d[j] for k,d in diag.items()},delta_C=delta[:,j],relaxation_hz=mats['relaxation_hz'],length=.1,cells=8,source_resistance=25.,load_resistance=100.) for j in range(signals)]
        vv=np.stack([x.voltage for x in refs],axis=2)@basis.T;ii=np.stack([x.current for x in refs],axis=2)@basis.T
        vv=np.concatenate((vv[:,0],vv[:,1]),axis=1);ii=np.concatenate((ii[:,0],ii[:,1]),axis=1)
        ev=float(np.max(abs(result.voltage-vv)));ei=float(np.max(abs(result.current-ii)))
        limits.append(dict(basis='diagonal' if np.array_equal(basis,np.eye(signals)) else 'modal',voltage_error=ev,current_error=ei));assert ev<=1e-10 and ei<=1e-12
    # Independently assembled 2+1 or 2+2 exact block limits.
    block={k:np.diag(d) for k,d in diag.items()};block['delta_C']=np.array([np.diag(d) for d in delta]);block['relaxation_hz']=mats['relaxation_hz'];vv=np.zeros((len(t),2*signals));ii=np.zeros_like(vv)
    for lo,hi in [(0,2),(2,signals)]:
        count=hi-lo
        if count==2:
            for key,cross in dict(R=2.,L=60e-9,G=-.0001,C_inf=-20e-12).items():block[key][lo,lo+1]=block[key][lo+1,lo]=cross
            block['delta_C'][:,lo:hi,lo:hi]=np.array([[[150.,-150.],[-150.,150.]],[[40.,40.],[40.,40.]]])*1e-12
            ref=psd_coupled_debye_rlgc_ladder_response(t,drive[:,lo:hi],**{k:block[k][lo:hi,lo:hi] for k in diag},delta_C=block['delta_C'][:,lo:hi,lo:hi],relaxation_hz=mats['relaxation_hz'],length=.1,cells=8,source_resistance=[25.,25.],load_resistance=[100.,100.])
        else:
            ref=debye_rlgc_ladder_response(t,drive[:,lo],**{k:block[k][lo,lo] for k in diag},delta_C=block['delta_C'][:,lo,lo],relaxation_hz=mats['relaxation_hz'],length=.1,cells=8,source_resistance=25.,load_resistance=100.)
        vv[:,lo:hi]=ref.voltage[:,:count];vv[:,signals+lo:signals+hi]=ref.voltage[:,count:];ii[:,lo:hi]=ref.current[:,:count];ii[:,signals+lo:signals+hi]=ref.current[:,count:]
    result=call(t,drive,8,signals,block);ev=float(np.max(abs(result.voltage-vv)));ei=float(np.max(abs(result.current-ii)));item['block_limits']=dict(voltage_error=ev,current_error=ei);assert ev<=1e-10 and ei<=1e-12
    zero=dict(mats,delta_C=np.zeros_like(mats['delta_C']));result=call(t,drive,8,signals,zero)
    ref=multiconductor_rlgc_ladder_response(t,drive,signals=signals,**{k:mats[k] for k in ['R','L','G']},C=mats['C_inf'],length=.1,cells=8,source_resistance=[25.]*signals,load_resistance=[100.]*signals)
    ev=float(np.max(abs(result.voltage-ref.voltage)));ei=float(np.max(abs(result.current-ref.current)));item['zero_strength']=dict(voltage_error=ev,current_error=ei);assert ev<=1e-10 and ei<=1e-12
    # Original charge-state KCL; independent of candidate mass/k/auxiliary-voltage construction.
    j=np.arange(signals);off=np.eye(signals,k=1)+np.eye(signals,k=-1)
    r=np.diag(20.+3*j)+2*off;l=(np.diag(450.+20*j)+60*off)*1e-9
    g=np.diag(.002+.0002*j)-.0002*off;c=(np.diag(210.+10*j)-20*off)*1e-12
    ds=np.zeros((2,signals,signals));ds[0,:2,:2]=np.array([[80.,-40.],[-40.,20.]])*1e-12;ds[1,1:3,1:3]=np.array([[32.,32.],[32.,32.]])*1e-12
    r=np.zeros((signals,signals));r[:2,:2]=[[20.,-20.],[-20.,20.]]
    g=np.zeros_like(r);g[1:3,1:3]=np.array([[.002,.002],[.002,.002]])
    rs=23.+7*j;rl=91.+11*j;poles=mats['relaxation_hz'];tau=1/(2*np.pi*poles);n=8;dx=.1/n;weights=np.ones(n+1);weights[[0,-1]]=.5;nv=signals*(n+1);base=nv+signals*n;u=np.linspace(0,12,241)
    def drive_u(x):return min(x/2.,1.)*amp(signals)
    def dynamics(x,state):
        v=state[:nv].reshape(n+1,signals);i=state[nv:base].reshape(n,signals);charge=state[base:].reshape(n+1,2,signals);dq=np.empty_like(charge)
        for p,mat in enumerate(ds):dq[:,p]=(v@mat.T-charge[:,p])/tau[p]
        flow=np.zeros_like(v);flow[:-1]-=i;flow[1:]+=i;flow[0]+=(drive_u(x)-v[0])/rs;flow[-1]-=v[-1]/rl
        dv=np.linalg.solve(c,(flow/(dx*weights[:,None])-v@g.T-dq.sum(axis=1)).T).T;di=np.linalg.solve(l,((v[:-1]-v[1:])/dx-i@r.T).T).T
        return 1e-9*np.r_[dv.ravel(),di.ravel(),dq.ravel()]
    state=np.zeros(base+2*nv);values=np.zeros((len(u),len(state)))
    with clock('reference'):
        for left,right in [(0.,2.),(2.,12.)]:
            idx=np.flatnonzero((u>left)&(u<=right));sol=solve_ivp(dynamics,[left,right],state,method='DOP853',t_eval=u[idx],rtol=1e-11,atol=1e-15,max_step=.005);assert sol.success;values[idx]=sol.y.T;state=sol.y[:,-1]
    v=values[:,:nv].reshape(len(u),n+1,signals);dd=np.array([drive_u(x) for x in u]);vv=np.concatenate((v[:,0],v[:,-1]),axis=1);ii=np.concatenate(((dd-v[:,0])/rs,-v[:,-1]/rl),axis=1)
    with clock('openphysics'):
        result=call(u*1e-9,dd,n,signals,dict(R=r,L=l,G=g,C_inf=c,delta_C=ds,relaxation_hz=poles),rs,rl)
    ev=float(np.max(abs(result.voltage-vv)));ei=float(np.max(abs(result.current-ii)))
    item['independent_kcl']=dict(voltage_error=ev,current_error=ei,power_error=result.power_balance_relative_error,total_power_error=result.total_power_balance_relative_error);assert ev<=1e-8 and ei<=1e-9
    record_kcl(clock,signals,item['independent_kcl'])
    errors=[]
    for samples in [128,256,512]:
        ph,a=phasor(1e8,64,10,samples,signals);err=float(np.max(abs(ph-frequency_reference(1e8,signals,64))));errors.append(err);print('time',signals,samples,err,flush=True)
    item['time_refinement']=errors;assert errors[2]<errors[1]<errors[0]
    phases=[phasor(1e8,64,cycles,512,signals)[0] for cycles in [8,9,10]];diff=[float(np.max(abs(phases[k+1]-phases[k]))) for k in range(2)];item['horizon_differences']=diff;assert max(diff)<=1e-8
    spatial=[];item['continuous_spatial']=spatial
    for f,cycles,samples in [(1e8,10,512),(5e8,30,256)]:
        spatial_clock=Stopwatch()
        with spatial_clock('reference'):
            ref=frequency_reference(f,signals)
        cases=[]
        for cells in [16,32,64]:
            with spatial_clock('openphysics'):
                ph,a=phasor(f,cells,cycles,samples,signals)
            err=float(np.max(abs(ph-ref)));cases.append(dict(cells=cells,voltage_error=err,power_error=a.power_balance_relative_error,total_power_error=a.total_power_balance_relative_error));print('space',signals,f,cells,err,flush=True)
        spatial.append(dict(frequency=f,cycles=cycles,samples=samples,cases=cases));assert cases[2]['voltage_error']<cases[1]['voltage_error']<cases[0]['voltage_error'] and cases[2]['voltage_error']<=.001
        record_space(spatial_clock,signals,f,cases)


def run(signals=3,time=None,source=None,**changes):
    time=np.linspace(0,12e-9,121) if time is None else time
    source=drive(time,signals) if source is None else source
    _,_,_,mats=modal_data(signals)
    kw=dict(signals=signals,**mats,length=.1,cells=4,source_resistance=[25.]*signals,load_resistance=[100.]*signals)
    kw.update(changes)
    return response(time,source,**kw)


def drive(t,signals):return np.minimum(t/2e-9,1.)[:,None]*amp(signals)


def power_checks(a):
    assert a.power_balance_relative_error<=1e-10 and a.total_power_balance_relative_error<=1e-10
    np.testing.assert_allclose(a.total_energy_rate,a.line_power-a.series_loss-a.shunt_loss-a.relaxation_loss,rtol=1e-10,atol=1e-15)
    for name in ['energy','polarization_energy','relaxation_loss','series_loss','shunt_loss','source_resistor_loss','load_resistor_loss']:
        assert np.all(getattr(a,name)>=0)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('pulse',[False,True])
@pytest.mark.parametrize('lossless',[False,True])
def test_states_lumped_polarization_units_copy_and_passivity(signals,pulse,lossless):
    t=np.linspace(0,12e-9,121);d=drive(t,signals);_,_,_,m=modal_data(signals)
    if pulse:d*=np.clip((6e-9-t)/2e-9,0,1)[:,None]
    kw=dict(R=np.zeros((signals,signals)),G=np.zeros((signals,signals))) if lossless else {}
    a=run(signals,t,d,**kw);power_checks(a)
    assert type(a) is PSDMulticonductorDebyeRLGCLadderResponse
    assert a.port_names==tuple(f'{end}_{j}' for end in ('near','far') for j in range(signals))
    assert a.node_voltage.shape==(121,5,signals) and a.segment_current.shape==(121,4,signals)
    assert a.voltage.shape==a.current.shape==(121,2*signals)
    assert a.polarization_voltage.shape==a.polarization_charge.shape==a.polarization_current.shape==(121,5,2,signals)
    assert np.all(a.node_voltage[0]==0) and np.all(a.segment_current[0]==0) and np.all(a.polarization_voltage[0]==0)
    np.testing.assert_allclose(a.current[:,:signals],(d-a.voltage[:,:signals])/25)
    np.testing.assert_allclose(a.current[:,signals:],-a.voltage[:,signals:]/100)
    weights=np.ones(5);weights[[0,-1]]=.5
    for p,mat in enumerate(m['delta_C']):
        np.testing.assert_allclose(a.polarization_charge[:,:,p],.1/4*weights[None,:,None]*(a.polarization_voltage[:,:,p]@mat.T),rtol=1e-14,atol=0)
        expected=.1/4*weights[None,:,None]*((a.node_voltage-a.polarization_voltage[:,:,p])@mat.T)*2*np.pi*m['relaxation_hz'][p]
        np.testing.assert_allclose(a.polarization_current[:,:,p],expected,rtol=1e-9,atol=1e-15)
    original=a.to_dict(include_states=True);json.dumps(original,allow_nan=False)
    assert original['scope']=='finite-passive-psd-multiconductor-debye-ladder-startup'
    assert 'polarization_charge_c' not in a.to_dict()
    t[:]=4;d[:]=5;assert a.to_dict(include_states=True)==original
    inputs=a.inputs;inputs['signals']=99;assert a.inputs['signals']==signals
    for name in ['time','source_voltages','node_voltage','segment_current','voltage','current','energy','energy_rate','series_loss','shunt_loss','line_power','source_power','source_resistor_loss','load_resistor_loss','polarization_voltage','polarization_charge','polarization_current','polarization_energy','polarization_energy_rate','relaxation_loss']:
        value=getattr(a,name);assert not value.flags.writeable
        changed=np.array(value);b=replace(a,**{name:changed});changed[:]=9;np.testing.assert_array_equal(getattr(b,name),value)
    assert not a.total_energy.flags.writeable and not a.total_energy_rate.flags.writeable
    with pytest.raises(ValueError):a.to_dict(include_states=1)
    with pytest.raises(ValueError):replace(a,polarization_voltage=np.full_like(a.polarization_voltage,np.nan))
    with pytest.raises(ValueError,match='response must be'):startup_port_waves(a,z_ref=[50.]*(2*signals))


@pytest.mark.parametrize('signals',[3,4])
def test_zero_drive_linear_time_impedance_conductor_and_pole_invariants(signals):
    t=np.linspace(0,12e-9,121);d=drive(t,signals);a=run(signals,t,d);_,_,_,m=modal_data(signals)
    z=run(signals,t,np.zeros_like(d));assert not np.any(z.total_energy) and z.power_balance_relative_error==z.total_power_balance_relative_error==0
    linear=run(signals,t,-2*d)
    timed=run(signals,3*t,d,L=3*m['L'],C_inf=3*m['C_inf'],delta_C=3*m['delta_C'],relaxation_hz=m['relaxation_hz']/3)
    impedance=run(signals,t,d,R=3*m['R'],L=3*m['L'],G=m['G']/3,C_inf=m['C_inf']/3,delta_C=m['delta_C']/3,source_resistance=[75.]*signals,load_resistance=[300.]*signals)
    reverse=run(signals,t,d,delta_C=m['delta_C'][::-1],relaxation_hz=m['relaxation_hz'][::-1])
    for b,vs,cs,es in [(linear,-2,-2,4),(timed,1,1,3),(impedance,1,1/3,1/3),(reverse,1,1,1)]:
        np.testing.assert_allclose(b.voltage,vs*a.voltage,rtol=1e-10,atol=1e-12)
        np.testing.assert_allclose(b.current,cs*a.current,rtol=1e-10,atol=1e-12)
        np.testing.assert_allclose(b.total_energy,es*a.total_energy,rtol=1e-10,atol=1e-22);power_checks(b)
    np.testing.assert_allclose(reverse.polarization_charge,a.polarization_charge[:,:,::-1],rtol=1e-10,atol=1e-22)
    p=np.arange(signals)[::-1];pm={k:v[np.ix_(p,p)] for k,v in m.items() if k in ['R','L','G','C_inf']};pm['delta_C']=m['delta_C'][:,p][:,:,p]
    perm=run(signals,t,d[:,p],**pm);cols=np.r_[p,signals+p]
    np.testing.assert_allclose(perm.voltage,a.voltage[:,cols],rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(perm.polarization_charge,a.polarization_charge[:,:,:,p],rtol=1e-10,atol=1e-22)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('kind',['one','first-zero','last-zero','all-zero'])
def test_declared_poles_zero_columns_and_input_copy(signals,kind):
    _,_,_,m=modal_data(signals);delta=m['delta_C'].copy();poles=m['relaxation_hz'].copy()
    if kind=='one':delta=delta[:1];poles=poles[:1]
    elif kind=='first-zero':delta[0]=0
    elif kind=='last-zero':delta[-1]=0
    else:delta[:]=0
    a=run(signals,delta_C=delta,relaxation_hz=poles);power_checks(a);original=a.to_dict(include_states=True)
    for p,mat in enumerate(delta):
        if not np.any(mat):
            for name in ['polarization_voltage','polarization_charge','polarization_current']:assert not np.any(getattr(a,name)[:,:,p])
    assert a.polarization_voltage.shape[2]==len(poles)
    delta[:]=99;poles[:]=1;assert a.to_dict(include_states=True)==original


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('bad',['empty','many','shape','asymmetric','negative','singular','ratio','complex','boolean','nan','inf'])
def test_strict_strengths(signals,bad):
    _,_,_,m=modal_data(signals);v=m['delta_C'].copy()
    if bad=='empty':v=v[:0]
    elif bad=='many':v=np.concatenate([v,v])
    elif bad=='shape':v=v[:,:,:-1]
    elif bad=='asymmetric':v[0,0,1]=np.nextafter(v[0,1,0],np.inf)
    elif bad=='negative':v[0]=-np.eye(signals)
    elif bad=='singular':v[0]=np.diag([1.]*(signals-1)+[0.])
    elif bad=='ratio':v[0]=np.diag([1.]*(signals-1)+[1e-13])
    elif bad=='complex':v=v.astype(complex)
    elif bad=='boolean':v=v.astype(bool)
    elif bad=='nan':v[0,0,0]=np.nan
    else:v[0,0,0]=np.inf
    if bad in ('singular','ratio'):
        a=run(signals,delta_C=v);power_checks(a);assert a.inputs['delta_C_f_per_m']==v.tolist()
    else:
        with pytest.raises(ValueError):run(signals,delta_C=v)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('poles',[[],[1.],[1.,2.,3.],[-1.,1.],[0.,1.],[1.,np.inf],[1.,np.nan],[True,False],[1+0j,2+0j],[[1.,2.]]])
def test_strict_poles(signals,poles):
    with pytest.raises(ValueError):run(signals,relaxation_hz=poles)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('poles',[[1e308,1.],[1e-320,1.]])
def test_pole_finite_scale_guards(signals,poles):
    with pytest.raises(ValueError):run(signals,relaxation_hz=poles)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('name',['R','L','G','C_inf'])
@pytest.mark.parametrize('bad',['shape','asymmetric','negative','singular','ratio','complex','boolean','nan','inf'])
def test_strict_matrices(signals,name,bad):
    _,_,_,m=modal_data(signals);v=m[name].copy()
    if bad=='shape':v=v[:-1]
    elif bad=='asymmetric':v[0,1]=np.nextafter(v[1,0],np.inf)
    elif bad=='negative':v=-np.eye(signals)
    elif bad=='singular':v=np.diag([1.]*(signals-1)+[0.])
    elif bad=='ratio':v=np.diag([1.]*(signals-1)+[1e-13])
    elif bad=='complex':v=v.astype(complex)
    elif bad=='boolean':v=v.astype(bool)
    elif bad=='nan':v[0,0]=np.nan
    else:v[0,0]=np.inf
    if name in ('R','G') and bad in ('singular','ratio'):
        a=run(signals,**{name:v});power_checks(a);assert a.inputs[name+'_ohm_per_m' if name=='R' else 'G_s_per_m']==v.tolist()
    else:
        with pytest.raises(ValueError):run(signals,**{name:v})


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('key,value',[
    ('cells',0),('cells',65),('cells',1.5),('cells',True),('length',0),('length',-1),('length',np.inf),
    ('source_resistance',25.),('load_resistance',None),('source_resistance',[0.,25.,25.]),
    ('load_resistance',[100.,100.]),('source_resistance',[np.inf]*3),('load_resistance',[-1.]*4)])
def test_strict_sizes_and_terminal_vectors(signals,key,value):
    with pytest.raises(ValueError):run(signals,**{key:value})


@pytest.mark.parametrize('signals',[None,True,2,5,3.0,'3'])
def test_explicit_signal_count(signals):
    _,_,_,m=modal_data(3)
    with pytest.raises(ValueError):psd_multiconductor_debye_rlgc_ladder_response([0.,1e-9],np.zeros((2,3)),signals=signals,**m,length=.1,cells=1,source_resistance=[25.]*3,load_resistance=[100.]*3)


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
@pytest.mark.parametrize('key,value',[('length',1e-320),('L',1e-320),('C_inf',1e-320),('R',1e308),('G',1e308)])
def test_finite_scale_guards(signals,key,value):
    kw={key:value if key=='length' else value*np.eye(signals)}
    with pytest.raises((ValueError,np.linalg.LinAlgError)):run(signals,**kw)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('limit',['slow','fast'])
def test_relaxation_extremes_approach_declared_constant_capacitance(signals,limit):
    t=np.linspace(0,12e-9,121);d=drive(t,signals);_,_,_,m=modal_data(signals)
    capacitance=m['C_inf'] if limit=='slow' else m['C_inf']+sum(m['delta_C'])
    ref=multiconductor_rlgc_ladder_response(t,d,signals=signals,
        **{k:m[k] for k in ['R','L','G']},C=capacitance,length=.1,cells=4,
        source_resistance=[25.]*signals,load_resistance=[100.]*signals)
    poles=[1e4,1e3,1e2] if limit=='slow' else [1e10,1e11,1e12]
    errors=[]
    for pole in poles:
        result=run(signals,t,d,relaxation_hz=[pole,pole]);power_checks(result)
        errors.append(float(np.max(abs(result.voltage-ref.voltage))))
    assert errors[2]<errors[1]<errors[0] and errors[2]<1e-3,errors


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('tiny',[0.,1e-13,1e-20])
def test_null_and_nearly_singular_strength_without_rank_clipping(signals,tiny):
    delta=np.array([np.diag([150e-12]+[150e-12*tiny]*(signals-1))])
    a=run(signals,delta_C=delta,relaxation_hz=[8e7]);power_checks(a)
    assert a.inputs['delta_C_f_per_m']==delta.tolist()
    assert np.any(a.polarization_voltage[:,:,:,1:])
    if tiny==0:
        assert not np.any(a.polarization_charge[:,:,:,1:])
        assert not np.any(a.polarization_current[:,:,:,1:])
    else:
        assert np.any(a.polarization_charge[:,:,:,1:])
        assert np.any(a.polarization_current[:,:,:,1:])
    weights=np.ones(5);weights[[0,-1]]=.5
    expected=.1/4*weights[None,:,None]*(a.polarization_voltage[:,:,0]@delta[0].T)
    np.testing.assert_array_equal(a.polarization_charge[:,:,0],expected)


@pytest.mark.parametrize('signals',[3,4])
def test_drive_only_null_direction_has_no_polarization_charge_energy_or_loss(signals):
    delta=np.array([np.diag([150e-12]+[0.]*(signals-1))]);t=np.linspace(0,12e-9,121)
    d=np.zeros((len(t),signals));d[:,-1]=np.minimum(t/2e-9,1.)
    a=run(signals,t,d,R=np.eye(signals)*20,L=np.eye(signals)*450e-9,G=np.eye(signals)*.002,
        C_inf=np.eye(signals)*210e-12,delta_C=delta,relaxation_hz=[8e7]);power_checks(a)
    assert np.any(a.polarization_voltage[:,:,:,-1])
    for name in ['polarization_charge','polarization_current','polarization_energy','polarization_energy_rate','relaxation_loss']:
        assert not np.any(getattr(a,name))


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('pulse',[False,True])
def test_noncommuting_rank_one_loss_and_declared_strengths(signals,pulse):
    t=np.linspace(0,12e-9,121);d=drive(t,signals)
    if pulse:d*=np.clip((6e-9-t)/2e-9,0,1)[:,None]
    r=np.zeros((signals,signals));r[:2,:2]=[[20.,-20.],[-20.,20.]]
    g=np.zeros_like(r);g[1:3,1:3]=[[.002,.002],[.002,.002]]
    a=run(signals,t,d,R=r,G=g);power_checks(a)
    assert a.inputs['R_ohm_per_m']==r.tolist() and a.inputs['G_s_per_m']==g.tolist()
    if pulse:assert np.any(a.polarization_energy_rate<0)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('name',['R','G','delta_C'])
def test_original_strict_strength_api_still_rejects_new_psd_case(signals,name):
    from sipi import multiconductor_debye_rlgc_ladder_response as strict
    from test_multiconductor_debye_startup import modal_data as strict_data
    _,_,_,m=strict_data(signals);matrix=np.diag([1.]*(signals-1)+[0.])
    m[name]=np.array([matrix])*1e-12 if name=='delta_C' else matrix*(20 if name=='R' else .002)
    if name=='delta_C':m['relaxation_hz']=np.array([8e7])
    t=np.linspace(0,12e-9,121);d=drive(t,signals)
    kw=dict(signals=signals,**m,length=.1,cells=4,source_resistance=[25.]*signals,load_resistance=[100.]*signals)
    with pytest.raises(ValueError):strict(t,d,**kw)
    power_checks(response(t,d,**kw))


@pytest.mark.parametrize('signals',[3,4])
def test_positive_strength_agrees_with_original_strict_model(signals):
    from sipi import multiconductor_debye_rlgc_ladder_response as strict
    from test_multiconductor_debye_startup import modal_data as strict_data
    _,_,_,m=strict_data(signals);t=np.linspace(0,12e-9,121);d=drive(t,signals)
    kw=dict(signals=signals,**m,length=.1,cells=4,source_resistance=[25.]*signals,load_resistance=[100.]*signals)
    a=response(t,d,**kw);b=strict(t,d,**kw);power_checks(a)
    for name,tolerance in [('voltage',1e-12),('current',1e-12),('total_energy',1e-22),('polarization_charge',1e-22)]:
        np.testing.assert_allclose(getattr(a,name),getattr(b,name),rtol=1e-10,atol=tolerance)
