# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Two-signal finite RLGC startup with mixed ideal/resistive/open/short ends."""
import json

import numpy as np
from scipy.signal import lsim

from .network import _real, _scalar
from .coupled_startup import CoupledRLGCLadderResponse, _coupled_core_input, _quadratic

__all__ = ['MixedBoundaryRLGCLadderResponse', 'coupled_boundary_ladder_response']


class MixedBoundaryRLGCLadderResponse(CoupledRLGCLadderResponse):
    """Two-signal circuit response with explicit per-conductor mixed ends."""
    def to_dict(self, *, include_states=False):
        out = super().to_dict(include_states=include_states)
        out['scope'] = 'finite-passive-two-signal-mixed-boundary-rlgc-startup'
        return out


def _boundary_input(time, source_voltages, *, R, L, G, C, length, cells,
                    source_resistance, load_resistance):
    data = _coupled_core_input(time, source_voltages,
        R=R, L=L, G=G, C=C, length=length, cells=cells)
    rs = _real('source_resistance', source_resistance)
    raw_load = np.asarray(load_resistance, dtype=object)
    if rs.shape != (2,) or np.any(rs < 0) or raw_load.shape != (2,):
        raise ValueError('source/load resistance need two entries; sources finite and nonnegative')
    rl = tuple(None if x is None else _scalar('load_resistance', x, zero=True) for x in raw_load)
    return (*data, rs, rl)


def coupled_boundary_ladder_response(time, source_voltages, *, R, L, G, C,
                                     length, cells, source_resistance, load_resistance):
    """Propagate a two-signal passive finite circuit with explicit mixed ends.

    Same constant real exactly symmetric2x2 PSD R/G, conditioned SPD L/C,
    cells1..128, uniform2..10000times and zero-first PWL(times,2) contract as
    coupled_rlgc_ladder_response. Source resistances are finite>=0 (0=ideal),
    load entries finite>=0 (0=short) or None=open; both vectors explicit.
    Zero initial stored energy is required. No reactive external elements.

    Mass-matrix elimination retains mutual endpoint capacitance. A change of
    free state removes prescribed-voltage derivative forcing before PWL lsim;
    state/current reconstruction uses right source slopes and final slope0.
    All four port currents enter the line; short/ideal currents include full
    endpoint C*dV/dt+G*V. This is a finite circuit with input-specific spatial,
    source and time convergence requirements, not an exact continuous line.
    """
    time, drive, r, l, g, c, length, n, rs, rl = _boundary_input(time, source_voltages,
        R=R, L=L, G=G, C=C, length=length, cells=cells,
        source_resistance=source_resistance, load_resistance=load_resistance)
    dx = length/n; weights = np.ones(n+1); weights[[0, -1]] = .5
    nv = 2*(n+1); size = 4*n+2
    with np.errstate(over='ignore', invalid='ignore', divide='ignore', under='ignore'):
        cap = c*dx*.5; ind = l*dx
        slope = np.vstack((np.diff(drive, axis=0)/np.diff(time)[:, None], [0., 0.]))
    if (dx <= 0 or not np.all(np.isfinite(np.r_[cap.ravel(), ind.ravel(), slope.ravel()]))
            or np.linalg.eigvalsh(cap)[0] <= 0 or np.linalg.eigvalsh(ind)[0] <= 0):
        raise ValueError('cell matrices or source slopes exceed finite scales')
    mass = np.zeros((size, size)); stiffness = np.zeros_like(mass); b = np.zeros((size, 2))
    fixed = []; fixed_drive = []
    with np.errstate(over='ignore', invalid='ignore', divide='ignore', under='ignore'):
        for node in range(n+1):
            s = slice(2*node, 2*node+2)
            mass[s, s] = c*dx*weights[node]; stiffness[s, s] = -g*dx*weights[node]
            if node > 0: stiffness[s, nv+2*(node-1):nv+2*node] = np.eye(2)
            if node < n: stiffness[s, nv+2*node:nv+2*node+2] = -np.eye(2)
        for j in range(2):
            if rs[j] == 0:
                fixed.append(j); fixed_drive.append(np.eye(2)[j])
            else:
                stiffness[j, j] -= 1/rs[j]; b[j, j] = 1/rs[j]
            idx = 2*n+j
            if rl[j] == 0:
                fixed.append(idx); fixed_drive.append(np.zeros(2))
            elif rl[j] is not None:
                stiffness[idx, idx] -= 1/rl[j]
        for node in range(n):
            s = slice(nv+2*node, nv+2*node+2)
            mass[s, s] = l*dx; stiffness[s, s] = -r*dx
            stiffness[s, 2*node:2*node+2] = np.eye(2)
            stiffness[s, 2*node+2:2*node+4] = -np.eye(2)
    if not all(np.all(np.isfinite(x)) for x in (mass, stiffness, b)):
        raise ValueError('circuit coefficients exceed finite scales')
    free = np.array([i for i in range(size) if i not in fixed]); fixed = np.array(fixed, dtype=int)
    mapping = np.array(fixed_drive, dtype=float).reshape(len(fixed), 2)
    mf = mass[np.ix_(free, free)]
    try:
        with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
            a = np.linalg.solve(mf, stiffness[np.ix_(free, free)])
            transform = np.linalg.solve(mf, mass[np.ix_(free, fixed)])
            beta = (np.linalg.solve(mf, b[free])
                +(np.linalg.solve(mf, stiffness[np.ix_(free, fixed)])-a@transform)@mapping)
    except np.linalg.LinAlgError as exc:
        raise ValueError('free circuit mass matrix is numerically singular') from exc
    if not all(np.all(np.isfinite(x)) for x in (a, transform, beta)):
        raise ValueError('reduced circuit coefficients exceed finite scales')
    _, _, z = lsim((a, beta, np.zeros((1, len(free))), np.zeros((1, 2))), drive, time, interp=True)
    z = np.asarray(z)
    if z.shape != (len(time), len(free)) or not np.all(np.isfinite(z)):
        raise ValueError('state propagation returned invalid shape or nonfinite values')
    with np.errstate(over='ignore', invalid='ignore', divide='ignore', under='ignore'):
        xp = drive@mapping.T; dp = slope@mapping.T
        x = np.zeros((len(time), size)); rhs = np.zeros_like(x)
        x[:, free] = z-xp@transform.T; x[:, fixed] = xp
        rhs[:, free] = z@a.T+drive@beta.T-dp@transform.T; rhs[:, fixed] = dp
        v = x[:, :nv].reshape(len(time), n+1, 2); i = x[:, nv:].reshape(len(time), n, 2)
        dv = rhs[:, :nv].reshape(v.shape); di = rhs[:, nv:].reshape(i.shape)
        voltage = v[:, [0, n], :].reshape(len(time), 4)
        current = np.zeros((len(time), 4))
        near = (dv[:, 0]@c.T+v[:, 0]@g.T)*dx*.5+i[:, 0]
        far = (dv[:, -1]@c.T+v[:, -1]@g.T)*dx*.5-i[:, -1]
        for j in range(2):
            current[:, j] = near[:, j] if rs[j] == 0 else (drive[:, j]-v[:, 0, j])/rs[j]
            current[:, 2+j] = far[:, j] if rl[j] == 0 else 0. if rl[j] is None else -v[:, -1, j]/rl[j]
        energy = .5*dx*(np.sum(_quadratic(v, c)*weights, axis=1)+np.sum(_quadratic(i, l), axis=1))
        rate = dx*(np.sum(np.einsum('tni,ij,tnj->tn', v, c, dv)*weights, axis=1)
                   +np.sum(np.einsum('tni,ij,tnj->tn', i, l, di), axis=1))
        series = dx*np.sum(_quadratic(i, r), axis=1)
        shunt = dx*np.sum(_quadratic(v, g)*weights, axis=1)
        line_power = np.sum(voltage*current, axis=1)
        source_power = np.sum(drive*current[:, :2], axis=1)
        source_loss = np.sum(rs*current[:, :2]**2, axis=1)
        load_loss = np.zeros(len(time))
        for j in range(2):
            if rl[j] is not None: load_loss += rl[j]*current[:, 2+j]**2
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
        cells=n, source_resistance_ohm=rs.tolist(), load_resistance_ohm=list(rl))
    return MixedBoundaryRLGCLadderResponse(json.dumps(data, sort_keys=True, allow_nan=False),
        time, drive, v, i, voltage, current, energy, rate, series, shunt, line_power,
        source_power, source_loss, load_loss, error)
