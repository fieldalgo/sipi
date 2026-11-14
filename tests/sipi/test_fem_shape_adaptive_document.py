# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict bounded FEM refinement grammar and field-free common admission."""
import json
import pytest
from sipi import CrossSection,FEMShapeAdaptiveResolutionDocument as Document
from sipi.execution import normalize_saved,execute_saved
from sipi.execution_request import SavedExecutionRequest
from test_fem_shape_resolution import inputs,TOLERANCES


def document():
    base,outer=inputs()
    return Document(base,outer_documents=outer,tolerances=TOLERANCES,max_levels=2,max_solves=5)


def test_field_free_detached_roundtrip(monkeypatch):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**kw:pytest.fail('normalization meshed'))
    doc=document();text=doc.dumps()
    assert text==Document.loads(text).dumps()==normalize_saved(text)
    assert SavedExecutionRequest(text).input_json==text
    copy=doc.to_dict();copy['line']['length_m']=1;copy['tolerances'].clear()
    assert doc.dumps()==text


@pytest.mark.parametrize('kind',['extra','missing','schema','outer-type','outer-empty','nested','unit','allowance-extra','allowance-missing','negative','factor','budget','physical','levels','duplicate','nonfinite'])
def test_strict_inputs_before_fields(monkeypatch,kind):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**kw:pytest.fail('invalid input meshed'))
    raw=document().to_dict()
    if kind=='extra':raw['unexpected']=0
    if kind=='missing':raw.pop('refinement_factor')
    if kind=='schema':raw['schema']='unknown'
    if kind=='outer-type':raw['outer_lines']={}
    if kind=='outer-empty':raw['outer_lines']=[]
    if kind=='nested':raw['line']['schema']='sipi.transmission-line/7'
    if kind=='unit':raw['tolerances']['R']=raw['tolerances'].pop('R_ohm_per_m')
    if kind=='allowance-extra':raw['tolerances']['R_ohm_per_m']['floor']=0
    if kind=='allowance-missing':raw['tolerances']['R_ohm_per_m'].pop('absolute')
    if kind=='negative':raw['tolerances']['R_ohm_per_m']['relative']=-1
    if kind=='factor':raw['refinement_factor']=True
    if kind=='budget':raw['max_solves']=4
    if kind=='levels':raw['max_levels']=True
    if kind=='physical':raw['outer_lines'][0]['length_m']=.03
    if kind=='duplicate':
        with pytest.raises(ValueError):Document.loads('{"schema":"duplicate",'+document().dumps()[1:])
        return
    if kind=='nonfinite':raw['tolerances']['R_ohm_per_m']['relative']=float('nan')
    with pytest.raises((ValueError,TypeError)):Document.loads(json.dumps(raw))


def test_common_budget_precedes_any_line(monkeypatch):
    from sipi.fem_shape_line import FEMShapeTransmissionLineDocument
    monkeypatch.setattr(FEMShapeTransmissionLineDocument,'analyze',lambda *a,**kw:pytest.fail('budget reached fields'))
    with pytest.raises(ValueError,match='budget'):execute_saved(document().dumps(),max_evaluations=4)


def test_line_diagnostics_are_not_resolution_diagnostics():
    with pytest.raises(ValueError):SavedExecutionRequest(document().dumps(),diagnostics=('characteristic',))


def test_interrupt_is_not_converted_to_failed_receipt(monkeypatch):
    from sipi.fem_shape_line import FEMShapeTransmissionLineDocument
    def stop(self):raise KeyboardInterrupt('cancelled')
    monkeypatch.setattr(FEMShapeTransmissionLineDocument,'analyze',stop)
    with pytest.raises(KeyboardInterrupt):SavedExecutionRequest(document().dumps()).run()
