# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Lossy-line iid yield: exact binomial references and retained physical rows."""
from dataclasses import replace
from importlib import metadata
import json

import numpy as np
import pytest

from sipi import CrossSection
from sipi.dielectric import ConstantDielectric
from sipi.study import ImpedanceStudyDocument
from sipi.line_model import TransmissionLineDocument
from sipi.line_study import LineQuantityStudy, LineQuantityStudyRow, LineQuantityStudyDocument
from sipi.line_yield import LineQuantityYieldDocument, assess_line_yield
from sipi.execution import execute_saved, normalize_saved, saved_schemas
from test_line_study import document as scalar_study
from test_differential_line_study import document as paired_study
from test_differential_line_goal import QUANTITY, synthetic, MESH
from test_yield_assessment import independent_interval
from crosscheck import require_tool, Stopwatch, emit, make_record, observable


def random_study(quantity=QUANTITY, count=3, kind='uniform'):
    raw = (paired_study() if quantity == QUANTITY else scalar_study(quantity)).to_dict()
    sample = raw['study']['sampling']; sample['kind'] = kind
    if kind == 'corners': sample.pop('count', None)
    else: sample['count'] = count
    if kind == 'uniform': sample['seed'] = 123
    if kind == 'normal':
        sample.update(seed=3, correlation=[[1.]], variables=[
            dict(name=sample['variables'][0]['name'], mean=.7e-3, std=.01e-3)])
    return LineQuantityStudyDocument.from_dict(raw)


def synthetic_rows(values, quantity='impedance_real', kind='uniform'):
    """Algorithm fixture only; constructing rows is not evidence of field solves."""
    doc = random_study(quantity, len(values), kind); source = ImpedanceStudyDocument.from_dict(doc.to_dict()['study'])
    rows = tuple(LineQuantityStudyRow(i, tuple(map(float, sample)), json.dumps(parameters),
        json.dumps(evaluation), None, value, 'diagnostic' if value is None else 'complete',
        'ValueError' if value is None else None, 'retained solver failure' if value is None else None)
        for i, (value, sample, parameters, evaluation) in enumerate(zip(values, doc.samples(),
            source.sample_parameters(), source.sample_material_evaluations())))
    return LineQuantityStudy(doc.dumps(), quantity,
        tuple(v['name'] for v in doc.to_dict()['study']['sampling']['variables']), rows, None)


@pytest.mark.parametrize('quantity', ['impedance_real', 'attenuation', QUANTITY])
def test_quantity_units_inclusive_limits_and_unresolved_denominator(quantity):
    values = [0., 1., 2., None] if quantity == 'attenuation' else [45., 55., 80., None]
    limits = dict(minimum=0., maximum=1.) if quantity == 'attenuation' else dict(minimum=45., maximum=55.)
    study = synthetic_rows(values, quantity); result = assess_line_yield(study, **limits, minimum_yield=.8)
    assert result.classifications == ('pass', 'pass', 'fail', 'unresolved')
    assert (result.passed, result.failed, result.unresolved) == (2, 1, 1)
    assert result.sample_fraction_bounds == (.5, .75) and result.goal_status == 'undetermined'
    out = result.to_dict(); assert out['unit'] == ('Np/m' if quantity == 'attenuation' else 'ohm')
    assert out['quantity'] == quantity and out['rows'][3]['phase'] == 'diagnostic'
    assert [row['value'] for row in out['rows']] == values
    for k in (2, 3):
        low, high = independent_interval(k, 4, .95)
        assert result.confidence_interval[0] <= low+1e-14
        assert result.confidence_interval[1] >= high-1e-14
    assert result.study is study
    json.dumps(out, allow_nan=False)


@pytest.mark.parametrize('count', [2, 5, 20])
@pytest.mark.parametrize('confidence', [.5, .9, .95, .999])
def test_exact_intervals_against_independent_finite_binomial_inversion(count, confidence):
    for k in range(count+1):
        result = assess_line_yield(synthetic_rows([50.]*k+[80.]*(count-k), QUANTITY),
            minimum=45., maximum=55., confidence=confidence)
        np.testing.assert_allclose(result.confidence_interval, independent_interval(k, count, confidence),
                                   rtol=0., atol=1e-12)


def test_independent_exact_binomial_tool_at_extreme_counts():
    require_tool('scipy')
    from scipy.stats import binomtest
    clock = Stopwatch(); actual = []; expected = []
    cases = [(2, 0), (2, 2), (50, 17), (1000, 0), (1000, 1000), (1000, 999)]
    with clock('openphysics'):
        for n, k in cases:
            actual.append(assess_line_yield(synthetic_rows([0.]*k+[2.]*(n-k), 'attenuation'),
                                           maximum=1.).confidence_interval)
    with clock('reference'):
        for n, k in cases:
            interval = binomtest(k, n).proportion_ci(confidence_level=.95, method='exact')
            expected.append([interval.low, interval.high])
    error = float(np.max(abs(np.asarray(actual)-expected)))
    record = make_record(case='lossy-line-yield-exact-binomial', physics='fixed iid acceptance statistics',
        api='sipi.line_yield.assess_line_yield', discretization='inverse-beta unresolved-label envelope',
        tool='scipy', tool_discretization='stats.binomtest exact central interval',
        matched=['same counts and confidence, including zero/all successes and zero attenuation'],
        not_matched=['synthetic classification fixtures, not measured manufacturing or field accuracy',
                     'finite binomial-sum inversion independently checks the probability formula'],
        observables=[observable('confidence interval', '1', 'maximum absolute endpoint difference', error, 1e-12)],
        analytical_acceptance='finite binomial tails and all unresolved label possibilities', stopwatch=clock)
    record['openphysics'].update(distribution='sipi', version=metadata.version('sipi')); emit(record)
    assert error < 1e-12


def test_all_unknown_and_target_decisions_use_confidence_bounds():
    unknown = assess_line_yield(synthetic_rows([None]*5, QUANTITY), minimum=45., maximum=55., minimum_yield=.5)
    assert unknown.confidence_interval == (0., 1.) and unknown.sample_fraction_bounds == (0., 1.)
    assert unknown.goal_status == 'undetermined'
    good = synthetic_rows([50.]*20, QUANTITY)
    lower = .025**(1/20)
    result = assess_line_yield(good, minimum=45., minimum_yield=lower)
    assert result.goal_status == 'pass' and result.confidence_interval[0] == pytest.approx(lower, abs=1e-14)
    assert assess_line_yield(good, maximum=55., minimum_yield=1.).goal_status == 'undetermined'
    assert assess_line_yield(good, maximum=55.).goal_status == 'not-requested'
    assert assess_line_yield(synthetic_rows([80.]*20), maximum=55., minimum_yield=.8).goal_status == 'fail'


def test_actual_paired_uniform_yield_exact_study_and_saved_execution_replay():
    source = random_study(); direct = source.analyze(max_evaluations=3)
    doc = LineQuantityYieldDocument(source, minimum=95., maximum=105., minimum_yield=.9)
    restored = LineQuantityYieldDocument.loads(doc.dumps())
    result = restored.analyze(max_evaluations=3)
    assert not result.unresolved
    for actual, expected in zip(result.study.rows, direct.rows):
        assert actual.to_dict() == expected.to_dict()
        for key in ('R', 'L', 'G', 'C'):
            np.testing.assert_allclose(getattr(actual.result, key), getattr(expected.result, key), rtol=1e-10)
        np.testing.assert_allclose(actual.result.characteristic().z_characteristic,
                                   expected.result.characteristic().z_characteristic, rtol=1e-10)
    expected = assess_line_yield(direct, minimum=95., maximum=105., minimum_yield=.9)
    assert result.to_dict() == expected.to_dict()
    report = execute_saved(doc.dumps(), max_evaluations=3)
    assert report['status'] == 'complete' and report['result'] == expected.to_dict()
    assert report['result']['count'] == 3 and report['result']['goal_status'] == 'undetermined'
    json.dumps(report, allow_nan=False)


def test_lossless_scalar_material_samples_accept_zero_attenuation():
    study = ImpedanceStudyDocument('stripline', dict(width=.5e-3, plane_spacing=1e-3,
        eps_r=1., box_width=4e-3), quantity='z0', frequency=1e9,
        materials={'dielectric': ConstantDielectric(4., 0.)}, mesh=MESH,
        material_variables={'dk': dict(region='dielectric', path=['eps_r'])},
        sampling=dict(kind='uniform', count=3, seed=12, variables=[dict(name='dk', lower=3., upper=5.)]))
    line = LineQuantityStudyDocument(study, conductor=dict(kind='perfect'), quantity='attenuation')
    result = LineQuantityYieldDocument(line, minimum=0., maximum=0., minimum_yield=.9).analyze()
    assert result.passed == 3 and result.failed == result.unresolved == 0
    assert all(row.value == 0. for row in result.study.rows)
    assert result.to_dict()['unit'] == 'Np/m' and result.goal_status == 'undetermined'


def test_correlated_normal_invalid_geometry_remains_unresolved(monkeypatch):
    raw = paired_study().to_dict()
    raw['study']['sampling'] = dict(kind='normal', count=8, seed=3, correlation=[[1., .5], [.5, 1.]],
        variables=[dict(name='left_width', mean=.6e-3, std=.5e-3),
                   dict(name='right_width', mean=.5e-3, std=.3e-3)])
    source = LineQuantityStudyDocument.from_dict(raw); synthetic(monkeypatch)
    doc = LineQuantityYieldDocument(source, minimum=0., maximum=1000., minimum_yield=.8)
    report = execute_saved(doc.dumps()); result = doc.analyze()
    assert report['status'] == 'incomplete' and report['result'] == result.to_dict()
    assert (result.passed, result.failed, result.unresolved) == (5, 0, 3)
    assert result.sample_fraction_bounds == (5/8, 1.)
    assert [i for i, label in enumerate(result.classifications) if label == 'unresolved'] == [0, 3, 4]
    np.testing.assert_array_equal([row.sample_values for row in result.study.rows], source.samples())
    for k in range(5, 9):
        low, high = independent_interval(k, 8, .95)
        assert result.confidence_interval[0] <= low+1e-14 and result.confidence_interval[1] >= high-1e-14


@pytest.mark.parametrize('kind', ['sweep', 'corners'])
def test_deterministic_samples_are_not_iid_yield(kind):
    with pytest.raises(ValueError, match='iid'):
        LineQuantityYieldDocument(random_study(count=2, kind=kind), minimum=45.)
    with pytest.raises(ValueError, match='iid'):
        assess_line_yield(synthetic_rows([50., 50.], kind=kind), minimum=45.)


def test_inconsistent_external_rows_rejected_without_authenticity_claim():
    study = synthetic_rows([50., 80., None], QUANTITY); first = study.rows[0]
    bad = [replace(study, rows=study.rows[:-1]), replace(study, quantity='attenuation'),
        replace(study, variable_names=('other',)), replace(study, rows=study.rows[::-1]),
        replace(study, rows=(replace(first, sample_values=(999.,)), *study.rows[1:])),
        replace(study, rows=(replace(first, sample_values=None), *study.rows[1:])),
        replace(study, rows=(replace(first, sample_values=(True,)), *study.rows[1:])),
        replace(study, rows=(replace(first, value=float('nan')), *study.rows[1:])),
        replace(study, rows=(replace(first, value=0.), *study.rows[1:])),
        replace(study, rows=(replace(first, phase='input'), *study.rows[1:])),
        replace(study, rows=(replace(first, error_type='ValueError'), *study.rows[1:])),
        replace(study, rows=(*study.rows[:2], replace(study.rows[2], value=50.))),
        replace(study, rows=(*study.rows[:2], replace(study.rows[2], phase='complete')))]
    for invalid in bad:
        with pytest.raises(ValueError): assess_line_yield(invalid, minimum=45.)


@pytest.mark.parametrize('changes', [dict(minimum=None, maximum=None), dict(minimum=60., maximum=40.),
    dict(minimum=-1.), dict(maximum=True), dict(minimum=float('nan')), dict(maximum=10**400),
    dict(confidence=0.), dict(confidence=1.), dict(confidence=True), dict(confidence=1e-300),
    dict(confidence=float('inf')), dict(minimum_yield=-.1), dict(minimum_yield=1.1), dict(minimum_yield=True)])
def test_invalid_criteria_do_not_invoke_fields(monkeypatch, changes):
    def forbidden(*args, **kwargs): pytest.fail('invalid yield request reached fields')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    kwargs = dict(minimum=45., maximum=55.); kwargs.update(changes)
    with pytest.raises(ValueError): LineQuantityYieldDocument(random_study(), **kwargs)


def test_roundtrip_registry_and_budget_before_fields(monkeypatch):
    def forbidden(*args, **kwargs): pytest.fail('parsing or rejected yield budget invoked fields')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    monkeypatch.setattr(TransmissionLineDocument, 'analyze', forbidden)
    doc = LineQuantityYieldDocument(random_study(), minimum=95., maximum=105.)
    assert normalize_saved(doc.dumps()) == doc.dumps() and 'sipi.line-quantity-yield/1' in saved_schemas()
    raw = doc.to_dict(); restored = LineQuantityYieldDocument.from_dict(raw)
    raw['study']['study']['parameters']['left_width'] = 1.
    assert restored.dumps() == doc.dumps()
    with pytest.raises(ValueError, match='sample count'): doc.analyze(max_evaluations=2)
    with pytest.raises(ValueError, match='sample count'): execute_saved(doc.dumps(), max_evaluations=2)
    with pytest.raises(ValueError, match='diagnostics'): execute_saved(doc.dumps(), diagnostics=['characteristic'])


@pytest.mark.parametrize('case', ['schema', 'extra', 'missing', 'legacy_study'])
def test_strict_saved_fields(case):
    raw = LineQuantityYieldDocument(random_study(), minimum=95.).to_dict()
    if case == 'schema': raw['schema'] = 'sipi.line-quantity-yield/999'
    if case == 'extra': raw['extra'] = 0
    if case == 'missing': del raw['confidence']
    if case == 'legacy_study': raw['study'] = raw['study']['study']
    with pytest.raises(ValueError): LineQuantityYieldDocument.from_dict(raw)


@pytest.mark.parametrize('text', ['{"schema":1,"schema":1}', '{"x":NaN}', '{"x":Infinity}', '{"x":1e999}'])
def test_duplicate_and_nonfinite_json_reject(text):
    with pytest.raises(ValueError): LineQuantityYieldDocument.loads(text)
