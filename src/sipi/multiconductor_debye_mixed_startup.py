# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Typed finite-series voltage/current sources for multiconductor PSD Debye circuits."""
from dataclasses import dataclass, fields
import json
import numpy as np
from scipy.signal import lsim
from .network import _real, _scalar
from .sampling import _integer
from .multiconductor_debye_norton_startup import (
    NortonMulticonductorDebyeReactiveLadderResponse, _multiconductor_debye_norton_input)
from .coupled_debye_startup import _propagate_coupled_debye
from .psd_multiconductor_debye_startup import PSDMulticonductorDebyeRLGCLadderResponse

__all__ = ['MixedSourceMulticonductorDebyeReactiveLadderResponse', 'psd_multiconductor_debye_mixed_reactive_ladder_response']


@dataclass(frozen=True)
class MixedSourceMulticonductorDebyeReactiveLadderResponse:
    """Typed source values and separate voltage-series/current-shunt losses.

    source_values columns have explicit V/A units. Near current enters the
    line and differs from a current-source injection. Internal line energy
    excludes external C/RL storage; total energy includes it.
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
    def source_kinds(self):
        return tuple(source['kind'] for source in self.inputs['sources'])

    @property
    def source_units(self):
        return tuple('V' if kind == 'voltage' else 'A' for kind in self.source_kinds)

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
        out = dict(scope='finite-passive-multiconductor-psd-debye-mixed-reactive-startup', input=self.inputs,
            source_kinds=list(self.source_kinds), source_units=list(self.source_units),
            port_names=list(self.port_names), time_s=self.time.tolist(),
            voltage_v=self.voltage.tolist(), current_into_line_a=self.current.tolist(),
            instantaneous_energy_j=self.energy.tolist(), energy_rate_w=self.energy_rate.tolist(),
            polarization_energy_j=self.polarization_energy.tolist(),
            polarization_energy_rate_w=self.polarization_energy_rate.tolist(),
            total_energy_j=self.total_energy.tolist(), total_energy_rate_w=self.total_energy_rate.tolist(),
            relaxation_loss_w=self.relaxation_loss.tolist(), series_loss_w=self.series_loss.tolist(),
            shunt_loss_w=self.shunt_loss.tolist(), line_power_w=self.line_power.tolist(),
            source_power_w=self.source_power.tolist(), source_series_resistor_loss_w=self.source_series_resistor_loss.tolist(),
            source_shunt_resistor_loss_w=self.source_shunt_resistor_loss.tolist(),
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
        out.update(line_energy_j=self.line_energy.tolist(), line_energy_rate_w=self.line_energy_rate.tolist(),
            load_capacitor_current_a=self.load_capacitor_current.tolist(),
            load_capacitor_energy_j=self.load_capacitor_energy.tolist(),
            load_capacitor_power_w=self.load_capacitor_power.tolist(),
            load_branch_current_a=self.load_branch_current.tolist(),
            load_branch_energy_j=self.load_branch_energy.tolist(),
            load_branch_energy_rate_w=self.load_branch_energy_rate.tolist(),
            load_branch_resistor_loss_w=self.load_branch_resistor_loss.tolist())
        return out



def _multiconductor_debye_mixed_input(time, sources, *, signals, R, L, G, C_inf,
        delta_C, relaxation_hz, length, cells, load_resistance,
        load_capacitance, load_branch_resistance, load_branch_inductance):
    signals = _integer(signals, 3, 4)
    if not isinstance(sources, (list, tuple)) or len(sources) != signals:
        raise ValueError('sources needs signals explicit voltage/current objects')
    columns = []; conductance = []; resistance = []; kinds = []; canonical = []
    for source in sources:
        if (not isinstance(source, dict) or not isinstance(source.get('kind'), str)
                or source['kind'] not in ('voltage', 'current')):
            raise ValueError('each source needs explicit voltage or current kind')
        kind = source['kind']
        value_key, parameter_key = (('voltage_v', 'series_resistance_ohm') if kind == 'voltage'
                                    else ('current_a', 'shunt_conductance_s'))
        if set(source) != {'kind', value_key, parameter_key}:
            raise ValueError('source keys must match its explicit kind and SI units')
        value = _real(value_key, source[value_key])
        if value.ndim != 1 or (columns and value.shape != columns[0].shape):
            raise ValueError('each source waveform must share one-dimensional time rows')
        parameter = _scalar(parameter_key, source[parameter_key], zero=kind == 'current')
        with np.errstate(over='ignore', under='ignore', divide='ignore', invalid='ignore'):
            gs = np.divide(1., parameter) if kind == 'voltage' else parameter
        if not np.isfinite(gs) or (kind == 'voltage' and gs <= 0):
            raise ValueError('source transformation exceeds finite positive conductance scales')
        columns.append(value); conductance.append(gs); resistance.append(parameter if kind == 'voltage' else 0.)
        kinds.append(kind); canonical.append(dict(kind=kind, **{value_key:value.tolist(), parameter_key:parameter}))
    values = np.column_stack(columns); gs = np.array(conductance); voltage = np.array(kinds) == 'voltage'
    injection = values.copy()
    with np.errstate(over='ignore', under='ignore', invalid='ignore'):
        injection[:, voltage] *= gs[voltage]
    if (not np.all(np.isfinite(injection))
            or np.any((values[:, voltage] != 0) & (injection[:, voltage] == 0))):
        raise ValueError('source transformation exceeds finite nonzero current scales')
    data, cap, rb, lb, signals, gs = _multiconductor_debye_norton_input(time, injection,
        signals=signals, R=R, L=L, G=G, C_inf=C_inf, delta_C=delta_C,
        relaxation_hz=relaxation_hz, length=length, cells=cells,
        source_shunt_conductance=gs, load_resistance=load_resistance,
        load_capacitance=load_capacitance, load_branch_resistance=load_branch_resistance,
        load_branch_inductance=load_branch_inductance)
    return data, cap, rb, lb, signals, gs, values, voltage, np.array(resistance), canonical


def psd_multiconductor_debye_mixed_reactive_ladder_response(time, sources, *, signals,
        R, L, G, C_inf, delta_C, relaxation_hz, length, cells, load_resistance,
        load_capacitance, load_branch_resistance, load_branch_inductance):
    """Propagate explicitly typed finite-series voltage and shunted current sources.

    Each of signals3/4 objects has exactly three keys. Voltage: kind='voltage',
    voltage_v[time], finite series_resistance_ohm>0. Current: kind='current',
    current_a[time], finite shunt_conductance_s>=0 (zero=ideal current).
    Uniform2..10000 rows start0 and every source starts0. No voltage R0,
    Dirichlet/current short, scalar broadcast or resistance/conductance alias.

    Finite positive voltage-source conductance1/Rs and injectionVs/Rs reuse
    the unchanged Norton finite circuit. Nonfinite reciprocals/injections or
    a nonzero drive lost to underflow are rejected before propagation. Original
    values/units are preserved in sources, not replaced by equivalent currents.
    Voltage power is Vs*Iterminal; current power is Iinjected*Vnear. Source
    series and shunt losses are separate; totalrelative1e-10 remains required.

    Original PSD line/strength, SPD storage, external C/RL, pole, cell and
    finite-scale contracts remain. This typed boundary does not establish
    arbitrary continuous-transient accuracy or automatic saved/wave admission.
    """
    data, cap, rb, lb, signals, gs, values, vm, rs, sources = _multiconductor_debye_mixed_input(
        time, sources, signals=signals, R=R, L=L, G=G, C_inf=C_inf,
        delta_C=delta_C, relaxation_hz=relaxation_hz, length=length, cells=cells,
        load_resistance=load_resistance, load_capacitance=load_capacitance,
        load_branch_resistance=load_branch_resistance, load_branch_inductance=load_branch_inductance)
    r = _propagate_coupled_debye(data, psd_strength=True,
        result_type=NortonMulticonductorDebyeReactiveLadderResponse, propagator=lsim,
        load_capacitance=cap, load_branch=(rb, lb), signals=signals, source_conductance=gs,
        scale_states=True)
    near_v = r.voltage[:, :signals]; near_i = r.current[:, :signals]
    with np.errstate(over='ignore', under='ignore', invalid='ignore'):
        supplied = np.sum(values[:, vm]*near_i[:, vm], axis=1)+np.sum(values[:, ~vm]*near_v[:, ~vm], axis=1)
        series = np.sum(rs[vm]*near_i[:, vm]**2, axis=1)
        shunt = np.sum(gs[~vm]*near_v[:, ~vm]**2, axis=1)
        losses = series+shunt+r.load_resistor_loss+r.load_branch_resistor_loss+r.series_loss+r.shunt_loss+r.relaxation_loss
        residual = r.total_energy_rate-supplied+losses
    if (not all(np.all(np.isfinite(x)) for x in (supplied, series, shunt, losses, residual))
            or np.any(series < 0) or np.any(shunt < 0)):
        raise ValueError('mixed-source power diagnostics exceed finite scales')
    scale = max(np.max(abs(r.total_energy_rate)), np.max(abs(supplied)), np.max(abs(losses)))
    error = float(np.max(abs(residual))/scale) if scale else 0.
    if not np.isfinite(error) or error > 1e-10:
        raise ValueError('mixed-source power balance exceeds relative 1e-10')
    stored = r.inputs
    stored.pop('source_currents_a'); stored.pop('source_shunt_conductance_s')
    stored['sources'] = sources
    outputs = {f.name:getattr(r, f.name) for f in fields(r)
        if f.name not in ('input_json', 'source_currents', 'source_power',
                          'source_shunt_resistor_loss', 'total_power_balance_relative_error')}
    return MixedSourceMulticonductorDebyeReactiveLadderResponse(**outputs,
        input_json=json.dumps(stored, sort_keys=True, allow_nan=False), source_values=values,
        source_power=supplied, source_series_resistor_loss=series, source_shunt_resistor_loss=shunt,
        total_power_balance_relative_error=error)
