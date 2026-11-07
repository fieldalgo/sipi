# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit mixed Thevenin/Norton terminal boundaries, including open and short."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from .network import LineNetwork
from .norton_termination import _residual
from .termination import _snapshot, _values

__all__ = ['MixedTerminatedNetwork', 'terminate_mixed_network']


@dataclass(frozen=True)
class MixedTerminatedNetwork:
    """Port-basis peak phasors; each terminal has its own explicit source kind.

    Arrays are (frequencies, ports), except condition_number/wave_residual [F].
    Unused source/load columns are zero. boundary_residual is dimensionless
    per port, normalizing KVL in V and KCL in A separately. All arrays are
    read-only snapshots. a/b are sqrt(W); currents point into the network.
    """
    network: LineNetwork
    kinds: tuple[str, ...]
    source_voltages: np.ndarray
    series_impedances: np.ndarray
    source_currents: np.ndarray
    shunt_admittances: np.ndarray
    a: np.ndarray
    b: np.ndarray
    voltage: np.ndarray
    current: np.ndarray
    condition_number: np.ndarray
    boundary_residual: np.ndarray
    wave_residual: np.ndarray

    def __post_init__(self):
        for name in ('source_voltages', 'series_impedances', 'source_currents',
                     'shunt_admittances', 'a', 'b', 'voltage', 'current',
                     'condition_number', 'boundary_residual', 'wave_residual'):
            object.__setattr__(self, name, _snapshot(getattr(self, name)))

    @property
    def frequency(self):
        return self.network.frequency

    @property
    def port_names(self):
        return self.network.port_names

    @property
    def basis(self):
        return self.network.basis

    def _power(self, product):
        with np.errstate(over='ignore', invalid='ignore'):
            weight = np.where(self.frequency == 0, 1., .5)
            power = weight*np.real(np.sum(product, axis=1))
        if not np.all(np.isfinite(product)) or not np.all(np.isfinite(power)):
            raise ValueError('average power overflow; rescale the excitation')
        return _snapshot(power)

    @property
    def network_power(self):
        with np.errstate(over='ignore', invalid='ignore'):
            product = self.voltage*np.conj(self.current)
        return self._power(product)

    @property
    def termination_power(self):
        with np.errstate(over='ignore', invalid='ignore'):
            product = ((self.series_impedances*self.current)*np.conj(self.current)
                       + self.voltage*np.conj(self.shunt_admittances*self.voltage))
        return self._power(product)

    @property
    def source_power(self):
        with np.errstate(over='ignore', invalid='ignore'):
            product = (self.source_voltages*np.conj(self.current)
                       + self.voltage*np.conj(self.source_currents))
        return self._power(product)


def _boundaries(network, boundaries):
    if not isinstance(boundaries, Mapping) or set(boundaries) != set(network.port_names):
        raise ValueError('boundaries must name every network port exactly once')
    tables = [dict() for _ in range(4)]
    kinds = []
    for name in network.port_names:
        item = boundaries[name]
        if not isinstance(item, Mapping):
            raise ValueError('each boundary must be a mapping')
        kind = item.get('kind')
        if kind == 'thevenin':
            if set(item) != {'kind', 'source_voltage', 'impedance'}:
                raise ValueError('thevenin boundary needs kind, source_voltage and impedance')
            tables[0][name], tables[1][name] = item['source_voltage'], item['impedance']
        elif kind == 'norton':
            if set(item) != {'kind', 'source_current', 'admittance'}:
                raise ValueError('norton boundary needs kind, source_current and admittance')
            tables[2][name], tables[3][name] = item['source_current'], item['admittance']
        else:
            raise ValueError('boundary kind must be thevenin or norton')
        kinds.append(kind)
    values = [_values(network, table, label, 0., passive=passive)
              for table,label,passive in zip(tables,
                  ('source_voltages','series_impedances','source_currents','shunt_admittances'),
                  (False,True,False,True))]
    return tuple(kinds), values


def terminate_mixed_network(network: LineNetwork, boundaries) -> MixedTerminatedNetwork:
    """Solve explicit Thevenin or Norton data at every port of the actual basis.

    A Thevenin entry contains kind='thevenin', source_voltage [V], impedance
    [ohm]; a Norton entry contains kind='norton', source_current [A], admittance
    [S]. Each numeric value is a finite complex scalar or F samples; Re Z/Y>=0.
    Z=0 is ideal voltage/short and Y=0 ideal current/open. No default, infinity
    or large-load surrogate is inferred. Existing single-kind APIs are unchanged.

    Reject nonfinite arithmetic, condition >1e12, normalized boundary or wave
    residual >1e-10. Per-port residual scales include incident/reflected V or I
    contributions before cancellation. DC power has weight 1, positive peak
    phasors weight 1/2. This does not certify supplied S passivity or causality.
    """
    if not isinstance(network, LineNetwork):
        raise TypeError('network must be a LineNetwork')
    kinds, (vs, z, source, y) = _boundaries(network, boundaries)
    net = LineNetwork(network.frequency, network.s, network.z_ref,
                      network.port_names, network.basis)
    is_voltage = np.array([kind == 'thevenin' for kind in kinds])
    root = np.sqrt(net.z_ref)
    gamma, drive = np.empty_like(vs), np.empty_like(vs)
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        zv = z[:, is_voltage]+net.z_ref[is_voltage]
        yi = y[:, ~is_voltage]*net.z_ref[~is_voltage]
        denominator = 1+yi
        gamma[:, is_voltage] = 1-2*net.z_ref[is_voltage]/zv
        drive[:, is_voltage] = (vs[:, is_voltage]/zv)*root[is_voltage]
        gamma[:, ~is_voltage] = -1+2/denominator
        drive[:, ~is_voltage] = (source[:, ~is_voltage]/denominator)*root[~is_voltage]
        system = np.eye(len(net.port_names))-gamma[:, :, None]*net.s
    if not all(np.all(np.isfinite(x)) for x in (zv, yi, denominator, gamma, drive, system)):
        raise ValueError('nonfinite mixed boundary system; rescale the input')
    try:
        condition = np.linalg.cond(system)
        if np.any(~np.isfinite(condition)) or np.any(condition > 1e12):
            raise ValueError('singular or ill-conditioned mixed boundary (limit=1e12)')
        a = np.linalg.solve(system, drive[..., None])[..., 0]
    except np.linalg.LinAlgError as exc:
        raise ValueError('singular mixed boundary') from exc
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        b = (net.s @ a[..., None])[..., 0]
        voltage, current = (a+b)*root, (a-b)/root
        primary = np.where(is_voltage, voltage, current)
        supplied = np.where(is_voltage, vs, source)
        drop = np.where(is_voltage, z*current, y*voltage)
        error = supplied-primary-drop
        wave_error = a-gamma*b-drive
        factor = np.where(is_voltage, root, 1/root)
        scale = np.maximum.reduce([abs(supplied), abs(primary), abs(drop),
                                   abs(a*factor), abs(b*factor)])
        boundary = abs(error)/np.maximum(scale, np.finfo(float).tiny)
    if not all(np.all(np.isfinite(x)) for x in
               (a,b,voltage,current,primary,supplied,drop,error,wave_error,scale,boundary)):
        raise ValueError('nonfinite mixed boundary solution; rescale the input')
    wave = _residual(wave_error, a, gamma*b, drive)
    if np.any(boundary > 1e-10) or np.any(wave > 1e-10):
        raise ValueError('mixed boundary residual exceeds 1e-10')
    return MixedTerminatedNetwork(net,kinds,vs,z,source,y,a,b,voltage,current,
                                  condition,boundary,wave)
