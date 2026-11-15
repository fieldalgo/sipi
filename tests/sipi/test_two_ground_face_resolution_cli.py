# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved face resolution CLI keeps disagreement and partial failure distinct."""
import json
import pytest
from sipi import cli
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject
from sipi.two_ground_face_resolution_document import TwoGroundFaceResolutionDocument as Document
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument as Line
from test_two_ground_face_resolution_document import document
from test_two_ground_face_resolution import synthetic
from test_execution_record import ARTIFACTS


@pytest.mark.parametrize('mode',['budget','diagnostics','bytes'])
def test_cli_refusals_precede_fields(monkeypatch,tmp_path,capsys,mode):
    source=tmp_path/'input.json';source.write_text(document().dumps())
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('refused request solved'))
    extra={'budget':['--max-evaluations','5'],'diagnostics':['--diagnostic','characteristic'],
           'bytes':['--max-input-bytes','16']}[mode]
    assert cli.main(['run',str(source),*extra])==(1 if mode=='budget' else 2)
    out=capsys.readouterr();assert out.err and not out.out


@pytest.mark.parametrize('mode',['accepted','disagree','failed'])
def test_cli_record_and_project_preserve_partial_or_complete(monkeypatch,tmp_path,capsys,mode):
    calls=synthetic(monkeypatch,fail_at=4 if mode=='failed' else None,disagree=mode=='disagree')
    doc=document();source,target=tmp_path/'입력.json',tmp_path/'결과.json'
    source.write_text(doc.dumps(),encoding='utf-8')
    assert cli.main(['run',str(source),'--output',str(target),'--max-evaluations','6'])==(1 if mode=='failed' else 0)
    receipt=json.loads(target.read_text());out=receipt['execution']
    assert out['status']==('failed' if mode=='failed' else 'complete')
    assert out['result']['accepted']==(mode=='accepted')
    assert len(calls)==(4 if mode=='failed' else 6)
    request=SavedExecutionRequest(doc.dumps(),max_evaluations=6)
    record=SavedExecutionRecord(request,receipt,run_id='face-resolution:run',artifacts=ARTIFACTS,schema='sipi.execution-record/2')
    project=SavedProject(request,project_id='face-resolution',design_id='a',title='Resolution',label='Source')
    project=project.attach_record('a',record,select=True)
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('restore solved'))
    assert SavedProject.loads(project.dumps()).current_record('a').receipt==receipt
    assert source.read_text()==doc.dumps() and not list(tmp_path.glob('.sipi-result-*'))
    assert not capsys.readouterr().out
