# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict saved periodic Thevenin circuits with explicit source/load tables."""
from __future__ import annotations

from dataclasses import dataclass
import json

import numpy as np

from .band import _metadata
from .circuit_document import _json_copy, _complex_value
from .document import _keys, _unique_object
from .network import LineNetwork, _real
from .periodic import _grid, _time_grid
from .periodic_document import _ports, _extract
from .periodic_termination import PeriodicTerminatedResponse, periodic_terminated_response
from .sampling import _integer

__all__ = ['PeriodicCircuitDocument', 'PeriodicCircuitResult']


@dataclass(frozen=True)
class PeriodicCircuitResult:
    input_json: str
    source_network: LineNetwork
    network: LineNetwork
    extraction: object | None
    solution: PeriodicTerminatedResponse


class PeriodicCircuitDocument:
    """sipi.periodic-circuit/1; every final-basis source and load is explicit.

    Real source values are DC constants or N time samples. Complex finite
    passive terminations are constants or F frequency samples, with real DC.
    Source validation never meshes fields; existing small network algebra is
    allowed. N time samples count against the pre-field/FFT evaluation budget.
    """
    def __init__(self, network, *, source_voltages, terminations, basis='single-ended'):
        self._assign(dict(schema='sipi.periodic-circuit/1', network=network,
            source_voltages=source_voltages, terminations=terminations, basis=basis))

    def _assign(self, data):
        data = _json_copy(data)
        _keys(data, ('schema', 'network', 'basis', 'source_voltages', 'terminations'),
              where='periodic circuit')
        if data['schema'] != 'sipi.periodic-circuit/1':
            raise ValueError('unsupported periodic-circuit schema')
        source, canonical, frequency, ports, refs = _metadata(data['network'])
        count, _, _, _ = _time_grid(frequency)
        if isinstance(source, LineNetwork):
            _grid(source)
        output_ports = _ports(data['basis'], ports, refs)
        for name in ('source_voltages', 'terminations'):
            if not isinstance(data[name], dict) or set(data[name]) != set(output_ports):
                raise ValueError(name+' must explicitly name every output-basis port exactly once')
        sources, loads = {}, {}
        for name in output_ports:
            values = _real('source_voltages '+name, data['source_voltages'][name])
            if values.ndim and values.shape != (count,):
                raise ValueError('source_voltages needs a real constant or 2*frequencies-1 samples per port')
            sources[name] = values.tolist()
            value, encoded = _complex_value(data['terminations'][name], len(frequency))
            if np.any(value.real < 0):
                raise ValueError('terminations must be passive: real part >= 0')
            if (value.item() if value.ndim == 0 else value[0]).imag != 0:
                raise ValueError('DC terminations must be exactly real')
            loads[name] = encoded
        self._data = dict(schema=data['schema'], network=canonical, basis=data['basis'],
                          source_voltages=sources, terminations=loads)
        self._sample_count = count

    @property
    def sample_count(self):
        return self._sample_count

    @classmethod
    def from_dict(cls, data):
        out = cls.__new__(cls); out._assign(data); return out

    @classmethod
    def loads(cls, text):
        def reject(value):
            raise ValueError(f'nonfinite JSON number: {value}')
        return cls.from_dict(json.loads(text, object_pairs_hook=_unique_object, parse_constant=reject))

    def dumps(self):
        return json.dumps(self._data, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)

    def to_dict(self):
        return json.loads(self.dumps())

    def analyze(self, *, max_evaluations=128):
        budget = _integer(max_evaluations, 2, 10000)
        if self.sample_count > budget:
            raise ValueError('periodic time sample count exceeds max_evaluations before field/FFT work')
        data = self._data
        original, network, extraction = _extract(data)
        loads = {name:_complex_value(value, len(network.frequency))[0]
                 for name,value in data['terminations'].items()}
        solution = periodic_terminated_response(network,
            source_voltages=data['source_voltages'], terminations=loads)
        return PeriodicCircuitResult(self.dumps(), original, network, extraction, solution)
