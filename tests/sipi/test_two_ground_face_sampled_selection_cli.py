# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Fixed-family CLI retains every candidate and unresolved original row."""
import json
import pytest
from sipi import cli
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument as Line
from test_two_ground_face_sampled_pair_selection import document
from test_two_ground_face_sampled_pair_study import synthetic
from test_execution_record import ARTIFACTS


@pytest.mark.parametrize('mode',['budget','diagnostics','bytes'])
def test_cli_refuses_before_any_candidate_fields(monkeypatch,tmp_path,capsys,mode):
    source=tmp_path/'input.json';source.write_text(document().dumps())
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('refused candidate solved'))
    extra={'budget':['--max-evaluations','7'],'diagnostics':['--diagnostic','characteristic'],
           'bytes':['--max-input-bytes','16']}[mode]
    assert cli.main(['run',str(source),*extra])==(1 if mode=='budget' else 2)
    out=capsys.readouterr();assert out.err and not out.out


@pytest.mark.parametrize('failed',[False,True])
def test_cli_reopens_all_candidates_and_original_unknowns(monkeypatch,tmp_path,capsys,failed):
    calls=synthetic(monkeypatch,fail_at=2 if failed else None);doc=document()
    source,target=tmp_path/'입력.json',tmp_path/'결과.json';source.write_text(doc.dumps(),encoding='utf-8')
    assert cli.main(['run',str(source),'--output',str(target),'--max-evaluations','8'])==(1 if failed else 0)
    receipt=json.loads(target.read_text());out=receipt['execution'];result=out['result']
    assert out['status']==('incomplete' if failed else 'complete')
    assert result['unresolved']==int(failed) and result['evaluations']==len(calls)==8
    assert len(result['candidates'])==2
    assert all(candidate['assessment']['count']==4 for candidate in result['candidates'])
    if failed:
        row=result['candidates'][0]['assessment']['rows'][1]
        assert row['classification']=='unresolved' and row['values_ohm'] is None
        assert row['cause_details']['type']=='TwoGroundFacePanelLineError'
    request=SavedExecutionRequest(doc.dumps(),max_evaluations=8)
    record=SavedExecutionRecord(request,receipt,run_id='face-grid-family:run',artifacts=ARTIFACTS)
    project=SavedProject(request,project_id='face-grid-family',design_id='a',title='Family',label='Source')
    project=project.attach_record('a',record,select=True)
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('restore solved'))
    assert SavedProject.loads(project.dumps()).current_record('a').receipt==receipt
    assert source.read_text()==doc.dumps() and not list(tmp_path.glob('.sipi-result-*'))
    assert not capsys.readouterr().out
