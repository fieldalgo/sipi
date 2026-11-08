# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit passive scalar Debye polarization states in a finite line circuit."""
from dataclasses import dataclass, fields
import json

import numpy as np
from scipy.signal import lsim

from .network import _real
from .rlgc_startup import _ladder_input
from .sampling import _integer

__all__ = ['DebyeRLGCLadderResponse', 'debye_rlgc_ladder_response']


@dataclass(frozen=True)
class DebyeRLGCLadderResponse:
    """Separate instantaneous and polarization energies; currents enter the line.

    Polarization arrays have shape (time, node, declared pole), retaining zero
    strengths and input order. Charge/current are lumped node quantities, C/A.
    This is deliberately separate from constant-capacitance response classes.
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

    def __post_init__(self):
        for field in fields(self):
            if field.type is not np.ndarray:
                continue
            value = np.array(getattr(self, field.name), dtype=float, copy=True)
            if not np.all(np.isfinite(value)):
                raise ValueError('Debye startup output must remain finite')
            value.setflags(write=False)
            object.__setattr__(self, field.name, value)
        if not all(np.all(np.isfinite(a)) for a in (self.total_energy, self.total_energy_rate)):
            raise ValueError('combined Debye startup energy must remain finite')

    @property
    def port_names(self):
        return ('source', 'load')

    @property
    def inputs(self):
        return json.loads(self.input_json)

    @property
    def total_energy(self):
        with np.errstate(over='ignore', invalid='ignore'):
            value = self.energy+self.polarization_energy
        value.setflags(write=False)
        return value

    @property
    def total_energy_rate(self):
        with np.errstate(over='ignore', invalid='ignore'):
            value = self.energy_rate+self.polarization_energy_rate
        value.setflags(write=False)
        return value

    def to_dict(self, *, include_states=False):
        if type(include_states) is not bool:
            raise ValueError('include_states must be a boolean')
        out = dict(scope='finite-passive-scalar-debye-ladder-startup', input=self.inputs,
            port_names=list(self.port_names), time_s=self.time.tolist(),
            voltage_v=self.voltage.tolist(), current_into_line_a=self.current.tolist(),
            instantaneous_energy_j=self.energy.tolist(), energy_rate_w=self.energy_rate.tolist(),
            polarization_energy_j=self.polarization_energy.tolist(),
            polarization_energy_rate_w=self.polarization_energy_rate.tolist(),
            total_energy_j=self.total_energy.tolist(), total_energy_rate_w=self.total_energy_rate.tolist(),
            relaxation_loss_w=self.relaxation_loss.tolist(), series_loss_w=self.series_loss.tolist(),
            shunt_loss_w=self.shunt_loss.tolist(), line_power_w=self.line_power.tolist(),
            source_power_w=self.source_power.tolist(), source_resistor_loss_w=self.source_resistor_loss.tolist(),
            load_resistor_loss_w=self.load_resistor_loss.tolist(),
            power_balance_relative_error=self.power_balance_relative_error,
            total_power_balance_relative_error=self.total_power_balance_relative_error,
            states_included=include_states)
        if include_states:
            data = self.inputs
            out.update(node_positions_m=np.linspace(0., data['length_m'], data['cells']+1).tolist(),
                segment_centres_m=((np.arange(data['cells'])+.5)*data['length_m']/data['cells']).tolist(),
                node_voltage_v=self.node_voltage.tolist(), segment_current_a=self.segment_current.tolist(),
                polarization_voltage_v=self.polarization_voltage.tolist(),
                polarization_charge_c=self.polarization_charge.tolist(),
                polarization_current_a=self.polarization_current.tolist())
        return out


def _debye_input(time, source_voltages, *, R, L, G, C_inf, delta_C, relaxation_hz,
                 length, cells, source_resistance, load_resistance):
    cells = _integer(cells, 1, 128)
    base = _ladder_input(time, source_voltages, R=R, L=L, G=G, C=C_inf,
        length=length, cells=cells, source_resistance=source_resistance,
        load_resistance=load_resistance)
    delta = _real('delta_C', delta_C); poles = _real('relaxation_hz', relaxation_hz)
    if (delta.ndim != 1 or not 1 <= len(delta) <= 4 or poles.shape != delta.shape
            or np.any(delta < 0) or np.any(poles <= 0)):
        raise ValueError('delta_C needs 1..4 nonnegative strengths and matching positive relaxation_hz')
    return (*base, delta, poles)


def debye_rlgc_ladder_response(time, source_voltages, *, R, L, G, C_inf, delta_C,
                               relaxation_hz, length, cells, source_resistance, load_resistance):
    """Propagate a zero-state scalar line with explicit passive Debye capacitance.

    C*(f)=C_inf+sum(delta_C/(1+j*f/relaxation_hz)), with C_inf>0 and 1..4
    strengths >=0 in F/m, positive relaxation frequencies in Hz. R>=0 ohm/m,
    L>0 H/m and G>=0 S/m are constant; length>0 m. Explicit cells=1..128,
    time=2..10000 uniform samples starting at zero, matching real voltage PWL
    drive starting at zero. The final drive is held; its final slope is zero.
    Finite source/load resistance >=0; source zero is ideal, load zero short,
    load None open. Limits are resource bounds, not accuracy guarantees.

    Each active pole has tau*w'=V-w, tau=1/(2*pi*f_relax). Half-end shunts
    retain polarization even at prescribed voltages. Positive auxiliary
    capacitance energy and relaxation resistor loss are reported separately
    from C_inf/L energy. Zero-strength poles have zero reported states.
    SciPy lsim integrates the finite PWL circuit; line and supplied-source
    energy balances both require relative error <=1e-10.

    No automatic material/geometry extraction, arbitrary dispersion fitting,
    skin effect, coupled conductors, reactive external loads, saved request
    or port-wave adaptation is inferred. Check time/source/space convergence.
    """
    time, drive, r, l, g, c, length, n, rs, rl, delta, poles = _debye_input(
        time, source_voltages, R=R, L=L, G=G, C_inf=C_inf, delta_C=delta_C,
        relaxation_hz=relaxation_hz, length=length, cells=cells,
        source_resistance=source_resistance, load_resistance=load_resistance)
    dx = length/n; nv = n+1; base = 2*n+1
    weights = np.ones(nv); weights[[0, -1]] = .5
    active = np.flatnonzero(delta > 0); size = base+len(active)*nv
    with np.errstate(over='ignore', invalid='ignore', divide='ignore', under='ignore'):
        tau = 1/(2*np.pi*poles)
        cap = c*dx*weights; leak = g*dx*weights; ind = l*dx; res = r*dx
        pcap = dx*weights[:, None]*delta[None, :]; conductance = pcap/tau
        slope = np.r_[np.diff(drive)/np.diff(time), 0.]
    if (not all(np.all(np.isfinite(x)) for x in (tau, cap, leak, ind, res, pcap, conductance, slope))
            or np.any(tau <= 0) or np.any(cap <= 0) or ind <= 0
            or np.any(pcap[:, active] <= 0) or np.any(conductance[:, active] <= 0)):
        raise ValueError('Debye cell parameters or source slopes exceed finite scales')
    mass = np.zeros(size); k = np.zeros((size, size)); b = np.zeros(size)
    mass[:nv] = cap; mass[nv:base] = ind
    k[np.arange(nv), np.arange(nv)] = -leak
    k[np.arange(nv, base), np.arange(nv, base)] = -res
    for j in range(n):
        k[j, nv+j] = -1.; k[j+1, nv+j] = 1.
        k[nv+j, j] = 1.; k[nv+j, j+1] = -1.
    with np.errstate(over='ignore', invalid='ignore', divide='ignore', under='ignore'):
        for slot, pole in enumerate(active):
            index = base+slot*nv+np.arange(nv); value = conductance[:, pole]
            mass[index] = pcap[:, pole]
            k[np.arange(nv), np.arange(nv)] -= value; k[index, index] -= value
            k[np.arange(nv), index] += value; k[index, np.arange(nv)] += value
        if rs > 0:
            k[0, 0] -= 1/rs; b[0] = 1/rs
        if rl is not None and rl > 0:
            k[n, n] -= 1/rl
        fixed = ([0] if rs == 0 else [])+([n] if rl == 0 else [])
        free = np.array([j for j in range(size) if j not in fixed])
        a = k[np.ix_(free, free)]/mass[free, None]; beta = b[free]/mass[free]
        if rs == 0:
            beta += k[free, 0]/mass[free]
    if not all(np.all(np.isfinite(x)) for x in (a, beta)):
        raise ValueError('Debye circuit coefficients exceed finite scales')
    _, _, state = lsim((a, beta[:, None], np.zeros((1, len(free))), np.zeros((1, 1))),
                        drive, time, interp=True)
    state = np.asarray(state)
    if state.ndim == 1:
        state = state[:, None]
    if state.shape != (len(time), len(free)) or not np.all(np.isfinite(state)):
        raise ValueError('state propagation returned invalid shape or nonfinite values')
    if np.any(state[0] != 0):
        raise ValueError('state propagation must preserve the zero initial state')
    with np.errstate(over='ignore', invalid='ignore', divide='ignore', under='ignore'):
        x = np.zeros((len(time), size)); rhs = np.zeros_like(x)
        x[:, free] = state; rhs[:, free] = state@a.T+drive[:, None]*beta
        if rs == 0:
            x[:, 0] = drive; rhs[:, 0] = slope
        v = x[:, :nv]; i = x[:, nv:base]; dv = rhs[:, :nv]; di = rhs[:, nv:base]
        w = np.zeros((len(time), nv, len(delta))); dw = np.zeros_like(w)
        for slot, pole in enumerate(active):
            w[:, :, pole] = x[:, base+slot*nv:base+(slot+1)*nv]
            dw[:, :, pole] = rhs[:, base+slot*nv:base+(slot+1)*nv]
        charge = pcap*w; pcurrent = pcap*dw
        near = cap[0]*dv[:, 0]+leak[0]*v[:, 0]+pcurrent[:, 0].sum(axis=1)+i[:, 0]
        far = cap[-1]*dv[:, -1]+leak[-1]*v[:, -1]+pcurrent[:, -1].sum(axis=1)-i[:, -1]
        voltage = v[:, [0, n]]
        current = np.column_stack((near if rs == 0 else (drive-v[:, 0])/rs,
            far if rl == 0 else np.zeros(len(time)) if rl is None else -v[:, -1]/rl))
        energy = .5*np.sum(cap*v*v, axis=1)+.5*ind*np.sum(i*i, axis=1)
        rate = np.sum(cap*v*dv, axis=1)+ind*np.sum(i*di, axis=1)
        pe = .5*np.sum(pcap*w*w, axis=(1, 2)); pr = np.sum(pcap*w*dw, axis=(1, 2))
        relaxation = np.sum(conductance*(v[:, :, None]-w)**2, axis=(1, 2))
        series = res*np.sum(i*i, axis=1); shunt = np.sum(leak*v*v, axis=1)
        power = np.sum(voltage*current, axis=1); supplied = drive*current[:, 0]
        source_loss = rs*current[:, 0]**2
        load_loss = np.zeros(len(time)) if rl is None else rl*current[:, 1]**2
        losses = series+shunt+relaxation; total_rate = rate+pr
        residual = total_rate-power+losses
        combined_loss = source_loss+load_loss+losses
        total = total_rate-supplied+combined_loss
    if not all(np.all(np.isfinite(a)) for a in (rhs, total_rate, power, losses, combined_loss, supplied, residual, total)):
        raise ValueError('Debye energy diagnostics exceed finite scales')
    scale = max(np.max(abs(total_rate)), np.max(abs(power)), np.max(abs(losses)))
    tscale = max(np.max(abs(total_rate)), np.max(abs(supplied)), np.max(abs(combined_loss)))
    error = float(np.max(abs(residual))/scale) if scale else 0.
    terr = float(np.max(abs(total))/tscale) if tscale else 0.
    if not all(np.isfinite(e) and e <= 1e-10 for e in (error, terr)):
        raise ValueError('Debye circuit power balance exceeds relative 1e-10')
    data = dict(time_s=time.tolist(), source_voltages_v=drive.tolist(), R_ohm_per_m=r,
        L_h_per_m=l, G_s_per_m=g, C_inf_f_per_m=c, delta_C_f_per_m=delta.tolist(),
        relaxation_hz=poles.tolist(), length_m=length, cells=n,
        source_resistance_ohm=rs, load_resistance_ohm=rl)
    return DebyeRLGCLadderResponse(json.dumps(data, sort_keys=True, allow_nan=False),
        time, drive, v, i, voltage, current, energy, rate, series, shunt, power, supplied,
        source_loss, load_loss, w, charge, pcurrent, pe, pr, relaxation, error, terr)
