# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit two-signal Debye startup with possibly singular PSD strengths."""
from dataclasses import dataclass
import numpy as np
from scipy.signal import lsim
from .network import _real
from .coupled_startup import _coupled_input, _passive_matrix
from .coupled_debye_startup import CoupledDebyeRLGCLadderResponse, _propagate_coupled_debye

__all__ = ['PSDCoupledDebyeRLGCLadderResponse', 'psd_coupled_debye_rlgc_ladder_response']


@dataclass(frozen=True)
class PSDCoupledDebyeRLGCLadderResponse:
    """Four-terminal response with canonical auxiliary voltages for PSD strengths.

    Null-direction auxiliary voltage is a zero-state low-pass realization, not
    a measured polarization coordinate. Charge/current are lumped DeltaC*w
    and its time derivative, including half shunts at both ends. This separate
    class does not implicitly enter existing wave or saved adapters.
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

    __post_init__ = CoupledDebyeRLGCLadderResponse.__post_init__
    inputs = CoupledDebyeRLGCLadderResponse.inputs
    total_energy = CoupledDebyeRLGCLadderResponse.total_energy
    total_energy_rate = CoupledDebyeRLGCLadderResponse.total_energy_rate
    port_names = CoupledDebyeRLGCLadderResponse.port_names

    def to_dict(self, *, include_states=False):
        out = CoupledDebyeRLGCLadderResponse.to_dict(self, include_states=include_states)
        out['scope'] = 'finite-passive-two-signal-psd-debye-ladder-startup'
        return out


def _psd_debye_input(time, source_voltages, *, R, L, G, C_inf, delta_C,
                     relaxation_hz, length, cells, source_resistance, load_resistance):
    data = _coupled_input(time, source_voltages, R=R, L=L, G=G, C=C_inf,
        length=length, cells=cells, source_resistance=source_resistance,
        load_resistance=load_resistance)
    delta = _real('delta_C', delta_C); poles = _real('relaxation_hz', relaxation_hz)
    if (delta.ndim != 3 or delta.shape[1:] != (2, 2) or not 1 <= len(delta) <= 2
            or poles.shape != (len(delta),) or np.any(poles <= 0)):
        raise ValueError('delta_C needs 1..2 real 2x2 matrices and matching positive relaxation_hz')
    for matrix in delta:
        _passive_matrix('delta_C', matrix)
    return (*data, delta, poles)


def psd_coupled_debye_rlgc_ladder_response(time, source_voltages, *, R, L, G,
        C_inf, delta_C, relaxation_hz, length, cells, source_resistance, load_resistance):
    """Propagate zero-state two-signal Debye circuits with explicit PSD strengths.

    Exactly symmetric real2x2 R/G and each of1..2 DeltaC matrices are PSD;
    L/C_inf are SPD with normalized eigenvalue ratio above1e-12. No symmetry
    repair, negative eigenvalue clipping, rank threshold or inferred material.
    Units: ohm/m,H/m,S/m,F/m,Hz,m. Two source/load resistances must be finite
    positive ohms; no ideal/open/short/reactive/current-source boundary.

    Cells1..128, uniform times2..10000 starting0, drive(times,2) first row0.
    SciPy lsim propagates the PWL interpolant. Every nonzero pole uses the
    canonical vector tau*w'=V-w without inverting DeltaC. Unobservable null
    components of w carry no charge or stored/lost energy; exactly zero
    strengths omit states and preserve zero output columns and declared order.
    Polarization arrays are(time,node,pole,conductor), with node-lumped C/A.

    Finite/nonnegative storage/loss and both line/source relative1e-10 power
    guards apply. Counts are resource bounds, not accuracy/runtime guarantees.
    Existing strict-SPD API and its saved contracts retain their restrictions.
    This API does not imply extraction, arbitrary fitting, general dispersive
    boundaries, wave/saved integration, or measured-board accuracy.
    """
    data = _psd_debye_input(time, source_voltages, R=R, L=L, G=G, C_inf=C_inf,
        delta_C=delta_C, relaxation_hz=relaxation_hz, length=length, cells=cells,
        source_resistance=source_resistance, load_resistance=load_resistance)
    return _propagate_coupled_debye(data, psd_strength=True,
        result_type=PSDCoupledDebyeRLGCLadderResponse, propagator=lsim)
