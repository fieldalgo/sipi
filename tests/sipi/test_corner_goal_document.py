# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved corner goals, actual parent parity and complete failure receipts."""
from dataclasses import FrozenInstanceError
import json
import pytest
from meshine import MeshSizeLimitError
from sipi import (CrossSection, ImpedanceDesignDocument,
                  CornerImpedanceDesignDocument as Document, CornerCrossSectionDocument)
from sipi.dielectric import ConstantDielectric
from sipi.execution import execute_saved, normalize_saved
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject
from test_corner_goal import MESH, BOUNDS, fake_analysis

ARTIFACTS=[dict(component='sipi',version='example-only',kind='wheel',sha256='1'*64)]


def document(kind='geometry'):
    params=dict(width=.0006,plane_spacing=.002,eps_r=4.,thickness=.0004,box_width=.008)
    options=(dict(variable='width',bounds=BOUNDS) if kind=='geometry' else
        dict(variable='dk',bounds=[3.8,4.2],frequency=1e9,
             materials={'dielectric':ConstantDielectric(4.)},
             material_variables={'dk':dict(region='dielectric',path=['eps_r'])}))
    design=ImpedanceDesignDocument('stripline',params,target=44.3,tolerance=.1,
        search_tolerance=.025,max_evaluations=12,mesh=MESH,**options)
    return Document(design,2.5e-6)


@pytest.mark.parametrize('bad',[None,True,0.,-1.,float('nan'),float('inf'),'1e-6',2e-5])
def test_bad_corner_precedes_fields(bad,monkeypatch):
    raw=document().to_dict();raw['corner_size']=bad
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('unexpected mesh'))
    with pytest.raises(ValueError):Document.from_dict(raw)


@pytest.mark.parametrize('change',['extra','missing','schema','nested','edge','search'])
def test_strict_nested_goal_contract(change,monkeypatch):
    raw=document().to_dict()
    if change=='extra':raw['result']={}
    elif change=='missing':del raw['design']
    elif change=='schema':raw['schema']='sipi.corner-impedance-design/2'
    elif change=='nested':raw['design']['mesh']['corner_size']=1e-6
    elif change=='edge':raw['design']['mesh']['edge_size']=1e-6
    else:raw['design']['search_tolerance_ohm']=.2
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('unexpected mesh'))
    with pytest.raises(ValueError):Document.from_dict(raw)


def test_roundtrip_snapshot_duplicate_and_original_rejection(monkeypatch):
    saved=document();original=saved.dumps()
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('unexpected mesh'))
    assert normalize_saved(original)==original
    assert Document.loads(original).dumps()==original
    raw=saved.to_dict();raw['corner_size']=999
    nested=saved.design.to_dict();nested['target_ohm']=999
    assert saved.dumps()==original
    with pytest.raises(FrozenInstanceError):saved._data_json='{}'
    with pytest.raises(ValueError,match='duplicate'):
        Document.loads(original.replace('"corner_size":','"corner_size": 1e-6, "corner_size":',1))
    with pytest.raises(ValueError):ImpedanceDesignDocument.from_dict(saved.to_dict())
    with pytest.raises(TypeError):Document({},1e-6)


def test_nested_evaluation_budget_is_checked_before_fields(monkeypatch):
    saved=document()
    monkeypatch.setattr(Document,'solve',lambda *a:pytest.fail('budget reached solve'))
    with pytest.raises(ValueError,match='before any solve'):
        execute_saved(saved.dumps(),max_evaluations=11)


@pytest.mark.parametrize('failure',['budget','bracket','refinement','mesh-search','mesh-refinement'])
def test_failed_receipts_keep_history_and_resolved_corner(failure,monkeypatch):
    raw=document().to_dict()
    if failure=='budget':raw['design']['max_evaluations']=3
    saved=Document.from_dict(raw)
    def analyze(self,**options):
        refined=options['corner_size']==1.25e-6
        if failure=='mesh-search' or failure=='mesh-refinement' and refined:
            raise MeshSizeLimitError('registered corner mesh budget')
        line=fake_analysis(self,**options)
        if failure=='bracket':line.z0=50.
        elif failure=='refinement' and refined:line.z0+=1
        return line
    monkeypatch.setattr(CrossSection,'analyze',analyze)
    request=SavedExecutionRequest(saved.dumps(),max_evaluations=12);receipt=request.run()
    output=receipt['execution']
    assert output['status']=='failed' and output['result'] is None
    error=output['error'];expected={'budget':2,'bracket':2,'refinement':4,'mesh-search':0,'mesh-refinement':3}[failure]
    assert len(error['history'])==expected
    if failure.startswith('mesh-'):
        nested=CornerCrossSectionDocument.from_dict(error['input'])
        assert nested.corner_size==(2.5e-6 if failure=='mesh-search' else 1.25e-6)
        assert error['cause_type']=='MeshSizeLimitError' and error['attempts']==expected+1
    record=SavedExecutionRecord(request,receipt,run_id='failure:'+failure,artifacts=ARTIFACTS)
    monkeypatch.setattr(Document,'solve',lambda *a:pytest.fail('reopening solved'))
    assert SavedExecutionRecord.loads(record.dumps()).receipt==receipt


@pytest.fixture(scope='module',params=['geometry','material'])
def actual(request):
    saved=document(request.param)
    return request.param,saved,saved.solve()


def test_actual_saved_goal_retains_parent_contract(actual,record_property):
    kind,saved,result=actual
    data=dict(kind=kind,parameter=result.parameter,target=result.target,requested=result.impedance,
        refined=result.refined_impedance,input=result.document.to_dict(),
        material_evaluation=None if result.material_evaluation_json is None else json.loads(result.material_evaluation_json),
        history=[dict(parameter=row.parameter,impedance=row.impedance,stage=row.stage) for row in result.history])
    record_property('saved_corner_goal',json.dumps(data))
    assert abs(result.residual)<=.025 and abs(result.refined_residual)<=.1
    assert len(result.history)==4 and result.history[-1].stage=='refinement'
    assert result.document.corner_size==saved.corner_size


def test_actual_result_transport_and_project_reopen(actual,monkeypatch):
    kind,saved,result=actual
    def replay(self):
        assert self.dumps()==saved.dumps()
        return result
    # Explicit transport replay of the actual result; no additional field.
    monkeypatch.setattr(Document,'solve',replay)
    request=SavedExecutionRequest(saved.dumps(),max_evaluations=12);receipt=request.run()
    output=receipt['execution'];assert output['status']=='complete'
    assert output['result']['unit']=='ohm' and output['result']['document']==result.document.to_dict()
    record=SavedExecutionRecord(request,receipt,run_id='corner-goal:'+kind,artifacts=ARTIFACTS)
    project=SavedProject(request,project_id='p',design_id='a',title='Goal',label='A').attach_record('a',record,select=True)
    monkeypatch.setattr(Document,'solve',lambda *a:pytest.fail('reopening solved'))
    reopened=SavedProject.loads(project.dumps())
    assert reopened.current_record('a').receipt==receipt
    assert Document.loads(reopened.prepare('a').source_text).dumps()==saved.dumps()
    edited=Document(saved.design,saved.corner_size/2)
    changed=reopened.update_design('a',SavedExecutionRequest(edited.dumps(),max_evaluations=12))
    assert changed.current_record('a') is None and changed.design('a')['records']==[record.to_dict()]
