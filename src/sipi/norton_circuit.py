# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict saved frequency-domain Norton circuits with explicit current/load tables."""
from __future__ import annotations

from dataclasses import dataclass
import json

import numpy as np

from .band import _metadata
from .circuit_document import _json_copy, _complex_value
from .document import _keys, _unique_object
from .network import LineNetwork
from .norton_termination import NortonTerminatedNetwork, terminate_norton_network
from .periodic_document import _ports, _extract
from .sampling import _integer

__all__ = ['NortonCircuitDocument', 'NortonCircuitResult']


@dataclass(frozen=True)
class NortonCircuitResult:
    input_json: str
    source_network: LineNetwork
    network: LineNetwork
    extraction: object | None
    response: NortonTerminatedNetwork


class NortonCircuitDocument:
    """sipi.norton-circuit/1; every final-basis current and admittance is explicit.

    Values are finite complex constants or F frequency samples; passive
    admittance Y=0 is an ideal current/open boundary, never an infinity.
    Validation does not solve fields. Analysis counts F against the budget
    before extraction or boundary feedback. No periodic/uniform-grid or real-DC
    restriction is added to the existing frequency-domain source contract.
    """
    def __init__(self, network, *, source_currents, termination_admittances, basis='single-ended'):
        self._assign(dict(schema='sipi.norton-circuit/1', network=network, basis=basis,
            source_currents=source_currents, termination_admittances=termination_admittances))

    def _assign(self, data):
        data = _json_copy(data)
        _keys(data, ('schema', 'network', 'basis', 'source_currents', 'termination_admittances'),
              where='Norton circuit')
        if data['schema'] != 'sipi.norton-circuit/1':
            raise ValueError('unsupported norton-circuit schema')
        _, canonical, frequency, ports, refs = _metadata(data['network'])
        output_ports = _ports(data['basis'], ports, refs)
        tables = {}
        for key in ('source_currents', 'termination_admittances'):
            if not isinstance(data[key], dict) or set(data[key]) != set(output_ports):
                raise ValueError(key+' must explicitly name every output-basis port exactly once')
            table = {}
            for name in output_ports:
                value, encoded = _complex_value(data[key][name], len(frequency))
                if key == 'termination_admittances' and np.any(value.real < 0):
                    raise ValueError('termination_admittances must be passive: real part >= 0')
                table[name] = encoded
            tables[key] = table
        self._data = dict(schema=data['schema'], network=canonical, basis=data['basis'], **tables)
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
            raise ValueError('Norton frequency count exceeds max_evaluations before field/feedback work')
        data = self._data
        original, network, extraction = _extract(data)
        currents, admittances = ({name:_complex_value(value, self.frequency_count)[0]
            for name,value in data[key].items()} for key in ('source_currents', 'termination_admittances'))
        response = terminate_norton_network(network, source_currents=currents,
                                            termination_admittances=admittances)
        return NortonCircuitResult(self.dumps(), original, network, extraction, response)
