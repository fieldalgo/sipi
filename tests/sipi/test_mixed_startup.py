# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Typed mixed-source startup: independent LC/KCL/ABCD and source power contracts."""
import json
import importlib.metadata as metadata
import numpy as np
import pytest
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import (coupled_mixed_source_ladder_response, coupled_reactive_ladder_response,
                  coupled_norton_reactive_ladder_response)
R=np.array([[20.,3.],[3.,20.]])
L=np.array([[500.,100.],[100.,500.]])*1e-9
G=np.array([[.002,-.0003],[-.0003,.002]])
C=np.array([[220.,-40.],[-40.,220.]])*1e-12
Q=np.array([[1.,1.],[1.,-1.]])/np.sqrt(2)


def sources(drive,resistance,kinds):
    return [dict(kind=kind,**{('voltage_v' if kind=='voltage' else 'current_a'):drive[:,j],
         ('series_resistance_ohm' if kind=='voltage' else 'shunt_resistance_ohm'):resistance[j]}) for j,kind in enumerate(kinds)]


def circuit(clock,t,drive,n,r=R,l=L,g=G,c=C,source=(25.,25.),load=(100.,100.),load_capacitance=None,length=.1,branch_r=None,branch_l=None,kinds=('voltage','current')):
    with clock('openphysics'):
        a=coupled_mixed_source_ladder_response(t,sources(drive,source,kinds),R=r,L=l,G=g,C=c,length=length,cells=n,
            load_resistance=load,load_capacitance=load_capacitance,load_branch_resistance=branch_r,load_branch_inductance=branch_l)
    return dict(v=a.voltage,i=a.current,energy=a.energy,branch_current=a.load_branch_current,
        source_power=a.source_power,source_series=a.source_series_resistor_loss,source_shunt=a.source_shunt_resistor_loss,
        power_error=a.power_balance_relative_error,total_power_error=a.total_power_balance_relative_error)


def reference_record(case,tool,voltage,current,branch,clock,details):
    obs=[observable('terminal voltage','V','maximum absolute error',voltage,.001 if tool=='scikit-rf' else 1e-8)]
    if current is not None:obs.extend([observable('terminal current','A','maximum absolute error',current,1e-9),observable('branch current','A','maximum absolute error',branch,1e-9)])
    record=make_record(case=case,physics='mixed voltage/current passive line with external C and series RL',
        api='sipi.coupled_mixed_source_ladder_response',discretization='finite pi cells,transformed mass state,PWL exact state propagation',
        tool=tool,tool_discretization=details,matched=['same explicit line,source kinds/units,resistive and reactive boundaries'],
        not_matched=['finite circuit versus continuous line for frequency comparison; no measured board claim'],
        observables=obs,analytical_acceptance='one-cell mixed L/LC,source power separation,line and combined energy',stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)


def test_finite_mixed_source_equivalence_and_power_partition():
 clock=Stopwatch();report={}
 t=np.linspace(0,12e-9,121);drive=np.column_stack((np.minimum(t/2e-9,1.),-.01*np.minimum(t/3e-9,1.)))
 rb=np.array([[13.,1.],[1.,9.]]);lb=np.array([[12.,2.],[2.,8.]])*1e-9;cl=np.array([[20.,-4.],[-4.,30.]])*1e-12
 a=circuit(clock,t,drive,16,source=[25.,37.],load=[91.,None],load_capacitance=cl,branch_r=rb,branch_l=lb)
 ref=coupled_reactive_ladder_response(t,drive*np.array([1.,37.]),R=R,L=L,G=G,C=C,length=.1,cells=16,source_resistance=[25.,37.],load_resistance=[91.,None],load_capacitance=cl,load_branch_resistance=rb,load_branch_inductance=lb)
 ev=float(np.max(abs(a['v']-ref.voltage)));ei=float(np.max(abs(a['i']-ref.current)));assert ev<=1e-10 and ei<=1e-12
 supplied=drive[:,0]*a['i'][:,0]+drive[:,1]*a['v'][:,1];series=25*a['i'][:,0]**2;shunt=a['v'][:,1]**2/37
 for actual,expected in [(a['source_power'],supplied),(a['source_series'],series),(a['source_shunt'],shunt)]:np.testing.assert_allclose(actual,expected,rtol=1e-10,atol=1e-12)
 report['finite_equivalence']=dict(voltage_error=ev,current_error=ei);print('equivalence',report['finite_equivalence'],flush=True)


def test_independent_decoupled_mixed_l_lc_ramp_hold():
 clock=Stopwatch();report={}
 # Independent decoupled ideal voltage/ideal current one-cell ramp/hold.
 t=np.linspace(0.,2.,1001);tau=.8;drive=np.minimum(t,tau)[:,None]*[.7,.3];w=np.sqrt(2.)
 a=circuit(clock,t,drive,1,r=np.zeros((2,2)),l=np.eye(2),g=np.zeros((2,2)),c=np.eye(2),length=1.,source=[0.,None],load=[0.,0.],load_capacitance=np.zeros((2,2)),branch_r=np.zeros((2,2)),branch_l=np.eye(2))
 shift=np.maximum(t-tau,0);iv=.35*(t**2-shift**2);ic=.3*(t-np.sin(w*t)/w-shift+np.sin(w*shift)/w)
 vc=.3*(1-np.cos(w*t)-(1-np.cos(w*shift)));dv=np.where(t<tau,.7,0.)
 v=np.column_stack((drive[:,0],vc,np.zeros((len(t),2))));i=np.column_stack((iv+.5*dv,drive[:,1],-iv,-ic))
 energy=.5*(iv**2+ic**2)+.25*(drive[:,0]**2+vc**2)
 for actual,expected in [(a['v'],v),(a['i'],i),(a['energy'],energy)]:np.testing.assert_allclose(actual,expected,rtol=1e-10,atol=1e-12)
 report['analytic_mixed_lc']=dict(voltage_error=float(np.max(abs(a['v']-v))),current_error=float(np.max(abs(a['i']-i))),power_error=a['power_error'],total_power_error=a['total_power_error']);print('analytic',report['analytic_mixed_lc'],flush=True)


def test_independent_asymmetric_direct_kcl_with_ideal_and_finite_mixed_sources():
 clock=Stopwatch();report={}
 require_tool("scipy");from scipy.integrate import solve_ivp
 rb=np.array([[13.,1.],[1.,9.]]);lb=np.array([[12.,2.],[2.,8.]])*1e-9
 # Direct node KCL reference: no assembled candidate matrices or transforms.
 r=np.array([[25.,2.],[2.,17.]]);l=np.array([[510.,70.],[70.,430.]])*1e-9;g=np.array([[.003,-.0002],[-.0002,.0015]]);c=np.array([[230.,-30.],[-30.,190.]])*1e-12
 n=16;dx=.1/n;nv=2*(n+1);u=np.linspace(0,12,241);cl=np.array([[20.,-4.],[-4.,30.]])*1e-12
 def drive_u(x,kinds):return np.array([(1. if kind=='voltage' else .02)*np.minimum(x/(2+j),1.)*(-.4 if j else 1.) for j,kind in enumerate(kinds)])
 def slope_u(x,kinds):return np.array([(1. if kind=='voltage' else .02)/(2+j)*1e9*(-.4 if j else 1.) if x<2+j else 0. for j,kind in enumerate(kinds)])
 comparisons=[]
 for kinds,rs,rl in [(('voltage','current'),[0.,None],[91.,None]),(('current','voltage'),[None,0.],[None,0.]),(('voltage','current'),[25.,37.],[91.,113.])]:
  fixed={}
  for j in range(2):
   if rs[j]==0:fixed[j]=j if kinds[j]=='voltage' else None
   if rl[j]==0:fixed[2*n+j]=None
  free=np.array([j for j in range(nv) if j not in fixed]);nf=len(free)
  def full(x,y):
   v=np.zeros(nv);v[free]=y[:nf];d=drive_u(x,kinds)
   for index,port in fixed.items():v[index]=0. if port is None else d[port]
   return v.reshape(n+1,2),y[nf:nf+2*n].reshape(n,2),y[-2:]
  def dynamics(x,y,all_values=False):
   v,i,ib=full(x,y);dv=np.zeros_like(v);ds=slope_u(x,kinds);d=drive_u(x,kinds)
   flow=np.zeros_like(v);flow[:-1]-=i;flow[1:]+=i;flow[-1]-=ib
   for j in range(2):
    if rs[j]!=0:flow[0,j]+=(d[j]-v[0,j])/rs[j] if kinds[j]=='voltage' else d[j]-(0. if rs[j] is None else v[0,j]/rs[j])
    if rl[j] is not None and rl[j]>0:flow[-1,j]-=v[-1,j]/rl[j]
   for node in range(n+1):
    wt=.5 if node in [0,n] else 1.;cap=c*dx*wt+(cl if node==n else 0.);rhs=flow[node]-g@v[node]*dx*wt
    f=[j for j in range(2) if 2*node+j not in fixed];pres=[j for j in range(2) if j not in f]
    for j in pres:
     port=fixed[2*node+j];dv[node,j]=0. if port is None else ds[port]
    if f:dv[node,f]=np.linalg.solve(cap[np.ix_(f,f)],rhs[f]-cap[np.ix_(f,pres)]@dv[node,pres])
   di=np.linalg.solve(l,((v[:-1]-v[1:])/dx-i@r.T).T).T;dib=np.linalg.solve(lb,v[-1]-rb@ib)
   if all_values:return v,i,ib,dv,di,dib
   return 1e-9*np.r_[dv.ravel()[free],di.ravel(),dib]
  # End each integration at the PWL knots; independent RHS uses explicit slopes.
  y=np.zeros(nf+2*n+2);samples=np.zeros((len(u),len(y)))
  for left,right in [(0.,2.),(2.,3.),(3.,12.)]:
   ids=np.flatnonzero((u>left)&(u<=right));times=u[ids]
   with clock('reference'):sol=solve_ivp(dynamics,[left,right],y,method='DOP853',t_eval=times,rtol=1e-11,atol=1e-13,max_step=.005)
   assert sol.success
   samples[ids]=sol.y.T;y=sol.y[:,-1]
  states=[dynamics(x,y,True) for x,y in zip(u,samples)];v=np.array([z[0] for z in states]);ii=np.array([z[1] for z in states]);ib=np.array([z[2] for z in states]);dv=np.array([z[3] for z in states])
  near=(dv[:,0]@c.T+v[:,0]@g.T)*dx*.5+ii[:,0];far=(dv[:,-1]@c.T+v[:,-1]@g.T)*dx*.5-ii[:,-1]
  evv=v[:,[0,n],:].reshape(len(u),4);eii=np.concatenate((near,far),axis=1)
  a=circuit(clock,u*1e-9,np.array([drive_u(x,kinds) for x in u]),n,r,l,g,c,rs,rl,load_capacitance=cl,branch_r=rb,branch_l=lb,kinds=kinds)
  ev=float(np.max(abs(a['v']-evv)));ei=float(np.max(abs(a['i']-eii)));eb=float(np.max(abs(a['branch_current']-ib)))
  row=dict(kinds=kinds,source=rs,load=rl,voltage_error=ev,current_error=ei,branch_current_error=eb,power_error=a['power_error'],total_power_error=a['total_power_error']);comparisons.append(row);report['asymmetric_kcl']=comparisons;print('kcl',row,flush=True)
  assert ev<=1e-8 and max(ei,eb)<=1e-9
 reference_record("sipi-mixed-startup-kcl","scipy",max(x["voltage_error"] for x in comparisons),max(x["current_error"] for x in comparisons),max(x["branch_current_error"] for x in comparisons),clock,"independent per-node KCL DOP853,ideal V/I permutations and finite mixed,explicit PWL knot intervals")


def test_independent_continuous_mixed_source_spatial_refinement():
 clock=Stopwatch();report={}
 skrf=require_tool("scikit-rf")
 # Continuous coupled admittance from independent scikit-rf modal ABCD.
 f=500e6;w=2*np.pi*f;t=np.arange(20*256+1)/(f*256);amp=np.array([1.,-.008]);drive=np.sin(w*t)[:,None]*amp
 cl=np.array([[30.,-5.],[-5.,30.]])*1e-12;rb=np.array([[10.,2.],[2.,10.]]);lb=rb*1e-9
 with clock('reference'):
  yn=np.zeros((4,4),dtype=complex)
  for m in range(2):
   rm,lm,gm,cm=[(Q.T@a@Q)[m,m] for a in [R,L,G,C]]
   gamma=np.sqrt((rm+1j*w*lm)*(gm+1j*w*cm));zc=np.sqrt((rm+1j*w*lm)/(gm+1j*w*cm))
   media=skrf.media.DefinedGammaZ0(frequency=skrf.Frequency.from_f([f],unit='hz'),z0_port=50.,z0=zc,gamma=gamma)
   aa,bb,cc,dd=media.line(.1,unit='m').a[0].ravel();block=np.array([[dd,-1],[-1,aa]])/bb
   for j in range(2):
    for k in range(2):yn[2*j:2*j+2,2*k:2*k+2]+=block[j,k]*np.outer(Q[:,m],Q[:,m])
  yload=np.eye(2)/100+1j*w*cl+np.linalg.inv(rb+1j*w*lb)
  system=yn.copy();system[:2,:2]+=np.diag([1/25,1/37]);system[2:,2:]+=yload
  expected=np.linalg.solve(system,np.r_[amp[0]/25,amp[1],0.,0.]);last=slice(-4*256-1,-1);phase=np.exp(-1j*w*t[last]);rows=[]
 for n in [32,64,128]:
  a=circuit(clock,t,drive,n,source=[25.,37.],load=[100.,100.],load_capacitance=cl,branch_r=rb,branch_l=lb)
  phasor=2/len(phase)*(phase@a['v'][last])/(-1j);err=float(np.max(abs(phasor-expected)))
  rows.append(dict(cells=n,voltage_error=err,power_error=a['power_error'],total_power_error=a['total_power_error']));report['continuous_phasor']=rows;print('phasor',rows[-1],flush=True)
 assert rows[-1]['voltage_error']<=.001 and rows[2]['voltage_error']<rows[1]['voltage_error']<rows[0]['voltage_error']
 reference_record("sipi-mixed-startup-continuous","scikit-rf",rows[-1]["voltage_error"],None,None,clock,"continuous modal ABCD into4port admittance,500MHz20cycles256samples/final4,32/64/128cells")



def arguments(**changes):
    t=np.linspace(0,12e-9,121);drive=np.column_stack((np.minimum(t/2e-9,1.),-.008*np.minimum(t/3e-9,1.)))
    a=dict(time=t,sources=sources(drive,[0.,None],['voltage','current']),
        R=R,L=L,G=G,C=C,length=.1,cells=8,load_resistance=[91.,None],
        load_capacitance=np.array([[20.,-4.],[-4.,30.]])*1e-12,
        load_branch_resistance=[[13.,1.],[1.,9.]],load_branch_inductance=np.array([[12.,2.],[2.,8.]])*1e-9)
    a.update(changes);return a


def power_checks(r):
    assert max(r.power_balance_relative_error,r.total_power_balance_relative_error)<=1e-10
    np.testing.assert_allclose(r.line_power,r.energy_rate+r.series_loss+r.shunt_loss,rtol=1e-10,atol=1e-12)
    loss=r.source_series_resistor_loss+r.source_shunt_resistor_loss+r.series_loss+r.shunt_loss+r.load_resistor_loss+r.load_branch_resistor_loss
    np.testing.assert_allclose(r.source_power-loss,r.total_energy_rate,rtol=1e-10,atol=1e-12)
    for name in ['energy','load_capacitor_energy','load_branch_energy','source_series_resistor_loss','source_shunt_resistor_loss','series_loss','shunt_loss','load_resistor_loss','load_branch_resistor_loss']:
        assert np.all(getattr(r,name)>=0)


@pytest.mark.parametrize('kinds,resistance,load',[
    (['voltage','current'],[0.,None],[91.,None]),(['current','voltage'],[None,0.],[None,0.]),
    (['voltage','current'],[25.,37.],[91.,113.]),(['current','voltage'],[37.,25.],[91.,113.]),
    (['voltage','current'],[0.,0.],[0.,None]),(['current','voltage'],[0.,0.],[None,0.]),
])
def test_typed_ideal_short_and_finite_sources_preserve_units_and_power(kinds,resistance,load):
    a=arguments();drive=np.column_stack([np.minimum(a['time']/(2e-9+j*1e-9),1.)*(1. if k=='voltage' else .02) for j,k in enumerate(kinds)])
    a.update(sources=sources(drive,resistance,kinds),load_resistance=load)
    r=coupled_mixed_source_ladder_response(**a);power_checks(r)
    assert r.source_kinds==tuple(kinds) and r.source_units==tuple('V' if k=='voltage' else 'A' for k in kinds)
    np.testing.assert_array_equal(r.source_values,drive)
    for j,k in enumerate(kinds):
        if k=='voltage' and resistance[j]==0:np.testing.assert_array_equal(r.voltage[:,j],drive[:,j])
        if k=='current' and resistance[j]==0:assert np.all(r.voltage[:,j]==0)
        if k=='current' and resistance[j] is None:np.testing.assert_array_equal(r.current[:,j],drive[:,j])
    assert not hasattr(r,'source_voltages') and not hasattr(r,'source_currents') and not hasattr(r,'source_resistor_loss')


@pytest.mark.parametrize('kind',['voltage','current'])
def test_homogeneous_source_kinds_match_existing_qualified_physical_apis(kind):
    a=arguments();drive=np.column_stack((np.minimum(a['time']/2e-9,1.),-.4*np.minimum(a['time']/3e-9,1.)))*(1. if kind=='voltage' else .02)
    resistance=[0.,37.] if kind=='voltage' else [None,37.];a['sources']=sources(drive,resistance,[kind,kind])
    r=coupled_mixed_source_ladder_response(**a);a.pop('sources')
    other=(coupled_reactive_ladder_response(source_voltages=drive,source_resistance=resistance,**a) if kind=='voltage'
        else coupled_norton_reactive_ladder_response(source_currents=drive,source_shunt_resistance=resistance,**a))
    for name in ['voltage','current','node_voltage','segment_current','energy','energy_rate','load_capacitor_current','load_capacitor_energy','load_branch_current','load_branch_energy','source_power','load_resistor_loss']:
        np.testing.assert_allclose(getattr(r,name),getattr(other,name),rtol=1e-10,atol=1e-12)
    if kind=='voltage':
        assert not np.any(r.source_shunt_resistor_loss);np.testing.assert_array_equal(r.source_series_resistor_loss,other.source_resistor_loss)
    else:
        assert not np.any(r.source_series_resistor_loss);np.testing.assert_array_equal(r.source_shunt_resistor_loss,other.source_shunt_resistor_loss)
    power_checks(r)


@pytest.mark.parametrize('mutate',[
    lambda a:a.update(sources=None),lambda a:a.update(sources=[]),lambda a:a.update(sources=a['sources'][:1]),
    lambda a:a['sources'].__setitem__(0,None),lambda a:a['sources'][0].update(kind='mixed'),
    lambda a:a['sources'][0].update(kind=True),lambda a:a['sources'][0].update(current_a=[0.]*121),
    lambda a:a['sources'][0].pop('voltage_v'),lambda a:a['sources'][0].update(shunt_resistance_ohm=25.),
    lambda a:a['sources'][1].update(series_resistance_ohm=25.),lambda a:a['sources'][1].pop('current_a'),
    lambda a:a['sources'][0].update(series_resistance_ohm=None),lambda a:a['sources'][0].update(series_resistance_ohm=-1.),
    lambda a:a['sources'][1].update(shunt_resistance_ohm=np.inf),lambda a:a['sources'][1].update(shunt_resistance_ohm=True),
    lambda a:a['sources'][0].update(voltage_v=1.),lambda a:a['sources'][0].update(voltage_v=[[0.]*121]),
    lambda a:a['sources'][0].update(voltage_v=[0.,1.]),lambda a:a['sources'][0].update(voltage_v=[1.]*121),
    lambda a:a['sources'][1].update(current_a=[0.+0j]*121),lambda a:a['sources'][1].update(current_a=[False]*121),
    lambda a:a['sources'][1].update(current_a=[np.nan]*121),lambda a:a.update(time=[0.,1.,3.]),
    lambda a:a.update(load_resistance=[-1.,None]),lambda a:a.update(cells=129),
    lambda a:a.update(load_branch_inductance=np.zeros((2,2))),lambda a:a.update(C=np.zeros((2,2))),
])
def test_strict_sources_and_shared_passive_controls_reject_before_propagation(mutate,monkeypatch):
    import sipi.coupled_boundary_startup as core
    def forbidden(*a,**kw):pytest.fail('invalid input reached propagation')
    monkeypatch.setattr(core,'lsim',forbidden);a=arguments();mutate(a)
    with pytest.raises((ValueError,TypeError)):coupled_mixed_source_ladder_response(**a)


def test_detached_readonly_states_metadata_and_finite_json():
    a=arguments();r=coupled_mixed_source_ladder_response(**a);text=json.dumps(r.to_dict(include_states=True),sort_keys=True,allow_nan=False)
    a['sources'][0]['voltage_v'][:]=99;a['sources'][1]['kind']='voltage'
    data=r.inputs;data['sources'][0]['voltage_v'][0]=99
    for name in ['time','source_values','node_voltage','segment_current','voltage','current','energy','energy_rate','series_loss','shunt_loss','line_power','source_power','source_series_resistor_loss','source_shunt_resistor_loss','load_resistor_loss','load_capacitor_current','load_capacitor_energy','load_capacitor_power','load_branch_current','load_branch_energy','load_branch_energy_rate','load_branch_resistor_loss','total_energy','total_energy_rate']:
        assert not getattr(r,name).flags.writeable
    assert json.dumps(r.to_dict(include_states=True),sort_keys=True,allow_nan=False)==text
    out=r.to_dict();assert not out['states_included'] and 'node_voltage_v' not in out
    assert out['source_units']==['V','A'] and out['scope']=='finite-passive-two-signal-mixed-source-reactive-startup'
    with pytest.raises(ValueError):r.to_dict(include_states=1)


@pytest.mark.parametrize('rankone',[False,True])
def test_zero_and_rankone_external_loads_and_zero_drives(rankone):
    mat=np.array([[1.,-1.],[-1.,1.]]) if rankone else np.zeros((2,2));a=arguments(load_capacitance=mat*20e-12,load_branch_resistance=mat)
    r=coupled_mixed_source_ladder_response(**a);power_checks(r)
    a['sources'][0]['voltage_v'][:]=0;a['sources'][1]['current_a'][:]=0;r=coupled_mixed_source_ladder_response(**a)
    assert not np.any(r.voltage) and not np.any(r.current) and not np.any(r.total_energy);power_checks(r)


def test_linear_time_impedance_and_conductor_permutation_invariants():
    a=arguments();r=coupled_mixed_source_ladder_response(**a)
    b=arguments();b['sources'][0]['voltage_v']*= -.4;b['sources'][1]['current_a']*= -.4
    scaled=coupled_mixed_source_ladder_response(**b)
    np.testing.assert_allclose(scaled.voltage,-.4*r.voltage,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(scaled.current,-.4*r.current,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(scaled.total_energy,.16*r.total_energy,rtol=1e-10,atol=1e-20)
    b=arguments();b['time']=b['time']*3
    for name in ['L','C','load_capacitance','load_branch_inductance']:b[name]=np.array(b[name])*3
    stretched=coupled_mixed_source_ladder_response(**b)
    np.testing.assert_allclose(stretched.voltage,r.voltage,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(stretched.current,r.current,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(stretched.total_energy,r.total_energy*3,rtol=1e-10,atol=1e-20)
    b=arguments();b['sources'][1]['current_a']/=4
    for name in ['R','L','load_branch_resistance','load_branch_inductance']:b[name]=np.array(b[name])*4
    for name in ['G','C','load_capacitance']:b[name]=np.array(b[name])/4
    b['load_resistance']=[364.,None];z=coupled_mixed_source_ladder_response(**b)
    np.testing.assert_allclose(z.voltage,r.voltage,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(z.current,r.current/4,rtol=1e-10,atol=1e-12)
    b=arguments();b['sources']=b['sources'][::-1];b['load_resistance']=b['load_resistance'][::-1]
    for name in ['R','L','G','C','load_capacitance','load_branch_resistance','load_branch_inductance']:b[name]=np.array(b[name])[::-1,::-1]
    swapped=coupled_mixed_source_ladder_response(**b);order=[1,0,3,2]
    np.testing.assert_allclose(swapped.voltage,r.voltage[:,order],rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(swapped.current,r.current[:,order],rtol=1e-10,atol=1e-12)
    assert swapped.source_units==('A','V')
    for out in [scaled,stretched,z,swapped]:power_checks(out)


def test_lossless_postpulse_energy_is_preserved_with_mixed_ideal_sources():
    a=arguments(R=np.zeros((2,2)),G=np.zeros((2,2)),load_resistance=[None,None],load_branch_resistance=np.zeros((2,2)))
    pulse=np.interp(a['time'],[0,2e-9,4e-9,6e-9],[0,1,1,0])
    a['sources']=sources(np.column_stack((pulse,-.008*pulse)),[0.,None],['voltage','current'])
    r=coupled_mixed_source_ladder_response(**a);power_checks(r);energy=r.total_energy[a['time']>=6e-9]
    assert energy[0]>0;np.testing.assert_allclose(energy,energy[0],rtol=1e-10,atol=1e-20)
    assert not np.any(r.source_power[a['time']>=6e-9])


def test_unrepresentable_cell_scales_remain_failure():
    a=arguments(L=np.eye(2)*1e-300,C=np.eye(2)*1e-300,length=1e-300)
    with pytest.raises(ValueError,match='finite scales'):coupled_mixed_source_ladder_response(**a)
