# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit positive-strength two-signal Debye startup with resistive ends."""
from dataclasses import dataclass
import json

import numpy as np
from scipy.signal import lsim

from .network import _real
from .coupled_startup import _coupled_input, _passive_matrix, _quadratic
from .debye_startup import DebyeRLGCLadderResponse

__all__ = ['CoupledDebyeRLGCLadderResponse', 'coupled_debye_rlgc_ladder_response']


@dataclass(frozen=True)
class CoupledDebyeRLGCLadderResponse:
    """Four terminals; polarization arrays (time,node,pole,conductor).

    Charges/currents include lumped node capacitance and half-end weights.
    Reuse neutral array/serialization behavior without inheriting the scalar
    response type or implicitly entering its wave/saved adapters.
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
    polarization_voltage: np.ndarray
    polarization_charge: np.ndarray
    polarization_current: np.ndarray
    polarization_energy: np.ndarray
    polarization_energy_rate: np.ndarray
    relaxation_loss: np.ndarray
    power_balance_relative_error: float
    total_power_balance_relative_error: float

    __post_init__ = DebyeRLGCLadderResponse.__post_init__
    inputs = DebyeRLGCLadderResponse.inputs
    total_energy = DebyeRLGCLadderResponse.total_energy
    total_energy_rate = DebyeRLGCLadderResponse.total_energy_rate

    @property
    def port_names(self):
        return ('near_0', 'near_1', 'far_0', 'far_1')

    def to_dict(self, *, include_states=False):
        out = DebyeRLGCLadderResponse.to_dict(self, include_states=include_states)
        out['scope'] = 'finite-passive-two-signal-debye-ladder-startup'
        return out


def _coupled_debye_input(time, source_voltages, *, R, L, G, C_inf, delta_C,
                         relaxation_hz, length, cells, source_resistance, load_resistance):
    data = _coupled_input(time, source_voltages, R=R, L=L, G=G, C=C_inf,
        length=length, cells=cells, source_resistance=source_resistance,
        load_resistance=load_resistance)
    delta = _real('delta_C', delta_C); poles = _real('relaxation_hz', relaxation_hz)
    if (delta.ndim != 3 or delta.shape[1:] != (2, 2) or not 1 <= len(delta) <= 2
            or poles.shape != (len(delta),) or np.any(poles <= 0)):
        raise ValueError('delta_C needs 1..2 real 2x2 matrices and matching positive relaxation_hz')
    for index, matrix in enumerate(delta):
        if np.any(matrix):
            try:
                _passive_matrix('C', matrix)
            except ValueError as exc:
                raise ValueError(f'delta_C[{index}] must be exactly symmetric SPD with eigenvalue ratio above 1e-12, or exactly zero') from exc
    return (*data, delta, poles)


def coupled_debye_rlgc_ladder_response(time, source_voltages, *, R, L, G, C_inf,
        delta_C, relaxation_hz, length, cells, source_resistance, load_resistance):
    """Propagate an explicit passive two-signal Debye circuit from zero state.

    Constant real exactly symmetric2x2 R/G are PSD; L/C_inf are SPD with
    normalized eigenvalue ratio above1e-12. Capacitance is C_inf plus
    sum(delta_C/(1+j*f/relaxation_hz)), with 1..2 strengths each SPD at the
    same ratio or exactly zero; arbitrary singular/rank-one strengths are
    rejected. Negative eigenvalues are never repaired. Units are ohm/m,H/m,
    S/m,F/m,Hz,m. Source/load each specify two finite positive ohm values.

    Explicit cells1..128 and uniform time2..10000 starting0; source voltage
    shape(times,2) has a zero first row. SciPy lsim propagates its PWL
    interpolant, with zero initial state and half shunts at both ends.
    Each auxiliary vector obeys tau*w'=V-w. Instantaneous Cinf/L and
    polarization energy/rate are separate; relaxation and R/G/source/load
    resistor losses enter relative1e-10 line/source balance guards.
    Pole order/zero matrices are preserved, but zero strengths omit states.

    Counts are resource bounds, not convergence or execution-time guarantees.
    No ideal/open/short/reactive/current-source ends, general PSD strengths,
    field/material extraction, arbitrary fitting, wave/saved adaptation or
    measured-board accuracy is inferred. Check time,source and space limits.
    """
    data = _coupled_debye_input(
        time, source_voltages, R=R, L=L, G=G, C_inf=C_inf, delta_C=delta_C,
        relaxation_hz=relaxation_hz, length=length, cells=cells,
        source_resistance=source_resistance, load_resistance=load_resistance)
    return _propagate_coupled_debye(data, psd_strength=False,
        result_type=CoupledDebyeRLGCLadderResponse, propagator=lsim)


def _propagate_coupled_debye(data, *, psd_strength, result_type, propagator):
    """Shared circuit propagation; strict-SPD path preserves original arithmetic."""
    time, drive, r, l, g, c, length, n, rs, rl, delta, poles = data
    dx = length/n; weights = np.ones(n+1); weights[[0, -1]] = .5
    active = [index for index, matrix in enumerate(delta) if np.any(matrix)]
    nv = 2*(n+1); base = nv+2*n; size = base+len(active)*nv
    with np.errstate(over='ignore', invalid='ignore', divide='ignore', under='ignore'):
        tau = 1/(2*np.pi*poles)
        storage = [.5*dx*c, dx*l] if psd_strength else [.5*dx*c, dx*l, *[.5*dx*delta[p] for p in active]]
        conductance = [dx*delta[p]/tau[p] for p in active]
        slopes = np.diff(drive, axis=0)/np.diff(time)[:, None]
    if (dx <= 0 or np.any(tau <= 0)
            or not all(np.all(np.isfinite(x)) for x in [tau, slopes, *storage, *conductance])
            or any(np.linalg.eigvalsh(x)[0] <= 0 for x in storage)
            or (any(not np.any(x) or np.linalg.eigvalsh(x)[0] < 0 for x in conductance)
                if psd_strength else any(np.linalg.eigvalsh(x)[0] <= 0 for x in conductance))):
        raise ValueError('Debye cell matrices or source slopes exceed finite scales')
    mass = np.zeros((size, size)); k = np.zeros_like(mass); b = np.zeros((size, 2))
    with np.errstate(over='ignore', invalid='ignore', divide='ignore', under='ignore'):
        mass[:nv, :nv] = np.kron(np.diag(dx*weights), c)
        mass[nv:base, nv:base] = np.kron(np.eye(n)*dx, l)
        k[:nv, :nv] = -np.kron(np.diag(dx*weights), g)
        k[nv:base, nv:base] = -np.kron(np.eye(n)*dx, r)
        for j in range(n):
            near = slice(2*j, 2*j+2); far = slice(2*j+2, 2*j+4)
            segment = slice(nv+2*j, nv+2*j+2)
            k[near, segment] = -np.eye(2); k[far, segment] = np.eye(2)
            k[segment, near] = np.eye(2); k[segment, far] = -np.eye(2)
        for slot, pole in enumerate(active):
            sl = slice(base+slot*nv, base+(slot+1)*nv)
            cap = np.kron(np.diag(dx*weights), delta[pole]); cond = cap/tau[pole]
            if psd_strength:
                mass[sl, sl] = np.eye(nv); k[:nv, :nv] -= cond
                k[sl, sl] = -np.eye(nv)/tau[pole]
                k[:nv, sl] += cond; k[sl, :nv] = np.eye(nv)/tau[pole]
            else:
                mass[sl, sl] = cap; k[:nv, :nv] -= cond; k[sl, sl] -= cond
                k[:nv, sl] += cond; k[sl, :nv] += cond
        k[:2, :2] -= np.diag(1/rs); k[nv-2:nv, nv-2:nv] -= np.diag(1/rl)
        b[:2] = np.diag(1/rs)
    if not all(np.all(np.isfinite(x)) for x in (mass, k, b)):
        raise ValueError('Debye circuit coefficients exceed finite scales')
    with np.errstate(over='ignore', invalid='ignore', divide='ignore', under='ignore'):
        a = np.linalg.solve(mass, k); beta = np.linalg.solve(mass, b)
    if not all(np.all(np.isfinite(x)) for x in (a, beta)):
        raise ValueError('Debye normalized coefficients exceed finite scales')
    _, _, x = propagator((a, beta, np.zeros((1, size)), np.zeros((1, 2))), drive, time, interp=True)
    x = np.asarray(x)
    if x.shape != (len(time), size) or not np.all(np.isfinite(x)):
        raise ValueError('state propagation returned invalid shape or nonfinite values')
    if np.any(x[0] != 0):
        raise ValueError('state propagation must preserve the zero initial state')
    with np.errstate(over='ignore', invalid='ignore', divide='ignore', under='ignore'):
        rhs = x@a.T+drive@beta.T
        v = x[:, :nv].reshape(len(time), n+1, 2); i = x[:, nv:base].reshape(len(time), n, 2)
        dv = rhs[:, :nv].reshape(v.shape); di = rhs[:, nv:base].reshape(i.shape)
        shape = (len(time), n+1, len(delta), 2)
        w = np.zeros(shape); dw = np.zeros(shape); charge = np.zeros(shape); pcurrent = np.zeros(shape)
        for slot, pole in enumerate(active):
            w[:, :, pole] = x[:, base+slot*nv:base+(slot+1)*nv].reshape(v.shape)
            dw[:, :, pole] = rhs[:, base+slot*nv:base+(slot+1)*nv].reshape(v.shape)
            charge[:, :, pole] = dx*weights[None, :, None]*(w[:, :, pole]@delta[pole].T)
            pcurrent[:, :, pole] = dx*weights[None, :, None]*(dw[:, :, pole]@delta[pole].T)
        energy = .5*dx*(np.sum(weights*_quadratic(v, c), axis=1)+np.sum(_quadratic(i, l), axis=1))
        rate = dx*(np.sum(weights*np.einsum('tni,ij,tnj->tn', v, c, dv), axis=1)
                   +np.sum(np.einsum('tni,ij,tnj->tn', i, l, di), axis=1))
        pe = np.zeros(len(time)); pr = np.zeros(len(time)); relaxation = np.zeros(len(time))
        for pole in active:
            mat = delta[pole]; wp = w[:, :, pole]; dwp = dw[:, :, pole]
            pe += .5*dx*np.sum(weights*_quadratic(wp, mat), axis=1)
            pr += dx*np.sum(weights*np.einsum('tni,ij,tnj->tn', wp, mat, dwp), axis=1)
            relaxation += dx/tau[pole]*np.sum(weights*_quadratic(v-wp, mat), axis=1)
        voltage = np.concatenate((v[:, 0], v[:, -1]), axis=1)
        current = np.concatenate(((drive-v[:, 0])/rs, -v[:, -1]/rl), axis=1)
        series = dx*np.sum(_quadratic(i, r), axis=1)
        shunt = dx*np.sum(weights*_quadratic(v, g), axis=1)
        power = np.sum(voltage*current, axis=1); supplied = np.sum(drive*current[:, :2], axis=1)
        source_loss = np.sum(rs*current[:, :2]**2, axis=1); load_loss = np.sum(rl*current[:, 2:]**2, axis=1)
        total_rate = rate+pr; losses = series+shunt+relaxation
        combined_loss = source_loss+load_loss+losses
        residual = total_rate-power+losses; total = total_rate-supplied+combined_loss
    if (not all(np.all(np.isfinite(a)) for a in (rhs, energy, pe, total_rate, power, supplied, losses, combined_loss, residual, total))
            or any(np.any(a < 0) for a in (energy, pe, relaxation, series, shunt, source_loss, load_loss))):
        raise ValueError('passive Debye energy diagnostics exceed finite scales')
    scale = max(np.max(abs(total_rate)), np.max(abs(power)), np.max(abs(losses)))
    tscale = max(np.max(abs(total_rate)), np.max(abs(supplied)), np.max(abs(combined_loss)))
    error = float(np.max(abs(residual))/scale) if scale else 0.
    terr = float(np.max(abs(total))/tscale) if tscale else 0.
    if not all(np.isfinite(e) and e <= 1e-10 for e in (error, terr)):
        raise ValueError('Debye circuit power balance exceeds relative 1e-10')
    data = dict(time_s=time.tolist(), source_voltages_v=drive.tolist(), R_ohm_per_m=r.tolist(),
        L_h_per_m=l.tolist(), G_s_per_m=g.tolist(), C_inf_f_per_m=c.tolist(),
        delta_C_f_per_m=delta.tolist(), relaxation_hz=poles.tolist(), length_m=length,
        cells=n, source_resistance_ohm=rs.tolist(), load_resistance_ohm=rl.tolist())
    return result_type(json.dumps(data, sort_keys=True, allow_nan=False),
        time, drive, v, i, voltage, current, energy, rate, series, shunt, power, supplied,
        source_loss, load_loss, w, charge, pcurrent, pe, pr, relaxation, error, terr)
