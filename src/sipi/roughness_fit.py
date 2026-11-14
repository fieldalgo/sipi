# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Fixed-radius causal sphere fitting of explicit surface-impedance samples."""
from dataclasses import dataclass

import numpy as np
from scipy.optimize import nnls

from .conductor import _metal_samples, surface_impedance
from .network import _frequencies, _real, _scalar
from .roughness import CausalHuray, _sphere_response

__all__ = ['HurayFit', 'fit_huray']


@dataclass(frozen=True)
class HurayFit:
    """Fixed-radii candidate and sampled residuals, not foil validation.

    normalized_residual = (predicted - input) / smooth_surface_impedance.
    accepted applies only to its maximum magnitude at the input samples.
    """
    model: CausalHuray
    frequency: np.ndarray
    resistance: np.ndarray
    reactance: np.ndarray
    weights: np.ndarray
    conductivity: float
    relative_permeability: float
    predicted: np.ndarray
    normalized_residual: np.ndarray
    condition: float
    scaled_kkt_error: float
    maximum_error_ratio: float
    weighted_rms_error_ratio: float
    error_limit_ratio: float

    def __post_init__(self):
        if not isinstance(self.model, CausalHuray):
            raise ValueError('fitted model must be CausalHuray')
        shape = np.asarray(self.frequency).shape
        if len(shape) != 1 or not 2 <= shape[0] <= 10000:
            raise ValueError('fit requires 2..10000 samples')
        for key in ('frequency', 'resistance', 'reactance', 'weights', 'predicted', 'normalized_residual'):
            values = np.array(getattr(self, key), dtype=complex if key in ('predicted', 'normalized_residual') else float, copy=True)
            if values.shape != shape or not np.all(np.isfinite(values)):
                raise ValueError(f'{key} must match the finite frequency grid')
            values.flags.writeable = False
            object.__setattr__(self, key, values)
        for key in ('conductivity', 'relative_permeability', 'condition', 'scaled_kkt_error',
                    'maximum_error_ratio', 'weighted_rms_error_ratio', 'error_limit_ratio'):
            object.__setattr__(self, key, _scalar(key, getattr(self, key),
                zero=key in ('scaled_kkt_error', 'maximum_error_ratio', 'weighted_rms_error_ratio')))

    @property
    def accepted(self):
        return self.maximum_error_ratio <= self.error_limit_ratio

    def to_dict(self):
        def complex_values(value): return dict(real=value.real.tolist(), imag=value.imag.tolist())
        return dict(scope='fixed-radii-sampled-surface-impedance-fit',
            model=dict(kind='causal-huray', radii_m=list(self.model.radii_m), surface_ratios=list(self.model.surface_ratios)),
            frequency_hz=self.frequency.tolist(), resistance_ohms=self.resistance.tolist(),
            reactance_ohms=self.reactance.tolist(), weights=self.weights.tolist(),
            conductivity=self.conductivity, relative_permeability=self.relative_permeability,
            predicted_ohms=complex_values(self.predicted), normalized_residual=complex_values(self.normalized_residual),
            condition=self.condition, scaled_kkt_error=self.scaled_kkt_error,
            maximum_error_ratio=self.maximum_error_ratio, weighted_rms_error_ratio=self.weighted_rms_error_ratio,
            error_limit_ratio=self.error_limit_ratio, accepted=self.accepted)


def _fit_inputs(frequency, resistance, reactance, radii_m, conductivity, relative_permeability, max_error_ratio, weights):
    """Copy and validate fit inputs without optimization or field solves."""
    f = _frequencies(frequency)
    if not 2 <= len(f) <= 10000 or f[0] <= 0:
        raise ValueError('fit requires 2..10000 strictly positive frequency samples')
    radii = _real('radii_m', radii_m)
    if radii.ndim != 1 or not 1 <= len(radii) <= 16 or np.any(radii <= 0) or np.any(np.diff(radii) <= 0):
        raise ValueError('fit requires 1..16 distinct increasing positive fixed radii')
    real, imag = _real('resistance', resistance), _real('reactance', reactance)
    if real.shape != f.shape or imag.shape != f.shape or np.any(real <= 0) or np.any(imag <= 0):
        raise ValueError('positive surface resistance/reactance must match the frequency grid')
    w = np.ones_like(f) if weights is None else _real('weights', weights)
    if w.shape != f.shape or np.any(w <= 0):
        raise ValueError('positive weights must match every sample')
    sigma = _scalar('conductivity', conductivity)
    mu_r = _scalar('relative_permeability', relative_permeability)
    limit = _scalar('max_error_ratio', max_error_ratio)
    _, delta, _, smooth = _metal_samples(f, sigma, mu_r, 0.)
    return f, real, imag, radii, sigma, mu_r, limit, w, delta, smooth


def fit_huray(frequency, *, resistance, reactance, radii_m, conductivity,
              max_error_ratio, relative_permeability=1., weights=None):
    """Fit nonnegative full-sphere area ratios at 1..16 explicit fixed radii.

    Samples are surface impedance R+jX in ohm/square, exp(+j omega t), with
    known conductivity and uniform permeability. Both R and X must be positive;
    data below the smooth model are retained, not clipped. Positive sample
    weights multiply squared residuals normalized by the known smooth complex
    impedance. A common weight scale does not change the objective.

    Require full column rank and condition <=1e10. NNLS has 10*N iterations,
    with no retries, and scaled KKT residual <=1e-10. Above-limit candidates
    retain all samples and accepted=False. This is not radius selection,
    measurement uncertainty, deembedding, a continuous-band error bound, or
    measured foil validation. No field solve is performed.
    """
    f, real, imag, radii, sigma, mu_r, limit, w, delta, smooth = _fit_inputs(
        frequency, resistance, reactance, radii_m, conductivity, relative_permeability, max_error_ratio, weights)
    basis = np.column_stack([1.5*_sphere_response(radius, delta) for radius in radii])
    root_weights = np.sqrt(w)/np.sqrt(np.max(w))
    matrix = np.vstack((basis.real*root_weights[:, None], basis.imag*root_weights[:, None]))
    singular = np.linalg.svd(matrix, compute_uv=False)
    if len(singular) != len(radii) or singular[-1] <= 0 or singular[-1] < singular[0]/1e10:
        raise ValueError('fixed-radii design must have full rank and condition <= 1e10')
    condition = float(singular[0]/singular[-1])
    if condition > 1e10:
        raise ValueError('fixed-radii condition exceeds 1e10')
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        target = (real+1j*imag)/smooth-1.
    if not np.all(np.isfinite(target)):
        raise ValueError('normalized surface samples cannot be represented')
    target = np.concatenate((target.real, target.imag))
    amplitude = max(1., float(np.max(abs(target))))
    rhs = (target/amplitude)*np.tile(root_weights, 2)
    coefficients, _ = nnls(matrix, rhs, maxiter=10*len(radii))
    if not np.all(np.isfinite(coefficients)) or np.any(coefficients < 0):
        raise RuntimeError('NNLS returned invalid nonnegative surface ratios')
    difference = matrix@coefficients-rhs
    gradient = matrix.T@difference
    gradient /= max(1., float(singular[0]*np.linalg.norm(difference)))
    kkt = max(float(np.max(np.maximum(-gradient, 0.))),
              float(np.max(abs(coefficients*gradient)))/max(1., float(np.max(coefficients))))
    if not np.isfinite(kkt) or kkt > 1e-10:
        raise RuntimeError('NNLS optimality residual exceeds 1e-10')
    with np.errstate(over='ignore', invalid='ignore'):
        coefficients = coefficients*amplitude
    model = CausalHuray(radii, coefficients)
    predicted = surface_impedance(f, conductivity=sigma, relative_permeability=mu_r, roughness=model)
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        residual = (predicted-(real+1j*imag))/smooth
    maximum = float(np.max(abs(residual)))
    if not np.isfinite(maximum):
        raise RuntimeError('fit residual cannot be represented')
    scale = max(1., maximum)
    rms = scale*float(np.linalg.norm((residual/scale)*root_weights)/np.linalg.norm(root_weights))
    return HurayFit(model, f, real, imag, w, sigma, mu_r, predicted, residual,
                    condition, kkt, maximum, rms, limit)
