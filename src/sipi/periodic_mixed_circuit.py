# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict saved periodic waveforms with explicit mixed terminal boundaries."""
from __future__ import annotations

from dataclasses import dataclass
import json

import numpy as np

from .band import _metadata
from .circuit_document import _json_copy, _complex_value
from .document import _keys, _unique_object
from .network import LineNetwork, _real
from .periodic import _grid, _time_grid
from .periodic_mixed import PeriodicMixedResponse, periodic_mixed_response
from .periodic_document import _ports, _extract
from .sampling import _integer

__all__ = ['PeriodicMixedCircuitDocument', 'PeriodicMixedCircuitResult']


@dataclass(frozen=True)
class PeriodicMixedCircuitResult:
    input_json: str
    source_network: LineNetwork
    network: LineNetwork
    extraction: object | None
    solution: PeriodicMixedResponse


class PeriodicMixedCircuitDocument:
    """sipi.periodic-mixed-circuit/1; every final-basis terminal is explicit.

    Source values are real DC constants or N time samples. Finite passive
    complex loads are scalar/F samples with real DC. Uniform real-DC harmonics
    and odd N=2F-1 follow the periodic API. Parsing never solves fields;
    analysis counts N against the budget before extraction or FFT work.
    """
    def __init__(self, network, *, boundaries, basis='single-ended'):
        self._assign(dict(schema='sipi.periodic-mixed-circuit/1', network=network,
                          basis=basis, boundaries=boundaries))

    def _assign(self, data):
        data = _json_copy(data)
        _keys(data, ('schema', 'network', 'basis', 'boundaries'), where='mixed circuit')
        if data['schema'] != 'sipi.periodic-mixed-circuit/1':
            raise ValueError('unsupported periodic-mixed-circuit schema')
        source, canonical, frequency, ports, refs = _metadata(data['network'])
        count, _, _, _ = _time_grid(frequency)
        if isinstance(source, LineNetwork):
            _grid(source)
        output_ports = _ports(data['basis'], ports, refs)
        if not isinstance(data['boundaries'], dict) or set(data['boundaries']) != set(output_ports):
            raise ValueError('boundaries must explicitly name every output-basis port exactly once')
        boundaries = {}
        for name in output_ports:
            item = data['boundaries'][name]
            if not isinstance(item, dict):
                raise ValueError('each boundary must be an object')
            kind = item.get('kind')
            if kind == 'thevenin':
                source_key, load_key = 'source_voltage', 'impedance'
            elif kind == 'norton':
                source_key, load_key = 'source_current', 'admittance'
            else:
                raise ValueError('boundary kind must be thevenin or norton')
            _keys(item, ('kind', source_key, load_key), where='mixed boundary')
            source = _real(source_key+' '+name, item[source_key])
            if source.ndim and source.shape != (count,):
                raise ValueError('periodic source needs a real constant or 2*frequencies-1 samples')
            value, load = _complex_value(item[load_key], len(frequency))
            if np.any(value.real < 0):
                raise ValueError('boundary loads must be passive: real part >= 0')
            if (value.item() if value.ndim == 0 else value[0]).imag != 0:
                raise ValueError('DC impedances and admittances must be exactly real')
            boundaries[name] = dict(kind=kind, **{source_key:source.tolist(), load_key:load})
        self._data = dict(schema=data['schema'], network=canonical,
                          basis=data['basis'], boundaries=boundaries)
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
        boundaries = {name:{key:(value if key in ('kind', 'source_voltage', 'source_current') else
            _complex_value(value, len(network.frequency))[0]) for key,value in item.items()}
            for name,item in data['boundaries'].items()}
        solution = periodic_mixed_response(network, boundaries)
        return PeriodicMixedCircuitResult(self.dumps(), original, network, extraction, solution)
