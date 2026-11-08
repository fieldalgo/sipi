# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit v3 two-signal RLGC inputs with a passive load-capacitance matrix."""
import json

import numpy as np

from .document import _keys, _unique_object
from .sampling import _copy, _integer
from .coupled_capacitive_startup import CapacitiveRLGCLadderResponse, coupled_capacitive_ladder_response
from .coupled_boundary_startup import _boundary_input
from .coupled_startup import _passive_matrix

__all__ = ['CapacitiveRLGCLadderDocument']

_SCHEMA = 'sipi.coupled-rlgc-startup/3'
_NAMES = dict(time_s='time', source_voltages_v='source_voltages',
    R_ohm_per_m='R', L_h_per_m='L', G_s_per_m='G', C_f_per_m='C',
    length_m='length', cells='cells', source_resistance_ohm='source_resistance',
    load_resistance_ohm='load_resistance', load_capacitance_f='load_capacitance')


class CapacitiveRLGCLadderDocument:
    """Explicit cells and uniform PWL samples, validated without propagation.

    Caller max_evaluations bounds actual time samples, not cells or states.
    The saved cell count remains unchanged under the API's separate 1..128 cap.
    These limits do not guarantee spatial/source convergence or runtime.
    """
    def __init__(self, time, source_voltages, *, R, L, G, C, length, cells,
                 source_resistance, load_resistance, load_capacitance):
        self._assign_inputs(dict(time=time, source_voltages=source_voltages,
            R=R, L=L, G=G, C=C, length=length, cells=cells,
            source_resistance=source_resistance, load_resistance=load_resistance, load_capacitance=load_capacitance))

    def _assign_inputs(self, arguments):
        arguments = dict(arguments)
        cap = _passive_matrix('load_capacitance', arguments.pop('load_capacitance'))
        values = (*_boundary_input(**arguments), cap)
        self._data = dict(schema=_SCHEMA, **{saved:(value.tolist() if isinstance(value, np.ndarray)
            else value) for saved,value in zip(_NAMES, values)})

    @classmethod
    def from_dict(cls, data):
        data = _copy(data)
        _keys(data, ('schema', *_NAMES), where='coupled RLGC startup')
        if data['schema'] != _SCHEMA:
            raise ValueError('unsupported coupled-rlgc-startup schema')
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
        result = coupled_capacitive_ladder_response(**{api:data[saved] for saved,api in _NAMES.items()})
        expected = {k:v for k,v in data.items() if k != 'schema'}
        if (not isinstance(result, CapacitiveRLGCLadderResponse) or result.inputs != expected
                or not np.array_equal(result.time, data['time_s'])
                or not np.array_equal(result.source_voltages, data['source_voltages_v'])
                or result.node_voltage.shape != (self.samples, data['cells']+1, 2)
                or result.segment_current.shape != (self.samples, data['cells'], 2)
                or result.voltage.shape != (self.samples, 4)
                or result.current.shape != (self.samples, 4)
                or result.load_capacitor_current.shape != (self.samples, 2)
                or result.load_capacitor_energy.shape != (self.samples,)
                or result.load_capacitor_power.shape != (self.samples,)):
            raise ValueError('RLGC solve changed saved inputs, time or cell count')
        return result
