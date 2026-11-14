# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Whole-plan budgets, strict snapshots and retained resolution disagreements."""
import json
import numpy as np
import pytest
from sipi import CrossSection
from sipi.panel_pair_study import PanelForwardPairStudyDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.panel_resolution_yield import assess_panel_pair_resolution_yield
from sipi.panel_resolution_yield_document import PanelResolutionYieldDocument
from sipi.execution import execute_saved, normalize_saved
from test_panel_pair_yield import random_document, LIMITS
from test_panel_pair_goal import synthetic


def document(*,physical=False):
    if physical:
        from test_layered_panel_study import document as coated, LIMITS as limits
        raw=coated().to_dict();raw['study']['sampling']['count']=2
        stages=('base','volume','panel','joint')
    else:
        raw=random_document(2).to_dict();limits=LIMITS;stages=('base','joint')
    studies=[]
    for stage in stages:
        data=json.loads(json.dumps(raw))
        if stage in ('volume','joint'):
            for key in ('edge_size','far_size','grade'):data['study']['mesh'][key]/=2
        if stage in ('panel','joint'):data['panel']['panels_per_edge']*=2
        studies.append(PanelForwardPairStudyDocument.from_dict(data))
    return PanelResolutionYieldDocument(studies,acceptance=limits,minimum_yield=.9)


def test_field_free_canonical_snapshots_and_required_budget(monkeypatch):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('normalization meshed'))
    monkeypatch.setattr(PanelForwardPairStudyDocument,'analyze',lambda *a,**k:pytest.fail('normalization analyzed'))
    doc=document();text=doc.dumps()
    assert doc.required_evaluations==4
    assert normalize_saved(text)==text==PanelResolutionYieldDocument.loads(text).dumps()
    raw=doc.to_dict();raw['studies'][0]['panel']['panels_per_edge']=256
    nested=doc.studies[0];nested._data['panel']['panels_per_edge']=256
    assert doc.dumps()==text and doc.studies[0].to_dict()['panel']['panels_per_edge']==32


def test_direct_and_common_execution_match_exactly(monkeypatch):
    calls=synthetic(monkeypatch);doc=document();direct=doc.analyze(max_evaluations=4)
    assert len(calls)==4
    expected=assess_panel_pair_resolution_yield([d.analyze(max_evaluations=2) for d in doc.studies],
        acceptance=LIMITS,minimum_yield=.9)
    assert expected.to_dict()==direct.to_dict()
    calls.clear();out=execute_saved(doc.dumps(),max_evaluations=4)
    assert out['status']==('incomplete' if direct.unresolved else 'complete')
    assert out['input']==doc.to_dict() and out['result']==direct.to_dict() and out['error'] is None
    assert len(calls)==4 and out['result']['count']==2
    json.dumps(out,allow_nan=False)


@pytest.mark.parametrize('attempt',[1,2,3,4])
def test_original_failed_rows_are_incomplete_but_every_planned_row_is_attempted(monkeypatch,attempt):
    calls=synthetic(monkeypatch,fail_at=attempt);doc=document()
    out=execute_saved(doc.dumps(),max_evaluations=4)
    assert out['status']=='incomplete' and out['error'] is None and len(calls)==4
    result=out['result'];assert result['count']==2 and result['unresolved']==1
    source=result['resolutions'][(attempt-1)//2]['assessment']['rows'][(attempt-1)%2]
    assert source['phase']=='extraction' and source['error_type']=='ArithmeticError'
    assert source['input']==json.loads(calls[attempt-1]) and source['values_ohm'] is None
    assert result['rows'][(attempt-1)%2]['classification']=='unresolved'


@pytest.mark.parametrize('budget',[0,1,2,3,True,4.,10001])
def test_whole_plan_budget_rejected_before_any_analysis(monkeypatch,budget):
    doc=document()
    monkeypatch.setattr(PanelForwardPairStudyDocument,'analyze',lambda *a,**k:pytest.fail('rejected plan analyzed'))
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('rejected plan meshed'))
    with pytest.raises(ValueError):doc.analyze(max_evaluations=budget)
    with pytest.raises(ValueError):execute_saved(doc.dumps(),max_evaluations=budget)


@pytest.mark.parametrize('options',[dict(diagnostics=['characteristic']),dict(max_input_bytes=16)])
def test_common_transport_limits_before_fields(monkeypatch,options):
    doc=document()
    monkeypatch.setattr(PanelResolutionYieldDocument,'analyze',lambda *a,**k:pytest.fail('rejected request analyzed'))
    with pytest.raises(ValueError):execute_saved(doc.dumps(),**options)


@pytest.mark.parametrize('where',['root','source','panel','acceptance'])
@pytest.mark.parametrize('mode',['missing','extra'])
def test_strict_nested_keys(where,mode):
    raw=document().to_dict()
    target={'root':raw,'source':raw['studies'][0],'panel':raw['studies'][0]['panel'],
            'acceptance':raw['acceptance']}[where]
    if mode=='missing':target.pop(next(iter(target)))
    else:target['unexpected']=1
    with pytest.raises(ValueError):PanelResolutionYieldDocument.from_dict(raw)


@pytest.mark.parametrize('mode',['schema','duplicate','nonfinite','nonobject','nested-schema'])
def test_ambiguous_json_and_versions_refused(mode):
    raw=document().to_dict();text=json.dumps(raw)
    if mode=='schema':raw['schema']='sipi.panel-resolution-yield/unsupported'
    if mode=='nested-schema':raw['studies'][0]['schema']='unknown'
    if mode=='duplicate':text=text.replace('"ground_modes": 512','"ground_modes": 512, "ground_modes": 512')
    elif mode=='nonfinite':text=text.replace('"confidence": 0.95','"confidence": NaN')
    elif mode=='nonobject':text='[]'
    else:text=json.dumps(raw)
    with pytest.raises(ValueError):PanelResolutionYieldDocument.loads(text)


@pytest.mark.parametrize('mode',['duplicate','geometry','seed','mixed-schema','too-many','one','not-list','corners','total-budget'])
def test_plan_preflight_rejects_without_solving(monkeypatch,mode):
    raw=document().to_dict()
    if mode=='duplicate':raw['studies'][1]=raw['studies'][0]
    if mode=='geometry':raw['studies'][1]['study']['parameters']['left_width']*=1.01
    if mode=='seed':raw['studies'][1]['study']['sampling']['seed']+=1
    if mode=='mixed-schema':raw['studies'][1]['schema']='sipi.panel-forward-pair-study/2'
    if mode=='too-many':raw['studies']*=5
    if mode=='one':raw['studies']=raw['studies'][:1]
    if mode=='not-list':raw['studies']={}
    if mode=='corners':
        for item in raw['studies']:
            sampling=item['study']['sampling'];sampling['kind']='corners'
            sampling.pop('seed',None);sampling.pop('count',None)
    if mode=='total-budget':
        for item in raw['studies']:item['study']['sampling']['count']=5001
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('preflight meshed'))
    with pytest.raises(ValueError):PanelResolutionYieldDocument.from_dict(raw)


def test_generation_failure_precedes_all_fields_and_interrupts_propagate(monkeypatch):
    doc=document();calls=[]
    original=PanelForwardPairStudyDocument.samples
    def failed(self):raise OverflowError('retained sample failure')
    monkeypatch.setattr(PanelForwardPairStudyDocument,'samples',failed)
    monkeypatch.setattr(PanelForwardPairStudyDocument,'analyze',lambda *a,**k:calls.append(1))
    with pytest.raises(OverflowError,match='retained sample failure'):doc.analyze(max_evaluations=4)
    assert not calls
    monkeypatch.setattr(PanelForwardPairStudyDocument,'samples',original)
    def interrupt(*a,**k):calls.append(1);raise KeyboardInterrupt
    monkeypatch.setattr(PanelForwardPairStudyDocument,'analyze',interrupt)
    with pytest.raises(KeyboardInterrupt):doc.analyze(max_evaluations=4)
    assert calls==[1]


@pytest.mark.parametrize('value',[None,{},[None]])
def test_constructor_requires_source_documents(value):
    with pytest.raises(TypeError):PanelResolutionYieldDocument(value,acceptance=LIMITS)


def test_actual_saved_coated_disagreement_and_common_replay(monkeypatch,record_property):
    from test_layered_panel_goal import independent,snapshot
    doc=document(physical=True);fields={};original=PanelTransmissionLineDocument.analyze
    def capture(self):
        line=original(self);fields[self.dumps()]=line;return line
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',capture)
    result=doc.analyze(max_evaluations=8)
    record_property('saved_resolution_fields',json.dumps([snapshot(r) for r in fields.values()],allow_nan=False))
    record_property('saved_resolution_references',json.dumps([independent(r) for r in fields.values()]))
    assert len(fields)==8 and result.classifications==('unresolved','pass')
    assert result.sample_fraction_bounds==(.5,1.)
    calls=[]
    def replay(self):
        calls.append(self.dumps());assert self.dumps() in fields
        return fields[self.dumps()]
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',replay)
    out=execute_saved(doc.dumps(),max_evaluations=8)
    record_property('saved_resolution_execution',json.dumps(out,allow_nan=False))
    assert out['status']=='incomplete' and out['error'] is None and out['result']==result.to_dict()
    assert out['input']==doc.to_dict() and len(calls)==doc.required_evaluations==8
    assert out['result']['count']==2 and out['result']['resolution_count']==4
