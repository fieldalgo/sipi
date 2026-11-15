# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
import json
import subprocess
import sys
import numpy as np
import pytest
from sipi import CrossSection
from sipi.execution import execute_saved,normalize_saved,saved_schemas
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject
from sipi.two_ground_panel_line import TwoGroundPanelLineError
import sipi.two_ground_conductor as current
import sipi.two_ground_panel_line as module
from test_two_ground_panel_line import document,Document
from test_execution import network_equal
from test_execution_record import ARTIFACTS
from test_project import project


@pytest.fixture(scope='module')
def observations():
    return [(document(case),document(case).analyze()) for case in ('scalar-offset','pair-asymmetric')]


def test_field_free_request_and_canonical_registration(monkeypatch):
    def forbidden(*a,**k):pytest.fail('preparation reached fields')
    monkeypatch.setattr(current,'_solver',forbidden);monkeypatch.setattr(CrossSection,'mesh',forbidden)
    text=document().dumps();assert normalize_saved(text)==text
    assert 'sipi.two-ground-panel-transmission-line/1' in saved_schemas()
    a=SavedExecutionRequest(text,diagnostics=['characteristic','modes'])
    assert a.input_json==text and a.controls['diagnostics']==['characteristic','modes']
    assert SavedProject(a,project_id='two-ground',design_id='a',title='Two-ground',label='Nominal').prepare('a').request_id==a.request_id


@pytest.mark.parametrize('route',['execute','request','cli'])
def test_frequency_budget_refuses_before_current_or_mesh(monkeypatch,tmp_path,capsys,route):
    from sipi import cli
    raw=document().to_dict();raw['frequency_hz'].append(8e9);doc=Document.from_dict(raw)
    def forbidden(*a,**k):pytest.fail('budget reached fields')
    monkeypatch.setattr(Document,'analyze',forbidden);monkeypatch.setattr(CrossSection,'mesh',forbidden)
    if route=='cli':
        p=tmp_path/'input.json';p.write_text(doc.dumps())
        assert cli.main(['run',str(p),'--max-evaluations','2'])==1
        assert 'before any field solve' in capsys.readouterr().err
    else:
        with pytest.raises(ValueError,match='before any field solve'):
            if route=='execute':execute_saved(doc.dumps(),max_evaluations=2)
            else:SavedExecutionRequest(doc.dumps(),max_evaluations=2).run()


def test_actual_host_matches_direct_line_and_separate_surface_records(observations,record_property):
    records=[]
    for doc,result in observations:
        output=execute_saved(doc.dumps(),diagnostics=['characteristic','modes'])
        assert output['status']=='complete' and output['error'] is None and output['input']==doc.to_dict()
        data=output['result'];assert data['names']==list(result.names)
        for key,expected in [('R_ohm_per_m',result.R),('L_h_per_m',result.L),('G_s_per_m',result.G),('C_f_per_m',result.C)]:
            np.testing.assert_array_equal(data[key],expected)
        network_equal(data['network'],result.network)
        assert data['current_solver']==result.current_record()
        assert data['dielectric_mesh']==result.mesh_record()
        boundaries=data['conductor_boundaries'];assert boundaries['labels']==list(result.conductor.boundary_labels)
        np.testing.assert_array_equal(boundaries['surface_current_factors_per_m'],result.current_factors.boundary_parts)
        np.testing.assert_array_equal(boundaries['current_integrals'],result.current_factors.boundary_integrals)
        np.testing.assert_array_equal(boundaries['resistance_ohm_per_m'],result.conductor.resistance_parts)
        assert data['diagnostics']['characteristic']['status']=='complete'
        assert data['diagnostics']['modes']['status']=='complete'
        records.append(output)
    record_property('two_ground_execution',json.dumps(records,sort_keys=True))


@pytest.mark.parametrize('stage',['current','mesh','dielectric','network'])
def test_typed_failure_request_record_project_preserves_exact_context(monkeypatch,observations,stage):
    doc,result=observations[0]
    error=TwoGroundPanelLineError(ArithmeticError('controlled failure'),stage=stage,input_json=doc.dumps(),
        factors=None if stage=='current' else result.current_factors,settings=doc.current_options,
        mesh_observation=None if stage in ('current','mesh') else result.mesh_record())
    def failure(self):raise error
    monkeypatch.setattr(Document,'analyze',failure)
    request=SavedExecutionRequest(doc.dumps());receipt=request.run()
    assert receipt['execution']['status']=='failed' and receipt['execution']['result'] is None
    assert receipt['execution']['error']==error.to_dict()
    record=SavedExecutionRecord(request,receipt,run_id='two-ground:'+stage,artifacts=ARTIFACTS)
    reopened=SavedExecutionRecord.loads(record.dumps())
    assert reopened.receipt==receipt
    assert reopened.to_dict()['artifacts']['verification']=='host-declared'
    saved=project(request).attach_record('a',record,select=True)
    assert SavedProject.loads(saved.dumps()).current_record('a').dumps()==record.dumps()
    damaged=record.to_dict();damaged['receipt']['execution']['error']['stage']='changed'
    with pytest.raises(ValueError,match='digest'):SavedExecutionRecord.from_dict(damaged)


def test_completed_record_reopens_without_calculation(monkeypatch,observations):
    doc,result=observations[0]
    monkeypatch.setattr(Document,'analyze',lambda self:result)
    request=SavedExecutionRequest(doc.dumps(),diagnostics=['characteristic']);receipt=request.run()
    record=SavedExecutionRecord(request,receipt,run_id='complete:two-ground',artifacts=ARTIFACTS)
    def forbidden(*a,**k):pytest.fail('reopen calculated')
    monkeypatch.setattr(Document,'analyze',forbidden);monkeypatch.setattr(CrossSection,'mesh',forbidden)
    saved=project(request).attach_record('a',record,select=True)
    restored=SavedProject.loads(saved.dumps());assert restored.current_record('a').receipt==receipt
    assert restored.prepare('a').request_id==request.request_id


def test_absent_shared_capability_is_failed_receipt(monkeypatch):
    def absent(name):raise ImportError('missing explicit candidate capability')
    monkeypatch.setattr(current,'import_module',absent)
    request=SavedExecutionRequest(document().dumps());receipt=request.run()
    out=receipt['execution'];assert out['status']=='failed' and out['result'] is None
    assert out['error']['stage']=='current' and out['error']['cause_type']=='RuntimeError'
    assert out['error']['current_solver'] is None and out['error']['dielectric_mesh'] is None
    assert SavedExecutionRecord(request,receipt,run_id='missing:capability',artifacts=ARTIFACTS).receipt==receipt


def test_cli_subprocess_uses_saved_schema_and_preserves_input(tmp_path):
    doc=document();source=tmp_path/'입력.json';target=tmp_path/'결과.json';source.write_text(doc.dumps(),encoding='utf-8')
    completed=subprocess.run([sys.executable,'-m','sipi','run',str(source),'--output',str(target)],capture_output=True,text=True)
    assert completed.returncode==0,completed.stderr
    assert not completed.stdout and not completed.stderr
    receipt=json.loads(target.read_text());assert receipt['execution']['status']=='complete'
    assert receipt['execution']['input']==doc.to_dict() and source.read_text()==doc.dumps()
    assert receipt['execution']['result']['current_solver']['kind']=='two-ground-rectangle-panels'
    assert not list(tmp_path.glob('.sipi-result-*'))
