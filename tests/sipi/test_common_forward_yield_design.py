# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Fixed common-current candidates: family bounds, retained rows and replay."""
from fractions import Fraction
import json

import numpy as np
import pytest

from sipi import CrossSection
from sipi.execution import execute_saved, normalize_saved, saved_schemas
from sipi.line_study import LineQuantityStudyDocument
from sipi.line_yield import assess_line_yield
from sipi.yield_design import YieldDesignDocument
from test_common_forward_line_yield import random_study
from test_common_forward_line_goal import QUANTITY
from test_lossy_yield_design import inject, design as previous_design
from test_yield_assessment import independent_interval

SCHEMA = 'sipi.yield-design/3'


def design(costs=(3., 1., 2.), *, count=40, confidence=.95, target=.8):
    return YieldDesignDocument([dict(name=f'candidate-{i}', cost=cost,
        study=random_study(count).to_dict()) for i, cost in enumerate(costs)],
        cost_unit='relative fabrication cost', minimum=38., maximum=41.,
        minimum_yield=target, confidence=confidence, schema=SCHEMA)


@pytest.mark.parametrize('count', [1, 2, 3, 7, 32])
@pytest.mark.parametrize('confidence', [.1, .5, .9, .95, .999])
def test_conservative_family_budget_and_independent_interval(monkeypatch, count, confidence):
    inject(monkeypatch, [[40.]*7+[50.]*3]*count)
    result = design([1.]*count, count=10, confidence=confidence).analyze(max_evaluations=10*count)
    level = result.candidate_confidence
    assert (1-Fraction(level))*count <= 1-Fraction(confidence)
    assert level >= confidence
    expected = independent_interval(7, 10, level)
    for candidate in result.candidates:
        np.testing.assert_allclose(candidate.assessment.confidence_interval, expected, rtol=0., atol=1e-12)
        assert [row.index for row in candidate.assessment.study.rows] == list(range(10))
    assert result.to_dict()['unit'] == 'ohm' and result.to_dict()['quantity'] == QUANTITY


def test_cheaper_unknown_and_equal_cost_input_order_are_preserved(monkeypatch):
    doc = design((4., 1., 2., 2.))
    calls = inject(monkeypatch, [[40.]*40, [None]*40, [40.]*40, [40.]*40])
    report = execute_saved(doc.dumps(), max_evaluations=160)
    out = report['result']
    assert report['status'] == 'incomplete' and out['status'] == 'selected'
    assert out['selected'] == dict(index=2, name='candidate-2', cost=2.)
    assert out['unresolved'] == 40 and out['evaluations'] == 160 and len(calls) == 4
    assert out['candidates'][1]['assessment']['goal_status'] == 'undetermined'
    assert all(row['error'] == 'retained field failure' for row in out['candidates'][1]['assessment']['rows'])
    for candidate, original in zip(out['candidates'], doc.to_dict()['candidates']):
        assert candidate['study'] == original['study']
        assert [row['index'] for row in candidate['assessment']['rows']] == list(range(40))
    json.dumps(report, allow_nan=False)


@pytest.mark.parametrize('values,status', [([50.]*40, 'none-certified'),
                                          ([None]*40, 'undetermined'),
                                          ([40.]*20+[50.]*20, 'none-certified')])
def test_no_selection_keeps_every_candidate(monkeypatch, values, status):
    inject(monkeypatch, [values]*3)
    result = design().analyze()
    assert result.status == status and result.selected_index is None
    assert len(result.candidates) == 3 and result.to_dict()['selected'] is None


def test_candidate_dependence_is_allowed_but_each_row_is_iid(monkeypatch):
    raw = design((1., 2.)).to_dict()
    for candidate in raw['candidates']:
        candidate['study'] = random_study(40, 'normal').to_dict()
    calls = inject(monkeypatch, [[40.]*40, [40.]*40])
    result = YieldDesignDocument.from_dict(raw).analyze()
    assert calls[0] == calls[1]
    assert all(c.assessment.to_dict()['sampling_model']['correlation'] == [[1.]] for c in result.candidates)
    assert result.selected_index == 0


def test_actual_two_common_candidates_replay_direct_rows_and_selection():
    raw = design((2., 1.), count=2, confidence=.9, target=.1).to_dict()
    for entry, low, high in zip(raw['candidates'], [.6e-3, .7e-3], [.7e-3, .8e-3]):
        source = entry['study']['study']; nominal = (low+high)/2
        source['parameters'].update(left_width=nominal, gap=.95e-3-(nominal+.5e-3)/2)
        source['sampling']['variables'] = [dict(name='left_width', lower=low, upper=high)]
    doc = YieldDesignDocument.from_dict(raw)
    result = doc.analyze(max_evaluations=4)
    assert result.selected_index == 1 and result.status == 'selected' and result.unresolved == 0
    assert (1-Fraction(result.candidate_confidence))*2 <= 1-Fraction(.9)
    for entry, candidate in zip(doc.to_dict()['candidates'], result.candidates):
        source = LineQuantityStudyDocument.from_dict(entry['study'])
        direct = source.analyze(max_evaluations=2)
        expected = assess_line_yield(direct, minimum=38., maximum=41., confidence=result.candidate_confidence,
                                     minimum_yield=.1)
        assert candidate.assessment.to_dict() == expected.to_dict()
        assert candidate.assessment.passed == 2 and candidate.assessment.goal_status == 'pass'
        np.testing.assert_allclose(candidate.assessment.confidence_interval,
            independent_interval(2, 2, result.candidate_confidence), rtol=0., atol=1e-12)
        for row, reference in zip(candidate.assessment.study.rows, direct.rows):
            assert row.to_dict() == reference.to_dict() and row.input_json == reference.input_json
            for key in ('R', 'L', 'G', 'C'):
                np.testing.assert_allclose(getattr(row.result, key), getattr(reference.result, key), rtol=1e-10)
            np.testing.assert_allclose(row.result.characteristic().z_characteristic,
                                      reference.result.characteristic().z_characteristic, rtol=1e-10)
    report = execute_saved(doc.dumps(), max_evaluations=4)
    assert report['status'] == 'complete' and report['result'] == result.to_dict()


@pytest.mark.parametrize('quantity', ['impedance_real', 'attenuation', 'differential_forward_impedance_real'])
def test_old_lossy_outputs_are_exact_and_new_study_version_preserves_assessments(monkeypatch, quantity):
    old = previous_design((2., 1.), count=4, target=.1, quantity=quantity)
    raw = old.to_dict(); raw['schema'] = SCHEMA
    new = YieldDesignDocument.from_dict(raw)
    inject(monkeypatch, [[50.]*4, [50.]*4]); expected = old.analyze()
    inject(monkeypatch, [[50.]*4, [50.]*4]); result = new.analyze()
    assert result.to_dict() == expected.to_dict()
    for candidate in raw['candidates']: candidate['study']['schema'] = 'sipi.line-quantity-study/3'
    inject(monkeypatch, [[50.]*4, [50.]*4]); upgraded = YieldDesignDocument.from_dict(raw).analyze()
    assert upgraded.selected_index == expected.selected_index
    for actual, reference in zip(upgraded.candidates, expected.candidates):
        assert actual.assessment.to_dict() == reference.assessment.to_dict()


def test_default_v1_and_explicit_v2_do_not_admit_common_study3():
    raw = design(count=2).to_dict()
    for schema in ['sipi.yield-design/1', 'sipi.yield-design/2']:
        with pytest.raises(ValueError): YieldDesignDocument.from_dict(dict(raw, schema=schema))
    kwargs = {k: v for k, v in raw.items() if k not in ('schema', 'candidates')}
    with pytest.raises(ValueError): YieldDesignDocument(raw['candidates'], **kwargs)


def test_total_budget_and_detached_normalization_before_any_solve(monkeypatch):
    def forbidden(*args, **kwargs): pytest.fail('parsing or total budget reached fields')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    monkeypatch.setattr(LineQuantityStudyDocument, 'analyze', forbidden)
    doc = design((1., 2.), count=3)
    assert SCHEMA in saved_schemas() and normalize_saved(doc.dumps()) == doc.dumps()
    raw = doc.to_dict(); restored = YieldDesignDocument.from_dict(raw)
    raw['candidates'][0]['study']['study']['parameters']['left_width'] = 1.
    assert restored.dumps() == doc.dumps()
    with pytest.raises(ValueError, match='before any solve'): doc.analyze(max_evaluations=5)
    with pytest.raises(ValueError, match='before any solve'): execute_saved(doc.dumps(), max_evaluations=5)
    with pytest.raises(ValueError, match='before any solve'): design((1., 2.), count=6000).analyze(max_evaluations=10000)
    with pytest.raises(ValueError, match='diagnostics'): execute_saved(doc.dumps(), diagnostics=['characteristic'])


@pytest.mark.parametrize('case', ['schema', 'missing', 'extra', 'quantity', 'frequency', 'legacy_source',
    'deterministic', 'duplicate', 'negative_cost', 'boolean_cost', 'infinite_cost', 'no_target',
    'rounding', 'empty', 'too_many', 'bad_unit'])
def test_strict_fixed_candidates_and_same_frequency(monkeypatch, case):
    raw = design((1., 2.), count=2).to_dict()
    if case == 'schema': raw['schema'] = 'sipi.yield-design/999'
    elif case == 'missing': del raw['cost_unit']
    elif case == 'extra': raw['optimizer'] = 'adaptive'
    elif case == 'quantity': raw['candidates'][1]['study']['quantity'] = 'differential_forward_impedance_real'
    elif case == 'frequency': raw['candidates'][1]['study']['study']['material_evaluation']['frequency_hz'] = 2e9
    elif case == 'legacy_source': raw['candidates'][0]['study'] = raw['candidates'][0]['study']['study']
    elif case == 'deterministic':
        sample = raw['candidates'][0]['study']['study']['sampling']; sample['kind'] = 'sweep'; del sample['seed']
    elif case == 'duplicate': raw['candidates'][1]['name'] = raw['candidates'][0]['name']
    elif case == 'negative_cost': raw['candidates'][0]['cost'] = -1.
    elif case == 'boolean_cost': raw['candidates'][0]['cost'] = True
    elif case == 'infinite_cost': raw['candidates'][0]['cost'] = float('inf')
    elif case == 'no_target': raw['minimum_yield'] = None
    elif case == 'rounding': raw['confidence'] = np.nextafter(1., 0.)
    elif case == 'empty': raw['candidates'] = []
    elif case == 'too_many': raw['candidates'] = raw['candidates']*17
    elif case == 'bad_unit': raw['cost_unit'] = 'cost\n'
    def forbidden(*args, **kwargs): pytest.fail('invalid fixed set reached fields')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    with pytest.raises(ValueError): YieldDesignDocument.from_dict(raw)


def test_unrepresentable_sampling_does_not_return_partial_selection(monkeypatch):
    raw = design((1., 2.), count=8).to_dict()
    raw['candidates'][0]['study']['study']['sampling'] = dict(kind='normal', count=8, seed=3,
        correlation=[[1.]], variables=[dict(name='left_width', mean=1e308, std=1e308)])
    def forbidden(*args, **kwargs): pytest.fail('unrepresentable first sampling reached fields')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    with np.errstate(over='ignore'), pytest.raises(ValueError, match='sampling overflow'):
        YieldDesignDocument.from_dict(raw).analyze(max_evaluations=16)


@pytest.mark.parametrize('text', ['{"schema":1,"schema":1}', '{"x":NaN}', '{"x":Infinity}', '{"x":1e999}'])
def test_duplicate_nonfinite_saved_json_rejected(text):
    with pytest.raises(ValueError): YieldDesignDocument.loads(text)
