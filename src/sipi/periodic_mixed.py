# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Real periodic waveforms with mixed voltage/current terminal boundaries."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from .mixed_termination import MixedTerminatedNetwork, _boundaries, terminate_mixed_network
from .network import LineNetwork, _real
from .periodic import PeriodicResponse, _grid, _readonly, _finite
from .periodic_termination import _inverse_peak

__all__ = ['PeriodicMixedResponse', 'periodic_mixed_response']


@dataclass(frozen=True)
class PeriodicMixedResponse:
    """Read-only real source and load arrays [N,P], zero in unused-kind columns.

    source_voltages/termination_voltages are V at Thevenin ports;
    source_currents/termination_currents are A at Norton ports. response keeps
    all port waves, V/I and the time grid; frequency_solution keeps kinds,
    explicit loads, DC means/positive peak phasors, diagnostics and powers.
    """
    source_voltages: np.ndarray
    source_currents: np.ndarray
    termination_voltages: np.ndarray
    termination_currents: np.ndarray
    response: PeriodicResponse
    frequency_solution: MixedTerminatedNetwork


def periodic_mixed_response(network: LineNetwork, boundaries) -> PeriodicMixedResponse:
    """Apply real periodic sources to explicit mixed Thevenin/Norton boundaries.

    Every actual-basis port uses the mixed solver's exact kind/field contract,
    except source values are real DC constants or N=2F-1 time samples. Loads
    remain finite passive complex scalars/F samples, with exactly real DC.
    The network needs uniform harmonics from exactly real DC and F>=2.

    Ideal voltage/short and current/open may coexist. Reactive load drops and
    shunt currents are synthesized from Z(f)I(f) and Y(f)V(f), not pointwise
    time products. All periodic and mixed-feedback guards remain in force.
    No interpolation, window, missing-DC estimate or startup inference occurs.
    """
    count, period, dt, time = _grid(network)
    if not isinstance(boundaries, Mapping) or set(boundaries) != set(network.port_names):
        raise ValueError('boundaries must name every network port exactly once')
    samples = np.zeros((count, len(network.port_names)))
    frequency_boundaries, source_keys = {}, []
    for column,name in enumerate(network.port_names):
        item = boundaries[name]
        if not isinstance(item, Mapping):
            raise ValueError('each boundary must be a mapping')
        kind = item.get('kind')
        if kind == 'thevenin':
            source_key, load_key = 'source_voltage', 'impedance'
        elif kind == 'norton':
            source_key, load_key = 'source_current', 'admittance'
        else:
            raise ValueError('boundary kind must be thevenin or norton')
        if set(item) != {'kind', source_key, load_key}:
            raise ValueError('boundary fields must match the selected source kind')
        source = _real(source_key+' '+name, item[source_key])
        if source.ndim and source.shape != (count,):
            raise ValueError('periodic source needs a real constant or 2*frequencies-1 samples')
        samples[:, column] = source
        source_keys.append(source_key)
        frequency_boundaries[name] = dict(kind=kind, **{source_key:0., load_key:item[load_key]})
    kinds, (_, z, _, y) = _boundaries(network, frequency_boundaries)
    if np.any(z[0].imag != 0) or np.any(y[0].imag != 0):
        raise ValueError('DC impedances and admittances must be exactly real')
    with np.errstate(over='ignore', invalid='ignore', divide='ignore', under='ignore'):
        drive = np.fft.rfft(samples, axis=0, norm='forward')
        drive[1:] *= 2
        _finite(drive)
        for column,(name,key) in enumerate(zip(network.port_names,source_keys)):
            frequency_boundaries[name][key] = drive[:, column]
        solved = terminate_mixed_network(network, frequency_boundaries)
        a, b, v, i = (_inverse_peak(getattr(solved, key), count)
                      for key in ('a', 'b', 'voltage', 'current'))
        drop = _inverse_peak(solved.series_impedances*solved.current, count)
        shunt = _inverse_peak(solved.shunt_admittances*solved.voltage, count)
    is_voltage = np.array([kind == 'thevenin' for kind in kinds])
    response = PeriodicResponse(_readonly(time), period, dt, a, b, v, i,
        _readonly(network.z_ref), network.port_names, network.basis)
    return PeriodicMixedResponse(_readonly(np.where(is_voltage,samples,0.)),
        _readonly(np.where(is_voltage,0.,samples)), drop, shunt, response, solved)
