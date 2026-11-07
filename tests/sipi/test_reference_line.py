# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict reference-surface records, shared extraction and downstream reuse."""
import json

import numpy as np
import pytest

from sipi import CrossSection, CrossSectionDocument
from sipi.boundary_conductor import SurfaceMetal
from sipi.face_conductor import ReferenceSurfaceMetals, TraceFaceMetals, surface_conductor_loss_by_face
from sipi.line_model import TransmissionLineDocument
from sipi.dielectric import DebyeDielectric, dispersive_line
from sipi.roughness import CausalHuray, GroissRMS
from sipi.network import rlgc_network
from sipi.execution import normalize_saved, execute_saved
from sipi.circuit_document import CircuitDocument
from sipi.termination import terminate_network
from sipi.length_design import LineLengthDesignDocument
from test_face_line import metal
from test_reference_surfaces import boxed_pair, FINE


def document():
    section = boxed_pair()
    cross = CrossSectionDocument(section, mesh=FINE)
    faces = {t.name: {side: metal() for side in ('bottom', 'top', 'left', 'right')}
             for t in section.traces if not t.ground}
    faces['positive']['bottom'] = metal(58e6, dict(kind='causal-huray', radii_m=[.2e-6], surface_ratios=[2.]))
    reference = dict(kind='surfaces', bottom=metal(),
        top=metal(58e6, dict(kind='hammerstad', rms_m=.5e-6)),
        sides=metal(45e6, dict(kind='groiss', rms_m=.2e-6)),
        conductors={'guardL': metal(35e6), 'guardR': metal()})
    return TransmissionLineDocument(cross, [1e9, 4e9],
        materials={'substrate': DebyeDielectric(2., [2.], [2e9])},
        conductor=dict(kind='surface-faces', conductors=faces, reference=reference, ground_thickness=35e-6),
        length=.03, z_ref=75., schema='sipi.transmission-line/5')


@pytest.fixture(scope='module')
def extracted():
    doc = document()
    return doc, doc.analyze()


def test_saved_reference_rlgc_matches_direct_separate_apis(extracted):
    doc, result = extracted; section = doc.cross_section.section; smooth = SurfaceMetal(58e6)
    faces = {t.name: TraceFaceMetals.uniform(smooth) for t in section.traces if not t.ground}
    faces['positive'] = TraceFaceMetals(SurfaceMetal(58e6, roughness=CausalHuray([.2e-6], [2.])),
                                      smooth, smooth, smooth)
    reference = ReferenceSurfaceMetals(smooth, SurfaceMetal(58e6, roughness_rms=.5e-6),
        SurfaceMetal(45e6, roughness=GroissRMS(.2e-6)), {'guardL': SurfaceMetal(35e6), 'guardR': smooth})
    loss = surface_conductor_loss_by_face(section, result.frequency, conductors=faces,
        reference=reference, ground_thickness=35e-6, **FINE)
    dielectric = dispersive_line(section, result.frequency,
        materials={'substrate': DebyeDielectric(2., [2.], [2e9])}, **FINE)
    for actual, expected in [(result.R, loss.R), (result.L, dielectric.L+loss.L_internal),
                              (result.C, dielectric.C), (result.G, dielectric.G)]:
        np.testing.assert_allclose(actual, expected, rtol=1e-10, atol=0)
    net = rlgc_network(result.frequency, R=loss.R, L=dielectric.L+loss.L_internal,
        C=dielectric.C, G=dielectric.G, length=.03, z_ref=75., names=result.names)
    np.testing.assert_allclose(result.network.s, net.s, rtol=0, atol=1e-10)
    assert result.conductor.boundary_labels[-5:] == ('reference:bottom', 'reference:top',
        'reference:sides', 'reference:ground:guardL', 'reference:ground:guardR')
    np.testing.assert_array_equal(result.network.z_ref, [75.]*4)


def test_replay_detaches_references_and_shares_one_mesh_and_c0(monkeypatch, extracted):
    import sipi.line_model as implementation
    doc, expected = extracted; raw = doc.to_dict()
    restored = TransmissionLineDocument.from_dict(raw)
    raw['conductor']['reference']['conductors']['guardL']['conductivity'] = 1.
    assert restored.dumps() == doc.dumps() == normalize_saved(doc.dumps())
    meshes = []; shared = []; oldmesh = CrossSection.mesh; olddielectric = implementation._dispersive_from_mesh
    def mesh(self, **options): meshes.append(1); return oldmesh(self, **options)
    def dielectric(*args, **kwargs): shared.append(kwargs['c0']); return olddielectric(*args, **kwargs)
    monkeypatch.setattr(CrossSection, 'mesh', mesh)
    monkeypatch.setattr(implementation, '_dispersive_from_mesh', dielectric)
    result = TransmissionLineDocument.loads(restored.dumps()).analyze()
    assert len(meshes) == len(shared) == 1 and shared[0] is result.conductor.factors.C0
    assert result.input_json == doc.dumps()
    np.testing.assert_allclose(result.network.s, expected.network.s, rtol=0, atol=1e-12)


@pytest.mark.parametrize('kind', ['perfect', 'surface', 'surface-boundaries', 'surface-faces'])
def test_version_five_preserves_all_common_reference_forms(kind):
    from test_face_line import document as old_document
    raw = old_document().to_dict()
    if kind == 'perfect': raw['conductor'] = dict(kind=kind)
    if kind == 'surface': raw['conductor'] = dict(kind=kind, conductivity=58e6, relative_permeability=1.,
        roughness=dict(kind='smooth'), ground_thickness=35e-6)
    if kind == 'surface-boundaries':
        raw['conductor'] = dict(kind=kind, reference=metal(), ground_thickness=35e-6,
            conductors={name: metal() for name in ('positive', 'negative')})
    old = TransmissionLineDocument.from_dict(raw).analyze()
    raw['schema'] = 'sipi.transmission-line/5'
    new = TransmissionLineDocument.from_dict(raw).analyze()
    for key in ('R', 'L', 'G', 'C'):
        np.testing.assert_allclose(getattr(new, key), getattr(old, key), rtol=1e-12, atol=0)
    np.testing.assert_allclose(new.network.s, old.network.s, rtol=0, atol=1e-12)


def test_execution_retains_every_reference_diagnostic(extracted):
    doc, result = extracted; loss = result.conductor
    report = execute_saved(doc.dumps(), diagnostics=['characteristic'])
    assert report['status'] == 'complete' and report['input'] == doc.to_dict()
    b = report['result']['conductor_boundaries']
    assert b['labels'] == list(loss.boundary_labels)
    for key, values in [('skin_depth_m', loss.skin_depth), ('roughness_factor', loss.roughness_factor),
        ('resistance_ohm_per_m', loss.resistance_parts), ('surface_current_factors_per_m', loss.factors.parts),
        ('current_integrals', loss.factors.current_integrals),
        ('whole_boundary_current_integrals', loss.factors.base.current_integrals)]:
        np.testing.assert_allclose(b[key], values, rtol=1e-12)
    np.testing.assert_allclose(np.array(b['surface_impedance_ohms']['real'])+1j*np.array(b['surface_impedance_ohms']['imag']),
                               loss.surface_impedance, rtol=1e-12)
    assert b['current_flux_error'] == pytest.approx(loss.factors.current_error, rel=1e-12)
    json.dumps(report, allow_nan=False)


def test_existing_circuit_keeps_reference_surface_extraction(extracted):
    doc, result = extracted; name = result.network.port_names[0]
    circuit = CircuitDocument(dict(kind='transmission-line', document=doc.to_dict()),
        excitation=dict(kind='sources', voltages={name: 1}), terminations={})
    actual = circuit.analyze()
    expected = terminate_network(result.network, source_voltages={name: 1}, terminations={})
    np.testing.assert_allclose(actual.response.voltage, expected.voltage, rtol=0, atol=1e-10)
    assert actual.extraction.conductor.boundary_labels == result.conductor.boundary_labels


def test_length_design_extracts_new_reference_source_once_and_replays(monkeypatch):
    raw = document().to_dict(); raw['length_m'] = 0.
    doc = LineLengthDesignDocument(dict(kind='transmission-line', document=raw),
        bounds=[0., .3], tolerance=1e-5, max_evaluations=32, basis='mixed-mode',
        limits=[dict(name='insertion', input_port='d_near', output_port='d_far',
                     frequency_hz=[1e9, 4e9], minimum=.7, maximum=None)], schema='sipi.line-length-design/2')
    calls = []; original = TransmissionLineDocument.analyze
    def counted(self): calls.append(1); return original(self)
    monkeypatch.setattr(TransmissionLineDocument, 'analyze', counted)
    result = doc.solve()
    assert len(calls) == 1
    assert result.extraction.conductor.boundary_labels[-1] == 'reference:ground:guardR'
    assert result.feasible.passed and not result.infeasible.passed
    ledger = result.to_dict()['source_evaluation']
    assert ledger['field_extractions'] == 1 and ledger['evaluations'] == 1+len(result.history)
    old = LineLengthDesignDocument(ledger['resolved_network'], bounds=[0., .3], tolerance=1e-5,
        max_evaluations=31, basis='mixed-mode', limits=doc.to_dict()['limits']).solve()
    assert old.history == result.history


@pytest.mark.parametrize('case', ['schema1', 'schema2', 'schema3', 'schema4', 'schema6',
    'boundary_kind', 'missing_kind', 'unknown_kind', 'extra_reference', 'missing_plane', 'null_plane',
    'open_plane', 'missing_ground', 'extra_ground', 'null_ground', 'wrong_map', 'missing_roughness',
    'unknown_roughness', 'extra_metal', 'boolean_sigma', 'infinite_sigma', 'plane_depth', 'trace_depth'])
def test_strict_reference_records_reject_before_meshing(monkeypatch, case):
    raw = document().to_dict(); c = raw['conductor']; ref = c['reference']
    if case.startswith('schema'): raw['schema'] = 'sipi.transmission-line/'+case[-1]
    if case == 'boundary_kind':
        c['kind'] = 'surface-boundaries'; c['conductors'] = {name: metal() for name in c['conductors']}
    if case == 'missing_kind': del ref['kind']
    if case == 'unknown_kind': ref['kind'] = 'future'
    if case == 'extra_reference': ref['extra'] = 1
    if case == 'missing_plane': del ref['top']
    if case == 'null_plane': ref['top'] = None
    if case == 'open_plane': raw['cross_section']['box']['top'] = 'open'
    if case == 'missing_ground': del ref['conductors']['guardL']
    if case == 'extra_ground': ref['conductors']['unknown'] = metal()
    if case == 'null_ground': ref['conductors']['guardL'] = None
    if case == 'wrong_map': ref['conductors'] = []
    if case == 'missing_roughness': del ref['top']['roughness']
    if case == 'unknown_roughness': ref['top']['roughness']['kind'] = 'unknown'
    if case == 'extra_metal': ref['top']['extra'] = 1
    if case == 'boolean_sigma': ref['bottom']['conductivity'] = True
    if case == 'infinite_sigma': ref['bottom']['conductivity'] = float('inf')
    if case == 'plane_depth': ref['top']['conductivity'] = 1e4
    if case == 'trace_depth': ref['conductors']['guardL']['conductivity'] = 1e4
    def forbidden(*args, **kwargs): pytest.fail('invalid reference input reached meshing')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    with pytest.raises(ValueError): TransmissionLineDocument.from_dict(raw)
    with pytest.raises(ValueError): normalize_saved(json.dumps(raw))


def test_valid_normalization_and_duplicate_reference_keys_have_no_fields(monkeypatch):
    doc = document(); raw = doc.dumps()
    def forbidden(*args, **kwargs): pytest.fail('normalization reached meshing')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    assert normalize_saved(raw) == raw
    bad = raw.replace('"kind": "surfaces"', '"kind": "surfaces", "kind": "surfaces"', 1)
    assert bad != raw
    with pytest.raises(ValueError): TransmissionLineDocument.loads(bad)
    with pytest.raises(ValueError): normalize_saved(bad)
