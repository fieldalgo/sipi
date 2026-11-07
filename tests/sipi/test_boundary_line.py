# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved distinct-metal shared-mesh composition and downstream replay."""
import json
import numpy as np
import pytest

from sipi import CrossSection, CrossSectionDocument, coupled_microstrip
from sipi.line_model import TransmissionLineDocument
from sipi.boundary_conductor import SurfaceMetal, surface_conductor_loss_by_boundary
from sipi.roughness import CausalHuray
from sipi.execution import normalize_saved, execute_saved
from sipi.circuit_document import CircuitDocument
from sipi.termination import terminate_network
from sipi.network import rlgc_network


def document():
    cross = CrossSectionDocument(coupled_microstrip(width=.5e-3, gap=.3e-3,
        substrate_height=1e-3, thickness=50e-6, eps_r=4.),
        mesh=dict(edge_size=5e-6, far_size=.2e-3, grade=.1))
    names = [t.name for t in cross.section.traces if not t.ground]
    def metal(sigma, roughness):
        return dict(conductivity=sigma, relative_permeability=1., roughness=roughness)
    conductor = dict(kind='surface-boundaries', ground_thickness=35e-6,
        conductors={names[0]: metal(58e6, dict(kind='causal-huray', radii_m=[.2e-6], surface_ratios=[2.])),
                    names[1]: metal(35e6, dict(kind='hammerstad', rms_m=.5e-6))},
        reference=metal(45e6, dict(kind='smooth')))
    return TransmissionLineDocument(cross, [1e9, 4e9], materials={}, conductor=conductor,
                                    length=.03, schema='sipi.transmission-line/3')


@pytest.fixture(scope='module')
def extracted():
    doc = document()
    return doc, doc.analyze()


def test_direct_boundary_and_dielectric_apis_match_shared_saved_result(extracted):
    doc, result = extracted; section = doc.cross_section.section
    names = result.names
    loss = surface_conductor_loss_by_boundary(section, result.frequency,
        conductors={names[0]: SurfaceMetal(58e6, roughness=CausalHuray([.2e-6], [2.])),
                    names[1]: SurfaceMetal(35e6, roughness_rms=.5e-6)},
        reference=SurfaceMetal(45e6), ground_thickness=35e-6, **doc.cross_section.mesh_options)
    dielectric = section.analyze(**doc.cross_section.mesh_options)
    for actual, expected in ((result.R, loss.R), (result.L, dielectric.L+loss.L_internal),
                              (result.C, np.broadcast_to(dielectric.C, result.C.shape))):
        np.testing.assert_allclose(actual, expected, rtol=1e-10, atol=0)
    expected = rlgc_network(result.frequency, R=loss.R, L=dielectric.L+loss.L_internal,
        C=dielectric.C, G=np.zeros((2, 2)), length=.03, names=names)
    np.testing.assert_allclose(result.network.s, expected.s, rtol=0, atol=1e-10)
    assert not np.allclose(result.R[:, 0, 0], result.R[:, 1, 1])


def test_replay_is_detached_and_uses_one_mesh(monkeypatch, extracted):
    doc, expected = extracted; data = doc.to_dict()
    restored = TransmissionLineDocument.from_dict(data)
    data['conductor']['reference']['conductivity'] = 123
    assert restored.dumps() == doc.dumps() == normalize_saved(doc.dumps())
    calls = []; original = CrossSection.mesh
    def counted(self, *args, **kwargs):
        calls.append(1); return original(self, *args, **kwargs)
    monkeypatch.setattr(CrossSection, 'mesh', counted)
    got = TransmissionLineDocument.loads(doc.dumps()).analyze()
    assert len(calls) == 1
    np.testing.assert_allclose(got.R, expected.R, rtol=1e-12)
    np.testing.assert_allclose(got.network.s, expected.network.s, rtol=0, atol=1e-10)
    assert got.input_json == doc.dumps()


def test_common_schema_two_and_three_preserve_results():
    raw = document().to_dict()
    raw['conductor'] = dict(kind='surface', conductivity=58e6, relative_permeability=1.,
        roughness=dict(kind='smooth'), ground_thickness=35e-6)
    new = TransmissionLineDocument.from_dict(raw).analyze()
    raw['schema'] = 'sipi.transmission-line/2'
    old = TransmissionLineDocument.from_dict(raw).analyze()
    for key in ('R', 'L', 'G', 'C'):
        np.testing.assert_allclose(getattr(new, key), getattr(old, key), rtol=1e-12, atol=0)
    np.testing.assert_allclose(new.network.s, old.network.s, rtol=0, atol=1e-12)


def test_execution_keeps_boundary_diagnostics_and_circuit_accepts_saved_source(extracted):
    doc, direct = extracted
    output = execute_saved(doc.dumps(), diagnostics=['characteristic'])
    assert output['status'] == 'complete' and output['input'] == doc.to_dict()
    b = output['result']['conductor_boundaries']; loss = direct.conductor
    assert b['labels'] == list(loss.boundary_labels)
    np.testing.assert_allclose(b['resistance_ohm_per_m'], loss.resistance_parts, rtol=1e-12)
    np.testing.assert_allclose(b['skin_depth_m'], loss.skin_depth, rtol=1e-12)
    np.testing.assert_allclose(b['roughness_factor'], loss.roughness_factor, rtol=1e-12)
    np.testing.assert_allclose(np.array(b['surface_impedance_ohms']['real'])+1j*np.array(b['surface_impedance_ohms']['imag']),
                               loss.surface_impedance, rtol=1e-12)
    json.dumps(output, allow_nan=False)
    name = direct.network.port_names[0]
    circuit = CircuitDocument(dict(kind='transmission-line', document=doc.to_dict()),
        excitation=dict(kind='sources', voltages={name: 1}), terminations={})
    loaded = circuit.analyze()
    expected = terminate_network(direct.network, source_voltages={name: 1}, terminations={})
    np.testing.assert_allclose(loaded.response.voltage, expected.voltage, rtol=0, atol=1e-10)
    assert loaded.extraction.conductor.boundary_labels == loss.boundary_labels


@pytest.mark.parametrize('change', ['old_schema', 'missing_signal', 'extra_signal', 'extra_metal',
    'missing_roughness', 'unknown_roughness', 'boolean_sigma', 'nonfinite_sigma', 'thin_reference',
    'low_signal_sigma', 'low_reference_sigma', 'unknown_top', 'unknown_conductor', 'missing_reference'])
def test_invalid_saved_boundary_materials_rejected_before_meshing(monkeypatch, change):
    raw = document().to_dict(); c = raw['conductor']; name = next(iter(c['conductors']))
    if change == 'old_schema': raw['schema'] = 'sipi.transmission-line/2'
    if change == 'missing_signal': del c['conductors'][name]
    if change == 'extra_signal': c['conductors']['unknown'] = c['reference'].copy()
    if change == 'extra_metal': c['reference']['extra'] = 1
    if change == 'missing_roughness': del c['reference']['roughness']
    if change == 'unknown_roughness': c['reference']['roughness'] = dict(kind='unknown')
    if change == 'boolean_sigma': c['reference']['conductivity'] = True
    if change == 'nonfinite_sigma': c['reference']['conductivity'] = float('inf')
    if change == 'thin_reference': c['ground_thickness'] = 1e-9
    if change == 'low_signal_sigma': c['conductors'][name]['conductivity'] = 1e4
    if change == 'low_reference_sigma': c['reference']['conductivity'] = 1e4
    if change == 'unknown_top': raw['extra'] = 1
    if change == 'unknown_conductor': c['extra'] = 1
    if change == 'missing_reference': del c['reference']
    def forbidden(*args, **kwargs): pytest.fail('invalid input reached meshing')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    with pytest.raises(ValueError): TransmissionLineDocument.from_dict(raw)
    with pytest.raises(ValueError): normalize_saved(json.dumps(raw))


def test_valid_normalization_never_meshes_and_duplicate_keys_reject(monkeypatch):
    text = document().dumps()
    def forbidden(*args, **kwargs): pytest.fail('normalization reached meshing')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    assert normalize_saved(text) == text
    duplicated = text.replace('"conductivity": 45000000.0', '"conductivity": 45000000.0, "conductivity": 45000000.0')
    assert duplicated != text
    with pytest.raises(ValueError): TransmissionLineDocument.loads(duplicated)
