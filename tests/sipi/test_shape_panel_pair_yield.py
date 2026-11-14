# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent joint-event statistics, unknown rows and explicit saved method."""
from dataclasses import replace
import json
import numpy as np
import pytest
from sipi import CrossSection
from sipi.shape_panel_pair_study import (ShapePanelForwardPairStudyDocument,
    ShapePanelForwardPairStudy, ShapePanelForwardPairStudyRow)
from sipi.shape_panel_pair_yield import (ShapePanelForwardPairYieldDocument,
    assess_shape_panel_pair_yield)
from sipi.shape_panel_line import ShapePanelTransmissionLineDocument
from sipi.panel_pair_yield import assess_panel_pair_yield,PanelForwardPairYieldDocument
from sipi.execution import normalize_saved
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from test_execution_record import ARTIFACTS
from test_panel_pair_yield import random_document,LIMITS,Q
from test_yield_assessment import independent_interval
from test_shape_panel_pair_goal_document import synthetic_transport


def document():
    return ShapePanelForwardPairYieldDocument(ShapePanelForwardPairStudyDocument(random_document()),
        acceptance=LIMITS,minimum_yield=.8)


def fixture(values,kind='uniform'):
    source=ShapePanelForwardPairStudyDocument(random_document(len(values),kind))
    # Statistical rows have no fabricated field evidence.
    rows=tuple(ShapePanelForwardPairStudyRow(i,tuple(sample),None,None,None,value,
        'complete' if value is not None else 'diagnostic',
        None if value is not None else 'ArithmeticError',
        None if value is not None else 'retained unknown')
        for i,(sample,value) in enumerate(zip(source.samples(),values)))
    return ShapePanelForwardPairStudy(source.dumps(),
        tuple(v['name'] for v in source.study.to_dict()['study']['sampling']['variables']),rows,None)


def test_joint_truth_table_preserves_identity_rows_and_denominator():
    study=fixture([(90.,35.),(110.,45.),(80.,40.),(100.,50.),(80.,50.),None])
    result=assess_shape_panel_pair_yield(study,acceptance=LIMITS,minimum_yield=.8)
    assert result.study is study and result.classifications==('pass','pass','fail','fail','fail','unresolved')
    assert (result.passed,result.failed,result.unresolved)==(2,3,1)
    assert result.sample_fraction_bounds==(2/6,3/6) and result.goal_status=='undetermined'
    report=result.to_dict();assert report['scope']=='iid-stated-shape-current-distribution-not-measured-production-yield'
    assert report['sampling_model']==json.loads(study.input_json)['study']['study']['sampling']
    assert report['rows']==[dict(row.to_dict(),classification=label) for row,label in zip(study.rows,result.classifications)]
    assert all(row['current_solver'] is None for row in report['rows'])
    with pytest.raises(TypeError):result.acceptance[Q[0]]['minimum']=0
    with pytest.raises(ValueError):assess_panel_pair_yield(study,acceptance=LIMITS)


def test_joint_count_is_not_the_product_of_marginals():
    a=assess_shape_panel_pair_yield(fixture([(100.,80.),(200.,40.)]),acceptance=LIMITS)
    b=assess_shape_panel_pair_yield(fixture([(100.,40.),(200.,80.)]),acceptance=LIMITS)
    assert a.passed==0 and b.passed==1


@pytest.mark.parametrize('count',[2,5,20])
@pytest.mark.parametrize('confidence',[.5,.9,.95,.999])
def test_independent_finite_binomial_tail_inversion(count,confidence):
    for passed in range(count+1):
        result=assess_shape_panel_pair_yield(fixture([(100.,40.)]*passed+[(200.,40.)]*(count-passed)),acceptance=LIMITS,confidence=confidence)
        np.testing.assert_allclose(result.confidence_interval,independent_interval(passed,count,confidence),rtol=0,atol=1e-12)


def test_all_unknown_completions_are_enclosed_and_extreme_counts_match_scipy():
    from scipy.stats import binomtest
    for passed in range(6):
        for unknown in range(6-passed):
            result=assess_shape_panel_pair_yield(fixture([(100.,40.)]*passed+[None]*unknown+[(200.,40.)]*(5-passed-unknown)),acceptance=LIMITS)
            for k in range(passed,passed+unknown+1):
                low,high=independent_interval(k,5,.95)
                assert result.confidence_interval[0]<=low+1e-14 and result.confidence_interval[1]>=high-1e-14
    for count,passed in ((2,0),(2,2),(50,17),(1000,999)):
        result=assess_shape_panel_pair_yield(fixture([(100.,40.)]*passed+[(200.,40.)]*(count-passed)),acceptance=LIMITS)
        ref=binomtest(passed,count).proportion_ci(confidence_level=.95,method='exact')
        np.testing.assert_allclose(result.confidence_interval,[ref.low,ref.high],rtol=0,atol=1e-12)


@pytest.mark.parametrize('kind',['sweep','corners'])
def test_non_iid_admission_precedes_fields(monkeypatch,kind):
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('non-iid solved'))
    with pytest.raises(ValueError,match='iid'):
        ShapePanelForwardPairYieldDocument(ShapePanelForwardPairStudyDocument(random_document(kind=kind)),acceptance=LIMITS)
    with pytest.raises(ValueError,match='iid'):assess_shape_panel_pair_yield(fixture([(100.,40.)]*4,kind),acceptance=LIMITS)


@pytest.mark.parametrize('change',[dict(index=True),dict(index=1),dict(sample_values=(True,.2e-3)),
    dict(sample_values=(0.,0.)),dict(values=(0.,40.)),dict(values=(100.,float('nan'))),
    dict(values=(True,40.)),dict(values=(100.,)),dict(values=[100.,40.]),dict(values=None),
    dict(phase='diagnostic'),dict(error_type='ValueError')])
def test_corrupt_completed_row_refused(change):
    study=fixture([(100.,40.)]*4);study=replace(study,rows=(replace(study.rows[0],**change),)+study.rows[1:])
    with pytest.raises(ValueError):assess_shape_panel_pair_yield(study,acceptance=LIMITS)


@pytest.mark.parametrize('change',[dict(values=(100.,40.)),dict(error_type=None),dict(phase='complete'),dict(error=7)])
def test_corrupt_unresolved_row_refused(change):
    study=fixture([None]*4);study=replace(study,rows=(replace(study.rows[0],**change),)+study.rows[1:])
    with pytest.raises(ValueError):assess_shape_panel_pair_yield(study,acceptance=LIMITS)


def test_missing_reordered_or_changed_sampling_rows_rejected():
    study=fixture([(100.,40.)]*4)
    for broken in (None,replace(study,rows=study.rows[:3]),replace(study,rows=study.rows[::-1]),
                   replace(study,variable_names=('wrong',)),replace(study,input_json=random_document().dumps())):
        with pytest.raises(ValueError):assess_shape_panel_pair_yield(broken,acceptance=LIMITS)


@pytest.mark.parametrize('kind',['schema','missing','extra','duplicate','nan','old-study','non-iid'])
def test_strict_input_contract(kind):
    raw=document().to_dict();text=json.dumps(raw)
    if kind=='schema':raw['schema']='sipi.shape-panel-forward-pair-yield/2'
    if kind=='missing':raw.pop('confidence')
    if kind=='extra':raw['extra']=1
    if kind=='duplicate':text=text.replace('"confidence": 0.95','"confidence": 0.95, "confidence": 0.95')
    if kind=='nan':text=text.replace('"confidence": 0.95','"confidence": NaN')
    if kind=='old-study':raw['study']=raw['study']['study']
    if kind=='non-iid':raw['study']['study']['study']['sampling']={'kind':'corners','variables':[dict(name='left_width',lower=.2e-3,upper=.3e-3)]}
    if kind not in ('duplicate','nan'):text=json.dumps(raw)
    with pytest.raises(ValueError):ShapePanelForwardPairYieldDocument.loads(text)


@pytest.mark.parametrize('key,value',[('confidence',True),('confidence',0.),('confidence',1.),
    ('minimum_yield',-1.),('minimum_yield',1.1),('acceptance',{}),
    ('acceptance',{Q[0]:dict(minimum=None,maximum=None),Q[1]:LIMITS[Q[1]]})])
def test_invalid_criteria_refused(key,value):
    raw=document().to_dict();raw[key]=value
    with pytest.raises(ValueError):ShapePanelForwardPairYieldDocument.from_dict(raw)


def test_field_free_roundtrip_and_explicit_method(monkeypatch):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('normalize meshed'))
    doc=document();text=doc.dumps();assert normalize_saved(text)==text==ShapePanelForwardPairYieldDocument.loads(text).dumps()
    raw=doc.to_dict();raw['acceptance'][Q[0]]['minimum']=0;assert doc.dumps()==text
    with pytest.raises(ValueError):PanelForwardPairYieldDocument.loads(text)


@pytest.mark.parametrize('failure',[None,2])
def test_complete_incomplete_receipts_keep_current_and_partial_error(monkeypatch,failure):
    calls=synthetic_transport(monkeypatch,fail_at=failure)
    request=SavedExecutionRequest(document().dumps(),max_evaluations=4);receipt=request.run()
    out=receipt['execution'];assert out['status']==('complete' if failure is None else 'incomplete')
    assert len(calls)==4 and out['result']['count']==4
    assert out['result']['unresolved']==(0 if failure is None else 1)
    for i,row in enumerate(out['result']['rows']):
        if i+1==failure:assert row['cause_details']['message']=='original current refusal'
        else:assert row['current_solver']['diagnostics']=={'transport_stub':1.}
    saved=SavedExecutionRecord(request,receipt,run_id='shape-yield:synthetic',artifacts=ARTIFACTS)
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('restore solved'))
    assert SavedExecutionRecord.loads(saved.dumps()).receipt==receipt


def test_correlated_invalid_rows_budget_and_interrupt(monkeypatch):
    calls=synthetic_transport(monkeypatch)
    doc=ShapePanelForwardPairYieldDocument(ShapePanelForwardPairStudyDocument(random_document(8,'normal')),
        acceptance={q:dict(minimum=0.,maximum=10000.) for q in Q})
    with pytest.raises(ValueError,match='before any solve'):doc.analyze(max_evaluations=7)
    assert not calls
    result=doc.analyze(max_evaluations=8)
    assert 0<result.unresolved<8 and result.passed==len(calls) and result.failed==0
    assert result.sample_fraction_bounds==(result.passed/8,1.)
    calls=synthetic_transport(monkeypatch,fail_at=2,interrupt=True)
    with pytest.raises(KeyboardInterrupt):document().analyze(max_evaluations=4)
    assert len(calls)==2
