# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit sampled periodic network response; exp(+j omega t), SI units.

No missing DC inference, interpolation, window, startup transient or causality
repair is performed. Negative impulse lags wrap around the stated period.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .network import LineNetwork, _real

__all__ = ['PeriodicResponse', 'PeriodicImpulse', 'periodic_response', 'periodic_impulse']


def _readonly(value):
    array = np.array(value, dtype=float, copy=True)
    array.setflags(write=False)
    return array


def _time_grid(f):
    """Validate already-normalized source frequencies without solving its fields."""
    if len(f) < 2 or f[0] != 0:
        raise ValueError('periodic response requires DC and at least one positive harmonic')
    df = f[1]
    with np.errstate(over='ignore', invalid='ignore', divide='ignore', under='ignore'):
        expected = np.arange(len(f), dtype=float)*df
        error = np.max(np.abs(f-expected))/f[-1]
        period = 1./df
        count = 2*len(f)-1
        dt = period/count
        time = np.arange(count, dtype=float)*dt
    if not np.isfinite(error) or error > 1e-12:
        raise ValueError('frequencies must be uniformly spaced harmonics from DC')
    if (not np.isfinite(period) or not np.isfinite(dt) or dt <= 0
            or not np.all(np.isfinite(time)) or np.any(np.diff(time) <= 0)):
        raise ValueError('period and time samples are not representable at this numeric scale')
    return count, float(period), float(dt), time


def _grid(network):
    if not isinstance(network, LineNetwork):
        raise ValueError('network must be a LineNetwork')
    grid = _time_grid(network.frequency)
    if np.any(network.s[0].imag != 0):
        raise ValueError('DC S must be exactly real for a real periodic response')
    return grid


def _finite(*arrays):
    if any(not np.all(np.isfinite(a)) for a in arrays):
        raise ValueError('periodic transform is not representable at this numeric scale')


@dataclass(frozen=True)
class PeriodicResponse:
    """One period of real power waves [sqrt(W)], voltage [V] and current [A].

    Computed arrays are read-only. Currents point into the network; all ports
    have the input network's order, basis and positive real references [ohm].
    This is periodic steady state, not the response to switching a source on.
    """
    time: np.ndarray
    period: float
    dt: float
    incident: np.ndarray
    reflected: np.ndarray
    voltage: np.ndarray
    current: np.ndarray
    z_ref: np.ndarray
    port_names: tuple[str, ...]
    basis: str


@dataclass(frozen=True)
class PeriodicImpulse:
    """Centered lag [s] and dimensionless discrete circular-convolution weights.

    ``weights[lag, output_port, input_port]`` uses the input network's order.
    Weights multiply discrete samples: they are not a continuous Dirac density.
    Negative lags represent wrapping, not evidence for or against causality.
    """
    lag: np.ndarray
    period: float
    dt: float
    weights: np.ndarray
    z_ref: np.ndarray
    port_names: tuple[str, ...]
    basis: str


def periodic_response(network: LineNetwork, incident) -> PeriodicResponse:
    """Apply S to a real periodic power-wave array shaped (2*F-1, ports).

    F>=2 frequencies must start at exactly DC and equal k*df to 1e-12 times
    the maximum frequency; DC S must be exactly real. Odd sample count avoids
    a Nyquist bin and preserves every supplied positive-frequency phase.
    No passivity, causality, between-sample or out-of-band behavior is inferred.
    """
    count, period, dt, time = _grid(network)
    a = _real('incident', incident)
    if a.shape != (count, len(network.port_names)):
        raise ValueError('incident must have shape (2*frequencies-1, ports)')
    with np.errstate(over='ignore', invalid='ignore', divide='ignore', under='ignore'):
        spectrum = np.fft.rfft(a, axis=0)
        outgoing = np.einsum('fij,fj->fi', network.s, spectrum)
        _finite(spectrum, outgoing)
        b = np.fft.irfft(outgoing, n=count, axis=0)
        root = np.sqrt(network.z_ref)
        voltage = root*(a+b)
        current = (a-b)/root
    _finite(b, voltage, current)
    return PeriodicResponse(_readonly(time), period, dt, _readonly(a), _readonly(b),
        _readonly(voltage), _readonly(current), _readonly(network.z_ref),
        network.port_names, network.basis)


def periodic_impulse(network: LineNetwork) -> PeriodicImpulse:
    """Return the same odd-length periodic transform as discrete impulse weights.

    Output lags run from -(F-1)*dt to +(F-1)*dt. For circular convolution,
    unshift the weights with ifftshift(weights, axes=0). There is no window,
    zero padding, interpolation, extrapolation or amplitude renormalization.
    """
    count, period, dt, _ = _grid(network)
    with np.errstate(over='ignore', invalid='ignore', under='ignore'):
        weights = np.fft.fftshift(np.fft.irfft(network.s, n=count, axis=0), axes=0)
        lag = np.arange(-(count//2), count//2+1, dtype=float)*dt
    _finite(weights, lag)
    return PeriodicImpulse(_readonly(lag), period, dt, _readonly(weights),
        _readonly(network.z_ref), network.port_names, network.basis)
