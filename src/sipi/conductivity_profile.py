# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""One-dimensional conductivity profiles with an explicit exterior port plane.

This full-Maxwell half-space solve is separate from the quasi-TEM roughness
multipliers. Its port impedance includes the transition's exterior field;
it must not be added directly to a line's mean-plane external inductance.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from scipy.integrate import solve_ivp
from scipy.special import ndtr

from .constants import epsilon_0, mu_0
from .network import _frequencies, _scalar

__all__ = ['GaussianConductivityProfile', 'ConductivityProfileResult']


def _finite_scalar(name, value, *, zero=False):
    value = _scalar(name, value, zero=zero)
    if not math.isfinite(value):
        raise ValueError(f'{name} cannot be represented as a finite float')
    return value


def _cutoff(value):
    value = _finite_scalar('cutoff_rms', value)
    if not 5 <= value <= 10:
        raise ValueError('cutoff_rms must be between 5 and 10')
    return value


def _samples(profile, frequency, cutoff):
    f = _frequencies(frequency)
    if f[0] <= 0 or len(f) > 1024 or not np.all(np.isfinite(f)):
        raise ValueError('profile needs 1..1024 finite strictly positive frequencies')
    if not math.isfinite(cutoff*profile.rms_m):
        raise ValueError('profile reference plane cannot be represented')
    log_f = np.log(f)
    log_sigma = math.log(profile.conductivity)
    log_xi = math.log(2*np.pi*epsilon_0)+log_f-log_sigma
    # Inclusive physical bounds need only floating-point arithmetic slack:
    # subtraction of large logs can move an exact boundary a few ulps.
    # Keep the actual samples, never clamp them to the nominal boundary.
    eps = np.finfo(float).eps
    xi_roundoff = 4*eps*(abs(math.log(2*np.pi*epsilon_0))+abs(log_f)+abs(log_sigma)+1)
    if np.any(log_xi > math.log(1e-3)+xi_roundoff):
        raise ValueError('profile requires sigma/(omega*eps0) >= 1000')
    log_delta = -.5*(math.log(np.pi*mu_0)+log_f+log_sigma)
    log_rs = .5*(math.log(np.pi*mu_0)+log_f-log_sigma)
    if profile.rms_m:
        log_ratio = math.log(profile.rms_m)-log_delta
        ratio_roundoff = 4*eps*(abs(math.log(profile.rms_m))+abs(log_delta)+1)
        if np.any(log_ratio > math.log(10)+ratio_roundoff):
            raise ValueError('profile supports rms_m/skin_depth <= 10')
    with np.errstate(over='ignore', under='ignore'):
        delta = np.exp(log_delta)
        rs = np.exp(log_rs)
        xi = np.exp(log_xi)
        ratio = np.exp(log_ratio) if profile.rms_m else np.zeros(f.shape)
    if (not all(np.all(np.isfinite(a)) for a in (delta, rs, xi, ratio))
            or np.any(delta <= 0) or np.any(rs <= 0) or np.any(xi <= 0)
            or (profile.rms_m and np.any(ratio <= 0))):
        raise ValueError('profile scales cannot be represented')
    return f, delta, rs, xi, ratio


@dataclass(frozen=True, kw_only=True)
class GaussianConductivityProfile:
    """Nonmagnetic half-space sigma(x)=conductivity*Phi(x/rms_m).

    x increases into the metal from the statistical mean plane. Within
    +/-cutoff_rms*rms_m the Gaussian CDF is resolved; beyond it, conductivity
    is respectively zero and the supplied bulk value. Permittivity is eps0
    throughout, including the metal. No Ra/Rz conversion or material fit.
    """
    conductivity: float
    rms_m: float

    def __post_init__(self):
        object.__setattr__(self, 'conductivity',
                           _finite_scalar('conductivity', self.conductivity))
        object.__setattr__(self, 'rms_m', _finite_scalar('rms_m', self.rms_m, zero=True))

    def analyze(self, frequency, *, cutoff_rms=8.0):
        """Return E/H (ohm/square) at x=-cutoff_rms*rms_m, exp(+j omega t).

        Frequencies are 1..1024 increasing positive Hz samples. The bounded
        contract requires sigma/(omega*eps0)>=1000 and rms_m/delta<=10.
        Zero RMS returns the full-Maxwell smooth bulk impedance at x=0.
        The exterior impedance may have negative reactance; it is not a
        nonnegative internal-inductance correction or a roughness multiplier.
        """
        cutoff = _cutoff(cutoff_rms)
        f, _, rs, xi, ratio = _samples(self, frequency, cutoff)
        values = np.empty(f.shape, dtype=complex)
        for i, (resistance, displacement, rho) in enumerate(zip(rs, xi, ratio)):
            bulk = (1+1j)/np.sqrt(1+1j*displacement)
            if self.rms_m == 0:
                value = bulk
            else:
                def rhs(u, y):
                    return rho*((ndtr(u)+1j*displacement)*y*y-2j)
                solved = solve_ivp(rhs, (cutoff, -cutoff), [bulk],
                                   method='DOP853', rtol=2e-11, atol=2e-12)
                if not solved.success:
                    raise RuntimeError(f'conductivity profile integration failed: {solved.message}')
                value = solved.y[0, -1]
            with np.errstate(over='ignore', invalid='ignore', under='ignore'):
                values[i] = resistance*value
            if not np.isfinite(values[i]) or values[i].real <= 0:
                raise RuntimeError('conductivity profile produced an invalid passive-port impedance')
        return ConductivityProfileResult(self, f, values, cutoff)


@dataclass(frozen=True)
class ConductivityProfileResult:
    """Read-only frequency/impedance samples and their explicit exterior plane.

    Positive real impedance means inward time-average dissipation. Reactance
    is the magnetic/electric energy difference and is not forced positive.
    No measured-material or general 2D line validity follows from these fields.
    """
    profile: GaussianConductivityProfile
    frequency: np.ndarray
    impedance: np.ndarray
    cutoff_rms: float = 8.0

    def __post_init__(self):
        if not isinstance(self.profile, GaussianConductivityProfile):
            raise TypeError('profile must be a GaussianConductivityProfile')
        cutoff = _cutoff(self.cutoff_rms)
        f, _, _, _, _ = _samples(self.profile, self.frequency, cutoff)
        z = np.array(self.impedance, dtype=complex, copy=True)
        if z.shape != f.shape or not np.all(np.isfinite(z)) or np.any(z.real <= 0):
            raise ValueError('impedance needs finite matching samples with positive real parts')
        f.setflags(write=False)
        z.setflags(write=False)
        object.__setattr__(self, 'frequency', f)
        object.__setattr__(self, 'impedance', z)
        object.__setattr__(self, 'cutoff_rms', cutoff)

    @property
    def reference_plane_m(self):
        """Port x relative to the statistical mean; negative is outside metal."""
        return -self.cutoff_rms*self.profile.rms_m

    @property
    def skin_depth(self):
        """Bulk good-conductor scale delta (m), not a fitted profile depth."""
        result = _samples(self.profile, self.frequency, self.cutoff_rms)[1]
        result.setflags(write=False)
        return result
