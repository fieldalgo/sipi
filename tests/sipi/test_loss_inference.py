# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent scalar loss inversion, physical constraints and failure contracts."""
import json

import numpy as np
import pytest
from scipy.linalg import expm

from sipi import infer_shunt_loss, rlgc_propagation


def inputs():
    return dict(frequency=np.geomspace(1e5, 1e10, 21), alpha=np.linspace(.2, 30, 21),
                R=0., L=400e-9, C=150e-12, max_error_np_per_m=1e-9)


def test_zero_resistance_analytic_inverse(record_property):
    kw = inputs()
    result = infer_shunt_loss(**kw)
    w = 2*np.pi*kw['frequency']
    a, l, c = kw['alpha'], kw['L'], kw['C']
    exact = 2*a*np.sqrt(a*a+w*w*l*c)/(w*l)
    error = float(np.max(abs(result.conductance/exact-1)))
    record_property('analytic_relative_error', error)
    assert error < 1e-10
    assert result.accepted
    np.testing.assert_array_equal(result.alpha_zero_shunt, 0)
    np.testing.assert_allclose(result.effective_loss_tangent, exact/(w*c), rtol=1e-10)


def test_independent_telegrapher_exponential_eigenvalues(record_property):
    f = inputs()['frequency']
    r = 50+2*np.sqrt(f/1e9)
    l, c, length = 400e-9, 150e-12, .03
    g = 2*np.pi*f*c*.02
    alpha = []
    for fi, ri, gi in zip(f, r, g):
        # Independent finite-length voltage/current transfer, no gamma square root.
        transfer = expm(np.array([[0, ri+2j*np.pi*fi*l], [gi+2j*np.pi*fi*c, 0]])*length)
        alpha.append(np.log(max(abs(np.linalg.eigvals(transfer))))/length)
    result = infer_shunt_loss(f, alpha=alpha, R=r, L=l, C=c, max_error_np_per_m=1e-9)
    error = float(np.max(abs(result.conductance/g-1)))
    record_property('expm_conductance_relative_error', error)
    record_property('expm_alpha_absolute_error', result.maximum_error_np_per_m)
    assert error < 1e-7
    assert result.maximum_error_np_per_m < 1e-9
    assert result.accepted


@pytest.mark.parametrize('r,g', [(0, .1), (100, 0), (2, .002), (1e4, 1e-6), (1e-3, 10)])
def test_low_and_high_loss_forward_replay_and_power(r, g):
    f = inputs()['frequency']
    p = rlgc_propagation(f, R=[[r]], L=[[400e-9]], C=[[150e-12]], G=[[g]])
    result = infer_shunt_loss(f, alpha=p.alpha[:, 0], R=r, L=400e-9, C=150e-12, max_error_np_per_m=1e-9)
    np.testing.assert_allclose(result.conductance, g, rtol=1e-8, atol=0)
    np.testing.assert_allclose(result.propagation.alpha, p.alpha, rtol=1e-10, atol=0)
    np.testing.assert_allclose(result.propagation.alpha_conductor+result.propagation.alpha_dielectric,
                               result.propagation.alpha, rtol=1e-10)
    assert np.all(result.conductance >= 0) and result.accepted


def test_below_baseline_preserves_input_and_constrained_candidate():
    f = [1e6, 1e9]
    kw = dict(alpha=[0, 0], R=100., L=400e-9, C=150e-12)
    result = infer_shunt_loss(f, **kw, max_error_np_per_m=1e-6)
    assert not result.accepted
    np.testing.assert_array_equal(result.conductance, 0)
    np.testing.assert_array_equal(result.alpha_input, 0)
    np.testing.assert_array_equal(result.residual, result.alpha_zero_shunt)
    np.testing.assert_array_equal(result.evaluations, 1)
    loose = infer_shunt_loss(f, **kw, max_error_np_per_m=10)
    assert loose.accepted  # Error limit does not change the physical candidate.
    np.testing.assert_array_equal(loose.conductance, result.conductance)
    assert json.loads(json.dumps(result.to_dict(), allow_nan=False))['accepted'] is False


def test_zero_loss_and_frequency_dependent_rlc_and_copy():
    kw = inputs()
    kw.update(alpha=np.zeros(21), R=np.zeros(21), L=np.linspace(300e-9, 500e-9, 21),
              C=np.linspace(100e-12, 200e-12, 21))
    result = infer_shunt_loss(**kw)
    for name in ('frequency', 'alpha', 'R', 'L', 'C'):
        kw[name][:] = -1
    np.testing.assert_array_equal(result.conductance, 0)
    np.testing.assert_array_equal(result.propagation.alpha, 0)
    assert result.accepted
    for name in ('alpha_input', 'resistance', 'inductance', 'capacitance', 'conductance',
                 'alpha_zero_shunt', 'evaluations', 'effective_loss_tangent', 'residual'):
        assert not getattr(result, name).flags.writeable
    assert np.all(result.inductance > 0)
    record = result.to_dict()
    record['L_h_per_m'][0] = -1
    assert result.inductance[0] > 0


@pytest.mark.parametrize('key,value', [
    ('frequency', []), ('frequency', [0]), ('frequency', [1, 1]), ('frequency', [2, 1]),
    ('frequency', [True]), ('frequency', np.arange(1, 10002)),
    ('alpha', 1.), ('alpha', [-1]*21), ('alpha', [1]*20), ('alpha', [np.nan]*21),
    ('alpha', [True]*21), ('alpha', [1+0j]*21),
    ('R', -1), ('R', True), ('R', [1]*20), ('R', [[1]]), ('R', np.inf),
    ('L', 0), ('L', -1), ('L', True), ('L', 1j), ('C', 0), ('C', '1'), ('C', np.nan),
    ('max_error_np_per_m', 0), ('max_error_np_per_m', True), ('max_error_np_per_m', np.inf),
], ids=lambda v: str(v) if not isinstance(v, (list, np.ndarray)) else 'array')
def test_invalid_inputs_rejected_before_root(monkeypatch, key, value):
    import sipi.loss_inference as module
    monkeypatch.setattr(module, 'brentq', lambda *a, **k: pytest.fail('invalid input reached root'))
    kw = inputs(); kw[key] = value
    with pytest.raises(ValueError):
        infer_shunt_loss(**kw)


def test_single_sample_and_exact_acceptance_boundary():
    result = infer_shunt_loss([1e9], alpha=[0], R=100, L=400e-9, C=150e-12, max_error_np_per_m=10)
    at = infer_shunt_loss([1e9], alpha=[0], R=100, L=400e-9, C=150e-12,
                          max_error_np_per_m=result.maximum_error_np_per_m)
    assert at.accepted


def test_fixed_iteration_policy_and_failure_transport(monkeypatch):
    import sipi.loss_inference as module
    original = module.brentq
    seen = []
    def root(*args, **kwargs):
        seen.append(kwargs)
        return original(*args, **kwargs)
    monkeypatch.setattr(module, 'brentq', root)
    result = infer_shunt_loss(**inputs())
    assert len(seen) == 21
    assert all(k['maxiter'] == 128 and k['rtol'] == 8*np.finfo(float).eps for k in seen)
    assert np.all(result.evaluations > 1)
    def fail(*args, **kwargs):
        raise RuntimeError('retained root failure')
    monkeypatch.setattr(module, 'brentq', fail)
    with pytest.raises(RuntimeError, match='retained root failure'):
        infer_shunt_loss(**inputs())


@pytest.mark.parametrize('changes', [dict(frequency=[1e308], alpha=[1]),
    dict(frequency=[1], alpha=[1], L=1e308, C=1e308),
    dict(frequency=[1], alpha=[1], L=1e-300, C=1e-300),
    dict(frequency=[1], alpha=[1e100], L=1, C=1)], ids=['frequency', 'product', 'underflow', 'bracket'])
def test_unrepresentable_or_unbracketed_not_reported_as_fit(changes):
    kw = inputs(); kw.update(changes)
    with pytest.raises((ValueError, RuntimeError)):
        infer_shunt_loss(**kw)
