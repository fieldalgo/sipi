# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Finite resolution disagreements, one iid denominator and independent tails."""
from dataclasses import replace, FrozenInstanceError
import itertools
import json
import numpy as np
import pytest
from sipi import CrossSection
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.panel_pair_study import PanelForwardPairStudyDocument
from sipi.panel_pair_yield import assess_panel_pair_yield
from sipi.panel_resolution_yield import assess_panel_pair_resolution_yield as assess
from test_panel_pair_yield import fixture, LIMITS
from test_yield_assessment import independent_interval

VALUES = {'p':(100.,40.),'f':(200.,40.),'u':None}


def study(labels, resolution=0):
    # A statistical fixture only; this does not pretend to extract physical fields.
    result=fixture([VALUES[label] for label in labels])
    raw=json.loads(result.input_json);raw['panel']['panels_per_edge']=32+16*resolution
    doc=PanelForwardPairStudyDocument.from_dict(raw)
    return replace(result,input_json=doc.dumps())


@pytest.mark.parametrize('resolutions',[2,3])
def test_joint_truth_table_and_single_denominator(resolutions):
    cases=list(itertools.product('pfu',repeat=resolutions))
    studies=[study([row[i] for row in cases],i) for i in range(resolutions)]
    result=assess(studies,acceptance=LIMITS,minimum_yield=.8)
    expected=tuple('pass' if all(x=='p' for x in row) else
                   ('fail' if all(x=='f' for x in row) else 'unresolved') for row in cases)
    assert result.classifications==expected
    assert (result.passed,result.failed,result.unresolved)==(1,1,len(cases)-2)
    assert result.sample_fraction_bounds==(1/len(cases),(len(cases)-1)/len(cases))
    data=result.to_dict();assert data['count']==len(cases) and data['resolution_count']==resolutions
    assert [r['labels_by_resolution'] for r in data['rows']]==[
        [a.classifications[i] for a in result.assessments] for i in range(len(cases))]
    assert data['scope']=='iid-finite-resolution-envelope-not-a-discretization-error-bound'
    json.dumps(data,allow_nan=False)


@pytest.mark.parametrize('n',[2,5,10])
@pytest.mark.parametrize('confidence',[.5,.9,.95,.999])
def test_independent_binomial_envelope_for_every_possible_completion(n,confidence):
    for passed in range(n+1):
        for unknown in range(n-passed+1):
            a='p'*passed+'f'*(n-passed)
            b='p'*(passed+unknown)+'f'*(n-passed-unknown)
            result=assess([study(a),study(b,1)],acceptance=LIMITS,confidence=confidence)
            low=independent_interval(passed,n,confidence)[0]
            high=independent_interval(passed+unknown,n,confidence)[1]
            np.testing.assert_allclose(result.confidence_interval,[low,high],rtol=0,atol=1e-12)
            for completed in range(passed,passed+unknown+1):
                interval=independent_interval(completed,n,confidence)
                assert result.confidence_interval[0]<=interval[0]+1e-14
                assert result.confidence_interval[1]>=interval[1]-1e-14


def test_any_original_failed_row_keeps_errors_and_unknown_state():
    inputs=[study('ppff'),study('pufu',1)]
    before=[r.to_dict() for r in inputs]
    result=assess(inputs,acceptance=LIMITS,minimum_yield=.9)
    assert result.classifications==('pass','unresolved','fail','unresolved')
    assert result.sample_fraction_bounds==(.25,.75) and result.goal_status=='undetermined'
    for i,resolution in enumerate(result.to_dict()['resolutions']):
        assert resolution['assessment']==assess_panel_pair_yield(inputs[i],acceptance=LIMITS,minimum_yield=.9).to_dict()
    assert [r.to_dict() for r in inputs]==before
    assert result.assessments[1].study.rows[1].error=='retained failure'


def test_no_fields_no_mutation_and_resolution_permutation(monkeypatch):
    inputs=[study('ppff'),study('pfff',1)];before=[s.to_dict() for s in inputs]
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('comparison meshed'))
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('comparison solved'))
    result=assess(inputs,acceptance=LIMITS)
    reverse=assess(inputs[::-1],acceptance=LIMITS)
    assert result.classifications==reverse.classifications
    assert result.confidence_interval==reverse.confidence_interval
    assert result.goal_status=='not-requested'
    output=result.to_dict();output['resolutions'][0]['input']['panel']['panels_per_edge']=256
    assert result.assessments[0].study.input_json==inputs[0].input_json
    inputs.clear();assert len(result.assessments)==2
    assert [a.study.to_dict() for a in result.assessments]==before
    with pytest.raises(FrozenInstanceError):result.classifications=()
    with pytest.raises(TypeError):result.acceptance[next(iter(LIMITS))]['minimum']=0


@pytest.mark.parametrize('count',[0,1,9])
def test_bounded_resolution_count(count):
    with pytest.raises(ValueError,match='2..8'):assess([study('pf')]*count,acceptance=LIMITS)


@pytest.mark.parametrize('inputs',[None,'invalid',[None,None]])
def test_nonstudy_inputs_refused(inputs):
    with pytest.raises(ValueError):assess(inputs,acceptance=LIMITS)


def test_duplicate_controls_are_not_extra_resolution_evidence():
    with pytest.raises(ValueError,match='distinct'):assess([study('pf'),study('fp')],acceptance=LIMITS)


@pytest.mark.parametrize('change',['geometry','frequency','dielectric','sampling','schema','order'])
def test_physics_and_sampling_cannot_change(change):
    first=study('ppff');second=study('ppff',1);raw=json.loads(second.input_json)
    if change=='geometry':raw['study']['parameters']['left_width']*=1.01
    if change=='frequency':raw['study']['material_evaluation']['frequency_hz']*=2
    if change=='dielectric':raw['study']['parameters']['eps_r']=5.
    if change=='sampling':raw['study']['sampling']['seed']+=1
    if change=='schema':raw['schema']='sipi.panel-forward-pair-study/2'
    if change=='order':raw['study']['sampling']['variables'].reverse()
    second=replace(second,input_json=PanelForwardPairStudyDocument.from_dict(raw).dumps())
    with pytest.raises(ValueError,match='preserve physical inputs and sampling'):
        assess([first,second],acceptance=LIMITS)


@pytest.mark.parametrize('change',['index','missing','values','names'])
def test_original_row_validation_is_required_for_every_resolution(change):
    first=study('ppff');second=study('ppff',1)
    if change=='index':second=replace(second,rows=(replace(second.rows[0],index=99),*second.rows[1:]))
    if change=='missing':second=replace(second,rows=second.rows[:-1])
    if change=='values':second=replace(second,rows=(replace(second.rows[0],sample_values=(0.,0.)),*second.rows[1:]))
    if change=='names':second=replace(second,variable_names=('changed','gap'))
    with pytest.raises(ValueError):assess([first,second],acceptance=LIMITS)


@pytest.mark.parametrize('options',[dict(confidence=0.),dict(confidence=True),dict(minimum_yield=1.1),
                                     dict(acceptance={})])
def test_bad_statistical_controls_refused(options):
    args=dict(acceptance=LIMITS);args.update(options)
    with pytest.raises(ValueError):assess([study('pf'),study('pf',1)],**args)


@pytest.mark.parametrize('labels,target,expected',[('p'*20,.5,'pass'),('f'*20,.5,'fail'),('pf',.5,'undetermined')])
def test_requested_goal_retains_conservative_interval_semantics(labels,target,expected):
    result=assess([study(labels),study(labels,1)],acceptance=LIMITS,minimum_yield=target)
    assert result.goal_status==expected


def test_eight_resolutions_still_count_samples_once():
    result=assess([study('ppff',i) for i in range(8)],acceptance=LIMITS)
    assert len(result.assessments)==8 and result.to_dict()['count']==4
    assert result.sample_fraction_bounds==(.5,.5)


def test_actual_boundary_sample_is_unresolved_without_altering_nominal_yield(record_property):
    from test_layered_panel_study import document, LIMITS as physical_limits
    from test_layered_panel_goal import independent,snapshot
    base=document().to_dict();base['study']['sampling']['count']=2
    studies=[];references=[]
    for phase in ('base','volume','panel','joint'):
        raw=json.loads(json.dumps(base))
        if phase in ('volume','joint'):
            for key in ('edge_size','far_size','grade'):raw['study']['mesh'][key]/=2
        if phase in ('panel','joint'):raw['panel']['panels_per_edge']*=2
        result=PanelForwardPairStudyDocument.from_dict(raw).analyze(max_evaluations=2)
        assert not result.failed;studies.append(result)
        references.append([independent(row.result) for row in result.rows])
    result=assess(studies,acceptance=physical_limits,minimum_yield=.9)
    record_property('actual_resolution_labels',json.dumps(result.to_dict(),allow_nan=False))
    record_property('actual_resolution_fields',json.dumps([[snapshot(r.result) for r in s.rows] for s in studies],allow_nan=False))
    record_property('actual_resolution_references',json.dumps(references))
    assert result.classifications==('unresolved','pass')
    assert result.sample_fraction_bounds==(.5,1.) and result.to_dict()['count']==2
    nominal=assess_panel_pair_yield(studies[0],acceptance=physical_limits,minimum_yield=.9)
    assert nominal.classifications==('fail','pass') and nominal.sample_fraction_bounds==(.5,.5)
    np.testing.assert_allclose(result.confidence_interval,[independent_interval(1,2,.95)[0],1.],rtol=0,atol=1e-12)
