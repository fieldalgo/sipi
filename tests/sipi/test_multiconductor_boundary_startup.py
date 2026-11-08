# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit mixed ends: original charge KCL, analytical limits and spatial refinement."""
import json
import numpy as np
import pytest
from dataclasses import fields
from itertools import product
from importlib import metadata
from scipy.integrate import solve_ivp
from crosscheck import Stopwatch,emit,make_record,observable,require_tool
from sipi import (multiconductor_boundary_ladder_response as response,
 coupled_boundary_ladder_response,rlgc_ladder_response,lossless_line_response,
 multiconductor_rlgc_ladder_response,psd_multiconductor_debye_rlgc_ladder_response,startup_port_waves)
import sipi.multiconductor_boundary_startup as module

def fixture(signals=3,pulse=False,cells=8,rows=121):
 t=np.linspace(0,12e-9,rows);u=np.minimum(t/2e-9,1.)
 if pulse:u-=np.minimum(np.maximum((t-6e-9)/2e-9,0.),1.)
 j=np.arange(signals);off=np.eye(signals,k=1)+np.eye(signals,k=-1)
 R=np.zeros((signals,signals));R[:2,:2]=[[20,-20],[-20,20]]
 G=np.zeros_like(R);G[1:3,1:3]=[[.002,.002],[.002,.002]]
 return dict(time=t,source_voltages=u[:,None]*np.array([1.,-.4,.2,-.1])[:signals],signals=signals,
 R=R,L=(np.diag(450+20*j)+60*off)*1e-9,G=G,C=(np.diag(210+10*j)-20*off)*1e-12,
 length=.1,cells=cells,source_resistance=np.array([0.,25.,0.,40.])[:signals],load_resistance=[None,0.,75.,0.][:signals])

def power(r):
 assert r.power_balance_relative_error<=1e-10 and r.total_power_balance_relative_error<=1e-10
 np.testing.assert_allclose(r.energy_rate,r.line_power-r.series_loss-r.shunt_loss,rtol=1e-10,atol=1e-12)
 np.testing.assert_allclose(r.source_power,r.source_resistor_loss+r.load_resistor_loss+r.line_power,rtol=1e-10,atol=1e-12)
 assert np.min(r.energy)>=0 and np.min(r.series_loss)>=0 and np.min(r.shunt_loss)>=0
 n=r.inputs['signals'];rs=r.inputs['source_resistance_ohm'];rl=r.inputs['load_resistance_ohm']
 for j in range(n):
  if rs[j]==0:np.testing.assert_array_equal(r.voltage[:,j],r.source_voltages[:,j])
  else:np.testing.assert_allclose(r.current[:,j],(r.source_voltages[:,j]-r.voltage[:,j])/rs[j],rtol=1e-13,atol=1e-15)
  if rl[j] is None:assert not np.any(r.current[:,n+j])
  elif rl[j]==0:assert not np.any(r.voltage[:,n+j])
  else:np.testing.assert_allclose(r.current[:,n+j],-r.voltage[:,n+j]/rl[j],rtol=1e-13,atol=1e-15)
 return r

def forbid(*a,**kw):pytest.fail('invalid input reached propagation')

@pytest.mark.parametrize('n',[3,4])
@pytest.mark.parametrize('key,bad',[
 ('signals',True),('signals',3.),('signals',2),('signals',5),('signals',None),
 ('cells',True),('cells',1.),('cells',0),('cells',129),
 ('length',True),('length',0.),('length',-1.),('length',float('inf')),
 ('time',None),('time',[0.]),('time',[1.,2.]),('time',[0.,1.,3.]),('time',[0.,1.,1.]),('time',[0.,True,2.]),('time',[0.,complex(1),2.])])
def test_general_input_rejected_before_propagation(n,key,bad,monkeypatch):
 a=fixture(n);a[key]=bad;monkeypatch.setattr(module,'lsim',forbid)
 with pytest.raises((ValueError,TypeError)):response(**a)

@pytest.mark.parametrize('n',[3,4])
@pytest.mark.parametrize('key',['source_resistance','load_resistance'])
@pytest.mark.parametrize('bad',['none','scalar','short','long','matrix','negative','tinynegative','boolean','complex','string','nonfinite'])
def test_explicit_boundary_vectors_reject(n,key,bad,monkeypatch):
 a=fixture(n);x=[25.]*n
 if bad=='none':x=None
 elif bad=='scalar':x=25.
 elif bad=='short':x.pop()
 elif bad=='long':x.append(25.)
 elif bad=='matrix':x=np.diag(x)
 else:x[0]={'negative':-1.,'tinynegative':-1e-300,'boolean':True,'complex':25+0j,'string':'25','nonfinite':np.inf}[bad]
 a[key]=x;monkeypatch.setattr(module,'lsim',forbid)
 with pytest.raises((ValueError,TypeError)):response(**a)

@pytest.mark.parametrize('n',[3,4])
@pytest.mark.parametrize('key',['R','L','G','C'])
@pytest.mark.parametrize('bad',['shape','asymmetry','negative','tinynegative','boolean','complex','nonfinite'])
def test_matrix_contract(n,key,bad,monkeypatch):
 a=fixture(n);x=np.eye(n)
 if bad=='shape':x=np.eye(n+1)
 elif bad=='asymmetry':x[0,1]=np.nextafter(0.,1.)
 elif bad=='negative':x[0,0]=-1.
 elif bad=='tinynegative':x[0,0]=-1e-300
 elif bad=='boolean':x=x.astype(bool)
 elif bad=='complex':x=x.astype(complex)
 else:x[0,0]=np.inf
 a[key]=x;monkeypatch.setattr(module,'lsim',forbid)
 with pytest.raises((ValueError,TypeError)):response(**a)

@pytest.mark.parametrize('n',[3,4])
@pytest.mark.parametrize('key',['L','C'])
@pytest.mark.parametrize('kind',['zero','singular','ratio'])
def test_storage_conditioning_rejected(n,key,kind,monkeypatch):
 a=fixture(n);x=np.eye(n)
 if kind=='zero':x[:]=0
 else:x[-1,-1]=0 if kind=='singular' else 1e-13
 a[key]=x;monkeypatch.setattr(module,'lsim',forbid)
 with pytest.raises(ValueError):response(**a)

@pytest.mark.parametrize('n',[3,4])
@pytest.mark.parametrize('bad',['scalar','oned','wrongsignals','short','boolean','complex','nonfinite','first','too-many'])
def test_time_drive_identity_and_budget(n,bad,monkeypatch):
 a=fixture(n);x=a['source_voltages']
 if bad=='scalar':x=1.
 elif bad=='oned':x=x[:,0]
 elif bad=='wrongsignals':x=x[:,:-1]
 elif bad=='short':x=x[:-1]
 elif bad=='boolean':x=x.astype(bool)
 elif bad=='complex':x=x.astype(complex)
 elif bad=='nonfinite':x[1,0]=np.inf
 elif bad=='first':x[0,0]=1e-30
 else:a['time']=np.linspace(0,12e-9,10001);x=np.zeros((10001,n))
 a['source_voltages']=x;monkeypatch.setattr(module,'lsim',forbid)
 with pytest.raises((ValueError,TypeError)):response(**a)

@pytest.mark.parametrize('n',[3,4])
@pytest.mark.parametrize('kind',['cell-underflow','source-conductance','load-conductance','slope-overflow'])
def test_nonrepresentable_coefficients_reject_before_propagation(n,kind,monkeypatch):
 a=fixture(n)
 if kind=='cell-underflow':a.update(L=np.eye(n)*1e-300,C=np.eye(n)*1e-300,length=1e-300)
 elif kind=='source-conductance':a['source_resistance'][0]=1e-320
 elif kind=='load-conductance':a['load_resistance'][0]=1e-320
 else:a['source_voltages'][1,0]=1e308
 monkeypatch.setattr(module,'lsim',forbid)
 with pytest.raises(ValueError,match='finite scales'):response(**a)

@pytest.mark.parametrize('n',[3,4])
@pytest.mark.parametrize('kind',['shape','nan'])
def test_bad_propagation_shape_and_values(n,kind,monkeypatch):
 a=fixture(n)
 def broken(system,drive,time,**kw):
  value=np.zeros((len(time),system[0].shape[0]+(kind=='shape')))
  if kind=='nan':value[1,0]=np.nan
  return time,np.zeros(len(time)),value
 monkeypatch.setattr(module,'lsim',broken)
 with pytest.raises(ValueError,match='invalid shape or nonfinite'):response(**a)

@pytest.mark.parametrize('n',[3,4])
@pytest.mark.parametrize('tiny',[0.,1e-13,1e-20])
def test_exact_psd_nearzero_entries_preserved(n,tiny):
 a=fixture(n);a.update(R=np.diag([20.]+[20*tiny]*(n-1)),G=np.diag([.002]+[.002*tiny]*(n-1)))
 r=power(response(**a));assert r.inputs['R_ohm_per_m']==a['R'].tolist() and r.inputs['G_s_per_m']==a['G'].tolist()

@pytest.mark.parametrize('n',[3,4])
def test_permutation_and_physical_scaling(n):
 a=fixture(n);r=power(response(**a));p=np.arange(n)[::-1];b=dict(a)
 for key in ['R','L','G','C']:b[key]=a[key][np.ix_(p,p)]
 b['source_voltages']=a['source_voltages'][:,p];b['source_resistance']=a['source_resistance'][p];b['load_resistance']=[a['load_resistance'][j] for j in p]
 other=power(response(**b));order=np.r_[p,n+p]
 for key in ['voltage','current']:np.testing.assert_allclose(getattr(other,key),getattr(r,key)[:,order],rtol=1e-10,atol=1e-12)
 b=dict(a);b.update(length=a['length']*3,**{key:a[key]/3 for key in ['R','L','G','C']});other=power(response(**b))
 for key in ['node_voltage','segment_current','current','energy','source_power']:np.testing.assert_allclose(getattr(other,key),getattr(r,key),rtol=1e-10,atol=1e-12)
 b=dict(a);b['source_voltages']=a['source_voltages']*-.7;other=power(response(**b))
 for key in ['node_voltage','segment_current','current']:np.testing.assert_allclose(getattr(other,key),-.7*getattr(r,key),rtol=1e-10,atol=1e-12)
 for key in ['energy','source_power','series_loss','shunt_loss']:np.testing.assert_allclose(getattr(other,key),.49*getattr(r,key),rtol=1e-10,atol=1e-12)

@pytest.mark.parametrize('n',[3,4])
def test_zero_detached_readonly_json_and_separate_wave_type(n):
 a=fixture(n);r=power(response(**a));before=json.dumps(r.to_dict(include_states=True),sort_keys=True,allow_nan=False)
 for f in fields(r):
  if isinstance(getattr(r,f.name),np.ndarray):assert not getattr(r,f.name).flags.writeable
 a['source_voltages'][1,0]=999;a['L'][:]=999;out=r.to_dict(include_states=True);out['input']['load_resistance_ohm'][0]=999
 assert json.dumps(r.to_dict(include_states=True),sort_keys=True,allow_nan=False)==before
 assert r.port_names==tuple(f'{end}_{j}' for end in ['near','far'] for j in range(n))
 assert startup_port_waves(r,z_ref=[50.]*(2*n)).incident.shape==(121,2*n)
 with pytest.raises(ValueError):r.to_dict(include_states=1)
 a=fixture(n);a['source_voltages'][:]=0;r=power(response(**a))
 for key in ['node_voltage','segment_current','voltage','current','energy','energy_rate','source_power']:assert not np.any(getattr(r,key))


def independent(a):
 n=a['signals'];cells=a['cells'];dx=a['length']/cells;t=a['time'];drive=a['source_voltages'];rs=a['source_resistance'];rl=a['load_resistance'];C=a['C'];L=a['L'];R=a['R'];G=a['G']
 fixed=np.zeros((cells+1,n),dtype=bool);fixed[0]=rs==0;fixed[-1]=[x==0 for x in rl];free=~fixed;nv=int(free.sum());weights=np.ones(cells+1);weights[[0,-1]]=.5
 def sample(tt,segment):
  k=min(np.searchsorted(t,segment,side='right')-1,len(t)-2);k=max(k,0)
  # Every integration interval stays within a declared waveform knot.
  slope=(drive[k+1]-drive[k])/(t[k+1]-t[k]);return drive[k]+(tt-t[k])*slope,slope
 def evaluate(tt,y,segment):
  vs,slope=sample(tt,segment);v=np.zeros((cells+1,n));v[free]=y[:nv];v[0,fixed[0]]=vs[fixed[0]];i=y[nv:].reshape(cells,n)
  dv=np.zeros_like(v);dv[0,fixed[0]]=slope[fixed[0]]
  for k in range(cells+1):
   charge=-dx*weights[k]*(G@v[k])
   if k>0:charge+=i[k-1]
   if k<cells:charge-=i[k]
   if k==0:
    for j in range(n):
     if rs[j]>0:charge[j]+=(vs[j]-v[k,j])/rs[j]
   if k==cells:
    for j in range(n):
     if rl[j] is not None and rl[j]>0:charge[j]-=v[k,j]/rl[j]
   f=free[k];p=fixed[k]
   if np.any(f):dv[k,f]=np.linalg.solve(C[np.ix_(f,f)]*dx*weights[k],charge[f]-dx*weights[k]*C[np.ix_(f,p)]@dv[k,p])
  di=np.linalg.solve(L*dx,(v[:-1]-v[1:]-i@R.T*dx).T).T
  return np.r_[dv[free],di.ravel()],v,i,dv
 # Integrate declared ramp corners separately using direct free voltages,
 # not the candidate's transformed state, mass matrix or lsim coefficients.
 knots=[0.,2e-9,6e-9,8e-9,12e-9];y=np.zeros(nv+cells*n);states=[]
 for start,end in zip(knots,knots[1:]):
  sol=solve_ivp(lambda tt,z:evaluate(tt,z,(start+end)/2)[0],(start,end),y,method='DOP853',rtol=1e-11,atol=1e-15,max_step=.005e-9,dense_output=True)
  assert sol.success;y=sol.y[:,-1]
  ix=np.where((t>=start)&((t<end) if end<t[-1] else (t<=end)))[0]
  for k in ix:states.append((k,sol.sol(t[k])))
 states=dict(states);v=[];i=[];cur=[]
 for k,tt in enumerate(t):
  # Right derivatives at corners; final slope is explicitly zero.
  segment=tt if k<len(t)-1 else tt+1e-9
  _,vv,ii,dv=evaluate(tt,states[k],segment)
  if k==len(t)-1:
   # Last drive is flat for these fixtures, matching final derivative zero.
   assert np.all(drive[-1]==drive[-2])
  near=(dv[0]@C.T+vv[0]@G.T)*dx*.5+ii[0]
  far=(dv[-1]@C.T+vv[-1]@G.T)*dx*.5-ii[-1]
  v.append(vv);i.append(ii);cur.append(np.r_[near,far])
 return np.array(v),np.array(i),np.array(cur)

@pytest.mark.parametrize('n',[3,4])
@pytest.mark.parametrize('pulse',[False,True])
def test_independent_original_charge_kcl(n,pulse):
 require_tool('scipy');clock=Stopwatch();a=fixture(n,pulse)
 with clock('openphysics'):actual=power(response(**a))
 with clock('reference'):v,i,cur=independent(a)
 ev=float(np.max(abs(actual.node_voltage-v)));ei=float(np.max(abs(actual.segment_current-i)));ec=float(np.max(abs(actual.current-cur)))
 assert ev<=1e-8 and ei<=1e-9 and ec<=1e-9
 record=make_record(case=f'sipi-multiconductor-boundary-kcl-{n}-{pulse}',physics='constant passive multiconductor circuit with ideal/open/short boundaries',
  api='sipi.multiconductor_boundary_ladder_response',discretization='finite half-end pi circuit; fixed-voltage mass elimination and transformed-state PWL lsim',
  tool='scipy',tool_discretization='independent original per-node charge KCL, direct free voltages with fixed-voltage derivative forcing, DOP853 and split input knots',
  matched=['same noncommuting PSD R/G,SPD L/C,length,cells,explicit boundary vectors andPWL samples'],
  not_matched=['finite circuit rather than Maxwell or measured interconnect'],
  observables=[observable('node voltage','V','maximum absolute error',ev,1e-8),observable('segment current','A','maximum absolute error',ei,1e-9),observable('terminal current','A','maximum absolute error',ec,1e-9)],
  analytical_acceptance='one-cell ramp RL,old scalar/two-signal block limits,all boundary masks,lossless modal spatial refinement',stopwatch=clock)
 record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)

@pytest.mark.parametrize('n',[3,4])
@pytest.mark.parametrize('zeroR',[False,True])
def test_one_cell_analytic_ideal_short_ramp(n,zeroR):
 rows=[]
 a = fixture(n, cells=1)
 a.update(R=np.zeros((n, n)) if zeroR else np.diag(20 + 3 * np.arange(n)), G=np.diag(0.002 + 0.001 * np.arange(n)), L=np.diag(450 + 20 * np.arange(n)) * 1e-09, source_resistance=np.zeros(n), load_resistance=[0.0] * n)
 out = power(response(**a))
 t = a['time']
 amp = np.array([1.0, -0.4, 0.2, -0.1])[:n]
 Tr = 2e-09
 ind = np.diag(a['L']) * a['length']
 res = np.diag(a['R']) * a['length']
 if zeroR:
     expected = np.where(t[:, None] <= Tr, t[:, None] ** 2 / (2 * Tr), t[:, None] - Tr / 2) * amp / ind
 else:
     tau = ind / res
     it = amp / res * (1 - tau / Tr * (1 - np.exp(-Tr / tau)))
     expected = np.where(t[:, None] <= Tr, amp / res * (t[:, None] / Tr - tau / Tr * -np.expm1(-t[:, None] / tau)), amp / res + (it - amp / res) * np.exp(-(t[:, None] - Tr) / tau))
 slope = np.zeros_like(a['source_voltages'])
 slope[t < Tr] = amp / Tr
 near = expected + (slope @ a['C'].T + a['source_voltages'] @ a['G'].T) * a['length'] * 0.5
 err = float(np.max(abs(out.segment_current[:, 0] - expected)))
 assert err <= 1e-11
 np.testing.assert_allclose(out.current[:, :n], near, rtol=1e-10, atol=1e-12)
 np.testing.assert_allclose(out.current[:, n:], -expected, rtol=1e-10, atol=1e-12)
 rows.append(dict(case='one-cell-analytic-ramp-RL', signals=n, zeroR=zeroR, max_i=err))

@pytest.mark.parametrize('n',[3,4])
def test_all_ideal_resistive_open_short_masks(n):
 rows=[]
 count = 0
 for near in product([0.0, 25.0], repeat=n):
     for far in product([None, 0.0, 100.0], repeat=n):
         a = fixture(n, cells=1, rows=13)
         a.update(source_resistance=near, load_resistance=far)
         power(response(**a))
         count += 1
 rows.append(dict(case='all-boundary-masks', signals=n, cases=count))
 assert count==6**n

@pytest.mark.parametrize('n',[3,4])
@pytest.mark.parametrize('pulse',[False,True])
def test_original_positive_psd_scalar_and_two_signal_limits(n,pulse):
 rows=[]
 a = fixture(n, pulse)
 a.update(R=np.diag(20 + 3 * np.arange(n)), G=np.diag(0.002 + 0.0003 * np.arange(n)), source_resistance=25 + 5 * np.arange(n), load_resistance=80 + 10 * np.arange(n))
 out = power(response(**a))
 ref = multiconductor_rlgc_ladder_response(**a)
 for field in ['node_voltage', 'segment_current', 'voltage', 'current', 'energy', 'energy_rate', 'source_power', 'source_resistor_loss', 'load_resistor_loss']:
     np.testing.assert_allclose(getattr(out, field), getattr(ref, field), rtol=1e-10, atol=1e-12)
 rows.append(dict(case='positive-boundary-original', signals=n, pulse=pulse))
 a = fixture(n, pulse)
 a.update(source_resistance=25 + 5 * np.arange(n), load_resistance=80 + 10 * np.arange(n))
 out = power(response(**a))
 kw = dict(a)
 kw['C_inf'] = kw.pop('C')
 kw.update(delta_C=np.zeros((1, n, n)), relaxation_hz=[80000000.0])
 ref = psd_multiconductor_debye_rlgc_ladder_response(**kw)
 for field in ['node_voltage', 'segment_current', 'voltage', 'current', 'energy', 'energy_rate', 'source_power', 'source_resistor_loss', 'load_resistor_loss']:
     np.testing.assert_allclose(getattr(out, field), getattr(ref, field), rtol=1e-10, atol=1e-12)
 rows.append(dict(case='PSD-zero-Debye-positive-boundary', signals=n, pulse=pulse))
 a = fixture(n, pulse)
 L = np.diag(450 + 20 * np.arange(n)) * 1e-09
 C = np.diag(210 + 10 * np.arange(n)) * 1e-12
 R = np.zeros((n, n))
 G = np.zeros((n, n))
 for lo in range(0, n - 1, 2):
     R[lo:lo + 2, lo:lo + 2] = [[20, -20], [-20, 20]]
     G[lo:lo + 2, lo:lo + 2] = [[0.002, 0.002], [0.002, 0.002]]
     L[lo, lo + 1] = L[lo + 1, lo] = 6e-08
     C[lo, lo + 1] = C[lo + 1, lo] = -2e-11
 a.update(R=R, L=L, G=G, C=C)
 out = power(response(**a))
 v = np.zeros_like(out.node_voltage)
 i = np.zeros_like(out.segment_current)
 ports = np.zeros_like(out.current)
 for lo in range(0, n, 2):
     ix = list(range(lo, min(lo + 2, n)))
     m = len(ix)
     kw = {}
     for key, dummy in [('R', 0.0), ('L', 1e-09), ('G', 0.0), ('C', 1e-12)]:
         x = np.eye(2) * dummy
         x[:m, :m] = a[key][np.ix_(ix, ix)]
         kw[key] = x
     drive = np.zeros((len(a['time']), 2))
     drive[:, :m] = a['source_voltages'][:, ix]
     rs = [25.0, 25.0]
     rl = [100.0, 100.0]
     for j, k in enumerate(ix):
         rs[j] = a['source_resistance'][k]
         rl[j] = a['load_resistance'][k]
     ref = coupled_boundary_ladder_response(a['time'], drive, **kw, length=a['length'], cells=a['cells'], source_resistance=rs, load_resistance=rl)
     v[:, :, ix] = ref.node_voltage[:, :, :m]
     i[:, :, ix] = ref.segment_current[:, :, :m]
     ports[:, ix] = ref.current[:, :m]
     ports[:, np.array(ix) + n] = ref.current[:, 2:2 + m]
 for actual, expected in [(out.node_voltage, v), (out.segment_current, i), (out.current, ports)]:
     np.testing.assert_allclose(actual, expected, rtol=1e-10, atol=1e-12)
 rows.append(dict(case='two-plus-one-or-two-block-reference', signals=n, pulse=pulse, max_v=float(np.max(abs(out.node_voltage - v))), max_i=float(np.max(abs(out.current - ports)))))
 a = fixture(n, pulse)
 a.update(**{key: np.diag(np.diag(a[key])) for key in ['R', 'L', 'G', 'C']})
 out = power(response(**a))
 for j in range(n):
     ref = rlgc_ladder_response(a['time'], a['source_voltages'][:, j], **{key: a[key][j, j] for key in ['R', 'L', 'G', 'C']}, length=a['length'], cells=a['cells'], source_resistance=a['source_resistance'][j], load_resistance=a['load_resistance'][j])
     np.testing.assert_allclose(out.node_voltage[:, :, j], ref.node_voltage, rtol=1e-10, atol=1e-12)
     np.testing.assert_allclose(out.current[:, [j, n + j]], ref.current, rtol=1e-10, atol=1e-12)
 rows.append(dict(case='diagonal-scalar-reference', signals=n, pulse=pulse))

@pytest.mark.parametrize('n',[3,4])
def test_twelve_lossless_modal_boundaries_refine_and_pwl_sampling_is_invariant(n):
 rows=[]
 q = np.eye(n)
 if n == 3:
     q[:2, :2] = np.array([[1.0, 1.0], [1.0, -1.0]]) / np.sqrt(2)
 else:
     q = np.array([[1, 1, 1, 1], [1, -1, 1, -1], [1, 1, -1, -1], [1, -1, -1, 1]]) / 2
 lm = (500.0 + 50 * np.arange(n)) * 1e-09
 cm = (220.0 + 20 * np.arange(n)) * 1e-12
 L = q @ np.diag(lm) @ q.T
 L = (L + L.T) * 0.5
 C = q @ np.diag(cm) @ q.T
 C = (C + C.T) * 0.5
 amp = np.array([1.0, 0.0, 0.3, -0.1])[:n]
 am = amp @ q
 t = np.linspace(0, 1.2e-08, 1201)
 for rs in [0.0, 25.0]:
     for rl in [0.0, None, 100.0]:
         modes = [lossless_line_response(t, source_times=[0.0, 2e-09], source_voltages=[0.0, am[j]], z0_ohm=np.sqrt(lm[j] / cm[j]), delay_s=0.1 * np.sqrt(lm[j] * cm[j]), source_resistance=rs, load_resistance=rl) for j in range(n)]
         v = (np.stack([x.voltage for x in modes], axis=-1) @ q.T).reshape(len(t), 2 * n)
         i = (np.stack([x.current for x in modes], axis=-1) @ q.T).reshape(len(t), 2 * n)
         ev = []
         ei = []
         for cells in [32, 64, 128]:
             a = dict(time=t, source_voltages=np.minimum(t[:, None] / 2e-09, 1.0) * amp, signals=n, R=np.zeros((n, n)), L=L, G=np.zeros((n, n)), C=C, length=0.1, cells=cells, source_resistance=[rs] * n, load_resistance=[rl] * n)
             out = power(response(**a))
             ev.append(float(np.max(abs(out.voltage - v))))
             ei.append(float(np.max(abs(out.current - i))))
         row = dict(signals=n, rs=rs, rl=rl, cells=[32, 64, 128], voltage_error=ev, current_error=ei)
         rows.append(row)
         print(json.dumps(row), flush=True)
         assert ev[-1] <= 0.02 and ei[-1] <= 0.0005
         assert max(ev) < 1e-14 or ev[2] < ev[1] < ev[0]
         assert max(ei) < 1e-14 or ei[2] < ei[1] < ei[0]
 actual = []
 for count in [601, 1201, 2401]:
     a = fixture(n, cells=16, rows=count)
     actual.append(power(response(**a)))
 for out, stride in zip(actual[1:], [2, 4]):
     np.testing.assert_allclose(out.voltage[::stride], actual[0].voltage, rtol=1e-10, atol=1e-12)
     np.testing.assert_allclose(out.current[::stride], actual[0].current, rtol=1e-10, atol=1e-12)
 rows.append(dict(signals=n, case='identical-PWL-common-samples', rows=[601, 1201, 2401]))
