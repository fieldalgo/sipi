# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Field-free saved finite comparisons and partial evidence transport."""
import json
import pytest
from sipi.two_ground_harmonic_guard_corner_face_resolution_document import TwoGroundHarmonicGuardCornerFaceResolutionDocument as Document
from sipi.two_ground_harmonic_guard_corner_face_panel_line import TwoGroundHarmonicGuardCornerFacePanelTransmissionLineDocument as Line
from sipi.execution import normalize_saved,execute_saved
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject
from test_two_ground_harmonic_guard_corner_face_resolution import inputs,synthetic
from test_execution_record import ARTIFACTS
from resolution_studies import ENABLED as STUDIES,recorded_case


def document():
    line,kw=inputs();return Document(line,**kw)


def test_fieldfree_roundtrip_registry_project_and_budget(monkeypatch):
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('preparation solved'))
    doc=document();text=doc.dumps();assert Document.loads(text).dumps()==normalize_saved(text)==text
    raw=doc.to_dict();raw['refined_panel']['ground_modes']=4096;assert doc.dumps()==text
    request=SavedExecutionRequest(text,max_evaluations=6)
    project=SavedProject(request,project_id='two-ground-harmonic-guard-corner-face-resolution',design_id='a',title='Resolution',label='Source')
    assert SavedProject.loads(project.dumps()).prepare('a').request_id==request.request_id
    with pytest.raises(ValueError,match='before any field solve'):doc.analyze(max_evaluations=5)
    with pytest.raises(ValueError,match='before any field solve'):execute_saved(text,max_evaluations=5)
    with pytest.raises(ValueError,match='diagnostics'):execute_saved(text,diagnostics=['characteristic'])


@pytest.mark.parametrize('case',['schema','missing','extra','line','outer','tolerance-unit','missing-absolute',
    'extra-tolerance','negative','budget','panel','duplicate','nan'])
def test_invalid_saved_input_rejects_before_fields(monkeypatch,case):
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('bad saved input solved'))
    raw=document().to_dict();text=None
    if case=='schema':raw['schema']+='/future'
    if case=='missing':raw.pop('max_solves')
    if case=='extra':raw['extra']=1
    if case=='line':raw['line']['schema']='sipi.transmission-line/1'
    if case=='outer':raw['outer_lines']={}
    if case=='tolerance-unit':raw['tolerances']['R']=raw['tolerances'].pop('R_ohm_per_m')
    if case=='missing-absolute':raw['tolerances']['R_ohm_per_m'].pop('absolute')
    if case=='extra-tolerance':raw['tolerances']['R_ohm_per_m']['floor']=1.
    if case=='negative':raw['tolerances']['R_ohm_per_m']['absolute']=-1.
    if case=='budget':raw['max_solves']=5
    if case=='panel':raw['refined_panel']['ground_modes']=64
    if case=='duplicate':text=json.dumps(raw).replace('"max_solves": 6','"max_solves": 6,"max_solves": 6')
    if case=='nan':text=json.dumps(raw).replace('"max_solves": 6','"max_solves": NaN')
    with pytest.raises((ValueError,TypeError)):Document.loads(text or json.dumps(raw))


@pytest.mark.parametrize('fail_at',[None,1,2,3,4,5,6])
def test_complete_and_failed_execution_record_restore(monkeypatch,fail_at):
    calls=synthetic(monkeypatch,fail_at=fail_at)
    request=SavedExecutionRequest(document().dumps(),max_evaluations=6);receipt=request.run();out=receipt['execution']
    assert out['status']==('complete' if fail_at is None else 'failed')
    assert len(calls)==(6 if fail_at is None else fail_at)
    result=out['result'];assert result['scope']=='two-ground-harmonic-guard-corner-face-finite-resolution-not-absolute-accuracy'
    if fail_at is None:assert result['accepted'] and result['completed']
    else:
        assert not result['accepted'] and not result['completed']
        assert out['error']==result['failure'] and out['error']['details']['cause_type']=='ArithmeticError'
    record=SavedExecutionRecord(request,receipt,run_id='two-ground-harmonic-guard-corner-face-resolution:run',artifacts=ARTIFACTS,schema='sipi.execution-record/2')
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('restore solved'))
    assert SavedExecutionRecord.loads(record.dumps()).receipt==receipt
    project=SavedProject(request,project_id='corner-resolution',design_id='a',title='Resolution',label='Input').attach_record('a',record,select=True)
    assert SavedProject.loads(project.dumps()).current_record('a').receipt==receipt


def test_complete_disagreement_is_not_hidden_as_success(monkeypatch):
    synthetic(monkeypatch,disagree=True);out=execute_saved(document().dumps(),max_evaluations=6)
    assert out['status']=='complete' and out['result']['completed'] and not out['result']['accepted']
    assert any(not row['accepted'] for row in out['result']['comparisons'])


def test_interrupt_propagates(monkeypatch):
    calls=synthetic(monkeypatch,fail_at=2,interrupt=True)
    with pytest.raises(KeyboardInterrupt):execute_saved(document().dumps(),max_evaluations=6)
    assert len(calls)==2


def test_saved_document_runs_the_recorded_study(monkeypatch):
    """The saved document's base line is the recorded study's base input, which
    test_two_ground_harmonic_guard_corner_face_resolution.py reproduces in the regular suite;
    the other five lines are the study's (inputs()). The actual six-line receipt below runs
    only with the finite-resolution studies (tests/_support/resolution_studies.py)."""
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('field-free check solved'))
    saved=json.loads(document().dumps());base,kw=inputs()
    assert saved['line']==recorded_case('test_two_ground_harmonic_guard_corner_face_resolution',0)['base_input']==json.loads(base.dumps())
    assert [json.loads(Line.from_dict(row).dumps()) for row in saved['outer_lines']]==[json.loads(d.dumps()) for d in kw['outer_documents']]
    assert saved['refined_panel']==kw['refined_panel_options'] and saved['max_solves']==6


if STUDIES:  # dispatch-only: the same six lines as the study, through the saved-document path
    @pytest.mark.slow
    def test_actual_saved_finite_resolution_receipt(record_property):
        receipt=SavedExecutionRequest(document().dumps(),max_evaluations=6).run()
        record_property('two_ground_face_saved_finite_resolution',json.dumps(receipt,sort_keys=True))
        out=receipt['execution'];assert out['status']=='complete'
        assert out['result']['completed'] and out['result']['accepted']
        assert len(out['result']['evaluations'])==len(out['result']['comparisons'])==6


@pytest.mark.parametrize('case',['v1','scope','count','stage','input','prefix','evidence','typed-input','typed-message','typed-kind','untyped-details'])
def test_partial_record_rejects_changed_failure_contract(monkeypatch,case):
    synthetic(monkeypatch,fail_at=4)
    request=SavedExecutionRequest(document().dumps(),max_evaluations=6);receipt=request.run()
    result=receipt['execution']['result'];error=receipt['execution']['error']
    if case=='scope':result['scope']='accuracy-certified'
    if case=='count':result['expected_evaluations']=5
    if case=='stage':error['stage']='outer:8'
    if case=='input':error['input']['length_m']=.04
    if case=='prefix':result['evaluations'][0]['input']['length_m']=.04
    if case=='evidence':result['evaluations'][0].pop('current_solver')
    if case=='typed-input':error['details']['input']['length_m']=.04
    if case=='typed-message':error['details']['message']='changed'
    if case=='typed-kind':error['details']['cause_type']=''
    if case=='untyped-details':error['kind']='ValueError'
    result['failure']=json.loads(json.dumps(error))
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('record validation solved'))
    with pytest.raises(ValueError):SavedExecutionRecord(request,receipt,run_id='two-ground-harmonic-guard-corner-face-resolution:bad',artifacts=ARTIFACTS,
        schema='sipi.execution-record/1' if case=='v1' else 'sipi.execution-record/2')


def test_comparison_failure_record_retains_completed_prefix(monkeypatch):
    synthetic(monkeypatch,mismatch=True);request=SavedExecutionRequest(document().dumps(),max_evaluations=6)
    receipt=request.run();record=SavedExecutionRecord(request,receipt,run_id='two-ground-harmonic-guard-corner-face-resolution:comparison',artifacts=ARTIFACTS,schema='sipi.execution-record/2')
    assert record.receipt==receipt and len(receipt['execution']['result']['evaluations'])==4


@pytest.mark.parametrize('outcome',['complete','disagree','failed'])
def test_cli_receipt_keeps_finite_acceptance_and_partial_failure(monkeypatch,tmp_path,outcome):
    from sipi import cli
    synthetic(monkeypatch,fail_at=3 if outcome=='failed' else None,disagree=outcome=='disagree')
    doc=document();source=tmp_path/'input.json';target=tmp_path/'receipt.json'
    source.write_text(doc.dumps(),encoding='utf-8')
    assert cli.main(['run',str(source),'--output',str(target),'--max-evaluations','6'])==(1 if outcome=='failed' else 0)
    receipt=json.loads(target.read_text(encoding='utf-8'));output=receipt['execution']
    assert output['result']['scope']=='two-ground-harmonic-guard-corner-face-finite-resolution-not-absolute-accuracy'
    assert output['result']['accepted']==(outcome=='complete')
    assert output['result']['completed']==(outcome!='failed')
    request=SavedExecutionRequest(doc.dumps(),max_evaluations=6)
    record=SavedExecutionRecord(request,receipt,run_id='corner-cli:'+outcome,artifacts=ARTIFACTS,schema='sipi.execution-record/2')
    assert SavedExecutionRecord.loads(record.dumps()).receipt==receipt
