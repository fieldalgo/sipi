# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
import json
from dataclasses import replace
import numpy as np
import pytest
from sipi.panel_pair_yield import PanelForwardPairYieldDocument, assess_panel_pair_yield
from sipi import CrossSection
from sipi.panel_pair_study import PanelForwardPairStudyDocument, PanelForwardPairStudy, PanelForwardPairStudyRow
from sipi.panel_line import PanelTransmissionLineDocument
from test_panel_pair_study import document, Q
from test_panel_pair_goal import synthetic
from test_yield_assessment import independent_interval

LIMITS={Q[0]:dict(minimum=90.,maximum=110.),Q[1]:dict(minimum=35.,maximum=45.)}


def random_document(count=4, kind='uniform'):
    raw=document().to_dict();sampling=raw['study']['sampling'];sampling['kind']=kind
    if kind=='corners':sampling.pop('count',None)
    else:sampling['count']=count
    if kind=='uniform':sampling['seed']=123
    if kind=='normal':
        sampling.update(seed=3,correlation=[[1.,.5],[.5,1.]],variables=[
            dict(name='left_width',mean=.2e-3,std=.3e-3),dict(name='gap',mean=.2e-3,std=.3e-3)])
    if kind=='sweep':sampling['variables']=sampling['variables'][:1]
    return PanelForwardPairStudyDocument.from_dict(raw)


def fixture(values,kind='uniform'):
    """Statistical fixture; manually assembled rows do not establish field accuracy."""
    doc=random_document(len(values),kind)
    rows=tuple(PanelForwardPairStudyRow(i,tuple(sample),None,None,None,value,
        'complete' if value is not None else 'diagnostic',
        None if value is not None else 'ArithmeticError',
        None if value is not None else 'retained failure')
        for i,(value,sample) in enumerate(zip(values,doc.samples())))
    return PanelForwardPairStudy(doc.dumps(),tuple(v['name'] for v in doc.to_dict()['study']['sampling']['variables']),rows,None)


def test_joint_truth_table_inclusive_limits_and_unknown_denominator():
    values=[(90.,35.),(110.,45.),(80.,40.),(100.,50.),(80.,50.),None]
    study=fixture(values);result=assess_panel_pair_yield(study,acceptance=LIMITS,minimum_yield=.8)
    assert result.classifications==('pass','pass','fail','fail','fail','unresolved')
    assert (result.passed,result.failed,result.unresolved)==(2,3,1)
    assert result.sample_fraction_bounds==(2/6,3/6) and result.goal_status=='undetermined'
    report=result.to_dict();assert report['quantities']==list(Q) and report['unit']=='ohm'
    assert [r['values_ohm'] for r in report['rows']]==[None if v is None else list(v) for v in values]
    assert report['event']=='both-paired-forward-impedance-limits'
    assert result.study is study
    with pytest.raises(TypeError):result.acceptance[Q[0]]['minimum']=0
    json.dumps(report,allow_nan=False)


def test_joint_event_is_not_product_of_marginal_pass_fractions():
    opposite=assess_panel_pair_yield(fixture([(100.,80.),(200.,40.)]),acceptance=LIMITS)
    together=assess_panel_pair_yield(fixture([(100.,40.),(200.,80.)]),acceptance=LIMITS)
    # Both marginals pass one of two samples, but the joint counts differ.
    assert opposite.passed==0 and together.passed==1
    assert opposite.sample_fraction_bounds==(0.,0.) and together.sample_fraction_bounds==(.5,.5)


@pytest.mark.parametrize('count',[2,5,20])
@pytest.mark.parametrize('confidence',[.5,.9,.95,.999])
def test_independent_finite_binomial_tail_inversion(count,confidence):
    for passed in range(count+1):
        result=assess_panel_pair_yield(fixture([(100.,40.)]*passed+[(200.,40.)]*(count-passed)),acceptance=LIMITS,confidence=confidence)
        np.testing.assert_allclose(result.confidence_interval,independent_interval(passed,count,confidence),rtol=0,atol=1e-12)


def test_interval_encloses_every_possible_unresolved_completion():
    for passed in range(6):
        for unknown in range(6-passed):
            result=assess_panel_pair_yield(fixture([(100.,40.)]*passed+[None]*unknown+[(200.,40.)]*(5-passed-unknown)),acceptance=LIMITS)
            for k in range(passed,passed+unknown+1):
                low,high=independent_interval(k,5,.95)
                assert result.confidence_interval[0]<=low+1e-14 and result.confidence_interval[1]>=high-1e-14


def test_scipy_exact_binomial_reference_at_extreme_counts():
    from scipy.stats import binomtest
    for count,passed in [(2,0),(2,2),(50,17),(1000,0),(1000,999),(1000,1000)]:
        result=assess_panel_pair_yield(fixture([(100.,40.)]*passed+[(200.,40.)]*(count-passed)),acceptance=LIMITS)
        ref=binomtest(passed,count).proportion_ci(confidence_level=.95,method='exact')
        np.testing.assert_allclose(result.confidence_interval,[ref.low,ref.high],rtol=0,atol=1e-12)


def test_all_unknown_and_goal_decisions_use_joint_confidence_bounds():
    unknown=assess_panel_pair_yield(fixture([None]*5),acceptance=LIMITS,minimum_yield=.5)
    assert unknown.confidence_interval==(0.,1.) and unknown.goal_status=='undetermined'
    good=fixture([(100.,40.)]*20);low=.025**(1/20)
    accepted=assess_panel_pair_yield(good,acceptance=LIMITS,minimum_yield=low)
    assert accepted.goal_status=='pass' and accepted.confidence_interval[0]==pytest.approx(low,abs=1e-14)
    assert assess_panel_pair_yield(good,acceptance=LIMITS,minimum_yield=1.).goal_status=='undetermined'
    assert assess_panel_pair_yield(good,acceptance=LIMITS).goal_status=='not-requested'
    assert assess_panel_pair_yield(fixture([(200.,40.)]*20),acceptance=LIMITS,minimum_yield=.8).goal_status=='fail'


@pytest.mark.parametrize('kind',['sweep','corners'])
def test_non_iid_request_and_direct_result_reject_before_fields(monkeypatch,kind):
    def forbidden(*a,**k):pytest.fail('non-iid input reached fields')
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',forbidden)
    with pytest.raises(ValueError,match='iid'):PanelForwardPairYieldDocument(random_document(kind=kind),acceptance=LIMITS)
    with pytest.raises(ValueError,match='iid'):assess_panel_pair_yield(fixture([(100.,40.)]*4,kind),acceptance=LIMITS)


@pytest.mark.parametrize('bad',[None,{}, {Q[0]:LIMITS[Q[0]]},dict(LIMITS,unknown={}),
    {Q[0]:dict(minimum=None,maximum=None),Q[1]:LIMITS[Q[1]]},
    {Q[0]:dict(minimum=110.,maximum=90.),Q[1]:LIMITS[Q[1]]},
    {Q[0]:dict(minimum=True,maximum=110.),Q[1]:LIMITS[Q[1]]},
    {Q[0]:dict(minimum=-1.,maximum=110.),Q[1]:LIMITS[Q[1]]},
    {Q[0]:dict(minimum=90.,maximum=float('inf')),Q[1]:LIMITS[Q[1]]},
    {Q[0]:dict(minimum=90.),Q[1]:LIMITS[Q[1]]}])
def test_invalid_limits_reject(bad):
    with pytest.raises(ValueError):PanelForwardPairYieldDocument(random_document(),acceptance=bad)
    with pytest.raises(ValueError):assess_panel_pair_yield(fixture([(100.,40.)]*4),acceptance=bad)


@pytest.mark.parametrize('key,value',[('confidence',True),('confidence',0.),('confidence',1.),
    ('confidence',float('nan')),('minimum_yield',True),('minimum_yield',-1.),('minimum_yield',1.1)])
def test_invalid_probability_contract(key,value):
    with pytest.raises(ValueError):PanelForwardPairYieldDocument(random_document(),acceptance=LIMITS,**{key:value})


def test_field_free_canonical_snapshots_and_strict_json(monkeypatch):
    def forbidden(*a,**k):pytest.fail('normalization reached fields')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    doc=PanelForwardPairYieldDocument(random_document(),acceptance=LIMITS)
    text=doc.dumps();raw=doc.to_dict();raw['acceptance'][Q[0]]['minimum']=0.
    assert doc.dumps()==text and PanelForwardPairYieldDocument.loads(text).dumps()==text
    for bad in [dict(doc.to_dict(),extra=1),{k:v for k,v in doc.to_dict().items() if k!='confidence'},dict(doc.to_dict(),schema='unknown')]:
        with pytest.raises(ValueError):PanelForwardPairYieldDocument.from_dict(bad)
    for bad in [text.replace('"confidence": 0.95','"confidence": 0.95, "confidence": 0.95'),text.replace('"confidence": 0.95','"confidence": NaN')]:
        with pytest.raises(ValueError):PanelForwardPairYieldDocument.loads(bad)


@pytest.mark.parametrize('change',[
    dict(index=True),dict(index=1),dict(sample_values=(True,.2e-3)),dict(sample_values=(0.,0.)),
    dict(values=(0.,40.)),dict(values=(100.,float('nan'))),dict(values=(True,40.)),
    dict(values=(100.,)),dict(values=[100.,40.]),dict(values=None),dict(phase='diagnostic'),dict(error_type='ValueError')])
def test_completed_row_corruption_rejects(change):
    study=fixture([(100.,40.)]*4);broken=replace(study,rows=(replace(study.rows[0],**change),)+study.rows[1:])
    with pytest.raises(ValueError):assess_panel_pair_yield(broken,acceptance=LIMITS)


@pytest.mark.parametrize('change',[dict(values=(100.,40.)),dict(error_type=None),dict(phase='complete'),dict(error=7)])
def test_unresolved_row_corruption_rejects(change):
    study=fixture([None]*4);broken=replace(study,rows=(replace(study.rows[0],**change),)+study.rows[1:])
    with pytest.raises(ValueError):assess_panel_pair_yield(broken,acceptance=LIMITS)


def test_wrong_study_shape_cannot_drop_or_reorder_rows():
    study=fixture([(100.,40.)]*4)
    for broken in [None,replace(study,rows=study.rows[:3]),replace(study,rows=study.rows[::-1]),
        replace(study,rows=(object(),)+study.rows[1:]),replace(study,variable_names=('wrong','names'))]:
        with pytest.raises(ValueError):assess_panel_pair_yield(broken,acceptance=LIMITS)


def test_seeded_correlated_invalid_geometry_stays_in_denominator(monkeypatch):
    calls=synthetic(monkeypatch);source=random_document(8,'normal')
    doc=PanelForwardPairYieldDocument(source,acceptance={q:dict(minimum=0.,maximum=10000.) for q in Q})
    result=doc.analyze(max_evaluations=8)
    assert 0<result.unresolved<8 and result.failed==0 and result.passed==len(calls)
    assert len(result.study.rows)==8 and result.sample_fraction_bounds==(result.passed/8,1.)
    np.testing.assert_array_equal([row.sample_values for row in result.study.rows],source.samples())
    assert result.study.summary is None
    json.dumps(result.to_dict(),allow_nan=False)


def test_budget_propagates_before_extraction(monkeypatch):
    doc=PanelForwardPairYieldDocument(random_document(),acceptance=LIMITS)
    def forbidden(*a,**k):pytest.fail('budget rejection reached fields')
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',forbidden)
    with pytest.raises(ValueError):doc.analyze(max_evaluations=3)


def test_one_sided_bounds_and_zero_probability_goal_keep_meaning():
    limits={Q[0]:dict(minimum=100.,maximum=None),Q[1]:dict(minimum=None,maximum=40.)}
    result=assess_panel_pair_yield(fixture([(100.,40.),(120.,30.),(90.,30.),(120.,50.)]),acceptance=limits)
    assert result.classifications==('pass','pass','fail','fail')
    unknown=assess_panel_pair_yield(fixture([None]*4),acceptance=limits,minimum_yield=0.)
    assert unknown.goal_status=='pass' and unknown.unresolved==4 and unknown.confidence_interval==(0.,1.)
    zero=assess_panel_pair_yield(fixture([(100.,40.)]*4),acceptance={q:dict(minimum=None,maximum=0.) for q in Q})
    assert zero.failed==4


def test_confidence_near_endpoints_and_mutable_acceptance_snapshot():
    limits=json.loads(json.dumps(LIMITS));source=fixture([(100.,40.)]*4)
    result=assess_panel_pair_yield(source,acceptance=limits,confidence=float(np.nextafter(1.,0.)))
    assert 0.<result.confidence_interval[0]<1. and result.confidence_interval[1]==1.
    limits[Q[0]]['maximum']=0.
    assert result.acceptance[Q[0]]['maximum']==110.
    with pytest.raises(ValueError):
        assess_panel_pair_yield(source,acceptance=LIMITS,confidence=float(np.nextafter(0.,1.)))


@pytest.mark.parametrize('phase',['parameters','materials','input','extraction','diagnostic'])
def test_all_failure_phases_remain_unresolved_and_later_rows_run(monkeypatch,phase):
    import sipi.panel_pair_study as module
    calls=synthetic(monkeypatch,fail_at=2 if phase=='extraction' else None)
    if phase in ('parameters','materials','input'):
        name=dict(parameters='_parameters',materials='_sample_material',input='_line_from_inputs')[phase];original=getattr(module,name);seen=[]
        def fail_second(*a,**k):
            seen.append(1)
            if len(seen)==2:raise ArithmeticError('retained phase cause')
            return original(*a,**k)
        monkeypatch.setattr(module,name,fail_second)
    elif phase=='diagnostic':
        original=PanelTransmissionLineDocument.analyze
        def diagnose(self):
            line=original(self)
            if len(calls)==2:
                def fail():raise ArithmeticError('retained phase cause')
                line.characteristic=fail
            return line
        monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',diagnose)
    result=PanelForwardPairYieldDocument(random_document(),acceptance=LIMITS).analyze(max_evaluations=4)
    assert result.unresolved==1 and len(result.study.rows)==4
    assert result.classifications[1]=='unresolved' and result.study.rows[1].phase==phase
    assert result.study.rows[1].error_type=='ArithmeticError'
    assert all(row.complete for i,row in enumerate(result.study.rows) if i!=1)


def test_saved_execution_matches_direct_and_retains_whole_request(monkeypatch):
    from sipi.execution import execute_saved,normalize_saved,saved_schemas
    synthetic(monkeypatch);doc=PanelForwardPairYieldDocument(random_document(),acceptance=LIMITS,minimum_yield=.9)
    expected=doc.analyze(max_evaluations=4).to_dict();output=execute_saved(doc.dumps(),max_evaluations=4)
    assert output['status']=='complete' and output['error'] is None
    assert output['result']==expected and output['input']==doc.to_dict()
    assert normalize_saved(doc.dumps())==doc.dumps()
    assert 'sipi.panel-forward-pair-yield/1' in saved_schemas()
    json.dumps(output,allow_nan=False)


@pytest.mark.parametrize('mode',['budget','diagnostics','input_bytes'])
def test_transport_controls_reject_before_extraction(monkeypatch,mode):
    from sipi.execution import execute_saved
    doc=PanelForwardPairYieldDocument(random_document(),acceptance=LIMITS)
    def forbidden(*a,**k):pytest.fail('refused transport reached fields')
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',forbidden)
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    options={'max_evaluations':3} if mode=='budget' else ({'diagnostics':['characteristic']} if mode=='diagnostics' else {'max_input_bytes':16})
    with pytest.raises(ValueError):execute_saved(doc.dumps(),**options)


@pytest.mark.parametrize('phase',['parameters','materials','input','extraction','diagnostic'])
def test_common_execution_keeps_every_failure_phase_and_row(monkeypatch,phase):
    from sipi.execution import execute_saved
    import sipi.panel_pair_study as module
    calls=synthetic(monkeypatch,fail_at=2 if phase=='extraction' else None)
    if phase in ('parameters','materials','input'):
        name=dict(parameters='_parameters',materials='_sample_material',input='_line_from_inputs')[phase]
        original=getattr(module,name);seen=[]
        def fail_second(*a,**k):
            seen.append(1)
            if len(seen)==2:raise ArithmeticError('retained row cause')
            return original(*a,**k)
        monkeypatch.setattr(module,name,fail_second)
    elif phase=='diagnostic':
        original=PanelTransmissionLineDocument.analyze
        def diagnose(self):
            line=original(self)
            if len(calls)==2:
                def fail():raise ArithmeticError('retained row cause')
                line.characteristic=fail
            return line
        monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',diagnose)
    doc=PanelForwardPairYieldDocument(random_document(),acceptance=LIMITS,minimum_yield=0.)
    output=execute_saved(doc.dumps(),max_evaluations=4);result=output['result'];row=result['rows'][1]
    assert output['status']=='incomplete' and output['error'] is None and output['input']==doc.to_dict()
    assert result['goal_status']=='pass' and result['unresolved']==1 and result['count']==4
    assert result['passed']+result['failed']+result['unresolved']==4
    assert [r['index'] for r in result['rows']]==list(range(4))
    assert row['classification']=='unresolved' and row['phase']==phase and row['values_ohm'] is None
    assert row['error_type']=='ArithmeticError'
    assert row['error']==('retained physical failure' if phase=='extraction' else 'retained row cause')
    assert row['sample_values']==random_document().samples()[1].tolist()
    assert (row['parameters'] is not None)==(phase!='parameters')
    assert (row['material_evaluation'] is not None)==(phase not in ('parameters','materials'))
    assert (row['input'] is not None)==(phase in ('extraction','diagnostic'))
    json.dumps(output,allow_nan=False)


def test_failed_joint_limits_are_complete_evaluations_not_solver_failures(monkeypatch):
    from sipi.execution import execute_saved
    synthetic(monkeypatch)
    doc=PanelForwardPairYieldDocument(random_document(),
        acceptance={q:dict(minimum=None,maximum=0.) for q in Q},minimum_yield=.9)
    output=execute_saved(doc.dumps(),max_evaluations=4)
    assert output['status']=='complete' and output['result']['goal_status']=='fail'
    assert output['result']['failed']==4 and output['result']['unresolved']==0


def test_single_quantity_yield_consumers_do_not_coerce_paired_input(monkeypatch):
    from sipi.line_yield import LineQuantityYieldDocument,assess_line_yield
    synthetic(monkeypatch);source=random_document();result=source.analyze(max_evaluations=4)
    with pytest.raises(ValueError):LineQuantityYieldDocument(source,minimum=90.,maximum=110.)
    with pytest.raises(ValueError):assess_line_yield(result,minimum=90.,maximum=110.)
