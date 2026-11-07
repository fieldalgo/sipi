# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Full-loss sampling, independent propagation/statistics and retained failures."""
import json
import statistics
from importlib import metadata

import numpy as np
import pytest
from scipy.constants import epsilon_0, mu_0

from sipi import CrossSection, CrossSectionDocument, stripline
from sipi.dielectric import ConstantDielectric
from sipi.study import ImpedanceStudyDocument
from sipi.line_model import TransmissionLineDocument
from sipi.line_study import LineQuantityStudyDocument, _summary
from sipi.execution import execute_saved, normalize_saved, saved_schemas
from test_line_goal import MESH, install_fake
from test_line_goal_document import study as width_source, document as width_goal
from test_face_line import metal
from crosscheck import require_tool, Stopwatch, emit, make_record, observable


def document(quantity='impedance_real'):
    source = width_source().to_dict(); source['sampling']['count'] = 3
    return LineQuantityStudyDocument(source, conductor=width_goal().to_dict()['conductor'], quantity=quantity)


def material_source(sampling=None):
    return ImpedanceStudyDocument('stripline', dict(width=.5e-3, plane_spacing=1e-3,
        eps_r=1., box_width=4e-3), quantity='z0', frequency=1e9,
        materials={'dielectric': ConstantDielectric(4., .02)}, mesh=MESH,
        material_variables={'loss': dict(region='dielectric', path=['tan_delta'])},
        sampling=(dict(kind='sweep', count=3, variables=[dict(name='loss', lower=0., upper=.1)])
                  if sampling is None else sampling))


@pytest.fixture(scope='module')
def width_result():
    doc = document()
    return doc, doc.analyze()


def test_real_finite_width_sampling_matches_direct_lines_and_statistics(width_result):
    doc, result = width_result
    assert not result.failed and result.unit == 'ohm' and len(result.rows) == 3
    assert result.variable_names == ('width',)
    values = []
    for row, width in zip(result.rows, doc.samples()[:, 0]):
        line = TransmissionLineDocument(CrossSectionDocument(stripline(width=width,
            plane_spacing=1e-3, thickness=50e-6, eps_r=4., tan_delta=.02, box_width=4e-3), mesh=MESH),
            [1e9], materials={}, conductor=doc.to_dict()['conductor'], length=0.,
            schema='sipi.transmission-line/6')
        expected = line.analyze()
        assert row.input_json == line.dumps() and row.phase == 'complete'
        value = expected.propagation().z_characteristic[0, 0].real
        assert row.value == pytest.approx(value, rel=1e-10)
        for key in ('R', 'L', 'G', 'C'):
            np.testing.assert_allclose(getattr(row.result, key), getattr(expected, key), rtol=1e-10)
        values.append(row.value)
    assert result.summary['mean'] == pytest.approx(statistics.mean(values), rel=1e-12)
    assert result.summary['sample_std'] == pytest.approx(statistics.stdev(values), rel=1e-12)
    assert result.input_json == doc.dumps()


def test_material_leaf_samples_match_closed_form_including_zero_attenuation():
    source = material_source(); doc = LineQuantityStudyDocument(source,
        conductor=dict(kind='perfect'), quantity='attenuation')
    result = doc.analyze(); assert not result.failed and result.unit == 'Np/m'
    for row, loss in zip(result.rows, [0., .05, .1]):
        expected = (2j*np.pi*1e9*np.sqrt(mu_0*epsilon_0*4)*np.sqrt(1-1j*loss)).real
        assert row.value == pytest.approx(expected, rel=1e-10, abs=0)
        assert row.to_dict()['material_evaluation']['materials']['dielectric']['parameters']['tan_delta'] == loss
        assert row.sample_values == (loss,)
    assert result.rows[0].value == 0 and result.summary['minimum'] == 0
    assert source.to_dict()['material_evaluation']['materials']['dielectric']['parameters']['tan_delta'] == .02
    json.dumps(result.to_dict(), allow_nan=False)


def test_joint_corner_geometry_material_sampling_uses_exact_source_vectors():
    source = material_source(dict(kind='corners', variables=[
        dict(name='width', lower=.4e-3, upper=.6e-3), dict(name='loss', lower=.01, upper=.03)]))
    doc = LineQuantityStudyDocument(source, conductor=dict(kind='perfect'), quantity='attenuation')
    np.testing.assert_array_equal(doc.samples(), source.samples())
    result = doc.analyze(); assert not result.failed and result.variable_names == ('width', 'loss')
    for row, (width, loss), parameters, material in zip(result.rows, source.samples(),
            source.sample_parameters(), source.sample_material_evaluations()):
        expected = (2j*np.pi*1e9*np.sqrt(mu_0*epsilon_0*4)*np.sqrt(1-1j*loss)).real
        assert row.value == pytest.approx(expected, rel=1e-10)
        assert row.to_dict()['parameters'] == parameters and row.to_dict()['material_evaluation'] == material
        assert row.to_dict()['input']['cross_section']['traces'][0]['width'] == width


def test_fixed_total_height_is_retained_in_every_sample(monkeypatch):
    source = ImpedanceStudyDocument('layered_stripline', dict(width=.5e-3, lower_height=.4e-3,
        upper_height=.6e-3, lower_eps_r=3., upper_eps_r=5., thickness=50e-6, box_width=4e-3),
        quantity='z0', frequency=1e9, materials={}, mesh=MESH, fixed_plane_spacing_m=1e-3,
        sampling=dict(kind='sweep', count=3, variables=[dict(name='lower_height', lower=.3e-3, upper=.5e-3)]))
    install_fake(monkeypatch)
    result = LineQuantityStudyDocument(source, conductor=dict(kind='perfect'), quantity='impedance_real').analyze()
    assert not result.failed
    for row, values in zip(result.rows, source.sample_parameters()):
        raw = row.to_dict()
        assert raw['parameters'] == values
        assert values['lower_height']+values['upper_height'] == pytest.approx(1e-3, rel=1e-15)
        assert sum(layer['thickness'] for layer in raw['input']['cross_section']['layers']) == pytest.approx(1e-3, rel=1e-15)


def test_sampled_ground_face_laws_keep_expanded_current_and_loss_parts():
    source = ImpedanceStudyDocument('coplanar_stripline', dict(width=.5e-3, gap=.2e-3,
        ground_width=.5e-3, plane_spacing=1e-3, trace_height=.4e-3, thickness=50e-6,
        eps_r=4., tan_delta=.02, box_width=4e-3), quantity='z0', frequency=1e9, materials={},
        mesh=MESH, sampling=dict(kind='sweep', count=2, variables=[dict(name='width', lower=.5e-3, upper=.6e-3)]))
    faces = ('bottom', 'top', 'left', 'right')
    conductor = dict(kind='surface-faces', ground_thickness=35e-6,
        conductors={'signal': {face: metal() for face in faces}},
        reference=dict(kind='surfaces', bottom=metal(), top=metal(), sides=None,
            conductors={'ground_left': dict(kind='faces', bottom=metal(), top=metal(58e6/4),
                left=metal(), right=metal()), 'ground_right': metal()}))
    result = LineQuantityStudyDocument(source, conductor=conductor, quantity='attenuation').analyze()
    assert not result.failed and len(result.rows) == 2
    for row in result.rows:
        assert 'reference:ground:ground_left:top' in row.result.conductor.boundary_labels
        np.testing.assert_allclose(row.result.conductor.resistance_parts.sum(axis=1), row.result.R, rtol=1e-12)
        assert row.to_dict()['input']['conductor']['reference']['conductors']['ground_left']['kind'] == 'faces'


def test_correlated_normal_failures_stay_ordered_without_partial_summary(monkeypatch):
    source = material_source(dict(kind='normal', count=8, seed=3, correlation=[[1., .5], [.5, 1.]],
        variables=[dict(name='width', mean=.2e-3, std=.3e-3), dict(name='loss', mean=.02, std=.06)]))
    doc = LineQuantityStudyDocument(source, conductor=dict(kind='perfect'), quantity='attenuation')
    calls = install_fake(monkeypatch); result = doc.analyze()
    assert result.failed > 0 and result.failed < 8 and result.summary is None
    assert len(result.rows) == 8 and [row.index for row in result.rows] == list(range(8))
    np.testing.assert_array_equal([row.sample_values for row in result.rows], source.samples())
    expected_failed = 0
    for row, (width, loss), parameters, material in zip(result.rows, source.samples(),
            source.sample_parameters(), source.sample_material_evaluations()):
        assert row.to_dict()['parameters'] == parameters
        assert row.to_dict()['material_evaluation'] == material
        invalid = width <= 0 or loss < 0
        assert (not row.complete) == invalid
        if invalid:
            expected_failed += 1
            assert row.phase == 'input' and row.input_json is None and row.value is None
        else:
            assert row.value == pytest.approx(1/(width/1e-3))
    assert result.failed == expected_failed and len(calls) == 8-expected_failed
    # Shared execution keeps all rows and explicitly reports incomplete.
    report = execute_saved(doc.dumps())
    assert report['status'] == 'incomplete' and report['result'] == result.to_dict()
    json.dumps(report, allow_nan=False)


@pytest.mark.parametrize('phase', ['extraction', 'diagnostic'])
def test_all_samples_attempted_after_solver_failure(monkeypatch, phase):
    calls = install_fake(monkeypatch, broken=phase)
    result = document().analyze()
    assert len(calls) == len(result.rows) == result.failed == 3 and result.summary is None
    assert all(row.phase == phase and row.error_type == 'ArithmeticError' and row.value is None for row in result.rows)
    assert all(row.input_json is not None for row in result.rows)


def test_changed_extraction_identity_is_a_retained_row_failure(monkeypatch):
    install_fake(monkeypatch); original = TransmissionLineDocument.analyze
    def wrong_name(self):
        line = original(self); line.names = ('unexpected',); return line
    monkeypatch.setattr(TransmissionLineDocument, 'analyze', wrong_name)
    result = document().analyze()
    assert result.failed == 3 and result.summary is None
    assert all(row.phase == 'extraction' and row.error_type == 'ValueError' for row in result.rows)


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -1., 0.])
def test_invalid_metric_rows_do_not_leak_nonfinite_json(monkeypatch, value):
    install_fake(monkeypatch, metric=lambda x: value)
    result = document().analyze()
    assert result.failed == 3 and result.summary is None
    assert all(row.phase == 'diagnostic' and row.value is None and row.error_type == 'ValueError'
               for row in result.rows)
    json.dumps(result.to_dict(), allow_nan=False)


def test_unrepresentable_derived_input_keeps_sample_and_continues(monkeypatch):
    import sipi.line_study as implementation
    original = implementation._parameters; calls = []
    def overflow_first(data, values):
        calls.append(1)
        return {'width': float('inf')} if len(calls) == 1 else original(data, values)
    monkeypatch.setattr(implementation, '_parameters', overflow_first)
    install_fake(monkeypatch)
    doc = document(); result = doc.analyze()
    assert result.failed == 1 and len(result.rows) == len(calls) == 3 and result.summary is None
    first = result.rows[0]
    assert first.phase == 'parameters' and first.parameters_json is None and first.input_json is None
    assert first.sample_values == tuple(doc.samples()[0])
    assert all(row.complete for row in result.rows[1:])
    json.dumps(result.to_dict(), allow_nan=False)


def test_shared_execution_complete_snapshot_and_readonly_outputs(monkeypatch):
    install_fake(monkeypatch); doc = document(); before = doc.dumps(); result = doc.analyze()
    report = execute_saved(before)
    assert report['status'] == 'complete' and report['result'] == result.to_dict()
    report['result']['rows'][0]['input']['length_m'] = 999
    assert json.loads(result.rows[0].input_json)['length_m'] == 0 and doc.dumps() == before
    with pytest.raises(TypeError): result.summary['mean'] = 999
    with pytest.raises(ValueError): doc.samples()[0, 0] = 999


def test_normalization_and_budget_do_not_solve_fields(monkeypatch):
    def forbidden(*args, **kwargs): pytest.fail('unexpected field or source study solve')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    monkeypatch.setattr(TransmissionLineDocument, 'analyze', forbidden)
    monkeypatch.setattr(ImpedanceStudyDocument, 'analyze', forbidden)
    doc = document(); assert normalize_saved(doc.dumps()) == doc.dumps()
    raw = doc.to_dict(); restored = LineQuantityStudyDocument.from_dict(raw)
    raw['study']['parameters']['width'] = 999
    assert restored.dumps() == doc.dumps()
    assert 'sipi.line-quantity-study/1' in saved_schemas()
    with pytest.raises(ValueError, match='sample count'): doc.analyze(max_evaluations=2)
    with pytest.raises(ValueError, match='sample count'): execute_saved(doc.dumps(), max_evaluations=2)
    with pytest.raises(ValueError, match='diagnostics'): execute_saved(doc.dumps(), diagnostics=['characteristic'])


def test_sampling_overflow_propagates_before_fields_without_resampling(monkeypatch):
    source = width_source().to_dict()
    source['sampling'] = dict(kind='normal', count=8, seed=3, correlation=[[1.]],
                             variables=[dict(name='width', mean=1e308, std=1e308)])
    doc = LineQuantityStudyDocument(source, conductor=dict(kind='perfect'), quantity='impedance_real')
    def forbidden(*args, **kwargs): pytest.fail('overflowing samples reached field work')
    monkeypatch.setattr(TransmissionLineDocument, 'analyze', forbidden)
    with np.errstate(over='ignore'), pytest.raises(ValueError, match='sampling overflow'): doc.analyze()


def test_independent_skrf_width_samples(width_result):
    skrf = require_tool('scikit-rf'); clock = Stopwatch(); errors = []
    for row in width_result[1].rows:
        line = row.result
        with clock('openphysics'): actual = line.propagation()
        with clock('reference'):
            medium = skrf.media.DistributedCircuit(skrf.Frequency.from_f(line.frequency, unit='hz'),
                R=line.R[:, 0, 0], L=line.L[:, 0, 0], G=line.G[:, 0, 0], C=line.C[:, 0, 0])
            expected_z, expected_gamma = medium.z0, medium.gamma
        errors.append(max(float(np.max(abs(actual.z_characteristic[:, 0]/expected_z-1))),
                          float(np.max(abs(actual.gamma[:, 0]/expected_gamma-1)))))
    error = max(errors)
    record = make_record(case='lossy-line-study-width-samples', physics='uniform scalar lossy line',
        api='sipi.line_study.LineQuantityStudyDocument', discretization='three independently remeshed width samples',
        tool='scikit-rf', tool_discretization='DistributedCircuit from identical extracted RLGC per sample',
        matched=['same scalar RLGC and frequency samples'],
        not_matched=['timings exclude field extraction; no empirical tolerance or independent field accuracy claim'],
        observables=[observable('Zc/gamma', 'relative', 'maximum relative difference', error, 1e-10)],
        analytical_acceptance='homogeneous sampled attenuation closed form and prior line API convergence', stopwatch=clock)
    record['openphysics'].update(distribution='sipi', version=metadata.version('sipi')); emit(record)
    assert error < 1e-10


@pytest.mark.parametrize('values', [[1., 2., 4., 8.], [0., 0., 0.], [1e308, 1e308, 1e308],
    [0., 1e308], [0., np.finfo(float).max], [0., 5e-324, 1e-323]])
def test_descriptive_statistics_against_independent_stable_reference(values):
    result = _summary(values); ordered = sorted(values)
    def quantile(q):
        position = (len(ordered)-1)*q; lower = int(position); fraction = position-lower
        return ordered[lower]*(1-fraction)+ordered[min(lower+1, len(ordered)-1)]*fraction
    expected = dict(minimum=min(values), maximum=max(values), mean=statistics.mean(values),
                    sample_std=statistics.stdev(values), p05=quantile(.05), p95=quantile(.95))
    for key in result: np.testing.assert_allclose(result[key], expected[key], rtol=1e-12, atol=0)
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize('values', [[1.], [1., np.inf], [-1., 0.], [[1., 2.]]])
def test_invalid_summary_input_rejects(values):
    with pytest.raises(ValueError): _summary(values)


@pytest.mark.parametrize('case', ['schema', 'missing', 'extra', 'quantity', 'legacy_source', 'pair', 'dc',
    'conductor', 'skin', 'material', 'sampling'])
def test_strict_input_rejects_before_mesh(monkeypatch, case):
    raw = document().to_dict()
    if case == 'schema': raw['schema'] = 'sipi.line-quantity-study/3'
    if case == 'missing': del raw['quantity']
    if case == 'extra': raw['extra'] = 1
    if case == 'quantity': raw['quantity'] = 'z0'
    if case == 'legacy_source':
        raw['study']['schema'] = 'sipi.impedance-study/1'
        del raw['study']['material_evaluation']; del raw['study']['fixed_plane_spacing_m']
    if case == 'pair':
        raw['study'] = ImpedanceStudyDocument('coupled_microstrip', dict(width=.5e-3, gap=.3e-3,
            substrate_height=1e-3, eps_r=4), quantity='z_diff', frequency=1e9, materials={}, mesh=MESH,
            sampling=dict(kind='sweep', count=2, variables=[dict(name='width', lower=.4e-3, upper=.6e-3)])).to_dict()
    if case == 'dc': raw['study']['material_evaluation']['frequency_hz'] = 0
    if case == 'conductor': raw['conductor']['kind'] = 'unknown'
    if case == 'skin': raw['conductor']['conductivity'] = 1e4
    if case == 'material': raw['study']['material_evaluation']['materials'] = {'missing': {}}
    if case == 'sampling': raw['study']['sampling']['count'] = True
    def forbidden(*args, **kwargs): pytest.fail('invalid input reached mesh')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    with pytest.raises(ValueError): LineQuantityStudyDocument.from_dict(raw)


@pytest.mark.parametrize('text', ['{"schema":1,"schema":1}', '{"x":NaN}', '{"x":Infinity}', '{"x":1e999}'])
def test_duplicate_or_nonfinite_json_rejects(text):
    with pytest.raises(ValueError): LineQuantityStudyDocument.loads(text)
