# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Unequal surface pair over two substrates: independent fields and limits."""
from dataclasses import replace
import numpy as np
import pytest
from sipi import (asymmetric_coupled_layered_microstrip, asymmetric_coupled_microstrip,
                  coupled_layered_microstrip, CrossSectionDocument, seek_impedance)
from sipi.constants import epsilon_0
from crosscheck import require_tool

P=dict(left_width=.4e-3,right_width=.7e-3,gap=.3e-3,lower_height=.3e-3,
       upper_height=.7e-3,lower_eps_r=3.,upper_eps_r=5.,lower_tan_delta=.01,
       upper_tan_delta=.03,left_thickness=25e-6,right_thickness=45e-6,
       left_top_width=.32e-3,right_top_width=.55e-3,box_width=.02,air_height=.01)
COARSE=dict(edge_size=5e-6,far_size=.25e-3,grade=.2)
FINE=dict(edge_size=2.5e-6,far_size=.125e-3,grade=.1)

def section(**changes):return asymmetric_coupled_layered_microstrip(**{**P,**changes})

@pytest.mark.parametrize('left,right',[(0.,0.),(25e-6,45e-6),(45e-6,25e-6)])
def test_separate_copper_dimensions_and_substrate_geometry(left,right):
 s=section(left_thickness=left,right_thickness=right,left_top_width=None,right_top_width=None)
 assert [t.name for t in s.traces]==['positive','negative']
 assert [t.y for t in s.traces]==[.001,.001]
 assert [t.thickness for t in s.traces]==[left,right]
 assert s.traces[1].x0-s.traces[0].x1==pytest.approx(.3e-3,rel=1e-12)
 assert s.traces[0].x0==-s.traces[1].x1
 assert [(x.eps_r,x.tan_delta) for x in s.layers]==[(3.,.01),(5.,.03),(1.,0.)]
 assert s.bottom=='ground' and s.top==s.sides=='open'
 d=CrossSectionDocument(s,mesh=COARSE);assert CrossSectionDocument.loads(d.dumps()).dumps()==d.dumps()

@pytest.mark.parametrize('changes',[dict(left_width=0),dict(right_width=-1),dict(gap=0),
 dict(lower_height=0),dict(upper_height=float('inf')),dict(lower_eps_r=.5),dict(upper_tan_delta=-1),
 dict(left_thickness=-1),dict(right_thickness=True),dict(left_thickness=0),dict(right_top_width=0),
 dict(air_height=30e-6),dict(box_width=.001)])
def test_invalid_materials_clipping_and_tapers(changes):
 with pytest.raises((ValueError,TypeError)):section(**changes)

@pytest.fixture(scope='module')
def fields():
 m=section().mesh(**COARSE);return m,m.line_parameters(),section().analyze(**FINE)

def test_independent_complex_energy_and_vacuum_assignment(fields,record_property):
 m,actual,_=fields;skfem=require_tool('scikit-fem')
 from skfem.helpers import dot,grad
 basis=skfem.Basis(skfem.MeshTri(m.mesh.nodes.T,m.mesh.triangles.T),skfem.ElementTriP1())
 @skfem.BilinearForm(dtype=complex)
 def form(u,v,w):return w.eps*dot(grad(u),grad(v))
 y=m.mesh.nodes[m.mesh.triangles,1].mean(axis=1)
 eps=np.where(y<.3e-3,3*(1-.01j),np.where(y<1e-3,5*(1-.03j),1.))
 fixed=np.unique(np.concatenate([m.ground,*m.signals.values()]));expected=[]
 for coeff in (eps,np.ones_like(eps)):
  k=skfem.asm(form,basis,eps=coeff[:,None]);columns=[]
  for nodes in m.signals.values():
   v=np.zeros(basis.N,complex);v[nodes]=1
   columns.append(skfem.solve(*skfem.condense(k,np.zeros(basis.N,complex),x=v,D=fixed)))
  u=np.array(columns).T;expected.append(epsilon_0*(u.T@(k@u)))
 errors=[]
 for a,b in [(actual.C,expected[0].real),(actual.C_loss,-expected[0].imag),(actual.C0,expected[1].real)]:
  error=float(np.max(abs(a-b))/np.max(abs(b)));errors.append(error);assert error<=1e-10
 record_property('independent_normalized_errors',str(errors))

def test_separate_mesh_width_and_air_gates(fields,record_property):
 _,coarse,fine=fields;changes={}
 for name,other,gate in [('mesh',coarse,.01),('box',section(box_width=.04).analyze(**FINE),.005),('air',section(air_height=.02).analyze(**FINE),.005)]:
  delta=max(float(np.max(abs(other.C-fine.C))/np.max(abs(fine.C))),abs(other.z_diff_forward/fine.z_diff_forward-1))
  changes[name]=delta;assert delta<=gate,(name,delta)
 record_property('relative_changes',str(changes))
 for a in (fine.C,fine.C0,fine.C_loss,fine.L):
  np.testing.assert_allclose(a,a.T,rtol=1e-12,atol=0);assert np.linalg.eigvalsh(a).min()>0
 with pytest.raises(ValueError):fine.even_odd()

def test_vacuum_and_uniform_substrate_limits(fields):
 m,_,_=fields
 vacuum=replace(m,eps_r=np.ones_like(m.eps_r),tan_delta=np.zeros_like(m.tan_delta)).line_parameters()
 np.testing.assert_array_equal(vacuum.C,vacuum.C0);np.testing.assert_array_equal(vacuum.C_loss,np.zeros_like(vacuum.C))
 layered=section(lower_eps_r=4.,upper_eps_r=4.,lower_tan_delta=.02,upper_tan_delta=.02).analyze(**FINE)
 p={k:v for k,v in P.items() if not k.startswith(('lower_','upper_'))}
 single=asymmetric_coupled_microstrip(**p,substrate_height=.001,eps_r=4.,tan_delta=.02).analyze(**FINE)
 for key in ('C','C0','C_loss','L'):
  a,b=getattr(layered,key),getattr(single,key);assert np.max(abs(a-b))/np.max(abs(b))<=.005
 assert abs(layered.z_diff_forward/single.z_diff_forward-1)<=.005

def test_equal_pair_reduces_to_symmetric_surface_geometry():
 p={k:v for k,v in P.items() if not k.startswith(('left_','right_'))}
 a=asymmetric_coupled_layered_microstrip(**p,left_width=.5e-3,right_width=.5e-3,left_thickness=35e-6,right_thickness=35e-6)
 b=coupled_layered_microstrip(**p,width=.5e-3,thickness=35e-6)
 assert CrossSectionDocument(a,mesh=COARSE).dumps()==CrossSectionDocument(b,mesh=COARSE).dumps()


def test_direct_left_width_goal_preserves_right_signal_and_substrates():
 result=seek_impedance(lambda width:section(left_width=width),(.35e-3,1.4e-3),100.,
                       quantity='z_diff_forward',mesh=COARSE,tolerance=.5,search_tolerance=.25)
 assert abs(result.residual)<=.5 and abs(result.refined_residual)<=.5
 assert result.history[-1].stage=='refinement'
 s=result.document.section
 assert s.traces[0].width==result.parameter and s.traces[1].width==P['right_width']
 assert [t.thickness for t in s.traces]==[25e-6,45e-6]
 assert [(l.eps_r,l.thickness) for l in s.layers[:2]]==[(3.,.3e-3),(5.,.7e-3)]
