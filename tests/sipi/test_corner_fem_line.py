# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit corner controls preserve line physics, provenance and failures."""
from dataclasses import FrozenInstanceError
import json
import numpy as np
import pytest
from meshine import MeshSizeLimitError
from sipi import CrossSection, CornerFEMShapeTransmissionLineDocument as Document
from sipi.fem_shape_line import FEMShapeTransmissionLineDocument, FEMShapeLineError, FEMShapeCurrentError
from sipi.execution import execute_saved, normalize_saved
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject
import sipi.fem_shape_line as api
from test_fem_shape_line import document as original
from test_fem_shape_line_physical import independent
from test_fem_shape_loss_physical import snapshot
from test_execution_record import ARTIFACTS
from test_project import project


def document(corner=2.5e-6): return Document(original(),corner)


@pytest.mark.parametrize('bad',[None,True,0.,-1.,float('nan'),float('inf'),'2e-6',1e-5])
def test_corner_admission_precedes_fields(bad,monkeypatch):
    raw=document().to_dict();raw['corner_size']=bad
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('unexpected mesh'))
    with pytest.raises(ValueError):Document.from_dict(raw)


@pytest.mark.parametrize('change',['extra','missing','schema','nested','signal','dc','skin'])
def test_nested_line_remains_strict(change,monkeypatch):
    raw=document().to_dict()
    if change=='extra':raw['result']={}
    elif change=='missing':del raw['line']
    elif change=='schema':raw['schema']='sipi.corner-fem-shape-transmission-line/2'
    elif change=='nested':raw['line']['cross_section']['mesh']['corner_size']=1e-6
    elif change=='signal':raw['line']['conductors'].pop('negative')
    elif change=='dc':raw['line']['frequency_hz']=[0.]
    else:raw['line']['ground_thickness_m']=1e-10
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('unexpected mesh'))
    with pytest.raises(ValueError):Document.from_dict(raw)


def test_canonical_snapshot_and_original_rejection(monkeypatch):
    doc=document();raw=doc.dumps()
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('unexpected mesh'))
    assert Document.loads(raw).dumps()==normalize_saved(raw)==raw
    copy=doc.to_dict();copy['corner_size']=999
    line=doc.line;line._data['length_m']=999
    assert doc.dumps()==raw
    assert doc.cross_section.corner_size==doc.corner_size
    with pytest.raises(FrozenInstanceError):doc._data_json='{}'
    with pytest.raises(ValueError,match='duplicate'):
        Document.loads(raw.replace('"corner_size":','"corner_size": 1e-6, "corner_size":',1))
    with pytest.raises(ValueError):FEMShapeTransmissionLineDocument.from_dict(doc.to_dict())
    with pytest.raises(TypeError):Document({},1e-6)


def test_budget_and_diagnostics_preflight(monkeypatch):
    raw=document().to_dict();raw['line']['frequency_hz']=[2e9,3e9,5e9]
    doc=Document.from_dict(raw)
    monkeypatch.setattr(Document,'analyze',lambda *a:pytest.fail('budget reached field'))
    with pytest.raises(ValueError,match='before any field'):
        execute_saved(doc.dumps(),max_evaluations=2)
    request=SavedExecutionRequest(doc.dumps(),max_evaluations=3,diagnostics=('characteristic','modes'))
    assert request.input_json==doc.dumps()


@pytest.fixture(scope='module',params=[5e-6,2.5e-6],ids=['equal-default','corner-half'])
def actual(request):
    doc=document(request.param)
    return doc,doc.analyze()


def test_actual_mesh_currents_and_independent_network(actual,record_property):
    doc,result=actual
    row=dict(corner=doc.corner_size,mesh=result.mesh_observation,loss=snapshot(result.conductor),current=result.current_record(),network_errors=independent(result))
    record_property('corner_fem_line',json.dumps(row,allow_nan=False))
    assert result.input_json==doc.dumps() and result.mesh_settings['corner_size']==doc.corner_size
    assert len(result.current_factors.samples)==24
    assert np.linalg.eigvalsh(result.R).min()>0
    assert np.linalg.eigvalsh(result.conductor.L_internal).min()>0
    # Current derivative, two-step and extension gates run inside the unchanged method.
    # This is not a finite-mesh convergence claim for weak mutual resistance.


def test_actual_result_request_record_and_project(actual,monkeypatch):
    doc,result=actual
    def replay(self):
        assert self.dumps()==doc.dumps()
        return result
    monkeypatch.setattr(Document,'analyze',replay)
    request=SavedExecutionRequest(doc.dumps(),diagnostics=('characteristic','modes'))
    receipt=request.run();out=receipt['execution'];assert out['status']=='complete'
    assert out['result']['current_solver']==result.current_record()
    np.testing.assert_array_equal(out['result']['R_ohm_per_m'],result.R)
    saved=SavedExecutionRecord(request,receipt,run_id='corner:line',artifacts=ARTIFACTS)
    attached=project(request).attach_record('a',saved,select=True)
    monkeypatch.setattr(Document,'analyze',lambda *a:pytest.fail('reopening solved'))
    reopened=SavedProject.loads(attached.dumps());assert reopened.current_record('a').receipt==receipt
    changed=reopened.update_design('a',SavedExecutionRequest(document(doc.corner_size/2).dumps()))
    assert changed.current_record('a') is None and changed.design('a')['records']==[saved.to_dict()]


@pytest.mark.parametrize('stage',['material-admission','conductor-admission','mesh','current','conductor','dielectric','network'])
def test_staged_failure_keeps_corner_and_current(actual,monkeypatch,stage):
    doc,result=actual;original_line=doc.line;original_cross=doc.cross_section
    field=original_cross.section.mesh(**original_cross.mesh_options)
    request=SavedExecutionRequest(doc.dumps());import sipi.execution as execution
    monkeypatch.setattr(execution,'_load',lambda *a,**kw:doc)
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**kw:field)
    monkeypatch.setattr(api,'fem_shape_current_factors',lambda *a:result.current_factors)
    def fail(*a,**kw):raise MeshSizeLimitError('retained limit') if stage=='mesh' else ValueError('retained stage')
    owner,name={'material-admission':(api,'_material_samples'),'conductor-admission':(api,'_boundary_samples'),
        'mesh':(CrossSection,'mesh'),'current':(api,'fem_shape_current_factors'),
        'conductor':(api,'_boundary_from_factors'),'dielectric':(api,'_dispersive_from_mesh'),'network':(api,'rlgc_network')}[stage]
    monkeypatch.setattr(owner,name,fail)
    # Reuse admitted snapshots to exercise each staged failure, including admission.
    monkeypatch.setattr(Document,'line',property(lambda self:original_line))
    monkeypatch.setattr(Document,'cross_section',property(lambda self:original_cross))
    receipt=request.run();error=receipt['execution']['error']
    assert receipt['execution']['status']=='failed' and error['stage']==stage
    assert error['input']==doc.to_dict()
    if stage=='mesh':assert error['cause_type']=='MeshSizeLimitError'
    expected=None if stage in ('material-admission','conductor-admission','mesh','current') else result.current_record()
    assert error['current_solver']==expected
    monkeypatch.undo()
    saved=SavedExecutionRecord(request,receipt,run_id='corner:failed',artifacts=ARTIFACTS)
    assert SavedExecutionRecord.loads(saved.dumps()).receipt==receipt


def test_partial_current_and_interruption(actual,monkeypatch):
    doc,result=actual;cur=result.current_factors
    error=FEMShapeCurrentError('offset solve',stage='capacitance-differences',base=cur.base,
        extension_parts=cur.extension_parts,samples=cur.samples[:1],request=(0,0,0,1,cur.step_m))
    def fail(*a):raise error
    monkeypatch.setattr(api,'fem_shape_current_factors',fail)
    request=SavedExecutionRequest(doc.dumps());receipt=request.run();out=receipt['execution']
    assert out['status']=='failed' and out['error']['input']==doc.to_dict()
    assert out['error']['partial_current']['failed_request']==list(error.request)
    assert len(out['error']['partial_current']['samples'])==1
    record=SavedExecutionRecord(request,receipt,run_id='corner:partial',artifacts=ARTIFACTS)
    assert SavedExecutionRecord.loads(record.dumps()).receipt==receipt
    def stop(*a):raise KeyboardInterrupt('cancelled')
    monkeypatch.setattr(api,'fem_shape_current_factors',stop)
    with pytest.raises(KeyboardInterrupt):doc.analyze()
