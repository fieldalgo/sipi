# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
import json
import pytest
from sipi import CrossSection
from sipi.panel_line import PanelTransmissionLineDocument
from test_sampled_panel_pair_study import document, synthetic, F
import sipi.sampled_panel_pair_study as module
import sipi.execution as execution


def test_transport_complete_matches_direct_and_preserves_grid(monkeypatch):
    synthetic(monkeypatch);doc=document();expected=doc.analyze(max_evaluations=4).to_dict()
    output=execution.execute_saved(doc.dumps(),max_evaluations=4)
    assert output['status']=='complete' and output['error'] is None and output['input']==doc.to_dict()
    assert output['result']==expected and output['result']['frequencies_hz']==list(F)
    assert execution.normalize_saved(doc.dumps())==doc.dumps()
    assert 'sipi.sampled-panel-forward-pair-study/1' in execution.saved_schemas()
    json.dumps(output,allow_nan=False)


@pytest.mark.parametrize('mode',['budget','diagnostics','input_bytes'])
def test_transport_limit_before_any_fields(monkeypatch,mode):
    doc=document()
    def forbidden(*a,**k):pytest.fail('refused transport invoked fields')
    monkeypatch.setattr(CrossSection,'mesh',forbidden);monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',forbidden)
    options={'max_evaluations':3} if mode=='budget' else {'diagnostics':['characteristic']} if mode=='diagnostics' else {'max_input_bytes':16}
    with pytest.raises(ValueError):execution.execute_saved(doc.dumps(),**options)


@pytest.mark.parametrize('phase',['parameters','materials','input','extraction','diagnostic'])
def test_transport_keeps_all_rows_and_atomic_failed_frequency_batch(monkeypatch,phase):
    calls=synthetic(monkeypatch,fail_at=2 if phase=='extraction' else None);doc=document()
    if phase in ('parameters','materials','input'):
        name=dict(parameters='_parameters',materials='_sample_material',input='_line_from_inputs')[phase];original=getattr(module,name);seen=[]
        def broken(*a,**k):
            seen.append(1)
            if len(seen)==2:raise ArithmeticError('original failed row')
            return original(*a,**k)
        monkeypatch.setattr(module,name,broken)
    if phase=='diagnostic':
        original=PanelTransmissionLineDocument.analyze
        def broken(self):
            line=original(self)
            if len(calls)==2:
                def fail():raise ArithmeticError('original failed row')
                line.characteristic=fail
            return line
        monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',broken)
    output=execution.execute_saved(doc.dumps(),max_evaluations=4);result=output['result']
    assert output['status']=='incomplete' and output['error'] is None
    assert result['count']==4 and result['failed']==1 and result['summary'] is None and result['frequencies_hz']==list(F)
    assert result['rows'][1]['phase']==phase and result['rows'][1]['values_ohm'] is None
    assert result['rows'][1]['error_type']=='ArithmeticError' and result['rows'][3]['phase']=='complete'
    json.dumps(output,allow_nan=False)
