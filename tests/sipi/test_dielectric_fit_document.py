# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved fit replay, strict input and pre-optimizer transport budgets."""
import json

import numpy as np
import pytest

from sipi import CrossSection, CrossSectionDocument, stripline
from sipi.dielectric import DebyeDielectric, dielectric_from_dict
from sipi.dielectric_fit import DebyeFitDocument, fit_debye
from sipi.execution import normalize_saved, execute_saved
from sipi.line_model import TransmissionLineDocument

F = np.geomspace(1e6, 1e12, 61)
POLES = [1e8, 1e9, 1e10]
MODEL = DebyeDielectric(2., [.8, 0., 1.2], POLES)


def document(mismatch=False):
    samples = MODEL.permittivity(F)
    real = samples.real+.02*np.cos(np.log(F)) if mismatch else samples.real
    return DebyeFitDocument(F, eps_real=real, eps_loss=-samples.imag, relaxation_hz=POLES,
                           weights=np.geomspace(.5, 2., len(F)), max_error=1e-8)


@pytest.mark.parametrize('mismatch', [False, True])
def test_complete_execution_keeps_separate_error_acceptance_and_exact_direct_result(mismatch):
    doc = document(mismatch); raw = doc.to_dict()
    direct = fit_debye(F, eps_real=raw['eps_real'], eps_loss=raw['eps_loss'], relaxation_hz=POLES,
                      weights=raw['weights'], max_error=raw['max_error'])
    result = execute_saved(doc.dumps(), max_evaluations=len(F))
    assert result['status'] == 'complete' and result['error'] is None
    assert result['input'] == raw and result['result'] == direct.to_dict()
    assert result['result']['accepted'] is (not mismatch)
    assert len(result['result']['residual']['real']) == len(F)
    json.dumps(result, allow_nan=False)


def test_roundtrip_detaches_all_input_arrays_and_resolves_default_weights():
    eps = MODEL.permittivity(F); frequency = F.copy(); real = eps.real.copy(); loss = -eps.imag.copy()
    poles = POLES.copy()
    doc = DebyeFitDocument(frequency, eps_real=real, eps_loss=loss, relaxation_hz=poles, max_error=1e-8)
    saved = doc.dumps(); raw = doc.to_dict(); restored = DebyeFitDocument.from_dict(raw)
    assert raw['weights'] == [1.]*len(F)
    frequency[:]=0;real[:]=1;loss[:]=0;poles[0]=1
    raw['weights'][0] = -1; raw['eps_loss'][0] = 1
    assert doc.dumps() == restored.dumps() == saved == normalize_saved(saved)
    assert DebyeFitDocument.loads(saved).analyze().to_dict() == doc.analyze().to_dict()


def test_valid_normalization_never_runs_matrix_factorization_optimizer_or_fields(monkeypatch):
    import sipi.dielectric_fit as implementation
    raw = document().to_dict()
    def forbidden(*args, **kwargs): pytest.fail('normalization reached numerical fitting or fields')
    monkeypatch.setattr(implementation.np.linalg, 'svd', forbidden)
    monkeypatch.setattr(implementation, 'nnls', forbidden)
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    doc = DebyeFitDocument.from_dict(raw)
    assert normalize_saved(doc.dumps()) == doc.dumps()


def test_caller_budget_rejects_before_matrix_work_and_accepts_exact_sample_count(monkeypatch):
    import sipi.dielectric_fit as implementation
    doc = document(); original = implementation.nnls; calls = []
    with monkeypatch.context() as context:
        def forbidden(*args, **kwargs): pytest.fail('over-budget fit reached numerical work')
        context.setattr(implementation.np.linalg, 'svd', forbidden)
        context.setattr(implementation, 'nnls', forbidden)
        with pytest.raises(ValueError, match='frequency count'): execute_saved(doc.dumps(), max_evaluations=len(F)-1)
    def counted(*args, **kwargs): calls.append(kwargs['maxiter']); return original(*args, **kwargs)
    monkeypatch.setattr(implementation, 'nnls', counted)
    result = execute_saved(doc.dumps(), max_evaluations=len(F))
    assert calls == [10*(len(POLES)+1)] and result['result']['accepted']


def test_numerical_identifiability_and_optimizer_failures_keep_original_exceptions(monkeypatch):
    import sipi.dielectric_fit as implementation
    raw = document().to_dict(); raw['relaxation_hz'] = [1e-300, 2e-300]
    nonidentifiable = DebyeFitDocument.from_dict(raw)
    assert normalize_saved(nonidentifiable.dumps()) == nonidentifiable.dumps()
    def failed(*args, **kwargs): raise RuntimeError('retained optimizer failure')
    monkeypatch.setattr(implementation, 'nnls', failed)
    with pytest.raises(ValueError, match='full rank'): execute_saved(nonidentifiable.dumps())
    with pytest.raises(RuntimeError, match='retained optimizer failure'): execute_saved(document().dumps())


def test_result_material_reuses_existing_saved_line_input():
    output = execute_saved(document().dumps())
    model = dielectric_from_dict(output['result']['model'])
    cross = CrossSectionDocument(stripline(width=.5e-3, plane_spacing=1e-3, thickness=35e-6,
        eps_r=4., box_width=4e-3), mesh=dict(edge_size=10e-6, far_size=.2e-3, grade=.2))
    def line(material):
        return TransmissionLineDocument(cross, [2e7, 3e8, 5e9], materials={'dielectric': material},
            conductor=dict(kind='perfect'), length=.03)
    saved = line(model).dumps()
    actual = TransmissionLineDocument.loads(saved).analyze(); expected = line(MODEL).analyze()
    for key in ('C', 'G', 'L'):
        np.testing.assert_allclose(getattr(actual, key), getattr(expected, key), rtol=1e-8, atol=0)
    np.testing.assert_allclose(actual.network.s, expected.network.s, rtol=0, atol=1e-8)


@pytest.mark.parametrize('case', ['future_schema', 'extra_key', 'missing_weights', 'null_weights',
    'extra_nested', 'bool_frequency', 'bool_loss', 'bool_weight', 'bool_limit', 'duplicate_frequency',
    'duplicate_poles', 'zero_pole', 'negative_loss', 'below_one', 'zero_weight', 'weight_shape',
    'real_shape', 'loss_shape', 'nonfinite_real', 'nonfinite_pole', 'zero_limit'])
def test_strict_saved_input_rejects_without_fitting(monkeypatch, case):
    import sipi.dielectric_fit as implementation
    raw = document().to_dict()
    if case == 'future_schema': raw['schema'] = 'sipi.dielectric-fit/2'
    if case == 'extra_key': raw['extra'] = 1
    if case == 'missing_weights': del raw['weights']
    if case == 'null_weights': raw['weights'] = None
    if case == 'extra_nested': raw['eps_real'][0] = dict(value=2., unit='relative')
    if case == 'bool_frequency': raw['frequency_hz'][0] = True
    if case == 'bool_loss': raw['eps_loss'][0] = False
    if case == 'bool_weight': raw['weights'][0] = True
    if case == 'bool_limit': raw['max_error'] = True
    if case == 'duplicate_frequency': raw['frequency_hz'][1] = raw['frequency_hz'][0]
    if case == 'duplicate_poles': raw['relaxation_hz'][1] = raw['relaxation_hz'][0]
    if case == 'zero_pole': raw['relaxation_hz'][0] = 0
    if case == 'negative_loss': raw['eps_loss'][0] = -.1
    if case == 'below_one': raw['eps_real'][0] = .9
    if case == 'zero_weight': raw['weights'][0] = 0
    if case == 'weight_shape': raw['weights'] = [1.]
    if case == 'real_shape': raw['eps_real'] = [2.]
    if case == 'loss_shape': raw['eps_loss'] = [0.]
    if case == 'nonfinite_real': raw['eps_real'][0] = float('inf')
    if case == 'nonfinite_pole': raw['relaxation_hz'][0] = float('nan')
    if case == 'zero_limit': raw['max_error'] = 0
    def forbidden(*args, **kwargs): pytest.fail('invalid saved input reached fitting')
    monkeypatch.setattr(implementation, 'nnls', forbidden)
    with pytest.raises(ValueError): DebyeFitDocument.from_dict(raw)
    with pytest.raises(ValueError): normalize_saved(json.dumps(raw))


@pytest.mark.parametrize('text', ['null', '[]', '{"schema":"sipi.dielectric-fit/1","schema":"sipi.dielectric-fit/1"}',
    '{"schema":"sipi.dielectric-fit/1","max_error":NaN}',
    '{"schema":"sipi.dielectric-fit/1","max_error":Infinity}',
    '{"schema":"sipi.dielectric-fit/1","max_error":1e999}'])
def test_duplicate_nonfinite_or_nonobject_json_rejects(text):
    with pytest.raises(ValueError): DebyeFitDocument.loads(text)
    with pytest.raises(ValueError): normalize_saved(text)


def test_line_diagnostics_and_input_byte_limit_reject_before_optimizer(monkeypatch):
    import sipi.dielectric_fit as implementation
    doc = document()
    def forbidden(*args, **kwargs): pytest.fail('rejected transport request reached optimizer')
    monkeypatch.setattr(implementation, 'nnls', forbidden)
    with pytest.raises(ValueError, match='diagnostics'): execute_saved(doc.dumps(), diagnostics=['modes'])
    with pytest.raises(ValueError): execute_saved(doc.dumps(), max_input_bytes=10)
