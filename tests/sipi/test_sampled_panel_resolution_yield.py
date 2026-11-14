# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""One manufacturing denominator across frequencies and numerical resolutions."""
from dataclasses import replace, FrozenInstanceError
import itertools
import json
import numpy as np
import pytest
from sipi import CrossSection
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.sampled_panel_pair_study import SampledPanelForwardPairStudyDocument as Document
from sipi.sampled_panel_pair_yield import assess_sampled_panel_pair_yield
from sipi.sampled_panel_resolution_yield import assess_sampled_panel_pair_resolution_yield as assess
from test_sampled_panel_pair_yield import fixture, limits, GOOD, BAD
from test_yield_assessment import independent_interval

VALUES = {'p': GOOD, 'f': BAD, 'u': None}


def study(labels, resolution=0):
    # Explicit statistical records; no physical extraction or accuracy is implied.
    result = fixture([VALUES[label] for label in labels])
    raw = json.loads(result.input_json);raw['panel']['panels_per_edge'] = 32+16*resolution
    return replace(result, input_json=Document.from_dict(raw).dumps())


@pytest.mark.parametrize('resolutions', [2, 3])
def test_full_joint_truth_table_keeps_one_manufactured_trial(resolutions):
    cases = list(itertools.product('pfu', repeat=resolutions))
    result = assess([study([row[i] for row in cases], i) for i in range(resolutions)], acceptance=limits())
    expected = tuple('pass' if all(x=='p' for x in row) else
                     ('fail' if all(x=='f' for x in row) else 'unresolved') for row in cases)
    assert result.classifications == expected
    assert (result.passed, result.failed, result.unresolved) == (1, 1, len(cases)-2)
    out = result.to_dict()
    assert out['count'] == len(cases) and out['resolution_count'] == resolutions
    assert out['frequencies_hz'] == list(result.frequencies)
    assert out['event'] == 'all-sampled-paired-limits-with-resolution-disagreement-unresolved'
    assert out['rows'][0]['labels_by_resolution'] == ['pass']*resolutions
    json.dumps(out, allow_nan=False)


@pytest.mark.parametrize('n', [2, 5, 10])
@pytest.mark.parametrize('confidence', [.5, .9, .95, .999])
def test_independent_binomial_envelope_includes_all_unknown_completions(n, confidence):
    for passed in range(n+1):
        for unknown in range(n-passed+1):
            a = study('p'*passed+'f'*(n-passed))
            b = study('p'*(passed+unknown)+'f'*(n-passed-unknown), 1)
            result = assess([a, b], acceptance=limits(), confidence=confidence)
            expected = [independent_interval(passed,n,confidence)[0], independent_interval(passed+unknown,n,confidence)[1]]
            np.testing.assert_allclose(result.confidence_interval, expected, rtol=0, atol=1e-12)
            for count in range(passed,passed+unknown+1):
                lo,hi=independent_interval(count,n,confidence)
                assert result.confidence_interval[0]<=lo+1e-14 and result.confidence_interval[1]>=hi-1e-14


def test_more_frequency_points_or_resolutions_are_not_independent_trials():
    base=[study('ppff'),study('pfff',1)]
    ordinary=assess(base,acceptance=limits())
    expanded=[]
    for i in range(8):
        old=base[i%2];raw=json.loads(old.input_json)
        grid=np.geomspace(raw['frequency_hz'][0],raw['frequency_hz'][-1],9).tolist()
        raw['frequency_hz']=grid;raw['panel']['panels_per_edge']=32+16*i
        expanded.append(replace(old,input_json=Document.from_dict(raw).dumps(),frequencies=tuple(grid),
            rows=tuple(replace(row,values=None if row.values is None else row.values*3) for row in old.rows)))
    result=assess(expanded,acceptance=limits(9))
    assert result.classifications==ordinary.classifications and result.confidence_interval==ordinary.confidence_interval
    assert result.to_dict()['count']==4 and result.to_dict()['resolution_count']==8
    assert len(result.frequencies)==9


def test_failure_preservation_permutation_and_immutable_arrays(monkeypatch):
    inputs=[study('ppff'),study('pufu',1)];before=[s.to_dict() for s in inputs]
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('comparison meshed'))
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('comparison solved'))
    result=assess(inputs,acceptance=limits(),minimum_yield=.9)
    reverse=assess(inputs[::-1],acceptance=limits(),minimum_yield=.9)
    assert result.classifications==reverse.classifications==('pass','unresolved','fail','unresolved')
    assert result.confidence_interval==reverse.confidence_interval and result.goal_status=='undetermined'
    for i,a in enumerate(result.to_dict()['resolutions']):
        assert a['assessment']==assess_sampled_panel_pair_yield(inputs[i],acceptance=limits(),minimum_yield=.9).to_dict()
    assert [s.to_dict() for s in inputs]==before
    assert result.assessments[1].study.rows[1].error=='retained failure'
    out=result.to_dict();out['acceptance'][next(iter(limits()))]['minimum'][0]=0
    assert result.acceptance[next(iter(limits()))]['minimum'][0]==90.
    with pytest.raises(TypeError):result.acceptance[next(iter(limits()))]['minimum'][0]=0
    with pytest.raises(FrozenInstanceError):result.classifications=()
    inputs.clear();assert len(result.assessments)==2


@pytest.mark.parametrize('count', [0,1,9])
def test_resolution_count_limits(count):
    with pytest.raises(ValueError,match='2..8'):assess([study('pf')]*count,acceptance=limits())


@pytest.mark.parametrize('value', [None,'invalid',[None,None]])
def test_only_sampled_study_results_are_accepted(value):
    with pytest.raises(ValueError):assess(value,acceptance=limits())


def test_duplicate_controls_are_not_extra_numerical_evidence():
    with pytest.raises(ValueError,match='distinct'):assess([study('pf'),study('fp')],acceptance=limits())


@pytest.mark.parametrize('change',['geometry','frequency','dielectric','sampling','schema','order'])
def test_same_physical_source_grid_and_sampling_required(change):
    a=study('ppff');b=study('ppff',1);raw=json.loads(b.input_json)
    if change=='geometry':raw['study']['parameters']['left_width']*=1.01
    if change=='frequency':raw['frequency_hz'][-1]*=1.01
    if change=='dielectric':raw['study']['parameters']['eps_r']=5.
    if change=='sampling':raw['study']['sampling']['seed']+=1
    if change=='schema':raw['schema']='sipi.sampled-panel-forward-pair-study/2'
    if change=='order':raw['study']['sampling']['variables'].reverse()
    b=replace(b,input_json=Document.from_dict(raw).dumps())
    with pytest.raises(ValueError,match='preserve physical inputs'):assess([a,b],acceptance=limits())


@pytest.mark.parametrize('change',['index','missing','values','names','grid','shape','error'])
def test_every_resolution_must_pass_original_row_validation(change):
    a=study('ppff');b=study('ppff',1)
    if change=='index':b=replace(b,rows=(replace(b.rows[0],index=99),*b.rows[1:]))
    if change=='missing':b=replace(b,rows=b.rows[:-1])
    if change=='values':b=replace(b,rows=(replace(b.rows[0],sample_values=(0.,0.)),*b.rows[1:]))
    if change=='names':b=replace(b,variable_names=('changed','gap'))
    if change=='grid':b=replace(b,frequencies=tuple(reversed(b.frequencies)))
    if change=='shape':b=replace(b,rows=(replace(b.rows[0],values=((1.,2.),)),*b.rows[1:]))
    if change=='error':b=replace(b,rows=(replace(b.rows[0],error_type='ArithmeticError'),*b.rows[1:]))
    with pytest.raises(ValueError):assess([a,b],acceptance=limits())


@pytest.mark.parametrize('options',[dict(confidence=0.),dict(confidence=True),dict(minimum_yield=1.1),dict(acceptance={})])
def test_invalid_limits_and_statistical_controls(options):
    args=dict(acceptance=limits());args.update(options)
    with pytest.raises(ValueError):assess([study('pf'),study('pf',1)],**args)


@pytest.mark.parametrize('labels,target,status',[('p'*20,.5,'pass'),('f'*20,.5,'fail'),('pf',.5,'undetermined')])
def test_goal_status_keeps_original_confidence_semantics(labels,target,status):
    result=assess([study(labels),study(labels,1)],acceptance=limits(),minimum_yield=target)
    assert result.goal_status==status


def test_actual_coated_rows_across_frequency_and_resolution(record_property):
    from test_layered_sampled_panel_study import document, LIMITS
    from test_layered_panel_goal import independent, snapshot
    base=document(2).to_dict();studies=[];records=[]
    for phase in ('base','volume','panel','joint'):
        raw=json.loads(json.dumps(base))
        if phase in ('volume','joint'):
            for key in ('edge_size','far_size','grade'):raw['study']['mesh'][key]/=2
        if phase in ('panel','joint'):raw['panel']['panels_per_edge']*=2
        current=Document.from_dict(raw).analyze(max_evaluations=2)
        studies.append(current)
        records.append(dict(phase=phase,input=raw,result=current.to_dict(),
            fields=[snapshot(row.result) for row in current.rows if row.complete]))
        record_property('sampled_resolution_fields',json.dumps(records,allow_nan=False))
        assert not current.failed
        records[-1]['references']=[independent(row.result) for row in current.rows]
    values=np.array([[row.values for row in s.rows] for s in studies])
    assert np.all(abs(values[1:]/values[0]-1)<=.005)
    assert np.all(abs(values[3]/values[1:3]-1)<=.005)
    result=assess(studies,acceptance=LIMITS,minimum_yield=.9)
    per_resolution=[assess_sampled_panel_pair_yield(s,acceptance=LIMITS,minimum_yield=.9) for s in studies]
    labels=[]
    for i in range(2):
        resolved=[a.classifications[i] for a in per_resolution]
        labels.append('pass' if all(x=='pass' for x in resolved) else
                      ('fail' if all(x=='fail' for x in resolved) else 'unresolved'))
    assert result.classifications==tuple(labels) and result.to_dict()['count']==2
    np.testing.assert_allclose(result.confidence_interval,
        [independent_interval(labels.count('pass'),2,.95)[0],
         independent_interval(labels.count('pass')+labels.count('unresolved'),2,.95)[1]],rtol=0,atol=1e-12)
    assert all(a.to_dict()==b.to_dict() for a,b in zip(result.assessments,per_resolution))
    record_property('sampled_resolution_references',json.dumps([r['references'] for r in records]))
    record_property('sampled_resolution_assessment',json.dumps(result.to_dict(),allow_nan=False))
