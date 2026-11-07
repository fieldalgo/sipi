# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Fixed-pole coefficient fits, analytical active sets and independent bounds."""
from importlib import metadata
import json

import numpy as np
import pytest

from sipi.dielectric import DebyeDielectric, dielectric_from_dict
from sipi.dielectric_fit import fit_debye
from crosscheck import require_tool, Stopwatch, emit, make_record, observable

F = np.geomspace(1e6, 1e12, 61)
POLES = np.array([1e8, 1e9, 1e10])


def fit(model=None, **changes):
    model = DebyeDielectric(2., [.8, .6, 1.2], POLES) if model is None else model
    eps = model.permittivity(F)
    args = dict(eps_real=eps.real, eps_loss=-eps.imag,
                relaxation_hz=list(model.relaxation_hz), max_error=1e-8)
    args.update(changes)
    return fit_debye(F, **args)


@pytest.mark.parametrize('base,strengths', [(2., [.8, .6, 1.2]), (2., [.8, 0., 1.2]),
    (1., [.8, .6, 1.2]), (4., [0., 0., 0.]), (1., [0., 0., 0.])])
def test_synthetic_coefficients_static_high_frequency_limits_and_passivity(base, strengths):
    model = DebyeDielectric(base, strengths, POLES)
    result = fit(model)
    np.testing.assert_allclose([result.model.eps_inf, *result.model.strengths], [base, *strengths], atol=1e-8, rtol=0)
    assert result.accepted and result.maximum_error < 1e-8 and result.scaled_kkt_error <= 1e-10
    assert result.condition < 1e10 and all(x >= 0 for x in result.model.strengths)
    np.testing.assert_allclose(result.model.permittivity([0]).real, [base+sum(strengths)], atol=1e-8, rtol=0)
    np.testing.assert_allclose(result.model.permittivity([1e30]).real, [base], atol=1e-8, rtol=0)
    outside = result.model.permittivity(np.geomspace(1e-10, 1e30, 81))
    assert np.all(outside.real >= 1) and np.all(outside.imag <= 0)
    # This checks the Debye law, not physical material validity at these frequencies.
    restored = dielectric_from_dict(result.to_dict()['model'])
    np.testing.assert_array_equal(restored.permittivity(F), result.predicted)


def one_pole_active_set(frequency, real, loss):
    # Independent two-variable normal equations with exhaustive boundary candidates.
    r = 1/(1+frequency**2); l = frequency/(1+frequency**2); y = real-1
    aa, ab, bb = len(frequency), sum(r), sum(r*r+l*l)
    ay, by = sum(y), sum(r*y+l*loss)
    determinant = aa*bb-ab*ab
    interior = np.array([(ay*bb-ab*by)/determinant, (aa*by-ab*ay)/determinant])
    candidates = [np.array([max(ay/aa, 0), 0]), np.array([0, max(by/bb, 0)]), np.zeros(2)]
    if np.all(interior >= 0): candidates.append(interior)
    return min(candidates, key=lambda x: sum((x[0]+r*x[1]-y)**2+(l*x[1]-loss)**2))


@pytest.mark.parametrize('case', ['interior', 'constant-boundary', 'baseline-boundary', 'zero'])
def test_single_pole_matches_analytical_boundary_enumeration(case):
    f = np.array([0., .1, 1., 10.])
    if case == 'interior':
        eps = DebyeDielectric(2., [3.], [1.]).permittivity(f); real, loss = eps.real, -eps.imag
    elif case == 'constant-boundary': real, loss = np.array([2., 2.5, 3., 3.5]), np.zeros(4)
    elif case == 'baseline-boundary': real, loss = np.ones(4), np.array([0., .2, 1., .3])
    else: real, loss = np.ones(4), np.zeros(4)
    expected = one_pole_active_set(f, real, loss)
    result = fit_debye(f, eps_real=real, eps_loss=loss, relaxation_hz=[1.], max_error=1e-8)
    np.testing.assert_allclose([result.model.eps_inf-1, *result.model.strengths], expected, atol=1e-10, rtol=0)
    assert result.scaled_kkt_error <= 1e-10
    if case in ('constant-boundary', 'baseline-boundary'):
        assert not result.accepted and result.maximum_error > .01


def test_independent_bounded_least_squares_and_retained_nonfit_data():
    require_tool('scipy')
    from scipy.optimize import lsq_linear
    clock = Stopwatch()
    model = DebyeDielectric(2., [.8, 0., 1.2], POLES)
    eps = model.permittivity(F)
    real = eps.real+.01*np.cos(np.log(F)); loss = -eps.imag*(1+.08*np.sin(np.log(F)))
    weights = np.geomspace(.5, 3., len(F))
    with clock('openphysics'):
        actual = fit_debye(F, eps_real=real, eps_loss=loss, relaxation_hz=POLES, weights=weights, max_error=1e-5)
    with clock('reference'):
        # Direct complex relaxation division and a separate bounded optimizer.
        basis = np.column_stack([np.ones(len(F)), 1/(1+1j*F[:, None]/POLES)])
        a = np.vstack([basis.real*np.sqrt(weights[:, None]), -basis.imag*np.sqrt(weights[:, None])])
        b = np.r_[(real-1)*np.sqrt(weights), loss*np.sqrt(weights)]
        reference = lsq_linear(a, b, bounds=(0., np.inf), method='bvls', tol=1e-14, max_iter=1000)
        assert reference.success
        expected = 1+basis@reference.x
    coefficient_error = float(np.max(abs(np.r_[actual.model.eps_inf-1, actual.model.strengths]-reference.x)))
    prediction_error = float(np.max(abs(actual.predicted-expected)))
    record = make_record(case='fixed-pole-debye-fit', physics='passive scalar dielectric relaxation',
        api='sipi.dielectric_fit.fit_debye', discretization='normalized fixed-pole nonnegative least squares',
        tool='scipy', tool_discretization='independent complex basis and optimize.lsq_linear bounded variable least squares',
        matched=['identical fixed poles, sampled complex permittivity, positive weights and coefficient bounds'],
        not_matched=['both algorithms use SciPy numerical primitives; separate analytic active-set tests also apply',
                     'no measured material, pole selection, uncertainty or unsampled validity evidence'],
        observables=[observable('coefficients', '1', 'max absolute difference', coefficient_error, 1e-8),
                     observable('predicted permittivity', '1', 'max absolute difference', prediction_error, 1e-8)],
        analytical_acceptance='exhaustive one-pole boundary optima, synthetic multi-pole recovery, KKT and Debye limits',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi', version=metadata.version('sipi')); emit(record)
    assert max(coefficient_error, prediction_error) < 1e-8
    assert not actual.accepted
    np.testing.assert_array_equal(actual.eps_real, real)
    np.testing.assert_array_equal(actual.eps_loss, loss)
    np.testing.assert_allclose(actual.residual, expected-(real-1j*loss), atol=1e-8, rtol=0)
    assert actual.maximum_error == pytest.approx(np.max(abs(actual.residual)), rel=1e-12)
    assert actual.weighted_rms_error == pytest.approx(np.sqrt(np.sum(weights*abs(actual.residual)**2)/sum(weights)), rel=1e-12)
    exact_limit = fit_debye(F, eps_real=real, eps_loss=loss, relaxation_hz=POLES,
        weights=weights, max_error=actual.maximum_error)
    assert exact_limit.accepted


def test_weight_scale_invariance_and_inputs_outputs_are_detached():
    model = DebyeDielectric(2., [.8, 0., 1.2], POLES); eps = model.permittivity(F)
    frequency = F.copy(); real = eps.real.copy(); loss = -eps.imag.copy(); poles = POLES.copy()
    weights = np.geomspace(1., 100., len(F))
    first = fit_debye(frequency, eps_real=real, eps_loss=loss, relaxation_hz=poles, weights=weights, max_error=1e-8)
    second = fit_debye(frequency, eps_real=real, eps_loss=loss, relaxation_hz=poles, weights=weights*1e200, max_error=1e-8)
    np.testing.assert_allclose(first.predicted, second.predicted, rtol=0, atol=1e-10)
    np.testing.assert_allclose(first.model.strengths, second.model.strengths, rtol=0, atol=1e-10)
    frequency[:]=0;real[:]=1;loss[:]=0;poles[:]=1;weights[:]=1
    np.testing.assert_array_equal(first.frequency, F)
    np.testing.assert_array_equal(first.eps_real, eps.real)
    np.testing.assert_array_equal(first.model.relaxation_hz, POLES)
    for name in ('frequency', 'eps_real', 'eps_loss', 'weights', 'predicted', 'residual'):
        assert not getattr(first, name).flags.writeable
    raw = first.to_dict(); json.dumps(raw, allow_nan=False)
    raw['frequency_hz'][0] = 0; raw['model']['parameters']['strengths'][0] = -1
    assert first.to_dict()['frequency_hz'][0] == F[0] and first.model.strengths[0] >= 0


def test_extreme_frequencies_do_not_overflow_relaxation_basis():
    f = np.array([0., 1e100, 1e200, 1e308]); poles = [1e100, 1e200]
    model = DebyeDielectric(2., [1., 3.], poles); eps = model.permittivity(f)
    with np.errstate(over='raise', invalid='raise', divide='raise'):
        result = fit_debye(f, eps_real=eps.real, eps_loss=-eps.imag, relaxation_hz=poles, max_error=1e-8)
    assert result.accepted
    np.testing.assert_allclose([result.model.eps_inf, *result.model.strengths], [2., 1., 3.], rtol=0, atol=1e-8)


def test_fitted_material_reuses_existing_saved_line_and_forward_extraction():
    from sipi import CrossSectionDocument, stripline
    from sipi.line_model import TransmissionLineDocument
    original = DebyeDielectric(2., [1., 2.], [1e8, 1e9])
    fitted = fit(original)
    cross = CrossSectionDocument(stripline(width=.5e-3, plane_spacing=1e-3, thickness=35e-6,
        eps_r=4., box_width=4e-3), mesh=dict(edge_size=10e-6, far_size=.2e-3, grade=.2))
    def line(material):
        return TransmissionLineDocument(cross, [2e7, 3e8, 5e9], materials={'dielectric': material},
            conductor=dict(kind='perfect'), length=.04)
    doc = line(fitted.model)
    restored = TransmissionLineDocument.loads(doc.dumps())
    actual, expected = restored.analyze(), line(original).analyze()
    for key in ('C', 'G', 'L'):
        np.testing.assert_allclose(getattr(actual, key), getattr(expected, key), rtol=1e-8, atol=0)
    np.testing.assert_allclose(actual.network.s, expected.network.s, rtol=0, atol=1e-8)


@pytest.mark.parametrize('case', ['few_samples', 'many_samples', 'duplicate_frequency', 'negative_frequency',
    'boolean_frequency', 'nonfinite_frequency', 'empty_poles', 'many_poles', 'duplicate_poles', 'negative_pole',
    'boolean_pole', 'nonfinite_pole', 'real_shape', 'loss_shape', 'below_one', 'negative_loss',
    'boolean_real', 'complex_loss', 'infinite_real', 'nan_loss', 'zero_weight', 'negative_weight',
    'boolean_weight', 'weight_shape', 'infinite_weight', 'zero_limit', 'boolean_limit', 'infinite_limit',
    'rank_deficient', 'ill_conditioned'])
def test_invalid_inputs_and_nonidentifiable_basis_reject_before_optimizer(monkeypatch, case):
    import sipi.dielectric_fit as implementation
    f = F.copy(); eps = DebyeDielectric(2., [.8, .6, 1.2], POLES).permittivity(f)
    args = dict(eps_real=eps.real.copy(), eps_loss=-eps.imag.copy(), relaxation_hz=POLES.copy(),
                weights=np.ones(len(f)), max_error=1e-8)
    if case == 'few_samples': f = [1.]
    if case == 'many_samples': f = np.arange(10001.)
    if case == 'duplicate_frequency': f[1] = f[0]
    if case == 'negative_frequency': f[0] = -1
    if case == 'boolean_frequency': f = [False, True]
    if case == 'nonfinite_frequency': f[-1] = np.inf
    if case == 'empty_poles': args['relaxation_hz'] = []
    if case == 'many_poles': args['relaxation_hz'] = np.arange(1,34.)
    if case == 'duplicate_poles': args['relaxation_hz'][1] = POLES[0]
    if case == 'negative_pole': args['relaxation_hz'][0] = -1
    if case == 'boolean_pole': args['relaxation_hz'] = [True]
    if case == 'nonfinite_pole': args['relaxation_hz'] = [np.inf]
    if case == 'real_shape': args['eps_real'] = [[2.]*len(f)]
    if case == 'loss_shape': args['eps_loss'] = [0.]
    if case == 'below_one': args['eps_real'][0] = .9
    if case == 'negative_loss': args['eps_loss'][0] = -.1
    if case == 'boolean_real': args['eps_real'] = [True]*len(f)
    if case == 'complex_loss': args['eps_loss'] = np.ones(len(f), dtype=complex)
    if case == 'infinite_real': args['eps_real'][0] = np.inf
    if case == 'nan_loss': args['eps_loss'][0] = np.nan
    if case == 'zero_weight': args['weights'][0] = 0
    if case == 'negative_weight': args['weights'][0] = -1
    if case == 'boolean_weight': args['weights'] = [True]*len(f)
    if case == 'weight_shape': args['weights'] = 1.
    if case == 'infinite_weight': args['weights'][0] = np.inf
    if case == 'zero_limit': args['max_error'] = 0
    if case == 'boolean_limit': args['max_error'] = True
    if case == 'infinite_limit': args['max_error'] = np.inf
    if case == 'rank_deficient': args['relaxation_hz'] = [1e-300, 2e-300]
    if case == 'ill_conditioned': args['relaxation_hz'] = [1e9, 1e9*(1+1e-12)]
    def forbidden(*args, **kwargs): pytest.fail('invalid or ill-conditioned fit reached optimizer')
    monkeypatch.setattr(implementation, 'nnls', forbidden)
    with pytest.raises(ValueError): fit_debye(f, **args)


@pytest.mark.parametrize('kind', ['failure', 'negative', 'nonfinite', 'not_optimal'])
def test_optimizer_failure_or_invalid_certificate_never_returns_accepted_fit(monkeypatch, kind):
    import sipi.dielectric_fit as implementation
    def fake(matrix, rhs, *, maxiter):
        assert maxiter == 10*matrix.shape[1]
        if kind == 'failure': raise RuntimeError('retained optimizer failure')
        coefficients = np.zeros(matrix.shape[1])
        if kind == 'negative': coefficients[0] = -1.
        if kind == 'nonfinite': coefficients[0] = np.nan
        return coefficients, 0.
    monkeypatch.setattr(implementation, 'nnls', fake)
    with pytest.raises(RuntimeError): fit()
