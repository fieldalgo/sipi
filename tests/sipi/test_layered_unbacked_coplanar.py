# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Unbacked coplanar conductors above two independently specified substrates."""
from dataclasses import replace
import numpy as np
import pytest
from sipi import templates,CrossSectionDocument
from sipi.constants import epsilon_0
from crosscheck import require_tool

NAMES=['layered_unbacked_coplanar','coupled_layered_unbacked_coplanar','asymmetric_coupled_layered_unbacked_coplanar']
BASES=['unbacked_coplanar','coupled_unbacked_coplanar','asymmetric_coupled_unbacked_coplanar']
STACK=dict(lower_height=.3e-3,upper_height=.7e-3,lower_eps_r=3.,upper_eps_r=5.,lower_tan_delta=.01,upper_tan_delta=.03,air_height=.01,lower_air_height=.01,box_width=.02)
GEOMETRY=[dict(width=.5e-3,gap=.2e-3,ground_width=1e-3,thickness=35e-6,top_width=.4e-3),
 dict(width=.5e-3,gap=.3e-3,ground_gap=.2e-3,ground_width=1e-3,thickness=35e-6,top_width=.4e-3),
 dict(left_width=.4e-3,right_width=.7e-3,gap=.3e-3,ground_gap=.2e-3,ground_width=1e-3,
      left_thickness=25e-6,right_thickness=45e-6,ground_thickness=35e-6,left_top_width=.32e-3,right_top_width=.55e-3)]
COARSE=dict(edge_size=5e-6,far_size=.25e-3,grade=.2)
FINE=dict(edge_size=2.5e-6,far_size=.125e-3,grade=.1)

def section(i,**changes):return getattr(templates,NAMES[i])(**{**STACK,**GEOMETRY[i],**changes})
def impedance(i,line):return line.z0 if i==0 else line.even_odd()['z_diff'] if i==1 else line.z_diff_forward

@pytest.mark.parametrize('i',range(3),ids=NAMES)
def test_explicit_substrates_signal_and_ground_dimensions(i):
 s=section(i);signals=[t for t in s.traces if not t.ground];grounds=[t for t in s.traces if t.ground]
 assert len(signals)==(1 if i==0 else 2) and len(grounds)==2
 assert all(t.y==.011 for t in s.traces)
 assert all(t.width==1e-3 and t.thickness==35e-6 and t.top_width is None for t in grounds)
 assert [(l.name,l.eps_r,l.tan_delta) for l in s.layers]==[('lower_air',1.,0.),('lower',3.,.01),('upper',5.,.03),('air',1.,0.)]
 assert s.bottom=='open' and s.top==s.sides=='open'
 left=min(signals,key=lambda t:t.x0);right=max(signals,key=lambda t:t.x1)
 assert left.x0-max(t.x1 for t in grounds if t.x<0)==pytest.approx(.2e-3,rel=1e-12)
 assert min(t.x0 for t in grounds if t.x>0)-right.x1==pytest.approx(.2e-3,rel=1e-12)
 if i:assert right.x0-left.x1==pytest.approx(.3e-3,rel=1e-12)
 d=CrossSectionDocument(s,mesh=COARSE);assert CrossSectionDocument.loads(d.dumps()).dumps()==d.dumps()

@pytest.mark.parametrize('i',range(3),ids=NAMES)
@pytest.mark.parametrize('change',[dict(lower_air_height=0),dict(lower_air_height=float('nan')),dict(lower_height=0),dict(upper_eps_r=.5),dict(ground_width=0),dict(air_height=1e-6),dict(box_width=.1e-3)])
def test_invalid_layers_and_clipped_copper_reject(i,change):
 with pytest.raises((ValueError,TypeError)):section(i,**change)

@pytest.fixture(scope='module',params=range(3),ids=NAMES)
def fields(request):
 i=request.param;m=section(i).mesh(**COARSE)
 return i,m,m.line_parameters(),section(i).analyze(**FINE)


def test_independent_complex_and_vacuum_energy(fields,record_property):
 i,m,line,_=fields;skfem=require_tool('scikit-fem')
 from skfem.helpers import dot,grad
 basis=skfem.Basis(skfem.MeshTri(m.mesh.nodes.T,m.mesh.triangles.T),skfem.ElementTriP1())
 @skfem.BilinearForm(dtype=complex)
 def form(u,v,w):return w.eps*dot(grad(u),grad(v))
 y=m.mesh.nodes[m.mesh.triangles,1].mean(axis=1)
 eps=np.where(y<.01,1.,np.where(y<.0103,3*(1-.01j),np.where(y<.011,5*(1-.03j),1.)))
 fixed=np.unique(np.concatenate([m.ground,*m.signals.values()]));expected=[]
 for coeff in (eps,np.ones_like(eps)):
  k=skfem.asm(form,basis,eps=coeff[:,None]);columns=[]
  for nodes in m.signals.values():
   v=np.zeros(basis.N,complex);v[nodes]=1
   columns.append(skfem.solve(*skfem.condense(k,np.zeros(basis.N,complex),x=v,D=fixed)))
  u=np.array(columns).T;expected.append(epsilon_0*(u.T@(k@u)))
 errors=[float(np.max(abs(a-b))/np.max(abs(b))) for a,b in [(line.C,expected[0].real),(line.C_loss,-expected[0].imag),(line.C0,expected[1].real)]]
 record_property('independent_normalized_errors',str(errors));assert max(errors)<=1e-10


def test_separate_mesh_box_and_air_gates(fields,record_property):
 i,_,coarse,fine=fields;changes={}
 for name,other,gate in [('mesh',coarse,.01),('box',section(i,box_width=.04).analyze(**FINE),.005),('air',section(i,air_height=.02).analyze(**FINE),.005),('lower_air',section(i,lower_air_height=.02).analyze(**FINE),.005)]:
  delta=max(float(np.max(abs(other.C-fine.C))/np.max(abs(fine.C))),abs(impedance(i,other)/impedance(i,fine)-1))
  changes[name]=delta;assert delta<=gate,(name,delta)
 record_property('relative_changes',str(changes))
 for a in (fine.C,fine.C0,fine.C_loss,fine.L):
  np.testing.assert_allclose(a,a.T,atol=0,rtol=1e-12);assert np.linalg.eigvalsh(a).min()>0
 if i==2:
  with pytest.raises(ValueError):fine.even_odd()


def test_vacuum_and_uniform_substrate_limits(fields):
 i,m,_,_=fields
 vac=replace(m,eps_r=np.ones_like(m.eps_r),tan_delta=np.zeros_like(m.tan_delta)).line_parameters()
 np.testing.assert_array_equal(vac.C,vac.C0);np.testing.assert_array_equal(vac.C_loss,np.zeros_like(vac.C))
 a=section(i,lower_eps_r=4.,upper_eps_r=4.,lower_tan_delta=.02,upper_tan_delta=.02).analyze(**FINE)
 b=getattr(templates,BASES[i])(**GEOMETRY[i],substrate_height=.001,eps_r=4.,tan_delta=.02,air_height=.01,lower_air_height=.01,box_width=.02).analyze(**FINE)
 for k in ('C','C0','C_loss','L'):
  x,y=getattr(a,k),getattr(b,k);assert np.max(abs(x-y))/np.max(abs(y))<=.005
 assert abs(impedance(i,a)/impedance(i,b)-1)<=.005


@pytest.mark.parametrize('i',range(3),ids=NAMES)
def test_default_lower_air_uses_both_substrates_and_translates_all_copper(i):
 a=section(i,lower_air_height=None);b=section(i,lower_air_height=.02)
 assert a.layers[0].thickness==.01 and b.layers[0].thickness==.02
 assert a.layers[1:]==b.layers[1:]
 for t,u in zip(a.traces,b.traces):
  assert u.y-t.y==pytest.approx(.01,rel=1e-12)
  assert (u.x,u.width,u.thickness,u.ground)==(t.x,t.width,t.thickness,t.ground)
