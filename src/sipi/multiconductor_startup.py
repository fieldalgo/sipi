# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit three/four-signal constant RLGC zero-state finite circuits."""
from dataclasses import dataclass
import json

import numpy as np
from scipy.signal import lsim

from .network import _real, _scalar
from .sampling import _integer
from .startup import _times
from .coupled_startup import _quadratic
from .rlgc_startup import RLGCLadderResponse

__all__ = ['MulticonductorRLGCLadderResponse', 'multiconductor_rlgc_ladder_response']


@dataclass(frozen=True)
class MulticonductorRLGCLadderResponse:
    """Copied/read-only states, with near signals followed by far signals.

    Both terminal currents enter the line; segment currents point toward far.
    This independent class does not implicitly enter two/four-port wave APIs.
    """
    input_json: str
    time: np.ndarray
    source_voltages: np.ndarray
    node_voltage: np.ndarray
    segment_current: np.ndarray
    voltage: np.ndarray
    current: np.ndarray
    energy: np.ndarray
    energy_rate: np.ndarray
    series_loss: np.ndarray
    shunt_loss: np.ndarray
    line_power: np.ndarray
    source_power: np.ndarray
    source_resistor_loss: np.ndarray
    load_resistor_loss: np.ndarray
    power_balance_relative_error: float

    total_power_balance_relative_error: float

    __post_init__ = RLGCLadderResponse.__post_init__
    inputs = RLGCLadderResponse.inputs

    @property
    def port_names(self):
        return tuple(f'{end}_{j}' for end in ('near', 'far')
                     for j in range(self.inputs['signals']))

    def to_dict(self, *, include_states=False):
        out = RLGCLadderResponse.to_dict(self, include_states=include_states)
        out['scope'] = 'finite-passive-multiconductor-rlgc-ladder-startup'
        out['total_power_balance_relative_error'] = self.total_power_balance_relative_error
        return out


def _multiconductor_matrix(name, value, signals):
    matrix = _real(name, value)
    if matrix.shape != (signals, signals) or not np.array_equal(matrix, matrix.T):
        raise ValueError(f'{name} must be an exactly symmetric real signals-by-signals matrix')
    scale = np.max(abs(matrix))
    if scale == 0 and name in ('R', 'G'):
        return matrix
    eigen = np.linalg.eigvalsh(matrix/scale) if scale else np.zeros(signals)
    if eigen[0] <= 1e-12*eigen[-1]:
        raise ValueError(f'{name} needs SPD eigenvalue ratio above 1e-12; R/G also allow exact zero')
    return matrix


def _multiconductor_input(time, source_voltages, *, signals, R, L, G, C,
                          length, cells, source_resistance, load_resistance):
    signals = _integer(signals, 3, 4)
    time = _times('time', time)
    if not 2 <= len(time) <= 10000 or time[0] != 0:
        raise ValueError('time needs 2..10000 samples starting at zero')
    dt = np.diff(time)
    if not np.allclose(dt, dt[0], rtol=1e-10, atol=0):
        raise ValueError('time spacing must be uniform within relative 1e-10')
    drive = _real('source_voltages', source_voltages)
    if drive.shape != (len(time), signals) or np.any(drive[0] != 0):
        raise ValueError('source_voltages needs shape (times,signals) and a zero first row')
    r, l, g, c = [_multiconductor_matrix(name, value, signals)
                  for name, value in [('R', R), ('L', L), ('G', G), ('C', C)]]
    length = _scalar('length', length); cells = _integer(cells, 1, 128)
    rs = _real('source_resistance', source_resistance)
    rl = _real('load_resistance', load_resistance)
    if rs.shape != (signals,) or rl.shape != (signals,) or np.any(rs <= 0) or np.any(rl <= 0):
        raise ValueError('source/load resistance each need signals finite positive values')
    return time, drive, signals, r, l, g, c, length, cells, rs, rl


def multiconductor_rlgc_ladder_response(time, source_voltages, *, signals,
                                        R, L, G, C, length, cells,
                                        source_resistance, load_resistance):
    """Propagate an explicit three/four-signal finite uniform RLGC circuit.

    Constant SI R[ohm/m], L[H/m], G[S/m], C[F/m] are exactly symmetric real
    matrices. L/C are SPD; R/G are SPD or exactly zero. Every nonzero matrix
    needs eigenvalue ratio >1e-12. No repair or nonzero singular PSD admission.
    Both resistance vectors are finite positive. Explicit cells1..128 and
    uniform time2..10000 starting0 bound the zero-state PWL drive(times,signals),
    whose first row is zero. End C/G have half weights; N*(2*cells+1) states.
    Line and source power balance each retain relative1e-10 acceptance.

    This is a finite circuit using SciPy lsim, not extracted fields or a
    continuous-line accuracy guarantee. Check input-specific time/source/space
    convergence. Dispersion, reactive/current/ideal/open/short ends and general
    singular PSD R/G require separate models. No saved/wave adapter is inferred.
    """
    time, drive, signals, r, l, g, c, length, n, rs, rl = _multiconductor_input(
        time, source_voltages, signals=signals, R=R, L=L, G=G, C=C,
        length=length, cells=cells, source_resistance=source_resistance,
        load_resistance=load_resistance)
    dx = length/n; weights = np.ones(n+1); weights[[0, -1]] = .5
    nv = signals*(n+1); size = signals*(2*n+1)
    with np.errstate(over='ignore', invalid='ignore', divide='ignore', under='ignore'):
        cap = c*dx; ind = l*dx
        ci = np.linalg.inv(c); li = np.linalg.inv(l)
        slopes = np.diff(drive, axis=0)/np.diff(time)[:, None]
    if (dx <= 0 or not np.all(np.isfinite(np.r_[cap.ravel(), ind.ravel(), ci.ravel(), li.ravel(), slopes.ravel()]))
            or np.linalg.eigvalsh(cap)[0] <= 0 or np.linalg.eigvalsh(ind)[0] <= 0):
        raise ValueError('cell matrices or source slopes exceed finite scales')
    a = np.zeros((size, size)); b = np.zeros((size, signals))
    with np.errstate(over='ignore', invalid='ignore', divide='ignore', under='ignore'):
        for k in range(n+1):
            vs = slice(signals*k, signals*(k+1)); vc = ci/(dx*weights[k]); a[vs, vs] = -ci@g
            if k > 0: a[vs, nv+signals*(k-1):nv+signals*k] = vc
            if k < n: a[vs, nv+signals*k:nv+signals*(k+1)] = -vc
            if k == 0:
                source = vc@np.diag(1/rs); a[vs, vs] -= source; b[vs] = source
            if k == n: a[vs, vs] -= vc@np.diag(1/rl)
        for k in range(n):
            ids = slice(nv+signals*k, nv+signals*(k+1))
            a[ids, signals*k:signals*(k+1)] = li/dx; a[ids, signals*(k+1):signals*(k+2)] = -li/dx
            a[ids, ids] = -li@r
    if not np.all(np.isfinite(a)) or not np.all(np.isfinite(b)):
        raise ValueError('circuit coefficients exceed finite scales')
    _, _, x = lsim((a, b, np.zeros((1, size)), np.zeros((1, signals))), drive, time, interp=True)
    x = np.asarray(x)
    if x.shape != (len(time), size) or not np.all(np.isfinite(x)) or np.any(x[0] != 0):
        raise ValueError('state propagation returned invalid shape, nonfinite values or nonzero initial state')
    with np.errstate(over='ignore', invalid='ignore', divide='ignore', under='ignore'):
        rhs = x@a.T+drive@b.T
        v = x[:, :nv].reshape(len(time), n+1, signals); i = x[:, nv:].reshape(len(time), n, signals)
        dv = rhs[:, :nv].reshape(v.shape); di = rhs[:, nv:].reshape(i.shape)
        voltage = v[:, [0, n], :].reshape(len(time), 2*signals)
        current = np.concatenate(((drive-v[:, 0])/rs, -v[:, -1]/rl), axis=1)
        energy = .5*dx*(np.sum(_quadratic(v, c)*weights, axis=1)+np.sum(_quadratic(i, l), axis=1))
        rate = dx*(np.sum(np.einsum('tni,ij,tnj->tn', v, c, dv)*weights, axis=1)
                   +np.sum(np.einsum('tni,ij,tnj->tn', i, l, di), axis=1))
        series = dx*np.sum(_quadratic(i, r), axis=1)
        shunt = dx*np.sum(_quadratic(v, g)*weights, axis=1)
        line_power = np.sum(voltage*current, axis=1)
        source_power = np.sum(drive*current[:, :signals], axis=1)
        source_loss = np.sum(rs*current[:, :signals]**2, axis=1)
        load_loss = np.sum(rl*current[:, signals:]**2, axis=1)
        residual = rate-line_power+series+shunt
        total_loss = series+shunt+source_loss+load_loss
        total = rate-source_power+total_loss
    if (not all(np.all(np.isfinite(value)) for value in
                (rhs, voltage, current, energy, rate, line_power, series, shunt,
                 source_power, source_loss, load_loss, residual, total))
            or any(np.any(value < 0) for value in (energy, series, shunt, source_loss, load_loss))):
        raise ValueError('passive energy diagnostics exceed finite scales')
    scale = max(np.max(abs(rate)), np.max(abs(line_power)), np.max(abs(series+shunt)))
    total_scale = max(np.max(abs(rate)), np.max(abs(source_power)), np.max(abs(total_loss)))
    error = float(np.max(abs(residual))/scale) if scale > 0 else 0.
    total_error = float(np.max(abs(total))/total_scale) if total_scale > 0 else 0.
    if not all(np.isfinite(value) and value <= 1e-10 for value in (error, total_error)):
        raise ValueError('finite circuit line/source power balance exceeds relative 1e-10')
    data = dict(signals=signals, time_s=time.tolist(), source_voltages_v=drive.tolist(), R_ohm_per_m=r.tolist(),
        L_h_per_m=l.tolist(), G_s_per_m=g.tolist(), C_f_per_m=c.tolist(), length_m=length,
        cells=n, source_resistance_ohm=rs.tolist(), load_resistance_ohm=rl.tolist())
    return MulticonductorRLGCLadderResponse(json.dumps(data, sort_keys=True, allow_nan=False),
        time, drive, v, i, voltage, current, energy, rate, series, shunt, line_power,
        source_power, source_loss, load_loss, error, total_error)
