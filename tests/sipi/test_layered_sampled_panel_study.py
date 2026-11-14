# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Fixed coatings, one manufactured row across frequencies, and original counts."""
import json
import numpy as np
import pytest
from sipi import CrossSection
from sipi.study import ImpedanceStudyDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.sampled_panel_pair_study import SampledPanelForwardPairStudyDocument as StudyDocument
from sipi.sampled_panel_pair_yield import SampledPanelForwardPairYieldDocument as YieldDocument, assess_sampled_panel_pair_yield
from sipi.sampled_panel_pair_selection import SampledPanelForwardPairSelectionDocument
from sipi.execution import execute_saved,normalize_saved
from sipi.dielectric import TabulatedDielectric,dielectric_to_dict
from test_layered_panel_study import source as old_source,Q
from test_layered_sampled_panel_goal import factory,FREQUENCIES
from test_layered_panel_goal import independent,snapshot
from test_sampled_panel_pair_goal import synthetic
from test_panel_pair_study import expected_statistics
from test_yield_assessment import independent_interval

MEAN=(.0006050501120606677,.0004089487094424394)
LIMITS={q:dict(minimum=[lo]*3,maximum=[hi]*3) for q,lo,hi in zip(Q,[109.,39.75],[111.,40.25])}


def source(count=8):
    raw=old_source().to_dict();raw['parameters'].update(left_width=MEAN[0],gap=MEAN[1])
    raw['sampling']['count']=count
    for entry,value in zip(raw['sampling']['variables'],MEAN):entry['mean']=value
    return ImpedanceStudyDocument.from_dict(raw)


def document(count=8):
    return StudyDocument(source(count),conductor=factory(*MEAN).to_dict()['line']['conductor'],
        frequencies=FREQUENCIES,schema='sipi.sampled-panel-forward-pair-study/2')


def yield_document(count=8):
    return YieldDocument(document(count),acceptance=LIMITS,minimum_yield=.9,
                         schema='sipi.sampled-panel-forward-pair-yield/2')


def test_field_free_versions_and_copy_isolation(monkeypatch):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('normalization meshed'))
    for doc in (document(),yield_document()):
        text=doc.dumps();assert normalize_saved(text)==text==type(doc).loads(text).dumps()
        raw=doc.to_dict();raw['schema']='changed';assert doc.dumps()==text
    np.testing.assert_array_equal(document().samples(),source().samples())
    with pytest.raises(ValueError):StudyDocument(source(),conductor=document().to_dict()['conductor'],frequencies=FREQUENCIES)
    with pytest.raises(ValueError):YieldDocument(document(),acceptance=LIMITS)


@pytest.mark.parametrize('is_yield',[False,True])
@pytest.mark.parametrize('change',['schema','missing','extra','duplicate','nan'])
def test_strict_saved_inputs(is_yield,change):
    doc=yield_document() if is_yield else document();raw=doc.to_dict()
    if change=='schema':raw['schema']='unsupported'
    if change=='missing':raw.pop('study')
    if change=='extra':raw['unexpected']=1
    text=json.dumps(raw)
    if change=='duplicate':text=text.replace('"ground_modes": 512','"ground_modes": 512, "ground_modes": 512')
    if change=='nan':text=text.replace('"ground_modes": 512','"ground_modes": NaN')
    with pytest.raises(ValueError):type(doc).loads(text)


@pytest.mark.parametrize('version',[1,2])
def test_yield_matching_version_even_for_perfect_conductors(version):
    raw=yield_document().to_dict();raw['schema']=f'sipi.sampled-panel-forward-pair-yield/{version}'
    raw['study']['schema']=f'sipi.sampled-panel-forward-pair-study/{3-version}'
    raw['study']['conductor']={'kind':'perfect'}
    with pytest.raises(ValueError,match='matching study version'):YieldDocument.from_dict(raw)


@pytest.mark.parametrize('change',['band','core','anchor','panel','budget'])
def test_whole_grid_and_row_budget_admission_before_fields(monkeypatch,change):
    doc=document();raw=doc.to_dict()
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('invalid input meshed'))
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('invalid input analyzed'))
    if change=='band':raw['study']['material_evaluation']['materials']['substrate']=dielectric_to_dict(
        TabulatedDielectric((1e9,2e9),(4.,4.),(.02,.02)))
    if change=='core':raw['conductor']['ground_thickness']=10e-6
    if change=='anchor':raw['study']['material_evaluation']['frequency_hz']=2e9
    if change=='panel':raw['panel']['panels_per_edge']=257
    if change=='budget':
        with pytest.raises(ValueError,match='before any solve'):doc.analyze(max_evaluations=7)
        with pytest.raises(ValueError):execute_saved(yield_document().dumps(),max_evaluations=7)
    else:
        with pytest.raises(ValueError):StudyDocument.from_dict(raw)


@pytest.mark.parametrize('phase',['parameters','materials','input','extraction','diagnostic'])
def test_atomic_failure_keeps_later_whole_grid_rows_and_original_denominator(monkeypatch,phase):
    import sipi.sampled_panel_pair_study as module
    calls=synthetic(monkeypatch,fail_at=2 if phase=='extraction' else None)
    if phase in ('parameters','materials','input'):
        name=dict(parameters='_parameters',materials='_sample_material',input='_line_from_inputs')[phase]
        original=getattr(module,name);seen=[]
        def broken(*args,**kwargs):
            seen.append(1)
            if len(seen)==2:raise ArithmeticError('retained whole-grid failure')
            return original(*args,**kwargs)
        monkeypatch.setattr(module,name,broken)
    elif phase=='diagnostic':
        original=PanelTransmissionLineDocument.analyze;seen=[]
        def broken(self):
            result=original(self);seen.append(1)
            if len(seen)==2:
                def fail():raise ArithmeticError('retained diagnostic failure')
                result.characteristic=fail
            return result
        monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',broken)
    doc=document();study=doc.analyze(max_evaluations=8)
    assert len(study.rows)==8 and study.failed==1 and study.summary is None
    failed=study.rows[1];assert failed.phase==phase and failed.values is None and failed.error_type=='ArithmeticError'
    assert study.rows[-1].complete and len(study.rows[-1].values)==3
    np.testing.assert_array_equal([r.sample_values for r in study.rows],doc.samples())
    for row in study.rows:
        if row.input_json is not None:
            data=json.loads(row.input_json)
            assert data['line']['frequency_hz']==FREQUENCIES and data['line']['conductor']==doc.to_dict()['conductor']
            assert data['schema']=='sipi.panel-transmission-line/2' and data['line']['schema']=='sipi.transmission-line/7'
    result=assess_sampled_panel_pair_yield(study,acceptance=LIMITS,minimum_yield=.9)
    assert result.unresolved==1 and result.to_dict()['count']==8
    expected=(independent_interval(result.passed,8,.95)[0],independent_interval(result.passed+1,8,.95)[1])
    np.testing.assert_allclose(result.confidence_interval,expected,rtol=0,atol=1e-12)


@pytest.fixture(scope='module')
def physical():
    doc=document(2);return doc,doc.analyze(max_evaluations=2)


def test_actual_row_grid_statistics_joint_event_and_independent_fields(physical,record_property):
    doc,study=physical
    record_property('coated_sampled_study',json.dumps(study.to_dict(),allow_nan=False))
    record_property('coated_sampled_study_fields',json.dumps([snapshot(r.result) for r in study.rows if r.complete],allow_nan=False))
    assert not study.failed and len(study.rows)==2
    np.testing.assert_array_equal([r.sample_values for r in study.rows],doc.samples())
    for row in study.rows:assert row.input_json==factory(*row.sample_values).dumps()
    for f in range(3):
        for i,q in enumerate(Q):
            for key,value in expected_statistics([row.values[f][i] for row in study.rows]).items():
                assert study.summary[q][f][key]==pytest.approx(value,rel=1e-12)
    result=assess_sampled_panel_pair_yield(study,acceptance=LIMITS,minimum_yield=.9)
    labels=tuple('pass' if all(109<=dd<=111 and 39.75<=cc<=40.25 for dd,cc in row.values) else 'fail' for row in study.rows)
    assert result.classifications==labels and not result.unresolved
    np.testing.assert_allclose(result.confidence_interval,independent_interval(labels.count('pass'),2,.95),rtol=0,atol=1e-12)
    record_property('coated_sampled_joint_acceptance',json.dumps(result.to_dict(),allow_nan=False))
    record_property('coated_sampled_study_references',json.dumps([independent(r.result) for r in study.rows]))


def test_actual_rows_keep_separate_resolution_axes(physical,record_property):
    doc,study=physical;records=[]
    for row in study.rows:
        fields=[row.result]
        for phase in ('volume','panel','joint'):
            raw=json.loads(row.input_json)
            if phase in ('volume','joint'):
                for key in ('edge_size','far_size','grade'):raw['line']['cross_section']['mesh'][key]/=2
            if phase in ('panel','joint'):raw['panel']['panels_per_edge']*=2
            fields.append(PanelTransmissionLineDocument.from_dict(raw).analyze())
        values=np.array([np.diagonal(r.characteristic().mixed_mode().z_characteristic,axis1=1,axis2=2).real for r in fields])
        records.append(dict(index=row.index,fields=[snapshot(r) for r in fields],values=values.tolist()))
        record_property('coated_sampled_resolution_fields',json.dumps(records,allow_nan=False))
        assert np.all(abs(values[1:]/values[0]-1)<=.005)
        assert np.all(abs(values[3]/values[1:3]-1)<=.005)
        records[-1]['references']=[independent(r) for r in fields]
    record_property('coated_sampled_resolution_references',json.dumps([r['references'] for r in records]))


def test_sample_width_extremes_keep_finite_outer_gates(record_property):
    samples=source().samples();indices=[int(np.argmin(samples[:,0])),int(np.argmax(samples[:,0]))];records=[]
    for index in indices:
        fields=[]
        for box,air,modes in ((.024,.010,512),(.036,.015,768),(.048,.020,1024)):
            raw=factory(*samples[index],box=box,air=air).to_dict()
            for key in ('edge_size','far_size','grade'):raw['line']['cross_section']['mesh'][key]/=2
            raw['panel'].update(panels_per_edge=64,ground_modes=modes)
            fields.append(PanelTransmissionLineDocument.from_dict(raw).analyze())
        values=np.array([np.diagonal(r.characteristic().mixed_mode().z_characteristic,axis1=1,axis2=2).real for r in fields])
        changes=abs(np.diff(values,axis=0))
        records.append(dict(index=index,sample=samples[index].tolist(),values=values.tolist(),
            changes=changes.tolist(),fields=[snapshot(r) for r in fields]))
        record_property('coated_sampled_outer_fields',json.dumps(records,allow_nan=False))
        assert np.all(changes[:,:,0]<=1e-4*values[0,:,0])
        assert np.all(changes[1,:,1]<changes[0,:,1])
        records[-1]['references']=[independent(r) for r in fields]
    record_property('coated_sampled_outer_references',json.dumps([r['references'] for r in records]))


def test_actual_common_replay_and_explicit_selection_child_contract(physical,monkeypatch):
    doc,study=physical;fields={row.input_json:row.result for row in study.rows};calls=[]
    def replay(self):calls.append(self.dumps());return fields[self.dumps()]
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',replay)
    result=assess_sampled_panel_pair_yield(study,acceptance=LIMITS,minimum_yield=.9)
    for saved,expected in ((doc,study.to_dict()),(yield_document(2),result.to_dict())):
        calls.clear();out=execute_saved(saved.dumps(),max_evaluations=2)
        assert out['status']=='complete' and out['error'] is None
        assert out['input']==saved.to_dict() and out['result']==expected
        assert calls==[r.input_json for r in study.rows]
    selection=SampledPanelForwardPairSelectionDocument(
        [dict(name='first',cost=1.,study=doc.to_dict()),dict(name='second',cost=0.,study=doc.to_dict())],
        cost_unit='relative-cost',acceptance=LIMITS,minimum_yield=.9)
    calls.clear()
    with pytest.raises(ValueError):selection.analyze(max_evaluations=3)
    assert not calls
    selected=selection.analyze(max_evaluations=4)
    assert len(calls)==4 and selected.selected_index is None and selected.status=='undetermined'
    assert all(c.assessment.study.input_json==doc.dumps() for c in selected.candidates)
    for candidate in selected.candidates:
        a=candidate.assessment
        np.testing.assert_allclose(a.confidence_interval,independent_interval(a.passed,2,selected.candidate_confidence),rtol=0,atol=1e-12)
    calls.clear();out=execute_saved(selection.dumps(),max_evaluations=4)
    assert len(calls)==4 and out['result']==selected.to_dict() and out['input']==selection.to_dict()
