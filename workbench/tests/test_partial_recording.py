"""Host-selected explicit partial records preserve existing receipt bytes."""
import json
import pytest
from test_recording import capture,prepared,recording
from test_partial_execution_record import receipt
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject


@pytest.mark.parametrize('kind',['line','adaptive-line','panel','adaptive-panel'])
def test_supported_partial_resolution_record(capture,monkeypatch,kind):
    request,original,_=receipt(monkeypatch,kind,fail_at=2)
    def once(self):
        capture[1].append('solve');assert self is request;return original
    monkeypatch.setattr(SavedExecutionRequest,'run',once)
    result=recording.run_recorded(request);saved=SavedExecutionRecord.loads(result['record_text'])
    assert capture[1]==['snapshot','solve','snapshot']
    assert saved.to_dict()['schema']=='sipi.execution-record/2' and saved.receipt==original
    assert saved.receipt['execution']['result']['evaluations']
    monkeypatch.setattr(SavedExecutionRequest,'run',lambda *a,**k:pytest.fail('restore solved'))
    project=SavedProject(request,project_id='partial-host',design_id='a',title='Resolution',label='Input').attach_record('a',saved,select=True)
    assert SavedProject.loads(project.dumps()).current_record('a').receipt==original
    assert result['runtime_manifest_text']==capture[0]['manifest_text']


@pytest.mark.parametrize('kind',['adaptive-line','adaptive-panel'])
def test_adaptive_budget_retains_partial_result(capture,monkeypatch,kind):
    request,original,_=receipt(monkeypatch,kind,fail_at=None,budget=True)
    monkeypatch.setattr(SavedExecutionRequest,'run',lambda self:original)
    saved=SavedExecutionRecord.loads(recording.run_recorded(request)['record_text'])
    assert saved.to_dict()['schema']=='sipi.execution-record/2' and saved.receipt==original
    assert saved.receipt['execution']['result']['stop_reason']=='budget-exhausted'


def test_two_ground_typed_partial_record(capture,monkeypatch):
    from test_two_ground_resolution_document import document
    from test_two_ground_resolution import synthetic
    synthetic(monkeypatch,fail_at=3)
    request=SavedExecutionRequest(document().dumps(),max_evaluations=6);original=request.run()
    monkeypatch.setattr(SavedExecutionRequest,'run',lambda self:original)
    saved=SavedExecutionRecord.loads(recording.run_recorded(request)['record_text'])
    assert saved.to_dict()['schema']=='sipi.execution-record/2' and saved.receipt==original
    assert original['execution']['error']['details']['cause_type']=='ArithmeticError'
    assert len(original['execution']['result']['evaluations'])==2


@pytest.mark.parametrize('status',['complete','incomplete','failed'])
def test_existing_receipt_shapes_keep_version_one(capture,monkeypatch,status):
    request=prepared();original=request.run();out=original['execution'];out['status']=status
    if status=='failed':out.update(result=None,error=dict(type='ArithmeticError',message='structural fixture'))
    monkeypatch.setattr(SavedExecutionRequest,'run',lambda self:original)
    saved=SavedExecutionRecord.loads(recording.run_recorded(request)['record_text'])
    assert saved.to_dict()['schema']=='sipi.execution-record/1' and saved.receipt==original


def test_unsupported_nonnull_failure_still_rejects(capture,monkeypatch):
    request=prepared();original=request.run();out=original['execution']
    out.update(status='failed',error=dict(type='ArithmeticError',message='unsupported fixture'))
    monkeypatch.setattr(SavedExecutionRequest,'run',lambda self:original)
    with pytest.raises(ValueError,match='supported resolution input'):recording.run_recorded(request)
