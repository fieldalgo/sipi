# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict ground-face JSON, shared extraction, diagnostics and downstream replay."""
from importlib import metadata
import json

import numpy as np
import pytest

from sipi import CrossSection, CrossSectionDocument, PolygonTrace, coplanar_stripline
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
from test_reference_line import document as reference_document
from test_reference_surfaces import FINE
from crosscheck import require_tool, Stopwatch, emit, make_record, observable

FACES = ('bottom', 'top', 'left', 'right')


def document():
    raw = reference_document().to_dict(); raw['schema'] = 'sipi.transmission-line/6'
    raw['conductor']['reference']['conductors']['guardL'] = dict(kind='faces',
        bottom=metal(), top=metal(58e6/4), left=metal(45e6, dict(kind='hammerstad', rms_m=.5e-6)),
        right=metal(58e6, dict(kind='causal-huray', radii_m=[.5e-6], surface_ratios=[1.2])))
    return TransmissionLineDocument.from_dict(raw)


@pytest.fixture(scope='module')
def extracted():
    doc = document()
    return doc, doc.analyze()


def test_saved_rlgc_and_network_match_separate_python_apis(extracted):
    doc, result = extracted; section = doc.cross_section.section; smooth = SurfaceMetal(58e6)
    faces = {t.name: TraceFaceMetals.uniform(smooth) for t in section.traces if not t.ground}
    faces['positive'] = TraceFaceMetals(SurfaceMetal(58e6, roughness=CausalHuray([.2e-6], [2.])),
                                      smooth, smooth, smooth)
    ground = TraceFaceMetals(smooth, SurfaceMetal(58e6/4), SurfaceMetal(45e6, roughness_rms=.5e-6),
                             SurfaceMetal(58e6, roughness=CausalHuray([.5e-6], [1.2])))
    reference = ReferenceSurfaceMetals(smooth, SurfaceMetal(58e6, roughness_rms=.5e-6),
        SurfaceMetal(45e6, roughness=GroissRMS(.2e-6)), {'guardL': ground, 'guardR': smooth})
    loss = surface_conductor_loss_by_face(section, result.frequency, conductors=faces,
        reference=reference, ground_thickness=35e-6, **FINE)
    dielectric = dispersive_line(section, result.frequency,
        materials={'substrate': DebyeDielectric(2., [2.], [2e9])}, **FINE)
    for actual, expected in [(result.R, loss.R), (result.L, dielectric.L+loss.L_internal),
                              (result.C, dielectric.C), (result.G, dielectric.G)]:
        np.testing.assert_allclose(actual, expected, rtol=1e-10, atol=0)
    expected = rlgc_network(result.frequency, R=loss.R, L=dielectric.L+loss.L_internal,
        C=dielectric.C, G=dielectric.G, length=.03, z_ref=75., names=result.names)
    np.testing.assert_allclose(result.network.s, expected.s, rtol=0, atol=1e-10)
    assert result.conductor.boundary_labels[-5:] == tuple('reference:ground:guardL:'+face for face in FACES)+('reference:ground:guardR',)
    np.testing.assert_array_equal(result.network.z_ref, [75.]*4)


def test_normalization_is_detached_and_has_no_field_work(monkeypatch):
    def forbidden(*args, **kwargs): pytest.fail('saved normalization reached field work')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    doc = document(); raw = doc.to_dict(); restored = TransmissionLineDocument.from_dict(raw)
    raw['conductor']['reference']['conductors']['guardL']['top']['conductivity'] = 1.
    assert restored.dumps() == doc.dumps() == normalize_saved(doc.dumps())
    assert TransmissionLineDocument.loads(doc.dumps()).dumps() == doc.dumps()
    assert doc.to_dict()['schema'] == 'sipi.transmission-line/6'


def test_analysis_shares_one_mesh_vacuum_extraction_and_c0(monkeypatch, extracted):
    import sipi.line_model as implementation
    import sipi.face_conductor as face_implementation
    doc, expected = extracted; meshes = []; currents = []; shared = []
    oldmesh = CrossSection.mesh; oldcurrent = face_implementation._surface_current_data
    olddielectric = implementation._dispersive_from_mesh
    def mesh(self, **options): meshes.append(1); return oldmesh(self, **options)
    def current(*args): currents.append(1); return oldcurrent(*args)
    def dielectric(*args, **kwargs): shared.append(kwargs['c0']); return olddielectric(*args, **kwargs)
    monkeypatch.setattr(CrossSection, 'mesh', mesh)
    monkeypatch.setattr(face_implementation, '_surface_current_data', current)
    monkeypatch.setattr(implementation, '_dispersive_from_mesh', dielectric)
    result = TransmissionLineDocument.loads(doc.dumps()).analyze()
    assert len(meshes) == len(currents) == len(shared) == 1
    assert shared[0] is result.conductor.factors.C0 and result.input_json == doc.dumps()
    np.testing.assert_allclose(result.network.s, expected.network.s, rtol=0, atol=1e-12)


@pytest.mark.parametrize('kind', ['perfect', 'surface', 'surface-boundaries', 'surface-faces'])
def test_all_existing_conductor_forms_keep_normalized_records_in_version_six(monkeypatch, kind):
    from test_face_line import document as old_document
    raw = old_document().to_dict()
    if kind == 'perfect': raw['conductor'] = dict(kind=kind)
    if kind == 'surface': raw['conductor'] = dict(kind=kind, conductivity=58e6, relative_permeability=1.,
        roughness=dict(kind='smooth'), ground_thickness=35e-6)
    if kind == 'surface-boundaries':
        raw['conductor'] = dict(kind=kind, reference=metal(), ground_thickness=35e-6,
            conductors={name: metal() for name in ('positive', 'negative')})
    def forbidden(*args, **kwargs): pytest.fail('input compatibility check reached meshing')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    old = TransmissionLineDocument.from_dict(raw).to_dict()
    raw['schema'] = 'sipi.transmission-line/6'
    new = TransmissionLineDocument.from_dict(raw).to_dict()
    old['schema'] = new['schema']
    assert new == old


def test_uniform_ground_faces_reduce_to_old_whole_ground_rlgc_and_s():
    old = reference_document(); raw = old.to_dict(); raw['schema'] = 'sipi.transmission-line/6'
    ground = raw['conductor']['reference']['conductors']['guardL']
    raw['conductor']['reference']['conductors']['guardL'] = dict(kind='faces', **{face: ground for face in FACES})
    a, b = old.analyze(), TransmissionLineDocument.from_dict(raw).analyze()
    for key in ('R', 'L', 'G', 'C'): np.testing.assert_allclose(getattr(a, key), getattr(b, key), rtol=1e-12, atol=0)
    np.testing.assert_allclose(a.network.s, b.network.s, rtol=0, atol=1e-12)


def test_execution_keeps_expanded_ground_face_diagnostics(extracted):
    doc, result = extracted; loss = result.conductor
    out = execute_saved(doc.dumps(), diagnostics=['characteristic'])
    assert out['status'] == 'complete' and out['input'] == doc.to_dict()
    b = out['result']['conductor_boundaries']
    assert b['labels'] == list(loss.boundary_labels)
    for key, expected in [('skin_depth_m', loss.skin_depth), ('roughness_factor', loss.roughness_factor),
        ('resistance_ohm_per_m', loss.resistance_parts), ('surface_current_factors_per_m', loss.factors.parts),
        ('current_integrals', loss.factors.current_integrals),
        ('whole_boundary_current_integrals', loss.factors.base.current_integrals)]:
        np.testing.assert_allclose(b[key], expected, rtol=1e-12)
    zs = np.array(b['surface_impedance_ohms']['real'])+1j*np.array(b['surface_impedance_ohms']['imag'])
    np.testing.assert_allclose(zs, loss.surface_impedance, rtol=1e-12)
    json.dumps(out, allow_nan=False)


def test_existing_circuit_replays_new_ground_face_source(extracted):
    doc, result = extracted; name = result.network.port_names[0]
    circuit = CircuitDocument(dict(kind='transmission-line', document=doc.to_dict()),
        excitation=dict(kind='sources', voltages={name: 1}), terminations={})
    actual = circuit.analyze()
    expected = terminate_network(result.network, source_voltages={name: 1}, terminations={})
    np.testing.assert_allclose(actual.response.voltage, expected.voltage, rtol=0, atol=1e-10)
    assert actual.extraction.conductor.boundary_labels == result.conductor.boundary_labels


def test_extracted_length_goal_replays_ground_faces_once(monkeypatch):
    raw = document().to_dict(); raw['length_m'] = 0.
    doc = LineLengthDesignDocument(dict(kind='transmission-line', document=raw),
        bounds=[0., .3], tolerance=1e-5, max_evaluations=32, basis='mixed-mode',
        limits=[dict(name='insertion', input_port='d_near', output_port='d_far',
                     frequency_hz=[1e9, 4e9], minimum=.7, maximum=None)], schema='sipi.line-length-design/2')
    assert normalize_saved(doc.dumps()) == doc.dumps()
    calls = []; original = TransmissionLineDocument.analyze
    def counted(self): calls.append(1); return original(self)
    monkeypatch.setattr(TransmissionLineDocument, 'analyze', counted)
    result = doc.solve()
    assert len(calls) == 1 and result.feasible.passed and not result.infeasible.passed
    assert 'reference:ground:guardL:top' in result.extraction.conductor.boundary_labels
    ledger = result.to_dict()['source_evaluation']
    assert ledger['field_extractions'] == 1 and ledger['evaluations'] == 1+len(result.history)
    replay = LineLengthDesignDocument(ledger['resolved_network'], bounds=[0., .3], tolerance=1e-5,
        max_evaluations=31, basis='mixed-mode', limits=doc.to_dict()['limits']).solve()
    assert replay.history == result.history


def test_skrf_confirms_scalar_network_from_saved_ground_faces():
    skrf = require_tool('scikit-rf'); clock = Stopwatch()
    section = coplanar_stripline(width=.5e-3, gap=.2e-3, ground_width=.5e-3,
        plane_spacing=1e-3, trace_height=.4e-3, thickness=50e-6, eps_r=4., box_width=4e-3)
    ref = dict(kind='surfaces', bottom=metal(), top=metal(), sides=None,
        conductors={'ground_left': dict(kind='faces', bottom=metal(), top=metal(58e6/4),
                                        left=metal(), right=metal()), 'ground_right': metal()})
    doc = TransmissionLineDocument(CrossSectionDocument(section, mesh=FINE), [1e9, 4e9],
        materials={'dielectric': DebyeDielectric(2., [2.], [2e9])}, length=.03, z_ref=75.,
        conductor=dict(kind='surface-faces', conductors={'signal': {face: metal() for face in FACES}},
                       reference=ref, ground_thickness=35e-6), schema='sipi.transmission-line/6')
    with clock('openphysics'): actual = doc.analyze()
    with clock('reference'):
        medium = skrf.media.DistributedCircuit(frequency=skrf.Frequency.from_f(actual.frequency, unit='hz'),
            R=actual.R[:, 0, 0], L=actual.L[:, 0, 0], G=actual.G[:, 0, 0], C=actual.C[:, 0, 0], z0_port=75.)
        expected = medium.line(.03, unit='m').s
    error = float(np.max(abs(actual.network.s-expected)))
    record = make_record(case='saved-ground-face-line-network', physics='uniform lossy scalar transmission line',
        api='sipi.line_model.TransmissionLineDocument', discretization='saved face-ground fields and sampled RLGC',
        tool='scikit-rf', tool_discretization='DistributedCircuit with extracted scalar RLGC',
        matched=['identical RLGC samples, length, positive real reference and near/far ports'],
        not_matched=['network comparison does not independently validate the extracted fields',
                     'reference timing excludes field extraction; no empirical foil claim'],
        observables=[observable('S', '1', 'max absolute difference', error, 1e-10)],
        analytical_acceptance='prior face-current FE/foil limits and uniform ground-law reduction; this unit checks transport',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi', version=metadata.version('sipi')); emit(record)
    assert error < 1e-10


@pytest.mark.parametrize('case', ['schema1', 'schema2', 'schema3', 'schema4', 'schema5', 'schema7',
    'missing_kind', 'unknown_kind', 'missing_bottom', 'missing_top', 'missing_left', 'missing_right',
    'extra_face', 'null_face', 'unknown_metal', 'missing_sigma', 'boolean_sigma', 'infinite_sigma',
    'bad_roughness', 'plane_faces', 'thin', 'polygon', 'collision',
    'skin_bottom', 'skin_top', 'skin_left', 'skin_right'])
def test_strict_ground_records_and_physical_guards_before_mesh(monkeypatch, case):
    raw = document().to_dict(); ref = raw['conductor']['reference']; ground = ref['conductors']['guardL']
    if case.startswith('schema'): raw['schema'] = 'sipi.transmission-line/'+case[-1]
    if case == 'missing_kind': del ground['kind']
    if case == 'unknown_kind': ground['kind'] = 'future'
    if case in ['missing_bottom', 'missing_top', 'missing_left', 'missing_right']: del ground[case[8:]]
    if case == 'extra_face': ground['front'] = metal()
    if case == 'null_face': ground['bottom'] = None
    if case == 'unknown_metal': ground['bottom']['extra'] = 1
    if case == 'missing_sigma': del ground['bottom']['conductivity']
    if case == 'boolean_sigma': ground['bottom']['conductivity'] = True
    if case == 'infinite_sigma': ground['bottom']['conductivity'] = float('inf')
    if case == 'bad_roughness': ground['bottom']['roughness'] = dict(kind='unknown')
    if case == 'plane_faces': ref['bottom'] = ground
    if case == 'thin': raw['cross_section']['traces'][2]['thickness'] = 0.
    if case == 'polygon':
        old = document().cross_section.section
        polygon = PolygonTrace('guardL', [(-2.2e-3, .5e-3), (-1.8e-3, .5e-3),
                                         (-1.8e-3, .55e-3), (-2.2e-3, .55e-3)], ground=True)
        replacement = CrossSection(old.layers, [*old.traces[:2], polygon, old.traces[3]],
                                   old.width, top='ground', sides='ground')
        raw['cross_section'] = CrossSectionDocument(replacement, mesh=FINE).to_dict()
    if case == 'collision':
        raw['cross_section']['traces'][3]['name'] = 'guardL:bottom'
        ref['conductors']['guardL:bottom'] = ref['conductors'].pop('guardR')
    if case.startswith('skin_'): ground[case[5:]]['conductivity'] = 1e4
    def forbidden(*args, **kwargs): pytest.fail('invalid saved ground face reached meshing')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    with pytest.raises(ValueError): TransmissionLineDocument.from_dict(raw)


@pytest.mark.parametrize('text', ['{"schema":"sipi.transmission-line/6","schema":"sipi.transmission-line/6"}',
                                '{"x":NaN}', '{"x":Infinity}'])
def test_duplicate_or_nonfinite_json_rejects(text):
    with pytest.raises(ValueError): TransmissionLineDocument.loads(text)
