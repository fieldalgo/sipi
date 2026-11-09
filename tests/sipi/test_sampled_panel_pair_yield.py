# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
from dataclasses import replace
import json
import numpy as np
import pytest
from sipi import CrossSection
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.sampled_panel_pair_study import SampledPanelForwardPairStudyDocument as StudyDocument,SampledPanelForwardPairStudy as Study,SampledPanelForwardPairStudyRow as Row
from test_sampled_panel_pair_study import document as source_document,Q,F
from test_yield_assessment import independent_interval
from sipi.sampled_panel_pair_yield import SampledPanelForwardPairYieldDocument as Document,assess_sampled_panel_pair_yield as assess


def limits(count=3):
    return {q:dict(minimum=[lo]*count,maximum=[hi]*count) for q,lo,hi in zip(Q,[90.,35.],[110.,45.])}


def random_document(count=4,kind='uniform',frequencies=F):
    raw=source_document(frequencies=frequencies).to_dict();sampling=raw['study']['sampling'];sampling['kind']=kind
    if kind=='corners':sampling.pop('count',None)
    else:sampling['count']=count
    if kind=='uniform':sampling['seed']=123
    if kind=='normal':sampling.update(seed=3,correlation=[[1.,.5],[.5,1.]],variables=[dict(name='left_width',mean=.2e-3,std=.3e-3),dict(name='gap',mean=.2e-3,std=.3e-3)])
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
    frequencies=[1.,1e9,3e9] if kind=='frequency_bool' else F
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
    for bad in [text.replace('"confidence": 0.95','"confidence": 0.95, "confidence": 0.95'),text.replace('"confidence": 0.95','"confidence": NaN'),text.replace('sipi.sampled-panel-forward-pair-yield/1','sipi.sampled-panel-forward-pair-yield/2')]:
        with pytest.raises(ValueError):Document.loads(bad)


@pytest.mark.parametrize('where',['root','acceptance','quantity'])
@pytest.mark.parametrize('change',['extra','missing'])
def test_strict_saved_keys(where,change):
    raw=Document(random_document(),acceptance=limits()).to_dict();target=raw if where=='root' else raw['acceptance'] if where=='acceptance' else raw['acceptance'][Q[0]]
    if change=='extra':target['unexpected']=1
    else:target.pop(next(iter(target)))
    with pytest.raises(ValueError):Document.from_dict(raw)
