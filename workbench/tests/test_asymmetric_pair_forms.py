"""Unequal pairs keep conductor order and an explicit lossless forward launch."""
from pathlib import Path
import sys
import numpy as np
import pytest
import sipi
from sipi.template_document import TemplateSectionDocument
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'desktop'))
from engine import execute,TEMPLATES,serialize_line
from asymmetric_pair_cases import NAMES,COARSE,parameters

@pytest.mark.parametrize('name',NAMES)
@pytest.mark.parametrize('zero',[False,True])
def test_independent_dimensions_and_exact_editable_roundtrip(name,zero,monkeypatch):
 monkeypatch.setattr(sipi.CrossSection,'mesh',lambda *a,**k:pytest.fail('Saving solved fields'))
 p=parameters(name,**(dict(left_thickness=0,left_top_width=None) if zero else {}));out=execute(dict(action='template-document',template=name,parameters=p,mesh=COARSE))
 assert out['document_text']==TemplateSectionDocument(name,p,mesh=COARSE).dumps()
 assert execute(dict(action='template-open',text=out['document_text']))==out
 d=out['document'];a,b=d['traces'];assert [a['name'],b['name']]==['positive','negative']
 assert a['x']==-(p['gap']+p['right_width'])/2 and b['x']==(p['gap']+p['left_width'])/2
 assert b['x']-b['width']/2-(a['x']+a['width']/2)==pytest.approx(p['gap'],rel=1e-12)
 for side,t in [('left',a),('right',b)]:
  assert t['width']==p[side+'_width'] and t['thickness']==p[side+'_thickness']
  assert t['y']==((p['plane_spacing']-t['thickness'])/2 if name==NAMES[1] else p['substrate_height'])
 assert d['box']['top']==('ground' if name==NAMES[1] else 'open')

@pytest.mark.parametrize('name',NAMES)
@pytest.mark.parametrize('change',[dict(left_width=0),dict(right_width=True),dict(left_thickness=-1),dict(right_thickness=float('nan')),dict(left_top_width=0),dict(gap=0),dict(left_thickness=0),dict(box_width=.0001)])
def test_invalid_geometry_refused_before_field_solve(name,change,monkeypatch):
 monkeypatch.setattr(sipi.CrossSection,'mesh',lambda *a,**k:pytest.fail('Invalid input solved fields'))
 with pytest.raises((ValueError,TypeError)):execute(dict(action='analyze',template=name,parameters=parameters(name,**change)))

@pytest.mark.parametrize('name',NAMES)
@pytest.mark.parametrize('mode',['sweep','corners','monte_carlo'])
def test_independent_width_and_thickness_studies_use_forward_quantity(name,mode):
 p=parameters(name);variables=[dict(parameter='left_width',lower=p['left_width']*.9,upper=p['left_width']*1.1)]
 if mode!='sweep':variables.append(dict(parameter='right_thickness',lower=.000045,upper=.000055))
 study=execute(dict(action='study',template=name,parameters=p,mesh=COARSE,study=dict(mode=mode,variables=variables,points=2,seed=42)))['study']
 assert study['quantity']=='z_diff_forward' and study['failed']==0
 assert len(study['rows'])==(4 if mode=='corners' else 2)
 for row in study['rows']:
  changed={**p,**row['parameters']};assert row['document']==TemplateSectionDocument(name,changed,mesh=COARSE).cross_section.to_dict()
  assert row['impedance']==row['line']['z_diff_forward'] and 'z_diff' not in row['line']
  assert row['line']['forward_launch']['condition']=='Icommon=0; I=[Idiff,-Idiff]'

@pytest.mark.parametrize('name',NAMES)
@pytest.mark.parametrize('variable',['width','left_thickness','gap',None,True])
def test_target_requires_an_explicit_supported_width_before_solve(name,variable,monkeypatch):
 monkeypatch.setattr(sipi.CrossSection,'mesh',lambda *a,**k:pytest.fail('Invalid target solved fields'))
 with pytest.raises(ValueError):execute(dict(action='design',template=name,parameters=parameters(name),design=dict(variable=variable,bounds=[.0001,.0012],target=100,tolerance=.5)))

@pytest.mark.parametrize('name',NAMES)
@pytest.mark.parametrize('variable',['left_width','right_width'])
@pytest.mark.parametrize('explicit',[False,True])
def test_selected_width_policy_preserves_other_dimensions_and_original_failure(name,variable,explicit,monkeypatch):
 p=parameters(name);mesh=dict(COARSE) if explicit else TEMPLATES[name](**p).mesh_settings()
 if not explicit:mesh['edge_size']/=2;mesh['far_size']/=4
 error=ValueError('original selected-width target refusal')
 def seek(factory,bounds,target,**kw):
  assert kw==dict(tolerance=.5,quantity='z_diff_forward',mesh=mesh,max_evaluations=32,return_line=True,search_tolerance=.25)
  actual=factory(.00035);expected=TEMPLATES[name](**{**p,variable:.00035});assert sipi.CrossSectionDocument(actual).dumps()==sipi.CrossSectionDocument(expected).dumps();raise error
 monkeypatch.setattr(sipi,'seek_impedance',seek)
 with pytest.raises(ValueError) as caught:execute(dict(action='design',template=name,parameters=p,**({'mesh':COARSE} if explicit else {}),design=dict(variable=variable,bounds=[.0001,.0012],target=100,tolerance=.5)))
 assert caught.value is error

@pytest.mark.parametrize('name',NAMES)
def test_independent_energy_forward_mean_and_separate_convergence(name):
 from crosscheck import require_tool,Stopwatch,observable,make_record,emit
 from sipi.constants import epsilon_0,mu_0
 skfem=require_tool('scikit-fem');from skfem.helpers import dot,grad
 p=parameters(name);cs=TEMPLATES[name](**p);m=cs.mesh(**COARSE);clock=Stopwatch()
 with clock('openphysics'):line=m.line_parameters()
 with clock('reference'):
  basis=skfem.Basis(skfem.MeshTri(m.mesh.nodes.T,m.mesh.triangles.T),skfem.ElementTriP1())
  @skfem.BilinearForm(dtype=complex)
  def form(u,v,w):return w.eps*dot(grad(u),grad(v))
  fixed=np.unique(np.concatenate([m.ground,*m.signals.values()]));expected=[]
  for eps in [m.eps_r*(1-1j*m.tan_delta),np.ones_like(m.eps_r)]:
   k=skfem.asm(form,basis,eps=eps[:,None]);columns=[]
   for nodes in m.signals.values():
    v=np.zeros(basis.N,complex);v[nodes]=1;columns.append(skfem.solve(*skfem.condense(k,np.zeros(basis.N,complex),x=v,D=fixed)))
   u=np.array(columns).T;expected.append(epsilon_0*(u.T@(k@u)))
 c,c0=expected[0].real,expected[1].real;ind=epsilon_0*mu_0*np.linalg.inv(c0)
 errors=[float(np.max(abs(a-b))/np.max(abs(b))) for a,b in [(line.C,c),(line.C0,c0),(line.C_loss,-expected[0].imag),(line.L,ind)]]
 def root(a):values,vectors=np.linalg.eigh(a);return (vectors*np.sqrt(values))@vectors.T
 caproot=root(c);inverse=np.linalg.inv(caproot);z=inverse@root(caproot@ind@caproot)@inverse;d=np.array([1.,-1.]);forward=float(d@z@d);errors.append(abs(line.z_diff_forward/forward-1));assert max(errors)<1e-10
 out=serialize_line(line,forward_pair=True);assert out['z_diff_forward']==line.z_diff_forward and 'z_diff' not in out and 'eps_eff' not in out
 with pytest.raises(ValueError):line.even_odd()
 fine={**COARSE,'edge_size':COARSE['edge_size']/2,'far_size':COARSE['far_size']/2,'grade':COARSE['grade']/2};refined=cs.analyze(**fine)
 for other,limit in [(refined,.015),(TEMPLATES[name](**{**p,'box_width':p['box_width']*2}).analyze(**COARSE),.005)]+([] if name==NAMES[1] else [(TEMPLATES[name](**{**p,'air_height':p['air_height']*2}).analyze(**COARSE),.005)]):
  assert abs(other.z_diff_forward/line.z_diff_forward-1)<limit
  assert np.max(abs(other.C-line.C))/np.max(abs(line.C))<limit
 record=make_record(case=name+'-form-forward',physics='unequal lossy dielectric cross section',api='sipi.'+name,discretization='P1 finite unequal conductors',tool='scikit-fem',tool_discretization='independent complex/vacuum P1 energy and SPD matrix mean',matched=['geometry, mesh, material coefficients, boundaries and conductor order'],not_matched=['no measured manufacturing accuracy or 3D transition'],observables=[observable(n,u,'relative difference',e,1e-10) for n,u,e in zip(['C','C0','C_loss','L','forward Z'],['F/m','F/m','F/m','H/m','ohm'],errors)],analytical_acceptance='SPD Riccati branch; separate mesh1.5percent/side and air0.5percent',stopwatch=clock);emit(record)

@pytest.mark.parametrize('name',NAMES)
def test_asymmetric_vacuum_four_port_power_reciprocity_and_lossless_diagnostic(name):
 out=execute(dict(action='network',template=name,parameters=parameters(name,eps_r=1,tan_delta=0),mesh=COARSE,network=dict(start_hz=1e6,stop_hz=1e9,points=3,length=.1,resistance=0,z_ref=50)))
 line,n=out['line'],out['network'];assert n['extension']=='s4p' and 'z_diff_forward' in line and 'z_diff' not in line
 np.testing.assert_allclose(line['C'],line['C0'],rtol=2e-12,atol=1e-23);s=np.array(n['real'])+1j*np.array(n['imag']);np.testing.assert_allclose(s,s.transpose(0,2,1),rtol=0,atol=2e-12)
 for v in s:np.testing.assert_allclose(v.conj().T@v,np.eye(4),rtol=0,atol=2e-12)

def test_raw_asymmetric_document_keeps_existing_matrix_only_fallback(monkeypatch):
 cap=np.array([[120,-30],[-30,150]])*1e-12;ind=np.array([[400,70],[70,350]])*1e-9
 line=sipi.LineParameters(('positive','negative'),cap,np.eye(2)*1e-11,ind,cap*.02)
 monkeypatch.setattr(sipi.CrossSectionDocument,'analyze',lambda *a,**k:line)
 doc=TemplateSectionDocument(NAMES[0],parameters(NAMES[0]),mesh=COARSE).cross_section.to_dict()
 old=execute(dict(action='analyze',document=doc));extra=execute(dict(action='analyze',document=doc,template=NAMES[0]));assert old==extra
 assert 'scalar_summary_unavailable' in old['line'] and 'z_diff_forward' not in old['line']
 assert serialize_line(line,forward_pair=True)['z_diff_forward']==line.z_diff_forward
 zero=sipi.LineParameters(line.names,line.C,line.C0,line.L,np.zeros_like(line.C_loss))
 assert serialize_line(zero,forward_pair=True)['z_diff_forward']==line.z_diff_forward


def test_unequal_templates_are_registered_as_pairs_with_explicit_quantity():
 from engine import ASYMMETRIC_PAIR_TEMPLATES,PAIR_TEMPLATES
 import json
 reference=json.loads((Path(__file__).resolve().parents[2]/'tests/sipi/reference_data/template_section/reference.json').read_text())
 expected={r['template'] for r in reference['cases'] if r['template'].startswith('asymmetric_')}
 assert len(expected)==13 and expected==ASYMMETRIC_PAIR_TEMPLATES
 assert set(NAMES)<=expected
 assert ASYMMETRIC_PAIR_TEMPLATES<=PAIR_TEMPLATES<=TEMPLATES.keys()


@pytest.mark.parametrize('name',NAMES)
@pytest.mark.parametrize('variable',['left_width','right_width'])
def test_physical_selected_width_target_preserves_other_conductor(name,variable):
    buried=name==NAMES[1]
    p=dict(left_width=.3*1e-3 if buried else .4*1e-3,
           right_width=.5*1e-3 if buried else .65*1e-3,
           gap=.4*1e-3 if buried else .25*1e-3,eps_r=4,
           left_thickness=.035*1e-3,right_thickness=.05*1e-3,
           tan_delta=.02,box_width=.006 if buried else .012)
    p['plane_spacing' if buried else 'substrate_height']=.001 if buried else .0005
    if not buried:p['air_height']=.006
    out=execute(dict(action='design',template=name,parameters=p,
        design=dict(variable=variable,bounds=[.1*1e-3,1.2*1e-3],target=100,tolerance=.5)))
    d=out['design'];assert d['variable']==variable and d['quantity']=='z_diff_forward'
    assert 'width' not in d and .1*1e-3<=d['parameter']<=1.2*1e-3
    assert abs(d['residual'])<=.25 and abs(d['refined_residual'])<=.5
    assert d['search_tolerance']==.25 and len(d['history'])<=32
    assert d['history'][-1]['stage']=='refinement'
    changed={**p,variable:d['parameter']};doc=out['document']
    assert doc==TemplateSectionDocument(name,changed,mesh=doc['mesh']).cross_section.to_dict()
    assert out['line']['z_diff_forward']==d['impedance']
    chosen=next(row for row in d['history'] if row['stage']=='search' and row['parameter']==d['parameter'])
    assert chosen['impedance']==d['impedance']
    traces=doc['traces'];assert [t['name'] for t in traces]==['positive','negative']
    for side,t in zip(['left','right'],traces):
        assert t['width']==changed[side+'_width'] and t['thickness']==p[side+'_thickness']
        assert t['y']==((p['plane_spacing']-t['thickness'])/2 if buried else p['substrate_height'])
