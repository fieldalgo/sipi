# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit current-source RLGC inputs with passive shunts and external C/RL loads."""
import json

import numpy as np

from .document import _keys, _unique_object
from .sampling import _copy, _integer
from .norton_startup import NortonReactiveRLGCLadderResponse, coupled_norton_reactive_ladder_response
from .coupled_boundary_startup import _norton_input
from .coupled_reactive_startup import _branch_input

__all__ = ['NortonReactiveRLGCLadderDocument']

_SCHEMA = 'sipi.norton-rlgc-startup/1'
_NAMES = dict(time_s='time', source_currents_a='source_currents',
    R_ohm_per_m='R', L_h_per_m='L', G_s_per_m='G', C_f_per_m='C',
    length_m='length', cells='cells', source_shunt_resistance_ohm='source_shunt_resistance',
    load_resistance_ohm='load_resistance', load_capacitance_f='load_capacitance',
    load_branch_resistance_ohm='load_branch_resistance', load_branch_inductance_h='load_branch_inductance')


class NortonReactiveRLGCLadderDocument:
    """Explicit cells and uniform PWL samples, validated without propagation.

    Caller max_evaluations bounds actual time samples, not cells or states.
    The saved cell count remains unchanged under the API's separate 1..128 cap.
    These limits do not guarantee spatial/source convergence or runtime.
    """
    def __init__(self, time, source_currents, *, R, L, G, C, length, cells,
                 source_shunt_resistance, load_resistance, load_capacitance,
                 load_branch_resistance, load_branch_inductance):
        self._assign_inputs(dict(time=time, source_currents=source_currents,
            R=R, L=L, G=G, C=C, length=length, cells=cells,
            source_shunt_resistance=source_shunt_resistance, load_resistance=load_resistance, load_capacitance=load_capacitance,
            load_branch_resistance=load_branch_resistance, load_branch_inductance=load_branch_inductance))

    def _assign_inputs(self, arguments):
        arguments = dict(arguments)
        cap, rb, lb = _branch_input(arguments.pop('load_capacitance'),
            arguments.pop('load_branch_resistance'), arguments.pop('load_branch_inductance'))
        shunt = arguments.pop('source_shunt_resistance')
        values = (*_norton_input(**arguments, source_resistance=shunt), cap, rb, lb)
        self._data = dict(schema=_SCHEMA, **{saved:(value.tolist() if isinstance(value, np.ndarray)
            else value) for saved,value in zip(_NAMES, values)})

    @classmethod
    def from_dict(cls, data):
        data = _copy(data)
        _keys(data, ('schema', *_NAMES), where='Norton RLGC startup')
        if data['schema'] != _SCHEMA:
            raise ValueError('unsupported norton-rlgc-startup schema')
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
        result = coupled_norton_reactive_ladder_response(**{api:data[saved] for saved,api in _NAMES.items()})
        expected = {k:v for k,v in data.items() if k != 'schema'}
        if (not isinstance(result, NortonReactiveRLGCLadderResponse) or result.inputs != expected
                or not np.array_equal(result.time, data['time_s'])
                or not np.array_equal(result.source_currents, data['source_currents_a'])
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
