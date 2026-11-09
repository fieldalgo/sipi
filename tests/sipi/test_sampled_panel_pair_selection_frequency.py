# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
import json
import numpy as np
import pytest
from sipi.sampled_panel_pair_selection import SampledPanelForwardPairSelectionDocument as Document
from test_sampled_panel_pair_selection import document
from test_sampled_panel_pair_yield import fixture,random_document,limits,GOOD,BAD,Q
from sipi.sampled_panel_pair_study import SampledPanelForwardPairStudyDocument as Study

@pytest.mark.parametrize('change',['last','length','anchor','reordered'])
def test_every_candidate_uses_same_exact_full_frequency_vector(change):
    raw=document().to_dict();study=raw['candidates'][1]['study']
    if change=='last':study['frequency_hz'][-1]*=1.1
    elif change=='length':study['frequency_hz'].append(study['frequency_hz'][-1]*2)
    elif change=='anchor':study['frequency_hz'][0]*=.5;study['study']['material_evaluation']['frequency_hz']=study['frequency_hz'][0]
    else:study['frequency_hz'][1:]=reversed(study['frequency_hz'][1:])
    with pytest.raises(ValueError):Document.from_dict(raw)

def test_family_allocation_does_not_scale_with_frequency_count(monkeypatch):
    levels=[];intervals=[]
    for n in [2,3,9,64]:
        grid=np.geomspace(5e8,2e9,n);rows=[((100.,40.),)*n]*4
        result=fixture(rows,frequencies=grid)
        monkeypatch.setattr(Study,'analyze',lambda self,**kwargs:result)
        raw=document([json.loads(result.input_json)]*2,target=.3).to_dict() if n==3 else None
        if raw is None:
            raw=dict(schema='sipi.sampled-panel-forward-pair-selection/1',candidates=[dict(name=str(i),cost=i,study=json.loads(result.input_json)) for i in range(2)],cost_unit='relative-cost',acceptance=limits(n),confidence=.95,minimum_yield=.3)
        selected=Document.from_dict(raw).analyze(max_evaluations=8)
        assert selected.selected_index==0 and selected.to_dict()['evaluations']==8
        assert selected.to_dict()['frequencies_hz']==grid.tolist()
        levels.append(selected.candidate_confidence);intervals.append(selected.candidates[0].assessment.confidence_interval)
    assert len(set(levels))==len(set(intervals))==1

def test_frequency_specific_joint_failure_prevents_marginal_selection(monkeypatch):
    a=fixture([BAD]*4);b=fixture([GOOD]*4);pending=iter([a,b])
    monkeypatch.setattr(Study,'analyze',lambda self,**kwargs:next(pending))
    doc=document([json.loads(a.input_json),json.loads(b.input_json)],[0.,1.],target=.3)
    result=doc.analyze(max_evaluations=8)
    assert result.selected_index==1
    assert result.candidates[0].assessment.classifications==('fail',)*4
    assert result.candidates[1].assessment.classifications==('pass',)*4

@pytest.mark.parametrize('change',['scalar','short','unbounded','boolean'])
def test_no_implicit_limit_broadcast(change):
    raw=document().to_dict();value=raw['acceptance'][Q[0]]
    if change=='scalar':value['minimum']=90.
    elif change=='short':value['maximum'].pop()
    elif change=='unbounded':value['minimum'][1]=value['maximum'][1]=None
    else:value['minimum'][1]=True
    with pytest.raises(ValueError):Document.from_dict(raw)
