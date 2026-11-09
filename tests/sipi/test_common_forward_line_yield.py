# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Common-current iid acceptance: independent bounds and complete row identity."""
from dataclasses import replace
import itertools
import json

import numpy as np
import pytest

from sipi import CrossSection
from sipi.execution import execute_saved, normalize_saved, saved_schemas
from sipi.line_model import TransmissionLineDocument
from sipi.line_study import LineQuantityStudy, LineQuantityStudyDocument, LineQuantityStudyRow
from sipi.line_yield import LineQuantityYieldDocument, assess_line_yield
from sipi.study import ImpedanceStudyDocument
from test_common_forward_line_study import document as common_study
from test_common_forward_line_goal import QUANTITY, synthetic
from test_yield_assessment import independent_interval
from test_line_yield import random_study as previous_study
from test_line_goal import install_fake

SCHEMA = 'sipi.line-quantity-yield/2'


def random_study(count=4, kind='uniform'):
    raw = common_study().to_dict()
    raw['study']['sampling'] = dict(kind=kind, count=count, seed=17,
        variables=[dict(name='left_width', lower=.6e-3, upper=.8e-3)])
    if kind == 'normal':
        raw['study']['sampling'].update(correlation=[[1.]],
            variables=[dict(name='left_width', mean=.7e-3, std=.01e-3)])
    return LineQuantityStudyDocument.from_dict(raw)


def synthetic_rows(values):
    """Classification-only fixtures do not establish field accuracy."""
    doc = random_study(len(values))
    source = ImpedanceStudyDocument.from_dict(doc.to_dict()['study'])
    rows = tuple(LineQuantityStudyRow(i, tuple(map(float, sample)), json.dumps(parameters),
        json.dumps(evaluation), None, value, 'extraction' if value is None else 'complete',
        'ArithmeticError' if value is None else None, 'retained failure' if value is None else None)
        for i, (value, sample, parameters, evaluation) in enumerate(zip(values, doc.samples(),
            source.sample_parameters(), source.sample_material_evaluations())))
    return LineQuantityStudy(doc.dumps(), QUANTITY, ('left_width',), rows, None)


@pytest.mark.parametrize('n', [2, 5, 20])
@pytest.mark.parametrize('confidence', [.5, .9, .95, .999])
def test_common_interval_matches_independent_finite_binomial_inversion(n, confidence):
    for k in range(n+1):
        result = assess_line_yield(synthetic_rows([40.]*k+[50.]*(n-k)),
            minimum=38., maximum=41., confidence=confidence)
        np.testing.assert_allclose(result.confidence_interval,
            independent_interval(k, n, confidence), rtol=0., atol=1e-12)
        assert result.passed == k and result.failed == n-k and result.unresolved == 0


def test_unknown_labels_keep_denominator_and_enclose_every_assignment():
    values = [38., 41., 50., None, None, None]
    result = assess_line_yield(synthetic_rows(values), minimum=38., maximum=41., minimum_yield=.8)
    assert result.classifications == ('pass', 'pass', 'fail', 'unresolved', 'unresolved', 'unresolved')
    assert result.sample_fraction_bounds == (2/6, 5/6) and result.goal_status == 'undetermined'
    for labels in itertools.product((0, 1), repeat=3):
        low, high = independent_interval(2+sum(labels), 6, .95)
        assert result.confidence_interval[0] <= low+1e-12
        assert result.confidence_interval[1] >= high-1e-12
    report = result.to_dict()
    assert report['unit'] == 'ohm' and report['quantity'] == QUANTITY
    assert [row['index'] for row in report['rows']] == list(range(6))
    assert [row['value'] for row in report['rows']] == values
    assert all(row['error'] == 'retained failure' for row in report['rows'][3:])
    json.dumps(report, allow_nan=False)


def test_all_unknown_all_pass_all_fail_and_target_endpoints():
    unknown = assess_line_yield(synthetic_rows([None]*5), maximum=41., minimum_yield=.5)
    assert unknown.confidence_interval == (0., 1.) and unknown.sample_fraction_bounds == (0., 1.)
    assert unknown.goal_status == 'undetermined'
    low = .025**(1/20)
    good = assess_line_yield(synthetic_rows([40.]*20), maximum=41., minimum_yield=low)
    assert good.goal_status == 'pass'
    np.testing.assert_allclose(good.confidence_interval, [low, 1.], rtol=0., atol=1e-12)
    bad = assess_line_yield(synthetic_rows([50.]*20), maximum=41., minimum_yield=.8)
    assert bad.goal_status == 'fail'
    assert assess_line_yield(synthetic_rows([40.]*2), maximum=41.).goal_status == 'not-requested'


def test_real_common_uniform_saved_and_direct_rows_match_exactly():
    source = random_study()
    direct = source.analyze(max_evaluations=4)
    doc = LineQuantityYieldDocument(source, schema=SCHEMA, minimum=38., maximum=41., minimum_yield=.5)
    saved = LineQuantityYieldDocument.loads(doc.dumps()).analyze(max_evaluations=4)
    expected = assess_line_yield(direct, minimum=38., maximum=41., minimum_yield=.5)
    assert saved.to_dict() == expected.to_dict()
    assert saved.passed == 4 and saved.failed == saved.unresolved == 0
    assert [row.index for row in saved.study.rows] == list(range(4))
    np.testing.assert_array_equal([row.sample_values for row in saved.study.rows], source.samples())
    for actual, reference in zip(saved.study.rows, direct.rows):
        assert actual.input_json == reference.input_json and actual.to_dict() == reference.to_dict()
        for key in ('R', 'L', 'G', 'C'):
            np.testing.assert_allclose(getattr(actual.result, key), getattr(reference.result, key), rtol=1e-10)
        np.testing.assert_allclose(actual.result.characteristic().z_characteristic,
                                  reference.result.characteristic().z_characteristic, rtol=1e-10)
    np.testing.assert_allclose(saved.confidence_interval, independent_interval(4, 4, .95), rtol=0., atol=1e-12)
    report = execute_saved(doc.dumps(), max_evaluations=4)
    assert report['status'] == 'complete' and report['result'] == expected.to_dict()


def test_correlated_invalid_geometry_remains_unknown_and_later_rows_run(monkeypatch):
    raw = random_study().to_dict()
    raw['study']['sampling'] = dict(kind='normal', count=8, seed=3,
        correlation=[[1., .5], [.5, 1.]], variables=[
            dict(name='left_width', mean=.6e-3, std=.5e-3),
            dict(name='right_width', mean=.5e-3, std=.3e-3)])
    study = LineQuantityStudyDocument.from_dict(raw)
    calls = synthetic(monkeypatch)
    doc = LineQuantityYieldDocument(study, schema=SCHEMA, minimum=1., maximum=1000.)
    result = doc.analyze()
    assert result.unresolved == 3 and result.passed == 5 and len(calls) == 5
    assert [row.index for row in result.study.rows] == list(range(8))
    assert [i for i, label in enumerate(result.classifications) if label == 'unresolved'] == [0, 3, 4]
    np.testing.assert_array_equal([row.sample_values for row in result.study.rows], study.samples())
    assert result.sample_fraction_bounds == (5/8, 1.)
    for k in range(5, 9):
        low, high = independent_interval(k, 8, .95)
        assert result.confidence_interval[0] <= low+1e-12 and result.confidence_interval[1] >= high-1e-12
    report = execute_saved(doc.dumps())
    assert report['result'] == result.to_dict()
    assert len(calls) == 10


@pytest.mark.parametrize('kind', ['sweep', 'corners'])
def test_deterministic_common_samples_reject_iid_inference(monkeypatch, kind):
    raw = common_study().to_dict()
    raw['study']['sampling']['kind'] = kind
    if kind == 'corners': raw['study']['sampling'].pop('count')
    doc = LineQuantityStudyDocument.from_dict(raw)
    synthetic(monkeypatch)
    study = doc.analyze()
    with pytest.raises(ValueError, match='iid'):
        assess_line_yield(study, maximum=41.)
    with pytest.raises(ValueError, match='iid'):
        LineQuantityYieldDocument(doc, schema=SCHEMA, maximum=41.)


@pytest.mark.parametrize('change', ['drop', 'order', 'index', 'vector', 'boolean', 'quantity', 'variables',
                                  'zero', 'nan', 'phase', 'error_type', 'unknown_value'])
def test_external_row_identity_and_failure_corruption_rejected(change):
    study = synthetic_rows([40., 50., None]); first = study.rows[0]
    altered = dict(
        drop=replace(study, rows=study.rows[:-1]),
        order=replace(study, rows=study.rows[::-1]),
        index=replace(study, rows=(replace(first, index=1), *study.rows[1:])),
        vector=replace(study, rows=(replace(first, sample_values=(999.,)), *study.rows[1:])),
        boolean=replace(study, rows=(replace(first, sample_values=(True,)), *study.rows[1:])),
        quantity=replace(study, quantity='differential_forward_impedance_real'),
        variables=replace(study, variable_names=('different',)),
        zero=replace(study, rows=(replace(first, value=0.), *study.rows[1:])),
        nan=replace(study, rows=(replace(first, value=float('nan')), *study.rows[1:])),
        phase=replace(study, rows=(replace(first, phase='extraction'), *study.rows[1:])),
        error_type=replace(study, rows=(replace(first, error_type='ValueError'), *study.rows[1:])),
        unknown_value=replace(study, rows=(*study.rows[:2], replace(study.rows[2], value=40.))))
    with pytest.raises(ValueError): assess_line_yield(altered[change], maximum=41.)


@pytest.mark.parametrize('quantity', ['impedance_real', 'attenuation', 'differential_forward_impedance_real'])
def test_explicit_saved_v2_preserves_previous_quantity_reports(monkeypatch, quantity):
    source = previous_study(quantity)
    if quantity == 'differential_forward_impedance_real': synthetic(monkeypatch)
    else: install_fake(monkeypatch)
    old = LineQuantityYieldDocument(source, maximum=1000.)
    new = LineQuantityYieldDocument(source, maximum=1000., schema=SCHEMA)
    assert old.to_dict()['schema'] == 'sipi.line-quantity-yield/1'
    assert old.analyze().to_dict() == new.analyze().to_dict()
    raw = source.to_dict(); raw['schema'] = 'sipi.line-quantity-study/3'
    version3 = LineQuantityYieldDocument(LineQuantityStudyDocument.from_dict(raw), maximum=1000., schema=SCHEMA)
    assert version3.analyze().to_dict() == old.analyze().to_dict()


def test_default_and_explicit_old_saved_versions_still_reject_study3():
    for kwargs in ({}, dict(schema='sipi.line-quantity-yield/1')):
        with pytest.raises(ValueError, match='study/1 or /2'):
            LineQuantityYieldDocument(random_study(), maximum=41., **kwargs)


def test_strict_saved_roundtrip_copy_and_budget_before_fields(monkeypatch):
    def forbidden(*args, **kwargs): pytest.fail('parsing or rejected budget reached fields')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    monkeypatch.setattr(TransmissionLineDocument, 'analyze', forbidden)
    doc = LineQuantityYieldDocument(random_study(), schema=SCHEMA, maximum=41.)
    assert SCHEMA in saved_schemas() and normalize_saved(doc.dumps()) == doc.dumps()
    raw = doc.to_dict(); restored = LineQuantityYieldDocument.from_dict(raw)
    raw['study']['study']['parameters']['left_width'] = 1.
    assert restored.dumps() == doc.dumps()
    with pytest.raises(ValueError, match='sample count'): doc.analyze(max_evaluations=3)
    with pytest.raises(ValueError, match='sample count'): execute_saved(doc.dumps(), max_evaluations=3)
    with pytest.raises(ValueError, match='diagnostics'): execute_saved(doc.dumps(), diagnostics=['characteristic'])


@pytest.mark.parametrize('case', ['schema', 'extra', 'missing', 'no_limits', 'reversed', 'negative',
                                'boolean', 'nan', 'overflow', 'confidence', 'target', 'wrong_study'])
def test_strict_keys_and_invalid_criteria_before_fields(monkeypatch, case):
    raw = LineQuantityYieldDocument(random_study(), schema=SCHEMA, minimum=38., maximum=41.).to_dict()
    if case == 'schema': raw['schema'] = 'sipi.line-quantity-yield/999'
    elif case == 'extra': raw['extra'] = 0
    elif case == 'missing': del raw['confidence']
    elif case == 'no_limits': raw.update(minimum=None, maximum=None)
    elif case == 'reversed': raw.update(minimum=42.)
    elif case == 'negative': raw.update(minimum=-1.)
    elif case == 'boolean': raw.update(minimum=True)
    elif case == 'nan': raw.update(maximum=float('nan'))
    elif case == 'overflow': raw.update(maximum=10**400)
    elif case == 'confidence': raw.update(confidence=1.)
    elif case == 'target': raw.update(minimum_yield=1.1)
    elif case == 'wrong_study': raw['study'] = raw['study']['study']
    def forbidden(*args, **kwargs): pytest.fail('invalid input reached fields')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    with pytest.raises(ValueError): LineQuantityYieldDocument.from_dict(raw)


@pytest.mark.parametrize('text', ['{"schema":1,"schema":1}', '{"x":NaN}', '{"x":Infinity}', '{"x":1e999}'])
def test_duplicate_and_nonfinite_json_rejected(text):
    with pytest.raises(ValueError): LineQuantityYieldDocument.loads(text)
