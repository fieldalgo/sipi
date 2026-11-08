# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Zero-state passive scalar RLGC ladder propagation on an explicit time grid."""
from dataclasses import dataclass
import json

import numpy as np
from scipy.signal import lsim

from .network import _real, _scalar
from .sampling import _integer
from .startup import _times

__all__ = ['RLGCLadderResponse', 'rlgc_ladder_response']


@dataclass(frozen=True)
class RLGCLadderResponse:
    """Finite circuit states and port/energy diagnostics, copied and read-only.

    Node voltages are ordered from source to load; segment currents point +z.
    Both external port currents enter the line. Negative port power is retained.
    Interior arrays remain available even when omitted from JSON serialization.
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

    def __post_init__(self):
        for name in ('time', 'source_voltages', 'node_voltage', 'segment_current',
                     'voltage', 'current', 'energy', 'energy_rate', 'series_loss',
                     'shunt_loss', 'line_power', 'source_power', 'source_resistor_loss',
                     'load_resistor_loss'):
            value = np.array(getattr(self, name), dtype=float, copy=True)
            if not np.all(np.isfinite(value)):
                raise ValueError('ladder output must remain finite')
            value.setflags(write=False)
            object.__setattr__(self, name, value)

    @property
    def port_names(self):
        return ('source', 'load')

    @property
    def inputs(self):
        return json.loads(self.input_json)

    def to_dict(self, *, include_states=False):
        if type(include_states) is not bool:
            raise ValueError('include_states must be a boolean')
        out = dict(scope='finite-passive-scalar-rlgc-ladder-startup', input=self.inputs,
            port_names=list(self.port_names), time_s=self.time.tolist(),
            voltage_v=self.voltage.tolist(), current_into_line_a=self.current.tolist(),
            stored_energy_j=self.energy.tolist(), energy_rate_w=self.energy_rate.tolist(),
            series_loss_w=self.series_loss.tolist(), shunt_loss_w=self.shunt_loss.tolist(),
            line_power_w=self.line_power.tolist(), source_power_w=self.source_power.tolist(),
            source_resistor_loss_w=self.source_resistor_loss.tolist(),
            load_resistor_loss_w=self.load_resistor_loss.tolist(),
            power_balance_relative_error=self.power_balance_relative_error,
            states_included=include_states)
        if include_states:
            data = self.inputs
            out.update(node_positions_m=np.linspace(0., data['length_m'], data['cells']+1).tolist(),
                segment_centres_m=((np.arange(data['cells'])+.5)*data['length_m']/data['cells']).tolist(),
                node_voltage_v=self.node_voltage.tolist(), segment_current_a=self.segment_current.tolist())
        return out


def _ladder_input(time, source_voltages, *, R, L, G, C, length, cells,
                  source_resistance, load_resistance):
    time = _times('time', time)
    if not 2 <= len(time) <= 10000 or time[0] != 0:
        raise ValueError('time needs 2..10000 samples starting at zero')
    dt = np.diff(time)
    if not np.allclose(dt, dt[0], rtol=1e-10, atol=0):
        raise ValueError('time spacing must be uniform within relative 1e-10')
    drive = _real('source_voltages', source_voltages)
    if drive.shape != time.shape or drive[0] != 0:
        raise ValueError('source_voltages must match time and start at zero')
    r = _scalar('R', R, zero=True); l = _scalar('L', L)
    g = _scalar('G', G, zero=True); c = _scalar('C', C)
    length = _scalar('length', length); cells = _integer(cells, 1, 256)
    rs = _scalar('source_resistance', source_resistance, zero=True)
    rl = None if load_resistance is None else _scalar('load_resistance', load_resistance, zero=True)
    return time, drive, r, l, g, c, length, cells, rs, rl


def rlgc_ladder_response(time, source_voltages, *, R, L, G, C, length, cells,
                         source_resistance, load_resistance):
    """Propagate an explicit finite passive scalar line circuit from zero state.

    SI inputs: R[ohm/m]>=0, L[H/m]>0, G[S/m]>=0, C[F/m]>0, length[m]>0.
    Explicit cells=1..256 gives series R*dx/L*dx and shunt G*dx/C*dx, with
    half weights at the two end nodes. Time has 2..10000 uniformly spaced
    samples starting at zero; the real PWL drive has matching shape and starts
    at zero. It holds the last value afterwards. No initial capacitor impulse
    or initial stored energy is inferred. Cell/time limits are not accuracy
    or runtime guarantees; callers must check spatial/time/source convergence.

    Source/load resistances are finite >=0; zero source is ideal, zero load
    is short, and load None is open. Prescribed end voltages are removed from
    the dynamic state but retain their half-capacitor energy and leakage.
    Ideal-source current includes endpoint C*dV/dt with right PWL slope and
    final slope zero. Both port currents enter the line; segment currents +z.

    Existing SciPy lsim performs PWL state-space propagation. Finite-state,
    coefficient and relative power-balance (1e-10) guards precede acceptance.
    This solves the finite circuit, not the exact continuous distributed line.
    Constant RLGC do not represent arbitrary material dispersion, skin effect,
    coupled lines, reactive/nonlinear external loads or general TDR inference.
    """
    time, drive, r, l, g, c, length, n, rs, rl = _ladder_input(time, source_voltages,
        R=R, L=L, G=G, C=C, length=length, cells=cells,
        source_resistance=source_resistance, load_resistance=load_resistance)
    dx = length/n
    weights = np.ones(n+1); weights[[0, -1]] = .5
    with np.errstate(over='ignore', invalid='ignore', divide='ignore', under='ignore'):
        cap = c*dx*weights; leak = g*dx*weights; ind = l*dx; res = r*dx
        slope = np.r_[np.diff(drive)/np.diff(time), 0.]
    if (not np.all(np.isfinite(np.r_[cap, leak, ind, res, slope]))
            or np.any(cap <= 0) or ind <= 0):
        raise ValueError('cell parameters or source slopes exceed finite scales')
    a = np.zeros((2*n+1, 2*n+1)); b = np.zeros(2*n+1)
    with np.errstate(over='ignore', invalid='ignore', divide='ignore', under='ignore'):
        a[np.arange(n+1), np.arange(n+1)] = -leak/cap
        if rs > 0:
            a[0, 0] -= 1/(rs*cap[0]); b[0] = 1/(rs*cap[0])
        if rl is not None and rl > 0:
            a[n, n] -= 1/(rl*cap[n])
        for i in range(n):
            a[i, n+1+i] = -1/cap[i]; a[i+1, n+1+i] = 1/cap[i+1]
            a[n+1+i, i] = 1/ind; a[n+1+i, i+1] = -1/ind
            a[n+1+i, n+1+i] = -res/ind
    if not np.all(np.isfinite(a)) or not np.all(np.isfinite(b)):
        raise ValueError('circuit coefficients exceed finite scales')
    fixed = ([0] if rs == 0 else [])+([n] if rl == 0 else [])
    keep = np.array([i for i in range(2*n+1) if i not in fixed])
    reduced = a[np.ix_(keep, keep)]; input_vector = b[keep]
    if rs == 0:
        input_vector = input_vector+a[keep, 0]
    _, _, state = lsim((reduced, input_vector[:, None], np.zeros((1, len(keep))),
                        np.zeros((1, 1))), drive, time, interp=True)
    state = np.asarray(state)
    if state.ndim == 1:  # The one-cell ideal-source/short case has one state.
        state = state[:, None]
    if state.shape != (len(time), len(keep)) or not np.all(np.isfinite(state)):
        raise ValueError('state propagation returned invalid shape or nonfinite values')
    with np.errstate(over='ignore', invalid='ignore', divide='ignore', under='ignore'):
        full = np.zeros((len(time), 2*n+1)); full[:, keep] = state
        rhs = np.zeros_like(full); rhs[:, keep] = state@reduced.T+drive[:, None]*input_vector
        if rs == 0:
            full[:, 0] = drive; rhs[:, 0] = slope
        v = full[:, :n+1]; i = full[:, n+1:]; voltage = v[:, [0, n]]
        source_current = ((drive-v[:, 0])/rs if rs > 0 else
                          i[:, 0]+leak[0]*drive+cap[0]*slope)
        load_current = (np.zeros_like(time) if rl is None else
                        -i[:, -1] if rl == 0 else -v[:, -1]/rl)
        current = np.column_stack((source_current, load_current))
        energy = .5*np.sum(cap*v*v, axis=1)+.5*ind*np.sum(i*i, axis=1)
        rate = np.sum(cap*v*rhs[:, :n+1], axis=1)+ind*np.sum(i*rhs[:, n+1:], axis=1)
        series = res*np.sum(i*i, axis=1); shunt = np.sum(leak*v*v, axis=1)
        line_power = np.sum(voltage*current, axis=1)
        source_power = drive*source_current; source_loss = rs*source_current**2
        load_loss = np.zeros_like(time) if rl is None else rl*load_current**2
        residual = rate-line_power+series+shunt
    if not np.all(np.isfinite(np.r_[rate, line_power, series, shunt, residual])):
        raise ValueError('energy diagnostics exceed finite scales')
    scale = max(np.max(abs(rate)), np.max(abs(line_power)), np.max(abs(series+shunt)))
    error = float(np.max(abs(residual))/scale) if scale > 0 else 0.
    if not np.isfinite(error) or error > 1e-10:
        raise ValueError('finite circuit power balance exceeds relative 1e-10')
    data = dict(time_s=time.tolist(), source_voltages_v=drive.tolist(), R_ohm_per_m=r,
        L_h_per_m=l, G_s_per_m=g, C_f_per_m=c, length_m=length, cells=n,
        source_resistance_ohm=rs, load_resistance_ohm=rl)
    text = json.dumps(data, sort_keys=True, allow_nan=False)
    return RLGCLadderResponse(text, time, drive, v, i, voltage, current, energy, rate,
        series, shunt, line_power, source_power, source_loss, load_loss, error)
