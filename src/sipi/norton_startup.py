# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Current-driven two-signal startup with passive external C and RL loads."""
from dataclasses import dataclass
import json

import numpy as np

from .coupled_boundary_startup import _coupled_boundary_response
from .coupled_reactive_startup import _branch_input

__all__ = ['NortonReactiveRLGCLadderResponse', 'coupled_norton_reactive_ladder_response']


@dataclass(frozen=True)
class NortonReactiveRLGCLadderResponse:
    """Current-source drives and shunt losses, separate from voltage-source data.

    Port currents enter the line; source_currents are injected Norton currents.
    The difference flows through the near shunt resistor/short. Load branch
    current leaves the line. All energy/loss terms include both conductors.
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
    power_balance_relative_error: float
    load_capacitor_current: np.ndarray
    load_capacitor_energy: np.ndarray
    load_capacitor_power: np.ndarray
    total_power_balance_relative_error: float
    load_branch_current: np.ndarray
    load_branch_energy: np.ndarray
    load_branch_energy_rate: np.ndarray
    load_branch_resistor_loss: np.ndarray

    def __post_init__(self):
        for name in ('time', 'source_currents', 'node_voltage', 'segment_current',
                     'voltage', 'current', 'energy', 'energy_rate', 'series_loss',
                     'shunt_loss', 'line_power', 'source_power', 'source_shunt_resistor_loss',
                     'load_resistor_loss', 'load_capacitor_current', 'load_capacitor_energy',
                     'load_capacitor_power', 'load_branch_current', 'load_branch_energy',
                     'load_branch_energy_rate', 'load_branch_resistor_loss'):
            value = np.array(getattr(self, name), dtype=float, copy=True)
            if not np.all(np.isfinite(value)):
                raise ValueError('Norton startup output must remain finite')
            value.setflags(write=False)
            object.__setattr__(self, name, value)
        if not all(np.all(np.isfinite(a)) for a in (self.total_energy, self.total_energy_rate)):
            raise ValueError('combined Norton startup energy must remain finite')

    @property
    def port_names(self):
        return ('near_0', 'near_1', 'far_0', 'far_1')

    @property
    def inputs(self):
        return json.loads(self.input_json)

    @property
    def total_energy(self):
        with np.errstate(over='ignore', invalid='ignore'):
            value = self.energy+self.load_capacitor_energy+self.load_branch_energy
        value.setflags(write=False)
        return value

    @property
    def total_energy_rate(self):
        with np.errstate(over='ignore', invalid='ignore'):
            value = self.energy_rate+self.load_capacitor_power+self.load_branch_energy_rate
        value.setflags(write=False)
        return value

    def to_dict(self, *, include_states=False):
        if type(include_states) is not bool:
            raise ValueError('include_states must be a boolean')
        out = dict(scope='finite-passive-two-signal-norton-reactive-startup', input=self.inputs,
            port_names=list(self.port_names), time_s=self.time.tolist(),
            voltage_v=self.voltage.tolist(), current_into_line_a=self.current.tolist(),
            stored_energy_j=self.energy.tolist(), energy_rate_w=self.energy_rate.tolist(),
            series_loss_w=self.series_loss.tolist(), shunt_loss_w=self.shunt_loss.tolist(),
            line_power_w=self.line_power.tolist(), source_power_w=self.source_power.tolist(),
            source_shunt_resistor_loss_w=self.source_shunt_resistor_loss.tolist(),
            load_resistor_loss_w=self.load_resistor_loss.tolist(),
            power_balance_relative_error=self.power_balance_relative_error,
            load_capacitor_current_a=self.load_capacitor_current.tolist(),
            load_capacitor_energy_j=self.load_capacitor_energy.tolist(),
            load_capacitor_power_w=self.load_capacitor_power.tolist(),
            load_branch_current_a=self.load_branch_current.tolist(),
            load_branch_energy_j=self.load_branch_energy.tolist(),
            load_branch_energy_rate_w=self.load_branch_energy_rate.tolist(),
            load_branch_resistor_loss_w=self.load_branch_resistor_loss.tolist(),
            total_stored_energy_j=self.total_energy.tolist(),
            total_energy_rate_w=self.total_energy_rate.tolist(),
            total_power_balance_relative_error=self.total_power_balance_relative_error,
            states_included=include_states)
        if include_states:
            data = self.inputs
            out.update(node_positions_m=np.linspace(0., data['length_m'], data['cells']+1).tolist(),
                segment_centres_m=((np.arange(data['cells'])+.5)*data['length_m']/data['cells']).tolist(),
                node_voltage_v=self.node_voltage.tolist(), segment_current_a=self.segment_current.tolist())
        return out


def coupled_norton_reactive_ladder_response(time, source_currents, *, R, L, G, C,
                                            length, cells, source_shunt_resistance,
                                            load_resistance, load_capacitance,
                                            load_branch_resistance, load_branch_inductance):
    """Propagate explicit Norton currents into a constant passive two-signal line.

    source_currents has shape(times,2) in amperes and a zero first row. Each
    source_shunt_resistance is finite>=0 or None:0 shorts the near node, None
    removes the shunt and leaves an ideal current source. No scalar broadcast.
    Line/outer C and series RL load matrices, zero initial energy, explicit
    cells1..128 and uniform2..10000 time rows follow the reactive voltage API.

    Near port current=Iinj-Vnear/Rsh for finite/open shunts; a short's line
    current comes from internal endpoint C/G and series flux. Source power is
    Vnear*Iinj; shunt loss is Vnear**2/Rsh. It is not the series-resistor power
    partition of an equivalent Thevenin source. Store current units explicitly.

    Preserve internal line/capacitor/branch energy and separate passive losses;
    line and combined RHS balances require relative1e-10. Finite circuit only;
    no mixed voltage/current source kinds, arbitrary dispersion, initial stored
    energy, automatic horizon extension, or general time-domain accuracy claim.
    """
    cap, rb, lb = _branch_input(load_capacitance, load_branch_resistance, load_branch_inductance)
    line, ci, ce, cp, error, bi, be, br, bl = _coupled_boundary_response(time, source_currents,
        R=R, L=L, G=G, C=C, length=length, cells=cells,
        source_resistance=source_shunt_resistance, load_resistance=load_resistance,
        load_capacitance=cap, load_branch_resistance=rb, load_branch_inductance=lb, norton=True)
    return NortonReactiveRLGCLadderResponse(**line, load_capacitor_current=ci,
        load_capacitor_energy=ce, load_capacitor_power=cp,
        total_power_balance_relative_error=error, load_branch_current=bi,
        load_branch_energy=be, load_branch_energy_rate=br, load_branch_resistor_loss=bl)
