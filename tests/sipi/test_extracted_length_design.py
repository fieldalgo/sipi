# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""One field extraction, sampled length boundaries and a complete job ledger."""
from importlib import metadata
import json

import numpy as np
import pytest
from scipy.optimize import brentq

from sipi import CrossSection, CrossSectionDocument, stripline
from sipi.line_model import TransmissionLineDocument
from sipi.volume_line import VolumeLineDocument
from sipi.length_design import LineLengthDesignDocument, LengthGoalError
from sipi.execution import execute_saved, normalize_saved
from crosscheck import require_tool, Stopwatch, emit, make_record, observable


def field_source(kind='transmission-line'):
    if kind == 'volume-line':
        from test_execution import line
        raw = line(True).to_dict(); raw['length_m'] = 0.
    else:
        cross = CrossSectionDocument(stripline(width=.5e-3, plane_spacing=1e-3,
            thickness=35e-6, eps_r=4., tan_delta=.02, box_width=4e-3),
            mesh=dict(edge_size=2.5e-6, far_size=.1e-3, grade=.05))
        def metal(rms=0): return dict(conductivity=58e6, relative_permeability=1.,
                                    roughness=dict(kind='hammerstad', rms_m=rms))
        raw = TransmissionLineDocument(cross, [1e9, 2e9], materials={}, length=0., z_ref=75.,
            conductor=dict(kind='surface-faces', ground_thickness=35e-6, reference=metal(),
                conductors={'signal': dict(bottom=metal(.5e-6), top=metal(), left=metal(), right=metal())}),
            schema='sipi.transmission-line/4').to_dict()
    return dict(kind=kind, document=raw)


def document(kind='transmission-line', **changes):
    source = field_source(kind); frequency = source['document']['frequency_hz']
    options = dict(network=source, bounds=[0., 500. if kind == 'volume-line' else 2.],
        limits=[dict(name='insertion', input_port='near:signal', output_port='far:signal',
                     frequency_hz=[frequency[0], frequency[-1]], minimum=.7, maximum=None)],
        tolerance=1e-3 if kind == 'volume-line' else 1e-5, max_evaluations=32,
        schema='sipi.line-length-design/2')
    options.update(changes)
    return LineLengthDesignDocument(**options)


@pytest.fixture(scope='module')
def surface():
    doc = document()
    return doc, doc.solve()


def test_surface_face_extraction_is_once_per_request_and_matches_resolved_replay(monkeypatch, surface):
    doc, expected = surface; calls = []; original = TransmissionLineDocument.analyze
    def counted(self): calls.append(self.dumps()); return original(self)
    monkeypatch.setattr(TransmissionLineDocument, 'analyze', counted)
    raw = doc.to_dict(); restored = LineLengthDesignDocument.from_dict(raw)
    raw['network']['document']['conductor']['reference']['conductivity'] = 1.
    assert restored.dumps() == doc.dumps() == normalize_saved(doc.dumps())
    result = restored.solve()
    assert len(calls) == 1 and result.extraction is not None
    record = result.to_dict()['source_evaluation']
    assert record['evaluations'] == len(result.history)+1 <= 32
    assert record['field_extractions'] == 1 and record['length_evaluations'] == len(result.history)
    assert len(result.extraction.conductor.boundary_labels) == 5
    resolved = record['resolved_network']
    assert resolved['reference_ohms'] == 75.
    for key in ('R', 'L', 'G', 'C'):
        np.testing.assert_array_equal(resolved[key], getattr(result.extraction, key))
    direct = LineLengthDesignDocument(resolved, limits=doc.to_dict()['limits'], bounds=[0, 2],
                                     tolerance=1e-5, max_evaluations=31).solve()
    assert result.history == direct.history == expected.history
    assert result.feasible.to_dict() == direct.feasible.to_dict()
    assert result.infeasible.to_dict() == direct.infeasible.to_dict()
    assert 'source_evaluation' not in direct.to_dict()
    assert result.input_json == doc.dumps()
    exported = result.to_dict(); exported['source_evaluation']['resolved_network']['R'][0][0][0] = -1
    assert result.to_dict()['source_evaluation']['resolved_network']['R'][0][0][0] > 0


def test_skrf_confirms_extracted_scalar_boundary_and_length_tolerance(surface):
    skrf = require_tool('scikit-rf'); clock = Stopwatch(); doc, result = surface
    extracted = result.extraction; f = extracted.frequency
    with clock('reference'):
        medium = skrf.media.DistributedCircuit(frequency=skrf.Frequency.from_f(f, unit='hz'),
            R=extracted.R[:, 0, 0], L=extracted.L[:, 0, 0],
            G=extracted.G[:, 0, 0], C=extracted.C[:, 0, 0], z0_port=75.)
        def margin(length): return float(np.min(abs(medium.line(length, unit='m').s[:, 1, 0]))-.7)
        root = brentq(margin, result.feasible_length_m, result.infeasible_length_m, xtol=1e-12)
        differences = [float(np.max(abs(assessment.network.s-medium.line(length, unit='m').s)))
            for length, assessment in [(result.feasible_length_m, result.feasible),
                                       (result.infeasible_length_m, result.infeasible)]]
    with clock('openphysics'):
        # Replay the already extracted matrices; this timing does not include meshing.
        raw = json.loads(result.resolved_network_json)
        replay = LineLengthDesignDocument(raw, limits=doc.to_dict()['limits'], bounds=[0, 2],
            tolerance=1e-5, max_evaluations=31).solve()
    assert result.feasible_length_m <= root <= result.infeasible_length_m
    assert root-result.feasible_length_m <= 1e-5
    assert replay.history == result.history
    record = make_record(case='field-extracted-length-boundary', physics='uniform lossy line, frozen extracted RLGC',
        api='sipi.length_design.LineLengthDesignDocument', discretization='one face/dielectric extraction then bracket bisection',
        tool='scikit-rf', tool_discretization='DistributedCircuit endpoints and independent local scalar root',
        matched=['same extracted RLGC, full frequency grid, reference, ports and endpoint lengths'],
        not_matched=['this network comparison does not independently validate field extraction',
                     'no continuous-band or global maximum claim; replay timing excludes fields'],
        observables=[observable('S', '1', 'maximum endpoint absolute difference', max(differences), 1e-10)],
        analytical_acceptance='legacy distortionless closed form; independent endpoint/root and counted extraction/budget tests',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi', version=metadata.version('sipi')); emit(record)
    assert max(differences) < 1e-10


def test_volume_source_actual_extraction_replays_its_sampled_matrices(monkeypatch):
    doc = document('volume-line'); original = VolumeLineDocument.analyze; calls = []
    def counted(self): calls.append(1); return original(self)
    monkeypatch.setattr(VolumeLineDocument, 'analyze', counted)
    result = doc.solve()
    assert len(calls) == 1
    assert result.feasible.passed and not result.infeasible.passed
    assert result.infeasible_length_m-result.feasible_length_m <= 1e-3
    record = result.to_dict()['source_evaluation']; resolved = record['resolved_network']
    assert record['field_extractions'] == 1 and record['evaluations'] == len(result.history)+1
    for key in ('R', 'L', 'G', 'C'):
        np.testing.assert_array_equal(resolved[key], getattr(result.extraction, key))
    old = LineLengthDesignDocument(resolved, limits=doc.to_dict()['limits'], bounds=[0, 500],
                                  tolerance=1e-3, max_evaluations=31).solve()
    assert old.history == result.history


def test_coupled_face_source_keeps_mixed_mode_port_and_reference_contract():
    from test_face_line import document as face_document
    raw = face_document().to_dict(); raw['length_m'] = 0.
    doc = LineLengthDesignDocument(dict(kind='transmission-line', document=raw),
        limits=[dict(name='differential insertion', input_port='d_near', output_port='d_far',
                     frequency_hz=[1e9, 4e9], minimum=.7, maximum=None)],
        bounds=[0., .1], tolerance=1e-5, max_evaluations=32,
        basis='mixed-mode', schema='sipi.line-length-design/2')
    result = doc.solve()
    assert result.feasible.network.basis == 'mixed-mode'
    assert result.feasible.network.port_names == ('d_near', 'd_far', 'c_near', 'c_far')
    assert result.feasible.passed and not result.infeasible.passed
    assert result.to_dict()['source_evaluation']['resolved_network']['names'] == ['positive', 'negative']


def test_extraction_failure_keeps_phase_and_attempt_without_fabricated_rlgc(monkeypatch):
    doc = document()
    def failed(self): raise ValueError('retained field/mesh rejection')
    monkeypatch.setattr(TransmissionLineDocument, 'analyze', failed)
    report = execute_saved(doc.dumps())
    error = report['error']; record = error['source_evaluation']
    assert report['status'] == 'failed' and report['result'] is None
    assert error['history'] == [] and error['failed_length_m'] is None and error['cause_type'] == 'ValueError'
    assert 'retained field/mesh rejection' in error['message']
    assert record == dict(phase='extraction', field_extractions=1, length_evaluations=0,
                          evaluations=1, resolved_network=None)


def test_candidate_failure_is_counted_and_retains_resolved_input_and_prior_history(monkeypatch, surface):
    import sipi.length_design as implementation
    doc, known = surface
    monkeypatch.setattr(TransmissionLineDocument, 'analyze', lambda self: known.extraction)
    original = implementation._network_input
    def failed(raw):
        if raw.get('kind') == 'rlgc' and raw['length_m'] not in (0., 2.):
            raise ArithmeticError('retained candidate failure')
        return original(raw)
    monkeypatch.setattr(implementation, '_network_input', failed)
    report = execute_saved(doc.dumps()); error = report['error']; record = error['source_evaluation']
    assert report['status'] == 'failed' and error['cause_type'] == 'ArithmeticError'
    assert len(error['history']) == 2 and error['failed_length_m'] == 1.
    assert record['phase'] == 'network' and record['field_extractions'] == 1
    assert record['length_evaluations'] == 3 and record['evaluations'] == 4
    assert record['resolved_network'] == json.loads(known.resolved_network_json)


def test_saved_budget_counts_extraction_and_rejects_caller_overrun_before_fields(monkeypatch, surface):
    doc, known = surface; calls = []
    def counted(self): calls.append(1); return known.extraction
    monkeypatch.setattr(TransmissionLineDocument, 'analyze', counted)
    with pytest.raises(ValueError, match='budget'): execute_saved(doc.dumps(), max_evaluations=31)
    assert calls == []
    small = document(max_evaluations=3)
    report = execute_saved(small.dumps(), max_evaluations=3)
    assert len(calls) == 1 and report['status'] == 'failed'
    record = report['error']['source_evaluation']
    assert record['phase'] == 'budget' and record['evaluations'] == 3
    assert record['field_extractions'] == 1 and record['length_evaluations'] == 2
    assert len(report['error']['history']) == 2
    with pytest.raises(ValueError): document(max_evaluations=2)


@pytest.mark.parametrize('case', ['frequency', 'ports', 'reference'])
def test_changed_extraction_contract_is_rejected(monkeypatch, surface, case):
    from types import SimpleNamespace
    doc, known = surface
    original = known.extraction
    frequency = np.array([1., 2.]) if case == 'frequency' else original.frequency
    network = SimpleNamespace(port_names=('wrong', 'ports') if case == 'ports' else original.network.port_names,
        z_ref=np.array([50., 75.]) if case == 'reference' else original.network.z_ref)
    wrong = SimpleNamespace(frequency=frequency, network=network)
    monkeypatch.setattr(TransmissionLineDocument, 'analyze', lambda self: wrong)
    with pytest.raises(LengthGoalError, match='extraction failed') as caught: doc.solve()
    assert caught.value.source_evaluation['phase'] == 'extraction'
    assert caught.value.source_evaluation['evaluations'] == 1


@pytest.mark.parametrize('bounds', [[1., 2.], [0., 1e-6]])
def test_unaccepted_field_bracket_keeps_resolved_model_and_both_endpoints(monkeypatch, surface, bounds):
    _, known = surface
    monkeypatch.setattr(TransmissionLineDocument, 'analyze', lambda self: known.extraction)
    report = execute_saved(document(bounds=bounds).dumps())
    assert report['status'] == 'failed'
    error = report['error']; record = error['source_evaluation']
    assert record['phase'] == 'bracket' and record['evaluations'] == 3
    assert len(error['history']) == 2 and record['resolved_network'] is not None


@pytest.mark.parametrize('case', ['old_schema', 'future_schema', 'rlgc', 'other_source',
    'nonzero_length', 'extra_top', 'extra_source', 'extra_document', 'bad_metal', 'bad_budget'])
def test_strict_field_source_normalization_before_any_solve(monkeypatch, case):
    raw = document().to_dict()
    if case == 'old_schema': raw['schema'] = 'sipi.line-length-design/1'
    if case == 'future_schema': raw['schema'] = 'sipi.line-length-design/3'
    if case == 'rlgc':
        from test_length_design import source
        raw['network'] = source()
    if case == 'other_source': raw['network']['kind'] = 'network-transform'
    if case == 'nonzero_length': raw['network']['document']['length_m'] = .03
    if case == 'extra_top': raw['extra'] = 1
    if case == 'extra_source': raw['network']['extra'] = 1
    if case == 'extra_document': raw['network']['document']['extra'] = 1
    if case == 'bad_metal': raw['network']['document']['conductor']['reference']['conductivity'] = True
    if case == 'bad_budget': raw['max_evaluations'] = 2
    def forbidden(*args, **kwargs): pytest.fail('parsing/invalid input reached field solve')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    assert normalize_saved(document().dumps()) == document().dumps()
    with pytest.raises(ValueError): LineLengthDesignDocument.from_dict(raw)
    with pytest.raises(ValueError): normalize_saved(json.dumps(raw))


def test_saved_execution_keeps_original_source_and_finite_resolved_values(surface, monkeypatch):
    doc, result = surface
    monkeypatch.setattr(TransmissionLineDocument, 'analyze', lambda self: result.extraction)
    report = execute_saved(doc.dumps(), max_evaluations=32)
    assert report['status'] == 'complete' and report['result'] == result.to_dict()
    assert report['input'] == doc.to_dict()
    json.dumps(report, allow_nan=False)
