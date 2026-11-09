# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
import json
import numpy as np
import pytest
from sipi import CrossSection
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.sampled_panel_pair_study import SampledPanelForwardPairStudyDocument
from test_sampled_panel_pair_study import synthetic
from test_sampled_panel_pair_yield import Document,random_document,limits,fixture,GOOD,BAD,F,Q
import sipi.execution as execution


def test_saved_transport_matches_direct_and_retains_full_grid(monkeypatch):
    synthetic(monkeypatch);doc=Document(random_document(),acceptance=limits(),minimum_yield=.9)
    expected=doc.analyze(max_evaluations=4).to_dict();output=execution.execute_saved(doc.dumps(),max_evaluations=4)
    assert output['status']=='complete' and output['result']==expected and output['input']==doc.to_dict()
    assert output['result']['frequencies_hz']==list(F) and output['result']['count']==4
    assert execution.normalize_saved(doc.dumps())==doc.dumps()
    assert 'sipi.sampled-panel-forward-pair-yield/1' in execution.saved_schemas()
    json.dumps(output,allow_nan=False)


@pytest.mark.parametrize('mode',['budget','diagnostics','input_bytes'])
def test_transport_limits_are_checked_before_fields(monkeypatch,mode):
    doc=Document(random_document(),acceptance=limits())
    def forbidden(*a,**k):pytest.fail('invalid transport invoked fields')
    monkeypatch.setattr(CrossSection,'mesh',forbidden);monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',forbidden)
    options={'max_evaluations':3} if mode=='budget' else {'diagnostics':['characteristic']} if mode=='diagnostics' else {'max_input_bytes':16}
    with pytest.raises(ValueError):execution.execute_saved(doc.dumps(),**options)


@pytest.mark.parametrize('target',[None,0.,.9])
def test_execution_incomplete_is_separate_from_yield_goal_status(monkeypatch,target):
    study=fixture([GOOD,None,BAD,None]);doc=Document(SampledPanelForwardPairStudyDocument.loads(study.input_json),acceptance=limits(),minimum_yield=target)
    monkeypatch.setattr(SampledPanelForwardPairStudyDocument,'analyze',lambda self,**kw:study)
    output=execution.execute_saved(doc.dumps(),max_evaluations=4);r=output['result']
    assert output['status']=='incomplete' and output['error'] is None
    assert (r['passed'],r['failed'],r['unresolved'],r['count'])==(1,1,2,4)
    assert r['goal_status']==('not-requested' if target is None else 'pass' if target==0 else 'undetermined')
    assert [row['classification'] for row in r['rows']]==['pass','unresolved','fail','unresolved']
    json.dumps(output,allow_nan=False)


def test_original_field_failure_stays_unresolved_and_later_rows_run(monkeypatch):
    calls=synthetic(monkeypatch,fail_at=2);doc=Document(random_document(),acceptance=limits())
    output=execution.execute_saved(doc.dumps(),max_evaluations=4);r=output['result']
    assert output['status']=='incomplete' and r['unresolved']==1 and r['count']==len(calls)==4
    assert r['rows'][1]['phase']=='extraction' and r['rows'][1]['error_type']=='ArithmeticError'
    assert r['rows'][1]['classification']=='unresolved' and r['rows'][1]['values_ohm'] is None
    assert r['rows'][-1]['phase']=='complete' and r['frequencies_hz']==list(F)
