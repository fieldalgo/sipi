# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Joint iid events, independent binomial tails and preserved physical samples."""
from dataclasses import replace
import json
import numpy as np
import pytest
from sipi import CrossSection
from sipi.two_ground_pair_study import TwoGroundForwardPairStudyDocument as Source, TwoGroundForwardPairStudy as Study, TwoGroundForwardPairStudyRow as Row
from sipi.two_ground_pair_yield import TwoGroundForwardPairYieldDocument as Document, assess_two_ground_pair_yield as assess
from sipi.two_ground_panel_line import TwoGroundPanelTransmissionLineDocument as Line
from sipi.panel_pair_yield import assess_panel_pair_yield, PanelForwardPairYieldDocument
from sipi.execution import normalize_saved
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject
from test_two_ground_pair_study import document as source_document
from test_two_ground_pair_goal import synthetic
from test_panel_pair_yield import LIMITS,Q
from test_yield_assessment import independent_interval
from test_execution_record import ARTIFACTS


def source(count=4,kind='uniform',physical=False):
    raw=source_document(physical=physical).to_dict();sampling=raw['study']['sampling']
    sampling['kind']=kind
    if kind!='corners':sampling['count']=count
    if kind=='uniform':sampling['seed']=17
    if kind=='normal':sampling.update(seed=3,correlation=[[1.,.5],[.5,1.]],variables=[dict(name='width',mean=.0002,std=.0003),dict(name='gap',mean=.0002,std=.0003)])
    if kind=='sweep':sampling['variables']=sampling['variables'][:1]
    return Source.from_dict(raw)


def document():
    return Document(source(),acceptance=LIMITS,minimum_yield=.8)


def fixture(values,kind='uniform'):
    doc=source(len(values),kind)
    rows=tuple(Row(i,tuple(sample),None,None,None,value,
        'complete' if value is not None else 'diagnostic',
        None if value is not None else 'ArithmeticError',
        None if value is not None else 'retained unknown')
        for i,(sample,value) in enumerate(zip(doc.samples(),values)))
    return Study(doc.dumps(),tuple(v['name'] for v in doc.to_dict()['study']['sampling']['variables']),rows,None)


def test_joint_truth_table_identity_inclusive_bounds_and_original_denominator():
    study=fixture([(90.,35.),(110.,45.),(80.,40.),(100.,50.),(80.,50.),None])
    result=assess(study,acceptance=LIMITS,minimum_yield=.8)
    assert result.study is study and result.classifications==('pass','pass','fail','fail','fail','unresolved')
    assert (result.passed,result.failed,result.unresolved)==(2,3,1)
    assert result.sample_fraction_bounds==(2/6,3/6) and result.goal_status=='undetermined'
    report=result.to_dict();assert report['scope']=='iid-stated-two-ground-distribution-not-measured-production-yield'
    assert report['sampling_model']==json.loads(study.input_json)['study']['sampling']
    assert report['rows']==[dict(row.to_dict(),classification=label) for row,label in zip(study.rows,result.classifications)]
    with pytest.raises(TypeError):result.acceptance[Q[0]]['minimum']=0
    with pytest.raises(ValueError):assess_panel_pair_yield(study,acceptance=LIMITS)


def test_joint_count_is_not_product_of_marginal_counts():
    a=assess(fixture([(100.,80.),(200.,40.)]),acceptance=LIMITS)
    b=assess(fixture([(100.,40.),(200.,80.)]),acceptance=LIMITS)
    assert a.passed==0 and b.passed==1


@pytest.mark.parametrize('count',[2,5,20])
@pytest.mark.parametrize('confidence',[.5,.9,.95,.999])
def test_independent_binomial_tail_inversion(count,confidence):
    for passed in range(count+1):
        result=assess(fixture([(100.,40.)]*passed+[(200.,40.)]*(count-passed)),acceptance=LIMITS,confidence=confidence)
        np.testing.assert_allclose(result.confidence_interval,independent_interval(passed,count,confidence),rtol=0,atol=1e-12)


def test_all_unknown_completions_enclosed_and_extremes():
    from scipy.stats import binomtest
    for passed in range(6):
        for unknown in range(6-passed):
            result=assess(fixture([(100.,40.)]*passed+[None]*unknown+[(200.,40.)]*(5-passed-unknown)),acceptance=LIMITS)
            for k in range(passed,passed+unknown+1):
                low,high=independent_interval(k,5,.95)
                assert result.confidence_interval[0]<=low+1e-14 and result.confidence_interval[1]>=high-1e-14
    assert assess(fixture([None]*5),acceptance=LIMITS).confidence_interval==(0.,1.)
    for count,passed in ((2,0),(2,2),(50,17),(1000,999)):
        result=assess(fixture([(100.,40.)]*passed+[(200.,40.)]*(count-passed)),acceptance=LIMITS)
        ref=binomtest(passed,count).proportion_ci(confidence_level=.95,method='exact')
        np.testing.assert_allclose(result.confidence_interval,[ref.low,ref.high],rtol=0,atol=1e-12)


@pytest.mark.parametrize('kind',['sweep','corners'])
def test_non_iid_refused_before_fields(monkeypatch,kind):
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('non-iid solved'))
    with pytest.raises(ValueError,match='iid'):Document(source(kind=kind),acceptance=LIMITS)
    with pytest.raises(ValueError,match='iid'):assess(fixture([(100.,40.)]*4,kind),acceptance=LIMITS)


@pytest.mark.parametrize('change',[dict(index=True),dict(index=1),dict(sample_values=(True,.0002)),dict(sample_values=(0.,0.)),dict(values=(0.,40.)),dict(values=(100.,float('nan'))),dict(values=(True,40.)),dict(values=(100.,)),dict(values=[100.,40.]),dict(values=None),dict(phase='diagnostic'),dict(error_type='ValueError')])
def test_corrupt_complete_row_refused(change):
    study=fixture([(100.,40.)]*4);study=replace(study,rows=(replace(study.rows[0],**change),)+study.rows[1:])
    with pytest.raises(ValueError):assess(study,acceptance=LIMITS)


@pytest.mark.parametrize('change',[dict(values=(100.,40.)),dict(error_type=None),dict(phase='complete'),dict(error=7)])
def test_corrupt_unknown_row_refused(change):
    study=fixture([None]*4);study=replace(study,rows=(replace(study.rows[0],**change),)+study.rows[1:])
    with pytest.raises(ValueError):assess(study,acceptance=LIMITS)


def test_missing_reordered_or_changed_rows_refused():
    study=fixture([(100.,40.)]*4)
    for broken in (None,replace(study,rows=study.rows[:3]),replace(study,rows=study.rows[::-1]),replace(study,variable_names=('wrong',)),replace(study,input_json=document().dumps())):
        with pytest.raises(ValueError):assess(broken,acceptance=LIMITS)


@pytest.mark.parametrize('kind',['schema','missing','extra','duplicate','nan','wrong-study'])
def test_strict_saved_fields(kind):
    raw=document().to_dict();text=None
    if kind=='schema':raw['schema']+='/unknown'
    if kind=='missing':raw.pop('confidence')
    if kind=='extra':raw['extra']=1
    if kind=='duplicate':text=json.dumps(raw).replace('"confidence": 0.95','"confidence": 0.95, "confidence": 0.95')
    if kind=='nan':text=json.dumps(raw).replace('"confidence": 0.95','"confidence": NaN')
    if kind=='wrong-study':raw['study']=raw['study']['study']
    with pytest.raises(ValueError):Document.loads(text or json.dumps(raw))


@pytest.mark.parametrize('key,value',[('confidence',True),('confidence',0.),('confidence',1.),('minimum_yield',-1.),('minimum_yield',1.1),('acceptance',{}),('acceptance',{Q[0]:dict(minimum=None,maximum=None),Q[1]:LIMITS[Q[1]]})])
def test_invalid_criteria_refused(key,value):
    raw=document().to_dict();raw[key]=value
    with pytest.raises(ValueError):Document.from_dict(raw)


def test_fieldfree_snapshot_request_and_project_restore(monkeypatch):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('normalize meshed'))
    doc=document();text=doc.dumps();assert normalize_saved(text)==text==Document.loads(text).dumps()
    raw=doc.to_dict();raw['acceptance'][Q[0]]['minimum']=0;assert doc.dumps()==text
    with pytest.raises(ValueError):PanelForwardPairYieldDocument.loads(text)
    request=SavedExecutionRequest(text,max_evaluations=4)
    project=SavedProject(request,project_id='two-ground-yield',design_id='a',title='Acceptance',label='Source')
    assert SavedProject.loads(project.dumps()).prepare('a').request_id==request.request_id


@pytest.mark.parametrize('failure',[None,2])
def test_complete_partial_receipts_preserve_current_and_typed_failure(monkeypatch,failure):
    calls=synthetic(monkeypatch,fail_at=failure);request=SavedExecutionRequest(document().dumps(),max_evaluations=4);receipt=request.run();out=receipt['execution']
    assert out['status']==('complete' if failure is None else 'incomplete') and len(calls)==4
    assert out['result']['count']==4 and out['result']['unresolved']==(0 if failure is None else 1)
    for i,row in enumerate(out['result']['rows']):
        if i+1==failure:assert row['cause_details']['cause_type']=='ArithmeticError'
        else:assert row['current_solver']['kind']=='test-only-synthetic'
    record=SavedExecutionRecord(request,receipt,run_id='two-ground-yield:synthetic',artifacts=ARTIFACTS)
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('restore solved'))
    assert SavedExecutionRecord.loads(record.dumps()).receipt==receipt


def test_correlated_invalid_rows_budget_and_interrupt(monkeypatch):
    calls=synthetic(monkeypatch);doc=Document(source(8,'normal'),acceptance={q:dict(minimum=0.,maximum=10000.) for q in Q})
    with pytest.raises(ValueError,match='before any solve'):doc.analyze(max_evaluations=7)
    assert not calls
    result=doc.analyze(max_evaluations=8)
    assert 0<result.unresolved<8 and result.passed==len(calls) and result.failed==0
    assert result.sample_fraction_bounds==(result.passed/8,1.)
    calls=synthetic(monkeypatch,fail_at=2,interrupt=True)
    with pytest.raises(KeyboardInterrupt):document().analyze(max_evaluations=4)
    assert len(calls)==2


def test_actual_registered_iid_rows_and_independent_joint_classification(record_property):
    doc=Document(source(4,'uniform',physical=True),acceptance={Q[0]:dict(minimum=90.,maximum=91.),Q[1]:dict(minimum=44.4,maximum=44.6)},minimum_yield=.8)
    request=SavedExecutionRequest(doc.dumps(),max_evaluations=4);receipt=request.run();out=receipt['execution']
    record_property('two_ground_yield_receipt',json.dumps(receipt,sort_keys=True))
    assert out['status']=='complete';result=out['result'];assert result['count']==4 and result['unresolved']==0
    ordered_limits=[doc.to_dict()['acceptance'][q] for q in Q]
    expected=[]
    for row in result['rows']:
        assert row['current_solver']['kind']=='two-ground-rectangle-panels' and row['dielectric_mesh']
        values=row['values_ohm']
        expected.append('pass' if all(item['minimum']<=value<=item['maximum'] for value,item in zip(values,ordered_limits)) else 'fail')
    assert [row['classification'] for row in result['rows']]==expected
    np.testing.assert_allclose(result['confidence_interval'],independent_interval(expected.count('pass'),4,.95),rtol=0,atol=1e-12)
