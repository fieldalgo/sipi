# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit Norton current sources and finite passive shunt admittances."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from .network import LineNetwork
from .termination import _snapshot, _values

__all__ = ['NortonTerminatedNetwork', 'terminate_norton_network']


@dataclass(frozen=True)
class NortonTerminatedNetwork:
    """Read-only peak-phasor solution of I + Y V = Is at every network port.

    Array shapes are (frequencies, ports), except the per-frequency diagnostic
    and power arrays. Currents point into the network. Source currents are A;
    shunt admittances are S. Y=0 is an ideal current source, or an open when
    its source current is also zero. No impedance infinity is stored.
    """
    network: LineNetwork
    source_currents: np.ndarray
    termination_admittances: np.ndarray
    a: np.ndarray
    b: np.ndarray
    voltage: np.ndarray
    current: np.ndarray
    condition_number: np.ndarray
    kcl_residual: np.ndarray
    wave_residual: np.ndarray

    def __post_init__(self):
        for name in ('source_currents', 'termination_admittances', 'a', 'b',
                     'voltage', 'current', 'condition_number', 'kcl_residual', 'wave_residual'):
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

    def _power(self, current):
        with np.errstate(over='ignore', invalid='ignore'):
            weight = np.where(self.frequency == 0, 1., .5)
            value = weight*np.real(np.sum(self.voltage*np.conj(current), axis=1))
        if not np.all(np.isfinite(value)):
            raise ValueError('average power overflow; rescale the excitation')
        return _snapshot(value)

    @property
    def network_power(self):
        """Average power into the network [W]; arbitrary supplied S may be active."""
        return self._power(self.current)

    @property
    def termination_power(self):
        """Average dissipation in the parallel source/load admittances [W]."""
        with np.errstate(over='ignore', invalid='ignore'):
            shunt = self.termination_admittances*self.voltage
        return self._power(shunt)

    @property
    def source_power(self):
        """Average power delivered by all ideal current sources [W]."""
        return self._power(self.source_currents)


def _residual(error, *terms):
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        scale = np.maximum.reduce([np.max(np.abs(x), axis=1) for x in terms])
        numerator = np.max(np.abs(error), axis=1)
        result = numerator/np.maximum(scale, np.finfo(float).tiny)
    if not all(np.all(np.isfinite(x)) for x in (scale, numerator, result)):
        raise ValueError('nonfinite Norton residual scale; rescale the input')
    return result


def terminate_norton_network(network, *, source_currents, termination_admittances=None):
    """Solve named Norton sources with passive finite shunt admittances.

    Is [A] and Y [S] are finite complex scalars or F samples in the network's
    actual port basis. Omitted Is is zero; omitted Y is 1/Zref. Require a
    nonempty source mapping, even for zero drive. Y=0, Is=0 is an open; Y=0
    with nonzero Is is an ideal current source. For Y!=0 the Thevenin
    equivalent is Vs=Is/Y and Zt=1/Y. Use the existing Thevenin solver for a
    short/ideal voltage source; infinity is not an accepted admittance.

    Preserve all port V/I and reject singular/floating or condition >1e12
    feedback, normalized KCL/wave residual >1e-10 and nonrepresentable numeric
    intermediates/results. No passivity, stability or causality of S is inferred.
    Power uses DC weight 1 and positive-frequency peak-phasor weight 1/2.
    """
    if not isinstance(network, LineNetwork):
        raise TypeError('network must be a LineNetwork')
    if not isinstance(source_currents, Mapping) or not source_currents:
        raise ValueError('source_currents must be a nonempty mapping')
    source = _values(network, source_currents, 'source_currents', 0)
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        default_y = 1/network.z_ref
    admittance = _values(network, {} if termination_admittances is None else termination_admittances,
                         'termination_admittances', default_y, passive=True)
    if not np.all(np.isfinite(admittance)):
        raise ValueError('default admittance is not representable; supply explicit finite admittances')
    net = LineNetwork(network.frequency, network.s, network.z_ref,
                      network.port_names, network.basis)
    root = np.sqrt(net.z_ref)
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        product = admittance*net.z_ref
        denominator = 1+product
        gamma = -1+2/denominator
        drive = (source/denominator)*root
        system = np.eye(len(net.port_names))-gamma[:, :, None]*net.s
    if not all(np.all(np.isfinite(x)) for x in (product, denominator, gamma, drive, system)):
        raise ValueError('nonfinite Norton feedback system; rescale the input')
    try:
        condition = np.linalg.cond(system)
        if np.any(~np.isfinite(condition)) or np.any(condition > 1e12):
            bad = int(np.flatnonzero(~np.isfinite(condition) | (condition > 1e12))[0])
            raise ValueError(f'ill-conditioned Norton termination at {net.frequency[bad]:g} Hz '
                             f'(condition={condition[bad]:g}, limit=1e12)')
        a = np.linalg.solve(system, drive[..., None])[..., 0]
    except np.linalg.LinAlgError as exc:
        raise ValueError('singular Norton termination') from exc
    with np.errstate(over='ignore', invalid='ignore'):
        b = (net.s @ a[..., None])[..., 0]
        voltage = (a+b)*root
        current = (a-b)/root
        shunt = admittance*voltage
        kcl_error = source-current-shunt
        wave_error = a-gamma*b-drive
    if not all(np.all(np.isfinite(x)) for x in (a,b,voltage,current,shunt,kcl_error,wave_error)):
        raise ValueError('nonfinite Norton circuit solution; rescale the input')
    kcl = _residual(kcl_error, source, current, shunt)
    wave = _residual(wave_error, a, gamma*b, drive)
    if np.any(kcl > 1e-10) or np.any(wave > 1e-10):
        raise ValueError('Norton termination residual exceeds 1e-10')
    return NortonTerminatedNetwork(net,source,admittance,a,b,voltage,current,condition,kcl,wave)
