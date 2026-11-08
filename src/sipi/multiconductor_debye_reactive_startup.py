# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit PSD Debye circuit with separate passive external C and series RL loads."""
from dataclasses import dataclass
import numpy as np
from scipy.signal import lsim
from .multiconductor_startup import _multiconductor_matrix
from .psd_multiconductor_debye_startup import _psd_multiconductor_matrix
from .multiconductor_debye_capacitive_startup import _multiconductor_debye_capacitive_input
from .coupled_debye_startup import _propagate_coupled_debye
from .psd_multiconductor_debye_startup import PSDMulticonductorDebyeRLGCLadderResponse

__all__ = ['MulticonductorDebyeReactiveLadderResponse', 'psd_multiconductor_debye_reactive_ladder_response']


@dataclass(frozen=True)
class MulticonductorDebyeReactiveLadderResponse:
    """Separate internal polarization, external capacitor and series RL branch.

    line_energy/rate is internal instantaneous+polarization storage;
    total_energy/rate additionally includes external C and branch L. Branch
    current leaves the far line toward the load. load_resistor_loss refers to
    the parallel resistance; load_branch_resistor_loss is separate.
    This independent response does not implicitly enter existing wave APIs.
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

    load_capacitor_current: np.ndarray
    load_capacitor_energy: np.ndarray
    load_capacitor_power: np.ndarray
    load_branch_current: np.ndarray
    load_branch_energy: np.ndarray
    load_branch_energy_rate: np.ndarray
    load_branch_resistor_loss: np.ndarray

    __post_init__ = PSDMulticonductorDebyeRLGCLadderResponse.__post_init__
    inputs = PSDMulticonductorDebyeRLGCLadderResponse.inputs
    line_energy = PSDMulticonductorDebyeRLGCLadderResponse.total_energy
    line_energy_rate = PSDMulticonductorDebyeRLGCLadderResponse.total_energy_rate
    port_names = PSDMulticonductorDebyeRLGCLadderResponse.port_names

    @property
    def total_energy(self):
        with np.errstate(over='ignore', invalid='ignore'):
            value = self.line_energy+self.load_capacitor_energy+self.load_branch_energy
        value.setflags(write=False)
        return value

    @property
    def total_energy_rate(self):
        with np.errstate(over='ignore', invalid='ignore'):
            value = self.line_energy_rate+self.load_capacitor_power+self.load_branch_energy_rate
        value.setflags(write=False)
        return value

    def to_dict(self, *, include_states=False):
        out = PSDMulticonductorDebyeRLGCLadderResponse.to_dict(self, include_states=include_states)
        out.update(scope='finite-passive-multiconductor-psd-debye-reactive-startup',
            line_energy_j=self.line_energy.tolist(), line_energy_rate_w=self.line_energy_rate.tolist(),
            load_capacitor_current_a=self.load_capacitor_current.tolist(),
            load_capacitor_energy_j=self.load_capacitor_energy.tolist(),
            load_capacitor_power_w=self.load_capacitor_power.tolist(),
            load_branch_current_a=self.load_branch_current.tolist(),
            load_branch_energy_j=self.load_branch_energy.tolist(),
            load_branch_energy_rate_w=self.load_branch_energy_rate.tolist(),
            load_branch_resistor_loss_w=self.load_branch_resistor_loss.tolist())
        return out


def _multiconductor_debye_reactive_input(time, source_voltages, *, signals, R, L, G, C_inf, delta_C,
        relaxation_hz, length, cells, source_resistance, load_resistance, load_capacitance, load_branch_resistance, load_branch_inductance):
    data, cap, signals = _multiconductor_debye_capacitive_input(time, source_voltages,
        signals=signals, R=R, L=L, G=G, C_inf=C_inf,
        delta_C=delta_C, relaxation_hz=relaxation_hz, length=length, cells=cells,
        source_resistance=source_resistance, load_resistance=load_resistance,
        load_capacitance=load_capacitance)
    rb = _psd_multiconductor_matrix('load_branch_resistance', load_branch_resistance, signals)
    lb = _multiconductor_matrix('load_branch_inductance', load_branch_inductance, signals)
    return data, cap, rb, lb, signals


def psd_multiconductor_debye_reactive_ladder_response(time, source_voltages, *, signals, R, L, G,
        C_inf, delta_C, relaxation_hz, length, cells, source_resistance,
        load_resistance, load_capacitance, load_branch_resistance, load_branch_inductance):
    """Zero-state three/four-signal PSD Debye line with explicit parallel C and series RL load.

    All external matrices are exactly symmetric real signals-by-signals. Cload[F] and
    Rbranch[ohm] are PSD, including zero/rank-one; Lbranch[H] is SPD with
    eigenvalue ratio above1e-12. No inferred branch or eigenvalue repair.
    Original line contracts hold: R/G PSD,L/Cinf SPD,1..2 PSD strengths and
    positive poleHz,1..64cells,uniform2..10000times starting0,zero-first
    voltage(times,signals),signals3/4 and signals finite positive source/load resistances.

    Lbranch*di/dt=Vfar-Rbranch*i with zero initial current. Far into-line
    current is -Vfar/Rload-Cload*dVfar/dt-i. Parallel resistor loss is Vfar**2/Rload;
    branch resistor loss i.T*Rbranch*i is separate. Internal instantaneous and
    polarization storage, external C energy and branch L energy are distinct.
    Line and full source balances require relative1e-10, finite nonnegative
    storage/loss and no clipping. Zero strengths recover the constant reactive
    circuit equations; large explicit branch inductance approaches the capacitive case.
    Negative computed PSD eigenvalues are rejected conservatively, including
    near-singular sign ambiguity; no rank threshold or eigenvalue repair.

    Counts bound resources,not accuracy/runtime. No automatic horizon,
    ideal/open/short/current source,arbitrary RLC network,field extraction,
    saved/wave integration or measured accuracy is inferred.
    """
    data, cap, rb, lb, signals = _multiconductor_debye_reactive_input(time, source_voltages, signals=signals, R=R, L=L, G=G,
        C_inf=C_inf, delta_C=delta_C, relaxation_hz=relaxation_hz, length=length,
        cells=cells, source_resistance=source_resistance, load_resistance=load_resistance,
        load_capacitance=load_capacitance,
        load_branch_resistance=load_branch_resistance, load_branch_inductance=load_branch_inductance)
    return _propagate_coupled_debye(data, psd_strength=True,
        result_type=MulticonductorDebyeReactiveLadderResponse, propagator=lsim, load_capacitance=cap, load_branch=(rb, lb), signals=signals)
