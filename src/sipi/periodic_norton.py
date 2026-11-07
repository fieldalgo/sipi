# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Real periodic Norton source waveforms with explicit passive shunt boundaries."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .network import LineNetwork
from .norton_termination import NortonTerminatedNetwork, terminate_norton_network
from .periodic import PeriodicResponse, _grid, _readonly, _finite
from .periodic_termination import _sources, _inverse_peak
from .termination import _values

__all__ = ['PeriodicNortonResponse', 'periodic_norton_response']


@dataclass(frozen=True)
class PeriodicNortonResponse:
    """One period of real source/shunt currents [A] and complete port response.

    Time arrays have shape (samples, ports). frequency_solution retains DC means
    and positive-frequency peak phasors, admittances and original diagnostics.
    Sum its per-frequency powers to compare with the periodic time average.
    """
    source_currents: np.ndarray
    termination_currents: np.ndarray
    response: PeriodicResponse
    frequency_solution: NortonTerminatedNetwork


def periodic_norton_response(network: LineNetwork, *, source_currents,
                             termination_admittances=None) -> PeriodicNortonResponse:
    """Solve real periodic current sources with finite passive shunt admittances.

    Use the same real-DC uniform-harmonic grid as periodic_response, with odd
    N=2*F-1 samples. Named Is values are real constants or N samples [A]; omitted
    sources are zero. Y values are finite passive scalars or F complex samples
    [S], with real DC; omitted Y is 1/Zref. Y=0 is an ideal current source or
    an open when Is=0. No infinite/short admittance or large-impedance surrogate.

    I+Ishunt=Is holds in time; reactive shunt currents are synthesized from
    Y(f)V(f), not pointwise multiplication of time samples. Existing Norton
    condition/residual gates apply to every harmonic. No missing DC inference,
    interpolation, window, startup, causality or stability claim is added.
    Sources and loads apply in the actual network port basis.
    """
    count, period, dt, time = _grid(network)
    sources = _sources(network, source_currents, count, field='source_currents')
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        default_y = 1/network.z_ref
    loads = _values(network, {} if termination_admittances is None else termination_admittances,
                    'termination_admittances', default_y, passive=True)
    _finite(loads)
    if np.any(loads[0].imag != 0):
        raise ValueError('DC termination_admittances must be exactly real')
    with np.errstate(over='ignore', invalid='ignore', divide='ignore', under='ignore'):
        drive = np.fft.rfft(sources, axis=0, norm='forward')
        drive[1:] *= 2
        _finite(drive)
        solved = terminate_norton_network(network,
            source_currents=dict(zip(network.port_names, drive.T)),
            termination_admittances=dict(zip(network.port_names, loads.T)))
        a, b, v, i = (_inverse_peak(getattr(solved, key), count)
                      for key in ('a', 'b', 'voltage', 'current'))
        shunt = _inverse_peak(solved.termination_admittances*solved.voltage, count)
    response = PeriodicResponse(_readonly(time), period, dt, a, b, v, i,
        _readonly(network.z_ref), network.port_names, network.basis)
    return PeriodicNortonResponse(_readonly(sources), shunt, response, solved)
