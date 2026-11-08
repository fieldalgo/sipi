# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Typed mixed-source RLGC inputs with explicit waveform units and passive loads."""
import json

import numpy as np

from .document import _keys, _unique_object
from .sampling import _copy, _integer
from .mixed_startup import MixedSourceRLGCLadderResponse, coupled_mixed_source_ladder_response
from .coupled_boundary_startup import _mixed_input, _mixed_sources_data
from .coupled_reactive_startup import _branch_input

__all__ = ['MixedSourceRLGCLadderDocument']

_SCHEMA = 'sipi.mixed-rlgc-startup/1'
_NAMES = dict(time_s='time', sources='sources',
    R_ohm_per_m='R', L_h_per_m='L', G_s_per_m='G', C_f_per_m='C',
    length_m='length', cells='cells',
    load_resistance_ohm='load_resistance', load_capacitance_f='load_capacitance',
    load_branch_resistance_ohm='load_branch_resistance', load_branch_inductance_h='load_branch_inductance')


class MixedSourceRLGCLadderDocument:
    """Explicit cells and uniform PWL samples, validated without propagation.

    Caller max_evaluations bounds actual time samples, not cells or states.
    The saved cell count remains unchanged under the API's separate 1..128 cap.
    These limits do not guarantee spatial/source convergence or runtime.
    """
    def __init__(self, time, sources, *, R, L, G, C, length, cells,
                 load_resistance, load_capacitance, load_branch_resistance, load_branch_inductance):
        self._assign_inputs(dict(time=time, sources=sources,
            R=R, L=L, G=G, C=C, length=length, cells=cells,
            load_resistance=load_resistance, load_capacitance=load_capacitance,
            load_branch_resistance=load_branch_resistance, load_branch_inductance=load_branch_inductance))

    def _assign_inputs(self, arguments):
        arguments = dict(arguments)
        cap, rb, lb = _branch_input(arguments.pop('load_capacitance'),
            arguments.pop('load_branch_resistance'), arguments.pop('load_branch_inductance'))
        time, drive, r, l, g, c, length, n, rs, rl, kinds = _mixed_input(**arguments)
        values = (time, _mixed_sources_data(drive, rs, kinds), r, l, g, c, length, n, rl, cap, rb, lb)
        self._data = dict(schema=_SCHEMA, **{saved:(value.tolist() if isinstance(value, np.ndarray)
            else value) for saved,value in zip(_NAMES, values)})

    @classmethod
    def from_dict(cls, data):
        data = _copy(data)
        _keys(data, ('schema', *_NAMES), where='mixed-source RLGC startup')
        if data['schema'] != _SCHEMA:
            raise ValueError('unsupported mixed-rlgc-startup schema')
        out = cls.__new__(cls)
        out._assign_inputs({api:data[saved] for saved,api in _NAMES.items()})
        return out

    @classmethod
    def loads(cls, text):
        def reject(value):
            raise ValueError(f'nonfinite JSON number: {value}')
        return cls.from_dict(json.loads(text, object_pairs_hook=_unique_object, parse_constant=reject))

    def dumps(self):
        return json.dumps(self._data, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)

    def to_dict(self):
        return json.loads(self.dumps())

    @property
    def samples(self):
        return len(self._data['time_s'])

    def analyze(self, *, max_evaluations=128):
        budget = _integer(max_evaluations, 2, 10000)
        if self.samples > budget:
            raise ValueError('RLGC time samples exceed max_evaluations before state propagation')
        data = self.to_dict()
        result = coupled_mixed_source_ladder_response(**{api:data[saved] for saved,api in _NAMES.items()})
        kinds = tuple(source['kind'] for source in data['sources'])
        units = tuple('V' if kind == 'voltage' else 'A' for kind in kinds)
        drive = np.column_stack([source['voltage_v' if kind == 'voltage' else 'current_a']
            for source, kind in zip(data['sources'], kinds)])
        expected = {k:v for k,v in data.items() if k != 'schema'}
        if (not isinstance(result, MixedSourceRLGCLadderResponse) or result.inputs != expected
                or not np.array_equal(result.time, data['time_s'])
                or not np.array_equal(result.source_values, drive)
                or result.source_kinds != kinds or result.source_units != units
                or result.source_series_resistor_loss.shape != (self.samples,)
                or result.source_shunt_resistor_loss.shape != (self.samples,)
                or result.node_voltage.shape != (self.samples, data['cells']+1, 2)
                or result.segment_current.shape != (self.samples, data['cells'], 2)
                or result.voltage.shape != (self.samples, 4)
                or result.current.shape != (self.samples, 4)
                or result.load_capacitor_current.shape != (self.samples, 2)
                or result.load_capacitor_energy.shape != (self.samples,)
                or result.load_capacitor_power.shape != (self.samples,)
                or result.load_branch_current.shape != (self.samples, 2)
                or result.load_branch_energy.shape != (self.samples,)
                or result.load_branch_energy_rate.shape != (self.samples,)
                or result.load_branch_resistor_loss.shape != (self.samples,)):
            raise ValueError('RLGC solve changed saved inputs, time or cell count')
        return result
