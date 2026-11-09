# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
from dataclasses import FrozenInstanceError
import hashlib,json
import pytest
import sipi.execution_request as candidate
from sipi.execution_request import SavedExecutionRequest as Request
from sipi import CrossSection
from sipi.execution import execute_saved,saved_schemas
from sipi.panel_line import PanelTransmissionLineDocument
from test_execution import documents,lumped,line,cross
from test_sampled_panel_pair_goal import synthetic
from test_sampled_panel_pair_yield import random_document


def test_every_registered_schema_prepares_without_fields(monkeypatch):
    def forbidden(*a,**k):pytest.fail('request preparation executed fields')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    monkeypatch.setattr(candidate,'execute_saved',forbidden)
    seen=[]
    for document in documents():
        request=Request(document.dumps());seen.append(json.loads(request.input_json)['schema'])
        assert request.input_json==document.dumps()
        assert request.input_sha256==hashlib.sha256(document.dumps().encode('utf-8')).hexdigest()
        envelope=dict(schema='sipi.execution-request/1',input=document.to_dict(),controls=request.controls)
        encoded=json.dumps(envelope,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')
        assert request.request_id==hashlib.sha256(encoded).hexdigest()
    assert set(seen)==set(saved_schemas()) and len(seen)==len(saved_schemas())


def test_canonical_semantics_and_original_source_are_distinct():
    raw=lumped().to_dict();a=json.dumps(raw);b=json.dumps(dict(reversed(list(raw.items()))),indent=4)
    first=Request(a);second=Request(b)
    assert first.source_text==a and second.source_text==b and a!=b
    assert first.request_id==second.request_id and first.input_sha256==second.input_sha256
    # Use a validated independently constructed changed electrical document.
    from sipi import LumpedNetworkDocument
    changed=Request(LumpedNetworkDocument([0,1e9],resistance=20.,inductance=2e-9).dumps())
    assert changed.request_id!=first.request_id and changed.input_sha256!=first.input_sha256


def test_all_controls_affect_request_identity_but_not_input_hash():
    text=line().dumps();base=Request(text)
    variants=[Request(text,max_input_bytes=262145),Request(text,max_evaluations=129),Request(text,diagnostics=['characteristic'])]
    assert len({base.request_id,*(v.request_id for v in variants)})==4
    assert all(v.input_sha256==base.input_sha256 for v in variants)
    a=Request(text,diagnostics=['modes','characteristic']);b=Request(text,diagnostics=['characteristic','modes'])
    assert a.request_id==b.request_id and a.diagnostics==('characteristic','modes')


def test_frozen_source_and_returned_snapshots_do_not_alias():
    values=['modes'];request=Request(line().dumps(),diagnostics=values);before=request.to_dict()
    values.append('characteristic');request.controls['diagnostics'].append('characteristic')
    copy=request.to_dict();copy['controls']['max_evaluations']=900;copy['input']['frequency_hz'][0]=77
    assert request.to_dict()==before
    with pytest.raises(FrozenInstanceError):request.max_evaluations=500
    with pytest.raises(FrozenInstanceError):request.source_text='{}'


@pytest.mark.parametrize('options',[
    dict(max_evaluations=True),dict(max_evaluations=1),dict(max_evaluations=10001),dict(max_evaluations=2.),
    dict(max_input_bytes=True),dict(max_input_bytes=0),dict(max_input_bytes=1.),
    dict(diagnostics='modes'),dict(diagnostics={'modes'}),dict(diagnostics=['modes','modes']),
    dict(diagnostics=['unknown']),dict(diagnostics=[True]),dict(diagnostics=None)])
def test_invalid_generic_options_reject_before_fields(monkeypatch,options):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('invalid controls ran fields'))
    with pytest.raises(ValueError):Request(line().dumps(),**options)


def test_non_line_diagnostics_rejected_while_valid_lines_prepare():
    with pytest.raises(ValueError,match='top-level'):Request(cross().dumps(),diagnostics=['modes'])
    Request(line().dumps(),diagnostics=['modes'])
    Request(PanelTransmissionLineDocument(line()).dumps(),diagnostics=['characteristic'])


@pytest.mark.parametrize('text',['[]','{}','null','{"schema":"unknown"}','{"schema":"x","schema":"x"}','{"schema":"x","a":NaN}','{"schema":"x","a":1e999}'])
def test_strict_saved_validation_is_retained(text):
    with pytest.raises(ValueError):Request(text)


def test_unicode_byte_limit_and_canonical_expansion_preserve_admission():
    from sipi import LumpedNetworkDocument
    doc=LumpedNetworkDocument([0,1e9],resistance=10.,port_names=('입력','출력'))
    text=json.dumps(doc.to_dict(),separators=(',',':'),ensure_ascii=False)
    size=len(text.encode('utf-8'));assert size>len(text)
    with pytest.raises(ValueError,match='max_input_bytes'):Request(text,max_input_bytes=size-1)
    request=Request(text,max_input_bytes=size)
    assert len(request.input_json.encode('utf-8'))>size
    receipt=request.run();assert receipt['execution']==execute_saved(text,max_input_bytes=size)
    assert receipt['request']==request.to_dict()


def test_repeated_request_needs_host_run_token():
    request=Request(lumped().dumps());a=request.run();b=request.run()
    assert a==b and a['request']['request_id']==request.request_id
    a['request']['controls']['max_evaluations']=900
    assert request.max_evaluations==128 and b['request']==request.to_dict()


@pytest.mark.parametrize('fail_at',[None,2])
def test_study_complete_and_incomplete_match_existing_execution(monkeypatch,fail_at):
    text=random_document().dumps();synthetic(monkeypatch,fail_at=fail_at)
    expected=execute_saved(text,max_evaluations=4)
    synthetic(monkeypatch,fail_at=fail_at);request=Request(text,max_evaluations=4);receipt=request.run()
    assert receipt['execution']==expected and receipt['request']==request.to_dict()
    assert expected['status']==('incomplete' if fail_at else 'complete')
    if fail_at:assert expected['result']['rows'][1]['error']=='original failed frequency batch'


def test_model_budget_and_solver_exceptions_remain_original(monkeypatch):
    doc=random_document();request=Request(doc.dumps(),max_evaluations=2)
    # Preparation checks generic domains; existing model admission remains at run.
    synthetic(monkeypatch)
    with pytest.raises(ValueError,match='max_evaluations'):request.run()
    original=ArithmeticError('original unwrapped failure')
    def fail(*a,**k):raise original
    monkeypatch.setattr(candidate,'execute_saved',fail)
    with pytest.raises(ArithmeticError) as caught:Request(lumped().dumps()).run()
    assert caught.value is original


def test_receipt_refuses_different_execution_input(monkeypatch):
    def changed(*a,**k):return dict(schema='sipi.execution/1',input={},status='complete',result={},error=None)
    monkeypatch.setattr(candidate,'execute_saved',changed)
    with pytest.raises(RuntimeError,match='frozen request'):Request(lumped().dumps()).run()


@pytest.mark.parametrize('attempt',[1,2,3,4])
def test_goal_failure_receipt_keeps_original_stage_input_and_history(monkeypatch,attempt):
    from test_sampled_panel_pair_goal_document import document,Document
    raw=document().to_dict();raw['initial']=[1.35*.3e-3,.8*.2e-3];raw['max_evaluations']=4
    text=Document.from_dict(raw).dumps();synthetic(monkeypatch,fail_at=attempt)
    expected=execute_saved(text,max_evaluations=4)
    calls=synthetic(monkeypatch,fail_at=attempt);receipt=Request(text,max_evaluations=4).run()
    assert receipt['execution']==expected and expected['status']=='failed'
    error=receipt['execution']['error']
    assert error['attempts']==len(calls)==attempt and len(error['history'])==attempt-1
    assert error['input']==json.loads(calls[-1]) and error['cause_type']=='ArithmeticError'


def test_goal_generic_preparation_does_not_silently_clamp_model_budget(monkeypatch):
    from test_sampled_panel_pair_goal_document import document
    request=Request(document().dumps(),max_evaluations=63)
    def forbidden(*a,**k):pytest.fail('budget refusal ran fields')
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',forbidden)
    with pytest.raises(ValueError,match='batch budget'):request.run()
    assert json.loads(request.input_json)['max_evaluations']==64
