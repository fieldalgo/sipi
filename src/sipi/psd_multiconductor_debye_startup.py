# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit three/four-signal Debye circuits with singular PSD strengths."""
from dataclasses import dataclass
import numpy as np
from scipy.signal import lsim
from .network import _real
from .sampling import _integer
from .multiconductor_startup import _multiconductor_input
from .debye_startup import DebyeRLGCLadderResponse
from .coupled_debye_startup import _propagate_coupled_debye

__all__ = ['PSDMulticonductorDebyeRLGCLadderResponse', 'psd_multiconductor_debye_rlgc_ladder_response']


@dataclass(frozen=True)
class PSDMulticonductorDebyeRLGCLadderResponse:
    """Six/eight terminals; polarization arrays (time,node,pole,conductor).

    Null-direction auxiliary voltage is a canonical low-pass state, not a
    measured polarization coordinate. Charges/currents include lumped node
    capacitance and half-end weights.
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
        out['scope'] = 'finite-passive-psd-multiconductor-debye-ladder-startup'
        return out


def _psd_multiconductor_matrix(name, value, signals):
    matrix = _real(name, value)
    if matrix.shape != (signals, signals) or not np.array_equal(matrix, matrix.T):
        raise ValueError(f'{name} must be an exactly symmetric real signals-by-signals matrix')
    scale = np.max(abs(matrix))
    eigen = np.linalg.eigvalsh(matrix/scale) if scale else np.zeros(signals)
    if eigen[0] < 0:
        raise ValueError(f'{name} must be positive semidefinite; negative eigenvalues are not repaired')
    return matrix


def _psd_multiconductor_debye_input(time, source_voltages, *, signals, R, L, G,
        C_inf, delta_C, relaxation_hz, length, cells, source_resistance, load_resistance):
    signals = _integer(signals, 3, 4)
    r = _psd_multiconductor_matrix('R', R, signals)
    g = _psd_multiconductor_matrix('G', G, signals)
    # Reuse unchanged time, SPD storage and boundary validation with zero loss
    # placeholders; insert the validated PSD losses before any propagation.
    zero = np.zeros((signals, signals))
    data = _multiconductor_input(time, source_voltages, signals=signals,
        R=zero, L=L, G=zero, C=C_inf, length=length, cells=cells,
        source_resistance=source_resistance, load_resistance=load_resistance)
    time, drive, signals, _, l, _, c, length, n, rs, rl = data
    if n > 64:
        raise ValueError('PSD multiconductor Debye cells must be in 1..64')
    delta = _real('delta_C', delta_C); poles = _real('relaxation_hz', relaxation_hz)
    if (delta.ndim != 3 or delta.shape[1:] != (signals, signals) or not 1 <= len(delta) <= 2
            or poles.shape != (len(delta),) or np.any(poles <= 0)):
        raise ValueError('delta_C needs 1..2 real signals-by-signals matrices and matching positive relaxation_hz')
    for index, matrix in enumerate(delta):
        _psd_multiconductor_matrix(f'delta_C[{index}]', matrix, signals)
    return (time, drive, r, l, g, c, length, n, rs, rl, delta, poles), signals


def psd_multiconductor_debye_rlgc_ladder_response(time, source_voltages, *, signals,
        R, L, G, C_inf, delta_C, relaxation_hz, length, cells,
        source_resistance, load_resistance):
    """Propagate a separate zero-state three/four-signal PSD Debye circuit.

    Exactly symmetric real R/G and each of1..2 DeltaC matrices are PSD;
    L/C_inf are SPD with eigenvalue ratio above1e-12. Negative normalized
    eigenvalues are rejected without clipping, symmetry repair or a rank
    threshold. Floating-point eigensign ambiguity can reject a mathematical
    PSD matrix conservatively. Positive poles are in Hz; R/L/G/C units are
    ohm/m,H/m,S/m,F/m. Source/load each require signals positive finite ohms.

    Signals3..4,cells1..64,uniform time2..10000 starting0, and first-row-zero
    drive(times,signals) bound the zero-state PWL circuit. Half-end shunts and
    canonical tau*w'=V-w require no DeltaC inverse. Null auxiliary voltages
    carry no charge or stored/lost energy. Exact zero strengths omit states
    but retain zero output columns and declared order. Polarization arrays
    are(time,node,pole,signal); charge/current are node-lumped C/A.
    Both line/source power balance retain relative1e-10 acceptance.

    Existing strict-strength models retain their restrictions. No ideal,
    open/short/reactive/current ends, field extraction, arbitrary material
    fit, wave/saved admission or measured accuracy is inferred. Counts are
    resource bounds, not accuracy guarantees; check time/source/space limits.
    """
    data, signals = _psd_multiconductor_debye_input(time, source_voltages,
        signals=signals, R=R, L=L, G=G, C_inf=C_inf, delta_C=delta_C,
        relaxation_hz=relaxation_hz, length=length, cells=cells,
        source_resistance=source_resistance, load_resistance=load_resistance)
    return _propagate_coupled_debye(data, psd_strength=True,
        result_type=PSDMulticonductorDebyeRLGCLadderResponse, propagator=lsim,
        signals=signals)
