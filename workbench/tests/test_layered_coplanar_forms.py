"""Two-layer forms preserve the interface, distinct materials and physical limits."""
from pathlib import Path
import sys
import numpy as np
import pytest
import sipi
from sipi.template_document import TemplateSectionDocument
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'desktop'))
from engine import execute,TEMPLATES
from layered_coplanar_cases import NAMES,COARSE,parameters

@pytest.mark.parametrize('name',NAMES)
@pytest.mark.parametrize('thickness',[0,.000035])
def test_interface_and_independent_materials_roundtrip_without_meshing(name,thickness,monkeypatch):
 monkeypatch.setattr(sipi.CrossSection,'mesh',lambda *a,**kw:pytest.fail('Saving solved fields'))
 p=parameters(name,thickness=thickness,top_width=None if thickness==0 else .00025)
 out=execute(dict(action='template-document',template=name,parameters=p,mesh=COARSE))
 assert out['document_text']==TemplateSectionDocument(name,p,mesh=COARSE).dumps()
 assert execute(dict(action='template-open',text=out['document_text']))==out
 d=out['document'];assert [x['thickness'] for x in d['layers']]==[p['lower_height'],p['upper_height']]
 assert [x['eps_r'] for x in d['layers']]==[3.8,4.5]
 assert [x['tan_delta'] for x in d['layers']]==[.01,.02]
 assert all(t['y']==p['lower_height'] and t['thickness']==thickness for t in d['traces'])
 assert all(t['y']+thickness<p['lower_height']+p['upper_height'] for t in d['traces'])
 assert len(d['traces'])==(4 if name==NAMES[1] else 3)
 assert [t['ground'] for t in d['traces']]==([False,False,True,True] if name==NAMES[1] else [False,True,True])
 assert all(t.get('top_width', t['width']) == t['width'] for t in d['traces'] if t['ground'])
 assert all(t['width']==p['ground_width'] for t in d['traces'] if t['ground'])
 assert d['box']==dict(width=.012,bottom='ground',top='ground',sides='open')

@pytest.mark.parametrize('name',NAMES)
@pytest.mark.parametrize('change',[dict(gap=0),dict(ground_width=0),dict(box_width=.001),dict(lower_height=0),dict(upper_height=.00002),dict(lower_eps_r=.5),dict(upper_eps_r=True),dict(lower_tan_delta=-1),dict(upper_tan_delta=float('nan'))])
def test_invalid_interface_or_material_rejected_before_mesh(name,change,monkeypatch):
 monkeypatch.setattr(sipi.CrossSection,'mesh',lambda *a,**kw:pytest.fail('Invalid input solved fields'))
 with pytest.raises((ValueError,TypeError)):execute(dict(action='analyze',template=name,parameters=parameters(name,**change)))

@pytest.mark.parametrize('name',NAMES)
@pytest.mark.parametrize('mode',['sweep','corners','monte_carlo'])
def test_layer_height_and_permittivity_samples_keep_interface_and_nominal_mesh(name,mode):
 variables=[dict(parameter='upper_eps_r',lower=4.2,upper=4.8)]
 if mode!='sweep':variables.append(dict(parameter='lower_height',lower=.00038,upper=.00042))
 out=execute(dict(action='study',template=name,parameters=parameters(name),mesh=COARSE,study=dict(mode=mode,variables=variables,points=2,seed=42)))['study']
 assert out['status']=='complete' and out['failed']==0 and out['quantity']==('z_diff' if name==NAMES[1] else 'z0')
 assert len(out['rows'])==(4 if mode=='corners' else 2)
 for row in out['rows']:
  p=parameters(name,**row['parameters']);assert row['document']==TemplateSectionDocument(name,p,mesh=COARSE).cross_section.to_dict()
  assert row['impedance']==row['line'][out['quantity']]
  assert all(t['y']==p['lower_height'] for t in row['document']['traces'])

@pytest.mark.parametrize('name',NAMES)
def test_invalid_upper_clearance_bounds_are_not_resampled(name,monkeypatch):
 monkeypatch.setattr(sipi.CrossSection,'mesh',lambda *a,**kw:pytest.fail('Invalid bounds solved fields'))
 with pytest.raises(ValueError):execute(dict(action='study',template=name,parameters=parameters(name),mesh=COARSE,study=dict(mode='corners',variables=[dict(parameter='upper_height',lower=.00002,upper=.0006)],points=2,seed=42)))

@pytest.mark.parametrize('name',NAMES)
def test_independent_complex_energy_and_separate_mesh_outer_checks(name):
 from crosscheck import require_tool,Stopwatch,observable,make_record,emit
 from sipi.constants import epsilon_0,mu_0
 skfem=require_tool('scikit-fem');from skfem.helpers import dot,grad
 p=parameters(name);section=TEMPLATES[name](**p);m=section.mesh(**COARSE);clock=Stopwatch()
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
 c,c0=expected[0].real,expected[1].real
 errors=[float(np.max(abs(a-b))/np.max(abs(b))) for a,b in [(line.C,c),(line.C0,c0),(line.C_loss,-expected[0].imag),(line.L,epsilon_0*mu_0*np.linalg.inv(c0))]];assert max(errors)<1e-10
 def z(v):return v.even_odd()['z_diff'] if name==NAMES[1] else v.z0
 fine={**COARSE,'edge_size':COARSE['edge_size']/2,'far_size':COARSE['far_size']/2,'grade':COARSE['grade']/2}
 refined=section.analyze(**fine);outer=TEMPLATES[name](**{**p,'box_width':.024}).analyze(**COARSE)
 assert abs(z(refined)/z(line)-1)<.015 and abs(z(outer)/z(line)-1)<.005
 for value in [line,refined,outer]:
  assert np.linalg.eigvalsh(value.C).min()>0 and np.linalg.eigvalsh(value.C_loss).min()>0
  np.testing.assert_allclose(value.C,value.C.T,rtol=1e-12)
 record=make_record(case=name+'-form-interface',physics='two-layer lossy electrostatics',api='sipi.'+name,discretization='P1 finite copper at explicit interface',tool='scikit-fem',tool_discretization='independent complex/vacuum P1 Dirichlet energy',matched=['geometry, mesh, boundary, separate complex materials, conductor order'],not_matched=['no manufacturing measurements or 3D transition'],observables=[observable(n,u,'relative difference',e,1e-10) for n,u,e in zip(['C','C0','C_loss','L'],['F/m','F/m','F/m','H/m'],errors)],analytical_acceptance='positive reciprocal energy; separate fine1.5percent and box0.5percent',stopwatch=clock)
 emit(record)

@pytest.mark.parametrize('name',NAMES)
def test_vacuum_four_or_two_port_power_and_reciprocity(name):
 p=parameters(name,lower_eps_r=1,upper_eps_r=1,lower_tan_delta=0,upper_tan_delta=0)
 out=execute(dict(action='network',template=name,parameters=p,mesh=COARSE,network=dict(start_hz=1e6,stop_hz=1e9,points=3,length=.1,resistance=0,z_ref=50)))
 line,n=out['line'],out['network'];np.testing.assert_allclose(line['C'],line['C0'],rtol=2e-12,atol=1e-23)
 s=np.array(n['real'])+1j*np.array(n['imag']);np.testing.assert_allclose(s,s.transpose(0,2,1),rtol=0,atol=2e-12)
 for value in s:np.testing.assert_allclose(value.conj().T@value,np.eye(len(value)),rtol=0,atol=2e-12)

@pytest.mark.parametrize('name',NAMES)
@pytest.mark.parametrize('explicit',[False,True])
def test_buried_coplanar_width_policy_and_original_error_preserved(name,explicit,monkeypatch):
 p=parameters(name);mesh=dict(COARSE) if explicit else TEMPLATES[name](**p).mesh_settings()
 if not explicit:mesh['edge_size']/=2;mesh['far_size']/=4
 failure=ValueError('original target failure')
 def seek(factory,bounds,target,**kw):
  assert kw==dict(tolerance=.5,quantity='z_diff' if name==NAMES[1] else 'z0',mesh=mesh,max_evaluations=32,return_line=True,search_tolerance=.25)
  section=factory(.0002);assert all(t.y==p['lower_height'] for t in section.traces);assert [x.eps_r for x in section.layers]==[3.8,4.5];raise failure
 monkeypatch.setattr(sipi,'seek_impedance',seek)
 with pytest.raises(ValueError) as caught:execute(dict(action='design',template=name,parameters=p,**({'mesh':COARSE} if explicit else {}),design=dict(bounds=[.05e-3,1.5e-3],target=100 if name==NAMES[1] else 50,tolerance=.5)))
 assert caught.value is failure


@pytest.mark.parametrize('name,variable',[(n,v) for n in NAMES for v in ['gap','ground_width','ground_gap'] if v!='ground_gap' or n==NAMES[1]])
def test_ground_clearance_studies_keep_separate_finite_grounds(name,variable):
 p=parameters(name);value=p[variable]
 out=execute(dict(action='study',template=name,parameters=p,mesh=COARSE,study=dict(mode='sweep',variables=[dict(parameter=variable,lower=value*.9,upper=value*1.1)],points=2,seed=42)))['study']
 assert out['failed']==0 and len(out['rows'])==2
 for row in out['rows']:
  changed={**p,**row['parameters']};doc=TemplateSectionDocument(name,changed,mesh=COARSE).cross_section.to_dict();assert row['document']==doc
  signals=[t for t in doc['traces'] if not t['ground']];grounds=[t for t in doc['traces'] if t['ground']]
  assert len(grounds)==2 and all(t['width']==changed['ground_width'] for t in grounds)
  clearance=grounds[1]['x']-grounds[1]['width']/2-(signals[-1]['x']+signals[-1]['width']/2)
  assert clearance==pytest.approx(changed['ground_gap' if name==NAMES[1] else 'gap'],rel=1e-12)
  assert len(signals)==(2 if name==NAMES[1] else 1)

@pytest.mark.parametrize('name',NAMES)
def test_physical_width_target_keeps_interface_and_finite_side_grounds(name):
 p=dict(width=.0003,gap=.0002,ground_width=.001,lower_height=.0004,upper_height=.0006,lower_eps_r=3.8,upper_eps_r=4.5,thickness=.000035,lower_tan_delta=.01,upper_tan_delta=.02,box_width=.012)
 if name==NAMES[1]:p['ground_gap']=.0002
 out=execute(dict(action='design',template=name,parameters=p,design=dict(bounds=[.05*1e-3,.65*1e-3],target=100 if name==NAMES[1] else 50,tolerance=.5)))
 d=out['design'];assert .05*1e-3<=d['width']<=.65*1e-3 and abs(d['residual'])<=.25 and abs(d['refined_residual'])<=.5
 assert len(d['history'])<=32 and d['history'][-1]['stage']=='refinement' and d['search_tolerance']==.25
 doc=out['document'];assert [l['thickness'] for l in doc['layers']]==[.0004,.0006]
 assert [l['eps_r'] for l in doc['layers']]==[3.8,4.5] and [l['tan_delta'] for l in doc['layers']]==[.01,.02]
 for t in doc['traces']:
  assert t['y']==.0004 and t['thickness']==.000035
  assert t['width']==(p['ground_width'] if t['ground'] else d['width'])
 assert doc==TemplateSectionDocument(name,{**p,'width':d['width']},mesh=doc['mesh']).cross_section.to_dict()
 assert out['line']['z_diff' if name==NAMES[1] else 'z0']==d['impedance']
 chosen=next(row for row in d['history'] if row['stage']=='search' and row['parameter']==d['width']);assert chosen['impedance']==d['impedance']
