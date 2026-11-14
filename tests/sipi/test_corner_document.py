# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved corner controls, actual fields and detached execution records."""
from dataclasses import FrozenInstanceError
import json
import numpy as np
import pytest
from sipi import CrossSection, CrossSectionDocument, CornerCrossSectionDocument as Document
from sipi.execution import execute_saved, normalize_saved
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject
from test_corner_mesh_control import section, OPTIONS


def document(kind='rectangle'):
    return Document(CrossSectionDocument(section(kind), mesh=OPTIONS), 2.5e-6)


@pytest.mark.parametrize('bad', [True, False, None, 0., -1., float('nan'), float('inf'),
                                '1e-6', 1e-6j, [1e-6], 2e-5])
def test_invalid_corner_rejected_before_field(bad, monkeypatch):
    monkeypatch.setattr(CrossSection, 'mesh', lambda *a,**kw: pytest.fail('unexpected field'))
    raw = document().to_dict(); raw['corner_size'] = bad
    with pytest.raises((ValueError, TypeError)):
        Document.from_dict(raw)


@pytest.mark.parametrize('change', ['extra', 'missing', 'version', 'nested', 'length', 'oversized'])
def test_strict_snapshot_contract(change, monkeypatch):
    raw = document().to_dict()
    if change == 'extra': raw['result'] = {}
    elif change == 'missing': del raw['corner_size']
    elif change == 'version': raw['schema'] = 'sipi.corner-cross-section/2'
    elif change == 'nested': raw['cross_section']['mesh']['corner_size'] = 1e-6
    elif change == 'length': raw['cross_section']['length_unit'] = 'mm'
    else: raw['cross_section']['mesh']['edge_size'] = 1e-6
    monkeypatch.setattr(CrossSection, 'mesh', lambda *a,**kw: pytest.fail('unexpected field'))
    with pytest.raises(ValueError): Document.from_dict(raw)


def test_duplicate_nonfinite_and_wrong_python_input():
    raw = document().dumps()
    with pytest.raises(ValueError, match='duplicate'):
        Document.loads(raw.replace('"corner_size":', '"corner_size": 1e-6, "corner_size":', 1))
    for token in ('NaN', 'Infinity', '-Infinity'):
        with pytest.raises(ValueError, match='nonfinite'):
            Document.loads('{"corner_size":'+token+'}')
    with pytest.raises(TypeError): Document(section('rectangle'), 1e-6)


def test_defaults_and_detached_snapshot_without_field(monkeypatch):
    monkeypatch.setattr(CrossSection, 'mesh', lambda *a,**kw: pytest.fail('unexpected field'))
    cross = CrossSectionDocument(section('rectangle'))
    corner = cross.section.mesh_settings()['edge_size']/2
    doc = Document(cross, corner)
    assert doc.mesh_options == dict(corner_size=corner)
    assert Document.loads(doc.dumps()).dumps() == doc.dumps()
    assert doc.cross_section.dumps() == cross.dumps()
    raw = doc.to_dict();raw['corner_size'] = 999
    options = doc.mesh_options;options['corner_size'] = 999
    assert doc.corner_size == corner
    with pytest.raises(FrozenInstanceError): doc._data_json = '{}'
    with pytest.raises(ValueError): Document(cross, corner*4)
    with pytest.raises(ValueError): CrossSectionDocument.from_dict(doc.to_dict())


@pytest.fixture(scope='module', params=['rectangle', 'taper', 'polygon', 'region'])
def observed(request):
    doc = document(request.param)
    return request.param, doc, doc.analyze()


def test_actual_saved_fields_match_direct_contract(observed, record_property):
    kind, doc, actual = observed
    expected = section(kind).analyze(**OPTIONS, corner_size=doc.corner_size)
    for key in ('C', 'C0', 'C_loss', 'L'):
        np.testing.assert_array_equal(getattr(actual,key), getattr(expected,key))
    np.testing.assert_allclose(actual.C, 4*actual.C0, rtol=1e-9, atol=0)
    record_property('saved_corner', json.dumps(dict(kind=kind, input=doc.to_dict(), C0=actual.C0.tolist())))


def test_record_and_project_reopen_without_recalculation(observed, monkeypatch):
    kind, doc, actual = observed
    calls = []
    def replay(self):
        assert self.dumps() == doc.dumps()
        calls.append(self.dumps())
        return actual
    # Explicit replay of the actual module field; transport adds no field solve.
    monkeypatch.setattr(Document, 'analyze', replay)
    request = SavedExecutionRequest(doc.dumps())
    assert normalize_saved(doc.dumps()) == doc.dumps()
    receipt = request.run()
    assert len(calls) == 1 and receipt['execution']['status'] == 'complete'
    assert receipt['execution']['result']['C0_f_per_m'] == actual.C0.tolist()
    record = SavedExecutionRecord(request, receipt, run_id='corner:'+kind, artifacts=[
        dict(component='sipi', version='example-only', kind='wheel', sha256='1'*64)])
    project = SavedProject(request, project_id='corner', design_id='a', title='Corner', label='A')
    project = project.attach_record('a', record, select=True)
    monkeypatch.setattr(Document, 'analyze', lambda *a: pytest.fail('reopening solved'))
    reopened = SavedProject.loads(project.dumps())
    assert reopened.current_record('a').receipt == receipt
    assert Document.loads(reopened.prepare('a').source_text).dumps() == doc.dumps()
    edited = Document(doc.cross_section, doc.corner_size/2)
    changed = reopened.update_design('a', SavedExecutionRequest(edited.dumps()))
    assert changed.current_record('a') is None
    assert changed.design('a')['records'] == [record.to_dict()]
    assert reopened.current_record('a').receipt == receipt
