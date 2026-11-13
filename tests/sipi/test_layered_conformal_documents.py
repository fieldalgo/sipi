# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved coated layered inputs preserve substrate, film, air and objectives."""
import numpy as np
import pytest
from sipi import CrossSection,ImpedanceDesignDocument,seek_impedance
from sipi.template_document import TemplateSectionDocument
from sipi.study import ImpedanceStudyDocument
from sipi.execution import normalize_saved,execute_saved
from test_layered_conformal_microstrip import NAMES,STACK,GEOMETRY,COARSE,section


def assert_geometry(s):
 from shapely.geometry import Point
 assert len(s.layers)==3 and s.layers[0].thickness==.0003 and s.layers[1].thickness==.0007
 assert s.layers[-1].name=='air'
 film,=s.dielectric_regions
 assert film.name=='coating'
 assert s.height-film._shape.bounds[3]==pytest.approx(.01,rel=1e-12)
 for t in s.traces:
  slope=(t.width-t.top_width)/(2*t.thickness)
  point=np.array([t.x+(t.width+t.top_width)/4,t.y+t.thickness/2])+20e-6*np.array([1.,slope])/np.hypot(1,slope)
  assert film._shape.boundary.distance(Point(point))<=5e-15

Q=['z0','z_diff','z_diff_forward']
def parameters(i):return {**STACK,**GEOMETRY[i]}
def variable(i):return 'left_width' if i==2 else 'width'
def pitch(i):return None if i==0 else .8e-3 if i==1 else .85e-3

def study(i,kind='sweep',**changes):
 key=variable(i);w=parameters(i)[key];sampling=dict(kind=kind,variables=[dict(name=key,lower=w*.99,upper=w*1.01)])
 if kind!='corners':sampling['count']=2
 if kind in ('uniform','normal'):sampling['seed']=71
 if kind=='normal':sampling.update(variables=[dict(name=key,mean=w,std=w*.01)],correlation=[[1.]])
 opts=dict(quantity=Q[i],mesh=COARSE,sampling=sampling,fixed_pitch_m=pitch(i));opts.update(changes)
 return ImpedanceStudyDocument(NAMES[i],parameters(i),**opts)

@pytest.mark.parametrize('i',range(3),ids=NAMES)
def test_prepare_all_saved_sampling_without_solving(i,monkeypatch):
 monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('Preparing input solved fields'))
 d=TemplateSectionDocument(NAMES[i],parameters(i),mesh=COARSE)
 assert normalize_saved(d.dumps())==d.dumps() and TemplateSectionDocument.loads(d.dumps()).dumps()==d.dumps()
 for kind in ['sweep','corners','uniform','normal']:
  d=study(i,kind);assert normalize_saved(d.dumps())==d.dumps()
  assert ImpedanceStudyDocument.loads(d.dumps()).sample_parameters()==d.sample_parameters()

@pytest.mark.parametrize('i',range(3),ids=NAMES)
def test_uniform_width_matches_independent_pcg64_and_preserves_film(i):
 doc=study(i,'uniform');w=parameters(i)[variable(i)]
 expected=np.random.Generator(np.random.PCG64(71)).uniform([w*.99],[w*1.01],size=(2,1))[:,0]
 actual=doc.sample_parameters();np.testing.assert_array_equal([p[variable(i)] for p in actual],expected)
 for p in actual:
  s=section(i,**p)
  assert s.bottom=='ground' and all(not t.ground and t.y==.001 for t in s.traces)
  assert_geometry(s)
  if i:assert s.traces[1].x-s.traces[0].x==pytest.approx(pitch(i),rel=1e-12)

@pytest.mark.parametrize('i,bad',[(0,'z_diff'),(1,'z0'),(2,'z_diff')],ids=NAMES)
def test_invalid_objective_rejects_without_inventing_modes(i,bad):
 with pytest.raises(ValueError,match='requires quantity'):study(i,quantity=bad)

@pytest.mark.parametrize('i',range(3),ids=NAMES)
def test_plane_spacing_rejects_surface_stack(i):
 with pytest.raises(ValueError,match='layered stripline'):
  study(i,fixed_pitch_m=None,fixed_plane_spacing_m=.001,sampling=dict(kind='sweep',count=2,variables=[dict(name='lower_height',lower=.25e-3,upper=.35e-3)]))

@pytest.mark.parametrize('i',range(3),ids=NAMES)
def test_invalid_normal_coating_thickness_keeps_failed_rows(i,monkeypatch):
 d=study(i,fixed_pitch_m=None,sampling=dict(kind='normal',count=2,seed=71,correlation=[[1.]],variables=[dict(name='coating_thickness',mean=-20e-6,std=1e-12)]))
 monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('Invalid coating was meshed'))
 result=d.analyze();assert result.failed==2 and result.summary is None
 assert all(r.document is None and r.error_type=='ValueError' and r.parameters['coating_thickness']<0 for r in result.rows)

@pytest.mark.parametrize('i',range(3),ids=NAMES)
def test_material_sweep_replays_common_executor_with_fixed_coating_geometry(i):
 d=study(i,fixed_pitch_m=None,sampling=dict(kind='sweep',count=2,variables=[dict(name='coating_eps_r',lower=3.1,upper=3.5)]))
 r=d.analyze();assert r.failed==0 and r.rows[1].impedance<r.rows[0].impedance
 for row in r.rows:
  assert row.document.section.bottom=='ground'
  assert row.document.section.layers[0].eps_r==3.
  assert row.document.section.layers[1].eps_r==5.
  assert_geometry(row.document.section)
  assert all(t.y==.001 for t in row.document.section.traces)
 out=execute_saved(d.dumps());assert out['status']=='complete'
 assert [row['value'] for row in out['result']['rows']]==[row.impedance for row in r.rows]

@pytest.mark.parametrize('i',range(3),ids=NAMES)
def test_saved_target_replays_requested_and_refined_history(i):
 key=variable(i);bounds=[.32e-3,.8e-3] if i==2 else [.4e-3,.7e-3];target=90. if i==0 else 105.
 doc=ImpedanceDesignDocument(NAMES[i],parameters(i),variable=key,bounds=bounds,target=target,quantity=Q[i],mesh=COARSE,tolerance=.5,search_tolerance=.05)
 assert normalize_saved(doc.dumps())==doc.dumps()
 result=ImpedanceDesignDocument.loads(doc.dumps()).solve()
 direct=seek_impedance(lambda w:section(i,**{key:w}),bounds,target,quantity=Q[i],mesh=COARSE,tolerance=.5,search_tolerance=.05)
 assert [vars(x) for x in result.history]==[vars(x) for x in direct.history]
 assert result.refined_impedance==direct.refined_impedance
 assert abs(result.residual)<=.5 and abs(result.refined_residual)<=.5
 assert result.history[-1].stage=='refinement'
 assert result.document.section.bottom=='ground'
 assert_geometry(result.document.section)
 assert all(not t.ground and t.y==.001 for t in result.document.section.traces)


def test_equal_pair_retains_explicit_forward_objective_with_fixed_pitch():
 d=study(1,quantity='z_diff_forward')
 assert normalize_saved(d.dumps())==d.dumps()
 for p in d.sample_parameters():
  s=section(1,**p);signals=[t for t in s.traces if not t.ground]
  assert signals[1].x-signals[0].x==pytest.approx(.8e-3,rel=1e-12)
