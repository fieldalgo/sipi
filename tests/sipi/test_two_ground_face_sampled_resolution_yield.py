# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""One manufacturing denominator across frequencies and numerical resolutions."""
from dataclasses import replace, FrozenInstanceError
import itertools
import json
import numpy as np
import pytest
from sipi import CrossSection
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument as PanelTransmissionLineDocument
from sipi.two_ground_face_sampled_pair_study import TwoGroundFaceSampledForwardPairStudyDocument as Document
from sipi.two_ground_face_sampled_pair_yield import assess_two_ground_face_sampled_pair_yield
from sipi.two_ground_face_sampled_resolution_yield import assess_two_ground_face_sampled_pair_resolution_yield as assess
from test_two_ground_face_sampled_pair_yield import fixture, limits, GOOD, BAD
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
        assert a['assessment']==assess_two_ground_face_sampled_pair_yield(inputs[i],acceptance=limits(),minimum_yield=.9).to_dict()
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


@pytest.mark.parametrize('change',['geometry','frequency','dielectric','sampling','order','face','ground','thickness','box'])
def test_same_physical_source_grid_and_sampling_required(change):
    a=study('ppff');b=study('ppff',1);raw=json.loads(b.input_json)
    if change=='geometry':raw['study']['parameters']['width']*=1.01
    if change=='frequency':raw['frequency_hz'][-1]*=1.01
    if change=='dielectric':raw['study']['parameters']['eps_r']=5.
    if change=='sampling':raw['study']['sampling']['seed']+=1
    if change=='order':raw['study']['sampling']['variables'].reverse()
    if change=='face':raw['conductors']['positive']['top']['conductivity']*=.9
    if change=='ground':raw['reference']['top']['conductivity']*=.9
    if change=='thickness':raw['ground_thickness_m']*=1.1
    if change=='box':raw['study']['parameters']['box_width']*=2
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


def test_registered_face_debye_rows_have_independent_axes_and_joint_labels(record_property):
    from scipy.linalg import sqrtm
    from sipi.constants import mu_0,epsilon_0
    from test_two_ground_face_sampled_pair_study import physical_document, Q
    raw=physical_document().to_dict();raw['study']['sampling'].update(kind='uniform',count=2,seed=19)
    base=Document.from_dict(raw);studies=[];observations=[]
    transform=np.array([[1.,-1.],[.5,.5]])
    for phase in ('base','volume','panel','joint'):
        raw=base.to_dict()
        if phase in ('volume','joint'):
            for key in ('edge_size','far_size','grade'):raw['study']['mesh'][key]*=.5
        if phase in ('panel','joint'):raw['panel'].update(panels_per_edge=128,ground_modes=256)
        doc=Document.from_dict(raw);np.testing.assert_array_equal(doc.samples(),base.samples())
        current=doc.analyze(max_evaluations=2);studies.append(current)
        record_property('face_resolution_study_'+phase,json.dumps(current.to_dict(),sort_keys=True))
        assert not current.failed and len(current.rows)==2
        fields=[]
        for row in current.rows:
            line=row.result;c0=line.current_factors.C0
            field=dict(R=line.R,L_internal=line.conductor.L_internal,L_external=line.dielectric.L,
                       C=line.C,G=line.G,C0=c0)
            fields.append({key:np.asarray(value).tolist() for key,value in field.items()})
            record_property('face_resolution_fields_'+phase+'_'+str(row.index),json.dumps(fields[-1],sort_keys=True))
            for i,f in enumerate(line.frequency):
                omega=2*np.pi*f;z=line.R[i]+1j*omega*line.L[i];y=line.G[i]+1j*omega*line.C[i]
                gamma=np.asarray(sqrtm(z@y),dtype=complex)
                independent=np.diag(transform@np.linalg.solve(gamma,z)@transform.T).real
                np.testing.assert_allclose(row.values[i],independent,rtol=1e-10,atol=0)
                eps=3.+.7/(1+1j*f/1e9)
                np.testing.assert_allclose(line.C[i],eps.real*c0,rtol=.005,atol=0)
                np.testing.assert_allclose(line.G[i],omega*(-eps.imag)*c0,rtol=.005,atol=0)
                np.testing.assert_allclose(line.dielectric.L@c0,mu_0*epsilon_0*np.eye(2),rtol=1e-12,atol=1e-28)
        observations.append(fields)
    for left,right in ((0,1),(0,2),(0,3),(1,3),(2,3)):
        for a,b in zip(observations[left],observations[right]):
            for key in a:
                x,y=np.array(a[key]),np.array(b[key])
                assert np.all(abs(x-y)<=.01*np.maximum(abs(x),abs(y))),(left,right,key,x,y)
    acceptance={q:dict(minimum=[lo]*3,maximum=[hi]*3) for q,lo,hi in zip(Q,[100.,50.],[103.,52.])}
    result=assess(studies,acceptance=acceptance,minimum_yield=.8)
    record_property('face_resolution_joint_assessment',json.dumps(result.to_dict(),sort_keys=True))
    classifications=[]
    for index in range(2):
        labels=[]
        for study_result in studies:
            row=study_result.rows[index]
            assert row.sample_values==tuple(base.samples()[index])
            labels.append('pass' if all(acceptance[q]['minimum'][f]<=pair[i]<=acceptance[q]['maximum'][f]
                for f,pair in enumerate(row.values) for i,q in enumerate(Q)) else 'fail')
        classifications.append('pass' if all(x=='pass' for x in labels) else
                               ('fail' if all(x=='fail' for x in labels) else 'unresolved'))
        assert result.to_dict()['rows'][index]['labels_by_resolution']==labels
    assert result.classifications==tuple(classifications) and result.to_dict()['count']==2
    expected=[independent_interval(classifications.count('pass'),2,.95)[0],
              independent_interval(classifications.count('pass')+classifications.count('unresolved'),2,.95)[1]]
    np.testing.assert_allclose(result.confidence_interval,expected,rtol=0,atol=1e-12)


@pytest.mark.parametrize('which',['whole','generic'])
def test_other_current_method_is_not_reinterpreted(which):
    if which=='whole':from test_two_ground_sampled_pair_yield import fixture as other_fixture
    else:from test_sampled_panel_pair_yield import fixture as other_fixture
    with pytest.raises(ValueError):assess([study('pf'),other_fixture([GOOD,BAD])],acceptance=limits())


@pytest.mark.parametrize('kind',['corners','sweep'])
def test_non_iid_rejected_even_when_resolution_controls_differ(kind):
    records=[fixture([GOOD,BAD],kind=kind),fixture([GOOD,BAD],kind=kind)]
    raw=json.loads(records[1].input_json);raw['panel']['panels_per_edge']*=2
    records[1]=replace(records[1],input_json=Document.from_dict(raw).dumps())
    with pytest.raises(ValueError):assess(records,acceptance=limits())
