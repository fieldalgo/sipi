# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Simultaneous binomial bounds, fixed selection and actual saved FEM replay."""
from fractions import Fraction
import json
import math

import numpy as np
import pytest

from sipi import CrossSectionDocument
from sipi.execution import execute_saved, normalize_saved
from sipi.study import ImpedanceStudy, ImpedanceStudyDocument, StudyRow
from sipi.yield_design import YieldDesignDocument
from test_study import document, bounded, normal, PARAMETERS, MESH
from test_yield_assessment import independent_interval


def design(costs=(3., 1., 2.), *, count=40, confidence=.95, target=.8):
    return YieldDesignDocument([dict(name=f'candidate-{i}', cost=cost,
        study=document(bounded('uniform', count)).to_dict()) for i, cost in enumerate(costs)],
        cost_unit='relative fabrication cost', minimum=45, maximum=55,
        minimum_yield=target, confidence=confidence)


def inject(monkeypatch, outcomes):
    calls = []
    def analyze(self, *, max_evaluations):
        values = outcomes[len(calls)]; calls.append(self.dumps())
        data = self.to_dict()
        assert len(values) == data['sampling']['count']
        rows = tuple(StudyRow(i, params, None, value, 'ValueError' if value is None else None,
            'retained field failure' if value is None else None)
            for i, (params, value) in enumerate(zip(self.sample_parameters(), values)))
        return ImpedanceStudy(self.dumps(), data['quantity'], rows, None)
    monkeypatch.setattr(ImpedanceStudyDocument, 'analyze', analyze)
    return calls


@pytest.mark.parametrize('count', [1, 2, 3, 7, 32])
@pytest.mark.parametrize('confidence', [.1, .5, .9, .95, .999])
def test_family_error_budget_and_independent_binomial_bounds(monkeypatch, count, confidence):
    inject(monkeypatch, [[50.]*7+[80.]*3]*count)
    result = design([1.]*count, count=10, confidence=confidence).analyze(max_evaluations=10*count)
    level = result.candidate_confidence
    # Exact rational arithmetic on stored binary64 values: rounding cannot
    # weaken the requested family confidence, even for perfectly correlated candidates.
    assert (1-Fraction(level))*count <= 1-Fraction(confidence)
    assert level >= confidence
    np.testing.assert_allclose(result.candidates[0].assessment.confidence_interval,
                               independent_interval(7, 10, level), rtol=0, atol=1e-12)
    assert all(c.assessment.confidence_interval == result.candidates[0].assessment.confidence_interval
               for c in result.candidates)


def test_coverage_by_exact_enumeration_and_union_bound(monkeypatch):
    # Finite independent reference: enumerate every possible binomial count,
    # not a Monte Carlo histogram or a comparison to the same special function.
    doc = design((1, 2, 3), count=8, confidence=.9)
    for p in (.01, .2, .5, .8, .99):
        errors = []
        for k in range(9):
            inject(monkeypatch, [[50.]*k+[80.]*(8-k)]*3)
            result = doc.analyze(max_evaluations=24)
            low, high = result.candidates[0].assessment.confidence_interval
            errors.append((not low <= p <= high)*math.comb(8, k)*p**k*(1-p)**(8-k))
        assert 3*math.fsum(errors) <= .1+1e-14


def test_cheaper_uncertain_candidate_does_not_disappear_and_ties_use_input_order(monkeypatch):
    doc = design((4., 1., 2., 2.))
    calls = inject(monkeypatch, [[50.]*40, [None]*40, [50.]*40, [50.]*40])
    out = execute_saved(doc.dumps(), max_evaluations=160)
    result = out['result']
    assert len(calls) == 4 and result['evaluations'] == 160
    assert out['status'] == 'incomplete' and result['status'] == 'selected'
    assert result['selected'] == dict(index=2, name='candidate-2', cost=2.)
    assert result['candidates'][1]['assessment']['goal_status'] == 'undetermined'
    assert len(result['candidates'][1]['assessment']['rows']) == 40
    assert result['candidates'][1]['assessment']['rows'][0]['error'] == 'retained field failure'
    assert result['unresolved'] == 40
    assert all(c['study'] == d['study'] for c, d in zip(result['candidates'], doc.to_dict()['candidates']))
    json.dumps(out, allow_nan=False)


@pytest.mark.parametrize('values,status', [([80.]*40, 'none-certified'), ([None]*40, 'undetermined'),
                                          ([50.]*20+[80.]*20, 'none-certified')])
def test_no_selection_preserves_every_rejected_or_uncertain_candidate(monkeypatch, values, status):
    inject(monkeypatch, [values]*3)
    result = design().analyze()
    assert result.status == status and result.selected_index is None
    assert len(result.candidates) == 3 and result.to_dict()['selected'] is None


def test_required_target_zero_and_one_are_explicit_endpoint_contracts(monkeypatch):
    inject(monkeypatch, [[None]*2])
    result = design((0,), count=2, target=0).analyze()
    assert result.status == 'selected' and result.unresolved == 2
    inject(monkeypatch, [[50.]*40])
    assert design((0,), target=1).analyze().status == 'undetermined'


def test_shared_seeds_and_within_row_correlations_do_not_require_candidate_independence(monkeypatch):
    data = design((1, 2), count=40).to_dict()
    for candidate in data['candidates']:
        candidate['study'] = document(normal(40)).to_dict()
    calls = inject(monkeypatch, [[50.]*40]*2)
    result = YieldDesignDocument.from_dict(data).analyze()
    assert calls[0] == calls[1]
    assert result.candidates[0].assessment.to_dict()['sampling_model']['correlation'] == normal(40)['correlation']


def test_actual_field_replay_matches_every_independent_study():
    doc = design((1, 2), count=2, target=.9)
    data = doc.to_dict()
    data['candidates'][1]['study']['parameters']['eps_r'] = 3.5
    # Broad limits isolate actual field replay and finite-sample uncertainty;
    # this fixture is not a nominal 50-ohm geometry.
    data.update(minimum=1., maximum=1000.)
    doc = YieldDesignDocument.from_dict(data)
    report = execute_saved(doc.dumps(), max_evaluations=4)
    assert report['status'] == 'complete' and report['result']['status'] == 'undetermined'
    assert report['result']['evaluations'] == 4
    for inp, out in zip(data['candidates'], report['result']['candidates']):
        direct = ImpedanceStudyDocument.from_dict(inp['study']).analyze(max_evaluations=2)
        np.testing.assert_allclose([r.impedance for r in direct.rows],
            [r['impedance_ohm'] for r in out['assessment']['rows']], rtol=1e-12)
        assert [dict(r.parameters) for r in direct.rows] == [r['parameters'] for r in out['assessment']['rows']]


def test_whole_candidate_budget_is_checked_before_first_solve(monkeypatch):
    doc = design((1, 2), count=3)
    def forbidden(*args, **kwargs): pytest.fail('parsing or total-budget rejection reached field solve')
    monkeypatch.setattr(CrossSectionDocument, 'analyze', forbidden)
    assert normalize_saved(doc.dumps()) == doc.dumps()
    with pytest.raises(ValueError, match='before any solve'):
        execute_saved(doc.dumps(), max_evaluations=5)
    for bad in (True, 1, 10001, 1.5):
        with pytest.raises(ValueError): doc.analyze(max_evaluations=bad)
    with pytest.raises(ValueError, match='before any solve'):
        design((1, 2), count=6000).analyze(max_evaluations=10000)


def test_strict_saved_input_and_detached_snapshots():
    doc = design(count=2)
    restored = YieldDesignDocument.loads(doc.dumps())
    data = doc.to_dict(); data['candidates'][0]['study']['parameters']['width'] = 99
    assert doc.dumps() == restored.dumps() == normalize_saved(doc.dumps())
    bad = []
    for field, value in [('schema', 'sipi.yield-design/3'), ('extra', 1), ('confidence', True),
            ('confidence', math.nextafter(1., 0.)), ('minimum_yield', None), ('minimum_yield', 1.1),
            ('cost_unit', ''), ('cost_unit', 'money\n'), ('cost_unit', 'x'*129),
            ('candidates', []), ('candidates', {}), ('candidates', doc.to_dict()['candidates']*11)]:
        x = doc.to_dict(); x[field] = value; bad.append(x)
    for field, value in [('name', 'candidate-1'), ('name', True), ('name', 'bad\tname'),
            ('name', 'bad\u2028name'), ('name', 'bad\x85name'), ('cost', -1),
            ('cost', True), ('cost', float('inf')), ('cost', 10**400), ('extra', 'unknown')]:
        x = doc.to_dict(); x['candidates'][0][field] = value; bad.append(x)
    x = doc.to_dict(); del x['candidates'][0]['cost']; bad.append(x)
    x = doc.to_dict(); del x['confidence']; bad.append(x)
    x = doc.to_dict(); x['candidates'][0]['study'] = document(bounded()).to_dict(); bad.append(x)
    x = doc.to_dict(); x['candidates'][0]['study'] = ImpedanceStudyDocument('coupled_microstrip',
        dict(PARAMETERS, gap=.3e-3), sampling=bounded('uniform', 2), quantity='z_diff', mesh=MESH).to_dict(); bad.append(x)
    for data in bad:
        with pytest.raises(ValueError): YieldDesignDocument.from_dict(data)
    for replacement in ('NaN', '1e999', '0.95,"confidence":0.95'):
        text = doc.dumps().replace('"confidence": 0.95', '"confidence": '+replacement)
        for load in (YieldDesignDocument.loads, normalize_saved):
            with pytest.raises(ValueError): load(text)


def test_study_four_material_provenance_is_preserved(monkeypatch):
    from test_material_variables import plan
    data = design((1, 2), count=2).to_dict()
    study = plan(sampling=dict(kind='uniform', count=2, seed=17,
        variables=[dict(name='dk', lower=3.8, upper=4.2)]))
    for c in data['candidates']: c['study'] = study.to_dict()
    def failed(*args, **kwargs): raise ValueError('material field failure')
    monkeypatch.setattr('sipi.study._analyze_material', failed)
    report = execute_saved(YieldDesignDocument.from_dict(data).dumps(), max_evaluations=4)
    assert report['status'] == 'incomplete' and report['result']['unresolved'] == 4
    for candidate in report['result']['candidates']:
        assert [row['material_evaluation'] for row in candidate['assessment']['rows']] == study.sample_material_evaluations()
