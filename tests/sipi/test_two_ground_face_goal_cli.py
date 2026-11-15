# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""CLI file lifecycle, early refusal and restored face-goal records."""
from pathlib import Path
import json
import pytest
from sipi import cli
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject
from sipi.two_ground_face_pair_goal_document import TwoGroundFaceForwardPairDesignDocument as Document
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument as Line
from test_two_ground_face_pair_goal_document import document
from test_two_ground_face_pair_goal import synthetic
from test_execution_record import ARTIFACTS


@pytest.mark.parametrize('mode', ['budget', 'diagnostics', 'bytes'])
def test_cli_caller_limits_precede_fields(monkeypatch, tmp_path, capsys, mode):
    source = tmp_path/'input.json'
    source.write_text(document().dumps())
    monkeypatch.setattr(Document, 'solve', lambda *a: pytest.fail('rejected goal solved'))
    options = {'budget': ['--max-evaluations', '63'],
               'diagnostics': ['--diagnostic', 'characteristic'],
               'bytes': ['--max-input-bytes', '16']}[mode]
    assert cli.main(['run', str(source), *options]) == (1 if mode == 'budget' else 2)
    captured = capsys.readouterr()
    assert captured.err and not captured.out


def test_failed_cli_retains_original_face_cause_and_input(monkeypatch, tmp_path, capsys):
    synthetic(monkeypatch, fail_at=1)
    doc = document()
    source, target = tmp_path/'input.json', tmp_path/'failed.json'
    source.write_text(doc.dumps())
    assert cli.main(['run', str(source), '--output', str(target)]) == 1
    receipt = json.loads(target.read_text())
    error = receipt['execution']['error']
    assert error['cause_type'] == 'TwoGroundFacePanelLineError'
    assert error['cause_details']['cause_type'] == 'ArithmeticError'
    assert error['input']['schema'] == 'sipi.two-ground-face-panel-transmission-line/1'
    assert receipt['execution']['status'] == 'failed'
    assert source.read_text() == doc.dumps() and not list(tmp_path.glob('.sipi-result-*'))
    assert not capsys.readouterr().out


def test_actual_cli_selected_goal_and_project_reopen(tmp_path, capsys, monkeypatch, record_property):
    selected = json.loads((Path(__file__).parent/'data/two_ground/face_goal_selected.json').read_text())
    raw = document(True).to_dict()
    raw.update(initial=selected['parameters'], max_evaluations=4)
    doc = Document.from_dict(raw)
    source, target = tmp_path/'입력.json', tmp_path/'결과.json'
    source.write_text(doc.dumps(), encoding='utf-8')
    assert cli.main(['run', str(source), '--output', str(target), '--max-evaluations', '4']) == 0
    captured = capsys.readouterr()
    assert not captured.out and not captured.err
    receipt = json.loads(target.read_text())
    assert receipt['execution']['status'] == 'complete'
    assert receipt['execution']['result']['evaluations'] == 4
    assert receipt['execution']['input'] == doc.to_dict()
    request = SavedExecutionRequest(doc.dumps(), max_evaluations=4)
    record = SavedExecutionRecord(request, receipt, run_id='face-goal:complete', artifacts=ARTIFACTS)
    project = SavedProject(request, project_id='face-goal', design_id='a', title='Goal', label='Input')
    project = project.attach_record('a', record, select=True)
    monkeypatch.setattr(Line, 'analyze', lambda *a: pytest.fail('restore solved'))
    restored = SavedProject.loads(project.dumps())
    assert restored.current_record('a').receipt == receipt
    assert restored.prepare('a').request_id == request.request_id
    assert source.read_text() == doc.dumps() and not list(tmp_path.glob('.sipi-result-*'))
    record_property('face_goal_cli', json.dumps(receipt, sort_keys=True))
