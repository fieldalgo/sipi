# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict layered-material storage with shared field, circuit and diagnostic replay."""
import copy
import json

import numpy as np
import pytest

from sipi import CrossSection, CrossSectionDocument, MetalLayer, microstrip
from sipi.boundary_conductor import LayeredSurfaceMetal, SurfaceMetal, surface_conductor_loss_by_boundary
from sipi.face_conductor import TraceFaceMetals, ReferenceSurfaceMetals, surface_conductor_loss_by_face
from sipi.line_model import TransmissionLineDocument
from sipi.execution import execute_saved, normalize_saved
from sipi.circuit_document import CircuitDocument
from sipi.termination import terminate_network
from sipi.length_design import LineLengthDesignDocument
from test_layered_metal import transfer

F = [1e9, 4e9]
MESH = dict(edge_size=5e-6, far_size=.2e-3, grade=.1)
FACES = ('bottom', 'top', 'left', 'right')


def layers(index=0):
    return (MetalLayer((index+1)*.05e-6, 14e6, 3.), MetalLayer(1e-6, 40e6))


def record(index=0):
    return dict(kind='layered', conductivity=58e6, relative_permeability=1.,
        coatings=[dict(thickness_m=x.thickness_m, conductivity=x.conductivity,
                       relative_permeability=x.relative_permeability) for x in layers(index)])


def smooth(): return dict(conductivity=58e6, relative_permeability=1., roughness=dict(kind='smooth'))


def document():
    section = microstrip(width=.5e-3, substrate_height=1e-3, thickness=50e-6,
                         eps_r=4., box_width=6e-3, air_height=3e-3)
    return TransmissionLineDocument(CrossSectionDocument(section, mesh=MESH), F,
        conductor=dict(kind='surface-boundaries', conductors={section.traces[0].name: record()},
                       reference=record(1), ground_thickness=35e-6),
        materials={}, length=.03, schema='sipi.transmission-line/7')


def test_normalization_copies_and_keeps_layer_order_without_field_work(monkeypatch):
    monkeypatch.setattr(CrossSection, 'mesh', lambda *a, **k: pytest.fail('normalization meshed'))
    doc = document(); raw = doc.to_dict(); restored = TransmissionLineDocument.from_dict(raw)
    raw['conductor']['reference']['coatings'][0]['conductivity'] = -1
    assert restored.dumps() == doc.dumps() == normalize_saved(doc.dumps())
    assert TransmissionLineDocument.loads(doc.dumps()).dumps() == doc.dumps()
    assert restored.to_dict()['conductor']['reference']['coatings'][0]['conductivity'] == 14e6


@pytest.fixture(scope='module')
def extracted():
    doc = document()
    return doc, doc.analyze()


def test_saved_direct_rlgc_and_one_mesh_one_current_field(monkeypatch, extracted):
    import sipi.line_model as implementation
    import sipi.boundary_conductor as boundary
    doc, expected = extracted; section = doc.cross_section.section; calls = []
    original_mesh, original_current = CrossSection.mesh, boundary.surface_current_factors
    def mesh(self, **kw): calls.append('mesh'); return original_mesh(self, **kw)
    def current(*a, **kw): calls.append('current'); return original_current(*a, **kw)
    monkeypatch.setattr(CrossSection, 'mesh', mesh)
    monkeypatch.setattr(boundary, 'surface_current_factors', current)
    replay = TransmissionLineDocument.loads(doc.dumps()).analyze()
    assert calls == ['mesh', 'current']
    for key in ('R', 'L', 'C', 'G'): np.testing.assert_array_equal(getattr(replay, key), getattr(expected, key))
    direct = surface_conductor_loss_by_boundary(section, F,
        conductors={section.traces[0].name: LayeredSurfaceMetal(58e6, coatings=layers())},
        reference=LayeredSurfaceMetal(58e6, coatings=layers(1)), ground_thickness=35e-6, **MESH)
    dielectric = section.analyze(**MESH)
    np.testing.assert_allclose(expected.R, direct.R, rtol=1e-10)
    np.testing.assert_allclose(expected.L, dielectric.L+direct.L_internal, rtol=1e-10)
    np.testing.assert_allclose(expected.C, np.broadcast_to(dielectric.C, expected.C.shape), rtol=1e-10)
    np.testing.assert_allclose(expected.G, 0, rtol=0, atol=0)


def test_all_signal_reference_and_ground_face_positions_keep_distinct_layers():
    from test_ground_faces import boxed_pair
    s = boxed_pair(); names = [t.name for t in s.traces if not t.ground]
    signals = {name: {face: record(4*i+j) for j, face in enumerate(FACES)} for i, name in enumerate(names)}
    reference = dict(kind='surfaces', bottom=record(8), top=record(9), sides=record(10),
        conductors={'guardL': dict(kind='faces', **{face: record(11+j) for j, face in enumerate(FACES)}),
                    'guardR': record(15)})
    doc = TransmissionLineDocument(CrossSectionDocument(s, mesh=MESH), F, materials={},
        conductor=dict(kind='surface-faces', conductors=signals, reference=reference, ground_thickness=35e-6),
        length=.03, schema='sipi.transmission-line/7')
    result = TransmissionLineDocument.loads(doc.dumps()).analyze()
    metal = lambda i: LayeredSurfaceMetal(58e6, coatings=layers(i))
    direct = surface_conductor_loss_by_face(s, F,
        conductors={name: TraceFaceMetals(**{face: metal(4*i+j) for j, face in enumerate(FACES)})
                    for i, name in enumerate(names)},
        reference=ReferenceSurfaceMetals(metal(8), metal(9), metal(10),
            {'guardL': TraceFaceMetals(**{face: metal(11+j) for j, face in enumerate(FACES)}), 'guardR': metal(15)}),
        ground_thickness=35e-6, **MESH)
    np.testing.assert_allclose(result.R, direct.R, rtol=1e-10)
    np.testing.assert_allclose(result.conductor.L_internal, direct.L_internal, rtol=1e-10)
    for i in range(16):
        independent = np.array([transfer(f, layers=layers(i)) for f in F])
        np.testing.assert_allclose(result.conductor.surface_impedance[:, i], independent, rtol=1e-10)


def test_common_execution_and_circuit_retain_input_and_complex_impedance(extracted):
    doc, result = extracted
    output = execute_saved(doc.dumps(), diagnostics=['characteristic'])
    assert output['status'] == 'complete' and output['input'] == doc.to_dict()
    b = output['result']['conductor_boundaries']
    z = np.array(b['surface_impedance_ohms']['real'])+1j*np.array(b['surface_impedance_ohms']['imag'])
    np.testing.assert_array_equal(z, result.conductor.surface_impedance)
    name = result.network.port_names[0]
    circuit = CircuitDocument(dict(kind='transmission-line', document=doc.to_dict()),
        excitation=dict(kind='sources', voltages={name: 1}), terminations={})
    actual = circuit.analyze()
    expected = terminate_network(result.network, source_voltages={name: 1}, terminations={})
    np.testing.assert_allclose(actual.response.voltage, expected.voltage, rtol=0, atol=1e-10)
    assert actual.extraction.input_json == doc.dumps()
    json.dumps(output, allow_nan=False)


def test_empty_layers_keep_old_version_six_values(extracted):
    raw = document().to_dict(); name = next(iter(raw['conductor']['conductors']))
    for metal in (raw['conductor']['conductors'][name], raw['conductor']['reference']): metal['coatings'] = []
    new = TransmissionLineDocument.from_dict(raw).analyze()
    raw['schema'] = 'sipi.transmission-line/6'
    raw['conductor']['conductors'][name] = smooth(); raw['conductor']['reference'] = smooth()
    old = TransmissionLineDocument.from_dict(raw).analyze()
    for key in ('R', 'L', 'C', 'G'): np.testing.assert_array_equal(getattr(new, key), getattr(old, key))
    np.testing.assert_array_equal(new.network.s, old.network.s)


@pytest.mark.parametrize('version', range(1, 7))
def test_old_versions_reject_layered_record(version):
    raw = document().to_dict(); raw['schema'] = f'sipi.transmission-line/{version}'
    with pytest.raises(ValueError): TransmissionLineDocument.from_dict(raw)


@pytest.mark.parametrize('change', [dict(coatings=None), dict(coatings={}), dict(coatings=[{}]),
    dict(coatings=[dict(thickness_m=1e-6, conductivity=58e6, relative_permeability=1., extra=1)]),
    dict(coatings=[dict(thickness_m=30e-6, conductivity=58e6, relative_permeability=1.)]),
    dict(coatings=record()['coatings']*17), dict(roughness=dict(kind='smooth')),
    dict(conductivity=True), dict(relative_permeability=1j), dict(kind='unknown')],
    ids=['null', 'mapping', 'missing-layer-fields', 'extra-layer-field', 'core', 'count', 'roughness', 'bool', 'complex', 'kind'])
def test_strict_material_and_core_preflight_before_meshing(monkeypatch, change):
    raw = document().to_dict(); raw['conductor']['reference'].update(change)
    monkeypatch.setattr(CrossSection, 'mesh', lambda *a, **k: pytest.fail('bad material reached mesh'))
    with pytest.raises((ValueError, TypeError)): TransmissionLineDocument.from_dict(raw)


@pytest.mark.parametrize('key', ['kind', 'conductivity', 'relative_permeability', 'coatings'])
def test_each_material_field_required(key):
    raw = document().to_dict(); raw['conductor']['reference'].pop(key)
    with pytest.raises(ValueError): TransmissionLineDocument.from_dict(raw)


def test_nested_duplicate_and_nonfinite_json_rejected():
    text = document().dumps()
    for replacement in ('"thickness_m": NaN, "extra":', '"thickness_m": 0, "thickness_m":'):
        with pytest.raises(ValueError): TransmissionLineDocument.loads(text.replace('"thickness_m":', replacement, 1))


def test_length_design_extracts_layered_line_once(monkeypatch, extracted):
    raw = document().to_dict(); raw['length_m'] = 0
    ports = extracted[1].network.port_names
    doc = LineLengthDesignDocument(dict(kind='transmission-line', document=raw),
        bounds=[0., 3.], tolerance=1e-5, max_evaluations=32, basis='single-ended',
        limits=[dict(name='insertion', input_port=ports[0], output_port=ports[1],
                     frequency_hz=F, minimum=.99, maximum=None)], schema='sipi.line-length-design/2')
    calls = []; original = TransmissionLineDocument.analyze
    def analyze(self): calls.append(1); return original(self)
    monkeypatch.setattr(TransmissionLineDocument, 'analyze', analyze)
    result = doc.solve()
    assert calls == [1] and result.feasible.passed and not result.infeasible.passed
    assert result.extraction.input_json == TransmissionLineDocument.from_dict(raw).dumps()


def test_saved_network_matches_separate_layered_field_inputs(extracted):
    doc, actual = extracted; section = doc.cross_section.section
    loss = surface_conductor_loss_by_boundary(section, F,
        conductors={section.traces[0].name: LayeredSurfaceMetal(58e6, coatings=layers())},
        reference=LayeredSurfaceMetal(58e6, coatings=layers(1)), ground_thickness=35e-6, **MESH)
    dielectric = section.analyze(**MESH)
    expected = loss.network(C=dielectric.C, G=np.zeros((1, 1)), length=.03)
    np.testing.assert_allclose(actual.network.s, expected.s, rtol=0, atol=1e-10)
    assert np.max(np.linalg.svd(actual.network.s, compute_uv=False)) <= 1+1e-10


@pytest.mark.parametrize('faces', [False, True])
def test_version_seven_preserves_uncoated_reference_inputs(faces, monkeypatch):
    from test_reference_line import document as planes
    from test_ground_face_line import document as grounds
    monkeypatch.setattr(CrossSection, 'mesh', lambda *a, **k: pytest.fail('normalization meshed'))
    old = (grounds if faces else planes)().to_dict()
    promoted = copy.deepcopy(old); promoted['schema'] = 'sipi.transmission-line/7'
    assert TransmissionLineDocument.from_dict(promoted).to_dict() == promoted
    promoted['schema'] = old['schema']
    assert promoted == old
