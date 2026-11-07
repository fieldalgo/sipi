# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Exact binomial tails, unresolved labels and actual saved field-study replay."""
from dataclasses import replace
from importlib import metadata
import json
import math

import numpy as np
import pytest

from sipi import CrossSectionDocument
from sipi.study import ImpedanceStudy, StudyRow, ImpedanceStudyDocument
from sipi.yield_assessment import ImpedanceYieldDocument, assess_impedance_yield
from sipi.execution import normalize_saved, execute_saved
from test_study import document, bounded, normal
from crosscheck import require_tool, Stopwatch, emit, make_record, observable


def sample_study(values, *, kind='uniform'):
    spec = normal(len(values)) if kind == 'normal' else bounded(kind, len(values))
    doc = document(spec)
    params = doc.sample_parameters()
    rows = tuple(StudyRow(i, params[i], None, value,
        'ValueError' if value is None else None, 'retained solver failure' if value is None else None)
        for i, value in enumerate(values))
    return ImpedanceStudy(doc.dumps(), 'z0', rows, None)


def independent_interval(k, n, confidence):
    # Invert finite binomial sums by bisection; no beta special function.
    tail = (1-confidence)/2
    def invert(start, end, probability, decreasing=False):
        lo, hi = 0., 1.
        for _ in range(70):
            p = (lo+hi)/2
            value = math.fsum(math.comb(n, j)*p**j*(1-p)**(n-j) for j in range(start, end))
            if (value < probability) != decreasing: lo = p
            else: hi = p
        return (lo+hi)/2
    return (0. if k == 0 else invert(k, n+1, tail),
            1. if k == n else invert(0, k+1, tail, decreasing=True))


@pytest.mark.parametrize('n', [2, 5, 20])
@pytest.mark.parametrize('confidence', [.5, .9, .95, .999])
def test_exact_interval_matches_independent_binomial_tail_inversion(n, confidence):
    for k in range(n+1):
        result = assess_impedance_yield(sample_study([50.]*k+[80.]*(n-k)),
            minimum=45, maximum=55, confidence=confidence)
        np.testing.assert_allclose(result.confidence_interval, independent_interval(k, n, confidence),
                                   rtol=0, atol=1e-12)


def test_reference_exact_binomial_api_and_extreme_sample_counts():
    require_tool('scipy')
    from scipy.stats import binomtest
    clock = Stopwatch(); actual = []; expected = []
    cases = [(2, 0), (2, 2), (50, 17), (1000, 0), (1000, 1000), (1000, 999)]
    with clock('openphysics'):
        for n, k in cases:
            actual.append(assess_impedance_yield(sample_study([50.]*k+[80.]*(n-k)),
                          minimum=45, maximum=55).confidence_interval)
    with clock('reference'):
        for n, k in cases:
            ci = binomtest(k, n).proportion_ci(confidence_level=.95, method='exact')
            expected.append((ci.low, ci.high))
    difference = float(np.max(abs(np.array(actual)-expected)))
    record = make_record(case='impedance_yield_exact_binomial', physics='iid acceptance statistics',
        api='sipi.yield_assessment.assess_impedance_yield', discretization='inverse-beta exact equal-tailed interval',
        tool='scipy', tool_discretization='stats.binomtest exact confidence interval',
        matched=['same trial/success counts and 95% central confidence', 'no unresolved labels in this reference comparison'],
        not_matched=['manufacturing population, field accuracy and empirical data', 'separate direct finite-binomial-sum tests establish mathematical tails'],
        observables=[observable('confidence interval', '1', 'maximum endpoint absolute difference', difference, 1e-12)],
        analytical_acceptance='finite binomial sum inversion, zero/all-success limits and unresolved-label envelope', stopwatch=clock)
    record['openphysics'].update(distribution='sipi', version=metadata.version('sipi')); emit(record)
    assert difference < 1e-12


def test_unresolved_rows_keep_denominator_and_all_possible_labels():
    study = sample_study([45., 55., 40., None, None])
    result = assess_impedance_yield(study, minimum=45., maximum=55., minimum_yield=.8)
    assert result.classifications == ('pass', 'pass', 'fail', 'unresolved', 'unresolved')
    assert (result.passed, result.failed, result.unresolved) == (2, 1, 2)
    assert result.sample_fraction_bounds == (.4, .8)
    assert result.study is study and result.goal_status == 'undetermined'
    for k in (2, 3, 4):
        low, high = independent_interval(k, 5, .95)
        assert result.confidence_interval[0] <= low+1e-14
        assert result.confidence_interval[1] >= high-1e-14
    out = result.to_dict()
    assert len(out['rows']) == 5 and out['rows'][3]['error'] == study.rows[3].error
    json.dumps(out, allow_nan=False)


def test_endpoint_symmetry_confidence_and_sample_size_monotonicity():
    def assess(n, z, level=.95):
        return assess_impedance_yield(sample_study([z]*n), minimum=45, maximum=55, confidence=level)
    all_pass, all_fail = assess(20, 50), assess(20, 80)
    assert all_pass.confidence_interval[1] == 1 and all_fail.confidence_interval[0] == 0
    assert all_pass.confidence_interval[0] == pytest.approx(.025**(1/20), abs=1e-14)
    assert all_fail.confidence_interval[1] == pytest.approx(1-.025**(1/20), abs=1e-14)
    assert assess(50, 50).confidence_interval[0] > all_pass.confidence_interval[0]
    assert assess(20, 50, .99).confidence_interval[0] < all_pass.confidence_interval[0]
    unknown = assess_impedance_yield(sample_study([None]*5), minimum=45, maximum=55)
    assert unknown.confidence_interval == (0., 1.) and unknown.sample_fraction_bounds == (0., 1.)


def test_target_is_a_confidence_bound_decision_not_a_sample_percentage():
    low = assess_impedance_yield(sample_study([50.]*100), minimum=45, maximum=55).confidence_interval[0]
    result = assess_impedance_yield(sample_study([50.]*100), minimum=45, maximum=55, minimum_yield=low)
    assert result.goal_status == 'pass'
    assert assess_impedance_yield(result.study, minimum=45, maximum=55, minimum_yield=1).goal_status == 'undetermined'
    assert assess_impedance_yield(sample_study([80.]*100), minimum=45, maximum=55, minimum_yield=.8).goal_status == 'fail'
    assert assess_impedance_yield(result.study, minimum=45).goal_status == 'not-requested'


@pytest.mark.parametrize('kind', ['sweep', 'corners'])
def test_nonrandom_sampling_is_not_population_yield(kind):
    doc = document(bounded(kind, 2))
    with pytest.raises(ValueError, match='iid'): ImpedanceYieldDocument(doc, minimum=45)
    with pytest.raises(ValueError, match='iid'): assess_impedance_yield(sample_study([50., 50.], kind=kind), minimum=45)


@pytest.mark.parametrize('changes', [dict(minimum=None, maximum=None), dict(minimum=60, maximum=40),
    dict(minimum=-1), dict(maximum=True), dict(minimum=float('nan')), dict(maximum=10**400),
    dict(confidence=0), dict(confidence=1), dict(confidence=True), dict(confidence=1e-300),
    dict(confidence=float('inf')), dict(minimum_yield=-.1), dict(minimum_yield=1.1), dict(minimum_yield=True)])
def test_invalid_criteria_reject(changes):
    kwargs = dict(minimum=45, maximum=55); kwargs.update(changes)
    with pytest.raises(ValueError): ImpedanceYieldDocument(document(bounded('uniform', 2)), **kwargs)


def test_partial_or_inconsistent_external_results_reject():
    study = sample_study([50., 80., None])
    bad = [replace(study, rows=study.rows[:-1]), replace(study, quantity='z_diff'),
           replace(study, rows=study.rows[::-1]),
           replace(study, rows=(replace(study.rows[0], impedance=float('nan')), *study.rows[1:])),
           replace(study, rows=(*study.rows[:2], replace(study.rows[2], impedance=50.))),
           replace(study, rows=(replace(study.rows[0], error_type='ValueError'), *study.rows[1:]))]
    for value in bad:
        with pytest.raises(ValueError): assess_impedance_yield(value, minimum=45)


def test_actual_field_replay_and_saved_transport_preserve_all_samples():
    study = document(bounded('uniform', 3))
    doc = ImpedanceYieldDocument(study, minimum=1, maximum=1000, minimum_yield=.9)
    raw = doc.to_dict(); restored = ImpedanceYieldDocument.from_dict(raw)
    raw['study']['parameters']['width'] = 99
    assert doc.dumps() == restored.dumps() == normalize_saved(doc.dumps())
    direct = study.analyze(max_evaluations=3)
    report = execute_saved(restored.dumps(), max_evaluations=3)
    assert report['status'] == 'complete'
    assert report['result']['passed'] == 3 and report['result']['goal_status'] == 'undetermined'
    assert report['result']['sample_fraction_bounds'] == [1., 1.]
    np.testing.assert_allclose([r['impedance_ohm'] for r in report['result']['rows']],
                               [r.impedance for r in direct.rows], rtol=1e-12)
    assert [r['parameters'] for r in report['result']['rows']] == [dict(r.parameters) for r in direct.rows]
    json.dumps(report, allow_nan=False)


def test_field_failure_and_normal_correlation_are_retained(monkeypatch):
    doc = ImpedanceYieldDocument(document(normal(3)), minimum=45, maximum=55)
    def failed(*args, **kwargs): raise ValueError('retained field failure')
    monkeypatch.setattr(CrossSectionDocument, 'analyze', failed)
    out = execute_saved(doc.dumps(), max_evaluations=3)
    assert out['status'] == 'incomplete'
    assert out['result']['count'] == out['result']['unresolved'] == 3
    assert out['result']['confidence_interval'] == [0., 1.]
    assert out['result']['sampling_model']['correlation'] == normal(3)['correlation']
    assert all(r['error'] == 'retained field failure' for r in out['result']['rows'])


def test_budget_normalization_and_strict_keys_before_field_work(monkeypatch):
    doc = ImpedanceYieldDocument(document(bounded('uniform', 3)), minimum=45)
    def forbidden(*args, **kwargs): pytest.fail('parsing or over-budget input reached a field solve')
    monkeypatch.setattr(CrossSectionDocument, 'analyze', forbidden)
    assert normalize_saved(doc.dumps()) == doc.dumps()
    with pytest.raises(ValueError, match='max_evaluations'): execute_saved(doc.dumps(), max_evaluations=2)
    for key, value in [('schema', 'sipi.impedance-yield/2'), ('extra', 1)]:
        data = doc.to_dict(); data[key] = value
        with pytest.raises(ValueError): ImpedanceYieldDocument.from_dict(data)
    data = doc.to_dict(); del data['confidence']
    with pytest.raises(ValueError): ImpedanceYieldDocument.from_dict(data)
    for text in (doc.dumps().replace('"confidence": 0.95', '"confidence": NaN'),
                 doc.dumps().replace('"confidence": 0.95', '"confidence": 1e999'),
                 doc.dumps().replace('"confidence": 0.95', '"confidence": 0.95,"confidence": 0.95')):
        for load in (ImpedanceYieldDocument.loads, normalize_saved):
            with pytest.raises(ValueError): load(text)


def test_material_bound_samples_and_failed_row_provenance_survive_yield_export(monkeypatch):
    from types import SimpleNamespace
    from test_material_variables import plan
    import sipi.study as implementation
    sampling = dict(kind='uniform', count=2, seed=87,
        variables=[dict(name='dk', lower=3.8, upper=4.2)])
    study = plan(sampling=sampling)
    evaluations = study.sample_material_evaluations(); calls = []
    def observed(document, evaluation, quantity):
        calls.append(evaluation)
        if len(calls) == 2: raise ValueError('material field failure retained')
        return SimpleNamespace(z0=50.)
    monkeypatch.setattr(implementation, '_analyze_material', observed)
    doc = ImpedanceYieldDocument(study, minimum=45, maximum=55)
    out = execute_saved(doc.dumps(), max_evaluations=2)
    assert out['status'] == 'incomplete' and calls == evaluations
    assert [row['material_evaluation'] for row in out['result']['rows']] == evaluations
    assert [row['classification'] for row in out['result']['rows']] == ['pass', 'unresolved']
    assert out['result']['sample_fraction_bounds'] == [.5, 1.]
    assert out['input']['study']['schema'] == 'sipi.impedance-study/4'
