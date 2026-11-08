# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict saved inputs for an explicit passive three/four-signal Debye startup circuit."""
from dataclasses import fields
import json

import numpy as np

from .document import _keys, _unique_object
from .sampling import _copy, _integer
from .multiconductor_debye_startup import MulticonductorDebyeRLGCLadderResponse, _multiconductor_debye_input, multiconductor_debye_rlgc_ladder_response

__all__ = ['MulticonductorDebyeRLGCLadderDocument']

_SCHEMA = 'sipi.multiconductor-debye-rlgc-startup/1'
_NAMES = dict(time_s='time', source_voltages_v='source_voltages', signals='signals',
    R_ohm_per_m='R', L_h_per_m='L', G_s_per_m='G', C_inf_f_per_m='C_inf',
    length_m='length', cells='cells', source_resistance_ohm='source_resistance',
    load_resistance_ohm='load_resistance', delta_C_f_per_m='delta_C',
    relaxation_hz='relaxation_hz')


class MulticonductorDebyeRLGCLadderDocument:
    """Preserve declared poles and PWL samples; validate without propagation.

    max_evaluations counts actual time rows, separately from the physical
    1..64 cell and 1..2 pole limits. It is not a convergence/runtime guarantee.
    """
    def __init__(self, time, source_voltages, *, signals, R, L, G, C_inf, delta_C,
                 relaxation_hz, length, cells, source_resistance, load_resistance):
        self._assign_inputs(dict(time=time, source_voltages=source_voltages, signals=signals,
            R=R, L=L, G=G, C_inf=C_inf, delta_C=delta_C, relaxation_hz=relaxation_hz,
            length=length, cells=cells, source_resistance=source_resistance,
            load_resistance=load_resistance))

    def _assign_inputs(self, arguments):
        data, signals = _multiconductor_debye_input(**arguments)
        values = (*data[:2], signals, *data[2:])
        self._data = dict(schema=_SCHEMA, **{saved:(value.tolist() if isinstance(value, np.ndarray)
            else value) for saved, value in zip(_NAMES, values)})

    @classmethod
    def from_dict(cls, data):
        data = _copy(data)
        _keys(data, ('schema', *_NAMES), where='multiconductor Debye startup')
        if data['schema'] != _SCHEMA:
            raise ValueError('unsupported multiconductor-debye-rlgc-startup schema')
        out = cls.__new__(cls)
        out._assign_inputs({api:data[saved] for saved, api in _NAMES.items()})
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
            raise ValueError('Debye time samples exceed max_evaluations before state propagation')
        data = self.to_dict()
        result = multiconductor_debye_rlgc_ladder_response(**{api:data[saved] for saved, api in _NAMES.items()})
        expected = {k:v for k,v in data.items() if k != 'schema'}
        n = data['cells']; samples = self.samples; poles = len(data['delta_C_f_per_m']); signals = data['signals']
        if (type(result) is not MulticonductorDebyeRLGCLadderResponse or result.inputs != expected
                or not np.array_equal(result.time, data['time_s'])
                or not np.array_equal(result.source_voltages, data['source_voltages_v'])):
            raise ValueError('Debye solve changed saved inputs, time or source')
        shapes = dict(source_voltages=(samples, signals), node_voltage=(samples, n+1, signals), segment_current=(samples, n, signals),
            voltage=(samples, 2*signals), current=(samples, 2*signals),
            polarization_voltage=(samples, n+1, poles, signals),
            polarization_charge=(samples, n+1, poles, signals),
            polarization_current=(samples, n+1, poles, signals))
        for field in fields(result):
            if field.type is np.ndarray and getattr(result, field.name).shape != shapes.get(field.name, (samples,)):
                raise ValueError('Debye solve changed saved state or diagnostic shape')
        return result
