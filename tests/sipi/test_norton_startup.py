# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Current-source startup: independent LC, modal, KCL and source-power contracts."""
import importlib.metadata as metadata
import json

import numpy as np
import pytest
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import coupled_norton_reactive_ladder_response, coupled_reactive_ladder_response
import sipi.coupled_boundary_startup as engine

R=np.array([[20.,3.],[3.,20.]])
L=np.array([[500.,100.],[100.,500.]])*1e-9
G=np.array([[.002,-.0003],[-.0003,.002]])
C=np.array([[220.,-40.],[-40.,220.]])*1e-12
CL=np.array([[30.,-5.],[-5.,30.]])*1e-12
RB=np.array([[10.,2.],[2.,10.]])
LB=RB*1e-9
Q=np.array([[1.,1.],[1.,-1.]])/np.sqrt(2)


def arguments(**changes):
    kw=dict(R=R,L=L,G=G,C=C,length=.1,cells=16,source_shunt_resistance=[None,37.],load_resistance=[91.,None],
            load_capacitance=CL,load_branch_resistance=RB,load_branch_inductance=LB)
    kw.update(changes);return kw


def run(time=None,drive=None,**changes):
    time=np.linspace(0,12e-9,121) if time is None else time
    drive=np.column_stack((.02*np.minimum(np.asarray(time)/2e-9,1.),-.01*np.minimum(np.asarray(time)/3e-9,1.))) if drive is None else drive
    return coupled_norton_reactive_ladder_response(time,drive,**arguments(**changes))


def power_checks(r):
    for name in ['energy','load_capacitor_energy','load_branch_energy','series_loss','shunt_loss','source_shunt_resistor_loss','load_resistor_loss','load_branch_resistor_loss']:
        assert np.min(getattr(r,name))>=0
    assert r.power_balance_relative_error<=1e-10 and r.total_power_balance_relative_error<=1e-10
    np.testing.assert_allclose(r.energy_rate,r.line_power-r.series_loss-r.shunt_loss,rtol=1e-10,atol=1e-14)
    np.testing.assert_allclose(r.total_energy_rate,r.source_power-r.source_shunt_resistor_loss-r.load_resistor_loss-r.series_loss-r.shunt_loss-r.load_branch_resistor_loss,rtol=1e-10,atol=1e-14)
    np.testing.assert_allclose(r.source_power,np.sum(r.source_currents*r.voltage[:,:2],axis=1),rtol=1e-10,atol=1e-14)
    np.testing.assert_allclose(np.sum(r.voltage[:,2:]*r.load_branch_current,axis=1),r.load_branch_energy_rate+r.load_branch_resistor_loss,rtol=1e-10,atol=1e-14)


def circuit(t,drive,n,r=R,l=L,g=G,c=C,source=(25.,25.),load=(100.,100.),load_capacitance=CL,length=.1,branch_r=RB,branch_l=LB):
    result=run(t,drive,cells=n,R=r,L=l,G=g,C=c,source_shunt_resistance=source,load_resistance=load,
        load_capacitance=load_capacitance,length=length,load_branch_resistance=branch_r,load_branch_inductance=branch_l)
    power_checks(result)
    return dict(v=result.voltage,i=result.current,energy=result.energy,capenergy=result.load_capacitor_energy,
        branch_current=result.load_branch_current,branch_energy=result.load_branch_energy,
        power_error=result.power_balance_relative_error,total_power_error=result.total_power_balance_relative_error)


def reference_record(case,tool,error,limit,clock,details):
    record=make_record(case=case,physics='Norton-driven passive two-signal line with parallel C and series RL load',
        api='sipi.coupled_norton_reactive_ladder_response',discretization='explicit fullmatrix finite RLGC cells and external RL current states',
        tool=tool,tool_discretization=details,matched=['constant line/load matrices,zero state,explicit current drive and near shunt resistance'],
        not_matched=['finite spatial/PWL/zero-state transient versus continuous steady phasor when applicable'],
        observables=[observable('response error','V','maximum voltage difference',error,limit)],
        analytical_acceptance='exact current-driven one-cell LC and separate source/line/external energy balance',stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)


def test_finite_shunt_thevenin_equivalence_of_line_and_load_states():
 t=np.linspace(0,12e-9,121);drive=np.column_stack((.02*np.minimum(t/2e-9,1.),-.01*np.minimum(t/3e-9,1.)))
 rb=np.array([[13.,1.],[1.,9.]]);lb=np.array([[12.,2.],[2.,8.]])*1e-9;cl=np.array([[20.,-4.],[-4.,30.]])*1e-12
 actual=circuit(t,drive,16,source=[25.,37.],load=[91.,None],load_capacitance=cl,branch_r=rb,branch_l=lb)
 old=coupled_reactive_ladder_response(t,drive*np.array([25.,37.]),R=R,L=L,G=G,C=C,length=.1,cells=16,source_resistance=[25.,37.],load_resistance=[91.,None],load_capacitance=cl,load_branch_resistance=rb,load_branch_inductance=lb)
 ev=float(np.max(abs(actual['v']-old.voltage)));ei=float(np.max(abs(actual['i']-old.current)))
 assert ev<=1e-10 and ei<=1e-12
 for a,b in [(actual['energy'],old.energy),(actual['capenergy'],old.load_capacitor_energy),(actual['branch_energy'],old.load_branch_energy)]:np.testing.assert_allclose(a,b,rtol=1e-10,atol=1e-20)


def test_independent_one_cell_current_driven_lc_ramp_hold():
 t=np.linspace(0,4,401);amp=np.array([1.,-.4]);drive=np.minimum(t,1.)[:,None]*amp;ct=.2;w=np.sqrt(1/ct)
 actual=circuit(t,drive,1,r=np.zeros((2,2)),l=np.eye(2),g=np.zeros((2,2)),c=.4*np.eye(2),source=[None,None],load=[0.,0.],load_capacitance=np.zeros((2,2)),length=1.,branch_r=np.eye(2),branch_l=np.eye(2))
 before=(t-np.sin(w*t)/w)[:,None]*amp;dbefore=(1-np.cos(w*t))[:,None]*amp
 aa=-amp*np.sin(w)/w;bb=amp*(1-np.cos(w))/w;shift=t-1
 after=amp+np.cos(w*shift)[:,None]*aa+np.sin(w*shift)[:,None]*bb
 dafter=-w*np.sin(w*shift)[:,None]*aa+w*np.cos(w*shift)[:,None]*bb
 iline=np.where((t<=1)[:,None],before,after);vnear=np.where((t<=1)[:,None],dbefore,dafter)
 expectedv=np.column_stack((vnear,np.zeros_like(vnear)));expectedi=np.column_stack((drive,-iline))
 expectedenergy=.5*np.sum(iline**2,axis=1)+.1*np.sum(vnear**2,axis=1)
 for a,b in [(actual['v'],expectedv),(actual['i'],expectedi),(actual['energy'],expectedenergy)]:np.testing.assert_allclose(a,b,rtol=1e-10,atol=1e-12)
 assert np.all(actual['branch_current']==0) and np.all(actual['capenergy']==0)


def test_independent_finite_source_modal_refinement():
 skrf=require_tool("scikit-rf");clock=Stopwatch()
 f=500e6;w=2*np.pi*f;t=np.arange(20*256+1)/(f*256);drive=np.column_stack((.02*np.sin(w*t),np.zeros(len(t))));capload=np.array([[30.,-5.],[-5.,30.]])*1e-12;rb=np.array([[10.,2.],[2.,10.]]);lb=rb*1e-9;comparisons=[]
 for rs in [50.]:
  with clock("reference"):
   modal=[]
   for m in range(2):
    rm,lm,gm,cm=[(Q.T@a@Q)[m,m] for a in [R,L,G,C]];clm,rbm,lbm=[(Q.T@a@Q)[m,m] for a in [capload,rb,lb]]
    gamma=np.sqrt((rm+1j*w*lm)*(gm+1j*w*cm));zc=np.sqrt((rm+1j*w*lm)/(gm+1j*w*cm));yl=1/100+1j*w*clm+1/(rbm+1j*w*lbm)
    media=skrf.media.DefinedGammaZ0(frequency=skrf.Frequency.from_f([f],unit='hz'),z0_port=50.,z0=zc,gamma=gamma)
    a,b,c,d=media.line(.1,unit='m').a[0].ravel();denominator=c+d*yl+(0. if rs is None else (a+b*yl)/rs)
    vl=.02*Q[0,m]/denominator;modal.append(np.array([(a+b*yl)*vl,vl]))
  expected=(np.stack(modal,axis=-1)@Q.T).ravel();last=slice(-4*256-1,-1);phase=np.exp(-1j*w*t[last]);rows=[]
  for n in [32,64,128]:
   with clock("openphysics"):result=circuit(t,drive,n,source=[rs,rs],load_capacitance=capload,branch_r=rb,branch_l=lb)
   phasor=2/len(phase)*(phase@result['v'][last])/(-1j)
   rows.append(dict(cells=n,voltage_error=float(np.max(abs(phasor-expected))),power_error=result['power_error'],total_power_error=result['total_power_error']))
  comparisons.append(dict(source_shunt_resistance=rs,rows=rows));print('phasor',comparisons[-1],flush=True)
  assert rows[-1]['voltage_error']<=.001 and rows[2]['voltage_error']<rows[1]['voltage_error']<rows[0]['voltage_error']
 reference_record("sipi-norton-startup-finite-modal","scikit-rf",rows[-1]["voltage_error"],.001,clock,"continuous modal ABCD,Norton50ohm near shunt,500MHz20cycles/256samples/final4")


def test_independent_ideal_source_horizon_and_spatial_refinement():
 skrf=require_tool("scikit-rf");clock=Stopwatch()
 with clock("reference"):
  f=500e6;w=2*np.pi*f;capload=np.array([[30.,-5.],[-5.,30.]])*1e-12;rb=np.array([[10.,2.],[2.,10.]]);lb=rb*1e-9;modal=[]
  for m in range(2):
   rm,lm,gm,cm=[(Q.T@a@Q)[m,m] for a in [R,L,G,C]];clm,rbm,lbm=[(Q.T@a@Q)[m,m] for a in [capload,rb,lb]]
   gamma=np.sqrt((rm+1j*w*lm)*(gm+1j*w*cm));zc=np.sqrt((rm+1j*w*lm)/(gm+1j*w*cm));yl=1/100+1j*w*clm+1/(rbm+1j*w*lbm)
   media=skrf.media.DefinedGammaZ0(frequency=skrf.Frequency.from_f([f],unit='hz'),z0_port=50.,z0=zc,gamma=gamma)
   a,b,c,d=media.line(.1,unit='m').a[0].ravel();vl=.02*Q[0,m]/(c+d*yl);modal.append(np.array([(a+b*yl)*vl,vl]))
  expected=(np.stack(modal,axis=-1)@Q.T).ravel()
  finite=[]
  for n in [32,64,128]:
   cols=[];dx=.1/n
   for m in range(2):
    rm,lm,gm,cm=[(Q.T@a@Q)[m,m] for a in [R,L,G,C]];clm,rbm,lbm=[(Q.T@a@Q)[m,m] for a in [capload,rb,lb]]
    yy=(gm+1j*w*cm)*dx/2;zz=(rm+1j*w*lm)*dx
    half=np.array([[1.,0.],[yy,1.]],complex);series=np.array([[1.,zz],[0.,1.]],complex)
    chain=np.linalg.matrix_power(half@series@half,n);aa,bb,cc,dd=chain.ravel()
    yl=1/100+1j*w*clm+1/(rbm+1j*w*lbm);vl=.02*Q[0,m]/(cc+dd*yl);cols.append(np.array([(aa+bb*yl)*vl,vl]))
   value=(np.stack(cols,axis=-1)@Q.T).ravel();finite.append(dict(cells=n,voltage_error=float(np.max(abs(value-expected)))))
  print('pi frequency',finite,flush=True)
  assert finite[-1]['voltage_error']<=.001 and finite[2]['voltage_error']<finite[1]['voltage_error']<finite[0]['voltage_error']
 def evaluate(cycles,n):
  t=np.arange(cycles*128+1)/(f*128);drive=np.column_stack((.02*np.sin(w*t),np.zeros(len(t))));last=slice(-4*128-1,-1);phase=np.exp(-1j*w*t[last])
  with clock("openphysics"):result=circuit(t,drive,n,source=[None,None],load_capacitance=capload,branch_r=rb,branch_l=lb)
  phasor=2/len(phase)*(phase@result['v'][last])/(-1j)
  return dict(cycles=cycles,samples=len(t),cells=n,voltage_error=float(np.max(abs(phasor-expected))),power_error=result['power_error'],total_power_error=result['total_power_error'])
 rows=[evaluate(cycles,128) for cycles in [20,40,64]];print('horizon',rows,flush=True)
 assert rows[-1]['voltage_error']<=.001 and rows[2]['voltage_error']<rows[1]['voltage_error']<rows[0]['voltage_error']
 mesh=[evaluate(64,n) for n in [32,64]]+[rows[-1]];print('spatial',mesh,flush=True)
 assert mesh[-1]['voltage_error']<=.001 and mesh[2]['voltage_error']<mesh[1]['voltage_error']<mesh[0]['voltage_error']
 reference_record("sipi-norton-startup-ideal-modal","scikit-rf",mesh[-1]["voltage_error"],.001,clock,"continuous modal ABCD plus separate pi-cell frequency product,500MHz20/40/64cycles/128samples/final4")


def test_independent_asymmetric_current_driven_kcl():
 require_tool("scipy");from scipy.integrate import solve_ivp
 clock=Stopwatch()
 n=16;dx=.1/n;nv=2*(n+1);base_size=4*n+2;r=np.array([[25.,2.],[2.,17.]]);l=np.array([[510.,70.],[70.,430.]])*1e-9
 g=np.array([[.003,-.0002],[-.0002,.0015]]);c=np.array([[230.,-30.],[-30.,190.]])*1e-12;capload=np.array([[20.,-4.],[-4.,30.]])*1e-12
 rb=np.array([[13.,1.],[1.,9.]]);lb=np.array([[12.,2.],[2.,8.]])*1e-9
 u=np.linspace(0,12,241)
 def drive_u(t):return np.array([np.interp(t,[0,2],[0,.02]),np.interp(t,[0,3],[0,-.01])])
 def dynamics(t,x,all_states=False):
  v=x[:nv].reshape(n+1,2);i=x[nv:base_size].reshape(n,2);ib=x[-2:];dv=np.zeros_like(v)
  flow=np.zeros_like(v);flow[:-1]-=i;flow[1:]+=i;flow[-1]-=ib;flow[0]+=drive_u(t)
  flow[0,1]-=v[0,1]/37.;flow[-1,0]-=v[-1,0]/91.
  dv[1:-1]=np.linalg.solve(c,(flow[1:-1]/dx-v[1:-1]@g.T).T).T
  dv[0]=np.linalg.solve(c*dx*.5,flow[0]-g@v[0]*dx*.5)
  dv[-1]=np.linalg.solve(c*dx*.5+capload,flow[-1]-g@v[-1]*dx*.5)
  di=np.linalg.solve(l,((v[:-1]-v[1:])/dx-i@r.T).T).T;dib=np.linalg.solve(lb,v[-1]-rb@ib);deriv=np.r_[dv.ravel(),di.ravel(),dib]
  return deriv if all_states else 1e-9*deriv
 ce,cu=np.linalg.eigh(c);cs=(cu*np.sqrt(ce))@cu.T;min_tau=float(.1*np.sqrt(np.linalg.eigvalsh(cs@l@cs)[0])/1e-9)
 with clock('reference'):ref=solve_ivp(dynamics,[0,12],np.zeros(base_size+2),method='DOP853',t_eval=u,rtol=1e-10,atol=1e-12,max_step=min_tau/(5*n))
 assert ref.success
 with clock('openphysics'):actual=circuit(u*1e-9,np.array([drive_u(t) for t in u]),n,r,l,g,c,[None,37.],[91.,None],load_capacitance=capload,branch_r=rb,branch_l=lb)
 full=ref.y.T;deriv=np.array([dynamics(t,x,True) for t,x in zip(u,full)])
 v=full[:,:nv].reshape(len(u),n+1,2);ii=full[:,nv:base_size].reshape(len(u),n,2);ib=full[:,-2:];dv=deriv[:,:nv].reshape(v.shape)
 expectedv=v[:,[0,n],:].reshape(len(u),4);expectedi=np.zeros_like(expectedv)
 expectedi[:,:2]=np.array([drive_u(t) for t in u]);expectedi[:,1]-=v[:,0,1]/37.
 expectedi[:,2:]=-dv[:,-1]@capload.T-ib;expectedi[:,2]-=v[:,-1,0]/91.
 ev=float(np.max(abs(actual['v']-expectedv)));ei=float(np.max(abs(actual['i']-expectedi)));eb=float(np.max(abs(actual['branch_current']-ib)))
 print('Norton asymmetric errors',ev,ei,eb)
 assert ev<=1e-8 and max(ei,eb)<=1e-9
 reference_record("sipi-norton-startup-kcl","scipy",ev,1e-8,clock,"independent per-node current KCL and RL voltage ODE,DOP853 rtol1e-10/atol1e-12")


@pytest.mark.parametrize('shunt,load',[
    ([None,None],[91.,113.]),([0.,None],[None,0.]),([37.,0.],[0.,None]),
    ([0.,0.],[None,None]),([25.,37.],[0.,0.]),
])
def test_near_open_short_finite_shunts_preserve_current_and_power_conventions(shunt,load):
    r=run(source_shunt_resistance=shunt,load_resistance=load);power_checks(r)
    for j in range(2):
        if shunt[j]==0:assert np.all(r.voltage[:,j]==0)
        elif shunt[j] is None:np.testing.assert_array_equal(r.current[:,j],r.source_currents[:,j])
        else:np.testing.assert_allclose(r.current[:,j],r.source_currents[:,j]-r.voltage[:,j]/shunt[j],rtol=1e-12,atol=1e-14)
        if load[j]==0:assert np.all(r.voltage[:,2+j]==0)
    if shunt==[0.,0.]:
        assert np.all(r.total_energy==0) and np.all(r.current==0) and np.all(r.source_power==0)
    expected=sum(0 if value is None or value==0 else r.voltage[:,j]**2/value for j,value in enumerate(shunt))
    np.testing.assert_allclose(r.source_shunt_resistor_loss,expected,rtol=1e-12,atol=1e-14)


def test_thevenin_equivalence_does_not_confuse_source_power_partition():
    r=run(source_shunt_resistance=[25.,37.]);kw=arguments();kw.pop('source_shunt_resistance')
    old=coupled_reactive_ladder_response(r.time,r.source_currents*np.array([25.,37.]),**kw,source_resistance=[25.,37.])
    assert np.max(abs(r.source_power-old.source_power))>1e-4
    assert np.max(abs(r.source_shunt_resistor_loss-old.source_resistor_loss))>1e-4
    np.testing.assert_allclose(r.source_power-r.source_shunt_resistor_loss,old.source_power-old.source_resistor_loss,rtol=1e-10,atol=1e-14)
    assert not hasattr(r,'source_voltages') and not hasattr(r,'source_resistor_loss')
    assert 'source_currents_a' in r.inputs and 'source_voltages_v' not in r.inputs


def test_dc_limit_ideal_and_finite_current_source():
    t=np.arange(5001)*.2e-9;drive=np.minimum(t/2e-9,1.)[:,None]*np.array([.02,-.01]);rs=[None,37.];rl=[91.,113.]
    r=run(t,drive,G=np.zeros((2,2)),source_shunt_resistance=rs,load_resistance=rl,cells=8);power_checks(r)
    yload=np.diag(1/np.asarray(rl))+np.linalg.inv(RB);near_map=np.eye(2)+R*.1@yload
    vfar=np.linalg.solve(yload+np.diag([0.,1/37.])@near_map,drive[-1]);vnear=near_map@vfar;iline=yload@vfar
    errors=[]
    for ns in [600,800,1000]:
        stop=ns*5+1;window=slice(stop-101,stop)
        vp=np.tile(np.r_[vnear,vfar],(101,1));ip=np.tile(iline,(101,8,1));bp=np.tile(np.linalg.solve(RB,vfar),(101,1))
        errors.append((np.max(abs(r.voltage[window]-vp)),max(np.max(abs(r.segment_current[window]-ip)),np.max(abs(r.load_branch_current[window]-bp)))))
        if ns>=800:
            np.testing.assert_allclose(r.voltage[window],vp,rtol=1e-10,atol=1e-12)
            np.testing.assert_allclose(r.segment_current[window],ip,rtol=1e-10,atol=1e-12)
            np.testing.assert_allclose(r.load_branch_current[window],bp,rtol=1e-10,atol=1e-12)
    for component in range(2):assert errors[2][component]<errors[1][component]<errors[0][component]


def test_zero_input_and_rank_one_passive_branch():
    r=run(drive=np.zeros((121,2)),load_branch_resistance=[[1.,-1.],[-1.,1.]]);power_checks(r)
    assert np.all(r.total_energy==0) and np.all(r.voltage==0)
    r=run(load_branch_resistance=[[1.,-1.],[-1.,1.]]);power_checks(r)


def test_time_impedance_permutation_and_superposition():
    r=run(source_shunt_resistance=[None,None],load_resistance=[100.,100.]);power_checks(r)
    timed=run(r.time*3,r.source_currents,L=L*3,C=C*3,load_capacitance=CL*3,load_branch_inductance=LB*3,source_shunt_resistance=[None,None],load_resistance=[100.,100.])
    z=run(r.time,r.source_currents/2,R=R*2,L=L*2,G=G/2,C=C/2,source_shunt_resistance=[None,None],load_resistance=[200.,200.],load_capacitance=CL/2,load_branch_resistance=RB*2,load_branch_inductance=LB*2)
    np.testing.assert_allclose(timed.voltage,r.voltage,rtol=1e-9,atol=1e-12)
    np.testing.assert_allclose(timed.total_energy,r.total_energy*3,rtol=1e-9,atol=1e-20)
    np.testing.assert_allclose(z.voltage,r.voltage,rtol=1e-9,atol=1e-12)
    np.testing.assert_allclose(z.current,r.current/2,rtol=1e-9,atol=1e-12)
    swapped=run(r.time,r.source_currents[:,::-1],source_shunt_resistance=[None,None],load_resistance=[100.,100.])
    np.testing.assert_allclose(swapped.node_voltage,r.node_voltage[:,:,::-1],rtol=1e-9,atol=1e-12)
    a=run(r.time,r.source_currents*.4);b=run(r.time,r.source_currents*-.7);combined=run(r.time,r.source_currents*-.3)
    np.testing.assert_allclose(combined.voltage,a.voltage+b.voltage,rtol=1e-9,atol=1e-12)
    for x in [timed,z,swapped,a,b,combined]:power_checks(x)


def test_copied_current_inputs_readonly_output_and_finite_json():
    t=np.linspace(0,12e-9,121);drive=np.column_stack((.02*np.minimum(t/2e-9,1.),np.zeros(len(t))))
    shunt=[None,37.];r=run(t,drive,source_shunt_resistance=shunt);text=json.dumps(r.to_dict(include_states=True),sort_keys=True,allow_nan=False)
    t[:]=9;drive[:]=9;shunt[0]=99
    for name in ['source_currents','time','voltage','current','source_shunt_resistor_loss','load_branch_current','total_energy']:
        assert not getattr(r,name).flags.writeable
    d=r.inputs;d['source_currents_a'][0][0]=99
    assert json.dumps(r.to_dict(include_states=True),sort_keys=True,allow_nan=False)==text
    assert r.to_dict()['scope']=='finite-passive-two-signal-norton-reactive-startup'
    assert not r.to_dict()['states_included'] and r.to_dict(include_states=True)['states_included']
    with pytest.raises(ValueError):r.to_dict(include_states=1)


@pytest.mark.parametrize('shunt',[None,50.,[50.],[[50.,50.]],[-1.,None],[True,37.],[np.inf,None],[50.+0j,None]])
def test_invalid_source_shunt_rejects_before_propagation(shunt,monkeypatch):
    def forbidden(*a,**k):pytest.fail('invalid source reached propagation')
    monkeypatch.setattr(engine,'lsim',forbidden)
    with pytest.raises((ValueError,TypeError)):run(source_shunt_resistance=shunt)


@pytest.mark.parametrize('drive',[np.ones((121,2)),np.zeros(121),np.zeros((121,3)),np.full((121,2),np.nan),np.zeros((121,2),bool)])
def test_invalid_current_drive_rejects_with_current_label(drive,monkeypatch):
    def forbidden(*a,**k):pytest.fail('invalid drive reached propagation')
    monkeypatch.setattr(engine,'lsim',forbidden)
    with pytest.raises(ValueError,match='source_currents'):run(drive=drive)


def test_original_load_passivity_and_runtime_scale_guards():
    with pytest.raises(ValueError):run(load_branch_inductance=np.zeros((2,2)))
    with pytest.raises(ValueError):run(load_capacitance=[[1.,0.],[0.,-1e-30]])
    with pytest.raises(ValueError,match='finite scales'):run(load_branch_inductance=np.eye(2)*5e-324)
    with pytest.raises(ValueError):run(cells=True)


def test_lossless_zero_current_after_pulse_preserves_total_energy():
    t=np.linspace(0,12e-9,1201);drive=np.column_stack((.02*np.interp(t,[0,2e-9,4e-9,6e-9],[0,1,1,0]),np.zeros(len(t))))
    r=run(t,drive,R=np.zeros((2,2)),G=np.zeros((2,2)),load_branch_resistance=np.zeros((2,2)),
        source_shunt_resistance=[None,None],load_resistance=[None,None]);power_checks(r)
    after=t>=6.1e-9;energy=r.total_energy[after]
    assert np.min(energy)>0 and np.ptp(r.load_branch_energy[after])>1e-14
    np.testing.assert_allclose(energy,np.full_like(energy,energy[0]),rtol=1e-10,atol=1e-20)
    assert np.all(r.source_power[after]==0) and np.all(r.source_shunt_resistor_loss==0)
