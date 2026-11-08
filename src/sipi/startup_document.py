# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict stored inputs for initially unenergized scalar lossless startup."""
import json

import numpy as np

from .document import _keys, _unique_object
from .sampling import _copy, _integer
from .startup import LosslessLineResponse, _startup_input, lossless_line_response

__all__ = ['LosslessStartupDocument']

_SCHEMA = 'sipi.lossless-startup/1'
_NAMES = dict(time_s='time', source_times_s='source_times', source_voltages_v='source_voltages',
    z0_ohm='z0_ohm', delay_s='delay_s', source_resistance_ohm='source_resistance',
    load_resistance_ohm='load_resistance', max_terms='max_terms')


class LosslessStartupDocument:
    """Saved time/PWL/resistive inputs, without waveform work during parsing.

    The saved max_terms is an independent hard cap. analyze's caller budget
    counts actual required forward terms, not the saved ceiling or time samples.
    """
    def __init__(self, time, *, source_times, source_voltages, z0_ohm, delay_s,
                 source_resistance, load_resistance, max_terms=10000):
        self._assign_inputs(dict(time=time, source_times=source_times, source_voltages=source_voltages,
            z0_ohm=z0_ohm, delay_s=delay_s, source_resistance=source_resistance,
            load_resistance=load_resistance, max_terms=max_terms))

    def _assign_inputs(self, arguments):
        data, _, terms = _startup_input(**arguments)
        self._data = dict(schema=_SCHEMA, **{saved:(data[api].tolist() if isinstance(data[api], np.ndarray)
            else data[api]) for saved,api in _NAMES.items()})
        self._terms = terms

    @classmethod
    def from_dict(cls, data):
        data = _copy(data)
        _keys(data, ('schema', *_NAMES), where='lossless startup')
        if data['schema'] != _SCHEMA:
            raise ValueError('unsupported lossless-startup schema')
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
    def required_terms(self):
        return self._terms

    def analyze(self, *, max_evaluations=128):
        budget = _integer(max_evaluations, 2, 10000)
        if self.required_terms > budget:
            raise ValueError('required startup terms exceed max_evaluations before waveform evaluation')
        data = self.to_dict()
        result = lossless_line_response(**{api:data[saved] for saved,api in _NAMES.items()})
        expected_input = {k:v for k,v in data.items() if k not in ('schema', 'time_s')}
        if (not isinstance(result, LosslessLineResponse) or result.terms != self.required_terms
                or not np.array_equal(result.time, data['time_s'])
                or result.to_dict()['input'] != expected_input):
            raise ValueError('startup solve changed saved inputs or required term count')
        return result
