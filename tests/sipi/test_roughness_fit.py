# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Fixed-radius inverse constitutive law, independent rational data and BVLS."""
import itertools
from importlib import metadata
import numpy as np
import pytest
from scipy.constants import mu_0
from scipy.optimize import lsq_linear
from sipi.conductor import surface_impedance
from sipi.roughness_fit import fit_huray
from crosscheck import Stopwatch, emit, make_record, observable, require_tool

F = np.geomspace(1e6, 1e11, 41)
RADII = np.array([.2e-6, 1.2e-6, 4e-6])
RATIOS = np.array([.7, 2., 1.5])
SIGMA = 58e6


def independent(radii=RADII, ratios=RATIOS, frequency=F):
    # Rational real/imaginary forms computed without the production model.
    delta = 1/np.sqrt(np.pi*frequency*mu_0*SIGMA)
    x = np.asarray(radii)[None, :]/delta[:, None]
    denom = 1+2*x+2*x*x
    response = 1.5*((x+2*x*x)+1j*x)/denom
    smooth = (1+1j)*np.sqrt(np.pi*frequency*mu_0/SIGMA)
    return smooth*(1+response@ratios), smooth, response


def fit(values=None, **kwargs):
    z = independent()[0] if values is None else values
    return fit_huray(F, resistance=z.real, reactance=z.imag, radii_m=RADII,
                     conductivity=SIGMA, max_error_ratio=1e-9, **kwargs)


def test_exact_synthetic_recovers_fixed_radii_ratios_and_surface_law():
    result = fit()
    np.testing.assert_allclose(result.model.surface_ratios, RATIOS, rtol=1e-8, atol=0)
    exact = independent()[0]
    np.testing.assert_allclose(result.predicted, exact, rtol=1e-10, atol=0)
    assert result.accepted and result.maximum_error_ratio < 1e-10
    assert result.condition < 1e10 and result.scaled_kkt_error < 1e-10
    np.testing.assert_array_equal(result.predicted, surface_impedance(F, conductivity=SIGMA, roughness=result.model))
    assert not result.predicted.flags.writeable and not result.normalized_residual.flags.writeable
    assert result.to_dict()['scope'] == 'fixed-radii-sampled-surface-impedance-fit'


@pytest.mark.parametrize('radii,ratios', [([.5e-6], [0.]), ([.5e-6], [2.]),
    ([.2e-6, 4e-6], [0., 3.]), ([.2e-6, 1.2e-6, 4e-6], [.7, 0., 1.5]),
    ([.1e-6, .5e-6, 2e-6, 8e-6], [0., 1., 2., 0.])], ids=['smooth', 'one', 'two', 'three', 'four'])
def test_bvls_and_enumerated_active_sets_agree(radii, ratios):
    z, smooth, response = independent(radii, ratios)
    # Deterministic positive data perturbation yields both interior and active solutions.
    z = z+smooth*(2e-4*np.sin(np.arange(len(F))))
    w = np.linspace(.5, 2., len(F))
    root = np.sqrt(w)
    matrix = np.vstack((response.real*root[:, None], response.imag*root[:, None]))
    target = z/smooth-1
    rhs = np.r_[target.real*root, target.imag*root]
    reference = lsq_linear(matrix, rhs, bounds=(0, np.inf), method='bvls', tol=1e-12)
    assert reference.success
    candidates = []
    for bits in itertools.product((False, True), repeat=len(radii)):
        mask = np.array(bits)
        coef = np.zeros(len(radii))
        if np.any(mask): coef[mask] = np.linalg.lstsq(matrix[:, mask], rhs, rcond=None)[0]
        if np.all(coef >= 0): candidates.append((np.linalg.norm(matrix@coef-rhs)**2, coef))
    enumerated = min(candidates, key=lambda x:x[0])[1]
    result = fit_huray(F, resistance=z.real, reactance=z.imag, radii_m=radii,
                      conductivity=SIGMA, max_error_ratio=1e-3, weights=w)
    for expected in (reference.x, enumerated):
        np.testing.assert_allclose(result.model.surface_ratios, expected, rtol=1e-8, atol=1e-8)
    assert result.scaled_kkt_error < 1e-10
    np.testing.assert_allclose(result.normalized_residual, (result.predicted-z)/smooth, rtol=1e-10, atol=1e-14)


def test_incompatible_samples_are_retained_and_not_accepted():
    _, smooth, _ = independent()
    z = smooth*.8
    result = fit(z)
    assert not result.accepted
    np.testing.assert_array_equal(result.resistance, z.real)
    np.testing.assert_array_equal(result.reactance, z.imag)
    np.testing.assert_allclose(result.model.surface_ratios, 0, atol=1e-12, rtol=0)
    assert result.maximum_error_ratio == pytest.approx(.2, rel=1e-10)
    # An incompatible positive input is not rejected, clamped or silently repaired.
    assert result.to_dict()['accepted'] is False


def test_weights_change_objective_but_not_maximum_sample_gate():
    z, smooth, _ = independent()
    z[-1] += .2*smooth[-1]
    weights = np.ones(len(F));weights[-1] = 1e-8
    result = fit(z, weights=weights)
    assert not result.accepted and result.maximum_error_ratio > .1
    assert result.weighted_rms_error_ratio < .001
    for scale in (1e-200, 1e200):
        scaled = fit(z, weights=weights*scale)
        np.testing.assert_allclose(scaled.model.surface_ratios, result.model.surface_ratios, rtol=1e-10, atol=1e-12)
        np.testing.assert_allclose(scaled.predicted, result.predicted, rtol=1e-10, atol=0)


def test_inputs_are_copied_and_result_serialization_is_detached():
    z = independent()[0];r=z.real.copy();x=z.imag.copy();radii=RADII.copy();w=np.ones(len(F))
    result = fit_huray(F, resistance=r, reactance=x, radii_m=radii, weights=w,
                      conductivity=SIGMA, max_error_ratio=1e-9)
    before = result.to_dict()
    r[:]=1;x[:]=1;radii[:]=1;w[:]=1e3
    result.to_dict()['model']['surface_ratios'].clear()
    assert result.to_dict() == before


@pytest.mark.parametrize('change', [dict(frequency=[0, 1e9]), dict(frequency=[1e9]),
    dict(radii_m=[]), dict(radii_m=[1e-6, 1e-6]), dict(radii_m=[2e-6, 1e-6]),
    dict(radii_m=[-1e-6]), dict(radii_m=[True]), dict(radii_m=[float('nan')]),
    dict(radii_m=np.geomspace(1e-9, 1e-5, 17)), dict(resistance=[1.]), dict(reactance=[1.]),
    dict(resistance=np.zeros(41)), dict(reactance=-np.ones(41)), dict(weights=np.zeros(41)),
    dict(weights=np.full(41,float('inf'))), dict(weights=np.ones(40)), dict(conductivity=False),
    dict(conductivity=1e-10), dict(relative_permeability=0), dict(max_error_ratio=0),
    dict(max_error_ratio=True)], ids=['dc','short-frequency','no-radii','duplicate','order','negative-radius',
        'bool-radius','nan-radius','many-radii','short-r','short-x','zero-r','negative-x','zero-weight',
        'infinite-weight','short-weight','bool-sigma','not-good-conductor','zero-mu','zero-limit','bool-limit'])
def test_invalid_inputs_rejected_before_optimization(monkeypatch, change):
    import sipi.roughness_fit as implementation
    z=independent()[0]
    args=dict(frequency=F,resistance=z.real,reactance=z.imag,radii_m=RADII,
              conductivity=SIGMA,max_error_ratio=1e-9)
    args.update(change)
    monkeypatch.setattr(implementation,'nnls',lambda *a,**k:pytest.fail('Invalid fit optimized'))
    with pytest.raises(ValueError): fit_huray(**args)


def test_unidentifiable_saturated_populations_rejected_before_optimization(monkeypatch):
    import sipi.roughness_fit as implementation
    monkeypatch.setattr(implementation,'nnls',lambda *a,**k:pytest.fail('Rank deficient fit optimized'))
    z=independent()[0]
    with pytest.raises(ValueError, match='rank|condition'):
        fit_huray(F,resistance=z.real,reactance=z.imag,radii_m=[1e90,1e100],
                  conductivity=SIGMA,max_error_ratio=1e-9)


def test_failed_optimization_and_bad_kkt_do_not_fabricate_a_fit(monkeypatch):
    import sipi.roughness_fit as implementation
    def failed(*args,**kwargs): raise RuntimeError('iteration cap')
    monkeypatch.setattr(implementation,'nnls',failed)
    with pytest.raises(RuntimeError,match='iteration cap'):fit()
    monkeypatch.setattr(implementation,'nnls',lambda a,b,**kw:(np.zeros(a.shape[1]),0.))
    with pytest.raises(RuntimeError,match='optimality'):fit()


def test_independent_bvls_reference_record():
    require_tool('scipy')
    z, smooth, response = independent()
    z = z+smooth*(.002*np.sin(np.arange(len(F))))
    clock = Stopwatch()
    with clock('openphysics'):
        actual = fit(z)
    with clock('reference'):
        matrix = np.vstack((response.real,response.imag))
        target = z/smooth-1
        reference = lsq_linear(matrix,np.r_[target.real,target.imag],bounds=(0,np.inf),method='bvls',tol=1e-12)
        assert reference.success
        expected = smooth*(1+response@reference.x)
    coefficient_error = float(np.max(abs(np.asarray(actual.model.surface_ratios)-reference.x)))
    response_error = float(np.max(abs((actual.predicted-expected)/smooth)))
    record = make_record(case='fixed-radius-huray-fit',physics='causal sphere surface-impedance correction',
        api='sipi.roughness_fit.fit_huray',discretization='normalized nonnegative fixed-radius least squares',
        tool='scipy',tool_discretization='independent rational basis and bounded variable least squares',
        matched=['same fixed radii, positive complex surface samples, known conductivity/permeability and weights'],
        not_matched=['both optimizers use SciPy primitives; exhaustive active-set tests are separate',
                     'no foil measurement, radius selection, uncertainty or continuous-band validation'],
        observables=[observable('surface ratios','1','maximum absolute difference',coefficient_error,1e-8),
                     observable('surface impedance','1','maximum smooth-normalized difference',response_error,1e-10)],
        analytical_acceptance='test_roughness_fit.py: independent rational recovery and exhaustive active sets',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    assert coefficient_error < 1e-8 and response_error < 1e-10
    assert not actual.accepted
