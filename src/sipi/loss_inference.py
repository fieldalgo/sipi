# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Constrained shunt-loss inference from scalar traveling-wave attenuation."""
from dataclasses import dataclass

import numpy as np
from scipy.optimize import brentq

from .network import _frequencies, _real, _scalar
from .propagation import LinePropagation, _freeze, rlgc_propagation

__all__ = ['ShuntLossInference', 'infer_shunt_loss']


def _inference_inputs(frequency, alpha, R, L, C, max_error_np_per_m):
    f = _frequencies(frequency)
    if not 1 <= len(f) <= 10000 or f[0] <= 0:
        raise ValueError('inference requires 1..10000 positive frequency samples')
    a = _real('alpha', alpha)
    if a.shape != f.shape or np.any(a < 0):
        raise ValueError('nonnegative alpha in Np/m must match the frequency grid')
    values = []
    for name, raw in (('R', R), ('L', L), ('C', C)):
        value = _real(name, raw)
        if value.ndim == 0:
            value = np.full(f.shape, float(value))
        if value.shape != f.shape or np.any(value < 0 if name == 'R' else value <= 0):
            raise ValueError(f'{name} must be a passive scalar or match the frequency grid')
        values.append(value)
    return f, a, *values, _scalar('max_error_np_per_m', max_error_np_per_m)


@dataclass(frozen=True)
class ShuntLossInference:
    """Sampled candidate, including constrained mismatches below G=0 loss.

    effective_loss_tangent is G/(omega*C), not an identified constituent
    dielectric property. residual is predicted alpha minus supplied alpha.
    """
    propagation: LinePropagation
    alpha_input: np.ndarray
    resistance: np.ndarray
    inductance: np.ndarray
    capacitance: np.ndarray
    conductance: np.ndarray
    alpha_zero_shunt: np.ndarray
    evaluations: np.ndarray
    error_limit_np_per_m: float

    def __post_init__(self):
        if not isinstance(self.propagation, LinePropagation) or self.propagation.modes != ('single',):
            raise ValueError('inference requires scalar line propagation')
        f, a, r, l, c, limit = _inference_inputs(self.propagation.frequency,
            self.alpha_input, self.resistance, self.inductance, self.capacitance,
            self.error_limit_np_per_m)
        for name, value in zip(('alpha_input', 'resistance', 'inductance', 'capacitance'), (a, r, l, c)):
            object.__setattr__(self, name, _freeze(value))
        for name in ('conductance', 'alpha_zero_shunt', 'evaluations'):
            value = _real(name, getattr(self, name))
            if value.shape != f.shape or np.any(value < 0):
                raise ValueError(f'{name} must be nonnegative and match frequency')
            if name == 'evaluations' and (np.any(value < 1) or np.any(value != np.floor(value))):
                raise ValueError('evaluations must be positive integers')
            object.__setattr__(self, name, _freeze(value.astype(int) if name == 'evaluations' else value))
        object.__setattr__(self, 'error_limit_np_per_m', limit)

    @property
    def effective_loss_tangent(self):
        return _freeze(self.conductance/(2*np.pi*self.propagation.frequency*self.capacitance))

    @property
    def residual(self):
        return _freeze(self.propagation.alpha[:, 0]-self.alpha_input)

    @property
    def maximum_error_np_per_m(self):
        return float(np.max(abs(self.residual)))

    @property
    def accepted(self):
        return self.maximum_error_np_per_m <= self.error_limit_np_per_m

    def to_dict(self):
        p = self.propagation
        return dict(scope='sampled-scalar-shunt-loss-inference',
            frequency_hz=p.frequency.tolist(), alpha_input_np_per_m=self.alpha_input.tolist(),
            R_ohm_per_m=self.resistance.tolist(), L_h_per_m=self.inductance.tolist(),
            C_f_per_m=self.capacitance.tolist(), G_s_per_m=self.conductance.tolist(),
            effective_loss_tangent=self.effective_loss_tangent.tolist(),
            alpha_zero_shunt_np_per_m=self.alpha_zero_shunt.tolist(),
            alpha_predicted_np_per_m=p.alpha[:, 0].tolist(), beta_rad_per_m=p.beta[:, 0].tolist(),
            alpha_conductor_np_per_m=p.alpha_conductor[:, 0].tolist(),
            alpha_dielectric_np_per_m=p.alpha_dielectric[:, 0].tolist(),
            residual_np_per_m=self.residual.tolist(), evaluations=self.evaluations.tolist(),
            maximum_error_np_per_m=self.maximum_error_np_per_m,
            error_limit_np_per_m=self.error_limit_np_per_m, accepted=self.accepted)


def infer_shunt_loss(frequency, *, alpha, R, L, C, max_error_np_per_m):
    """Infer nonnegative G from propagation amplitude alpha [Np/m] and known RLC.

    Single uniform line, exp(+j omega t), SI units. R >= 0, L/C > 0 may be
    scalars or frequency arrays. Frequency and alpha are explicit arrays.
    Each sample solves Re sqrt((R+j*omega*L)*(G+j*omega*C)) = alpha.
    Below the G=0 baseline, retain the G=0 candidate and original input.
    Acceptance is a sampled absolute residual test with the caller's limit.

    Bracket from omega*C with at most 64 factors of four, then normalized
    Brent root finding with 128 iterations; no retries. Unrepresentable
    intermediates and solver failures raise. This is not insertion-loss
    deembedding, an S21 conversion, uncertainty estimation, multilayer loss
    attribution or a validation of the supplied field-derived RLC.
    """
    f, a, r, l, c, limit = _inference_inputs(frequency, alpha, R, L, C, max_error_np_per_m)
    g = np.zeros_like(f)
    baseline = np.empty_like(f)
    counts = np.zeros(len(f), dtype=int)
    for i in range(len(f)):
        with np.errstate(over='ignore', invalid='ignore'):
            wl, wc = 2*np.pi*f[i]*l[i], 2*np.pi*f[i]*c[i]
        if not np.isfinite(wl) or not np.isfinite(wc) or wl <= 0 or wc <= 0:
            raise ValueError('frequency-scaled L/C cannot be represented')

        def attenuation(value):
            counts[i] += 1
            with np.errstate(over='ignore', invalid='ignore'):
                gamma = np.sqrt(complex(r[i], wl)*complex(value, wc))
            if not np.isfinite(gamma):
                raise ValueError('propagation candidate cannot be represented')
            return float(gamma.real)

        baseline[i] = attenuation(0.)
        if a[i] <= baseline[i]:
            continue
        upper = wc
        for expansion in range(65):
            if attenuation(upper) >= a[i]:
                break
            if expansion == 64:
                raise RuntimeError('shunt conductance bracket exceeded 64 expansions')
            upper *= 4
            if not np.isfinite(upper):
                raise ValueError('shunt conductance bracket cannot be represented')
        root = brentq(lambda x: attenuation(x*upper)-a[i], 0., 1.,
            xtol=np.nextafter(0., 1.), rtol=8*np.finfo(float).eps, maxiter=128)
        g[i] = root*upper
    p = rlgc_propagation(f, **{name: value[:, None, None]
        for name, value in (('R', r), ('L', l), ('G', g), ('C', c))})
    result = ShuntLossInference(p, a, r, l, c, g, baseline, counts, limit)
    if not np.all(np.isfinite(result.effective_loss_tangent)):
        raise ValueError('effective shunt loss tangent cannot be represented')
    return result
