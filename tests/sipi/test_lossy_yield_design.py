# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Fixed lossy candidates, simultaneous bounds and exact saved study replay."""
from fractions import Fraction
import json

import numpy as np
import pytest

from sipi import CrossSection
from sipi.study import ImpedanceStudyDocument
from sipi.line_study import LineQuantityStudyDocument, LineQuantityStudy, LineQuantityStudyRow
from sipi.line_yield import assess_line_yield
from sipi.yield_design import YieldDesignDocument
from sipi.execution import execute_saved, normalize_saved, saved_schemas
from test_line_yield import random_study
from test_differential_line_goal import QUANTITY
from test_yield_assessment import independent_interval

SCHEMA = 'sipi.yield-design/2'


def design(costs=(3., 1., 2.), *, count=40, confidence=.95, target=.8, quantity=QUANTITY):
    return YieldDesignDocument([dict(name=f'candidate-{i}', cost=cost,
        study=random_study(quantity, count).to_dict()) for i, cost in enumerate(costs)],
        cost_unit='relative fabrication cost', minimum=45., maximum=55.,
        minimum_yield=target, confidence=confidence, schema=SCHEMA)


def inject(monkeypatch, outcomes):
    """Selection/statistics fixture; no claim of physical field extraction."""
    calls = []
    def analyze(self, *, max_evaluations):
        values = outcomes[len(calls)]; calls.append(self.dumps()); data = self.to_dict()
        source = ImpedanceStudyDocument.from_dict(data['study'])
        assert len(values) == data['study']['sampling']['count']
        rows = tuple(LineQuantityStudyRow(i, tuple(map(float, sample)), json.dumps(parameters),
            json.dumps(evaluation), None, value, 'diagnostic' if value is None else 'complete',
            'ValueError' if value is None else None, 'retained field failure' if value is None else None)
            for i, (value, sample, parameters, evaluation) in enumerate(zip(values, self.samples(),
                source.sample_parameters(), source.sample_material_evaluations())))
        return LineQuantityStudy(self.dumps(), data['quantity'],
            tuple(v['name'] for v in data['study']['sampling']['variables']), rows, None)
    monkeypatch.setattr(LineQuantityStudyDocument, 'analyze', analyze)
    return calls


@pytest.mark.parametrize('count', [1, 2, 3, 7, 32])
@pytest.mark.parametrize('confidence', [.1, .5, .9, .95, .999])
def test_family_budget_and_independent_binomial_bounds(monkeypatch, count, confidence):
    inject(monkeypatch, [[50.]*7+[80.]*3]*count)
    result = design([1.]*count, count=10, confidence=confidence).analyze(max_evaluations=10*count)
    level = result.candidate_confidence
    assert (1-Fraction(level))*count <= 1-Fraction(confidence)
    assert level >= confidence
    np.testing.assert_allclose(result.candidates[0].assessment.confidence_interval,
                               independent_interval(7, 10, level), rtol=0., atol=1e-12)
    assert all(c.assessment.confidence_interval == result.candidates[0].assessment.confidence_interval
               for c in result.candidates)
    assert result.to_dict()['unit'] == 'ohm'


def test_cheaper_unknown_candidate_and_input_order_tie_remain_visible(monkeypatch):
    doc = design((4., 1., 2., 2.))
    calls = inject(monkeypatch, [[50.]*40, [None]*40, [50.]*40, [50.]*40])
    report = execute_saved(doc.dumps(), max_evaluations=160); result = report['result']
    assert len(calls) == 4 and result['evaluations'] == 160
    assert report['status'] == 'incomplete' and result['status'] == 'selected'
    assert result['selected'] == dict(index=2, name='candidate-2', cost=2.)
    assert result['candidates'][1]['assessment']['goal_status'] == 'undetermined'
    assert result['unresolved'] == 40 and len(result['candidates'][1]['assessment']['rows']) == 40
    assert result['candidates'][1]['assessment']['rows'][0]['phase'] == 'diagnostic'
    assert all(row['study'] == original['study'] for row, original in zip(result['candidates'], doc.to_dict()['candidates']))
    json.dumps(report, allow_nan=False)


@pytest.mark.parametrize('values,status', [([80.]*40, 'none-certified'), ([None]*40, 'undetermined'),
                                          ([50.]*20+[80.]*20, 'none-certified')])
def test_unselected_results_keep_every_candidate(monkeypatch, values, status):
    inject(monkeypatch, [values]*3)
    result = design().analyze()
    assert result.status == status and result.selected_index is None
    assert len(result.candidates) == 3 and result.to_dict()['selected'] is None


def test_scalar_zero_attenuation_keeps_units_and_legacy_output_shape(monkeypatch):
    raw = design((2., 1.), quantity='attenuation').to_dict(); raw.update(minimum=0., maximum=.1)
    inject(monkeypatch, [[0.]*40, [0.]*40])
    result = YieldDesignDocument.from_dict(raw).analyze()
    assert result.selected_index == 1 and result.to_dict()['unit'] == 'Np/m'
    assert result.to_dict()['quantity'] == 'attenuation'
    from test_yield_design import design as legacy_design, inject as legacy_inject
    legacy_inject(monkeypatch, [[50.]*40])
    legacy = legacy_design((1.,)).analyze()
    assert legacy_design().to_dict()['schema'] == 'sipi.yield-design/1'
    assert 'unit' not in legacy.to_dict() and legacy.to_dict()['quantity'] == 'z0'


def test_same_seed_normal_candidates_do_not_require_independent_candidates(monkeypatch):
    raw = design((1., 2.)).to_dict()
    for candidate in raw['candidates']:
        candidate['study'] = random_study(QUANTITY, 40, 'normal').to_dict()
    calls = inject(monkeypatch, [[50.]*40, [50.]*40])
    result = YieldDesignDocument.from_dict(raw).analyze()
    assert calls[0] == calls[1]
    assert all(c.assessment.to_dict()['sampling_model']['correlation'] == [[1.]] for c in result.candidates)


def test_actual_two_paired_candidates_replay_direct_assessments():
    raw = design((2., 1.), count=2, confidence=.9, target=.1).to_dict()
    raw.update(minimum=1., maximum=1000.)
    for entry, low, high in zip(raw['candidates'], [.6e-3, .7e-3], [.7e-3, .8e-3]):
        source = entry['study']['study']; nominal = (low+high)/2
        source['parameters'].update(left_width=nominal, gap=.95e-3-(nominal+.5e-3)/2)
        source['sampling']['variables'] = [dict(name='left_width', lower=low, upper=high)]
    doc = YieldDesignDocument.from_dict(raw); result = doc.analyze(max_evaluations=4)
    assert result.selected_index == 1 and not result.unresolved and result.status == 'selected'
    for entry, candidate in zip(doc.to_dict()['candidates'], result.candidates):
        direct = LineQuantityStudyDocument.from_dict(entry['study']).analyze(max_evaluations=2)
        expected = assess_line_yield(direct, minimum=1., maximum=1000., confidence=result.candidate_confidence,
                                    minimum_yield=.1)
        assert candidate.assessment.to_dict() == expected.to_dict()
        assert candidate.to_dict()['study'] == entry['study']
        for actual, reference in zip(candidate.assessment.study.rows, direct.rows):
            assert actual.to_dict() == reference.to_dict()
            for key in ('R', 'L', 'G', 'C'):
                np.testing.assert_allclose(getattr(actual.result, key), getattr(reference.result, key), rtol=1e-10)
            np.testing.assert_allclose(actual.result.characteristic().z_characteristic,
                                       reference.result.characteristic().z_characteristic, rtol=1e-10)
    json.dumps(result.to_dict(), allow_nan=False)


def test_total_candidate_budget_and_normalization_before_first_field(monkeypatch):
    def forbidden(*args, **kwargs): pytest.fail('parsing or total budget reached fields')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    monkeypatch.setattr(LineQuantityStudyDocument, 'analyze', forbidden)
    doc = design((1., 2.), count=3)
    assert normalize_saved(doc.dumps()) == doc.dumps() and SCHEMA in saved_schemas()
    with pytest.raises(ValueError, match='before any solve'): doc.analyze(max_evaluations=5)
    with pytest.raises(ValueError, match='before any solve'): execute_saved(doc.dumps(), max_evaluations=5)
    with pytest.raises(ValueError, match='before any solve'): design((1., 2.), count=6000).analyze(max_evaluations=10000)
    with pytest.raises(ValueError, match='diagnostics'): execute_saved(doc.dumps(), diagnostics=['characteristic'])


@pytest.mark.parametrize('case', ['v1', 'schema', 'missing', 'extra', 'quantity', 'frequency', 'legacy_source',
    'deterministic', 'duplicate', 'negative_cost', 'no_target', 'rounding'])
def test_strict_lossy_candidates_and_common_frequency_before_fields(monkeypatch, case):
    raw = design((1., 2.), count=2).to_dict()
    if case == 'v1': raw['schema'] = 'sipi.yield-design/1'
    if case == 'schema': raw['schema'] = 'sipi.yield-design/999'
    if case == 'missing': del raw['cost_unit']
    if case == 'extra': raw['optimizer'] = 'adaptive'
    if case == 'quantity': raw['candidates'][1]['study'] = random_study('attenuation', 2).to_dict()
    if case == 'frequency': raw['candidates'][1]['study']['study']['material_evaluation']['frequency_hz'] = 2e9
    if case == 'legacy_source': raw['candidates'][0]['study'] = raw['candidates'][0]['study']['study']
    if case == 'deterministic':
        sample = raw['candidates'][0]['study']['study']['sampling']; sample['kind'] = 'sweep'; del sample['seed']
    if case == 'duplicate': raw['candidates'][1]['name'] = raw['candidates'][0]['name']
    if case == 'negative_cost': raw['candidates'][0]['cost'] = -1.
    if case == 'no_target': raw['minimum_yield'] = None
    if case == 'rounding': raw['confidence'] = np.nextafter(1., 0.)
    def forbidden(*args, **kwargs): pytest.fail('invalid candidate set reached fields')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    with pytest.raises(ValueError): YieldDesignDocument.from_dict(raw)


def test_invalid_sampling_generation_returns_no_partial_selection(monkeypatch):
    raw = design((1., 2.), count=8).to_dict()
    raw['candidates'][0]['study']['study']['sampling'] = dict(kind='normal', count=8, seed=3,
        correlation=[[1.]], variables=[dict(name='left_width', mean=1e308, std=1e308)])
    def forbidden(*args, **kwargs): pytest.fail('unrepresentable first sample generation reached fields')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    with np.errstate(over='ignore'), pytest.raises(ValueError, match='sampling overflow'):
        YieldDesignDocument.from_dict(raw).analyze(max_evaluations=16)
