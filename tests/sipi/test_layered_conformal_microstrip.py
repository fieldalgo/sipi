# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Two-substrate normal films retain geometry and independent field contracts."""
from dataclasses import replace
import numpy as np
import pytest
from sipi import templates,CrossSectionDocument
from sipi.constants import epsilon_0
from crosscheck import require_tool
from test_layered_coated_microstrip import GEOMETRY,COARSE,FINE,impedance

NAMES=['layered_conformal_coated_microstrip','coupled_layered_conformal_coated_microstrip',
       'asymmetric_coupled_layered_conformal_coated_microstrip']
BASES=['conformal_coated_microstrip','coupled_conformal_coated_microstrip','asymmetric_coupled_conformal_coated_microstrip']
BARE=['layered_microstrip','coupled_layered_microstrip','asymmetric_coupled_layered_microstrip']
PLANAR=['layered_coated_microstrip','coupled_layered_coated_microstrip','asymmetric_coupled_layered_coated_microstrip']
STACK=dict(lower_height=.3e-3,upper_height=.7e-3,lower_eps_r=3.,upper_eps_r=5.,
           lower_tan_delta=.01,upper_tan_delta=.03,coating_thickness=20e-6,
           coating_eps_r=3.3,coating_tan_delta=.02,air_height=.01,box_width=.02)
def section(i,**changes):return getattr(templates,NAMES[i])(**{**STACK,**GEOMETRY[i],**changes})

@pytest.mark.parametrize('i',range(3),ids=NAMES)
def test_layers_normal_offset_air_and_json_contract(i):
 from shapely.geometry import Point
 s=section(i);metal=max(t.thickness for t in s.traces);film=20e-6
 assert [(l.name,l.thickness,l.eps_r,l.tan_delta) for l in s.layers[:2]]==[('lower',.0003,3.,.01),('upper',.0007,5.,.03)]
 assert s.layers[-1].thickness==metal+film+.01
 assert s.bottom=='ground' and s.top==s.sides=='open'
 assert all(t.y==.001 and not t.ground for t in s.traces)
 region,=s.dielectric_regions;assert (region.name,region.eps_r,region.tan_delta)==('coating',3.3,.02)
 for t in s.traces:
  slope=(t.width-t.top_width)/(2*t.thickness)
  # Independent outward unit normal on the straight right copper side.
  v=np.array([1.,slope])/np.hypot(1,slope)
  p=np.array([t.x+(t.width+t.top_width)/4,t.y+t.thickness/2])+film*v
  assert region._shape.boundary.distance(Point(p))<=5e-15
 assert s.height==pytest.approx(.001+metal+film+.01,rel=1e-15)
 if i:
  assert s.traces[1].x0-s.traces[0].x1==pytest.approx(.3e-3,rel=1e-12)
  assert s.traces[0].x0+s.traces[1].x1==pytest.approx(0,abs=1e-18)
 d=CrossSectionDocument(s,mesh=COARSE);assert CrossSectionDocument.loads(d.dumps()).dumps()==d.dumps()
 small=section(i,air_height=1e-6);assert small.height-region._shape.bounds[3]==pytest.approx(1e-6,rel=1e-10)

@pytest.mark.parametrize('i',range(3),ids=NAMES)
@pytest.mark.parametrize('change',[
 dict(coating_thickness=0),dict(coating_thickness=1e-20),dict(coating_eps_r=.5),
 dict(coating_tan_delta=-.1),dict(lower_height=0),dict(upper_height=float('nan')),
 dict(lower_tan_delta=-.1),dict(upper_eps_r=.5),dict(air_height=0),dict(box_width=.1e-3)])
def test_invalid_layers_film_resolution_and_clipped_copper_reject(i,change):
 with pytest.raises((ValueError,TypeError)):section(i,**change)

@pytest.mark.parametrize('i',range(3),ids=NAMES)
def test_overhang_rejects(i):
 with pytest.raises(ValueError,match='overhang'):
  section(i,**({'left_top_width':.6e-3} if i==2 else {'top_width':.6e-3}))

@pytest.fixture(scope='module',params=range(3),ids=NAMES)
def fields(request):
 i=request.param;m=section(i).mesh(**COARSE)
 return i,m,m.line_parameters(),section(i).analyze(**FINE)


def test_independent_normal_offset_material_and_complex_energy(fields,record_property):
 i,m,line,_=fields;skfem=require_tool('scikit-fem')
 from skfem.helpers import dot,grad
 basis=skfem.Basis(skfem.MeshTri(m.mesh.nodes.T,m.mesh.triangles.T),skfem.ElementTriP1())
 @skfem.BilinearForm(dtype=complex)
 def form(u,v,w):return w.eps*dot(grad(u),grad(v))
 x,y=m.mesh.nodes[m.mesh.triangles].mean(axis=1).T;h=.001;d=20e-6
 film=(y>=h)&(y<=h+d)
 # Straight-side signed-distance inequalities; no production region/material lookup.
 for t in section(i).traces:
  slope=(t.width-t.top_width)/(2*t.thickness)
  film|=(y>=h+d)&(y<=h+t.thickness+d)&(abs(x-t.x)+slope*(y-h)<=t.width/2+d*np.hypot(1,slope))
 eps=np.where(y<.0003,3*(1-.01j),np.where(y<h,5*(1-.03j),np.where(film,3.3*(1-.02j),1.)))
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
 for name,other,gate in [('mesh',coarse,.01),('box',section(i,box_width=.04).analyze(**FINE),.005),('air',section(i,air_height=.02).analyze(**FINE),.005)]:
  delta=max(float(np.max(abs(other.C-fine.C))/np.max(abs(fine.C))),abs(impedance(i,other)/impedance(i,fine)-1))
  changes[name]=delta;assert delta<=gate,(name,delta)
 record_property('relative_changes',str(changes))
 for a in (fine.C,fine.C0,fine.C_loss,fine.L):
  np.testing.assert_allclose(a,a.T,atol=0,rtol=1e-12);assert np.linalg.eigvalsh(a).min()>0
 if i==2:
  with pytest.raises(ValueError):fine.even_odd()


def relative_parameters(i,a,b):
 e={k:float(np.max(abs(getattr(a,k)-getattr(b,k)))/np.max(abs(getattr(b,k)))) for k in ('C','C0','C_loss','L')}
 e['impedance']=abs(impedance(i,a)/impedance(i,b)-1);return e


def test_vacuum_and_uniform_substrate_limits(fields,record_property):
 i,m,_,_=fields
 vac=replace(m,eps_r=np.ones_like(m.eps_r),tan_delta=np.zeros_like(m.tan_delta)).line_parameters()
 np.testing.assert_array_equal(vac.C,vac.C0);np.testing.assert_array_equal(vac.C_loss,np.zeros_like(vac.C))
 a=section(i,lower_eps_r=4.,upper_eps_r=4.,lower_tan_delta=.02,upper_tan_delta=.02).analyze(**FINE)
 b=getattr(templates,BASES[i])(**GEOMETRY[i],substrate_height=.001,eps_r=4.,tan_delta=.02,
     coating_thickness=20e-6,coating_eps_r=3.3,coating_tan_delta=.02,air_height=.01,box_width=.02).analyze(**FINE)
 errors=relative_parameters(i,a,b);record_property('uniform_limit_changes',str(errors));assert max(errors.values())<=.005


def test_air_film_limit_uses_same_total_air_height(fields,record_property):
 i,_,_,_=fields
 a=section(i,coating_eps_r=1.,coating_tan_delta=0.).analyze(**FINE)
 params={k:v for k,v in STACK.items() if not k.startswith('coating_')}
 params['air_height']+=20e-6+max(t.thickness for t in section(i).traces)
 b=getattr(templates,BARE[i])(**GEOMETRY[i],**params).analyze(**FINE)
 errors=relative_parameters(i,a,b);record_property('air_limit_changes',str(errors));assert max(errors.values())<=.005


def test_zero_metal_limit_is_planar_film(fields,record_property):
 i,_,_,_=fields;geometry={**GEOMETRY[i]}
 for k in list(geometry):
  if 'thickness' in k:geometry[k]=0.
  if 'top_width' in k:geometry[k]=None
 a=section(i,**geometry).analyze(**FINE)
 params={k:v for k,v in STACK.items() if k!='coating_thickness'};params['coating_height']=20e-6
 b=getattr(templates,PLANAR[i])(**geometry,**params).analyze(**FINE)
 errors=relative_parameters(i,a,b);record_property('planar_limit_changes',str(errors));assert max(errors.values())<=.005
