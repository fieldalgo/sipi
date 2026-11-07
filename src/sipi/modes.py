# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Distinct forward modes, power normalization and sampled-frequency tracking."""
from dataclasses import dataclass

import numpy as np
from scipy.optimize import linear_sum_assignment

from .characteristic import rlgc_characteristic, _freeze, _relative_error, _scale
from .network import _frequencies, _matrix

__all__ = ['LineModes', 'ModeTrackingError', 'rlgc_modes']


class ModeTrackingError(ValueError):
    """An unresolved modal basis or continuation, with the failing frequency."""
    def __init__(self, message, *, index, frequency):
        super().__init__(f'{message} at frequency index {index} ({frequency:g} Hz)')
        self.index = index
        self.frequency = float(frequency)


@dataclass(frozen=True)
class LineModes:
    """Peak-phasor forward modes, each with Re(V^H I)/2 = 1 watt.

    gamma/alpha arrays are (frequency,mode), in 1/m. Voltage/current columns
    are (frequency,conductor,mode), in V/A at the reference cross section.
    Names identify conductor coordinates, not the tracked mode indices.
    Overlap uses adjacent averaged Hermitian characteristic admittance.
    The first overlap/gap entries are one (no preceding assignment).
    """
    frequency: np.ndarray
    names: tuple[str, ...]
    gamma: np.ndarray
    voltage: np.ndarray
    current: np.ndarray
    alpha_conductor: np.ndarray
    alpha_dielectric: np.ndarray
    overlap: np.ndarray
    assignment_gap: np.ndarray

    def __post_init__(self):
        f = _frequencies(self.frequency)
        names = tuple(self.names)
        if np.any(f <= 0) or not names or len(set(names)) != len(names) or any(
                not isinstance(n, str) or not n.strip() or '\n' in n or '\r' in n for n in names):
            raise ValueError('modes need positive frequencies and unique single-line conductor names')
        nf, n = len(f), len(names)
        for key in ('gamma', 'voltage', 'current', 'alpha_conductor', 'alpha_dielectric', 'overlap', 'assignment_gap'):
            dtype = complex if key in ('gamma', 'voltage', 'current') else float
            raw = np.asarray(getattr(self, key))
            if dtype is float and np.iscomplexobj(raw):
                raise ValueError(f'{key} must be real')
            value = np.asarray(raw, dtype=dtype)
            shape = (nf, n, n) if key in ('voltage', 'current') else ((nf,) if key == 'assignment_gap' else (nf, n))
            if value.shape != shape or not np.all(np.isfinite(value)):
                raise ValueError(f'{key} has invalid modal shape or nonfinite values')
            object.__setattr__(self, key, _freeze(value))
        power = .5*np.einsum('fij,fij->fj', self.voltage.conj(), self.current).real
        if np.max(abs(power-1)) > 1e-10:
            raise ValueError('each mode must have one watt of positive forward power')
        if (np.any(self.alpha_conductor < 0) or np.any(self.alpha_dielectric < 0)
                or np.any(self.overlap < .7) or np.any(self.overlap > 1+1e-10)
                or np.any(self.assignment_gap <= 1e-6)):
            raise ValueError('invalid modal loss or continuation diagnostics')
        scale = np.max(abs(self.gamma), axis=1, keepdims=True)
        if (np.any(self.gamma.imag <= 0) or np.any(self.gamma.real < -1e-10*scale)
                or np.any(abs(self.alpha_conductor+self.alpha_dielectric-self.gamma.real) > 1e-10*scale)):
            raise ValueError('modal forward branch or power balance is invalid')
        object.__setattr__(self, 'frequency', _freeze(f))
        object.__setattr__(self, 'names', names)


def _assign(previous, current, metric, *, index, hz):
    """Power-metric overlap and a unique globally optimal one-to-one assignment."""
    h = metric/_scale(metric)
    a = previous/np.linalg.norm(previous, axis=0)
    b = current/np.linalg.norm(current, axis=0)
    aa = np.einsum('ij,ij->j', a.conj(), h@a).real
    bb = np.einsum('ij,ij->j', b.conj(), h@b).real
    if np.any(aa <= 0) or np.any(bb <= 0):
        raise ModeTrackingError('nonpositive power overlap metric', index=index, frequency=hz)
    cross = a.conj().T@h@b
    score = abs(cross)/np.sqrt(aa[:, None]*bb[None, :])
    if not np.all(np.isfinite(score)) or np.any(score > 1+1e-10):
        raise ModeTrackingError('nonrepresentable power overlap', index=index, frequency=hz)
    row, permutation = linear_sum_assignment(-score)
    matched = score[row, permutation]
    best = float(matched.sum())
    gap = 1.0
    if len(matched) > 1:
        alternatives = []
        for i, j in zip(row, permutation):
            cost = -score.copy()
            cost[i, j] = np.inf
            ri, ci = linear_sum_assignment(cost)
            alternatives.append(float(score[ri, ci].sum()))
        gap = best-max(alternatives)
    if gap <= 1e-6:
        raise ModeTrackingError('ambiguous mode assignment; refine frequency sampling', index=index, frequency=hz)
    if np.min(matched) < .7:
        raise ModeTrackingError('mode overlap below 0.7; refine frequency sampling', index=index, frequency=hz)
    # Align each new mode so its overlap with the previous one is positive real.
    phase = np.exp(-1j*np.angle(cross[row, permutation]))
    return permutation, phase, matched, gap


def rlgc_modes(frequency, *, R, L, G, C, names=None):
    """Track distinct modes across supplied positive increasing frequencies.

    Reuses the full characteristic-matrix contract. First modes are sorted by
    increasing phase constant, then attenuation. Later labels maximize total
    power-metric overlap. Reject relative eigenvalue gaps <=1e-8, eigenvector
    condition >1e10, ambiguous assignment or overlap <0.7. No degeneracy basis,
    interpolation between samples or per-conductor modal impedance is inferred.
    """
    characteristic = rlgc_characteristic(frequency, R=R, L=L, G=G, C=C, names=names)
    f, names = characteristic.frequency, characteristic.names
    n = len(names)
    r, g = _matrix('R', R, len(f), n), _matrix('G', G, len(f), n)
    gammas, voltages, currents, conductor, dielectric, overlaps, gaps = [], [], [], [], [], [], []
    previous_h = None
    for k, hz in enumerate(f):
        matrix = characteristic.gamma_voltage[k]
        scale = _scale(matrix)
        roots, vectors = np.linalg.eig(matrix/scale)
        separation = abs(roots[:, None]-roots[None, :])
        separation[np.diag_indices(n)] = np.inf
        if np.min(separation) <= 1e-8*np.max(abs(roots)):
            raise ModeTrackingError('repeated or unresolved propagation roots', index=k, frequency=hz)
        if not np.isfinite(np.linalg.cond(vectors)) or np.linalg.cond(vectors) > 1e10:
            raise ModeTrackingError('ill-conditioned modal eigenvectors', index=k, frequency=hz)
        yc = characteristic.y_characteristic[k]
        h = .5*(yc+yc.conj().T)
        if k == 0:
            order = np.lexsort((roots.real, roots.imag))
            vectors, roots = vectors[:, order], roots[order]
            pivots = np.argmax(abs(vectors), axis=0)
            vectors *= np.exp(-1j*np.angle(vectors[pivots, np.arange(n)]))
            overlap, gap = np.ones(n), 1.0
        else:
            order, phase, overlap, gap = _assign(voltages[-1], vectors, .5*previous_h+.5*h, index=k, hz=hz)
            vectors, roots = vectors[:, order]*phase, roots[order]
        with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
            current = yc@vectors
            power = .5*np.einsum('ij,ij->j', vectors.conj(), current).real
            if not np.all(np.isfinite(power)) or np.any(power <= 0):
                raise ModeTrackingError('nonpositive or unrepresentable modal power', index=k, frequency=hz)
            vectors = vectors/np.sqrt(power)
            current = current/np.sqrt(power)
            alpha_r = .25*np.einsum('ij,ij->j', current.conj(), r[k]@current).real
            alpha_g = .25*np.einsum('ij,ij->j', vectors.conj(), g[k]@vectors).real
            gamma = roots*scale
        if not all(np.all(np.isfinite(v)) for v in (vectors, current, alpha_r, alpha_g, gamma)):
            raise ModeTrackingError('modal normalization or losses cannot be represented', index=k, frequency=hz)
        if np.any(alpha_r < 0) or np.any(alpha_g < 0):
            raise ModeTrackingError('negative modal loss; no clipping is applied', index=k, frequency=hz)
        if (_relative_error(matrix@vectors, vectors*gamma) > 1e-10
                or np.max(abs(alpha_r+alpha_g-gamma.real))/max(np.max(abs(gamma)), np.max(alpha_r+alpha_g)) > 1e-10):
            raise ModeTrackingError('modal equation or power-balance residual exceeds 1e-10', index=k, frequency=hz)
        gammas.append(gamma); voltages.append(vectors); currents.append(current)
        conductor.append(alpha_r); dielectric.append(alpha_g); overlaps.append(overlap); gaps.append(gap)
        previous_h = h
    return LineModes(f, names, gammas, voltages, currents, conductor, dielectric, overlaps, gaps)
