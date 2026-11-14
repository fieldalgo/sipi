# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit version-2 partial receipts preserve the original execution contract."""
import copy,json
from types import SimpleNamespace
import numpy as np
import pytest

from sipi import CrossSection
from sipi.line_model import TransmissionLineDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord as Record
from sipi.project import SavedProject
from test_execution_record import ARTIFACTS,rehash,record,lumped
from test_line_resolution_document import document as fixed_line
from test_adaptive_resolution_document import document as adaptive_line
from test_panel_resolution_document import document as fixed_panel
from test_adaptive_panel_resolution_document import document as adaptive_panel

V2='sipi.execution-record/2'


def receipt(monkeypatch,kind='panel',*,fail_at=2,budget=False):
    docs={'line':fixed_line,'adaptive-line':adaptive_line,'panel':fixed_panel,
          'adaptive-panel':lambda:adaptive_panel(levels=4 if budget else 2)}
    doc=docs[kind]();data=doc.to_dict()
    if budget:data['tolerances']={'C_f_per_m':{'relative':0.,'absolute':0.}}
    request=SavedExecutionRequest(json.dumps(data),max_evaluations=(8 if kind=='adaptive-panel' else 5) if budget else 128)
    calls=[]
    def analyze(self):
        calls.append(self.dumps())
        if len(calls)==fail_at:raise ValueError('explicit reproduction refusal')
        line=self.line if isinstance(self,PanelTransmissionLineDocument) else self
        frequency=np.array(line.to_dict()['frequency_hz'])
        names=tuple(t.name for t in line.cross_section.section.traces if not t.ground)
        base=np.eye(len(names))*1e-11*(len(calls) if budget else 1.)
        values=np.broadcast_to(base,(len(frequency),len(names),len(names))).copy()
        return SimpleNamespace(frequency=frequency,names=names,C=values,G=values*1e5,
            R=values*1e10,dielectric=SimpleNamespace(C0=base,L=np.eye(len(names))*1e-7),conductor=None)
    monkeypatch.setattr(TransmissionLineDocument,'analyze',analyze)
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',analyze)
    return request,request.run(),calls


@pytest.mark.parametrize('kind',['line','adaptive-line','panel','adaptive-panel'])
@pytest.mark.parametrize('attempt',[1,2,3])
def test_partial_fields_remain_v1_rejected_and_v2_exact(monkeypatch,kind,attempt,record_property):
    request,original,calls=receipt(monkeypatch,kind,fail_at=attempt)
    output=original['execution'];assert output['status']=='failed'
    assert len(calls)==attempt and len(output['result']['evaluations'])==attempt-1
    assert output['error']==output['result']['failure']
    with pytest.raises(ValueError,match='null result'):Record(request,original,run_id='partial:1',artifacts=ARTIFACTS)
    saved=Record(request,original,run_id='partial:1',artifacts=ARTIFACTS,schema=V2)
    text=saved.dumps()
    monkeypatch.setattr(SavedExecutionRequest,'run',lambda *a,**k:pytest.fail('restore ran'))
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('restore meshed'))
    restored=Record.loads(text)
    assert restored.dumps()==text and restored.receipt==original
    assert restored.prepare().to_dict()==request.to_dict()
    old=restored.to_dict();old['schema']='sipi.execution-record/1'
    with pytest.raises(ValueError,match='null result'):Record.from_dict(rehash(old))
    record_property('partial_receipt',json.dumps(original,sort_keys=True))


@pytest.mark.parametrize('kind',['adaptive-line','adaptive-panel'])
def test_budget_exhaustion_keeps_every_row_and_is_not_field_failure(monkeypatch,kind):
    request,original,calls=receipt(monkeypatch,kind,fail_at=None,budget=True)
    result=original['execution']['result']
    assert original['execution']['status']=='failed' and result['stop_reason']=='budget-exhausted'
    assert result['failure'] is None and not result['completed'] and not result['accepted']
    assert len(calls)==len(result['evaluations'])==(7 if kind=='adaptive-panel' else 3)
    saved=Record(request,original,run_id='budget:1',artifacts=ARTIFACTS,schema=V2)
    assert Record.loads(saved.dumps()).receipt==original
    with pytest.raises(ValueError,match='null result'):Record(request,original,run_id='budget:1',artifacts=ARTIFACTS)


def test_project_and_record_restore_never_replay_partial_fields(monkeypatch):
    request,original,_=receipt(monkeypatch)
    saved=Record(request,original,run_id='project:partial',artifacts=ARTIFACTS,schema=V2)
    project=SavedProject(request,project_id='project:1',design_id='a',title='Partial result',label='Original')
    project=project.attach_record('a',saved,select=True);text=project.dumps()
    monkeypatch.setattr(SavedExecutionRequest,'run',lambda *a,**k:pytest.fail('project restored fields'))
    restored=SavedProject.loads(text)
    assert restored.dumps()==text
    assert restored.to_dict()['designs'][0]['records'][0]==saved.to_dict()


@pytest.mark.parametrize('kind',['completed','completed-number','accepted','tolerance','missing','extra',
    'rows-type','row-type','comparisons-type','failure','kind','stage','message','error-input','error-extra',
    'expected-bool','expected-short','result-type'])
def test_rehashed_inconsistent_partial_fields_rejected(monkeypatch,kind):
    request,original,_=receipt(monkeypatch,fail_at=3)
    raw=Record(request,original,run_id='bad:1',artifacts=ARTIFACTS,schema=V2).to_dict()
    output=raw['receipt']['execution'];r=output['result'];error=output['error']
    if kind=='completed':r['completed']=True
    if kind=='completed-number':r['completed']=0
    if kind=='accepted':r['accepted']=True
    if kind=='tolerance':next(iter(r['tolerances'].values()))['relative']=.9
    if kind=='missing':r.pop('comparisons')
    if kind=='extra':r['extra']=1
    if kind=='rows-type':r['evaluations']={}
    if kind=='row-type':r['evaluations']=[None]
    if kind=='comparisons-type':r['comparisons']={}
    if kind=='failure':r['failure']['message']='changed'
    if kind=='kind':error['kind']=''
    if kind=='stage':error['stage']=False
    if kind=='message':error['message']=None
    if kind=='error-input':error['input']=[]
    if kind=='error-extra':error['extra']=1
    if kind=='expected-bool':r['expected_evaluations']=True
    if kind=='expected-short':r['expected_evaluations']=1
    if kind=='result-type':output['result']=[]
    with pytest.raises(ValueError):Record.from_dict(rehash(raw))


@pytest.mark.parametrize('kind',['reason','failure','selected','kind','stage','input','level-bool','outer-count','outer-bool','outer-true'])
@pytest.mark.parametrize('method',['adaptive-line','adaptive-panel'])
def test_rehashed_inconsistent_budget_receipts_rejected(monkeypatch,kind,method):
    request,original,_=receipt(monkeypatch,method,fail_at=None,budget=True)
    raw=Record(request,original,run_id='bad:budget',artifacts=ARTIFACTS,schema=V2).to_dict()
    r=raw['receipt']['execution']['result'];e=raw['receipt']['execution']['error']
    if kind=='reason':r['stop_reason']='accepted'
    if kind=='failure':r['failure']=copy.deepcopy(e)
    if kind=='selected':r['selected_evaluation_index']=0
    if kind=='kind':e['kind']='ValueError'
    if kind=='stage':e['stage']='field'
    if kind=='input':e['input']={}
    if kind=='level-bool':r['refinement_levels' if method=='adaptive-panel' else 'mesh_levels']=True
    if kind=='outer-count':r['expected_outer_evaluations']=0
    if kind=='outer-bool':r['outer_completed']=0
    if kind=='outer-true':r['outer_completed']=True
    with pytest.raises(ValueError):Record.from_dict(rehash(raw))


def test_nonresolution_failure_cannot_carry_an_arbitrary_result():
    raw=record(schema=V2).to_dict();raw['receipt']['execution'].update(status='failed',
        error=dict(stage='base',input={},kind='ValueError',message='not a resolution'),result={})
    with pytest.raises(ValueError,match='supported resolution'):Record.from_dict(rehash(raw))


@pytest.mark.parametrize('status',['complete','incomplete','failed'])
def test_original_envelope_states_and_digest_are_preserved_in_both_versions(status):
    request=lumped();original=request.run()
    if status=='incomplete':original['execution']['status']='incomplete'
    if status=='failed':original['execution'].update(status='failed',result=None,error=dict(type='Example',message='retained'))
    old=Record(request,original,run_id='state:1',artifacts=ARTIFACTS)
    new=Record(request,original,run_id='state:1',artifacts=ARTIFACTS,schema=V2)
    converted=old.to_dict();converted['schema']=V2
    assert new.to_dict()==rehash(converted)
    assert Record.loads(old.dumps()).dumps()==old.dumps()
    assert Record.loads(new.dumps()).receipt==original


def test_partial_record_byte_limit_digest_and_snapshot_detachment(monkeypatch):
    request,original,_=receipt(monkeypatch)
    saved=Record(request,original,run_id='limit:1',artifacts=ARTIFACTS,schema=V2)
    text=saved.dumps();size=len(text.encode('utf8'))
    assert Record.loads(text,max_record_bytes=size).dumps()==text
    with pytest.raises(ValueError,match='max_record_bytes'):Record.loads(text,max_record_bytes=size-1)
    mutated=saved.to_dict();mutated['receipt']['execution']['result']['evaluations'].clear()
    with pytest.raises(ValueError,match='digest'):Record.from_dict(mutated)
    original['execution']['result']['evaluations'].clear()
    assert saved.dumps()==text and len(saved.receipt['execution']['result']['evaluations'])==1


def test_partial_record_real_file_save_and_reopen_preserve_failure(monkeypatch,tmp_path):
    from sipi.project_io import read_project,save_project
    request,original,_=receipt(monkeypatch)
    saved=Record(request,original,run_id='file:partial',artifacts=ARTIFACTS,schema=V2)
    project=SavedProject(request,project_id='file:1',design_id='a',title='Partial',label='Original')
    project=project.attach_record('a',saved,select=True)
    monkeypatch.setattr(SavedExecutionRequest,'run',lambda *a,**k:pytest.fail('file operation ran fields'))
    target=tmp_path/'partial-result.json';written=save_project(target,project);loaded=read_project(target)
    assert loaded.file_sha256==written.file_sha256 and loaded.project.dumps()==project.dumps()
    assert loaded.project.to_dict()['designs'][0]['records'][0]['receipt']==original
    assert list(tmp_path.iterdir())==[target]


@pytest.mark.parametrize('method',['adaptive-line','adaptive-panel'])
def test_adaptive_field_failure_is_not_relabelled_as_budget_or_success(monkeypatch,method):
    request,original,_=receipt(monkeypatch,method)
    saved=Record(request,original,run_id='field:partial',artifacts=ARTIFACTS,schema=V2)
    for reason in ('budget-exhausted','accepted'):
        raw=saved.to_dict();raw['receipt']['execution']['result']['stop_reason']=reason
        with pytest.raises(ValueError,match='match its original error'):Record.from_dict(rehash(raw))


@pytest.mark.parametrize('error',[{'message':'missing type'}, {'type':'MissingMessage'}, {'type':'','message':'empty type'}])
def test_v2_retains_original_null_result_error_admission(error):
    raw=record(schema=V2).to_dict()
    raw['receipt']['execution'].update(status='failed',result=None,error=error)
    with pytest.raises(ValueError,match='typed error message'):Record.from_dict(rehash(raw))
