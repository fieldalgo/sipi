# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
from dataclasses import replace
from fractions import Fraction
import json, math
import numpy as np
import pytest
from sipi.two_ground_sampled_pair_selection import TwoGroundSampledForwardPairSelectionDocument as PanelForwardPairSelectionDocument
from sipi import CrossSection
from sipi.two_ground_panel_line import TwoGroundPanelTransmissionLineDocument as PanelTransmissionLineDocument
from sipi.two_ground_sampled_pair_study import TwoGroundSampledForwardPairStudyDocument as PanelForwardPairStudyDocument
from test_two_ground_sampled_pair_yield import fixture as sampled_fixture, random_document, limits, Q
LIMITS=limits()
def fixture(values):
    return sampled_fixture([None if v is None else (v,)*3 for v in values])
from test_two_ground_sampled_pair_study import synthetic, physical_document
from test_yield_assessment import independent_interval


def document(studies=None,costs=None,*,target=.3,confidence=.95):
    studies=[random_document().to_dict()]*2 if studies is None else studies
    costs=list(range(len(studies))) if costs is None else costs
    return PanelForwardPairSelectionDocument([dict(name='candidate-'+str(i),cost=cost,study=study)
        for i,(cost,study) in enumerate(zip(costs,studies))],cost_unit='relative-cost',
        acceptance=LIMITS,minimum_yield=target,confidence=confidence)


def supplied(monkeypatch,values,costs=None,*,target=.3,confidence=.95):
    studies=[fixture(v) for v in values];seen=[]
    def analyze(self,**kwargs):
        result=studies[len(seen)];assert self.dumps()==result.input_json;seen.append(result)
        return result
    monkeypatch.setattr(PanelForwardPairStudyDocument,'analyze',analyze)
    doc=document([json.loads(s.input_json) for s in studies],costs,target=target,confidence=confidence)
    return doc,seen


def test_lowest_cost_certified_and_original_order_tie(monkeypatch):
    values=[[(100.,40.)]*20]*3
    doc,seen=supplied(monkeypatch,values,[2.,1.,1.],target=.7)
    result=doc.analyze(max_evaluations=60)
    assert result.selected_index==1 and result.status=='selected' and len(seen)==3
    out=result.to_dict();assert out['selected']==dict(index=1,name='candidate-1',cost=1.)
    assert out['evaluations']==60 and out['quantities']==list(Q) and out['unit']=='ohm'
    assert out['acceptance']==LIMITS and out['cost_unit']=='relative-cost'
    assert all(c.assessment.confidence==result.candidate_confidence for c in result.candidates)
    assert all(c.assessment.goal_status=='pass' for c in result.candidates)
    json.dumps(out,allow_nan=False)


def test_cheaper_unresolved_candidate_is_kept_and_not_excluded_as_feasible(monkeypatch):
    doc,seen=supplied(monkeypatch,[[None]*20,[(100.,40.)]*20],[0.,1.],target=.7)
    result=doc.analyze(max_evaluations=40)
    assert result.selected_index==1 and result.status=='selected' and result.unresolved==20
    assert result.candidates[0].assessment.goal_status=='undetermined' and len(seen)==2
    assert len(result.to_dict()['candidates'][0]['assessment']['rows'])==20


@pytest.mark.parametrize('values,status',[
    ([[(200.,40.)]*20,[(100.,80.)]*20],'none-certified'),
    ([[(200.,40.)]*20,[None]*20],'undetermined'),
    ([[(100.,40.)]*4,[(100.,40.)]*4],'undetermined')])
def test_none_and_undetermined_are_distinct(monkeypatch,values,status):
    doc,_=supplied(monkeypatch,values,target=.9)
    result=doc.analyze(max_evaluations=sum(map(len,values)))
    assert result.selected_index is None and result.status==status and result.to_dict()['selected'] is None


@pytest.mark.parametrize('confidence',[.5,.9,.95,.999])
def test_exact_family_error_budget_for_all_supported_counts(monkeypatch,confidence):
    shared=fixture([(100.,40.)]*2)
    monkeypatch.setattr(PanelForwardPairStudyDocument,'analyze',lambda self,**kwargs:shared)
    for count in range(1,33):
        doc=document([json.loads(shared.input_json)]*count,target=0.,confidence=confidence)
        result=doc.analyze(max_evaluations=2*count)
        level=result.candidate_confidence;alpha=1-Fraction(confidence)
        assert 0<level<1 and (1-Fraction(level))*count<=alpha
        assert Fraction(math.nextafter(level,0.))<1-alpha/count
        assert all(c.assessment.confidence==level for c in result.candidates)
        if count==1:assert level==confidence


def test_near_one_family_confidence_refuses_unrepresentable_bonferroni():
    near=float(np.nextafter(1.,0.))
    assert document([random_document().to_dict()],confidence=near).to_dict()['confidence']==near
    with pytest.raises(ValueError,match='representable'):document(confidence=near)


def test_independent_candidate_intervals_with_unknowns_and_no_factor_two(monkeypatch):
    values=[[(100.,40.),(100.,80.),None, None],[(100.,40.)]*4]
    doc,_=supplied(monkeypatch,values,target=.3)
    result=doc.analyze(max_evaluations=8)
    assert result.candidate_confidence==pytest.approx(.975,abs=1e-15)
    for candidate in result.candidates:
        a=candidate.assessment;count=len(a.classifications)
        expected=(independent_interval(a.passed,count,result.candidate_confidence)[0],
                  independent_interval(a.passed+a.unresolved,count,result.candidate_confidence)[1])
        np.testing.assert_allclose(a.confidence_interval,expected,rtol=0,atol=1e-12)
    assert result.selected_index==1 and result.unresolved==2


def test_identical_correlated_candidate_samples_keep_family_count(monkeypatch):
    doc,_=supplied(monkeypatch,[[(100.,40.)]*4]*3,[1.,1.,1.],target=0.)
    result=doc.analyze(max_evaluations=12)
    assert result.selected_index==0 and len(result.candidates)==3
    assert all(c.assessment.study.input_json==result.candidates[0].assessment.study.input_json for c in result.candidates)
    assert result.candidate_confidence>.95


def test_zero_target_does_not_hide_unknown_rows(monkeypatch):
    doc,_=supplied(monkeypatch,[[None]*4,[None]*4],[2.,1.],target=0.)
    result=doc.analyze(max_evaluations=8)
    assert result.selected_index==1 and result.unresolved==8
    assert all(c.assessment.confidence_interval==(0.,1.) for c in result.candidates)


@pytest.mark.parametrize('budget',[0,1,True,8.,10001,7])
def test_whole_family_budget_before_any_samples_or_fields(monkeypatch,budget):
    doc=document()
    def forbidden(*a,**k):pytest.fail('rejected budget reached samples or fields')
    monkeypatch.setattr(PanelForwardPairStudyDocument,'samples',forbidden)
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',forbidden)
    with pytest.raises(ValueError):doc.analyze(max_evaluations=budget)


def test_later_overflowing_sample_generation_rejects_before_first_field(monkeypatch):
    good=random_document().to_dict();bad=random_document(4,'normal').to_dict()
    bad['study']['sampling']=dict(kind='normal',count=4,seed=3,correlation=[[1.]],variables=[dict(name='width',mean=1e308,std=1e308)])
    doc=document([good,bad])
    def forbidden(*a,**k):pytest.fail('later sample overflow allowed earlier fields')
    monkeypatch.setattr(PanelForwardPairStudyDocument,'analyze',forbidden)
    with np.errstate(over='ignore',invalid='ignore'):
        with pytest.raises(ValueError):doc.analyze(max_evaluations=8)


def test_preflight_all_candidates_before_any_analysis_and_preserve_unequal_counts(monkeypatch):
    docs=[random_document(2),random_document(4)];events=[];original=PanelForwardPairStudyDocument.samples
    def samples(self):events.append(('samples',self.to_dict()['study']['sampling']['count']));return original(self)
    monkeypatch.setattr(PanelForwardPairStudyDocument,'samples',samples)
    def analyze(self,**kwargs):
        n=self.to_dict()['study']['sampling']['count'];events.append(('analysis',n))
        assert events[:2]==[('samples',2),('samples',4)]
        return fixture([(100.,40.)]*n)
    monkeypatch.setattr(PanelForwardPairStudyDocument,'analyze',analyze)
    result=document([d.to_dict() for d in docs],target=0.).analyze(max_evaluations=6)
    assert result.to_dict()['evaluations']==6
    assert [len(c.assessment.study.rows) for c in result.candidates]==[2,4]


@pytest.mark.parametrize('kind',['duplicate_name','empty_name','bad_cost','bool_cost','missing_key','extra_key','non_iid','frequency','schema','empty','too_many','tuple','missing_target','cost_unit'])
def test_invalid_candidate_contract_before_fields(monkeypatch,kind):
    raw=document().to_dict();entry=raw['candidates'][1]
    if kind=='duplicate_name':entry['name']=raw['candidates'][0]['name']
    elif kind=='empty_name':entry['name']=' '
    elif kind=='bad_cost':entry['cost']=-1.
    elif kind=='bool_cost':entry['cost']=True
    elif kind=='missing_key':entry.pop('cost')
    elif kind=='extra_key':entry['extra']=0
    elif kind=='non_iid':
        sample=entry['study']['study']['sampling'];sample['kind']='corners';sample.pop('seed');sample.pop('count')
    elif kind=='frequency':entry['study']['study']['material_evaluation']['frequency_hz']=2e9
    elif kind=='schema':raw['schema']='unknown'
    elif kind=='empty':raw['candidates']=[]
    elif kind=='too_many':raw['candidates']*=17
    elif kind=='tuple':raw['candidates']=tuple(raw['candidates'])
    elif kind=='missing_target':raw['minimum_yield']=None
    elif kind=='cost_unit':raw['cost_unit']='bad\nunit'
    def forbidden(*a,**k):pytest.fail('invalid selection reached fields')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    with pytest.raises(ValueError):PanelForwardPairSelectionDocument.from_dict(raw)


def test_strict_json_and_deep_snapshot(monkeypatch):
    def forbidden(*a,**k):pytest.fail('normalization reached fields')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    doc=document();text=doc.dumps();raw=doc.to_dict();raw['candidates'][0]['study']['panel']['panels_per_edge']=64
    assert doc.dumps()==text and PanelForwardPairSelectionDocument.loads(text).dumps()==text
    for bad in [dict(doc.to_dict(),extra=0),{k:v for k,v in doc.to_dict().items() if k!='acceptance'}]:
        with pytest.raises(ValueError):PanelForwardPairSelectionDocument.from_dict(bad)
    for bad in [text.replace('"confidence": 0.95','"confidence": 0.95, "confidence": 0.95'),text.replace('"confidence": 0.95','"confidence": NaN')]:
        with pytest.raises(ValueError):PanelForwardPairSelectionDocument.loads(bad)


def test_all_candidates_continue_after_one_extraction_failure(monkeypatch):
    calls=synthetic(monkeypatch,fail_at=2);result=document(target=0.).analyze(max_evaluations=8)
    assert len(calls)==8 and result.unresolved==1 and result.selected_index==0
    assert [len(c.assessment.study.rows) for c in result.candidates]==[4,4]
    failed=result.candidates[0].assessment.study.rows[1]
    assert failed.phase=='extraction' and failed.error_type=='TwoGroundPanelLineError'
    assert failed.cause_details['cause_type']=='ArithmeticError'
    assert failed.cause_details['message']=='original current batch refusal'
    assert failed.input_json==calls[1]
    assert result.candidates[1].assessment.unresolved==0


def test_existing_single_quantity_selection_does_not_coerce_paired_inputs():
    from sipi.yield_design import YieldDesignDocument
    with pytest.raises(ValueError):
        YieldDesignDocument(document().to_dict()['candidates'],cost_unit='relative-cost',
            minimum=90.,maximum=110.,minimum_yield=.9,schema='sipi.yield-design/3')


@pytest.mark.parametrize('failure', [None,2])
def test_common_request_record_and_project_preserve_family(monkeypatch,failure):
    from sipi.execution import normalize_saved
    from sipi.execution_request import SavedExecutionRequest
    from sipi.execution_record import SavedExecutionRecord
    from sipi.project import SavedProject
    from test_execution_record import ARTIFACTS
    calls=synthetic(monkeypatch,fail_at=failure)
    doc=document(target=0.);assert normalize_saved(doc.dumps())==doc.dumps()
    request=SavedExecutionRequest(doc.dumps(),max_evaluations=8);receipt=request.run()
    out=receipt['execution'];result=out['result']
    assert out['status']==('complete' if failure is None else 'incomplete') and len(calls)==8
    assert result['evaluations']==8 and len(result['candidates'])==2
    assert result['unresolved']==(0 if failure is None else 1)
    for candidate in result['candidates']:
        assert candidate['study']['schema']=='sipi.two-ground-sampled-forward-pair-study/1'
        assert candidate['assessment']['scope']=='iid-stated-two-ground-frequency-grid-not-measured-production-yield'
    record=SavedExecutionRecord(request,receipt,run_id='grid-family:synthetic',artifacts=ARTIFACTS)
    project=SavedProject(request,project_id='grid-family',design_id='a',title='Candidates',label='Fixed set').attach_record('a',record)
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('restore solved'))
    assert SavedExecutionRecord.loads(record.dumps()).receipt==receipt
    assert SavedProject.loads(project.dumps()).prepare('a').request_id==request.request_id


@pytest.mark.parametrize('control',['budget','diagnostics','bytes'])
def test_host_controls_precede_all_candidate_fields(monkeypatch,control):
    from sipi.execution import execute_saved
    calls=synthetic(monkeypatch)
    kw={'max_evaluations':7} if control=='budget' else {'diagnostics':['characteristic']} if control=='diagnostics' else {'max_input_bytes':16}
    with pytest.raises(ValueError):execute_saved(document().dumps(),**kw)
    assert not calls


def test_interrupt_stops_family_without_selecting_earlier_candidate(monkeypatch):
    calls=synthetic(monkeypatch,fail_at=6,interrupt=True)
    with pytest.raises(KeyboardInterrupt):document(target=0.).analyze(max_evaluations=8)
    assert len(calls)==6


def test_valid_different_frequency_vectors_cannot_share_family_limits():
    a=random_document().to_dict();b=random_document(frequencies=[1e9,3e9,5e9]).to_dict()
    with pytest.raises(ValueError,match='exact same ordered frequency grid'):document([a,b])


def test_frequency_count_does_not_change_family_allocation_or_trials(monkeypatch):
    results=[]
    for n in (3,64):
        frequencies=np.geomspace(1e9,5e9,n)
        study=sampled_fixture([((100.,40.),)*n]*4,frequencies=frequencies)
        monkeypatch.setattr(PanelForwardPairStudyDocument,'analyze',lambda self,**kw:study)
        entries=[dict(name=str(i),cost=i,study=json.loads(study.input_json)) for i in range(2)]
        doc=PanelForwardPairSelectionDocument(entries,cost_unit='relative',acceptance=limits(n),minimum_yield=0.)
        result=doc.analyze(max_evaluations=8);results.append(result)
        assert result.to_dict()['evaluations']==8
    assert results[0].candidate_confidence==results[1].candidate_confidence
    assert results[0].candidates[0].assessment.confidence_interval==results[1].candidates[0].assessment.confidence_interval


def test_original_document_does_not_accept_two_ground_source():
    from sipi.sampled_panel_pair_selection import SampledPanelForwardPairSelectionDocument
    raw=document().to_dict();raw['schema']='sipi.sampled-panel-forward-pair-selection/1'
    with pytest.raises(ValueError):SampledPanelForwardPairSelectionDocument.from_dict(raw)


def test_real_registered_fixed_debye_family_and_independent_bounds(record_property):
    from sipi.execution_request import SavedExecutionRequest
    entries=[]
    for index,(lower,upper) in enumerate(((.00043,.00044),(.00044,.00045))):
        raw=physical_document().to_dict()
        raw['study']['sampling'].update(kind='uniform',count=4,seed=19,
            variables=[dict(name='width',lower=lower,upper=upper)])
        entries.append(dict(name='fixed-'+str(index),cost=index+1.,study=raw))
    acceptance={q:dict(minimum=[1.]*3,maximum=[1000.]*3) for q in Q}
    doc=PanelForwardPairSelectionDocument(entries,cost_unit='relative',acceptance=acceptance,confidence=.9,minimum_yield=.1)
    request=SavedExecutionRequest(doc.dumps(),max_evaluations=8);receipt=request.run()
    record_property('two_ground_grid_family_receipt',json.dumps(receipt,sort_keys=True))
    out=receipt['execution'];assert out['status']=='complete';result=out['result']
    assert result['evaluations']==8 and result['unresolved']==0
    assert result['selected']==dict(index=0,name='fixed-0',cost=1.)
    for entry,candidate in zip(doc.to_dict()['candidates'],result['candidates']):
        assert candidate['study']==entry['study']
        report=candidate['assessment'];assert report['passed']==4 and report['failed']==0
        np.testing.assert_allclose(report['confidence_interval'],independent_interval(4,4,result['candidate_confidence']),rtol=0,atol=1e-12)
        for row,sample in zip(report['rows'],PanelForwardPairStudyDocument.from_dict(entry['study']).samples()):
            assert row['sample_values']==list(sample) and row['classification']=='pass'
            assert row['current_solver']['kind']=='two-ground-rectangle-panels' and row['dielectric_mesh']
            assert all(1.<=value<=1000. for pair in row['values_ohm'] for value in pair)


def test_input_snapshot_is_serialized_after_all_original_attempts(monkeypatch):
    doc,seen=supplied(monkeypatch,[[(100.,40.)]*4]*2,target=0.)
    original=doc.dumps;events=[]
    def dumps():
        events.append(len(seen))
        return original()
    monkeypatch.setattr(doc,'dumps',dumps)
    doc.analyze(max_evaluations=8)
    assert events==[2]
