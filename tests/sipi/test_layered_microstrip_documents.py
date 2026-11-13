# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Stored surface-layer geometry, independent sampling and refined width goals."""
import json
import numpy as np
import pytest
from sipi import (CrossSection, ImpedanceDesignDocument, seek_impedance,
                  layered_microstrip, coupled_layered_microstrip)
from sipi.template_document import TemplateSectionDocument
from sipi.study import ImpedanceStudyDocument
from sipi.execution import normalize_saved,execute_saved
from test_layered_microstrip import PARAMS,COARSE

NAMES=['layered_microstrip','coupled_layered_microstrip']

def parameters(name):
    return dict(PARAMS,**({'gap':.3e-3} if name.startswith('coupled_') else {}))

def quantity(name):return 'z_diff' if name.startswith('coupled_') else 'z0'

def study(name,kind='sweep',**extra):
    sampling=dict(kind=kind,variables=[dict(name='upper_eps_r',lower=4.8,upper=5.2)])
    if kind!='corners':sampling['count']=2
    if kind in ('uniform','normal'):sampling['seed']=71
    if kind=='normal':sampling.update(variables=[dict(name='upper_eps_r',mean=5.,std=.1)],correlation=[[1.]])
    return ImpedanceStudyDocument(name,parameters(name),quantity=quantity(name),mesh=COARSE,sampling=sampling,**extra)

@pytest.mark.parametrize('name',NAMES)
def test_editable_and_study_documents_load_without_meshing(name,monkeypatch):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('Input preparation meshed'))
    doc=TemplateSectionDocument(name,parameters(name),mesh=COARSE)
    assert TemplateSectionDocument.loads(doc.dumps()).dumps()==doc.dumps()
    assert normalize_saved(doc.dumps())==doc.dumps()
    assert doc.cross_section.section.traces[0].y==.001
    for kind in ('sweep','corners','uniform','normal'):
        saved=study(name,kind);assert normalize_saved(saved.dumps())==saved.dumps()
        again=ImpedanceStudyDocument.loads(saved.dumps())
        assert again.sample_parameters()==saved.sample_parameters()
        assert all(p['lower_eps_r']==3. for p in again.sample_parameters())

@pytest.mark.parametrize('name',NAMES)
def test_uniform_samples_match_independent_pcg64_and_material_order(name):
    saved=study(name,'uniform');expected=np.random.Generator(np.random.PCG64(71)).uniform([4.8],[5.2],size=(2,1))[:,0]
    np.testing.assert_array_equal([p['upper_eps_r'] for p in saved.sample_parameters()],expected)

@pytest.mark.parametrize('name',NAMES)
def test_real_material_sweep_and_shared_execution_match(name):
    saved=study(name);result=saved.analyze()
    assert result.failed==0 and len(result.rows)==2
    assert result.rows[1].impedance<result.rows[0].impedance
    for row in result.rows:
        assert [l.eps_r for l in row.document.section.layers]==[3.,row.parameters['upper_eps_r'],1.]
        assert row.document.section.traces[0].y==.001
    out=execute_saved(saved.dumps())
    assert out['status']=='complete'
    assert [r['value'] for r in out['result']['rows']]==[r.impedance for r in result.rows]

def test_fixed_pitch_pair_retains_centres_and_rejects_plane_spacing():
    doc=ImpedanceStudyDocument(NAMES[1],parameters(NAMES[1]),quantity='z_diff',mesh=COARSE,
        fixed_pitch_m=.8e-3,sampling=dict(kind='sweep',count=2,variables=[dict(name='width',lower=.45e-3,upper=.55e-3)]))
    for p in doc.sample_parameters():
        sec=coupled_layered_microstrip(**p)
        np.testing.assert_allclose([t.x for t in sec.traces],[-.4e-3,.4e-3],atol=0,rtol=1e-12)
        assert p['gap']==pytest.approx(.8e-3-p['width'],rel=1e-12)
    with pytest.raises(ValueError,match='layered stripline'):
        ImpedanceStudyDocument(NAMES[1],parameters(NAMES[1]),quantity='z_diff',fixed_plane_spacing_m=.001,
            sampling=dict(kind='sweep',count=2,variables=[dict(name='lower_height',lower=.25e-3,upper=.35e-3)]))

@pytest.mark.parametrize('name',NAMES)
def test_invalid_normal_material_samples_stay_failed_without_fields(name,monkeypatch):
    doc=ImpedanceStudyDocument(name,parameters(name),quantity=quantity(name),mesh=COARSE,
        sampling=dict(kind='normal',count=2,seed=71,correlation=[[1.]],variables=[dict(name='upper_eps_r',mean=.5,std=1e-12)]))
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('Invalid samples meshed'))
    result=doc.analyze();assert result.failed==2 and result.summary is None
    assert all(row.document is None and row.error_type=='ValueError' for row in result.rows)
    assert all(row.parameters['upper_eps_r']<1 for row in result.rows)

@pytest.mark.parametrize('name',NAMES)
def test_saved_width_target_replays_exact_requested_and_refined_history(name):
    pair=name.startswith('coupled_');p=parameters(name);factory=coupled_layered_microstrip if pair else layered_microstrip
    doc=ImpedanceDesignDocument(name,p,variable='width',bounds=[.2e-3,1.5e-3],target=100. if pair else 75.,
        quantity=quantity(name),tolerance=.5,search_tolerance=.25,mesh=COARSE)
    assert normalize_saved(doc.dumps())==doc.dumps()
    assert json.loads(doc.dumps())['schema']=='sipi.impedance-design/4'
    actual=ImpedanceDesignDocument.loads(doc.dumps()).solve()
    direct=seek_impedance(lambda w:factory(**{**p,'width':w}),[.2e-3,1.5e-3],100. if pair else 75.,
        quantity=quantity(name),tolerance=.5,search_tolerance=.25,mesh=COARSE)
    assert [vars(x) for x in actual.history]==[vars(x) for x in direct.history]
    assert actual.refined_impedance==direct.refined_impedance
    assert actual.history[-1].stage=='refinement'
    assert abs(actual.residual)<=.5 and abs(actual.refined_residual)<=.5
