# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit mixed voltage/current startup with passive external C and RL loads."""
from dataclasses import dataclass
import json

import numpy as np

from .coupled_boundary_startup import _coupled_boundary_response
from .coupled_reactive_startup import _branch_input

__all__ = ['MixedSourceRLGCLadderResponse', 'coupled_mixed_source_ladder_response']


@dataclass(frozen=True)
class MixedSourceRLGCLadderResponse:
    """Per-source typed inputs and separate series/shunt source losses.

    source_values columns use source_units (V or A), determined by source_kinds.
    Port currents enter the line; injected currents differ from terminal currents.
    All state/diagnostic arrays are detached read-only values.
    """
    input_json: str
    time: np.ndarray
    source_values: np.ndarray
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
    source_series_resistor_loss: np.ndarray
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
        for name in ('time', 'source_values', 'node_voltage', 'segment_current',
                     'voltage', 'current', 'energy', 'energy_rate', 'series_loss',
                     'shunt_loss', 'line_power', 'source_power', 'source_series_resistor_loss', 'source_shunt_resistor_loss',
                     'load_resistor_loss', 'load_capacitor_current', 'load_capacitor_energy',
                     'load_capacitor_power', 'load_branch_current', 'load_branch_energy',
                     'load_branch_energy_rate', 'load_branch_resistor_loss'):
            value = np.array(getattr(self, name), dtype=float, copy=True)
            if not np.all(np.isfinite(value)):
                raise ValueError('mixed-source startup output must remain finite')
            value.setflags(write=False)
            object.__setattr__(self, name, value)
        if not all(np.all(np.isfinite(a)) for a in (self.total_energy, self.total_energy_rate)):
            raise ValueError('combined mixed-source startup energy must remain finite')

    @property
    def source_kinds(self):
        return tuple(source['kind'] for source in self.inputs['sources'])

    @property
    def source_units(self):
        return tuple('V' if kind == 'voltage' else 'A' for kind in self.source_kinds)

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
        out = dict(scope='finite-passive-two-signal-mixed-source-reactive-startup', input=self.inputs,
            source_kinds=list(self.source_kinds), source_units=list(self.source_units),
            port_names=list(self.port_names), time_s=self.time.tolist(),
            voltage_v=self.voltage.tolist(), current_into_line_a=self.current.tolist(),
            stored_energy_j=self.energy.tolist(), energy_rate_w=self.energy_rate.tolist(),
            series_loss_w=self.series_loss.tolist(), shunt_loss_w=self.shunt_loss.tolist(),
            line_power_w=self.line_power.tolist(), source_power_w=self.source_power.tolist(),
            source_series_resistor_loss_w=self.source_series_resistor_loss.tolist(),
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


def coupled_mixed_source_ladder_response(time, sources, *, R, L, G, C,
                                          length, cells, load_resistance, load_capacitance,
                                          load_branch_resistance, load_branch_inductance):
    """Propagate two explicitly typed voltage/current sources into a passive line.

    sources is a list/tuple of two dictionaries. Voltage source keys are kind,
    voltage_v (one value per time) and series_resistance_ohm (finite>=0).
    Current source keys are kind,current_a and shunt_resistance_ohm (finite>=0
    or None). Exact keys,real finite waveforms,zero first row; no unit inference.
    Voltage R0 prescribes near voltage; current R0 shorts it; current None is
    an ideal injection without a shunt. Both homogeneous and mixed kinds work.

    Constant real symmetric PSD line R/G,conditioned SPD L/C,PSD load C/Rbranch,
    conditioned SPD Lbranch,positive length,explicit1..128 cells,uniform2..10000
    time rows starting0 and zero initial energy retain the reactive API limits.
    Port currents enter the line. source_values have per-column source_units.
    Voltage-source power is Vs*Iterminal,current-source power is Iinj*Vterminal;
    source_series_resistor_loss and source_shunt_resistor_loss remain separate.
    Line/capacitor/branch energies and line/combined relative1e-10 balance stay.

    Finite circuit only; no arbitrary netlist,dispersion,initial energy or
    automatic settling/time-grid change. Saved/wave adapters are separate.
    """
    cap, rb, lb = _branch_input(load_capacitance, load_branch_resistance, load_branch_inductance)
    line, ci, ce, cp, error, bi, be, br, bl = _coupled_boundary_response(time, sources,
        R=R, L=L, G=G, C=C, length=length, cells=cells,
        source_resistance=None, load_resistance=load_resistance,
        load_capacitance=cap, load_branch_resistance=rb, load_branch_inductance=lb, mixed_sources=True)
    return MixedSourceRLGCLadderResponse(**line, load_capacitor_current=ci,
        load_capacitor_energy=ce, load_capacitor_power=cp,
        total_power_balance_relative_error=error, load_branch_current=bi,
        load_branch_energy=be, load_branch_energy_rate=br, load_branch_resistor_loss=bl)
