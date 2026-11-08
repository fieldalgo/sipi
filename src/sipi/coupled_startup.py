# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Zero-state finite passive two-signal RLGC circuits with resistive ends."""
import json

import numpy as np
from scipy.signal import lsim

from .network import _real, _scalar
from .sampling import _integer
from .startup import _times
from .rlgc_startup import RLGCLadderResponse

__all__ = ['CoupledRLGCLadderResponse', 'coupled_rlgc_ladder_response']


class CoupledRLGCLadderResponse(RLGCLadderResponse):
    """Two-signal states, copied/read-only; port order near0,near1,far0,far1.

    Node and segment arrays have a final two-conductor axis. Energy and power
    records sum both conductors; individual port powers are voltage*current.
    Both ends' port currents enter the line; segment current points +z.
    """
    @property
    def port_names(self):
        return ('near_0', 'near_1', 'far_0', 'far_1')

    def to_dict(self, *, include_states=False):
        out = super().to_dict(include_states=include_states)
        out['scope'] = 'finite-passive-two-signal-rlgc-ladder-startup'
        return out


def _passive_matrix(name, value):
    m = _real(name, value)
    if m.shape != (2, 2) or not np.array_equal(m, m.T):
        raise ValueError(f'{name} must be an exactly symmetric real 2x2 matrix')
    scale = np.max(abs(m))
    eigen = np.linalg.eigvalsh(m/scale) if scale else np.zeros(2)
    if name in ('L', 'C'):
        if eigen[0] <= 1e-12*eigen[-1]:
            raise ValueError(f'{name} must be positive definite with eigenvalue ratio above 1e-12')
    elif eigen[0] < 0:
        raise ValueError(f'{name} must be positive semidefinite; negative eigenvalues are not repaired')
    return m


def _coupled_core_input(time, source_voltages, *, R, L, G, C, length, cells,
                        _drive_name='source_voltages'):
    time = _times('time', time)
    if not 2 <= len(time) <= 10000 or time[0] != 0:
        raise ValueError('time needs 2..10000 samples starting at zero')
    dt = np.diff(time)
    if not np.allclose(dt, dt[0], rtol=1e-10, atol=0):
        raise ValueError('time spacing must be uniform within relative 1e-10')
    drive = _real(_drive_name, source_voltages)
    if drive.shape != (len(time), 2) or np.any(drive[0] != 0):
        raise ValueError(f'{_drive_name} needs shape (times,2) and a zero first row')
    r, l, g, c = [_passive_matrix(name, value) for name,value in [('R',R),('L',L),('G',G),('C',C)]]
    length = _scalar('length', length); cells = _integer(cells, 1, 128)
    return time, drive, r, l, g, c, length, cells


def _coupled_input(time, source_voltages, *, R, L, G, C, length, cells,
                   source_resistance, load_resistance):
    data = _coupled_core_input(time, source_voltages,
        R=R, L=L, G=G, C=C, length=length, cells=cells)
    rs = _real('source_resistance', source_resistance); rl = _real('load_resistance', load_resistance)
    if rs.shape != (2,) or rl.shape != (2,) or np.any(rs <= 0) or np.any(rl <= 0):
        raise ValueError('source/load resistance each need two finite positive values')
    return (*data, rs, rl)


def _quadratic(values, matrix):
    """Nonnegative quadratic of an already validated PSD matrix, no clipping."""
    scale = np.max(abs(matrix))
    if scale == 0:
        return np.zeros(values.shape[:-1])
    eigen, vectors = np.linalg.eigh(matrix/scale)
    return np.sum((values@vectors)**2*eigen, axis=-1)*scale


def coupled_rlgc_ladder_response(time, source_voltages, *, R, L, G, C, length,
                                  cells, source_resistance, load_resistance):
    """Propagate a finite uniform two-signal passive RLGC circuit from zero state.

    SI constant real exactly symmetric2x2 R/G are PSD; L/C are SPD with
    normalized eigenvalue ratio above1e-12. No negative eigenvalue repair.
    Explicit cells1..128, uniform time2..10000 starting0 and PWL drive(times,2)
    with first row0. Source/load each specify two finite positive resistances.
    End shunt C/G have half weights; existing SciPy lsim propagates the circuit.
    This excludes ideal/open/short/reactive ends, arbitrary material dispersion
    and general TDR inference. Input-specific spatial/source/time convergence
    remains necessary; bounded counts do not guarantee accuracy or runtime.
    """
    time, drive, r, l, g, c, length, n, rs, rl = _coupled_input(time, source_voltages,
        R=R, L=L, G=G, C=C, length=length, cells=cells,
        source_resistance=source_resistance, load_resistance=load_resistance)
    dx = length/n; weights = np.ones(n+1); weights[[0, -1]] = .5
    nv = 2*(n+1); size = 4*n+2
    with np.errstate(over='ignore', invalid='ignore', divide='ignore', under='ignore'):
        cap = c*dx; ind = l*dx
        ci = np.linalg.inv(c); li = np.linalg.inv(l)
        slopes = np.diff(drive, axis=0)/np.diff(time)[:, None]
    if (dx <= 0 or not np.all(np.isfinite(np.r_[cap.ravel(), ind.ravel(), ci.ravel(), li.ravel(), slopes.ravel()]))
            or np.linalg.eigvalsh(cap)[0] <= 0 or np.linalg.eigvalsh(ind)[0] <= 0):
        raise ValueError('cell matrices or source slopes exceed finite scales')
    a = np.zeros((size, size)); b = np.zeros((size, 2))
    with np.errstate(over='ignore', invalid='ignore', divide='ignore', under='ignore'):
        for k in range(n+1):
            vs = slice(2*k, 2*k+2); vc = ci/(dx*weights[k]); a[vs, vs] = -ci@g
            if k > 0: a[vs, nv+2*(k-1):nv+2*k] = vc
            if k < n: a[vs, nv+2*k:nv+2*k+2] = -vc
            if k == 0:
                source = vc@np.diag(1/rs); a[vs, vs] -= source; b[vs] = source
            if k == n: a[vs, vs] -= vc@np.diag(1/rl)
        for k in range(n):
            ids = slice(nv+2*k, nv+2*k+2)
            a[ids, 2*k:2*k+2] = li/dx; a[ids, 2*k+2:2*k+4] = -li/dx
            a[ids, ids] = -li@r
    if not np.all(np.isfinite(a)) or not np.all(np.isfinite(b)):
        raise ValueError('circuit coefficients exceed finite scales')
    _, _, x = lsim((a, b, np.zeros((1, size)), np.zeros((1, 2))), drive, time, interp=True)
    x = np.asarray(x)
    if x.shape != (len(time), size) or not np.all(np.isfinite(x)):
        raise ValueError('state propagation returned invalid shape or nonfinite values')
    with np.errstate(over='ignore', invalid='ignore', divide='ignore', under='ignore'):
        rhs = x@a.T+drive@b.T
        v = x[:, :nv].reshape(len(time), n+1, 2); i = x[:, nv:].reshape(len(time), n, 2)
        dv = rhs[:, :nv].reshape(v.shape); di = rhs[:, nv:].reshape(i.shape)
        voltage = v[:, [0, n], :].reshape(len(time), 4)
        current = np.concatenate(((drive-v[:, 0])/rs, -v[:, -1]/rl), axis=1)
        energy = .5*dx*(np.sum(_quadratic(v, c)*weights, axis=1)+np.sum(_quadratic(i, l), axis=1))
        rate = dx*(np.sum(np.einsum('tni,ij,tnj->tn', v, c, dv)*weights, axis=1)
                   +np.sum(np.einsum('tni,ij,tnj->tn', i, l, di), axis=1))
        series = dx*np.sum(_quadratic(i, r), axis=1)
        shunt = dx*np.sum(_quadratic(v, g)*weights, axis=1)
        line_power = np.sum(voltage*current, axis=1)
        source_power = np.sum(drive*current[:, :2], axis=1)
        source_loss = np.sum(rs*current[:, :2]**2, axis=1)
        load_loss = np.sum(rl*current[:, 2:]**2, axis=1)
        residual = rate-line_power+series+shunt
    if (not np.all(np.isfinite(np.r_[energy, rate, line_power, series, shunt, residual]))
            or np.any(energy < 0) or np.any(series < 0) or np.any(shunt < 0)):
        raise ValueError('passive energy diagnostics exceed finite scales')
    scale = max(np.max(abs(rate)), np.max(abs(line_power)), np.max(abs(series+shunt)))
    error = float(np.max(abs(residual))/scale) if scale > 0 else 0.
    if not np.isfinite(error) or error > 1e-10:
        raise ValueError('finite circuit power balance exceeds relative 1e-10')
    data = dict(time_s=time.tolist(), source_voltages_v=drive.tolist(), R_ohm_per_m=r.tolist(),
        L_h_per_m=l.tolist(), G_s_per_m=g.tolist(), C_f_per_m=c.tolist(), length_m=length,
        cells=n, source_resistance_ohm=rs.tolist(), load_resistance_ohm=rl.tolist())
    return CoupledRLGCLadderResponse(json.dumps(data, sort_keys=True, allow_nan=False),
        time, drive, v, i, voltage, current, energy, rate, series, shunt, line_power,
        source_power, source_loss, load_loss, error)
