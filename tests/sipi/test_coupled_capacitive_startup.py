# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit external load capacitance: independent LC, modal and KCL checks."""
import importlib.metadata as metadata
import json

import numpy as np
import pytest
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import coupled_capacitive_ladder_response, coupled_boundary_ladder_response
import sipi.coupled_boundary_startup as engine

R=np.array([[20.,3.],[3.,20.]])
L=np.array([[500.,100.],[100.,500.]])*1e-9
G=np.array([[.002,-.0003],[-.0003,.002]])
C=np.array([[220.,-40.],[-40.,220.]])*1e-12
CL=np.array([[30.,-5.],[-5.,30.]])*1e-12
Q=np.array([[1.,1.],[1.,-1.]])/np.sqrt(2)


def arguments(**changes):
    kw=dict(R=R,L=L,G=G,C=C,length=.1,cells=16,source_resistance=[25.,25.],load_resistance=[100.,100.],load_capacitance=CL)
    kw.update(changes);return kw


def run(time=None,drive=None,**changes):
    time=np.linspace(0,12e-9,121) if time is None else time
    drive=np.column_stack((np.minimum(np.asarray(time)/2e-9,1.),np.zeros(len(time)))) if drive is None else drive
    return coupled_capacitive_ladder_response(time,drive,**arguments(**changes))


def power_checks(r):
    assert np.min(r.energy)>=0 and np.min(r.load_capacitor_energy)>=0
    assert np.min(r.series_loss)>=0 and np.min(r.shunt_loss)>=0
    assert r.power_balance_relative_error<=1e-10 and r.total_power_balance_relative_error<=1e-10
    np.testing.assert_allclose(r.energy_rate,r.line_power-r.series_loss-r.shunt_loss,rtol=1e-10,atol=1e-14)
    np.testing.assert_allclose(r.total_energy_rate,r.source_power-r.source_resistor_loss-r.load_resistor_loss-r.series_loss-r.shunt_loss,rtol=1e-10,atol=1e-14)
    np.testing.assert_allclose(r.source_power,r.source_resistor_loss+r.load_resistor_loss+r.line_power+r.load_capacitor_power,rtol=1e-10,atol=1e-14)


@pytest.mark.parametrize('source,load',[([0.,37.],[0.,None]),([25.,25.],[100.,100.]),([0.,0.],[None,None])])
def test_zero_load_capacitance_reproduces_mixed_circuit(source,load):
    t=np.linspace(0,12e-9,121);drive=np.column_stack((np.minimum(t/2e-9,1.),np.zeros(len(t))))
    kw=arguments(source_resistance=source,load_resistance=load,cells=32,load_capacitance=np.zeros((2,2)))
    r=coupled_capacitive_ladder_response(t,drive,**kw);kw.pop('load_capacitance');old=coupled_boundary_ladder_response(t,drive,**kw)
    assert np.max(abs(r.voltage-old.voltage))<=1e-10 and np.max(abs(r.current-old.current))<=1e-12
    np.testing.assert_array_equal(r.node_voltage,old.node_voltage);np.testing.assert_array_equal(r.segment_current,old.segment_current)
    assert np.all(r.load_capacitor_current==0) and np.all(r.load_capacitor_energy==0)
    power_checks(r)


def test_single_cell_exact_lc_with_separate_line_and_load_energy():
    t=np.linspace(0,4,401);amp=np.array([1.,-.4]);drive=np.minimum(t,1.)[:,None]*amp;cl=np.array([.3,.7])
    r=run(t,drive,R=np.zeros((2,2)),L=np.eye(2),G=np.zeros((2,2)),C=.4*np.eye(2),length=1.,cells=1,
          source_resistance=[0.,0.],load_resistance=[None,None],load_capacitance=np.diag(cl))
    vol=[];current=[]
    for j in range(2):
        total=.2+cl[j];w=np.sqrt(1/total);before=amp[j]*(t-np.sin(w*t)/w);dvbefore=amp[j]*(1-np.cos(w*t))
        a=-amp[j]*np.sin(w)/w;b=amp[j]*(1-np.cos(w))/w;shift=t-1
        after=amp[j]+a*np.cos(w*shift)+b*np.sin(w*shift);dvafter=-a*w*np.sin(w*shift)+b*w*np.cos(w*shift)
        vol.append(np.where(t<=1,before,after));current.append(total*np.where(t<=1,dvbefore,dvafter))
    voltage=np.stack(vol,axis=-1);iline=np.stack(current,axis=-1);dv=iline/(.2+cl)
    slope=np.vstack((np.diff(drive,axis=0)/np.diff(t)[:,None],[0.,0.]));expectedi=np.concatenate((iline+.2*slope,-dv*cl),axis=1)
    line_energy=.5*np.sum(iline**2,axis=1)+.1*np.sum(drive**2+voltage**2,axis=1);cap_energy=.5*np.sum(cl*voltage**2,axis=1)
    for actual,expected in [(r.voltage[:,2:],voltage),(r.current,expectedi),(r.energy,line_energy),(r.load_capacitor_energy,cap_energy),
                            (r.load_capacitor_current,dv*cl),(r.total_energy,line_energy+cap_energy)]:
        np.testing.assert_allclose(actual,expected,rtol=1e-10,atol=1e-12)
    power_checks(r)


def test_independent_skrf_modal_capacitive_load_refinement():
    skrf=require_tool('scikit-rf');clock=Stopwatch();f=500e6;w=2*np.pi*f
    t=np.arange(20*256+1)/(f*256);drive=np.column_stack((np.sin(w*t),np.zeros(len(t))));modal=[]
    with clock('reference'):
        for m in range(2):
            rm,lm,gm,cm=[(Q.T@a@Q)[m,m] for a in [R,L,G,C]];clm=(Q.T@CL@Q)[m,m]
            gamma=np.sqrt((rm+1j*w*lm)*(gm+1j*w*cm));zc=np.sqrt((rm+1j*w*lm)/(gm+1j*w*cm));yl=1/100+1j*w*clm
            media=skrf.media.DefinedGammaZ0(frequency=skrf.Frequency.from_f([f],unit='hz'),z0_port=50.,z0=zc,gamma=gamma)
            a,b,c,d=media.line(.1,unit='m').a[0].ravel();vl=Q[0,m]/(a+b*yl+25*(c+d*yl));modal.append(np.array([(a+b*yl)*vl,vl]))
        expected=(np.stack(modal,axis=-1)@Q.T).ravel()
    last=slice(-4*256-1,-1);phase=np.exp(-1j*w*t[last]);errors=[]
    for n in [32,64,128]:
        with clock('openphysics'):r=run(t,drive,cells=n)
        phasor=2/len(phase)*(phase@r.voltage[last])/(-1j);errors.append(float(np.max(abs(phasor-expected))));power_checks(r)
    record=make_record(case='sipi-coupled-load-capacitance-modal',physics='passive two-signal line with external load capacitance',
        api='sipi.coupled_capacitive_ladder_response',discretization='32/64/128 fullmatrix finite cells plus endpoint capacitance',
        tool='scikit-rf',tool_discretization='modal continuous ABCD with Yload=1/R+jwCload and physical recombination',
        matched=['exchange-symmetric RLGC and Cload[[30,-5],[-5,30]]pF,0.1m,Rs25/RL100 each',
                 '500MHz first source,20cycles/256samplespercycle/final4-cycle phasor'],
        not_matched=['finite spatial cells and PWL input versus continuous frequency reference, interpolation error retained'],
        observables=[observable('four port voltage','V','maximum128-cell phasor error',errors[-1],.001)],
        analytical_acceptance='exact one-cell LC with separate load energy, asymmetric KCL and zero-C limits',stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    print('capacitive load phasor refinement',errors)
    assert errors[-1]<=.001 and errors[2]<errors[1]<errors[0]


def test_independent_asymmetric_node_kcl_with_full_load_capacitance():
    require_tool('scipy');from scipy.integrate import solve_ivp
    clock=Stopwatch();n=16;dx=.1/n;nv=2*(n+1);rmat=np.array([[25.,2.],[2.,17.]]);l=np.array([[510.,70.],[70.,430.]])*1e-9
    g=np.array([[.003,-.0002],[-.0002,.0015]]);c=np.array([[230.,-30.],[-30.,190.]])*1e-12;capload=np.array([[20.,-4.],[-4.,30.]])*1e-12
    u=np.linspace(0,12,241);free=np.arange(1,4*n+2)
    def drive(t):return np.array([np.interp(t,[0,2],[0,1]),np.interp(t,[0,3],[0,-.4])])
    def dynamics(t,xf,all_states=False):
        x=np.zeros(4*n+2);x[free]=xf;x[0]=drive(t)[0];v=x[:nv].reshape(n+1,2);i=x[nv:].reshape(n,2);dv=np.zeros_like(v)
        flow=np.zeros_like(v);flow[:-1]-=i;flow[1:]+=i;flow[0,1]+=(drive(t)[1]-v[0,1])/37.;flow[-1,0]-=v[-1,0]/91.
        dv[1:-1]=np.linalg.solve(c,(flow[1:-1]/dx-v[1:-1]@g.T).T).T
        dv[0,0]=.5/1e-9 if t<2 else 0.
        dv[0,1]=(flow[0,1]/(dx*.5)-g[1]@v[0]-c[1,0]*dv[0,0])/c[1,1]
        dv[-1]=np.linalg.solve(c*dx*.5+capload,flow[-1]-g@v[-1]*dx*.5)
        di=np.linalg.solve(l,((v[:-1]-v[1:])/dx-i@rmat.T).T).T;deriv=np.r_[dv.ravel(),di.ravel()]
        return (x,deriv) if all_states else 1e-9*deriv[free]
    ce,cu=np.linalg.eigh(c);cs=(cu*np.sqrt(ce))@cu.T;min_tau=float(.1*np.sqrt(np.linalg.eigvalsh(cs@l@cs)[0])/1e-9)
    with clock('reference'):
        ref=solve_ivp(dynamics,[0,12],np.zeros(len(free)),method='DOP853',t_eval=u,rtol=1e-10,atol=1e-12,max_step=min_tau/(5*n));assert ref.success
        pairs=[dynamics(t,xf,True) for t,xf in zip(u,ref.y.T)];full=np.array([x[0] for x in pairs]);deriv=np.array([x[1] for x in pairs])
        v=full[:,:nv].reshape(len(u),n+1,2);ii=full[:,nv:].reshape(len(u),n,2);dv=deriv[:,:nv].reshape(v.shape)
        ev=v[:,[0,n],:].reshape(len(u),4);ei=np.zeros_like(ev)
        ei[:,0]=(dv[:,0]@c[0]+v[:,0]@g[0])*dx*.5+ii[:,0,0]
        ei[:,1]=(np.array([drive(t)[1] for t in u])-v[:,0,1])/37.;ei[:,2:]=-dv[:,-1]@capload.T;ei[:,2]-=v[:,-1,0]/91.
    with clock('openphysics'):
        r=run(u*1e-9,np.array([drive(t) for t in u]),R=rmat,L=l,G=g,C=c,cells=n,source_resistance=[0.,37.],load_resistance=[91.,None],load_capacitance=capload)
    ve=float(np.max(abs(r.voltage-ev)));ie=float(np.max(abs(r.current-ei)));power_checks(r)
    record=make_record(case='sipi-coupled-load-capacitance-asymmetric-ode',physics='asymmetric passive finite circuit with external capacitor matrix',
        api='sipi.coupled_capacitive_ladder_response',discretization='mass-matrix free-state transform with PWL propagation',
        tool='scipy',tool_discretization='separate node KCL,DOP853; direct far-node Cline*dx/2+Cload solve',
        matched=['same16cells,asymmetric matrices,Rs[0,37]/RL[91,open],Cload[[20,-4],[-4,30]]pF,two ramps'],
        not_matched=['different propagation algorithms for same finite circuit,not independent spatial discretizations'],
        observables=[observable('four port voltage','V','maximum absolute difference',ve,1e-8),observable('four port current','A','maximum absolute difference',ie,1e-9)],
        analytical_acceptance='exact LC,zero-C,modal distributed reference and separate energy balances',stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    assert ve<=1e-8 and ie<=1e-9


def test_capacitance_at_two_shorts_has_zero_energy_and_no_state_effect():
    t=np.linspace(0,12e-9,121);drive=np.column_stack((np.minimum(t/2e-9,1.),np.zeros(len(t))))
    kw=arguments(cells=8,load_resistance=[0.,0.]);r=coupled_capacitive_ladder_response(t,drive,**kw)
    kw.pop('load_capacitance');old=coupled_boundary_ladder_response(t,drive,**kw)
    np.testing.assert_array_equal(r.node_voltage,old.node_voltage)
    assert np.all(r.load_capacitor_current==0) and np.all(r.load_capacitor_energy==0);power_checks(r)


def test_rank_one_capacitance_partial_short_and_resistor_loss_separation():
    cap=np.array([[20.,-20.],[-20.,20.]])*1e-12
    r=run(cells=8,load_resistance=[0.,None],load_capacitance=cap)
    assert np.all(r.voltage[:,2]==0) and np.all(r.load_resistor_loss==0)
    np.testing.assert_allclose(r.load_capacitor_current[:,0],-r.load_capacitor_current[:,1],rtol=1e-12,atol=1e-15)
    assert np.max(abs(r.load_capacitor_current[:,0]))>1e-4;power_checks(r)
    finite=run(cells=8)
    np.testing.assert_allclose(finite.load_resistor_loss,np.sum(finite.voltage[:,2:]**2/100.,axis=1),rtol=1e-12,atol=1e-15)
    assert np.max(abs(finite.load_resistor_loss-100*np.sum(finite.current[:,2:]**2,axis=1)))>1e-4
    power_checks(finite)


def test_lossless_trapped_energy_exchanges_with_external_capacitors():
    t=np.linspace(0,20e-9,401);pulse=np.interp(t,[0,2e-9,4e-9,6e-9],[0,1,1,0])
    r=run(t,np.column_stack((pulse,-.3*pulse)),R=np.zeros((2,2)),G=np.zeros((2,2)),cells=8,source_resistance=[0.,0.],load_resistance=[None,None])
    tail=t>=6e-9
    assert np.min(r.load_capacitor_power[tail])<0 and np.max(r.load_capacitor_power[tail])>0
    assert np.all(r.source_power[tail]==0)
    np.testing.assert_allclose(r.total_energy[tail],r.total_energy[tail][0],rtol=1e-10,atol=1e-23)
    power_checks(r)


def test_dc_resistive_limit_is_unchanged_by_load_capacitance():
    t=np.linspace(0,500e-9,2501);drive=np.column_stack((np.minimum(t/2e-9,1.),-.4*np.minimum(t/2e-9,1.)))
    rs=np.array([23.,37.]);rl=np.array([91.,113.]);r=run(t,drive,G=np.zeros((2,2)),cells=8,source_resistance=rs,load_resistance=rl)
    exact=np.linalg.solve(np.diag(rs+rl)+.1*R,drive[-1])
    expected=np.r_[drive[-1]-rs*exact,rl*exact]
    # The original200 ns fixture had not settled. Preserve the same DC gates;
    # resolve300/400/500 ns decay before the600 ns roundoff floor.
    indices=[1500,2000,2500]
    errors=[float(np.max(abs(r.voltage[k]-expected))) for k in indices]
    capcurrents=[float(np.max(abs(r.load_capacitor_current[k]))) for k in indices]
    assert errors[2]<errors[1]<errors[0] and capcurrents[2]<capcurrents[1]<capcurrents[0]
    for k in indices[-2:]:
        np.testing.assert_allclose(r.voltage[k],expected,rtol=1e-10,atol=1e-12)
        np.testing.assert_allclose(r.load_capacitor_current[k],np.zeros(2),rtol=0,atol=1e-13)

    np.testing.assert_allclose(r.load_capacitor_current[-1],np.zeros(2),rtol=0,atol=1e-13);power_checks(r)


def test_permutation_time_impedance_scaling_and_copies():
    t=np.linspace(0,12e-9,121);drive=np.column_stack((np.minimum(t/2e-9,1.),-.4*np.minimum(t/3e-9,1.)))
    cl=CL.copy();cl[0,0]+=10e-12;kw=dict(cells=8,source_resistance=[0.,37.],load_resistance=[91.,None],load_capacitance=cl)
    r=run(t,drive,**kw)
    perm=run(t,drive[:,::-1],R=R[::-1,::-1],L=L[::-1,::-1],G=G[::-1,::-1],C=C[::-1,::-1],cells=8,source_resistance=[37.,0.],load_resistance=[None,91.],load_capacitance=cl[::-1,::-1])
    np.testing.assert_allclose(perm.voltage,r.voltage[:,[1,0,3,2]],rtol=1e-10,atol=1e-12)
    scaled=run(t*1e6,drive,L=L*1e6,C=C*1e6,**dict(kw,load_capacitance=cl*1e6))
    np.testing.assert_allclose(scaled.voltage,r.voltage,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(scaled.total_energy/1e6,r.total_energy,rtol=1e-10,atol=1e-23)
    z=run(t,drive,R=R*1e3,L=L*1e3,G=G/1e3,C=C/1e3,**dict(kw,source_resistance=[0.,37e3],load_resistance=[91e3,None],load_capacitance=cl/1e3))
    np.testing.assert_allclose(z.voltage,r.voltage,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(z.load_capacitor_current*1e3,r.load_capacitor_current,rtol=1e-10,atol=1e-14)
    saved=r.to_dict();full=r.to_dict(include_states=True);t[:]=9;drive[:]=9;cl[:]=9
    full['input']['load_capacitance_f'][0][0]=99;full['load_capacitor_current_a'][0][0]=99
    assert r.to_dict()==saved and saved['scope']=='finite-passive-two-signal-capacitive-load-rlgc-startup'
    assert 'node_voltage_v' not in saved and np.shape(full['node_voltage_v'])==(121,9,2)
    assert not r.total_energy.flags.writeable and not r.total_energy_rate.flags.writeable
    for value in r.__dict__.values():
        if isinstance(value,np.ndarray):assert not value.flags.writeable
    json.dumps(saved,allow_nan=False)
    with pytest.raises(ValueError):r.to_dict(include_states=1)
    for value in [r,perm,scaled,z]:power_checks(value)


@pytest.mark.parametrize('cap',[
    None,0.,[1.,1.],np.zeros((3,3)),[[1.,0.],[0.,-1e-30]],[[True,0.],[0.,1.]],
    [[1.,1e-15],[0.,1.]],[[np.inf,0.],[0.,1.]],[[np.nan,0.],[0.,1.]],[[1j,0],[0,1]],
])
def test_invalid_load_capacitance_precedes_propagation(cap,monkeypatch):
    monkeypatch.setattr(engine,'lsim',lambda *a,**k:pytest.fail('invalid cap reached propagation'))
    with pytest.raises((ValueError,TypeError)):run(load_capacitance=cap)


@pytest.mark.parametrize('changes',[
    dict(cells=0),dict(cells=129),dict(source_resistance=[-1.,25.]),dict(load_resistance=[np.inf,None]),
    dict(R=-np.eye(2)),dict(C=np.zeros((2,2))),
    dict(C=np.eye(2)*1e308,length=3.,cells=1,load_capacitance=np.eye(2)*1e308),
])
def test_invalid_line_or_added_mass_precedes_propagation(changes,monkeypatch):
    monkeypatch.setattr(engine,'lsim',lambda *a,**k:pytest.fail('invalid line reached propagation'))
    with pytest.raises((ValueError,TypeError)):run(**changes)


def test_zero_input_has_zero_line_and_external_energy():
    r=run([0.,1e-9],[[0.,0.],[0.,0.]],cells=1)
    assert np.all(r.total_energy==0) and np.all(r.total_energy_rate==0)
    assert r.power_balance_relative_error==0 and r.total_power_balance_relative_error==0
    power_checks(r)
