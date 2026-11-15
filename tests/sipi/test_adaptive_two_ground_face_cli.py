# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""CLI retains adaptive partial histories in explicit version-2 records."""
import json
import pytest
from sipi import cli
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument as Line
from test_adaptive_two_ground_face_resolution_document import document
from test_adaptive_two_ground_face_resolution import fake
from test_execution_record import ARTIFACTS


@pytest.mark.parametrize('mode',['budget','diagnostics','bytes'])
def test_cli_limits_precede_fields(monkeypatch,tmp_path,capsys,mode):
    source=tmp_path/'input.json';source.write_text(document().dumps())
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('refused plan solved'))
    extra={'budget':['--max-evaluations','7'],'diagnostics':['--diagnostic','characteristic'],
           'bytes':['--max-input-bytes','16']}[mode]
    assert cli.main(['run',str(source),*extra])==(1 if mode=='budget' else 2)
    out=capsys.readouterr();assert out.err and not out.out


@pytest.mark.parametrize('mode',['accepted','outer','field','budget'])
def test_cli_partial_evidence_reopens_without_fields(monkeypatch,tmp_path,capsys,mode):
    calls=fake(monkeypatch,values={(1,1):2.,(2,2):3.} if mode=='budget' else None,
        fail=5 if mode=='field' else None,shape_error=True,outer=2. if mode=='outer' else 1.)
    doc=document(levels=4 if mode=='budget' else 2)
    source,target=tmp_path/'입력.json',tmp_path/'결과.json';source.write_text(doc.dumps(),encoding='utf-8')
    assert cli.main(['run',str(source),'--output',str(target),'--max-evaluations','8'])==(1 if mode in ('field','budget') else 0)
    receipt=json.loads(target.read_text());out=receipt['execution'];result=out['result']
    assert out['status']==('failed' if mode in ('field','budget') else 'complete')
    assert len(calls)==({'field':5,'budget':7}.get(mode,8))
    assert result['accepted']==(mode=='accepted')
    if mode=='field':assert out['error']['details']['type']=='TwoGroundFacePanelLineError'
    request=SavedExecutionRequest(doc.dumps(),max_evaluations=8)
    record=SavedExecutionRecord(request,receipt,run_id='adaptive-face:cli',artifacts=ARTIFACTS,schema='sipi.execution-record/2')
    project=SavedProject(request,project_id='adaptive-face-cli',design_id='a',title='Adaptive',label='Plan')
    project=project.attach_record('a',record,select=True)
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('restore solved'))
    assert SavedProject.loads(project.dumps()).current_record('a').receipt==receipt
    assert source.read_text()==doc.dumps() and not list(tmp_path.glob('.sipi-result-*'))
    assert not capsys.readouterr().out
