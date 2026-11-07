# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Periodic Thevenin sources and finite passive loads through existing feedback."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from .network import LineNetwork, _real
from .periodic import PeriodicResponse, _grid, _readonly, _finite
from .termination import TerminatedNetwork, terminate_network, _values

__all__ = ['PeriodicTerminatedResponse', 'periodic_terminated_response']


@dataclass(frozen=True)
class PeriodicTerminatedResponse:
    """Time-domain sources/drops [V], periodic waves and original harmonic solve.

    Time arrays use (samples, ports); frequency_solution has DC means and
    positive-frequency peak phasors. Sum its per-frequency average powers to
    compare with time-average powers. Arrays returned by the API are read-only.
    """
    source_voltages: np.ndarray
    termination_voltages: np.ndarray
    response: PeriodicResponse
    frequency_solution: TerminatedNetwork


def _sources(network, sources, count, *, field='source_voltages'):
    if not isinstance(sources, Mapping) or not sources:
        raise ValueError(field+' must be a nonempty mapping')
    result = np.zeros((count, len(network.port_names)))
    for name, raw in sources.items():
        if not isinstance(name, str) or name not in network.port_names:
            raise ValueError(field+' contains an unknown port')
        value = _real(field+' '+name, raw)
        if value.ndim and value.shape != (count,):
            raise ValueError(field+' needs a real constant or 2*frequencies-1 samples per port')
        result[:, network.port_names.index(name)] = value
    return result


def _inverse_peak(phasors, count):
    _finite(phasors)
    if np.any(phasors[0].imag != 0):
        raise ValueError('DC solution must be exactly real for a real periodic response')
    coefficients = np.array(phasors, dtype=complex, copy=True)
    coefficients[1:] *= .5
    result = np.fft.irfft(coefficients, n=count, axis=0, norm='forward')
    _finite(result)
    return _readonly(result)


def periodic_terminated_response(network: LineNetwork, *, source_voltages,
                                  terminations=None) -> PeriodicTerminatedResponse:
    """Solve real periodic Thevenin source waveforms with explicit finite loads.

    The network needs real DC and uniform harmonics, as periodic_response.
    Named source voltages are real constants or N=2*F-1 samples [V]; omitted
    sources are zero. Terminations are finite passive impedances [ohm], scalar
    or F complex samples; omitted values equal each port reference. DC loads
    must be exactly real. Zero impedance is supported, infinite/open is not.

    Existing terminate_network condition/residual gates apply at every harmonic.
    No interpolation, missing DC, startup, causality or stability is inferred.
    Mixed-mode sources and loads apply in the network's actual port basis.
    """
    count, period, dt, time = _grid(network)
    sources = _sources(network, source_voltages, count)
    loads = _values(network, {} if terminations is None else terminations,
                    'terminations', network.z_ref, passive=True)
    if np.any(loads[0].imag != 0):
        raise ValueError('DC terminations must be exactly real')
    with np.errstate(over='ignore', invalid='ignore', divide='ignore', under='ignore'):
        # Fourier coefficients are half the positive-frequency peak phasors.
        drive = np.fft.rfft(sources, axis=0, norm='forward')
        drive[1:] *= 2
        _finite(drive)
        solved = terminate_network(network,
            source_voltages=dict(zip(network.port_names, drive.T)),
            terminations=dict(zip(network.port_names, loads.T)))
        a, b, v, i = (_inverse_peak(getattr(solved, name), count)
                       for name in ('a', 'b', 'voltage', 'current'))
        drop = _inverse_peak(solved.terminations*solved.current, count)
    response = PeriodicResponse(_readonly(time), period, dt, a, b, v, i,
        _readonly(network.z_ref), network.port_names, network.basis)
    return PeriodicTerminatedResponse(_readonly(sources), drop, response, solved)
