# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved signal-face composition, one-mesh sharing and downstream replay."""
import json

import numpy as np
import pytest

from sipi import CrossSection, CrossSectionDocument, coupled_microstrip
from sipi.boundary_conductor import SurfaceMetal
from sipi.face_conductor import TraceFaceMetals, surface_conductor_loss_by_face
from sipi.line_model import TransmissionLineDocument
from sipi.dielectric import DebyeDielectric, dispersive_line
from sipi.roughness import CausalHuray
from sipi.execution import execute_saved, normalize_saved
from sipi.circuit_document import CircuitDocument
from sipi.termination import terminate_network
from sipi.network import rlgc_network


def metal(sigma=58e6, roughness=None):
    return dict(conductivity=sigma, relative_permeability=1.,
                roughness=dict(kind='smooth') if roughness is None else roughness)


def document():
    section = coupled_microstrip(width=.5e-3, gap=.3e-3, substrate_height=.5e-3,
        thickness=50e-6, top_width=.4e-3, eps_r=4., air_height=2e-3, box_width=6e-3)
    cross = CrossSectionDocument(section, mesh=dict(edge_size=2.5e-6, far_size=.1e-3, grade=.05))
    conductors = {t.name: {face: metal() for face in ('bottom', 'top', 'left', 'right')}
                  for t in section.traces}
    conductors['positive']['bottom'] = metal(58e6, dict(kind='causal-huray', radii_m=[.2e-6], surface_ratios=[2.]))
    conductors['positive']['top'] = metal(35e6, dict(kind='hammerstad', rms_m=.5e-6))
    conductor = dict(kind='surface-faces', conductors=conductors, reference=metal(45e6), ground_thickness=35e-6)
    return TransmissionLineDocument(cross, [1e9, 4e9], materials={'substrate': DebyeDielectric(2., [2.], [2e9])},
        conductor=conductor, length=.03, schema='sipi.transmission-line/4')


@pytest.fixture(scope='module')
def extracted():
    doc = document()
    return doc, doc.analyze()


def test_saved_face_rlgc_and_network_match_separate_direct_apis(extracted):
    doc, result = extracted; section = doc.cross_section.section
    smooth = SurfaceMetal(58e6)
    faces = {t.name: TraceFaceMetals.uniform(smooth) for t in section.traces}
    faces['positive'] = TraceFaceMetals(SurfaceMetal(58e6, roughness=CausalHuray([.2e-6], [2.])),
        SurfaceMetal(35e6, roughness_rms=.5e-6), smooth, smooth)
    metal_loss = surface_conductor_loss_by_face(section, result.frequency, conductors=faces,
        reference=SurfaceMetal(45e6), ground_thickness=35e-6, **doc.cross_section.mesh_options)
    dielectric = dispersive_line(section, result.frequency, materials={'substrate': DebyeDielectric(2., [2.], [2e9])},
                                  **doc.cross_section.mesh_options)
    for actual, expected in [(result.R, metal_loss.R), (result.L, dielectric.L+metal_loss.L_internal),
                              (result.C, dielectric.C), (result.G, dielectric.G)]:
        np.testing.assert_allclose(actual, expected, rtol=1e-10, atol=0)
    network = rlgc_network(result.frequency, R=metal_loss.R, L=dielectric.L+metal_loss.L_internal,
        C=dielectric.C, G=dielectric.G, length=.03, names=result.names)
    np.testing.assert_allclose(result.network.s, network.s, rtol=0, atol=1e-10)
    assert np.linalg.svd(result.network.s, compute_uv=False).max() <= 1+1e-10


def test_saved_replay_detaches_and_shares_one_mesh_and_vacuum_capacitance(monkeypatch, extracted):
    import sipi.line_model as implementation
    doc, expected = extracted; raw = doc.to_dict()
    restored = TransmissionLineDocument.from_dict(raw)
    raw['conductor']['conductors']['positive']['bottom']['conductivity'] = 1.
    assert restored.dumps() == doc.dumps() == normalize_saved(doc.dumps())
    meshes = []; capacitances = []; original_mesh = CrossSection.mesh
    original_dielectric = implementation._dispersive_from_mesh
    def counted(self, **kwargs):
        meshes.append(1); return original_mesh(self, **kwargs)
    def shared(*args, **kwargs):
        capacitances.append(kwargs['c0']); return original_dielectric(*args, **kwargs)
    monkeypatch.setattr(CrossSection, 'mesh', counted)
    monkeypatch.setattr(implementation, '_dispersive_from_mesh', shared)
    result = TransmissionLineDocument.loads(restored.dumps()).analyze()
    assert len(meshes) == len(capacitances) == 1
    assert capacitances[0] is result.conductor.factors.C0
    assert result.input_json == doc.dumps()
    np.testing.assert_allclose(result.R, expected.R, rtol=1e-12)
    np.testing.assert_allclose(result.network.s, expected.network.s, rtol=0, atol=1e-10)


@pytest.mark.parametrize('kind', ['perfect', 'surface', 'surface-boundaries'])
def test_older_conductor_contracts_are_unchanged_in_version_four(kind):
    raw = document().to_dict()
    if kind == 'perfect': raw['conductor'] = dict(kind=kind)
    if kind == 'surface': raw['conductor'] = dict(kind=kind, conductivity=58e6, relative_permeability=1.,
        roughness=dict(kind='smooth'), ground_thickness=35e-6)
    if kind == 'surface-boundaries': raw['conductor'] = dict(kind=kind,
        conductors={name: faces['bottom'] for name, faces in raw['conductor']['conductors'].items()},
        reference=metal(45e6), ground_thickness=35e-6)
    new = TransmissionLineDocument.from_dict(raw).analyze()
    raw['schema'] = 'sipi.transmission-line/3'
    old = TransmissionLineDocument.from_dict(raw).analyze()
    for attr in ('R', 'L', 'G', 'C'):
        np.testing.assert_allclose(getattr(new, attr), getattr(old, attr), rtol=1e-12, atol=0)
    np.testing.assert_allclose(new.network.s, old.network.s, rtol=0, atol=1e-12)
    default = TransmissionLineDocument(document().cross_section, [1e9], materials={},
        conductor=dict(kind='perfect'), length=.03)
    assert default.to_dict()['schema'] == 'sipi.transmission-line/1'


def test_execution_preserves_face_power_current_and_reference_diagnostics(extracted):
    doc, result = extracted; loss = result.conductor
    report = execute_saved(doc.dumps(), diagnostics=['characteristic'])
    assert report['status'] == 'complete' and report['input'] == doc.to_dict()
    assert report['result']['diagnostics']['characteristic']['status'] == 'complete'
    b = report['result']['conductor_boundaries']
    assert b['labels'] == list(loss.boundary_labels)
    for key, expected in [('resistance_ohm_per_m', loss.resistance_parts), ('skin_depth_m', loss.skin_depth),
        ('roughness_factor', loss.roughness_factor), ('surface_current_factors_per_m', loss.factors.parts),
        ('current_integrals', loss.factors.current_integrals),
        ('whole_boundary_current_integrals', loss.factors.base.current_integrals)]:
        np.testing.assert_allclose(b[key], expected, rtol=1e-12)
    np.testing.assert_allclose(np.array(b['surface_impedance_ohms']['real'])+1j*np.array(b['surface_impedance_ohms']['imag']),
                               loss.surface_impedance, rtol=1e-12)
    assert b['current_flux_error'] == pytest.approx(loss.factors.current_error, rel=1e-12)
    json.dumps(report, allow_nan=False)


def test_saved_face_line_is_reused_by_existing_circuit_source(extracted):
    doc, result = extracted
    name = result.network.port_names[0]
    circuit = CircuitDocument(dict(kind='transmission-line', document=doc.to_dict()),
        excitation=dict(kind='sources', voltages={name: 1}), terminations={})
    loaded = circuit.analyze()
    expected = terminate_network(result.network, source_voltages={name: 1}, terminations={})
    np.testing.assert_allclose(loaded.response.voltage, expected.voltage, rtol=0, atol=1e-10)
    assert loaded.extraction.conductor.boundary_labels == result.conductor.boundary_labels


@pytest.mark.parametrize('case', ['schema1', 'schema2', 'schema3', 'missing_signal', 'extra_signal',
    'missing_face', 'extra_face', 'nonobject_face', 'missing_metal', 'extra_metal', 'bool_metal',
    'infinite_metal', 'unknown_roughness', 'missing_reference', 'extra_conductor', 'thin_reference',
    'low_face_sigma', 'zero_thickness', 'extra_top'])
def test_strict_face_input_rejects_before_any_meshing(monkeypatch, case):
    raw = document().to_dict(); c = raw['conductor']; faces = c['conductors']['positive']
    if case.startswith('schema'): raw['schema'] = 'sipi.transmission-line/'+case[-1]
    if case == 'missing_signal': del c['conductors']['positive']
    if case == 'extra_signal': c['conductors']['unknown'] = faces
    if case == 'missing_face': del faces['top']
    if case == 'extra_face': faces['side'] = faces['left']
    if case == 'nonobject_face': faces['top'] = []
    if case == 'missing_metal': del faces['top']['roughness']
    if case == 'extra_metal': faces['top']['extra'] = 1
    if case == 'bool_metal': faces['top']['conductivity'] = True
    if case == 'infinite_metal': faces['top']['conductivity'] = float('inf')
    if case == 'unknown_roughness': faces['top']['roughness']['kind'] = 'unknown'
    if case == 'missing_reference': del c['reference']
    if case == 'extra_conductor': c['extra'] = 1
    if case == 'thin_reference': c['ground_thickness'] = 1e-9
    if case == 'low_face_sigma': faces['top']['conductivity'] = 1e4
    if case == 'zero_thickness': raw['cross_section']['traces'][0]['thickness'] = 0
    if case == 'extra_top': raw['extra'] = 1
    def forbidden(*args, **kwargs): pytest.fail('invalid saved face input reached meshing')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    with pytest.raises(ValueError): TransmissionLineDocument.from_dict(raw)
    with pytest.raises(ValueError): normalize_saved(json.dumps(raw))


def test_valid_parsing_has_no_fields_and_duplicate_face_keys_reject(monkeypatch):
    doc = document(); text = doc.dumps()
    def forbidden(*args, **kwargs): pytest.fail('saved input parsing reached meshing')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    assert normalize_saved(text) == text
    duplicate = text.replace('"relative_permeability": 1.0', '"relative_permeability": 1.0, "relative_permeability": 1.0', 1)
    assert duplicate != text
    with pytest.raises(ValueError): TransmissionLineDocument.loads(duplicate)
    with pytest.raises(ValueError): normalize_saved(duplicate)
