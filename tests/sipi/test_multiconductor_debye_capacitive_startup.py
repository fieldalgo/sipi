# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""External capacitive boundaries: independent charge equations and limits."""
import json
import importlib.metadata as metadata
from dataclasses import replace
import numpy as np
import pytest
from scipy.integrate import solve_ivp
from crosscheck import Stopwatch,emit,make_record,observable,require_tool
from sipi import (psd_coupled_debye_capacitive_ladder_response,
    psd_multiconductor_debye_rlgc_ladder_response,startup_port_waves,
    MulticonductorDebyeCapacitiveLadderResponse,
    psd_multiconductor_debye_capacitive_ladder_response as response)
import sipi.multiconductor_debye_capacitive_startup as module
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
    return q,diag,delta,cl,mats

def power_checks(a):
    assert max(a.power_balance_relative_error,a.total_power_balance_relative_error)<=1e-10
    np.testing.assert_allclose(a.line_energy_rate,a.line_power-a.series_loss-a.shunt_loss-a.relaxation_loss,rtol=1e-10,atol=1e-15)
    np.testing.assert_allclose(a.total_energy_rate,a.source_power-a.source_resistor_loss-a.load_resistor_loss-a.series_loss-a.shunt_loss-a.relaxation_loss,rtol=1e-10,atol=1e-15)
    for name in ['energy','polarization_energy','load_capacitor_energy','series_loss','shunt_loss','relaxation_loss','source_resistor_loss','load_resistor_loss']:
        assert np.all(getattr(a,name)>=0),name

def call(t,drive,n,signals,mats,rs=None,rl=None,length=.1):
    a=response(t,drive,signals=signals,**mats,length=length,cells=n,
        source_resistance=np.full(signals,25.) if rs is None else rs,
        load_resistance=np.full(signals,100.) if rl is None else rl)
    power_checks(a);return a

def frequency_reference(f,signals,n=None):
    q,diag,delta,cl,mats=modal_data(signals);modes=[]
    for j in range(signals):
        z=diag['R'][j]+2j*np.pi*f*diag['L'][j]
        cap=diag['C_inf'][j]+sum(d[j]/(1+1j*f/p) for d,p in zip(delta,mats['relaxation_hz']))
        y=diag['G'][j]+2j*np.pi*f*cap;yl=1/100+2j*np.pi*f*cl[j]
        if n is None:
            medium=require_tool("scikit-rf").media.DefinedGammaZ0(frequency=require_tool("scikit-rf").Frequency.from_f([f],unit='hz'),z0_port=50.,z0=np.sqrt(z/y),gamma=np.sqrt(z*y))
            aa,bb,cc,dd=medium.line(.1,unit='m').a[0].ravel();far=1/(aa+bb*yl+25*(cc+dd*yl));modes.append([(aa+bb*yl)*far,far])
        else:
            dx=.1/n;weights=np.ones(n+1);weights[[0,-1]]=.5;k=np.diag(y*dx*weights).astype(complex);inj=np.zeros(n+1,complex)
            k[0,0]+=1/25;inj[0]=1/25;k[-1,-1]+=yl
            for m in range(n):k[m,m]+=1/(z*dx);k[m+1,m+1]+=1/(z*dx);k[m,m+1]-=1/(z*dx);k[m+1,m]-=1/(z*dx)
            modes.append(np.linalg.solve(k,inj)[[0,n]])
    modes=np.array(modes);amplitudes=q.T@amp(signals)
    return np.r_[q@(amplitudes*modes[:,0]),q@(amplitudes*modes[:,1])]

def phasor(f,n,cycles,samples,signals):
    *_,mats=modal_data(signals);t=np.arange(cycles*samples+1)/(f*samples);drive=np.sin(2*np.pi*f*t)[:,None]*amp(signals)
    a=call(t,drive,n,signals,mats);last=slice(-4*samples-1,-1);phase=np.exp(-2j*np.pi*f*t[last])
    return 2/len(phase)*(phase@a.voltage[last])/(-1j),a

@pytest.mark.parametrize('signals',[3,4])
def test_independent_equations_block_rc_and_frequency_refinement(signals):
    require_tool('scipy');require_tool('scikit-rf');clock=Stopwatch()
    def measured_phasor(*args):
        with clock('openphysics'):return phasor(*args)
    def measured_reference(*args):
        with clock('reference'):return frequency_reference(*args)
    item=dict(signals=signals);q,diag,delta,cl,mats=modal_data(signals)
    t=np.linspace(0,12e-9,121);drive=np.minimum(t/2e-9,1.)[:,None]*amp(signals)
    # Block-diagonal inputs: 2+1 or2+2; the one active channel uses an
    # uncoupled, unexcited second channel in the existing two-signal API.
    block={k:np.diag(d) for k,d in diag.items()};block.update(delta_C=np.array([np.diag(d) for d in delta]),relaxation_hz=mats['relaxation_hz'],load_capacitance=np.diag(cl))
    vv=np.zeros((len(t),2*signals));ii=np.zeros_like(vv)
    for lo,hi in [(0,2),(2,signals)]:
        count=hi-lo
        if count==2:
            for key,cross in dict(R=2.,L=60e-9,G=-.0001,C_inf=-20e-12).items():block[key][lo,lo+1]=block[key][lo+1,lo]=cross
            block['delta_C'][:,lo:hi,lo:hi]=np.array([[[150.,-150.],[-150.,150.]],[[40.,40.],[40.,40.]]])*1e-12
            block['load_capacitance'][lo:hi,lo:hi]=np.array([[30.,-5.],[-5.,40.]])*1e-12
            args={k:block[k][lo:hi,lo:hi] for k in [*diag,'load_capacitance']};args['delta_C']=block['delta_C'][:,lo:hi,lo:hi];dd=drive[:,lo:hi]
        else:
            args={k:np.diag([block[k][lo,lo],dummy]) for k,dummy in dict(R=0.,L=1e-9,G=0.,C_inf=1e-12,load_capacitance=0.).items()}
            args['delta_C']=np.array([np.diag([d[lo,lo],0.]) for d in block['delta_C']]);dd=np.c_[drive[:,lo],np.zeros(len(t))]
        with clock("reference"):ref=psd_coupled_debye_capacitive_ladder_response(t,dd,**args,relaxation_hz=mats['relaxation_hz'],length=.1,cells=8,source_resistance=[25.,25.],load_resistance=[100.,100.])
        vv[:,lo:hi]=ref.voltage[:,:count];vv[:,signals+lo:signals+hi]=ref.voltage[:,2:2+count]
        ii[:,lo:hi]=ref.current[:,:count];ii[:,signals+lo:signals+hi]=ref.current[:,2:2+count]
    with clock("openphysics"):result=call(t,drive,8,signals,block);ev=float(np.max(abs(result.voltage-vv)));ei=float(np.max(abs(result.current-ii)))
    item['block_limits']=dict(voltage_error=ev,current_error=ei);assert ev<=1e-10 and ei<=1e-12
    with clock("openphysics"):result=call(t,drive,8,signals,dict(mats,load_capacitance=np.zeros((signals,signals))))
    with clock("reference"):ref=psd_multiconductor_debye_rlgc_ladder_response(t,drive,signals=signals,**{k:v for k,v in mats.items() if k!='load_capacitance'},length=.1,cells=8,source_resistance=[25.]*signals,load_resistance=[100.]*signals)
    ev=float(np.max(abs(result.voltage-ref.voltage)));ei=float(np.max(abs(result.current-ref.current)))
    item['zero_load']=dict(voltage_error=ev,current_error=ei);assert ev<=1e-10 and ei<=1e-12
    assert not np.any(result.load_capacitor_current) and not np.any(result.load_capacitor_energy)
    # Independent charge-state KCL, including external C in the far node.
    j=np.arange(signals);off=np.eye(signals,k=1)+np.eye(signals,k=-1)
    r=np.zeros((signals,signals));r[:2,:2]=[[20.,-20.],[-20.,20.]]
    g=np.zeros_like(r);g[1:3,1:3]=[[.002,.002],[.002,.002]]
    l=(np.diag(450.+20*j)+60*off)*1e-9;c=(np.diag(210.+10*j)-20*off)*1e-12
    ds=np.zeros((2,signals,signals));ds[0,:2,:2]=np.array([[80.,-40.],[-40.,20.]])*1e-12;ds[1,1:3,1:3]=np.array([[32.,32.],[32.,32.]])*1e-12
    load=(np.diag(20.+4*j)-3*off)*1e-12;rs=23.+7*j;rl=91.+11*j;poles=mats['relaxation_hz'];tau=1/(2*np.pi*poles)
    n=8;dx=.1/n;weights=np.ones(n+1);weights[[0,-1]]=.5;nv=signals*(n+1);base=nv+signals*n;u=np.linspace(0,12,241)
    def drive_u(x):return min(x/2.,1.)*amp(signals)
    def dynamics(x,state):
        v=state[:nv].reshape(n+1,signals);i=state[nv:base].reshape(n,signals);charge=state[base:].reshape(n+1,2,signals);dq=np.empty_like(charge)
        for p,mat in enumerate(ds):dq[:,p]=(v@mat.T-charge[:,p])/tau[p]
        flow=np.zeros_like(v);flow[:-1]-=i;flow[1:]+=i;flow[0]+=(drive_u(x)-v[0])/rs;flow[-1]-=v[-1]/rl
        dv=np.linalg.solve(c,(flow/(dx*weights[:,None])-v@g.T-dq.sum(axis=1)).T).T
        dv[-1]=np.linalg.solve(dx*weights[-1]*c+load,flow[-1]-dx*weights[-1]*(v[-1]@g.T+dq[-1].sum(axis=0)))
        di=np.linalg.solve(l,((v[:-1]-v[1:])/dx-i@r.T).T).T
        return 1e-9*np.r_[dv.ravel(),di.ravel(),dq.ravel()]
    state=np.zeros(base+2*nv);values=np.zeros((len(u),len(state)))
    for left,right in [(0.,2.),(2.,12.)]:
        idx=np.flatnonzero((u>left)&(u<=right))
        with clock('reference'):sol=solve_ivp(dynamics,[left,right],state,method='DOP853',t_eval=u[idx],rtol=1e-11,atol=1e-15,max_step=.005)
        assert sol.success;values[idx]=sol.y.T;state=sol.y[:,-1]
    v=values[:,:nv].reshape(len(u),n+1,signals);dd=np.array([drive_u(x) for x in u]);vv=np.concatenate((v[:,0],v[:,-1]),axis=1)
    derivative=np.array([dynamics(x,y) for x,y in zip(u,values)])/1e-9;dv=derivative[:,:nv].reshape(v.shape)
    ii=np.concatenate(((dd-v[:,0])/rs,-v[:,-1]/rl-dv[:,-1]@load.T),axis=1)
    with clock("openphysics"):result=call(u*1e-9,dd,n,signals,dict(R=r,L=l,G=g,C_inf=c,delta_C=ds,relaxation_hz=poles,load_capacitance=load),rs,rl)
    ev=float(np.max(abs(result.voltage-vv)));ei=float(np.max(abs(result.current-ii)))
    item['independent_kcl']=dict(voltage_error=ev,current_error=ei,power_error=result.power_balance_relative_error,total_power_error=result.total_power_balance_relative_error)
    print('kcl',signals,item['independent_kcl'],flush=True);assert ev<=1e-8 and ei<=1e-9
    # Closed-form PWL lumped RC limit as line length tends to zero.
    cap=(20.+5*j)*1e-12;tr=2e-9;t=np.linspace(0,12e-9,121);dd=np.minimum(t/tr,1.)[:,None]*amp(signals);tau_rc=20*cap
    def ramp(x):x=np.maximum(x,0)[:,None];return x+tau_rc*np.expm1(-x/tau_rc)
    expected=.8/tr*(ramp(t)-ramp(t-tr))*amp(signals);errors=[]
    lump=dict(R=np.zeros((signals,signals)),L=np.eye(signals)*450e-9,G=np.zeros((signals,signals)),C_inf=np.eye(signals)*210e-12,delta_C=np.zeros((1,signals,signals)),relaxation_hz=[8e7],load_capacitance=np.diag(cap))
    for length in [.01,.001,.0001]:
        with clock("openphysics"):result=call(t,dd,4,signals,lump,length=length);error=float(np.max(abs(result.voltage-np.c_[expected,expected])));errors.append(error)
    item['lumped_rc_length_limit']=errors;print('RC',signals,errors,flush=True);assert errors[2]<errors[1]<errors[0] and errors[2]<=1e-3
    errors=[]
    for samples in [128,256,512]:
        ph,a=measured_phasor(1e8,64,10,samples,signals);err=float(np.max(abs(ph-measured_reference(1e8,signals,64))));errors.append(err);print('time',signals,samples,err,flush=True)
    item['time_refinement']=errors;assert errors[2]<errors[1]<errors[0]
    phases=[measured_phasor(1e8,64,cycles,512,signals)[0] for cycles in [8,9,10]];diff=[float(np.max(abs(phases[k+1]-phases[k]))) for k in range(2)];item['horizon_differences']=diff;assert max(diff)<=1e-8
    spatial=[];item['continuous_spatial']=spatial
    for f,cycles,samples in [(1e8,8,1024),(5e8,30,256)]:
        ref=measured_reference(f,signals);cases=[]
        for cells in [16,32,64]:
            ph,a=measured_phasor(f,cells,cycles,samples,signals);err=float(np.max(abs(ph-ref)));cases.append(dict(cells=cells,voltage_error=err,power_error=a.power_balance_relative_error,total_power_error=a.total_power_balance_relative_error));print('space',signals,f,cells,err,flush=True)
        spatial.append(dict(frequency=f,cycles=cycles,samples=samples,cases=cases));assert cases[2]['voltage_error']<cases[1]['voltage_error']<cases[0]['voltage_error'] and cases[2]['voltage_error']<=.001

    record=make_record(case=f'multiconductor-debye-capacitive-{signals}',
        physics='zero-state passive multiconductor Debye circuit',
        api='sipi.psd_multiconductor_debye_capacitive_ladder_response',
        discretization='finite pi cells, canonical auxiliary voltages, PWL propagation',
        tool='scikit-rf',tool_discretization='modal distributed ABCD; separate charge-KCL DOP853 and lumped RC equation',
        matched=['explicit materials, dimensions, passive capacitor, resistances, drive and time'],
        not_matched=['continuous line versus finite cells; separate integration; no measured data'],
        observables=[observable('terminal voltage','V','maximum finest-cell error',max(x['cases'][-1]['voltage_error'] for x in spatial),1e-3),
                     observable('terminal voltage','V','charge-KCL maximum error',item['independent_kcl']['voltage_error'],1e-8),
                     observable('terminal current','A','charge-KCL maximum error',item['independent_kcl']['current_error'],1e-9)],
        analytical_acceptance='zero external C, 2+1/2+2 block, decreasing short-line RC limit; unchanged refinement gates',stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)

def run(signals,t=None,d=None,**changes):
    t=np.linspace(0,12e-9,121) if t is None else t
    d=np.minimum(t/2e-9,1.)[:,None]*amp(signals) if d is None else d
    *_,m=modal_data(signals)
    kw=dict(signals=signals,**m,length=.1,cells=4,source_resistance=[25.]*signals,load_resistance=[100.]*signals)
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
    np.testing.assert_allclose(a.current[:,signals:],-far/100-a.load_capacitor_current,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(a.load_resistor_loss,np.sum(far**2/100,axis=1),rtol=1e-10,atol=1e-15)
    np.testing.assert_allclose(a.load_capacitor_energy,.5*np.einsum('ti,ij,tj->t',far,cap,far),rtol=1e-10,atol=1e-22)
    np.testing.assert_allclose(a.load_capacitor_power,np.sum(far*a.load_capacitor_current,axis=1),rtol=1e-10,atol=1e-15)
    np.testing.assert_array_equal(a.total_energy,a.line_energy+a.load_capacitor_energy)
    np.testing.assert_array_equal(a.total_energy_rate,a.line_energy_rate+a.load_capacitor_power)
    if tiny==0:assert not np.any(a.load_capacitor_current[:,1:])
    else:assert np.any(a.load_capacitor_current[:,1:])
    if pulse:assert np.any(a.load_capacitor_power<0)

@pytest.mark.parametrize('signals',[3,4])
def test_linear_time_impedance_pole_and_signal_permutations(signals):
    t=np.linspace(0,12e-9,121);d=np.minimum(t/2e-9,1.)[:,None]*amp(signals);*_,m=modal_data(signals);a=run(signals,t,d)
    linear=run(signals,t,-2*d)
    timed=run(signals,3*t,d,L=3*m['L'],C_inf=3*m['C_inf'],delta_C=3*m['delta_C'],relaxation_hz=m['relaxation_hz']/3,load_capacitance=3*m['load_capacitance'])
    scaled=run(signals,t,d,R=3*m['R'],L=3*m['L'],G=m['G']/3,C_inf=m['C_inf']/3,delta_C=m['delta_C']/3,load_capacitance=m['load_capacitance']/3,source_resistance=[75.]*signals,load_resistance=[300.]*signals)
    poles=run(signals,t,d,delta_C=m['delta_C'][::-1],relaxation_hz=m['relaxation_hz'][::-1])
    for b,vs,cs,es in [(linear,-2,-2,4),(timed,1,1,3),(scaled,1,1/3,1/3),(poles,1,1,1)]:
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
    assert type(a) is MulticonductorDebyeCapacitiveLadderResponse
    assert a.polarization_voltage.shape==(121,5,len(poles),signals)
    weights=np.ones(5);weights[[0,-1]]=.5
    for p,mat in enumerate(delta):
        np.testing.assert_allclose(a.polarization_charge[:,:,p],.1/4*weights[None,:,None]*(a.polarization_voltage[:,:,p]@mat.T),rtol=1e-14,atol=0)
        if not np.any(mat):assert not np.any(a.polarization_voltage[:,:,p])
    saved=a.inputs;delta[:]=9;cap[:]=9;poles[:]=9;assert a.inputs==saved
    for name,value in a.__dict__.items():
        if isinstance(value,np.ndarray):assert not value.flags.writeable
    out=a.to_dict(include_states=True);json.dumps(out,allow_nan=False)
    assert out['scope']=='finite-passive-multiconductor-psd-debye-capacitive-startup'
    assert out['port_names']==[f'{end}_{j}' for end in ['near','far'] for j in range(signals)]
    out['input']['load_capacitance_f'][0][0]=9;assert a.inputs==saved
    with pytest.raises(ValueError):a.to_dict(include_states=1)
    with pytest.raises(ValueError,match='response must be'):startup_port_waves(a,z_ref=[50.]*(2*signals))

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
@pytest.mark.parametrize('key,value',[('cells',0),('cells',65),('cells',True),('cells',1.5),('length',0),('signals',2),('signals',5),('signals',True),('relaxation_hz',[0.,7e8]),('source_resistance',25.),('load_resistance',[0.,0.,0.])])
def test_original_resource_boundary_contracts(signals,key,value):
    *_,m=modal_data(signals);t=np.linspace(0,12e-9,121);d=np.minimum(t/2e-9,1.)[:,None]*amp(signals)
    kw=dict(signals=signals,**m,length=.1,cells=4,source_resistance=[25.]*signals,load_resistance=[100.]*signals);kw[key]=value
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
