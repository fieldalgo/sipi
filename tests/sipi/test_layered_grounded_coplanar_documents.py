# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved layered coplanar inputs preserve finite grounds and valid objectives."""
import numpy as np
import pytest
from sipi import CrossSection,ImpedanceDesignDocument,seek_impedance
from sipi.template_document import TemplateSectionDocument
from sipi.study import ImpedanceStudyDocument
from sipi.execution import normalize_saved,execute_saved
from test_layered_grounded_coplanar import NAMES,STACK,GEOMETRY,COARSE,FINE,section

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
def test_uniform_width_matches_independent_pcg64_and_preserves_ground_gap(i):
 doc=study(i,'uniform');w=parameters(i)[variable(i)]
 expected=np.random.Generator(np.random.PCG64(71)).uniform([w*.99],[w*1.01],size=(2,1))[:,0]
 actual=doc.sample_parameters();np.testing.assert_array_equal([p[variable(i)] for p in actual],expected)
 for p in actual:
  s=section(i,**p);signals=sorted([t for t in s.traces if not t.ground],key=lambda t:t.x);grounds=sorted([t for t in s.traces if t.ground],key=lambda t:t.x)
  assert signals[0].x0-grounds[0].x1==pytest.approx(.2e-3,rel=1e-12)
  assert grounds[1].x0-signals[-1].x1==pytest.approx(.2e-3,rel=1e-12)
  assert all(t.width==1e-3 and t.thickness==35e-6 for t in grounds)
  if i:assert signals[1].x-signals[0].x==pytest.approx(pitch(i),rel=1e-12)

@pytest.mark.parametrize('i,bad',[(0,'z_diff'),(1,'z0'),(2,'z_diff')],ids=NAMES)
def test_invalid_objective_rejects_without_inventing_modes(i,bad):
 with pytest.raises(ValueError,match='requires quantity'):study(i,quantity=bad)

@pytest.mark.parametrize('i',range(3),ids=NAMES)
def test_plane_spacing_rejects_surface_stack(i):
 with pytest.raises(ValueError,match='layered stripline'):
  study(i,fixed_pitch_m=None,fixed_plane_spacing_m=.001,sampling=dict(kind='sweep',count=2,variables=[dict(name='lower_height',lower=.25e-3,upper=.35e-3)]))

@pytest.mark.parametrize('i',range(3),ids=NAMES)
def test_invalid_normal_ground_width_keeps_failed_rows(i,monkeypatch):
 d=study(i,fixed_pitch_m=None,sampling=dict(kind='normal',count=2,seed=71,correlation=[[1.]],variables=[dict(name='ground_width',mean=-1e-3,std=1e-12)]))
 monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('Invalid ground was meshed'))
 result=d.analyze();assert result.failed==2 and result.summary is None
 assert all(r.document is None and r.error_type=='ValueError' and r.parameters['ground_width']<0 for r in result.rows)

@pytest.mark.parametrize('i',range(3),ids=NAMES)
def test_material_sweep_replays_common_executor_with_fixed_ground_geometry(i):
 d=study(i,fixed_pitch_m=None,sampling=dict(kind='sweep',count=2,variables=[dict(name='upper_eps_r',lower=4.8,upper=5.2)]))
 r=d.analyze();assert r.failed==0 and r.rows[1].impedance<r.rows[0].impedance
 for row in r.rows:
  assert row.document.section.layers[0].eps_r==3.
  assert all(t.y==.001 for t in row.document.section.traces)
 out=execute_saved(d.dumps());assert out['status']=='complete'
 assert [row['value'] for row in out['result']['rows']]==[row.impedance for row in r.rows]

@pytest.mark.parametrize('i',range(3),ids=NAMES)
def test_saved_target_replays_requested_and_refined_history(i):
 key=variable(i);bounds=[.32e-3,.8e-3] if i==2 else [.4e-3,.7e-3];target=60. if i==0 else 100.
 doc=ImpedanceDesignDocument(NAMES[i],parameters(i),variable=key,bounds=bounds,target=target,quantity=Q[i],mesh=FINE,tolerance=.5,search_tolerance=.1)
 assert normalize_saved(doc.dumps())==doc.dumps()
 result=ImpedanceDesignDocument.loads(doc.dumps()).solve()
 direct=seek_impedance(lambda w:section(i,**{key:w}),bounds,target,quantity=Q[i],mesh=FINE,tolerance=.5,search_tolerance=.1)
 assert [vars(x) for x in result.history]==[vars(x) for x in direct.history]
 assert result.refined_impedance==direct.refined_impedance
 assert abs(result.residual)<=.5 and abs(result.refined_residual)<=.5
 assert result.history[-1].stage=='refinement'
 for t in result.document.section.traces:
  if t.ground:assert t.width==1e-3 and t.thickness==35e-6


def test_equal_pair_retains_explicit_forward_objective_with_fixed_pitch():
 d=study(1,quantity='z_diff_forward')
 assert normalize_saved(d.dumps())==d.dumps()
 for p in d.sample_parameters():
  s=section(1,**p);signals=[t for t in s.traces if not t.ground]
  assert signals[1].x-signals[0].x==pytest.approx(.8e-3,rel=1e-12)
