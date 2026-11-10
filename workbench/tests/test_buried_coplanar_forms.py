"""Buried coplanar forms preserve explicit height, grounds and target gates."""
from pathlib import Path
import sys
import numpy as np
import pytest
import sipi
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'desktop'))
from engine import execute
from buried_coplanar_cases import NAMES,COARSE,parameters
from sipi.template_document import TemplateSectionDocument
pytestmark=pytest.mark.parametrize('name',NAMES)

def quantity(name):return 'z_diff' if name==NAMES[1] else 'z0'

@pytest.mark.parametrize('top',[None,.00025])
def test_explicit_height_ground_geometry_and_precise_saved_roundtrip(name,top,monkeypatch):
 monkeypatch.setattr(sipi.CrossSection,'mesh',lambda *a,**kw:pytest.fail('Document operation solved'))
 p={**parameters(name),'top_width':top};result=execute(dict(action='template-document',template=name,parameters=p,mesh=COARSE))
 assert execute(dict(action='template-open',text=result['document_text']))==result
 assert result['parameters']==TemplateSectionDocument(name,p,mesh=COARSE).to_dict()['parameters']
 d=result['document'];assert d['box']==dict(width=.006,bottom='ground',top='ground',sides='open')
 assert len(d['layers'])==1 and d['layers'][0]['name']=='dielectric'
 traces=d['traces'];grounds=[t for t in traces if t['ground']];signals=[t for t in traces if not t['ground']]
 assert len(grounds)==2 and len(signals)==(2 if name==NAMES[1] else 1)
 assert all(t['y']==p['trace_height'] and t['thickness']==p['thickness'] for t in traces)
 assert all(t['width']==p['ground_width'] and t.get('top_width') in (None,p['ground_width']) for t in grounds)
 right=signals[-1];g=grounds[-1]
 assert g['x']-g['width']/2-right['x']-right['width']/2==pytest.approx(p.get('ground_gap',p['gap']),rel=1e-12)
 p['trace_height']+=.0001
 moved=execute(dict(action='template-document',template=name,parameters=p,mesh=COARSE))
 assert all(b['y']-a['y']==pytest.approx(.0001,rel=1e-12) for a,b in zip(traces,moved['document']['traces']))
 assert moved['document']['mesh']==d['mesh'] and moved['document']['layers']==d['layers']

@pytest.mark.parametrize('change',[{'trace_height':None},{'trace_height':0},{'trace_height':.00099},{'gap':0},{'ground_width':0},{'plane_spacing':0},{'box_width':.0006}])
def test_invalid_geometry_is_rejected_before_mesh(name,change,monkeypatch):
 monkeypatch.setattr(sipi.CrossSection,'mesh',lambda *a,**kw:pytest.fail('Invalid geometry solved'))
 with pytest.raises(ValueError):execute(dict(action='analyze',template=name,parameters={**parameters(name),**change}))

@pytest.mark.parametrize('explicit',[False,True])
def test_goal_mesh_policy_and_failure_retained(name,explicit,monkeypatch):
 p=parameters(name);expected=dict(COARSE) if explicit else getattr(sipi,name)(**p).mesh_settings()
 if not explicit:expected['edge_size']/=2;expected['far_size']/=4
 failure=ValueError('unchanged numerical failure')
 def seek(factory,bounds,target,**kw):
  assert kw['search_tolerance']==.25 and kw['tolerance']==.5
  assert kw['mesh']==expected and kw['quantity']==quantity(name) and kw['max_evaluations']==32 and kw['return_line'] is True
  assert all(t.y==p['trace_height'] for t in factory(.00035).traces)
  raise failure
 monkeypatch.setattr(sipi,'seek_impedance',seek)
 with pytest.raises(ValueError) as caught:execute(dict(action='design',template=name,parameters=p,**({'mesh':COARSE} if explicit else {}),design=dict(bounds=[.00015,.00065],target=100 if name==NAMES[1] else 50,tolerance=.5)))
 assert caught.value is failure

@pytest.mark.parametrize('mode',['sweep','corners','monte_carlo'])
def test_height_and_gap_studies_preserve_fixed_mesh_and_all_ground_heights(name,mode):
 p=parameters(name);variables=[dict(parameter='trace_height',lower=.00035,upper=.00045)]
 if mode!='sweep':variables.append(dict(parameter='ground_gap' if name==NAMES[1] else 'gap',lower=.00025,upper=.00035))
 s=execute(dict(action='study',template=name,parameters=p,mesh=COARSE,study=dict(mode=mode,variables=variables,points=2,seed=42)))['study']
 assert s['status']=='complete' and s['failed']==0 and s['quantity']==quantity(name)
 assert len(s['rows'])==(4 if mode=='corners' else 2)
 for row in s['rows']:
  d=TemplateSectionDocument(name,{**p,**row['parameters']},mesh=COARSE).cross_section.to_dict()
  assert row['document']==d and row['impedance']==row['line'][quantity(name)]
  assert all(t['y']==row['parameters']['trace_height'] for t in d['traces'])

def test_invalid_height_study_bounds_rejected_before_mesh(name,monkeypatch):
 monkeypatch.setattr(sipi.CrossSection,'mesh',lambda *a,**kw:pytest.fail('Invalid study solved'))
 with pytest.raises(ValueError):execute(dict(action='study',template=name,parameters=parameters(name),mesh=COARSE,study=dict(mode='sweep',variables=[dict(parameter='trace_height',lower=.0009,upper=.001)],points=2,seed=42)))

def test_vacuum_tem_network_reciprocity_and_power(name):
 out=execute(dict(action='network',template=name,parameters=parameters(name,vacuum=True),mesh=COARSE,network=dict(start_hz=1e6,stop_hz=1e9,points=3,length=.1,resistance=0,z_ref=50)))
 line,n=out['line'],out['network'];count=2 if name==NAMES[1] else 1
 np.testing.assert_allclose(line['C'],line['C0'],rtol=2e-12,atol=1e-23)
 np.testing.assert_allclose(np.array(line['L'])@line['C']*299792458.**2,np.eye(count),rtol=2e-12,atol=2e-12)
 s=np.array(n['real'])+1j*np.array(n['imag']);np.testing.assert_allclose(s,s.transpose(0,2,1),rtol=0,atol=2e-12)
 for value in s:np.testing.assert_allclose(value.conj().T@value,np.eye(2*count),rtol=0,atol=2e-12)

def test_automatic_width_target_retains_height_and_outer_convergence(name):
 p=dict(parameters(name),width=.0003,trace_height=.0004,top_width=None)
 target=100. if name==NAMES[1] else 50.
 out=execute(dict(action='design',template=name,parameters=p,design=dict(bounds=[.00015,.00065],target=target,tolerance=.5)))
 d=out['design'];assert d['search_tolerance']==.25 and abs(d['residual'])<=.25 and abs(d['refined_residual'])<=.5
 assert d['history'][-1]['stage']=='refinement' and .00015<=d['width']<=.00065
 assert out['line'][quantity(name)]==d['impedance']
 chosen={**p,'width':d['width']};mesh=getattr(sipi,name)(**p).mesh_settings();mesh['edge_size']/=2;mesh['far_size']/=4
 assert out['document']==TemplateSectionDocument(name,chosen,mesh=mesh).cross_section.to_dict()
 outer=getattr(sipi,name)(**{**chosen,'box_width':.012}).analyze(**mesh)
 value=outer.even_odd()['z_diff'] if name==NAMES[1] else outer.z0
 assert value==pytest.approx(d['impedance'],rel=.005)

@pytest.mark.parametrize('tolerance',[0,-1,True,None,'0.5',float('inf'),float('nan')])
def test_invalid_target_tolerance_does_not_solve(name,tolerance,monkeypatch):
 monkeypatch.setattr(sipi.CrossSection,'mesh',lambda *a,**kw:pytest.fail('Invalid target solved'))
 with pytest.raises(ValueError,match='tolerance'):
  execute(dict(action='design',template=name,parameters=parameters(name),design=dict(bounds=[.00015,.00065],target=100,tolerance=tolerance)))
