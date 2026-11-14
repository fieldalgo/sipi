# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit surface corrections; exp(+j omega t), SI lengths.

These are constitutive half-space models, not resolved rough surfaces or
finite-metal DC solves. CausalHuray fixes the base matte/flat area ratio to one.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from .network import _real, _scalar

__all__ = ['CausalHuray', 'GroissRMS', 'CannonballHuray']


def _sphere_response(radius, delta):
    """Unit causal sphere response, without subtracting the smooth limit."""
    scale = np.maximum(radius, delta)
    a, d = radius/scale, delta/scale
    q = (1+1j)*a
    return q/(d+q)


@dataclass(frozen=True)
class GroissRMS:
    """Noncausal frequency-domain correction for a good-conductor half-space.

    rms_m is the RMS height Rq, not Ra or Rz. The empirical real factor
    1+exp(-(delta/(2*Rq))**1.6) multiplies the entire surface impedance.
    It saturates at two and is intended for relatively polished conductors,
    not a general rough-foil accuracy model. Zero RMS is exactly smooth.
    """
    rms_m: float

    def __post_init__(self):
        object.__setattr__(self, 'rms_m', _scalar('rms_m', self.rms_m, zero=True))

    def factor(self, skin_depth):
        """Real multiplier for nonempty positive one-dimensional depths (m)."""
        delta = _real('skin_depth', skin_depth)
        if delta.ndim != 1 or not delta.size or np.any(delta <= 0):
            raise ValueError('skin_depth must be a nonempty positive one-dimensional array')
        if self.rms_m == 0:
            return np.ones(delta.shape)
        # Logarithms avoid overflowing delta/Rq or 2*Rq. Overflow of the
        # positive exponent gives the exact floating-point smooth limit.
        power = 1.6*(np.log(delta)-math.log(self.rms_m)-math.log(2))
        with np.errstate(over='ignore', under='ignore'):
            return 1 + np.exp(-np.exp(power))

    def _impedance_factors(self, skin_depth):
        factor = self.factor(skin_depth)
        return factor, factor.copy()


@dataclass(frozen=True)
class CausalHuray:
    """Sphere radii (m) and full-sphere area ratios N*4*pi*a**2/A_flat.

    Each of 1..64 populations needs a positive radius and nonnegative area
    ratio. Caller arrays are copied into tuples. No conversion from Ra/Rq/Rz
    or assumption about sphere packing is made.
    """
    radii_m: tuple[float, ...]
    surface_ratios: tuple[float, ...]

    def __post_init__(self):
        radii = _real('radii_m', self.radii_m)
        ratios = _real('surface_ratios', self.surface_ratios)
        if (radii.ndim != 1 or not 1 <= radii.size <= 64
                or ratios.shape != radii.shape
                or np.any(radii <= 0) or np.any(ratios < 0)):
            raise ValueError('Huray needs 1..64 positive radii and matching nonnegative surface ratios')
        # Bound the entire high-frequency response before evaluating any input.
        try:
            saturation = 1 + 1.5*math.fsum(ratios)
        except OverflowError as exc:
            raise ValueError('Huray saturation cannot be represented') from exc
        if not np.isfinite(saturation):
            raise ValueError('Huray saturation cannot be represented')
        object.__setattr__(self, 'radii_m', tuple(float(x) for x in radii))
        object.__setattr__(self, 'surface_ratios', tuple(float(x) for x in ratios))

    def factor(self, skin_depth):
        """Complex multiplier H for nonempty positive skin depths (m).

        H = 1 + sum(1.5*SR*q/(1+q)), q=(1+j)*a/delta. The principal
        square root q=sqrt(s*mu*sigma*a**2) defines its causal continuation.
        Input order is retained. This multiplier is NOT the resistance ratio.
        """
        delta = _real('skin_depth', skin_depth)
        if delta.ndim != 1 or not delta.size or np.any(delta <= 0):
            raise ValueError('skin_depth must be a nonempty positive one-dimensional array')
        result = np.ones(delta.shape, dtype=complex)
        for radius, ratio in zip(self.radii_m, self.surface_ratios):
            # Normalize before division: even extreme finite a/delta must not
            # overflow, square to infinity or produce an indeterminate inf/inf.
            result += (1.5*ratio)*_sphere_response(radius, delta)
        if not np.all(np.isfinite(result)):
            raise ValueError('Huray response cannot be represented')
        return result

    def _impedance_factors(self, skin_depth):
        """Evaluate R/X ratios without subtracting nearly equal large values."""
        delta = np.asarray(skin_depth, dtype=float)
        resistance, reactance = np.ones(delta.shape), np.ones(delta.shape)
        for radius, ratio in zip(self.radii_m, self.surface_ratios):
            scale = np.maximum(radius, delta)
            a, d = radius/scale, delta/scale
            denominator = d*d+2*a*d+2*a*a
            weighted = (1.5*ratio)*a
            resistance += weighted*(2*a/denominator)
            reactance += weighted*(2*(d+a)/denominator)
        return resistance, reactance


@dataclass(frozen=True)
class CannonballHuray:
    """Explicit ten-point Rz mapping to the existing causal sphere model.

    The published rounded mapping is radius = 0.06*Rz. Fourteen equal spheres
    over a 36*radius**2 tile give full-sphere area ratio 14*pi/9. This assumes
    the stated triangular-profile/FCC heuristic; it is not a general Rz/Rq/Ra
    conversion or a measured foil fit. One uniform surface model is applied.
    Rz must be positive; select the smooth model for zero roughness.
    """
    rz_10point_m: float

    def __post_init__(self):
        value = _scalar('rz_10point_m', self.rz_10point_m)
        if .06*value == 0:
            raise ValueError('Cannonball sphere radius cannot be represented')
        object.__setattr__(self, 'rz_10point_m', value)

    @property
    def radius_m(self):
        return .06*self.rz_10point_m

    @property
    def surface_ratio(self):
        return 14*math.pi/9

    def to_huray(self):
        """Equivalent immutable sphere population, without rounding its area."""
        return CausalHuray((self.radius_m,), (self.surface_ratio,))

    def factor(self, skin_depth):
        """Complex causal multiplier, not the real resistance ratio."""
        return self.to_huray().factor(skin_depth)

    def _impedance_factors(self, skin_depth):
        return self.to_huray()._impedance_factors(skin_depth)
