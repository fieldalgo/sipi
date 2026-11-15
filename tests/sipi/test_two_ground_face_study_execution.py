# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Face-study CLI and project receipts retain complete and failed rows."""
import json
import pytest
from sipi import cli
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject
from sipi.two_ground_face_pair_study import TwoGroundFaceForwardPairStudyDocument as Document
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument as Line
from test_two_ground_face_pair_study import document
from test_two_ground_face_pair_goal import synthetic
from test_execution_record import ARTIFACTS


@pytest.mark.parametrize('failure', [None, 2])
def test_cli_record_project_and_each_frozen_face(monkeypatch, tmp_path, capsys, failure):
    synthetic(monkeypatch, fail_at=failure)
    doc = document()
    source, output = tmp_path/'input.json', tmp_path/'output.json'
    source.write_text(doc.dumps())
    assert cli.main(['run', str(source), '--output', str(output), '--max-evaluations', '4']) == (0 if failure is None else 1)
    receipt = json.loads(output.read_text())
    result = receipt['execution']['result']
    assert receipt['execution']['status'] == ('complete' if failure is None else 'incomplete')
    assert result['failed'] == (0 if failure is None else 1)
    assert (result['summary'] is not None) == (failure is None)
    assert result['scope'] == 'stated-two-ground-face-paired-samples-descriptive-not-production-yield'
    for row in result['rows']:
        assert row['input']['schema'] == 'sipi.two-ground-face-panel-transmission-line/1'
        assert row['input']['conductors'] == doc.to_dict()['conductors']
        assert row['input']['reference'] == doc.to_dict()['reference']
    request = SavedExecutionRequest(doc.dumps(), max_evaluations=4)
    record = SavedExecutionRecord(request, receipt, run_id='study', artifacts=ARTIFACTS)
    project = SavedProject(request, project_id='faces', design_id='a', title='Study', label='Input')
    project = project.attach_record('a', record, select=True)
    monkeypatch.setattr(Line, 'analyze', lambda *a: pytest.fail('restore solved'))
    assert SavedProject.loads(project.dumps()).current_record('a').receipt == receipt
    assert source.read_text() == doc.dumps() and not list(tmp_path.glob('.sipi-result-*'))
    assert not capsys.readouterr().out


def test_cli_budget_is_checked_before_rows(monkeypatch, tmp_path, capsys):
    doc = document()
    source, output = tmp_path/'input.json', tmp_path/'output.json'
    source.write_text(doc.dumps())
    monkeypatch.setattr(Line, 'analyze', lambda *a: pytest.fail('budget reached field'))
    assert cli.main(['run', str(source), '--output', str(output), '--max-evaluations', '3']) == 1
    assert not output.exists() and capsys.readouterr().err


def test_whole_study_schema_cannot_hide_face_laws():
    from sipi.two_ground_pair_study import TwoGroundForwardPairStudyDocument
    with pytest.raises(ValueError):
        TwoGroundForwardPairStudyDocument.from_dict(document().to_dict())
