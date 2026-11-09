# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
import json
import numpy as np
import pytest
from sipi import CrossSection
from sipi.panel_line import PanelTransmissionLineDocument
from test_sampled_panel_pair_goal_document import document, Document, F, synthetic
import sipi.execution as execution


def test_saved_execution_and_independent_modal_root(monkeypatch):
    synthetic(monkeypatch);doc=document();output=execution.execute_saved(doc.dumps(),max_evaluations=64)
    assert output['status']=='complete' and output['error'] is None and output['input']==doc.to_dict()
    np.testing.assert_allclose(output['result']['parameters'],[1.35*.3e-3,.8*.2e-3],rtol=1e-6)
    assert output['result']['frequencies_hz']==list(F)
    json.dumps(output,allow_nan=False)


def test_registry_normalization_and_preflight_budget_before_fields(monkeypatch):
    assert 'sipi.sampled-panel-forward-pair-design/1' in execution.saved_schemas()
    def forbidden(*a,**k):pytest.fail('budget preflight invoked fields')
    monkeypatch.setattr(CrossSection,'mesh',forbidden);monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',forbidden)
    doc=document();assert execution.normalize_saved(doc.dumps())==doc.dumps()
    with pytest.raises(ValueError,match='batch budget'):execution.execute_saved(doc.dumps(),max_evaluations=63)
    with pytest.raises(ValueError,match='top-level'):execution.execute_saved(doc.dumps(),diagnostics=['characteristic'])


@pytest.mark.parametrize('attempt',[1,2,3,4])
def test_failed_execution_keeps_frequency_batch_and_original_cause(monkeypatch,attempt):
    calls=synthetic(monkeypatch,fail_at=attempt);raw=document().to_dict();raw['initial']=[1.35*.3e-3,.8*.2e-3];raw['max_evaluations']=4
    doc=Document.from_dict(raw);output=execution.execute_saved(doc.dumps(),max_evaluations=4)
    assert output['status']=='failed' and output['result'] is None
    e=output['error'];assert e['attempts']==len(calls)==attempt and len(e['history'])==attempt-1
    assert e['frequencies_hz']==list(F) and e['cause_type']=='ArithmeticError' and e['input']==json.loads(calls[-1])
    assert e['stage']==['search','volume-refinement','panel-refinement','joint-refinement'][attempt-1]+'/extraction'
    json.dumps(output,allow_nan=False)


def test_failed_budget_history_is_returned_without_clamping(monkeypatch):
    calls=synthetic(monkeypatch);raw=document().to_dict();raw['max_evaluations']=5
    output=execution.execute_saved(Document.from_dict(raw).dumps(),max_evaluations=5)
    assert output['status']=='failed' and output['error']['stage']=='budget'
    assert output['error']['attempts']==len(output['error']['history'])==len(calls)==2
    assert output['input']['max_evaluations']==5


def test_frequency_count_does_not_consume_batch_budget(monkeypatch):
    from test_sampled_panel_pair_goal import targets
    from test_sampled_panel_pair_goal_document import Q
    calls=synthetic(monkeypatch);raw=document().to_dict()
    frequencies=np.geomspace(F[0],F[-1],9)
    raw['frequency_hz']=frequencies.tolist();raw['initial']=[1.35*.3e-3,.8*.2e-3];raw['max_evaluations']=4
    for i,q in enumerate(Q):
        raw['targets_ohm'][q]=targets(frequencies=frequencies)[:,i].tolist()
        raw['tolerances_ohm'][q]=[1e-6]*9
    output=execution.execute_saved(Document.from_dict(raw).dumps(),max_evaluations=4)
    assert output['status']=='complete' and output['result']['evaluations']==len(calls)==4
    assert output['result']['frequencies_hz']==frequencies.tolist()
