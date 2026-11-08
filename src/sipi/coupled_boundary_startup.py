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


def _norton_input(time, source_currents, *, R, L, G, C, length, cells,
                  source_resistance, load_resistance):
    data = _coupled_core_input(time, source_currents, R=R, L=L, G=G, C=C,
        length=length, cells=cells, _drive_name='source_currents')
    raw_source = np.asarray(source_resistance, dtype=object)
    raw_load = np.asarray(load_resistance, dtype=object)
    if raw_source.shape != (2,) or raw_load.shape != (2,):
        raise ValueError('source shunt/load resistances need two explicit entries')
    rs = tuple(None if x is None else _scalar('source_shunt_resistance', x, zero=True) for x in raw_source)
    rl = tuple(None if x is None else _scalar('load_resistance', x, zero=True) for x in raw_load)
    return (*data, rs, rl)


def _mixed_input(time, sources, *, R, L, G, C, length, cells, load_resistance):
    if not isinstance(sources, (list, tuple)) or len(sources) != 2:
        raise ValueError('sources need two explicit voltage/current objects')
    columns = []; kinds = []; resistances = []
    for source in sources:
        if not isinstance(source, dict) or source.get('kind') not in ('voltage', 'current'):
            raise ValueError('each source needs voltage or current kind')
        kind = source['kind']
        value_key, resistance_key = (('voltage_v', 'series_resistance_ohm') if kind == 'voltage'
                                     else ('current_a', 'shunt_resistance_ohm'))
        if set(source) != {'kind', value_key, resistance_key}:
            raise ValueError('source keys must match its explicit kind and units')
        values = _real(value_key, source[value_key])
        if values.ndim != 1:
            raise ValueError('each source waveform must be a one-dimensional sequence')
        raw = source[resistance_key]
        resistance = None if kind == 'current' and raw is None else _scalar(resistance_key, raw, zero=True)
        columns.append(values); kinds.append(kind); resistances.append(resistance)
    if columns[0].shape != columns[1].shape:
        raise ValueError('source waveforms must share the time rows')
    data = _coupled_core_input(time, np.column_stack(columns),
        R=R, L=L, G=G, C=C, length=length, cells=cells, _drive_name='source_values')
    raw_load = np.asarray(load_resistance, dtype=object)
    if raw_load.shape != (2,):
        raise ValueError('load resistances need two explicit entries')
    rl = tuple(None if x is None else _scalar('load_resistance', x, zero=True) for x in raw_load)
    return (*data, tuple(resistances), rl, tuple(kinds))


def _mixed_sources_data(drive, resistances, kinds):
    out = []
    for j, kind in enumerate(kinds):
        value_key, resistance_key = (('voltage_v', 'series_resistance_ohm') if kind == 'voltage'
                                     else ('current_a', 'shunt_resistance_ohm'))
        out.append(dict(kind=kind, **{value_key:drive[:, j].tolist(), resistance_key:resistances[j]}))
    return out


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
    return _coupled_boundary_response(time, source_voltages, R=R, L=L, G=G, C=C,
        length=length, cells=cells, source_resistance=source_resistance,
        load_resistance=load_resistance)


def _coupled_boundary_response(time, source_voltages, *, R, L, G, C,
                               length, cells, source_resistance, load_resistance,
                               load_capacitance=None, load_branch_resistance=None,
                               load_branch_inductance=None, norton=False, mixed_sources=False):
    if mixed_sources:
        time, drive, r, l, g, c, length, n, rs, rl, kinds = _mixed_input(time, source_voltages,
            R=R, L=L, G=G, C=C, length=length, cells=cells, load_resistance=load_resistance)
        current_source = tuple(kind == 'current' for kind in kinds)
    else:
        validator = _norton_input if norton else _boundary_input
        time, drive, r, l, g, c, length, n, rs, rl = validator(time, source_voltages,
            R=R, L=L, G=G, C=C, length=length, cells=cells,
            source_resistance=source_resistance, load_resistance=load_resistance)
        current_source = (norton, norton)
    dx = length/n; weights = np.ones(n+1); weights[[0, -1]] = .5
    nv = 2*(n+1); line_size = 4*n+2
    has_branch = load_branch_inductance is not None
    size = line_size+2 if has_branch else line_size
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
                fixed.append(j); fixed_drive.append(np.zeros(2) if current_source[j] else np.eye(2)[j])
            elif current_source[j]:
                if rs[j] is not None: stiffness[j, j] -= 1/rs[j]
                b[j, j] = 1.
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
    if has_branch:
        mass[-2:, -2:] = load_branch_inductance
        stiffness[-2:, -2:] = -load_branch_resistance
        stiffness[-2:, 2*n:2*n+2] = np.eye(2)
        stiffness[2*n:2*n+2, -2:] = -np.eye(2)
    if load_capacitance is not None:
        with np.errstate(over='ignore', invalid='ignore'):
            mass[2*n:2*n+2, 2*n:2*n+2] += load_capacitance
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
        v = x[:, :nv].reshape(len(time), n+1, 2); i = x[:, nv:line_size].reshape(len(time), n, 2)
        dv = rhs[:, :nv].reshape(v.shape); di = rhs[:, nv:line_size].reshape(i.shape)
        voltage = v[:, [0, n], :].reshape(len(time), 4)
        current = np.zeros((len(time), 4))
        near = (dv[:, 0]@c.T+v[:, 0]@g.T)*dx*.5+i[:, 0]
        far = (dv[:, -1]@c.T+v[:, -1]@g.T)*dx*.5-i[:, -1]
        for j in range(2):
            if current_source[j]:
                current[:, j] = near[:, j] if rs[j] == 0 else drive[:, j]-(0. if rs[j] is None else v[:, 0, j]/rs[j])
            else:
                current[:, j] = near[:, j] if rs[j] == 0 else (drive[:, j]-v[:, 0, j])/rs[j]
            current[:, 2+j] = far[:, j] if rl[j] == 0 else 0. if rl[j] is None else -v[:, -1, j]/rl[j]
        if load_capacitance is not None:
            cap_current = dv[:, -1]@load_capacitance.T
            for j in range(2):
                if rl[j] != 0:
                    current[:, 2+j] -= cap_current[:, j]
        if has_branch:
            branch_current = x[:, -2:]; branch_derivative = rhs[:, -2:]
            for j in range(2):
                if rl[j] != 0:
                    current[:, 2+j] -= branch_current[:, j]
        energy = .5*dx*(np.sum(_quadratic(v, c)*weights, axis=1)+np.sum(_quadratic(i, l), axis=1))
        rate = dx*(np.sum(np.einsum('tni,ij,tnj->tn', v, c, dv)*weights, axis=1)
                   +np.sum(np.einsum('tni,ij,tnj->tn', i, l, di), axis=1))
        series = dx*np.sum(_quadratic(i, r), axis=1)
        shunt = dx*np.sum(_quadratic(v, g)*weights, axis=1)
        line_power = np.sum(voltage*current, axis=1)
        if mixed_sources:
            source_power = np.zeros(len(time)); source_series = np.zeros(len(time)); source_shunt = np.zeros(len(time))
            for j in range(2):
                if current_source[j]:
                    source_power += drive[:, j]*voltage[:, j]
                    if rs[j] is not None and rs[j] > 0: source_shunt += voltage[:, j]**2/rs[j]
                else:
                    source_power += drive[:, j]*current[:, j]
                    source_series += rs[j]*current[:, j]**2
            source_loss = source_series+source_shunt
        elif norton:
            source_power = np.sum(drive*voltage[:, :2], axis=1)
            source_loss = np.zeros(len(time))
            for j in range(2):
                if rs[j] is not None and rs[j] > 0: source_loss += voltage[:, j]**2/rs[j]
        else:
            source_power = np.sum(drive*current[:, :2], axis=1)
            source_loss = np.sum(rs*current[:, :2]**2, axis=1)
        load_loss = np.zeros(len(time))
        for j in range(2):
            if load_capacitance is None:
                if rl[j] is not None: load_loss += rl[j]*current[:, 2+j]**2
            elif rl[j] is not None and rl[j] > 0:
                load_loss += v[:, -1, j]**2/rl[j]
        residual = rate-line_power+series+shunt
    if (not np.all(np.isfinite(np.r_[energy, rate, line_power, series, shunt, residual]))
            or np.any(energy < 0) or np.any(series < 0) or np.any(shunt < 0)):
        raise ValueError('passive energy diagnostics exceed finite scales')
    scale = max(np.max(abs(rate)), np.max(abs(line_power)), np.max(abs(series+shunt)))
    error = float(np.max(abs(residual))/scale) if scale > 0 else 0.
    if not np.isfinite(error) or error > 1e-10:
        raise ValueError('finite circuit power balance exceeds relative 1e-10')
    data = dict(time_s=time.tolist(), R_ohm_per_m=r.tolist(),
        L_h_per_m=l.tolist(), G_s_per_m=g.tolist(), C_f_per_m=c.tolist(), length_m=length,
        cells=n, load_resistance_ohm=list(rl))
    if mixed_sources:
        data.update(sources=_mixed_sources_data(drive, rs, kinds))
    elif norton:
        data.update(source_currents_a=drive.tolist(), source_shunt_resistance_ohm=list(rs))
    else:
        data.update(source_voltages_v=drive.tolist(), source_resistance_ohm=rs.tolist())
    if load_capacitance is not None:
        data['load_capacitance_f'] = load_capacitance.tolist()
    if has_branch:
        data['load_branch_resistance_ohm'] = load_branch_resistance.tolist()
        data['load_branch_inductance_h'] = load_branch_inductance.tolist()
    if mixed_sources:
        response = dict(input_json=json.dumps(data, sort_keys=True, allow_nan=False),
            time=time, source_values=drive, node_voltage=v, segment_current=i,
            voltage=voltage, current=current, energy=energy, energy_rate=rate,
            series_loss=series, shunt_loss=shunt, line_power=line_power,
            source_power=source_power, source_series_resistor_loss=source_series,
            source_shunt_resistor_loss=source_shunt,
            load_resistor_loss=load_loss, power_balance_relative_error=error)
    elif norton:
        response = dict(input_json=json.dumps(data, sort_keys=True, allow_nan=False),
            time=time, source_currents=drive, node_voltage=v, segment_current=i,
            voltage=voltage, current=current, energy=energy, energy_rate=rate,
            series_loss=series, shunt_loss=shunt, line_power=line_power,
            source_power=source_power, source_shunt_resistor_loss=source_loss,
            load_resistor_loss=load_loss, power_balance_relative_error=error)
    else:
        response = MixedBoundaryRLGCLadderResponse(json.dumps(data, sort_keys=True, allow_nan=False),
            time, drive, v, i, voltage, current, energy, rate, series, shunt, line_power,
            source_power, source_loss, load_loss, error)
    if load_capacitance is None:
        return response
    with np.errstate(over='ignore', invalid='ignore'):
        cap_energy = .5*_quadratic(v[:, -1], load_capacitance)
        cap_power = np.sum(v[:, -1]*cap_current, axis=1)
        total_rate = rate+cap_power
        total_loss = source_loss+load_loss+series+shunt
        if has_branch:
            branch_energy = .5*_quadratic(branch_current, load_branch_inductance)
            branch_rate = np.einsum('ti,ij,tj->t', branch_current, load_branch_inductance, branch_derivative)
            branch_loss = _quadratic(branch_current, load_branch_resistance)
            total_rate = total_rate+branch_rate
            total_loss = total_loss+branch_loss
        total_residual = total_rate-source_power+total_loss
    if (not np.all(np.isfinite(np.r_[cap_energy, cap_power, total_rate, total_loss, total_residual]))
            or np.any(cap_energy < 0)):
        raise ValueError('load capacitor diagnostics exceed finite scales')
    if has_branch and (not np.all(np.isfinite(np.r_[branch_energy, branch_rate, branch_loss]))
                       or np.any(branch_energy < 0) or np.any(branch_loss < 0)):
        raise ValueError('load RL branch diagnostics exceed finite scales')
    total_scale = max(np.max(abs(total_rate)), np.max(abs(source_power)), np.max(abs(total_loss)))
    total_error = float(np.max(abs(total_residual))/total_scale) if total_scale > 0 else 0.
    if not np.isfinite(total_error) or total_error > 1e-10:
        raise ValueError('line plus load capacitor power balance exceeds relative 1e-10')
    if has_branch:
        return (response, cap_current, cap_energy, cap_power, total_error,
                branch_current, branch_energy, branch_rate, branch_loss)
    return response, cap_current, cap_energy, cap_power, total_error
