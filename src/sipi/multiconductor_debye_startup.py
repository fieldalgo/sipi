# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit three/four-signal positive-strength Debye finite circuits."""
from dataclasses import dataclass
import numpy as np
from scipy.signal import lsim
from .network import _real
from .multiconductor_startup import _multiconductor_input, _multiconductor_matrix
from .debye_startup import DebyeRLGCLadderResponse
from .coupled_debye_startup import _propagate_coupled_debye

__all__ = ['MulticonductorDebyeRLGCLadderResponse', 'multiconductor_debye_rlgc_ladder_response']


@dataclass(frozen=True)
class MulticonductorDebyeRLGCLadderResponse:
    """Six/eight terminals; polarization arrays (time,node,pole,conductor).

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
        return tuple(f'{end}_{j}' for end in ('near', 'far') for j in range(self.inputs['signals']))

    def to_dict(self, *, include_states=False):
        out = DebyeRLGCLadderResponse.to_dict(self, include_states=include_states)
        out['scope'] = 'finite-passive-multiconductor-debye-ladder-startup'
        return out


def _multiconductor_debye_input(time, source_voltages, *, signals, R, L, G,
        C_inf, delta_C, relaxation_hz, length, cells, source_resistance, load_resistance):
    data = _multiconductor_input(time, source_voltages, signals=signals,
        R=R, L=L, G=G, C=C_inf, length=length, cells=cells,
        source_resistance=source_resistance, load_resistance=load_resistance)
    time, drive, signals, r, l, g, c, length, n, rs, rl = data
    if n > 64:
        raise ValueError('multiconductor Debye cells must be in 1..64')
    delta = _real('delta_C', delta_C); poles = _real('relaxation_hz', relaxation_hz)
    if (delta.ndim != 3 or delta.shape[1:] != (signals, signals) or not 1 <= len(delta) <= 2
            or poles.shape != (len(delta),) or np.any(poles <= 0)):
        raise ValueError('delta_C needs 1..2 real signals-by-signals matrices and matching positive relaxation_hz')
    for index, matrix in enumerate(delta):
        if np.any(matrix):
            try:
                _multiconductor_matrix('C', matrix, signals)
            except ValueError as exc:
                raise ValueError(f'delta_C[{index}] needs exact symmetry and SPD eigenvalue ratio above 1e-12, or exact zero') from exc
    return (time, drive, r, l, g, c, length, n, rs, rl, delta, poles), signals


def multiconductor_debye_rlgc_ladder_response(time, source_voltages, *, signals,
        R, L, G, C_inf, delta_C, relaxation_hz, length, cells,
        source_resistance, load_resistance):
    """Propagate a zero-state three/four-signal positive-strength Debye circuit.

    Constant real exactly symmetric R/G are SPD or exactly zero; L/C_inf are
    SPD. Each of1..2 DeltaC matrices is SPD or exactly zero. Every nonzero
    matrix needs eigenvalue ratio >1e-12. Capacitance is C_inf plus
    sum(DeltaC/(1+j*f/relaxation_hz)); positive poles in Hz. SI R/L/G/C units
    are ohm/m,H/m,S/m,F/m. Source/load require signals positive finite ohms.

    Explicit signals3..4,cells1..64,uniform time2..10000 starting0 and
    drive(times,signals) first row0 bound the zero-state PWL circuit. Half
    end shunts and canonical tau*w'=V-w preserve declared pole order; exact
    zero strengths omit states and retain zero output columns. Polarization
    arrays are(time,node,pole,signal) with lumped charge/current in C/A.
    Line/source power balance each retain relative1e-10 acceptance.

    No singular PSD strengths/R/G, ideal/open/short/reactive/current ends,
    field extraction, general dispersive fit, wave/saved adaptation, platform
    or measurement accuracy is inferred. Resource bounds are not accuracy
    guarantees: check source/time/space convergence for each use.
    """
    data, signals = _multiconductor_debye_input(time, source_voltages,
        signals=signals, R=R, L=L, G=G, C_inf=C_inf, delta_C=delta_C,
        relaxation_hz=relaxation_hz, length=length, cells=cells,
        source_resistance=source_resistance, load_resistance=load_resistance)
    return _propagate_coupled_debye(data, psd_strength=False,
        result_type=MulticonductorDebyeRLGCLadderResponse, propagator=lsim,
        signals=signals)
