# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Fixed coated paired samples, joint unknown bounds and separate refinements."""
import json
import numpy as np
import pytest
from sipi import CrossSection
from sipi.study import ImpedanceStudyDocument
from sipi.panel_pair_study import PanelForwardPairStudyDocument
from sipi.panel_pair_yield import PanelForwardPairYieldDocument, assess_panel_pair_yield
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.execution import execute_saved, normalize_saved
from test_layered_panel_goal import factory, independent, snapshot, MESH
from test_panel_pair_goal import synthetic
from test_panel_pair_study import expected_statistics
from test_yield_assessment import independent_interval

Q = ('differential_forward_impedance_real','common_forward_impedance_real')
LIMITS = {Q[0]:dict(minimum=109.,maximum=111.),Q[1]:dict(minimum=39.75,maximum=40.25)}
MEAN = (.0006073049209836395,.0004082505417130786)


def source():
    return ImpedanceStudyDocument('asymmetric_coupled_microstrip',
        dict(left_width=MEAN[0],right_width=.5e-3,gap=MEAN[1],substrate_height=.5e-3,
             eps_r=4.,tan_delta=.02,left_thickness=35e-6,right_thickness=50e-6,
             box_width=.024,air_height=.010),
        quantity='z_diff_forward',frequency=1e9,materials={},mesh=MESH,
        sampling=dict(kind='normal',count=8,seed=3,correlation=[[1.,.5],[.5,1.]],variables=[
            dict(name='left_width',mean=MEAN[0],std=10e-6),dict(name='gap',mean=MEAN[1],std=5e-6)]))


def document():
    return PanelForwardPairStudyDocument(source(),conductor=factory(*MEAN).to_dict()['line']['conductor'],
        schema='sipi.panel-forward-pair-study/2')


def yield_document():
    return PanelForwardPairYieldDocument(document(),acceptance=LIMITS,minimum_yield=.9,
                                         schema='sipi.panel-forward-pair-yield/2')


def test_explicit_versions_field_free_roundtrip_and_copies(monkeypatch):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('normalization meshed'))
    for doc in (document(),yield_document()):
        text=doc.dumps();assert normalize_saved(text)==text
        assert type(doc).loads(text).dumps()==text
        raw=doc.to_dict();raw['schema']='unexpected'
        assert doc.dumps()==text
    np.testing.assert_array_equal(document().samples(),source().samples())
    with pytest.raises(ValueError):PanelForwardPairStudyDocument(source(),conductor=document().to_dict()['conductor'])
    with pytest.raises(ValueError):PanelForwardPairYieldDocument(document(),acceptance=LIMITS)


@pytest.mark.parametrize('yield_input',[False,True])
@pytest.mark.parametrize('mode',['schema','missing','unknown','duplicate','nonfinite'])
def test_strict_saved_inputs(yield_input,mode):
    doc=yield_document() if yield_input else document();raw=doc.to_dict()
    if mode=='schema':raw['schema']='unknown'
    if mode=='missing':raw.pop('study')
    if mode=='unknown':raw['unexpected']=1
    text=json.dumps(raw)
    if mode=='duplicate':text=text.replace('"ground_modes": 512','"ground_modes": 512, "ground_modes": 512')
    if mode=='nonfinite':text=text.replace('"ground_modes": 512','"ground_modes": NaN')
    with pytest.raises(ValueError):type(doc).loads(text)


@pytest.mark.parametrize('version',[1,2])
def test_yield_requires_matching_nested_version(version):
    raw=yield_document().to_dict();raw['schema']=f'sipi.panel-forward-pair-yield/{version}'
    raw['study']['schema']=f'sipi.panel-forward-pair-study/{3-version}'
    # A smooth source is valid in either study version; the wrapper must still refuse mixing.
    raw['study']['conductor']={'kind':'perfect'}
    with pytest.raises(ValueError,match='matching study version'):
        PanelForwardPairYieldDocument.from_dict(raw)


@pytest.mark.parametrize('change',['core','panel','boundary','budget'])
def test_invalid_sources_or_budget_do_not_mesh(monkeypatch,change):
    doc=document();raw=doc.to_dict()
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('rejected request meshed'))
    if change=='core':raw['conductor']['ground_thickness']=10e-6
    if change=='panel':raw['panel']['panels_per_edge']=257
    if change=='boundary':raw['study']['parameters']['left_thickness']=0
    if change=='budget':
        with pytest.raises(ValueError,match='before any solve'):doc.analyze(max_evaluations=7)
    else:
        with pytest.raises(ValueError):PanelForwardPairStudyDocument.from_dict(raw)


def test_failed_pair_retains_denominator_order_and_later_coated_rows(monkeypatch):
    calls=synthetic(monkeypatch,fail_at=2);doc=document();study=doc.analyze(max_evaluations=8)
    assert len(calls)==len(study.rows)==8 and study.failed==1 and study.summary is None
    np.testing.assert_array_equal([r.sample_values for r in study.rows],source().samples())
    failed=study.rows[1]
    assert failed.phase=='extraction' and failed.error_type=='ArithmeticError' and failed.values is None
    assert failed.input_json==calls[1]
    for row in study.rows:
        raw=json.loads(row.input_json)
        assert raw['schema']=='sipi.panel-transmission-line/2' and raw['line']['schema']=='sipi.transmission-line/7'
        assert raw['line']['conductor']==doc.to_dict()['conductor']
    result=assess_panel_pair_yield(study,acceptance=LIMITS,minimum_yield=.9)
    assert result.unresolved==1 and len(result.classifications)==8
    assert result.sample_fraction_bounds==(result.passed/8,(result.passed+1)/8)
    low=independent_interval(result.passed,8,.95)[0]
    high=independent_interval(result.passed+1,8,.95)[1]
    np.testing.assert_allclose(result.confidence_interval,[low,high],rtol=0,atol=1e-12)


@pytest.fixture(scope='module')
def physical():
    doc=document();return doc,doc.analyze(max_evaluations=8)


def test_actual_correlated_samples_statistics_and_independent_fields(physical,record_property):
    doc,result=physical
    record_property('coated_panel_samples',json.dumps(result.to_dict(),allow_nan=False))
    record_property('coated_panel_sample_fields',json.dumps([snapshot(r.result) for r in result.rows if r.complete],allow_nan=False))
    assert not result.failed and len(result.rows)==8
    np.testing.assert_array_equal([r.sample_values for r in result.rows],doc.samples())
    for i,q in enumerate(Q):
        expected=expected_statistics([row.values[i] for row in result.rows])
        for key,value in expected.items():assert result.summary[q][key]==pytest.approx(value,rel=1e-12)
    for row in result.rows:
        assert row.input_json==factory(*row.sample_values).dumps()
    record_property('coated_panel_sample_references',json.dumps([independent(r.result) for r in result.rows]))


def test_actual_joint_event_uses_one_row_and_exact_binomial_bounds(physical,record_property):
    doc,study=physical;result=assess_panel_pair_yield(study,acceptance=LIMITS,minimum_yield=.9)
    labels=tuple('pass' if 109<=row.values[0]<=111 and 39.75<=row.values[1]<=40.25 else 'fail'
                 for row in study.rows)
    assert result.classifications==labels and not result.unresolved
    np.testing.assert_allclose(result.confidence_interval,independent_interval(labels.count('pass'),8,.95),rtol=0,atol=1e-12)
    record_property('coated_panel_joint_acceptance',json.dumps(result.to_dict(),allow_nan=False))


def test_common_study_and_yield_replay_preserve_actual_inputs(physical,monkeypatch):
    doc,study=physical;fields={row.input_json:row.result for row in study.rows};calls=[]
    def replay(self):
        calls.append(self.dumps());assert self.dumps() in fields
        return fields[self.dumps()]
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',replay)
    for saved,expected in ((doc,study.to_dict()),(yield_document(),
        assess_panel_pair_yield(study,acceptance=LIMITS,minimum_yield=.9).to_dict())):
        calls.clear();out=execute_saved(saved.dumps(),max_evaluations=8)
        assert out['status']=='complete' and out['result']==expected and out['input']==saved.to_dict()
        assert calls==[r.input_json for r in study.rows]


def test_each_actual_sample_keeps_separate_numerical_axes(physical,record_property):
    doc,study=physical;records=[]
    for row in study.rows:
        fields=[row.result]
        for phase in ('volume','panel','joint'):
            raw=json.loads(row.input_json)
            if phase!='panel':
                for key in ('edge_size','far_size','grade'):raw['line']['cross_section']['mesh'][key]/=2
            if phase!='volume':raw['panel']['panels_per_edge']*=2
            fields.append(PanelTransmissionLineDocument.from_dict(raw).analyze())
        values=np.array([np.diag(r.characteristic().mixed_mode().z_characteristic[0]).real for r in fields])
        delta=abs(values[1:]/values[0]-1);joint=abs(values[3]/values[1:3]-1)
        labels=['pass' if 109<=v[0]<=111 and 39.75<=v[1]<=40.25 else 'fail' for v in values]
        records.append(dict(index=row.index,values=values.tolist(),labels=labels,changes=delta.tolist(),
            joint_changes=joint.tolist(),fields=[snapshot(r) for r in fields],
            references=[independent(r) for r in fields[1:]]))
    record_property('coated_panel_sample_refinements',json.dumps(records,allow_nan=False))
    # Manufacturing acceptance is distinct from numerical resolution of each row.
    # These diagonal checks do not certify small mutual resistance entries.
    assert all(max(np.max(r['changes']),np.max(r['joint_changes']))<=.005 for r in records)
