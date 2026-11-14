# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Fixed coated candidates retain unknown samples and simultaneous bounds."""
from fractions import Fraction

import numpy as np
import pytest

from sipi import CrossSection
from sipi.line_study import LineQuantityStudyDocument
from sipi.line_yield import assess_line_yield
from sipi.yield_design import YieldDesignDocument
from sipi.execution import execute_saved, normalize_saved
from test_layered_study import document as study
from test_yield_assessment import independent_interval


def document(quantity='impedance_real'):
    valid = study(quantity, sampling=dict(kind='uniform', count=4, seed=123,
        variables=[dict(name='width', lower=.45e-3, upper=.55e-3)])).to_dict()
    unknown = study(quantity, sampling=dict(kind='uniform', count=4, seed=123,
        variables=[dict(name='thickness', lower=1e-6, upper=60e-6)])).to_dict()
    return YieldDesignDocument([dict(name='valid', cost=2., study=valid),
        dict(name='thin-core', cost=1., study=unknown)], cost_unit='relative',
        minimum=0. if quantity == 'attenuation' else 1., maximum=1000.,
        minimum_yield=.1, confidence=.95, schema='sipi.yield-design/4')


@pytest.mark.parametrize('quantity', ['impedance_real', 'attenuation',
    'differential_forward_impedance_real', 'common_forward_impedance_real'])
def test_actual_fixed_candidates_preserve_unresolved_cheaper_rows(quantity):
    doc = document(quantity); result = doc.analyze(max_evaluations=8)
    assert result.status == 'selected' and result.selected_index == 0
    assert result.candidates[0].assessment.goal_status == 'pass'
    assert result.candidates[1].assessment.goal_status == 'undetermined'
    assert result.unresolved > 0 and result.to_dict()['evaluations'] == 8
    assert result.to_dict()['unit'] == ('Np/m' if quantity == 'attenuation' else 'ohm')
    assert (1-Fraction(result.candidate_confidence))*2 <= 1-Fraction(.95)
    for entry, actual in zip(doc.to_dict()['candidates'], result.candidates):
        source = LineQuantityStudyDocument.from_dict(entry['study'])
        direct = assess_line_yield(source.analyze(), minimum=doc.to_dict()['minimum'], maximum=1000.,
            confidence=result.candidate_confidence, minimum_yield=.1)
        assert actual.assessment.to_dict() == direct.to_dict()
        assert actual.to_dict()['study'] == entry['study']
        a = actual.assessment; n = len(a.study.rows)
        expected = (independent_interval(a.passed, n, result.candidate_confidence)[0],
                    independent_interval(a.passed+a.unresolved, n, result.candidate_confidence)[1])
        np.testing.assert_allclose(a.confidence_interval, expected, rtol=0, atol=1e-12)
        for row, values in zip(a.study.rows, source.samples()):
            assert row.sample_values == tuple(values)
            if not row.complete:
                assert row.phase == 'input' and row.error_type == 'ValueError'
    assert result.candidates[1].assessment.study.summary is None


def test_common_execution_reports_incomplete_selection_and_original_inputs():
    doc = document(); direct = doc.analyze(max_evaluations=8).to_dict()
    report = execute_saved(doc.dumps(), max_evaluations=8)
    assert report['status'] == 'incomplete' and report['result'] == direct
    assert report['input'] == doc.to_dict()
    assert report['result']['selected'] == dict(index=0, name='valid', cost=2.)


def test_field_free_copy_and_total_budget(monkeypatch):
    monkeypatch.setattr(CrossSection, 'mesh', lambda *a, **k: pytest.fail('unexpected field solve'))
    doc = document(); raw = doc.to_dict(); restored = YieldDesignDocument.from_dict(raw)
    raw['candidates'][0]['study']['conductor']['reference']['coatings'][0]['conductivity'] = -1
    assert restored.dumps() == doc.dumps() == normalize_saved(doc.dumps())
    with pytest.raises(ValueError, match='before any solve'): doc.analyze(max_evaluations=7)
    with pytest.raises(ValueError, match='before any solve'): execute_saved(doc.dumps(), max_evaluations=7)


@pytest.mark.parametrize('case', ['quantity', 'frequency', 'old-version'])
def test_incompatible_candidate_contracts_reject_before_fields(case, monkeypatch):
    monkeypatch.setattr(CrossSection, 'mesh', lambda *a, **k: pytest.fail('rejection meshed'))
    raw = document().to_dict()
    if case == 'quantity': raw['candidates'][1]['study']['quantity'] = 'attenuation'
    if case == 'frequency': raw['candidates'][1]['study']['study']['material_evaluation']['frequency_hz'] = 2e9
    if case == 'old-version': raw['schema'] = 'sipi.yield-design/3'
    with pytest.raises(ValueError): YieldDesignDocument.from_dict(raw)


def test_legacy_candidate_order_ties_units_and_outcomes_retained(monkeypatch):
    from test_lossy_yield_design import design, inject
    inject(monkeypatch, [[50.]*40, [50.]*40, [50.]*40, [50.]*40])
    old = design((2., 2.)).to_dict(); old['schema'] = 'sipi.yield-design/3'
    new = dict(old, schema='sipi.yield-design/4')
    a = YieldDesignDocument.from_dict(old).analyze().to_dict()
    b = YieldDesignDocument.from_dict(new).analyze().to_dict()
    assert a == b and a['selected']['index'] == 0 and a['unit'] == 'ohm'
