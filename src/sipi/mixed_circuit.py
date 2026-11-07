# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict saved frequency-domain circuits with explicit mixed terminal boundaries."""
from __future__ import annotations

from dataclasses import dataclass
import json

import numpy as np

from .band import _metadata
from .circuit_document import _json_copy, _complex_value
from .document import _keys, _unique_object
from .network import LineNetwork
from .mixed_termination import MixedTerminatedNetwork, terminate_mixed_network
from .periodic_document import _ports, _extract
from .sampling import _integer

__all__ = ['MixedCircuitDocument', 'MixedCircuitResult']


@dataclass(frozen=True)
class MixedCircuitResult:
    input_json: str
    source_network: LineNetwork
    network: LineNetwork
    extraction: object | None
    response: MixedTerminatedNetwork


class MixedCircuitDocument:
    """sipi.mixed-circuit/1; every final-basis terminal is explicit.

    Each boundary selects finite Thevenin voltage/impedance or Norton current/
    admittance. Complex constants/F samples, nonnegative real loads, Z=0 and
    Y=0 retain the API contract. No periodic or real-DC restriction is added.
    Parsing does not solve fields; F counts against the pre-field budget.
    """
    def __init__(self, network, *, boundaries, basis='single-ended'):
        self._assign(dict(schema='sipi.mixed-circuit/1', network=network,
                          basis=basis, boundaries=boundaries))

    def _assign(self, data):
        data = _json_copy(data)
        _keys(data, ('schema', 'network', 'basis', 'boundaries'), where='mixed circuit')
        if data['schema'] != 'sipi.mixed-circuit/1':
            raise ValueError('unsupported mixed-circuit schema')
        _, canonical, frequency, ports, refs = _metadata(data['network'])
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
            _, source = _complex_value(item[source_key], len(frequency))
            value, load = _complex_value(item[load_key], len(frequency))
            if np.any(value.real < 0):
                raise ValueError('boundary loads must be passive: real part >= 0')
            boundaries[name] = dict(kind=kind, **{source_key:source, load_key:load})
        self._data = dict(schema=data['schema'], network=canonical,
                          basis=data['basis'], boundaries=boundaries)
        self._frequency_count = len(frequency)

    @property
    def frequency_count(self):
        return self._frequency_count

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
        if self.frequency_count > budget:
            raise ValueError('mixed frequency count exceeds max_evaluations before field/feedback work')
        data = self._data
        original, network, extraction = _extract(data)
        boundaries = {name:{key:(value if key == 'kind' else
            _complex_value(value, self.frequency_count)[0]) for key,value in item.items()}
            for name,item in data['boundaries'].items()}
        response = terminate_mixed_network(network, boundaries)
        return MixedCircuitResult(self.dumps(), original, network, extraction, response)
