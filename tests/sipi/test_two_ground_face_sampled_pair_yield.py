# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
from dataclasses import replace
import json
import numpy as np
import pytest
from sipi import CrossSection
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument as PanelTransmissionLineDocument
from sipi.two_ground_face_sampled_pair_study import TwoGroundFaceSampledForwardPairStudyDocument as StudyDocument, TwoGroundFaceSampledForwardPairStudy as Study, TwoGroundFaceSampledForwardPairStudyRow as Row
from test_two_ground_face_sampled_pair_study import document as source_document, Q, F, synthetic, physical_document
from test_yield_assessment import independent_interval
from sipi.two_ground_face_sampled_pair_yield import TwoGroundFaceSampledForwardPairYieldDocument as Document, assess_two_ground_face_sampled_pair_yield as assess


def limits(count=3):
    return {q:dict(minimum=[lo]*count,maximum=[hi]*count) for q,lo,hi in zip(Q,[90.,35.],[110.,45.])}


def random_document(count=4,kind='uniform',frequencies=F):
    raw=source_document().to_dict();raw['frequency_hz']=list(frequencies);raw['study']['material_evaluation']['frequency_hz']=float(frequencies[0]);sampling=raw['study']['sampling'];sampling['kind']=kind
    if kind=='corners':sampling.pop('count',None)
    else:sampling['count']=count
    if kind=='uniform':sampling['seed']=123
    if kind=='normal':sampling.update(seed=3,correlation=[[1.,.5],[.5,1.]],variables=[dict(name='width',mean=.2e-3,std=.3e-3),dict(name='gap',mean=.2e-3,std=.3e-3)])
    if kind=='sweep':sampling['variables']=sampling['variables'][:1]
    return StudyDocument.from_dict(raw)


def fixture(values,kind='uniform',frequencies=F):
    # Statistical records only; these manual rows do not establish field accuracy.
    doc=random_document(len(values),kind,frequencies)
    rows=tuple(Row(i,tuple(sample),None,None,None,value,'complete' if value is not None else 'diagnostic',
        None if value is not None else 'ArithmeticError',None if value is not None else 'retained failure')
        for i,(sample,value) in enumerate(zip(doc.samples(),values)))
    return Study(doc.dumps(),tuple(frequencies),tuple(v['name'] for v in doc.to_dict()['study']['sampling']['variables']),rows,None)


GOOD=((100.,40.),)*3;BAD=((100.,40.),(200.,40.),(100.,40.))


def test_one_joint_event_inclusive_bounds_and_original_unknown_denominator():
    low=((90.,35.),)*3;high=((110.,45.),)*3
    values=[low,high,BAD,((100.,40.),(100.,50.),(100.,40.)),None]
    study=fixture(values);result=assess(study,acceptance=limits(),minimum_yield=.8)
    assert result.classifications==('pass','pass','fail','fail','unresolved')
    assert (result.passed,result.failed,result.unresolved)==(2,2,1) and result.sample_fraction_bounds==(.4,.6)
    assert result.goal_status=='undetermined' and result.study is study
    out=result.to_dict();assert out['count']==5 and out['frequencies_hz']==list(F)
    assert out['event']=='all-sampled-paired-forward-impedance-limits'
    assert out['rows'][2]['values_ohm']==[list(row) for row in BAD]
    with pytest.raises(TypeError):result.acceptance[Q[0]]['minimum'][0]=0
    out['acceptance'][Q[0]]['minimum'][0]=0;assert result.acceptance[Q[0]]['minimum'][0]==90.
    json.dumps(out,allow_nan=False)


def test_joint_event_is_not_product_of_frequency_or_quantity_marginals():
    opposite=fixture([((100.,40.),(200.,40.),(100.,40.)),((200.,40.),(100.,40.),(100.,40.))])
    together=fixture([GOOD,((200.,40.),(200.,40.),(100.,40.))])
    a=assess(opposite,acceptance=limits());b=assess(together,acceptance=limits())
    assert a.passed==0 and b.passed==1 and a.sample_fraction_bounds==(0.,0.) and b.sample_fraction_bounds==(.5,.5)


def test_same_specimens_on_more_frequency_points_keep_trial_count_and_interval():
    a=assess(fixture([GOOD,BAD,None,GOOD]),acceptance=limits())
    grid=np.geomspace(F[0],F[-1],9)
    b=assess(fixture([GOOD*3,BAD*3,None,GOOD*3],frequencies=grid),acceptance=limits(9))
    assert a.classifications==b.classifications and a.confidence_interval==b.confidence_interval
    assert b.to_dict()['count']==4


@pytest.mark.parametrize('count',[2,5,20])
@pytest.mark.parametrize('confidence',[.5,.9,.95,.999])
def test_independent_binomial_tail_equations(count,confidence):
    for passed in range(count+1):
        result=assess(fixture([GOOD]*passed+[BAD]*(count-passed)),acceptance=limits(),confidence=confidence)
        np.testing.assert_allclose(result.confidence_interval,independent_interval(passed,count,confidence),rtol=0,atol=1e-12)


def test_every_unresolved_label_completion_is_enclosed():
    for passed in range(6):
        for unknown in range(6-passed):
            result=assess(fixture([GOOD]*passed+[None]*unknown+[BAD]*(5-passed-unknown)),acceptance=limits())
            for k in range(passed,passed+unknown+1):
                lo,hi=independent_interval(k,5,.95)
                assert result.confidence_interval[0]<=lo+1e-14 and result.confidence_interval[1]>=hi-1e-14


def test_scipy_exact_binomial_extreme_counts_and_goal_decisions():
    from scipy.stats import binomtest
    for n,k in [(2,0),(2,2),(50,17),(1000,0),(1000,999),(1000,1000)]:
        result=assess(fixture([GOOD]*k+[BAD]*(n-k)),acceptance=limits())
        ref=binomtest(k,n).proportion_ci(confidence_level=.95,method='exact')
        np.testing.assert_allclose(result.confidence_interval,[ref.low,ref.high],rtol=0,atol=1e-12)
    assert assess(fixture([None]*5),acceptance=limits()).confidence_interval==(0.,1.)
    assert assess(fixture([GOOD]*20),acceptance=limits(),minimum_yield=.8).goal_status=='pass'
    assert assess(fixture([GOOD]*20),acceptance=limits(),minimum_yield=1.).goal_status=='undetermined'
    assert assess(fixture([BAD]*20),acceptance=limits(),minimum_yield=.8).goal_status=='fail'
    assert assess(fixture([GOOD]*2),acceptance=limits()).goal_status=='not-requested'


def test_frequency_specific_one_sided_and_inclusive_bounds():
    bounds=limits();bounds[Q[0]]=dict(minimum=[None,100.,None],maximum=[100.,None,100.])
    assert assess(fixture([GOOD]*2),acceptance=bounds).passed==2
    bounds[Q[1]]['maximum'][1]=39.
    assert assess(fixture([GOOD]*2),acceptance=bounds).failed==2


@pytest.mark.parametrize('value',[90.,None,[90.],[90.,90.],[[90.],[90.],[90.]],[True,90.,90.],[-1.,90.,90.],[float('inf'),90.,90.]])
def test_no_limit_broadcast_or_invalid_entries(value):
    bounds=limits();bounds[Q[0]]['minimum']=value
    with pytest.raises(ValueError):assess(fixture([GOOD]*2),acceptance=bounds)
    with pytest.raises(ValueError):Document(random_document(),acceptance=bounds)


def test_missing_or_inverted_frequency_bounds_rejected():
    for no_bound in [True,False]:
        bounds=limits();bounds[Q[1]]['minimum'][1]=None if no_bound else 50.;bounds[Q[1]]['maximum'][1]=None if no_bound else 40.
        with pytest.raises(ValueError):Document(random_document(),acceptance=bounds)


@pytest.mark.parametrize('key,value',[('confidence',0.),('confidence',1.),('confidence',True),('minimum_yield',-.1),('minimum_yield',1.1),('minimum_yield',True)])
def test_confidence_and_yield_controls(key,value):
    with pytest.raises(ValueError):Document(random_document(),acceptance=limits(),**{key:value})


@pytest.mark.parametrize('kind',['sweep','corners'])
def test_non_iid_rejected_before_fields(monkeypatch,kind):
    def forbidden(*a,**k):pytest.fail('non-iid request invoked fields')
    monkeypatch.setattr(CrossSection,'mesh',forbidden);monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',forbidden)
    with pytest.raises(ValueError,match='iid'):Document(random_document(kind=kind),acceptance=limits())
    with pytest.raises(ValueError,match='iid'):assess(fixture([GOOD]*4,kind),acceptance=limits())


@pytest.mark.parametrize('kind',['frequency','frequency_bool','count','variables','index','sample','rowshape','inner_shape','nan','negative','bool_value','complete_phase','error_type','unknown_values','unknown_phase','unknown_error'])
def test_manual_structural_corruption_cannot_be_certified(kind):
    # A real 1 Hz source violates the unchanged skin-depth admission gate.
    # Start from an admitted grid, then corrupt its saved frequency tuple.
    frequencies=F
    study=fixture([GOOD,None],frequencies=frequencies);row=study.rows[0];unknown=study.rows[1]
    if kind=='frequency':study=replace(study,frequencies=study.frequencies[::-1])
    elif kind=='frequency_bool':study=replace(study,frequencies=(True,1e9,3e9))
    elif kind=='count':study=replace(study,rows=(row,))
    elif kind=='variables':study=replace(study,variable_names=study.variable_names[::-1])
    elif kind=='index':row=replace(row,index=True)
    elif kind=='sample':row=replace(row,sample_values=(0.,0.))
    elif kind=='rowshape':row=replace(row,values=(100.,40.))
    elif kind=='inner_shape':row=replace(row,values=((100.,),)*3)
    elif kind=='nan':row=replace(row,values=((100.,40.),(float('nan'),40.),(100.,40.)))
    elif kind=='negative':row=replace(row,values=((100.,40.),(-1.,40.),(100.,40.)))
    elif kind=='bool_value':row=replace(row,values=((100.,40.),(True,40.),(100.,40.)))
    elif kind=='complete_phase':row=replace(row,phase='diagnostic')
    elif kind=='error_type':row=replace(row,error_type='ValueError')
    elif kind=='unknown_values':unknown=replace(unknown,values=GOOD)
    elif kind=='unknown_phase':unknown=replace(unknown,phase='complete')
    elif kind=='unknown_error':unknown=replace(unknown,error_type=None)
    if kind not in ('frequency','frequency_bool','count','variables'):study=replace(study,rows=(row,unknown))
    with pytest.raises(ValueError):assess(study,acceptance=limits())


def test_field_free_saved_roundtrip_and_copied_limits(monkeypatch):
    def forbidden(*a,**k):pytest.fail('normalization invoked fields')
    monkeypatch.setattr(CrossSection,'mesh',forbidden);monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',forbidden)
    bounds=limits();doc=Document(random_document(),acceptance=bounds);text=doc.dumps()
    bounds[Q[0]]['minimum'][0]=0.;assert doc.dumps()==text and Document.loads(text).dumps()==text
    for bad in [text.replace('"confidence": 0.95','"confidence": 0.95, "confidence": 0.95'),text.replace('"confidence": 0.95','"confidence": NaN'),text.replace('sipi.two-ground-face-sampled-forward-pair-yield/1','sipi.two-ground-face-sampled-forward-pair-yield/unsupported')]:
        with pytest.raises(ValueError):Document.loads(bad)


@pytest.mark.parametrize('where',['root','acceptance','quantity'])
@pytest.mark.parametrize('change',['extra','missing'])
def test_strict_saved_keys(where,change):
    raw=Document(random_document(),acceptance=limits()).to_dict();target=raw if where=='root' else raw['acceptance'] if where=='acceptance' else raw['acceptance'][Q[0]]
    if change=='extra':target['unexpected']=1
    else:target.pop(next(iter(target)))
    with pytest.raises(ValueError):Document.from_dict(raw)


def document():
    return Document(random_document(), acceptance=limits(), minimum_yield=.8)


@pytest.mark.parametrize('failure', [None, 2])
def test_actual_adapter_preserves_atomic_rows_and_project_receipts(monkeypatch, failure):
    from sipi.execution_request import SavedExecutionRequest
    from sipi.execution_record import SavedExecutionRecord
    from sipi.project import SavedProject
    from test_execution_record import ARTIFACTS
    calls = synthetic(monkeypatch, fail_at=failure)
    doc = document(); request = SavedExecutionRequest(doc.dumps(), max_evaluations=4)
    receipt = request.run(); out = receipt['execution']
    assert out['status'] == ('complete' if failure is None else 'incomplete')
    assert len(calls) == out['result']['count'] == 4
    assert out['result']['unresolved'] == (0 if failure is None else 1)
    assert out['result']['scope'] == 'iid-stated-two-ground-face-frequency-grid-not-measured-production-yield'
    for i, row in enumerate(out['result']['rows']):
        if i+1 == failure:
            assert row['cause_details']['cause_type'] == 'ArithmeticError'
            assert row['classification'] == 'unresolved' and row['values_ohm'] is None
        else:
            assert row['current_solver']['kind'] == 'test-only-synthetic'
            assert row['dielectric_mesh']['kind'] == 'test-only-synthetic'
    record = SavedExecutionRecord(request, receipt, run_id='grid-yield:synthetic', artifacts=ARTIFACTS)
    project = SavedProject(request, project_id='grid-yield', design_id='a', title='Acceptance', label='Source')
    project = project.attach_record('a', record)
    monkeypatch.setattr(PanelTransmissionLineDocument, 'analyze', lambda *a,**k: pytest.fail('restore solved'))
    assert SavedExecutionRecord.loads(record.dumps()).receipt == receipt
    restored = SavedProject.loads(project.dumps())
    assert restored.prepare('a').request_id == request.request_id


@pytest.mark.parametrize('mode', ['budget','diagnostics','bytes'])
def test_caller_controls_are_rejected_before_fields(monkeypatch, mode):
    from sipi.execution import execute_saved
    calls = synthetic(monkeypatch)
    kwargs = {'max_evaluations':3} if mode == 'budget' else {'diagnostics':['characteristic']} if mode == 'diagnostics' else {'max_input_bytes':16}
    with pytest.raises(ValueError): execute_saved(document().dumps(), **kwargs)
    assert not calls


def test_correlated_invalid_rows_keep_all_original_samples_and_interrupt(monkeypatch):
    calls = synthetic(monkeypatch)
    doc = Document(random_document(8,'normal'), acceptance={q:dict(minimum=[0.]*3,maximum=[10000.]*3) for q in Q})
    result = doc.analyze(max_evaluations=8)
    assert 0 < result.unresolved < 8 and result.passed == len(calls) and result.failed == 0
    assert result.sample_fraction_bounds == (result.passed/8,1.)
    np.testing.assert_array_equal([row.sample_values for row in result.study.rows], StudyDocument.from_dict(doc.to_dict()['study']).samples())


def test_interrupt_remains_an_interrupt(monkeypatch):
    calls = synthetic(monkeypatch, fail_at=2, interrupt=True)
    with pytest.raises(KeyboardInterrupt): document().analyze(max_evaluations=4)
    assert len(calls) == 2


def test_wrong_study_method_and_row_type_are_rejected():
    from sipi.sampled_panel_pair_yield import assess_sampled_panel_pair_yield
    from sipi.sampled_panel_pair_study import SampledPanelForwardPairStudyRow as OriginalRow
    from test_sampled_panel_pair_yield import fixture as original_fixture
    with pytest.raises(ValueError): assess(original_fixture([GOOD]*4),acceptance=limits())
    with pytest.raises(ValueError): assess_sampled_panel_pair_yield(fixture([GOOD]*4),acceptance=limits())
    study = fixture([GOOD]*4); row = study.rows[0]
    original_row = OriginalRow(row.index,row.sample_values,row.parameters_json,row.material_evaluation_json,row.input_json,
        row.values,row.phase,row.error_type,row.error,row.result)
    with pytest.raises(ValueError): assess(replace(study,rows=(original_row,)+study.rows[1:]),acceptance=limits())


def test_real_registered_debye_iid_grid_joint_classification(record_property):
    from sipi.execution_request import SavedExecutionRequest
    raw = physical_document().to_dict()
    raw['study']['sampling'].update(kind='uniform', count=4, seed=19)
    source = StudyDocument.from_dict(raw)
    acceptance = {q:dict(minimum=[lo]*3,maximum=[hi]*3) for q,lo,hi in zip(Q,[100.,50.],[103.,52.])}
    doc = Document(source, acceptance=acceptance, minimum_yield=.8)
    request = SavedExecutionRequest(doc.dumps(),max_evaluations=4)
    receipt = request.run(); out = receipt['execution']
    record_property('two_ground_face_grid_yield_receipt',json.dumps(receipt,sort_keys=True))
    assert out['status'] == 'complete'
    result = out['result']; assert result['count'] == 4 and result['unresolved'] == 0
    expected = []
    for sample,row in zip(source.samples(),result['rows']):
        assert row['sample_values'] == list(sample)
        assert row['current_solver']['kind'] == 'two-ground-rectangle-face-panels' and row['dielectric_mesh']
        expected.append('pass' if all(acceptance[q]['minimum'][f] <= pair[i] <= acceptance[q]['maximum'][f]
            for f,pair in enumerate(row['values_ohm']) for i,q in enumerate(Q)) else 'fail')
    assert [row['classification'] for row in result['rows']] == expected
    assert set(expected)=={'pass','fail'}
    np.testing.assert_allclose(result['confidence_interval'],independent_interval(expected.count('pass'),4,.95),rtol=0,atol=1e-12)


def test_whole_grid_study_and_result_are_not_silently_accepted():
    from test_two_ground_sampled_pair_yield import random_document as whole_document,fixture as whole_fixture,GOOD as whole_good
    with pytest.raises(ValueError):Document(whole_document(),acceptance=limits())
    with pytest.raises(ValueError):assess(whole_fixture([whole_good]*4),acceptance=limits())
