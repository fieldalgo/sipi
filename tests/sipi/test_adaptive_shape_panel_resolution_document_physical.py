# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Actual saved plans reproduce direct finite observations and retained failures."""
import json
import pytest
from sipi.shape_panel_line import ShapePanelTransmissionLineDocument,ShapePanelLineError
from sipi.panel_shape_conductor import PanelShapeCurrentError
from sipi.adaptive_shape_panel_resolution_document import AdaptiveShapePanelResolutionDocument as Document
from sipi.execution import execute_saved
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord as Record
from test_execution_record import ARTIFACTS
from test_adaptive_shape_panel_resolution import inputs,TOLERANCES
from test_adaptive_shape_panel_resolution_physical import observed
from test_adaptive_shape_panel_resolution_document import document


def test_actual_direct_saved_and_execution_receipt_match(observed,monkeypatch,record_property):
    coated,line,steps,direct=observed;doc=document(coated)
    fields={r.input_json:r.result for r in direct.evaluations};calls=[]
    def replay(self):calls.append(self.dumps());return fields[self.dumps()]
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',replay)
    assert doc.analyze(max_evaluations=8).to_dict()==direct.to_dict()
    request=SavedExecutionRequest(doc.dumps(),max_evaluations=8);receipt=request.run()
    assert receipt['execution']['result']==direct.to_dict() and receipt['execution']['status']=='complete'
    assert len(calls)==16
    record_property('saved_adaptive_shape_observation',json.dumps(direct.to_dict(),allow_nan=False))
    for version in (1,2):
        saved=Record(request,receipt,run_id='adaptive-shape:actual',artifacts=ARTIFACTS,schema=f'sipi.execution-record/{version}')
        assert Record.loads(saved.dumps()).receipt==receipt
    assert len(calls)==16
    raw=doc.to_dict();raw['tolerances']={'R_ohm_per_m':dict(relative=.005,absolute=0.)}
    rejected=execute_saved(json.dumps(raw),max_evaluations=8)
    assert rejected['status']=='complete' and not rejected['result']['accepted']
    assert rejected['result']['stop_reason']=='outer-unaccepted'
    record_property('saved_adaptive_shape_rejection',json.dumps(rejected['result'],allow_nan=False))


def test_original_partial_current_at_joint_is_saved_without_another_solve(observed,monkeypatch,record_property):
    coated,line,steps,direct=observed;doc=document(coated);failed=direct.evaluations[3]
    fields={r.input_json:r.result for r in direct.evaluations};calls=[];factors=failed.result.current_factors
    cause=PanelShapeCurrentError('retained actual partial current',samples=factors.samples[:3],request=factors.samples[3].request)
    error=ShapePanelLineError(cause,stage='current',input_json=failed.input_json,factors=None,settings=failed.result.panel_settings)
    def replay(self):
        calls.append(self.dumps())
        if self.dumps()==failed.input_json:raise error
        return fields[self.dumps()]
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',replay)
    request=SavedExecutionRequest(doc.dumps(),max_evaluations=8);receipt=request.run();out=receipt['execution']
    assert out['status']=='failed' and out['result'] is None and len(calls)==4
    partial=out['error']['partial_assessment']
    assert partial['failure']['details']==error.to_dict() and partial['evaluations']==direct.to_dict()['evaluations'][:3]
    assert len(partial['failure']['details']['partial_current']['samples'])==3
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('restore solved'))
    for version in (1,2):
        saved=Record(request,receipt,run_id='adaptive-shape:partial',artifacts=ARTIFACTS,schema=f'sipi.execution-record/{version}')
        assert Record.loads(saved.dumps()).receipt==receipt
    record_property('saved_adaptive_shape_partial',json.dumps(out,allow_nan=False))
