# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""All frequency/quantity limits form one event per original manufactured row."""
from dataclasses import replace
import json
import numpy as np
import pytest
from sipi import CrossSection
from sipi.shape_sampled_panel_pair_study import (ShapeSampledPanelForwardPairStudyDocument,
    ShapeSampledPanelForwardPairStudy,ShapeSampledPanelForwardPairStudyRow)
from sipi.shape_sampled_panel_pair_yield import (ShapeSampledPanelForwardPairYieldDocument as Document,
    assess_shape_sampled_panel_pair_yield as assess)
from sipi.shape_panel_line import ShapePanelTransmissionLineDocument
from sipi.sampled_panel_pair_study import SampledPanelForwardPairStudyDocument
from sipi.sampled_panel_pair_yield import SampledPanelForwardPairYieldDocument,assess_sampled_panel_pair_yield
from sipi.execution import normalize_saved
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from test_execution_record import ARTIFACTS
from test_sampled_panel_pair_yield import random_document,fixture as old_fixture,limits,GOOD,BAD,F,Q
from test_yield_assessment import independent_interval
from test_shape_sampled_panel_pair_study import synthetic


def document():
    return Document(ShapeSampledPanelForwardPairStudyDocument(random_document()),acceptance=limits(),minimum_yield=.8)


def fixture(values,kind='uniform',frequencies=F):
    # Statistical rows contain no fabricated extraction evidence.
    old=old_fixture(values,kind,frequencies)
    source=ShapeSampledPanelForwardPairStudyDocument(SampledPanelForwardPairStudyDocument.loads(old.input_json))
    return ShapeSampledPanelForwardPairStudy(source.dumps(),old.frequencies,old.variable_names,
        tuple(ShapeSampledPanelForwardPairStudyRow(**vars(row)) for row in old.rows),old.summary)


def test_joint_inclusive_truth_table_retains_identity_current_fields_and_unknowns():
    study=fixture([((90.,35.),)*3,((110.,45.),)*3,BAD,((100.,40.),(100.,50.),(100.,40.)),None])
    result=assess(study,acceptance=limits(),minimum_yield=.8)
    assert result.study is study and result.classifications==('pass','pass','fail','fail','unresolved')
    assert result.sample_fraction_bounds==(.4,.6) and result.goal_status=='undetermined'
    data=result.to_dict();assert data['count']==5 and data['event']=='all-sampled-paired-forward-impedance-limits'
    assert data['scope']=='iid-stated-shape-current-frequency-grid-not-measured-production-yield'
    assert all(r['current_solver'] is None and r['cause_details'] is None for r in data['rows'])
    assert data['rows']==[dict(r.to_dict(),classification=label) for r,label in zip(study.rows,result.classifications)]
    with pytest.raises(TypeError):result.acceptance[Q[0]]['minimum'][0]=0
    with pytest.raises(ValueError):assess_sampled_panel_pair_yield(study,acceptance=limits())


def test_cross_frequency_joint_count_is_not_product_of_marginals():
    a=assess(fixture([BAD,((200.,40.),(100.,40.),(100.,40.))]),acceptance=limits())
    b=assess(fixture([GOOD,((200.,40.),(200.,40.),(100.,40.))]),acceptance=limits())
    assert a.passed==0 and b.passed==1


@pytest.mark.parametrize('size',[9,64])
def test_more_frequencies_do_not_increase_manufacturing_trial_count(size):
    a=assess(fixture([GOOD,BAD,None,GOOD]),acceptance=limits())
    good=tuple((100.,40.) for _ in range(size));bad=list(good);bad[1]=(200.,40.)
    b=assess(fixture([good,tuple(bad),None,good],frequencies=np.geomspace(F[0],F[-1],size)),acceptance=limits(size))
    assert a.classifications==b.classifications and a.confidence_interval==b.confidence_interval
    assert b.to_dict()['count']==4


@pytest.mark.parametrize('count',[2,5,20])
@pytest.mark.parametrize('confidence',[.5,.9,.95,.999])
def test_independent_finite_binomial_tail_inversion(count,confidence):
    for passed in range(count+1):
        result=assess(fixture([GOOD]*passed+[BAD]*(count-passed)),acceptance=limits(),confidence=confidence)
        np.testing.assert_allclose(result.confidence_interval,independent_interval(passed,count,confidence),rtol=0,atol=1e-12)


def test_unknown_completions_and_exact_extreme_counts():
    from scipy.stats import binomtest
    for passed in range(6):
        for unknown in range(6-passed):
            result=assess(fixture([GOOD]*passed+[None]*unknown+[BAD]*(5-passed-unknown)),acceptance=limits())
            for k in range(passed,passed+unknown+1):
                low,high=independent_interval(k,5,.95)
                assert result.confidence_interval[0]<=low+1e-14 and result.confidence_interval[1]>=high-1e-14
    for count,passed in ((2,0),(2,2),(50,17),(1000,999)):
        result=assess(fixture([GOOD]*passed+[BAD]*(count-passed)),acceptance=limits())
        ref=binomtest(passed,count).proportion_ci(confidence_level=.95,method='exact')
        np.testing.assert_allclose(result.confidence_interval,[ref.low,ref.high],rtol=0,atol=1e-12)


def test_frequency_specific_inclusive_one_sided_bounds():
    bound=limits();bound[Q[0]]=dict(minimum=[None,100.,None],maximum=[100.,None,100.])
    assert assess(fixture([GOOD]*2),acceptance=bound).passed==2
    bound[Q[1]]['maximum'][1]=39.;assert assess(fixture([GOOD]*2),acceptance=bound).failed==2


@pytest.mark.parametrize('value',[90.,None,[90.],[90.,90.],[[90.],[90.],[90.]],[True,90.,90.],[-1.,90.,90.],[float('inf'),90.,90.]])
def test_no_bound_broadcast_or_invalid_entries(value):
    bounds=limits();bounds[Q[0]]['minimum']=value
    with pytest.raises(ValueError):assess(fixture([GOOD]*2),acceptance=bounds)
    with pytest.raises(ValueError):Document(ShapeSampledPanelForwardPairStudyDocument(random_document()),acceptance=bounds)


@pytest.mark.parametrize('kind',['sweep','corners'])
def test_non_iid_rejected_before_fields(monkeypatch,kind):
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('non-iid solved'))
    with pytest.raises(ValueError,match='iid'):Document(ShapeSampledPanelForwardPairStudyDocument(random_document(kind=kind)),acceptance=limits())
    with pytest.raises(ValueError,match='iid'):assess(fixture([GOOD]*4,kind),acceptance=limits())


@pytest.mark.parametrize('change',[dict(index=True),dict(sample_values=(0.,0.)),dict(values=GOOD[:2]),
    dict(values=((100.,40.),(100.,float('nan')),(100.,40.))),dict(values=((100.,40.),(True,40.),(100.,40.))),
    dict(values=list(GOOD)),dict(values=None),dict(phase='diagnostic'),dict(error_type='ValueError')])
def test_corrupt_completed_grid_rejected(change):
    source=fixture([GOOD]*4);source=replace(source,rows=(replace(source.rows[0],**change),)+source.rows[1:])
    with pytest.raises(ValueError):assess(source,acceptance=limits())


def test_changed_frequency_order_missing_rows_and_bad_unknown_rejected():
    source=fixture([GOOD]*4)
    for bad in (replace(source,frequencies=source.frequencies[::-1]),replace(source,rows=source.rows[:3]),
        replace(source,rows=source.rows[::-1]),replace(source,input_json=random_document().dumps())):
        with pytest.raises(ValueError):assess(bad,acceptance=limits())
    unknown=fixture([None]*4)
    with pytest.raises(ValueError):assess(replace(unknown,rows=(replace(unknown.rows[0],values=GOOD),)+unknown.rows[1:]),acceptance=limits())


@pytest.mark.parametrize('kind',['schema','missing','extra','duplicate','nan','old-study'])
def test_strict_json_and_explicit_method(kind):
    raw=document().to_dict();text=json.dumps(raw)
    if kind=='schema':raw['schema']='sipi.shape-sampled-panel-forward-pair-yield/2'
    if kind=='missing':raw.pop('confidence')
    if kind=='extra':raw['extra']=1
    if kind=='duplicate':text=text.replace('"confidence": 0.95','"confidence": 0.95, "confidence": 0.95')
    if kind=='nan':text=text.replace('"confidence": 0.95','"confidence": NaN')
    if kind=='old-study':raw['study']=raw['study']['study']
    if kind not in ('duplicate','nan'):text=json.dumps(raw)
    with pytest.raises(ValueError):Document.loads(text)


def test_field_free_canonical_and_independent_copy(monkeypatch):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('normalize meshed'))
    doc=document();text=doc.dumps();assert normalize_saved(text)==text==Document.loads(text).dumps()
    raw=doc.to_dict();raw['acceptance'][Q[0]]['minimum'][0]=0.;assert doc.dumps()==text
    with pytest.raises(ValueError):SampledPanelForwardPairYieldDocument.loads(text)


@pytest.mark.parametrize('failure',[None,2])
def test_complete_partial_receipt_budget_and_original_current(monkeypatch,failure):
    calls=synthetic(monkeypatch,fail_at=failure);doc=document()
    with pytest.raises(ValueError,match='before any solve'):doc.analyze(max_evaluations=3)
    assert not calls
    request=SavedExecutionRequest(doc.dumps(),max_evaluations=4);receipt=request.run();out=receipt['execution']
    assert len(calls)==4 and out['result']['count']==4 and out['result']['frequencies_hz']==list(F)
    assert out['status']==('complete' if failure is None else 'incomplete')
    for i,row in enumerate(out['result']['rows']):
        if i+1==failure:assert row['cause_details']['partial_current']['samples']==[]
        else:assert row['current_solver']['diagnostics']=={'transport_stub':1.}
    saved=SavedExecutionRecord(request,receipt,run_id='shape-grid:yield',artifacts=ARTIFACTS)
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('restore solved'))
    assert SavedExecutionRecord.loads(saved.dumps()).receipt==receipt


def test_interrupt_propagates(monkeypatch):
    calls=synthetic(monkeypatch,fail_at=2,interrupt=True)
    with pytest.raises(KeyboardInterrupt):document().analyze(max_evaluations=4)
    assert len(calls)==2
