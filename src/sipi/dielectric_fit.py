# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Constrained Debye fitting at explicit fixed poles, with retained residuals."""
from dataclasses import dataclass
import json

import numpy as np
from scipy.optimize import nnls

from .dielectric import DebyeDielectric, dielectric_to_dict
from .circuit_document import _json_copy
from .document import _keys, _unique_object
from .network import _frequencies, _real, _scalar

__all__ = ['DebyeFit', 'fit_debye', 'DebyeFitDocument']


@dataclass(frozen=True)
class DebyeFit:
    """A candidate model and sampled errors, not measured material validation.

    ``residual`` is model permittivity minus (eps_real - j*eps_loss). All input
    samples, including those outside the requested error limit, are retained.
    ``accepted`` applies only to the maximum complex sample error.
    """
    model: DebyeDielectric
    frequency: np.ndarray
    eps_real: np.ndarray
    eps_loss: np.ndarray
    weights: np.ndarray
    predicted: np.ndarray
    residual: np.ndarray
    condition: float
    scaled_kkt_error: float
    maximum_error: float
    weighted_rms_error: float
    error_limit: float

    def __post_init__(self):
        if not isinstance(self.model, DebyeDielectric):
            raise ValueError('fitted model must be a DebyeDielectric')
        shape = np.asarray(self.frequency).shape
        if len(shape) != 1 or not 2 <= shape[0] <= 10000:
            raise ValueError('fit requires 2..10000 frequency samples')
        for key in ('frequency', 'eps_real', 'eps_loss', 'weights', 'predicted', 'residual'):
            value = np.array(getattr(self, key), dtype=complex if key in ('predicted', 'residual') else float, copy=True)
            if value.shape != shape or not np.all(np.isfinite(value)):
                raise ValueError(f'{key} must match the finite frequency grid')
            value.flags.writeable = False
            object.__setattr__(self, key, value)
        for key in ('condition', 'scaled_kkt_error', 'maximum_error', 'weighted_rms_error', 'error_limit'):
            value = _scalar(key, getattr(self, key), zero=key != 'error_limit')
            if not np.isfinite(value):
                raise ValueError(f'{key} is not representable')
            object.__setattr__(self, key, value)

    @property
    def accepted(self):
        return self.maximum_error <= self.error_limit

    def to_dict(self):
        def complex_values(value): return dict(real=value.real.tolist(), imag=value.imag.tolist())
        return dict(scope='fixed-pole-sampled-permittivity-fit', model=dielectric_to_dict(self.model),
            frequency_hz=self.frequency.tolist(), eps_real=self.eps_real.tolist(), eps_loss=self.eps_loss.tolist(),
            weights=self.weights.tolist(), predicted=complex_values(self.predicted), residual=complex_values(self.residual),
            condition=self.condition, scaled_kkt_error=self.scaled_kkt_error, maximum_error=self.maximum_error,
            weighted_rms_error=self.weighted_rms_error, error_limit=self.error_limit, accepted=self.accepted)


def _fit_inputs(frequency, eps_real, eps_loss, relaxation_hz, max_error, weights):
    """Validate and copy inputs without SVD, optimization or field work."""
    f = _frequencies(frequency)
    if not 2 <= len(f) <= 10000 or not np.all(np.isfinite(f)):
        raise ValueError('fit requires 2..10000 finite frequency samples')
    poles = _real('relaxation_hz', relaxation_hz)
    if (poles.ndim != 1 or not 1 <= len(poles) <= 32 or not np.all(np.isfinite(poles))
            or np.any(poles <= 0) or np.any(np.diff(poles) <= 0)):
        raise ValueError('fit requires 1..32 distinct increasing positive poles')
    real, loss = _real('eps_real', eps_real), _real('eps_loss', eps_loss)
    if (real.shape != f.shape or loss.shape != f.shape or not np.all(np.isfinite(real))
            or not np.all(np.isfinite(loss)) or np.any(real < 1) or np.any(loss < 0)):
        raise ValueError('finite eps_real>=1 and eps_loss>=0 must match the frequency grid')
    w = np.ones_like(f) if weights is None else _real('weights', weights)
    if w.shape != f.shape or not np.all(np.isfinite(w)) or np.any(w <= 0):
        raise ValueError('positive finite weights must match every frequency')
    limit = _scalar('max_error', max_error)
    if not np.isfinite(limit):
        raise ValueError('max_error is not representable')
    return f, real, loss, poles, w, limit


def fit_debye(frequency, *, eps_real, eps_loss, relaxation_hz, max_error, weights=None):
    """Fit eps_inf>=1 and nonnegative strengths at 1..32 fixed positive poles.

    Inputs use exp(+j*w*t): eps=eps_real-j*eps_loss, with eps_real>=1 and
    eps_loss>=0. Supply 2..10000 distinct increasing nonnegative frequencies
    and distinct increasing positive poles in Hz. Positive per-frequency
    weights multiply both real and loss squared residuals; omitted weights
    are one. Scaling every weight by the same factor leaves the fit unchanged.

    The normalized weighted real design matrix must have full column rank
    and condition <=1e10. NNLS has a fixed cap of 10*(number of poles+1)
    iterations, without retries; numerical/KKT failures raise. A model above
    max_error is retained with accepted=False, never silently accepted or
    changed by clipping data. max_error is an explicit positive absolute
    complex-permittivity error at samples, independent of objective weights.

    This is fixed-basis fitting, not pole selection, measurement uncertainty,
    a continuous-band error bound or physical material validity outside the
    samples. The returned Debye law is mathematically passive and causal.
    No field solve or mesh convergence is performed by this operation.
    """
    f, real, loss, poles, w, limit = _fit_inputs(frequency, eps_real, eps_loss, relaxation_hz, max_error, weights)

    # Stable relaxation basis even when f/pole or hypot(f,pole) would overflow.
    scale = np.maximum(f[:, None], poles)
    a, b = poles/scale, f[:, None]/scale
    denominator = a*a+b*b
    response_real, response_loss = a*a/denominator, a*b/denominator
    root_weights = np.sqrt(w)/np.sqrt(np.max(w))
    matrix = np.vstack([np.column_stack([np.ones_like(f), response_real])*root_weights[:, None],
                        np.column_stack([np.zeros_like(f), response_loss])*root_weights[:, None]])
    singular = np.linalg.svd(matrix, compute_uv=False)
    if len(singular) < len(poles)+1 or singular[-1] <= 0 or singular[-1] < singular[0]/1e10:
        raise ValueError('fixed-pole design must have full rank and condition <= 1e10')
    condition = float(singular[0]/singular[-1])
    if condition > 1e10:
        raise ValueError('fixed-pole condition exceeds 1e10')
    target = np.concatenate([real-1., loss])
    amplitude = max(1., float(np.max(target)))
    rhs = (target/amplitude)*np.tile(root_weights, 2)
    coefficients, _ = nnls(matrix, rhs, maxiter=10*(len(poles)+1))
    if not np.all(np.isfinite(coefficients)) or np.any(coefficients < 0):
        raise RuntimeError('NNLS returned invalid nonnegative coefficients')
    difference = matrix@coefficients-rhs
    gradient = matrix.T@difference
    gradient_scale = max(1., float(singular[0]*np.linalg.norm(difference)))
    normalized_gradient = gradient/gradient_scale
    kkt = max(float(np.max(np.maximum(-normalized_gradient, 0.))),
              float(np.max(abs(coefficients*normalized_gradient)))/max(1., float(np.max(coefficients))))
    if not np.isfinite(kkt) or kkt > 1e-10:
        raise RuntimeError('NNLS optimality residual exceeds 1e-10')
    with np.errstate(over='ignore', invalid='ignore'):
        coefficients = coefficients*amplitude
    model = DebyeDielectric(1.+coefficients[0], coefficients[1:], poles)
    predicted = model.permittivity(f)
    residual = predicted-(real-1j*loss)
    maximum = float(np.max(np.abs(residual)))
    if not np.isfinite(maximum):
        raise RuntimeError('fit residual is not representable')
    # Divide before squaring; neither huge weights nor residual amplitudes need overflow.
    residual_scale = max(1., maximum)
    weighted_rms = residual_scale*float(np.linalg.norm((residual/residual_scale)*root_weights)/np.linalg.norm(root_weights))
    return DebyeFit(model, f, real, loss, w, predicted, residual, condition, kkt,
                    maximum, weighted_rms, limit)


class DebyeFitDocument:
    """Strict saved fixed-pole fitting request; parsing performs no fitting.

    Numerical identifiability, condition and optimality are checked at analyze.
    Completed candidates retain their sampled acceptance flag independently of
    execution completion. Invalid inputs and numerical failures raise, never
    fabricating a model. The original fitted-model material schema is reused.
    """
    def __init__(self, frequency, *, eps_real, eps_loss, relaxation_hz, max_error, weights=None):
        f, real, loss, poles, w, limit = _fit_inputs(frequency, eps_real, eps_loss, relaxation_hz, max_error, weights)
        self._data = dict(schema='sipi.dielectric-fit/1', frequency_hz=f.tolist(), eps_real=real.tolist(),
            eps_loss=loss.tolist(), relaxation_hz=poles.tolist(), weights=w.tolist(), max_error=limit)

    @classmethod
    def from_dict(cls, data):
        data = _json_copy(data)
        _keys(data, ('schema', 'frequency_hz', 'eps_real', 'eps_loss', 'relaxation_hz', 'weights', 'max_error'),
              where='dielectric fit')
        if data['schema'] != 'sipi.dielectric-fit/1':
            raise ValueError('unsupported dielectric-fit schema')
        # JSON requests must resolve every weight explicitly, including defaults.
        if data['weights'] is None:
            raise ValueError('saved weights must explicitly match every frequency')
        return cls(data['frequency_hz'], eps_real=data['eps_real'], eps_loss=data['eps_loss'],
                   relaxation_hz=data['relaxation_hz'], weights=data['weights'], max_error=data['max_error'])

    @classmethod
    def loads(cls, text):
        def reject(value): raise ValueError(f'nonfinite JSON number: {value}')
        return cls.from_dict(json.loads(text, object_pairs_hook=_unique_object, parse_constant=reject))

    def dumps(self):
        return json.dumps(self._data, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)

    def to_dict(self):
        return json.loads(self.dumps())

    def analyze(self):
        data = self.to_dict()
        return fit_debye(data['frequency_hz'], eps_real=data['eps_real'], eps_loss=data['eps_loss'],
            relaxation_hz=data['relaxation_hz'], max_error=data['max_error'], weights=data['weights'])
