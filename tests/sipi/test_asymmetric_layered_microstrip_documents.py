# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved unequal surface layers retain launch, pitch and failure semantics."""
import json
import numpy as np
import pytest
from sipi import CrossSection,ImpedanceDesignDocument,seek_impedance
from sipi.template_document import TemplateSectionDocument
from sipi.study import ImpedanceStudyDocument
from sipi.execution import normalize_saved,execute_saved
from test_asymmetric_layered_microstrip import P,COARSE,section

NAME='asymmetric_coupled_layered_microstrip'
PITCH=.85e-3

def study(kind='sweep',**changes):
 sampling=dict(kind=kind,variables=[dict(name='left_width',lower=.38e-3,upper=.42e-3)])
 if kind!='corners':sampling['count']=2
 if kind in ('uniform','normal'):sampling['seed']=71
 if kind=='normal':sampling.update(variables=[dict(name='left_width',mean=.4e-3,std=.01e-3)],correlation=[[1.]])
 options=dict(quantity='z_diff_forward',mesh=COARSE,sampling=sampling,fixed_pitch_m=PITCH);options.update(changes)
 return ImpedanceStudyDocument(NAME,P,**options)


def test_all_stored_inputs_prepare_without_solving_fields(monkeypatch):
 monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('Preparing input solved fields'))
 d=TemplateSectionDocument(NAME,P,mesh=COARSE);assert normalize_saved(d.dumps())==d.dumps()
 assert TemplateSectionDocument.loads(d.dumps()).dumps()==d.dumps()
 for kind in ['sweep','corners','uniform','normal']:
  d=study(kind);assert normalize_saved(d.dumps())==d.dumps()
  assert ImpedanceStudyDocument.loads(d.dumps()).sample_parameters()==d.sample_parameters()

@pytest.mark.parametrize('quantity',['z0','z_diff'])
def test_unequal_pair_rejects_scalar_or_symmetric_modal_objective(quantity):
 with pytest.raises(ValueError,match='z_diff_forward'):study(quantity=quantity)


def test_two_width_uniform_sampling_matches_independent_pcg64_and_relative_pitch():
 variables=[dict(name='left_width',lower=.38e-3,upper=.42e-3),dict(name='right_width',lower=.68e-3,upper=.72e-3)]
 doc=study(sampling=dict(kind='uniform',count=3,seed=71,variables=variables))
 expected=np.random.Generator(np.random.PCG64(71)).uniform([.38e-3,.68e-3],[.42e-3,.72e-3],size=(3,2))
 actual=doc.sample_parameters();np.testing.assert_array_equal([[p['left_width'],p['right_width']] for p in actual],expected)
 for p in actual:
  s=section(**p);a,b=s.traces
  assert b.x-a.x==pytest.approx(PITCH,rel=1e-12)
  assert p['gap']==pytest.approx(PITCH-(p['left_width']+p['right_width'])/2,rel=1e-12)
  assert a.x0==pytest.approx(-b.x1,abs=1e-18)
  assert [(l.eps_r,l.thickness) for l in s.layers[:2]]==[(3.,.3e-3),(5.,.7e-3)]


def test_fixed_plane_spacing_does_not_reinterpret_surface_layer_heights():
 with pytest.raises(ValueError,match='layered stripline'):
  study(fixed_pitch_m=None,fixed_plane_spacing_m=.001,
        sampling=dict(kind='sweep',count=2,variables=[dict(name='lower_height',lower=.25e-3,upper=.35e-3)]))


def test_failed_normal_material_samples_keep_rows_without_field_solves(monkeypatch):
 d=study(fixed_pitch_m=None,sampling=dict(kind='normal',count=2,seed=71,correlation=[[1.]],variables=[dict(name='lower_eps_r',mean=.5,std=1e-12)]))
 monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('Invalid sample meshed'))
 r=d.analyze();assert r.failed==2 and r.summary is None
 assert all(x.document is None and x.error_type=='ValueError' and x.parameters['lower_eps_r']<1 for x in r.rows)


def test_real_upper_material_study_replays_shared_execution_without_modes():
 d=study(fixed_pitch_m=None,sampling=dict(kind='sweep',count=2,variables=[dict(name='upper_eps_r',lower=4.8,upper=5.2)]))
 r=d.analyze();assert r.failed==0 and r.rows[1].impedance<r.rows[0].impedance
 for row in r.rows:
  assert row.document.section.traces[0].y==.001
  assert row.document.section.layers[0].eps_r==3.
 out=execute_saved(d.dumps());assert out['status']=='complete'
 assert [x['value'] for x in out['result']['rows']]==[x.impedance for x in r.rows]

@pytest.mark.parametrize('fixed_pitch',[False,True])
def test_saved_left_width_goal_replays_exact_history_and_refinement(fixed_pitch):
 bounds=[.35e-3,.9e-3 if fixed_pitch else 1.4e-3]
 doc=ImpedanceDesignDocument(NAME,P,variable='left_width',bounds=bounds,target=100.,quantity='z_diff_forward',
       tolerance=.5,search_tolerance=.25,mesh=COARSE,fixed_pitch_m=PITCH if fixed_pitch else None)
 assert normalize_saved(doc.dumps())==doc.dumps() and json.loads(doc.dumps())['schema']=='sipi.impedance-design/4'
 replay=ImpedanceDesignDocument.loads(doc.dumps()).solve()
 def factory(w):return section(left_width=w,**({'gap':PITCH-(w+P['right_width'])/2} if fixed_pitch else {}))
 direct=seek_impedance(factory,bounds,100.,quantity='z_diff_forward',tolerance=.5,search_tolerance=.25,mesh=COARSE)
 assert [vars(x) for x in replay.history]==[vars(x) for x in direct.history]
 assert replay.refined_impedance==direct.refined_impedance
 assert abs(replay.residual)<=.5 and abs(replay.refined_residual)<=.5
 assert replay.document.section.traces[1].width==P['right_width']
 if fixed_pitch:assert replay.document.section.traces[1].x-replay.document.section.traces[0].x==pytest.approx(PITCH,rel=1e-12)
