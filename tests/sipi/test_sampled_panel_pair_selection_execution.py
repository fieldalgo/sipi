# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
import json
import pytest
from sipi.sampled_panel_pair_selection import SampledPanelForwardPairSelectionDocument as PanelForwardPairSelectionDocument
from sipi.sampled_panel_pair_study import SampledPanelForwardPairStudyDocument as PanelForwardPairStudyDocument
from sipi.panel_line import PanelTransmissionLineDocument
from test_sampled_panel_pair_goal import synthetic
from test_sampled_panel_pair_yield import random_document,Q
from test_sampled_panel_pair_selection import document
import sipi.execution as execution
execute_saved=execution.execute_saved;normalize_saved=execution.normalize_saved;saved_schemas=execution.saved_schemas

def test_common_execution_matches_direct_and_keeps_full_candidate_inputs(monkeypatch):
    calls=synthetic(monkeypatch);doc=document(target=0.)
    expected=doc.analyze(max_evaluations=8).to_dict();output=execute_saved(doc.dumps(),max_evaluations=8)
    assert output['status']=='complete' and output['error'] is None and output['input']==doc.to_dict()
    assert output['result']==expected and len(calls)==16
    assert normalize_saved(doc.dumps())==doc.dumps()
    assert 'sipi.sampled-panel-forward-pair-selection/1' in saved_schemas()
    json.dumps(output,allow_nan=False)


@pytest.mark.parametrize('mode',['budget','diagnostics','input_bytes'])
def test_transport_rejects_before_family_sampling_or_fields(monkeypatch,mode):
    doc=document()
    def forbidden(*a,**k):pytest.fail('refused transport reached sampling or fields')
    monkeypatch.setattr(PanelForwardPairStudyDocument,'samples',forbidden)
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',forbidden)
    options={'max_evaluations':7} if mode=='budget' else ({'diagnostics':['characteristic']} if mode=='diagnostics' else {'max_input_bytes':16})
    with pytest.raises(ValueError):execute_saved(doc.dumps(),**options)


@pytest.mark.parametrize('phase',['parameters','materials','input','extraction','diagnostic'])
def test_common_execution_preserves_failure_then_later_candidates(monkeypatch,phase):
    import sipi.sampled_panel_pair_study as module
    calls=synthetic(monkeypatch,fail_at=2 if phase=='extraction' else None)
    if phase in ('parameters','materials','input'):
        name=dict(parameters='_parameters',materials='_sample_material',input='_line_from_inputs')[phase]
        original=getattr(module,name);seen=[]
        def fail_second(*a,**k):
            seen.append(1)
            if len(seen)==2:raise ArithmeticError('retained candidate row cause')
            return original(*a,**k)
        monkeypatch.setattr(module,name,fail_second)
    elif phase=='diagnostic':
        original=PanelTransmissionLineDocument.analyze
        def diagnose(self):
            line=original(self)
            if len(calls)==2:
                def fail():raise ArithmeticError('retained candidate row cause')
                line.characteristic=fail
            return line
        monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',diagnose)
    doc=document(target=0.);output=execute_saved(doc.dumps(),max_evaluations=8);result=output['result']
    assert output['status']=='incomplete' and output['error'] is None and output['input']==doc.to_dict()
    assert result['status']=='selected' and result['evaluations']==8 and result['unresolved']==1
    row=result['candidates'][0]['assessment']['rows'][1]
    assert row['phase']==phase and row['classification']=='unresolved' and row['values_ohm'] is None
    assert row['error_type']=='ArithmeticError'
    assert row['error']==('original failed frequency batch' if phase=='extraction' else 'retained candidate row cause')
    assert row['sample_values']==random_document().samples()[1].tolist()
    assert (row['parameters'] is not None)==(phase!='parameters')
    assert (row['material_evaluation'] is not None)==(phase not in ('parameters','materials'))
    assert (row['input'] is not None)==(phase in ('extraction','diagnostic'))
    assert result['candidates'][1]['assessment']['unresolved']==0
    assert [r['index'] for r in result['candidates'][1]['assessment']['rows']]==list(range(4))
    json.dumps(output,allow_nan=False)


def test_no_candidate_certified_is_complete_when_all_fields_succeed(monkeypatch):
    synthetic(monkeypatch);raw=document(target=.9).to_dict()
    raw['acceptance']={q:dict(minimum=[None]*3,maximum=[0.]*3) for q in Q}
    output=execute_saved(PanelForwardPairSelectionDocument.from_dict(raw).dumps(),max_evaluations=8)
    assert output['status']=='complete' and output['result']['status']=='none-certified'
    assert output['result']['selected'] is None and output['result']['unresolved']==0
