# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent closed-form, modal and KCL checks of explicit external RL loads."""
import importlib.metadata as metadata
import json

import numpy as np
import pytest
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import coupled_reactive_ladder_response, coupled_capacitive_ladder_response
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
    kw=dict(R=R,L=L,G=G,C=C,length=.1,cells=16,source_resistance=[25.,25.],load_resistance=[100.,100.],
            load_capacitance=CL,load_branch_resistance=RB,load_branch_inductance=LB)
    kw.update(changes);return kw


def run(time=None,drive=None,**changes):
    time=np.linspace(0,12e-9,121) if time is None else time
    drive=np.column_stack((np.minimum(np.asarray(time)/2e-9,1.),np.zeros(len(time)))) if drive is None else drive
    return coupled_reactive_ladder_response(time,drive,**arguments(**changes))


def power_checks(r):
    for name in ['energy','load_capacitor_energy','load_branch_energy','series_loss','shunt_loss','load_branch_resistor_loss']:
        assert np.min(getattr(r,name))>=0
    assert r.power_balance_relative_error<=1e-10 and r.total_power_balance_relative_error<=1e-10
    np.testing.assert_allclose(r.energy_rate,r.line_power-r.series_loss-r.shunt_loss,rtol=1e-10,atol=1e-14)
    np.testing.assert_allclose(r.total_energy_rate,r.source_power-r.source_resistor_loss-r.load_resistor_loss-r.series_loss-r.shunt_loss-r.load_branch_resistor_loss,rtol=1e-10,atol=1e-14)
    np.testing.assert_allclose(np.sum(r.voltage[:,2:]*r.load_branch_current,axis=1),r.load_branch_energy_rate+r.load_branch_resistor_loss,rtol=1e-10,atol=1e-14)


def circuit(t,drive,n,r=R,l=L,g=G,c=C,source=(25.,25.),load=(100.,100.),load_capacitance=CL,length=.1,branch_r=RB,branch_l=LB):
    result=run(t,drive,cells=n,R=r,L=l,G=g,C=c,source_resistance=source,load_resistance=load,
        load_capacitance=load_capacitance,length=length,load_branch_resistance=branch_r,load_branch_inductance=branch_l)
    power_checks(result)
    return dict(v=result.voltage,i=result.current,energy=result.energy,capenergy=result.load_capacitor_energy,
        branch_current=result.load_branch_current,branch_energy=result.load_branch_energy,
        power_error=result.power_balance_relative_error,total_power_error=result.total_power_balance_relative_error)


def reference_record(case,tool,error,limit,clock,details):
    record=make_record(case=case,physics='passive two-signal line with parallel C and series RL load',
        api='sipi.coupled_reactive_ladder_response',discretization='explicit fullmatrix finite RLGC cells and external RL current states',
        tool=tool,tool_discretization=details,matched=['constant line and external load matrices,zero state,mixed resistive ends,explicit PWL drive'],
        not_matched=['finite spatial cells/PWL versus continuous phasor reference where applicable'],
        observables=[observable('response error','V','maximum voltage difference',error,limit)],
        analytical_acceptance='exact one-cell L-C-L ramp/hold and separate energy/power identities',stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)


def test_single_cell_exact_l_c_l_ramp_hold_and_separate_energy():
 t=np.linspace(0,4,401);amp=np.array([1.,-.4]);drive=np.minimum(t,1.)[:,None]*amp;cl=np.array([.3,.7]);lb=np.array([.8,1.3])
 actual=circuit(t,drive,1,r=np.zeros((2,2)),l=np.eye(2),g=np.zeros((2,2)),c=.4*np.eye(2),source=[0.,0.],load=[None,None],load_capacitance=np.diag(cl),length=1.,branch_r=np.zeros((2,2)),branch_l=np.diag(lb))
 vol=[];dv=[];ibr=[]
 for j in range(2):
  total=.2+cl[j];gain=lb[j]/(1+lb[j]);w=np.sqrt((1+1/lb[j])/total);ka=gain*amp[j]
  before=ka*(t-np.sin(w*t)/w);dvbefore=ka*(1-np.cos(w*t));integralbefore=ka*(t*t/2+(np.cos(w*t)-1)/w**2)
  aa=-ka*np.sin(w)/w;bb=ka*(1-np.cos(w))/w;shift=t-1
  after=ka+aa*np.cos(w*shift)+bb*np.sin(w*shift);dvafter=-aa*w*np.sin(w*shift)+bb*w*np.cos(w*shift)
  integralafter=ka*(.5+(np.cos(w)-1)/w**2)+ka*shift+aa*np.sin(w*shift)/w+bb*(1-np.cos(w*shift))/w
  vol.append(np.where(t<=1,before,after));dv.append(np.where(t<=1,dvbefore,dvafter));ibr.append(np.where(t<=1,integralbefore,integralafter)/lb[j])
 voltage=np.stack(vol,axis=-1);dv=np.stack(dv,axis=-1);ib=np.stack(ibr,axis=-1);iline=(.2+cl)*dv+ib
 slope=np.vstack((np.diff(drive,axis=0)/np.diff(t)[:,None],[0.,0.]));expectedi=np.concatenate((iline+.2*slope,-dv*cl-ib),axis=1)
 expectedenergy=.5*np.sum(iline**2,axis=1)+.1*np.sum(drive**2+voltage**2,axis=1);expectedcap=.5*np.sum(cl*voltage**2,axis=1);expectedbranch=.5*np.sum(lb*ib**2,axis=1)
 for a,b in [(actual['v'][:,2:],voltage),(actual['i'],expectedi),(actual['branch_current'],ib),(actual['energy'],expectedenergy),(actual['capenergy'],expectedcap),(actual['branch_energy'],expectedbranch)]:np.testing.assert_allclose(a,b,rtol=1e-10,atol=1e-12)


def test_independent_modal_rl_load_refinement():
 skrf=require_tool("scikit-rf");clock=Stopwatch()
 f=500e6;w=2*np.pi*f;t=np.arange(20*256+1)/(f*256);drive=np.column_stack((np.sin(w*t),np.zeros(len(t))));capload=np.array([[30.,-5.],[-5.,30.]])*1e-12;rb=np.array([[10.,2.],[2.,10.]]);lb=rb*1e-9;modal=[]
 with clock("reference"):
  for m in range(2):
   rm,lm,gm,cm=[(Q.T@a@Q)[m,m] for a in [R,L,G,C]];clm,rbm,lbm=[(Q.T@a@Q)[m,m] for a in [capload,rb,lb]]
   gamma=np.sqrt((rm+1j*w*lm)*(gm+1j*w*cm));zc=np.sqrt((rm+1j*w*lm)/(gm+1j*w*cm));yl=1/100+1j*w*clm+1/(rbm+1j*w*lbm)
   media=skrf.media.DefinedGammaZ0(frequency=skrf.Frequency.from_f([f],unit='hz'),z0_port=50.,z0=zc,gamma=gamma)
   a,b,c,d=media.line(.1,unit='m').a[0].ravel();vl=Q[0,m]/(a+b*yl+25*(c+d*yl));modal.append(np.array([(a+b*yl)*vl,vl]))
 expected=(np.stack(modal,axis=-1)@Q.T).ravel();last=slice(-4*256-1,-1);phase=np.exp(-1j*w*t[last]);rows=[]
 for n in [32,64,128]:
  with clock('openphysics'):result=circuit(t,drive,n,load_capacitance=capload,branch_r=rb,branch_l=lb)
  phasor=2/len(phase)*(phase@result['v'][last])/(-1j)
  rows.append(dict(cells=n,voltage_error=float(np.max(abs(phasor-expected))),power_error=result['power_error'],total_power_error=result['total_power_error']))
 print('reactive load modal refinement',rows)
 assert rows[-1]['voltage_error']<=.001 and rows[2]['voltage_error']<rows[1]['voltage_error']<rows[0]['voltage_error']
 reference_record("sipi-coupled-rl-load-modal","scikit-rf",rows[-1]["voltage_error"],.001,clock,"scikit-rf modal continuous ABCD with shunt R/C and series R+jwL admittance")


def test_independent_asymmetric_node_kcl_with_rl_states():
 require_tool("scipy");from scipy.integrate import solve_ivp
 clock=Stopwatch()
 n=16;dx=.1/n;nv=2*(n+1);base_size=4*n+2;r=np.array([[25.,2.],[2.,17.]]);l=np.array([[510.,70.],[70.,430.]])*1e-9
 g=np.array([[.003,-.0002],[-.0002,.0015]]);c=np.array([[230.,-30.],[-30.,190.]])*1e-12;capload=np.array([[20.,-4.],[-4.,30.]])*1e-12
 rb=np.array([[13.,1.],[1.,9.]]);lb=np.array([[12.,2.],[2.,8.]])*1e-9
 u=np.linspace(0,12,241);free=np.arange(1,base_size+2)
 def drive_u(t):return np.array([np.interp(t,[0,2],[0,1]),np.interp(t,[0,3],[0,-.4])])
 def dynamics(t,xf,all_states=False):
  x=np.zeros(base_size+2);x[free]=xf;x[0]=drive_u(t)[0];v=x[:nv].reshape(n+1,2);i=x[nv:base_size].reshape(n,2);ib=x[-2:];dv=np.zeros_like(v)
  flow=np.zeros_like(v);flow[:-1]-=i;flow[1:]+=i;flow[-1]-=ib
  flow[0,1]+=(drive_u(t)[1]-v[0,1])/37.;flow[-1,0]-=v[-1,0]/91.
  dv[1:-1]=np.linalg.solve(c,(flow[1:-1]/dx-v[1:-1]@g.T).T).T
  dv[0,0]=.5/1e-9 if t<2 else 0.
  dv[0,1]=(flow[0,1]/(dx*.5)-g[1]@v[0]-c[1,0]*dv[0,0])/c[1,1]
  dv[-1]=np.linalg.solve(c*dx*.5+capload,flow[-1]-g@v[-1]*dx*.5)
  di=np.linalg.solve(l,((v[:-1]-v[1:])/dx-i@r.T).T).T;dib=np.linalg.solve(lb,v[-1]-rb@ib);deriv=np.r_[dv.ravel(),di.ravel(),dib]
  return (x,deriv) if all_states else 1e-9*deriv[free]
 ce,cu=np.linalg.eigh(c);cs=(cu*np.sqrt(ce))@cu.T;min_tau=float(.1*np.sqrt(np.linalg.eigvalsh(cs@l@cs)[0])/1e-9)
 with clock('reference'):
  ref=solve_ivp(dynamics,[0,12],np.zeros(len(free)),method='DOP853',t_eval=u,rtol=1e-10,atol=1e-12,max_step=min_tau/(5*n))
 assert ref.success
 with clock('openphysics'):actual=circuit(u*1e-9,np.array([drive_u(t) for t in u]),n,r,l,g,c,[0.,37.],[91.,None],load_capacitance=capload,branch_r=rb,branch_l=lb)
 pairs=[dynamics(t,xf,True) for t,xf in zip(u,ref.y.T)];full=np.array([x[0] for x in pairs]);deriv=np.array([x[1] for x in pairs])
 v=full[:,:nv].reshape(len(u),n+1,2);ii=full[:,nv:base_size].reshape(len(u),n,2);ib=full[:,-2:];dv=deriv[:,:nv].reshape(v.shape)
 expectedv=v[:,[0,n],:].reshape(len(u),4);expectedi=np.zeros_like(expectedv)
 expectedi[:,0]=(dv[:,0]@c[0]+v[:,0]@g[0])*dx*.5+ii[:,0,0]
 expectedi[:,1]=(np.array([drive_u(t)[1] for t in u])-v[:,0,1])/37.
 expectedi[:,2:]=-dv[:,-1]@capload.T-ib;expectedi[:,2]-=v[:,-1,0]/91.
 ev=float(np.max(abs(actual['v']-expectedv)));ei=float(np.max(abs(actual['i']-expectedi)));eb=float(np.max(abs(actual['branch_current']-ib)))
 print('reactive load asymmetric errors',ev,ei,eb)
 assert ev<=1e-8 and max(ei,eb)<=1e-9
 reference_record("sipi-coupled-rl-load-kcl","scipy",ev,1e-8,clock,"per-node KCL and external branch voltage ODE,DOP853 rtol1e-10/atol1e-12")


@pytest.mark.parametrize('source,load',[([0.,0.],[0.,0.]),([0.,37.],[0.,None]),([23.,0.],[91.,0.]),([23.,37.],[None,None]),([23.,37.],[91.,113.])])
def test_mixed_boundaries_and_branch_terminal_power(source,load):
    r=run(source_resistance=source,load_resistance=load);power_checks(r)
    for j in range(2):
        if source[j]==0:np.testing.assert_array_equal(r.voltage[:,j],r.source_voltages[:,j])
        if load[j]==0:assert np.all(r.voltage[:,2+j]==0)
        else:
            resistive=0 if load[j] is None else r.voltage[:,2+j]/load[j]
            np.testing.assert_allclose(r.current[:,2+j],-resistive-r.load_capacitor_current[:,j]-r.load_branch_current[:,j],rtol=1e-12,atol=1e-14)
    if load==[0.,0.]:
        for name in ['load_branch_current','load_branch_energy','load_branch_resistor_loss','load_capacitor_energy']:
            assert np.all(getattr(r,name)==0)
        kw=arguments(source_resistance=source,load_resistance=load);kw.pop('load_branch_resistance');kw.pop('load_branch_inductance')
        old=coupled_capacitive_ladder_response(r.time,r.source_voltages,**kw)
        np.testing.assert_allclose(r.voltage,old.voltage,rtol=1e-10,atol=1e-12)
        np.testing.assert_allclose(r.current,old.current,rtol=1e-10,atol=1e-12)


def test_short_conductor_mutual_inductance_current_is_not_zeroed():
    r=run(source_resistance=[0.,37.],load_resistance=[0.,None]);power_checks(r)
    assert np.all(r.voltage[:,2]==0) and np.max(abs(r.load_branch_current[:,0]))>1e-6


def test_zero_input_and_rank_one_branch_resistance():
    r=run(drive=np.zeros((121,2)),load_branch_resistance=np.array([[1.,-1.],[-1.,1.]]));power_checks(r)
    assert np.all(r.voltage==0) and np.all(r.total_energy==0)
    r=run(load_branch_resistance=np.array([[1.,-1.],[-1.,1.]]));power_checks(r)


def test_dc_finite_series_branch_limit():
    t=np.linspace(0,500e-9,2501);drive=np.minimum(t/2e-9,1.)[:,None]*np.array([1.,-.4])
    rs=np.array([23.,37.]);rl=np.array([91.,113.]);r=run(t,drive,G=np.zeros((2,2)),source_resistance=rs,load_resistance=rl,cells=8)
    y=np.diag(1/rl)+np.linalg.inv(RB);vfar=np.linalg.solve(np.eye(2)+(np.diag(rs)+R*.1)@y,drive[-1])
    iline=y@vfar;vnear=vfar+R*.1@iline;ib=np.linalg.solve(RB,vfar)
    np.testing.assert_allclose(r.voltage[-1],np.r_[vnear,vfar],rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(r.segment_current[-1],np.tile(iline,(8,1)),rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(r.load_branch_current[-1],ib,rtol=1e-10,atol=1e-12)
    assert np.max(abs(r.load_capacitor_current[-1]))<=1e-13
    power_checks(r)


def test_time_impedance_and_conductor_permutation():
    r=run();power_checks(r);scale=3.;impedance=2.
    timed=run(r.time*scale,r.source_voltages,L=L*scale,C=C*scale,load_capacitance=CL*scale,load_branch_inductance=LB*scale)
    z=run(r.time,r.source_voltages,R=R*impedance,L=L*impedance,G=G/impedance,C=C/impedance,
        source_resistance=[50.,50.],load_resistance=[200.,200.],load_capacitance=CL/impedance,
        load_branch_resistance=RB*impedance,load_branch_inductance=LB*impedance)
    np.testing.assert_allclose(timed.voltage,r.voltage,rtol=1e-9,atol=1e-12)
    np.testing.assert_allclose(timed.load_branch_current,r.load_branch_current,rtol=1e-9,atol=1e-12)
    np.testing.assert_allclose(timed.total_energy,r.total_energy*scale,rtol=1e-9,atol=1e-20)
    np.testing.assert_allclose(z.voltage,r.voltage,rtol=1e-9,atol=1e-12)
    np.testing.assert_allclose(z.load_branch_current,r.load_branch_current/impedance,rtol=1e-9,atol=1e-12)
    np.testing.assert_allclose(z.total_energy,r.total_energy/impedance,rtol=1e-9,atol=1e-20)
    swapped=run(r.time,r.source_voltages[:,::-1])
    np.testing.assert_allclose(swapped.node_voltage,r.node_voltage[:,:,::-1],rtol=1e-9,atol=1e-12)
    np.testing.assert_allclose(swapped.load_branch_current,r.load_branch_current[:,::-1],rtol=1e-9,atol=1e-12)
    for a in [timed,z,swapped]:power_checks(a)


def test_superposition_and_negative_pulse_power():
    t=np.linspace(0,12e-9,121);a=np.column_stack((np.minimum(t/2e-9,1.),np.zeros(len(t))))
    b=np.column_stack((np.zeros(len(t)),-.4*np.interp(t,[0,2e-9,4e-9,6e-9],[0,1,1,0])))
    ra=run(t,a);rb=run(t,b);ab=run(t,a+b)
    np.testing.assert_allclose(ab.voltage,ra.voltage+rb.voltage,rtol=1e-9,atol=1e-12)
    np.testing.assert_allclose(ab.load_branch_current,ra.load_branch_current+rb.load_branch_current,rtol=1e-9,atol=1e-12)
    for r in [ra,rb,ab]:power_checks(r)


def test_nested_copies_read_only_states_and_finite_json():
    kwargs=arguments(load_branch_inductance=LB.copy(),load_branch_resistance=RB.copy(),load_capacitance=CL.copy())
    t=np.linspace(0,12e-9,121);drive=np.column_stack((np.minimum(t/2e-9,1.),np.zeros(len(t))))
    r=coupled_reactive_ladder_response(t,drive,**kwargs);text=json.dumps(r.to_dict(include_states=True),sort_keys=True,allow_nan=False)
    for name in ['load_branch_current','load_branch_energy','load_branch_energy_rate','load_branch_resistor_loss','total_energy','total_energy_rate']:
        assert not getattr(r,name).flags.writeable
    t[:]=9;drive[:]=9;kwargs['load_branch_inductance'][:]=9;kwargs['load_branch_resistance'][:]=9
    d=r.inputs;d['load_branch_inductance_h'][0][0]=99
    assert json.dumps(r.to_dict(include_states=True),sort_keys=True,allow_nan=False)==text
    assert r.to_dict()['scope']=='finite-passive-two-signal-reactive-load-rlgc-startup'
    assert not r.to_dict()['states_included'] and r.to_dict(include_states=True)['states_included']


@pytest.mark.parametrize('field,value',[
    ('load_branch_inductance',np.zeros((2,2))),('load_branch_inductance',[[1.,0.],[0.,1e-14]]),
    ('load_branch_inductance',[[1.,1.],[1.,1.]]),('load_branch_inductance',[[1.,0.],[0.,-1e-30]]),
    ('load_branch_inductance',[[1.,1e-15],[0.,1.]]),('load_branch_inductance',[[True,0],[0,1]]),
    ('load_branch_inductance',np.eye(2)*complex(1,1)),('load_branch_inductance',1.),
    ('load_branch_resistance',[[1.,0.],[0.,-1e-30]]),('load_branch_resistance',[[1.,1e-15],[0.,1.]]),
    ('load_branch_resistance',[[True,0],[0,1]]),('load_branch_resistance',[[1.,0.],[0.,np.inf]]),
    ('load_branch_resistance',[[[1.,0.],[0.,1.]]]),('load_branch_resistance',0.),
    ('load_capacitance',[[1.,0.],[0.,-1e-30]]),('load_capacitance',[[1.,1e-15],[0.,1.]]),
])
def test_invalid_external_matrix_rejected_before_propagation(field,value,monkeypatch):
    def forbidden(*a,**k):pytest.fail('invalid matrix reached propagation')
    monkeypatch.setattr(engine,'lsim',forbidden)
    with pytest.raises((ValueError,TypeError)):run(**{field:value})


def test_runtime_state_shape_and_nonfinite_guard(monkeypatch):
    for bad in [np.zeros((121,2)),np.full((121,68),np.nan)]:
        monkeypatch.setattr(engine,'lsim',lambda *a,**k:(None,None,bad))
        with pytest.raises(ValueError,match='state propagation'):run()


def test_lossless_post_pulse_energy_exchange_includes_inductor():
    t=np.linspace(0,12e-9,1201)
    drive=np.column_stack((np.interp(t,[0,2e-9,4e-9,6e-9],[0,1,1,0]),np.zeros(len(t))))
    r=run(t,drive,R=np.zeros((2,2)),G=np.zeros((2,2)),load_branch_resistance=np.zeros((2,2)),
          source_resistance=[0.,0.],load_resistance=[None,None]);power_checks(r)
    after=t>=6.1e-9;energy=r.total_energy[after]
    assert np.min(energy)>0 and np.ptp(r.load_branch_energy[after])>1e-14
    np.testing.assert_allclose(energy,np.full_like(energy,energy[0]),rtol=1e-10,atol=1e-20)
    assert np.all(r.source_power[after]==0) and np.all(r.load_branch_resistor_loss==0)


def test_tiny_branch_inductance_rejects_unrepresentable_dynamics():
    with pytest.raises(ValueError,match='finite scales'):
        run(load_branch_inductance=np.eye(2)*5e-324)
