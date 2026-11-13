# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit current-driven multiconductor PSD Debye circuit with external C and series RL loads."""
from dataclasses import dataclass
import numpy as np
from scipy.signal import lsim
from .network import _real
from .sampling import _integer
from .multiconductor_debye_reactive_startup import _multiconductor_debye_reactive_input
from .coupled_debye_startup import _propagate_coupled_debye
from .psd_multiconductor_debye_startup import PSDMulticonductorDebyeRLGCLadderResponse

__all__ = ['NortonMulticonductorDebyeReactiveLadderResponse', 'psd_multiconductor_debye_norton_reactive_ladder_response']


@dataclass(frozen=True)
class NortonMulticonductorDebyeReactiveLadderResponse:
    """Separate internal polarization, external capacitor and series RL branch.

    line_energy/rate is internal instantaneous+polarization storage;
    total_energy/rate additionally includes external C and branch L. Branch
    current leaves the far line toward the load. load_resistor_loss refers to
    the parallel resistance; load_branch_resistor_loss is separate.
    source_currents are injected amperes; source_shunt_resistor_loss is the
    near parallel conductance loss, not a Thevenin series resistor loss.
    This independent response does not implicitly enter existing wave APIs.
    """
    input_json: str
    time: np.ndarray
    source_currents: np.ndarray
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
    source_shunt_resistor_loss: np.ndarray
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
            source_power_w=self.source_power.tolist(), source_shunt_resistor_loss_w=self.source_shunt_resistor_loss.tolist(),
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
        out.update(scope='finite-passive-multiconductor-psd-debye-norton-reactive-startup',
            line_energy_j=self.line_energy.tolist(), line_energy_rate_w=self.line_energy_rate.tolist(),
            load_capacitor_current_a=self.load_capacitor_current.tolist(),
            load_capacitor_energy_j=self.load_capacitor_energy.tolist(),
            load_capacitor_power_w=self.load_capacitor_power.tolist(),
            load_branch_current_a=self.load_branch_current.tolist(),
            load_branch_energy_j=self.load_branch_energy.tolist(),
            load_branch_energy_rate_w=self.load_branch_energy_rate.tolist(),
            load_branch_resistor_loss_w=self.load_branch_resistor_loss.tolist())
        return out



def _multiconductor_debye_norton_input(time, source_currents, *, signals, R, L, G, C_inf,
        delta_C, relaxation_hz, length, cells, source_shunt_conductance,
        load_resistance, load_capacitance, load_branch_resistance, load_branch_inductance):
    signals = _integer(signals, 3, 4)
    gs = _real('source_shunt_conductance', source_shunt_conductance)
    if gs.shape != (signals,) or np.any(gs < 0):
        raise ValueError('source_shunt_conductance needs signals finite nonnegative real values')
    # The positive placeholder only reuses existing time/line/load validation.
    # The shared current-source path uses gs directly and never propagates rs.
    data, cap, rb, lb, signals = _multiconductor_debye_reactive_input(time, source_currents,
        signals=signals, R=R, L=L, G=G, C_inf=C_inf, delta_C=delta_C,
        relaxation_hz=relaxation_hz, length=length, cells=cells,
        source_resistance=np.ones(signals), load_resistance=load_resistance,
        load_capacitance=load_capacitance, load_branch_resistance=load_branch_resistance,
        load_branch_inductance=load_branch_inductance)
    return data, cap, rb, lb, signals, gs


def psd_multiconductor_debye_norton_reactive_ladder_response(time, source_currents, *, signals,
        R, L, G, C_inf, delta_C, relaxation_hz, length, cells,
        source_shunt_conductance, load_resistance, load_capacitance,
        load_branch_resistance, load_branch_inductance):
    """Zero-state three/four-signal PSD Debye line with explicit injected currents.

    source_currents[A] has shape(time,signals), first row zero; uniform2..10000
    times start0. source_shunt_conductance[S] is a signals-vector of finite
    nonnegative real values, zero meaning an ideal current source. No scalar
    broadcast, near short/Dirichlet or inferred Thevenin drive is accepted.
    Near terminal current=Iinj-Gs*Vnear, source power=Iinj dot Vnear and
    source shunt resistor loss=sum(Gs*Vnear**2). Positive Gs has the same line
    response as explicit Vs=Iinj/Gs, Rs=1/Gs, with different source partitions.

    Original PSD Debye line/external C and RL contracts remain: signals3/4,
    cells1..64,1..2PSD strengths,positive poleHz,PSD R/G/Cload/Rbranch and
    SPD L/Cinf/Lbranch with ratio>1e-12,positive load resistances. Exact real
    symmetry and conservative computed PSD eigensign rejection; no clipping.
    Units are ohm/m,H/m,S/m,F/m,Hz,m and externalF,ohm,H. Branch current
    starts0 and leaves the far line. Line storage is internal instantaneous+
    polarization; total adds externalC/L. Both relative1e-10 balances and
    finite nonnegative storage/loss checks remain. No source voltage or
    series-resistor-loss alias is supplied for injected currents/shunt losses.

    Counts bound resources,not accuracy/runtime. No arbitrary transient
    accuracy,horizon inference,mixed sources,ideal shorts,general dispersion,
    field extraction,saved/wave admission or measured accuracy is inferred.
    """
    data, cap, rb, lb, signals, gs = _multiconductor_debye_norton_input(time, source_currents,
        signals=signals, R=R, L=L, G=G, C_inf=C_inf, delta_C=delta_C,
        relaxation_hz=relaxation_hz, length=length, cells=cells,
        source_shunt_conductance=source_shunt_conductance, load_resistance=load_resistance,
        load_capacitance=load_capacitance, load_branch_resistance=load_branch_resistance,
        load_branch_inductance=load_branch_inductance)
    return _propagate_coupled_debye(data, psd_strength=True,
        result_type=NortonMulticonductorDebyeReactiveLadderResponse, propagator=lsim,
        load_capacitance=cap, load_branch=(rb, lb), signals=signals, source_conductance=gs,
        scale_states=True)
