# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved IID file lifecycle and strict separation from whole-boundary sources."""
import json
import pytest
from sipi import cli,CrossSection
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject
from test_execution_record import ARTIFACTS


@pytest.mark.parametrize('paired',[False,True])
@pytest.mark.parametrize('failure',[None,2])
def test_cli_complete_and_unknown_rows_remain_in_saved_project(monkeypatch,tmp_path,capsys,paired,failure):
    if paired:
        from test_two_ground_face_pair_yield import document,synthetic
    else:
        from test_two_ground_face_line_yield import document,synthetic
    calls=synthetic(monkeypatch,fail_at=failure);doc=document()
    source,target=tmp_path/'입력.json',tmp_path/'결과.json';source.write_text(doc.dumps(),encoding='utf-8')
    assert cli.main(['run',str(source),'--output',str(target),'--max-evaluations','4'])==(0 if failure is None else 1)
    assert len(calls)==4 and not capsys.readouterr().out
    receipt=json.loads(target.read_text());result=receipt['execution']['result']
    assert receipt['execution']['status']==('complete' if failure is None else 'incomplete')
    assert result['count']==4 and result['unresolved']==(0 if failure is None else 1)
    assert len(result['rows'])==4
    if failure:assert result['rows'][1]['classification']=='unresolved' and result['rows'][1]['cause_details']
    request=SavedExecutionRequest(doc.dumps(),max_evaluations=4)
    record=SavedExecutionRecord(request,receipt,run_id='face-yield:test',artifacts=ARTIFACTS)
    project=SavedProject(request,project_id='face-yield',design_id='a',title='Acceptance',label='Input').attach_record('a',record,select=True)
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('restore solved'))
    assert SavedProject.loads(project.dumps()).current_record('a').receipt==receipt
    assert source.read_text()==doc.dumps() and not list(tmp_path.glob('.sipi-result-*'))


@pytest.mark.parametrize('paired',[False,True])
def test_whole_source_and_rows_are_not_converted(monkeypatch,paired):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('type refusal solved'))
    if paired:
        from sipi.two_ground_face_pair_yield import TwoGroundFaceForwardPairYieldDocument as Document,assess_two_ground_face_pair_yield as assess
        from test_two_ground_pair_yield import source,fixture,LIMITS
        original=source();study=fixture([(100.,40.)]*4);options=dict(acceptance=LIMITS)
    else:
        from sipi.two_ground_face_line_yield import TwoGroundFaceLineQuantityYieldDocument as Document,assess_two_ground_face_line_yield as assess
        from test_two_ground_line_yield import source,rows
        original=source();study=rows([50.]*4);options=dict(maximum=55.)
    with pytest.raises(ValueError):Document(original,**options)
    with pytest.raises(ValueError):assess(study,**options)
