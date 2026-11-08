# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit PSD Debye circuit with a separate passive external capacitive load."""
from dataclasses import dataclass
import numpy as np
from scipy.signal import lsim
from .psd_multiconductor_debye_startup import _psd_multiconductor_matrix
from .coupled_debye_startup import _propagate_coupled_debye
from .psd_multiconductor_debye_startup import PSDMulticonductorDebyeRLGCLadderResponse, _psd_multiconductor_debye_input

__all__ = ['MulticonductorDebyeCapacitiveLadderResponse', 'psd_multiconductor_debye_capacitive_ladder_response']


@dataclass(frozen=True)
class MulticonductorDebyeCapacitiveLadderResponse:
    """Separate line polarization and external load storage/current.

    line_energy/rate includes instantaneous and polarization storage only;
    total_energy/rate also includes the external capacitor. Six/eight currents enter
    the line; far-port current includes both resistor and capacitor flow.
    This independent class does not implicitly enter existing wave/saved APIs.
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

    __post_init__ = PSDMulticonductorDebyeRLGCLadderResponse.__post_init__
    inputs = PSDMulticonductorDebyeRLGCLadderResponse.inputs
    line_energy = PSDMulticonductorDebyeRLGCLadderResponse.total_energy
    line_energy_rate = PSDMulticonductorDebyeRLGCLadderResponse.total_energy_rate
    port_names = PSDMulticonductorDebyeRLGCLadderResponse.port_names

    @property
    def total_energy(self):
        with np.errstate(over='ignore', invalid='ignore'):
            value = self.line_energy+self.load_capacitor_energy
        value.setflags(write=False)
        return value

    @property
    def total_energy_rate(self):
        with np.errstate(over='ignore', invalid='ignore'):
            value = self.line_energy_rate+self.load_capacitor_power
        value.setflags(write=False)
        return value

    def to_dict(self, *, include_states=False):
        out = PSDMulticonductorDebyeRLGCLadderResponse.to_dict(self, include_states=include_states)
        out.update(scope='finite-passive-multiconductor-psd-debye-capacitive-startup',
            line_energy_j=self.line_energy.tolist(), line_energy_rate_w=self.line_energy_rate.tolist(),
            load_capacitor_current_a=self.load_capacitor_current.tolist(),
            load_capacitor_energy_j=self.load_capacitor_energy.tolist(),
            load_capacitor_power_w=self.load_capacitor_power.tolist())
        return out


def _multiconductor_debye_capacitive_input(time, source_voltages, *, signals, R, L, G, C_inf, delta_C,
        relaxation_hz, length, cells, source_resistance, load_resistance, load_capacitance):
    data, signals = _psd_multiconductor_debye_input(time, source_voltages, signals=signals, R=R, L=L, G=G, C_inf=C_inf,
        delta_C=delta_C, relaxation_hz=relaxation_hz, length=length, cells=cells,
        source_resistance=source_resistance, load_resistance=load_resistance)
    cap = _psd_multiconductor_matrix('load_capacitance', load_capacitance, signals)
    return data, cap, signals


def psd_multiconductor_debye_capacitive_ladder_response(time, source_voltages, *, signals, R, L, G,
        C_inf, delta_C, relaxation_hz, length, cells, source_resistance,
        load_resistance, load_capacitance):
    """Zero-state three/four-signal PSD Debye line with an explicit parallel load capacitor.

    Cload[F] is real exactly symmetric signals-by-signals PSD, including zero/rank-one matrices;
    negative eigenvalues are rejected without repair. Original PSD Debye matrix,
    pole and PWL contracts hold: R/G PSD,L/Cinf SPD,1..2 PSD strengths/positiveHz,
    1..64cells,uniform2..10000times starting0,zero-first voltage(times,signals).
    Source/load resistances each remain signals finite positive ohm values.

    Add Cload to the far-node mass; I_into_far=-Vfar/Rload-Cload*dVfar/dt.
    Resistor loss is Vfar**2/Rload, not Rload*total_terminal_current**2.
    External .5*Vfar.T*Cload*Vfar storage is separate from internal instantaneous
    and polarization energy. Both line and full source power balances require
    relative1e-10, with finite nonnegative storage/loss and no clipping.
    Zero external capacitance recovers the original PSD circuit. Zero strengths
    remove polarization while retaining the declared external capacitor.

    Explicit signals3..4 retain the original PWL and matrix contracts.
    A negative computed PSD eigenvalue is rejected without repair even near
    numerical sign ambiguity. Counts bound resources, not accuracy/runtime. No automatic
    horizon,ideal/open/short/current source,inductive branch,field extraction,
    saved/wave integration or measured-board accuracy is inferred.
    """
    data, cap, signals = _multiconductor_debye_capacitive_input(time, source_voltages, signals=signals, R=R, L=L, G=G,
        C_inf=C_inf, delta_C=delta_C, relaxation_hz=relaxation_hz, length=length,
        cells=cells, source_resistance=source_resistance, load_resistance=load_resistance,
        load_capacitance=load_capacitance)
    return _propagate_coupled_debye(data, psd_strength=True,
        result_type=MulticonductorDebyeCapacitiveLadderResponse, propagator=lsim, load_capacitance=cap, signals=signals)
