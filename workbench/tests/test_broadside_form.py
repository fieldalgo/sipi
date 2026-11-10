"""Broadside forms preserve signed offset, vertical gap and physical gates."""
from pathlib import Path
import json,sys
import numpy as np
import pytest
import sipi
from sipi.templates import broadside_stripline
from sipi.template_document import TemplateSectionDocument
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'desktop'))
from engine import execute
from broadside_cases import NAME,COARSE,parameters

@pytest.mark.parametrize('offset',[-.0001,0,.0001])
def test_signed_offset_vertical_gap_and_exact_saved_geometry(offset,monkeypatch):
 monkeypatch.setattr(sipi.CrossSection,'mesh',lambda *a,**kw:pytest.fail('Document operation solved'))
 p=parameters(offset=offset);out=execute(dict(action='template-document',template=NAME,parameters=p,mesh=COARSE))
 assert execute(dict(action='template-open',text=out['document_text']))==out
 assert out['parameters']==TemplateSectionDocument(NAME,p,mesh=COARSE).parameters
 lower,upper=out['document']['traces'];assert [lower['name'],upper['name']]==['positive','negative']
 assert lower['x']==-offset/2 and upper['x']==offset/2
 assert lower['y']==p['plane_spacing']/2-p['gap']/2-p['thickness'] and upper['y']==p['plane_spacing']/2+p['gap']/2
 assert upper['y']-lower['y']-lower['thickness']==pytest.approx(p['gap'],abs=1e-18)
 assert all(t['width']==p['width'] and t['thickness']==p['thickness'] for t in [lower,upper])
 assert out['document']['box']==dict(width=.006,bottom='ground',top='ground',sides='open')
 assert len(out['document']['layers'])==1 and out['document']['layers'][0]['thickness']==.001

@pytest.mark.parametrize('change',[dict(thickness=0),dict(thickness=-1),dict(gap=0),dict(gap=.001),dict(plane_spacing=.0001),dict(offset=True),dict(offset=float('nan')),dict(offset=.02),dict(top_width=.0002)])
def test_invalid_broadside_geometry_rejected_before_mesh(change,monkeypatch):
 monkeypatch.setattr(sipi.CrossSection,'mesh',lambda *a,**kw:pytest.fail('Invalid geometry solved'))
 with pytest.raises((ValueError,TypeError)):execute(dict(action='analyze',template=NAME,parameters=parameters(**change)))

@pytest.mark.parametrize('mode',['sweep','corners','monte_carlo'])
def test_offset_and_vertical_gap_studies_preserve_centres_and_fixed_mesh(mode):
 variables=[dict(parameter='offset',lower=-.00012,upper=.00012)]
 if mode!='sweep':variables.append(dict(parameter='gap',lower=.00018,upper=.00022))
 out=execute(dict(action='study',template=NAME,parameters=parameters(),mesh=COARSE,study=dict(mode=mode,variables=variables,points=2,seed=42)))['study']
 assert out['status']=='complete' and out['failed']==0 and out['quantity']=='z_diff'
 assert len(out['rows'])==(4 if mode=='corners' else 2)
 for row in out['rows']:
  expected=TemplateSectionDocument(NAME,parameters(**row['parameters']),mesh=COARSE).cross_section.to_dict();assert row['document']==expected
  assert row['impedance']==row['line']['z_diff']
  lo,hi=row['document']['traces'];assert lo['x']==-row['parameters']['offset']/2 and hi['x']==row['parameters']['offset']/2


def test_invalid_vertical_gap_corner_is_not_silently_discarded(monkeypatch):
 monkeypatch.setattr(sipi.CrossSection,'mesh',lambda *a,**kw:pytest.fail('Invalid study solved'))
 with pytest.raises(ValueError):execute(dict(action='study',template=NAME,parameters=parameters(),mesh=COARSE,study=dict(mode='corners',variables=[dict(parameter='offset',lower=-.0001,upper=.0001),dict(parameter='gap',lower=.0002,upper=.001)],points=2,seed=42)))


def test_vacuum_broadside_network_reciprocity_and_power():
 out=execute(dict(action='network',template=NAME,parameters=parameters(eps_r=1,tan_delta=0),mesh=COARSE,network=dict(start_hz=1e6,stop_hz=1e9,points=3,length=.1,resistance=0,z_ref=50)))
 line,n=out['line'],out['network'];np.testing.assert_allclose(line['C'],line['C0'],rtol=2e-12,atol=1e-23)
 np.testing.assert_allclose(np.array(line['L'])@line['C']*299792458.**2,np.eye(2),rtol=2e-12,atol=2e-12)
 s=np.array(n['real'])+1j*np.array(n['imag']);np.testing.assert_allclose(s,s.transpose(0,2,1),rtol=0,atol=2e-12)
 for value in s:np.testing.assert_allclose(value.conj().T@value,np.eye(4),rtol=0,atol=2e-12)


def test_broadside_signed_offset_independent_energy_mesh_and_outer():
 from crosscheck import require_tool,Stopwatch,observable,make_record,emit
 from sipi.constants import epsilon_0,mu_0
 skfem=require_tool('scikit-fem');from skfem.helpers import dot,grad
 p=parameters();section=broadside_stripline(**p);m=section.mesh(**COARSE);clock=Stopwatch()
 with clock('openphysics'):line=m.line_parameters()
 with clock('reference'):
  basis=skfem.Basis(skfem.MeshTri(m.mesh.nodes.T,m.mesh.triangles.T),skfem.ElementTriP1())
  @skfem.BilinearForm(dtype=complex)
  def form(u,v,w):return w.eps*dot(grad(u),grad(v))
  fixed=np.unique(np.concatenate([m.ground,*m.signals.values()]));expected=[]
  for eps in [m.eps_r*(1-1j*m.tan_delta),np.ones_like(m.eps_r)]:
   k=skfem.asm(form,basis,eps=eps[:,None]);solutions=[]
   for nodes in m.signals.values():
    v=np.zeros(basis.N,complex);v[nodes]=1;solutions.append(skfem.solve(*skfem.condense(k,np.zeros(basis.N,complex),x=v,D=fixed)))
   u=np.array(solutions).T;expected.append(epsilon_0*(u.T@(k@u)))
 c,c0=expected[0].real,expected[1].real;errors=[float(np.max(abs(a-b))/np.max(abs(b))) for a,b in [(line.C,c),(line.C0,c0),(line.C_loss,-expected[0].imag),(line.L,epsilon_0*mu_0*np.linalg.inv(c0))]];assert max(errors)<1e-10
 fine={**COARSE,'edge_size':COARSE['edge_size']/2,'far_size':COARSE['far_size']/2,'grade':COARSE['grade']/2}
 z=line.even_odd()['z_diff'];refined=section.analyze(**fine).even_odd()['z_diff'];outer=broadside_stripline(**{**p,'box_width':.012}).analyze(**COARSE).even_odd()['z_diff'];mirror=broadside_stripline(**{**p,'offset':-p['offset']}).analyze(**COARSE).even_odd()['z_diff']
 assert abs(refined/z-1)<.015 and abs(outer/z-1)<.005 and abs(mirror/z-1)<.005
 np.testing.assert_allclose(line.C/line.C0,4,rtol=1e-9)
 record=make_record(case='broadside-form-signed-offset',physics='lossy homogeneous electrostatics',api='sipi.templates.broadside_stripline',discretization='P1 finite rectangular vertical pair with signed horizontal offset',tool='scikit-fem',tool_discretization='independent complex/vacuum P1 Dirichlet field energy',matched=['exact geometry, mesh, boundary, complex dielectric and conductor order'],not_matched=['no measured manufacturing data or three-dimensional transition'],observables=[observable(name,unit,'relative difference',error,1e-10) for name,unit,error in zip(['C','C0','C_loss','L'],['F/m','F/m','F/m','H/m'],errors)],analytical_acceptance='homogeneous C/C0=4; separate fine1.5percent,outer0.5percent,offset-reflection0.5percent',stopwatch=clock)
 emit(record)

@pytest.mark.parametrize('explicit',[False,True])
def test_goal_policy_and_original_failure_are_preserved(explicit,monkeypatch):
 p=parameters();mesh=dict(COARSE) if explicit else broadside_stripline(**p).mesh_settings()
 if not explicit:mesh['edge_size']/=4;mesh['far_size']/=4;mesh['grade']/=2
 failure=ValueError('original target failure')
 def seek(factory,bounds,target,**kw):
  assert kw==dict(tolerance=.5,quantity='z_diff',mesh=mesh,max_evaluations=32,return_line=True)
  lo,hi=factory(.0002).traces;assert hi.x-lo.x==p['offset']
  raise failure
 monkeypatch.setattr(sipi,'seek_impedance',seek)
 with pytest.raises(ValueError) as caught:execute(dict(action='design',template=NAME,parameters=p,**({'mesh':COARSE} if explicit else {}),design=dict(bounds=[.05*1e-3,.65*1e-3],target=100,tolerance=.5)))
 assert caught.value is failure


def test_width_target_preserves_vertical_geometry_and_requested_line():
 p=parameters(width=.0003,gap=.0002,offset=.0001)
 out=execute(dict(action='design',template=NAME,parameters=p,design=dict(bounds=[.05*1e-3,.65*1e-3],target=100,tolerance=.5)))
 d=out['design'];assert .05*1e-3<=d['width']<=.65*1e-3 and abs(d['residual'])<=.5 and abs(d['refined_residual'])<=.5
 assert len(d['history'])<=32 and d['history'][-1]['stage']=='refinement' and 'search_tolerance' not in d
 lo,hi=out['document']['traces'];assert lo['x']==-p['offset']/2 and hi['x']==p['offset']/2
 assert lo['width']==hi['width']==d['width'] and lo['thickness']==hi['thickness']==p['thickness']
 assert lo['y']==p['plane_spacing']/2-p['gap']/2-p['thickness'] and hi['y']==p['plane_spacing']/2+p['gap']/2
 assert out['line']['z_diff']==d['impedance']
 chosen=next(row for row in d['history'] if row['stage']=='search' and row['parameter']==d['width']);assert chosen['impedance']==d['impedance']
