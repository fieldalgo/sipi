# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Finite-grid sample receipts retain unknown rows and source files."""
import json
import pytest
from sipi import cli
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument as Line
from test_two_ground_face_sampled_pair_study import document,synthetic,F
from test_execution_record import ARTIFACTS


@pytest.mark.parametrize('mode',['budget','diagnostics','bytes'])
def test_cli_limits_precede_fields(monkeypatch,tmp_path,capsys,mode):
    source=tmp_path/'input.json';source.write_text(document().dumps())
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('refused sample solved'))
    extra={'budget':['--max-evaluations','3'],'diagnostics':['--diagnostic','characteristic'],
           'bytes':['--max-input-bytes','16']}[mode]
    assert cli.main(['run',str(source),*extra])==(1 if mode=='budget' else 2)
    out=capsys.readouterr();assert out.err and not out.out


@pytest.mark.parametrize('failed',[False,True])
def test_cli_restores_whole_frequency_rows_without_resampling(monkeypatch,tmp_path,capsys,failed):
    calls=synthetic(monkeypatch,fail_at=2 if failed else None);doc=document()
    source,target=tmp_path/'입력.json',tmp_path/'결과.json';source.write_text(doc.dumps(),encoding='utf-8')
    assert cli.main(['run',str(source),'--output',str(target),'--max-evaluations','4'])==(1 if failed else 0)
    receipt=json.loads(target.read_text());out=receipt['execution'];result=out['result']
    assert out['status']==('incomplete' if failed else 'complete')
    assert result['failed']==int(failed) and len(calls)==len(result['rows'])==4
    assert result['frequencies_hz']==F
    if failed:
        assert result['rows'][1]['values_ohm'] is None and result['summary'] is None
        assert result['rows'][1]['cause_details']['type']=='TwoGroundFacePanelLineError'
    request=SavedExecutionRequest(doc.dumps(),max_evaluations=4)
    record=SavedExecutionRecord(request,receipt,run_id='face-grid-study:run',artifacts=ARTIFACTS)
    project=SavedProject(request,project_id='face-grid-study',design_id='a',title='Samples',label='Source')
    project=project.attach_record('a',record,select=True)
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('restore solved'))
    assert SavedProject.loads(project.dumps()).current_record('a').receipt==receipt
    assert source.read_text()==doc.dumps() and not list(tmp_path.glob('.sipi-result-*'))
    assert not capsys.readouterr().out
