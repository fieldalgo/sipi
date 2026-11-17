# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit forward-current launches in uniform reciprocal RLGC lines."""
from dataclasses import dataclass

import numpy as np

from .characteristic import rlgc_characteristic
from .network import _frequencies, _matrix, _real

__all__ = ['ForwardWaveProfile', 'rlgc_forward_profile']


def _positions(value):
    result = _real('positions', value)
    if (result.ndim != 1 or not len(result) or np.any(result < 0)
            or np.any(np.diff(result) <= 0)):
        raise ValueError('positions must be a nonempty increasing array in metres, >= 0')
    return result


def _complex(name, value):
    raw = np.asarray(value)
    if (raw.dtype.kind not in 'iufc' or not np.all(np.isfinite(raw))
            or any(isinstance(x, (bool, np.bool_))
                   for x in np.asarray(value, dtype=object).flat)):
        raise ValueError(f'{name} must contain finite numeric phasors, not booleans')
    return np.array(raw, dtype=complex, copy=True)


def _freeze(value):
    result = np.array(value, copy=True)
    result.setflags(write=False)
    return result


@dataclass(frozen=True)
class ForwardWaveProfile:
    """Peak phasors (frequency,position,conductor) in single-ended coordinates.

    Power is average real watts; both loss arrays are watts per metre with
    shape (frequency,position). Positions are metres from the launch plane.
    No conductor-wise scalar impedance or decoupled mode is inferred.
    Arrays are copied snapshots. Construction alone does not validate physics.
    """
    frequency: np.ndarray
    positions: np.ndarray
    names: tuple[str, ...]
    voltage: np.ndarray
    current: np.ndarray
    power: np.ndarray
    conductor_loss: np.ndarray
    dielectric_loss: np.ndarray

    def __post_init__(self):
        f = _frequencies(self.frequency)
        if np.any(f <= 0):
            raise ValueError('forward profiles require positive frequency; DC is excluded')
        positions = _positions(self.positions)
        names = tuple(self.names)
        if (not names or any(not isinstance(n, str) or not n.strip()
                             or '\n' in n or '\r' in n for n in names)
                or len(set(names)) != len(names)):
            raise ValueError('names must be unique nonempty single-line strings')
        shape = (len(f), len(positions))
        for name in ('voltage', 'current', 'power', 'conductor_loss', 'dielectric_loss'):
            phasor = name in ('voltage', 'current')
            value = (_complex if phasor else _real)(name, getattr(self, name))
            if value.shape != (shape + (len(names),) if phasor else shape):
                raise ValueError(f'{name} has an inconsistent profile shape')
            object.__setattr__(self, name, _freeze(value))
        object.__setattr__(self, 'frequency', _freeze(f))
        object.__setattr__(self, 'positions', _freeze(positions))
        object.__setattr__(self, 'names', names)


def rlgc_forward_profile(frequency, *, R, L, G, C, launch_current, positions,
                         names=None):
    """Propagate an explicit pure forward launch, retaining all coupling.

    The convention is exp(+j omega t), with current positive along +z.
    launch_current is a peak-ampere phasor vector (N,) shared by all frequencies,
    or an explicit (F,N) array. All positions are finite, increasing and >= 0.
    RLGC and positive frequencies obey rlgc_characteristic's existing contract.

    V0=Zc I0, V(z)=exp(-Gamma_voltage*z)V0 and I(z)=Yc V(z).
    P=Re(V^H I)/2, qR=Re(I^H R I)/2, qG=Re(V^H G V)/2.
    These are total powers: interference and all off-diagonal terms remain.
    Accepted PSD roundoff is retained; outputs are not clipped or normalized.
    A zero-current launch is valid. Nonfinite arithmetic is rejected.

    A pure forward wave assumes the corresponding matched continuation, not
    arbitrary source/load termination. This adds no reflection, field solver,
    material inference, mode tracking, DC limit or measured-accuracy guarantee.
    """
    f = _frequencies(frequency)
    if np.any(f <= 0):
        raise ValueError('forward profiles require positive frequency; DC is excluded')
    z = _positions(positions)
    l = _matrix('L', L, len(f))
    n = l.shape[1]
    r, g, c = (_matrix(key, value, len(f), n)
               for key, value in (('R', R), ('G', G), ('C', C)))
    drive = _complex('launch_current', launch_current)
    if drive.shape == (n,):
        drive = np.broadcast_to(drive, (len(f), n)).copy()
    if drive.shape != (len(f), n):
        raise ValueError('launch_current needs shape (N,) or (frequencies,N)')
    characteristic = rlgc_characteristic(f, R=r, L=l, G=g, C=c, names=names)
    with np.errstate(over='ignore', invalid='ignore'):
        initial = np.einsum('fij,fj->fi', characteristic.z_characteristic, drive)
        if not np.all(np.isfinite(initial)):
            raise ValueError('forward launch voltage is not numerically representable')
        voltage = np.stack([
            initial if distance == 0 else np.einsum(
                'fij,fj->fi', characteristic.voltage_transfer(distance), initial)
            for distance in z], axis=1)
        current = np.einsum('fij,fpj->fpi', characteristic.y_characteristic, voltage)
        if z[0] == 0:
            current[:, 0] = drive
        power = .5*np.einsum('fpi,fpi->fp', voltage.conj(), current).real
        conductor = .5*np.einsum('fpi,fij,fpj->fp', current.conj(), r, current).real
        dielectric = .5*np.einsum('fpi,fij,fpj->fp', voltage.conj(), g, voltage).real
    if not all(np.all(np.isfinite(value))
               for value in (voltage, current, power, conductor, dielectric)):
        raise ValueError('forward profile is not numerically representable')
    return ForwardWaveProfile(f, z, characteristic.names, voltage, current,
                              power, conductor, dielectric)
