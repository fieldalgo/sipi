# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Forward traveling waves in reciprocal multiconductor RLGC coordinates."""
from dataclasses import dataclass

import numpy as np
from scipy.linalg import expm, sqrtm

from .network import _frequencies, _matrix, _scalar

__all__ = ['LineCharacteristic', 'rlgc_characteristic']

_TOL = 1e-10
_CONDITION_LIMIT = 1e12


def _scale(value):
    return max(float(np.max(abs(value.real))), float(np.max(abs(value.imag))))


def _relative_error(actual, expected):
    scale = max(_scale(actual), _scale(expected))
    return 0.0 if scale == 0 else float(np.max(abs(actual/scale-expected/scale)))


def _conditioned(value):
    if not np.all(np.isfinite(value)):
        raise ValueError('characteristic matrices must be finite')
    scale = _scale(value)
    if scale == 0:
        raise ValueError('characteristic matrix is singular')
    condition = np.linalg.cond(value/scale)
    if not np.isfinite(condition) or condition > _CONDITION_LIMIT:
        raise ValueError('characteristic matrix condition exceeds 1e12')


def _freeze(value):
    result = np.array(value, copy=True)
    result.setflags(write=False)
    return result


@dataclass(frozen=True)
class LineCharacteristic:
    """Forward-wave matrices in conductor coordinates, shape (F,N,N).

    dV/dz=-gamma_voltage V; I=y_characteristic V and V=z_characteristic I.
    z is longitudinal distance; I is positive in the forward +z direction.
    Gamma is in 1/m, Zc in ohms and Yc in siemens. These are matrices, not
    per-conductor scalar impedances or tracked modes. Arrays are snapshots.
    """
    frequency: np.ndarray
    names: tuple[str, ...]
    gamma_voltage: np.ndarray
    z_characteristic: np.ndarray
    y_characteristic: np.ndarray

    def __post_init__(self):
        f = _frequencies(self.frequency)
        if np.any(f <= 0):
            raise ValueError('characteristic matrices require positive frequency; DC is excluded')
        names = tuple(self.names)
        if (not names or any(not isinstance(n, str) or not n.strip() or '\n' in n or '\r' in n
                             for n in names) or len(set(names)) != len(names)):
            raise ValueError('conductor names must be unique nonempty single-line strings')
        for name in ('gamma_voltage', 'z_characteristic', 'y_characteristic'):
            value = np.asarray(getattr(self, name), dtype=complex)
            if value.shape != (len(f), len(names), len(names)) or not np.all(np.isfinite(value)):
                raise ValueError(f'{name} must be finite with shape (frequency,conductor,conductor)')
            object.__setattr__(self, name, _freeze(value))
        for gamma, zc, yc in zip(self.gamma_voltage, self.z_characteristic, self.y_characteristic):
            for value in (gamma, zc, yc):
                _conditioned(value)
            for value in (zc, yc):
                if _relative_error(value, value.T) > _TOL:
                    raise ValueError('characteristic impedance/admittance must be reciprocal')
                normalized = value/_scale(value)
                if np.linalg.eigvalsh(.5*normalized.real+.5*normalized.real.T).min() <= 0:
                    raise ValueError('characteristic impedance/admittance must have positive real part')
            if _relative_error(zc@yc, np.eye(len(names))) > _TOL:
                raise ValueError('characteristic impedance/admittance inverse residual exceeds 1e-10')
            roots = np.linalg.eigvals(gamma/_scale(gamma))
            if np.any(roots.imag <= 0) or np.any(roots.real < -_TOL):
                raise ValueError('forward roots require positive phase and nonnegative attenuation within roundoff')
        object.__setattr__(self, 'frequency', _freeze(f))
        object.__setattr__(self, 'names', names)

    def voltage_transfer(self, length):
        """Return exp(-Gamma*length) for a pure forward wave, not terminal S.

        length is metres, finite and nonnegative. Euclidean voltage norm can
        grow under modal interference; passivity concerns Re(V^H I)/2 instead.
        """
        length = _scalar('length', length, zero=True)
        values = []
        with np.errstate(over='ignore', invalid='ignore'):
            for gamma in self.gamma_voltage:
                argument = -gamma*length
                if not np.all(np.isfinite(argument)):
                    raise ValueError('forward voltage transfer is not numerically representable')
                try:
                    values.append(expm(argument))
                except (np.linalg.LinAlgError, OverflowError) as exc:
                    raise ValueError('forward voltage transfer is not numerically representable') from exc
        values = np.asarray(values)
        if not np.all(np.isfinite(values)):
            raise ValueError('forward voltage transfer is not numerically representable')
        return _freeze(values)


def rlgc_characteristic(frequency, *, R, L, G, C, names=None):
    """Reciprocal passive full-matrix forward-wave propagation, positive Hz.

    Inputs follow rlgc_network: real symmetric PSD R/G and PD L/C, one matrix
    or one per frequency. Z=R+jwL and Y=G+jwC; Gamma^2=ZY, Zc=Gamma^-1 Z.
    The branch Gamma=j*sqrt(-ZY) gives positive phase and avoids the negative
    real branch cut of sqrt(ZY) for lossless lines. Z/Y are scaled separately.

    Reject nonfinite/unrepresentable data, condition numbers above 1e12 and
    relative equation/reciprocity residuals above 1e-10. No pseudoinverse,
    diagonal projection or implicit mode normalization/tracking is performed.
    This is uniform-line RLGC algebra, not a new field or full-wave solver.
    """
    f = _frequencies(frequency)
    if np.any(f <= 0):
        raise ValueError('characteristic matrices require positive frequency; DC is excluded')
    l = _matrix('L', L, len(f)); n = l.shape[1]
    r, g, c = (_matrix(key, value, len(f), n) for key, value in (('R', R), ('G', G), ('C', C)))
    names = tuple(str(i+1) for i in range(n)) if names is None else tuple(names)
    if len(names) != n:
        raise ValueError('names must contain one name per conductor')
    gammas, impedances, admittances = [], [], []
    for index, hz in enumerate(f):
        with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
            z = r[index]+2j*np.pi*hz*l[index]
            y = g[index]+2j*np.pi*hz*c[index]
        if not np.all(np.isfinite(z)) or not np.all(np.isfinite(y)):
            raise ValueError('series impedance and shunt admittance must be representable')
        zs, ys = _scale(z), _scale(y)
        if zs == 0 or ys == 0:
            raise ValueError('series impedance or shunt admittance underflowed to zero')
        zn, yn = z/zs, y/ys
        product = -(zn@yn)
        if not np.any(r[index]) and not np.any(g[index]):
            product = product.real  # Preserve the exact lossless real-root problem.
        try:
            gn = 1j*np.asarray(sqrtm(product), dtype=complex)
            _conditioned(gn)
            if _relative_error(gn@gn, zn@yn) > _TOL:
                raise ValueError('forward matrix square-root residual exceeds 1e-10')
            zcn = np.linalg.solve(gn, zn)
            if _relative_error(zcn, zcn.T) > _TOL:
                raise ValueError('forward characteristic impedance is not reciprocal within 1e-10')
            zcn = .5*zcn+.5*zcn.T  # Average accepted roundoff only.
            if _relative_error(gn@zcn, zn) > _TOL:
                raise ValueError('forward constitutive residual exceeds 1e-10')
            with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
                gamma = gn*np.sqrt(zs)*np.sqrt(ys)
                zc = zcn*np.sqrt(zs)/np.sqrt(ys)
            _conditioned(zc)
            yc = np.linalg.solve(zc/_scale(zc), np.eye(n))/_scale(zc)
        except np.linalg.LinAlgError as exc:
            raise ValueError('forward characteristic solve is numerically singular') from exc
        gammas.append(gamma); impedances.append(zc); admittances.append(yc)
    return LineCharacteristic(f, names, gammas, impedances, admittances)
