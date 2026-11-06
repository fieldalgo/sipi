# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict saved network transformations using existing extraction contracts."""
from __future__ import annotations

from dataclasses import dataclass
import json

import numpy as np

from .circuit_document import _complex_value, _json_copy, _network_input
from .document import _keys, _unique_object
from .network import LineNetwork, _references
from .termination import terminate_ports

__all__ = ['NetworkTransformDocument', 'NetworkTransformResult']
_BASE_KINDS = ('rlgc', 'touchstone', 'transmission-line', 'volume-line', 'network-assembly', 'lumped-network')


def _source(value):
    if not isinstance(value, dict) or value.get('kind') not in _BASE_KINDS:
        raise ValueError('network requires rlgc, touchstone, transmission-line, volume-line, network-assembly or lumped-network')
    return _network_input(value)


def _loads(value, frequency, ports):
    if not isinstance(value, dict) or not value:
        raise ValueError('loads must be a nonempty object')
    if any(name not in ports for name in value):
        raise ValueError('loads contains an unknown current port')
    if len(value) == len(ports):
        raise ValueError('at least one port must remain')
    decoded, canonical = {}, {}
    for name, load in value.items():
        if isinstance(load, str):
            if load not in ('open', 'short'):
                raise ValueError('string loads must be open or short')
            decoded[name] = canonical[name] = load
        else:
            number, encoded = _complex_value(load, len(frequency))
            if np.any(number.real < 0):
                raise ValueError('loads must be passive: real part >= 0')
            decoded[name], canonical[name] = number, encoded
    return decoded, canonical


@dataclass(frozen=True)
class NetworkTransformResult:
    """Transformed S plus the original network, exact input and optional extraction."""
    network: LineNetwork
    source_network: LineNetwork
    input_json: str
    extraction: object | None


class NetworkTransformDocument:
    """sipi.network-transforms/1: one base input and 1..32 ordered operations.

    Operations are renormalize or terminate-ports. No nested transformations,
    file/network I/O or expressions. Parsing validates geometry and current
    port metadata without meshing; analysis extracts the source only once.
    """
    def __init__(self, network, *, operations):
        self._assign(dict(schema='sipi.network-transforms/1', network=network,
                          operations=operations))

    def _assign(self, data):
        data = _json_copy(data)
        _keys(data, ('schema', 'network', 'operations'), where='network transforms')
        if data['schema'] != 'sipi.network-transforms/1':
            raise ValueError('unsupported network-transforms schema')
        _, source, frequency, ports = _source(data['network'])
        steps = data['operations']
        if not isinstance(steps, list) or not 1 <= len(steps) <= 32:
            raise ValueError('operations must contain 1..32 steps')
        operations = []
        for step in steps:
            if not isinstance(step, dict):
                raise ValueError('each operation must be an object')
            kind = step.get('kind')
            if kind == 'renormalize':
                _keys(step, ('kind', 'reference_ohms'), where='renormalize operation')
                refs = _references(step['reference_ohms'], len(ports))
                operations.append(dict(kind=kind, reference_ohms=refs.tolist()))
            elif kind == 'terminate-ports':
                _keys(step, ('kind', 'loads'), where='terminate-ports operation')
                _, loads = _loads(step['loads'], frequency, ports)
                operations.append(dict(kind=kind, loads=loads))
                ports = tuple(p for p in ports if p not in loads)
            else:
                raise ValueError('unsupported network operation')
        self._data = dict(schema=data['schema'], network=source, operations=operations)
        self._frequency = np.array(frequency, copy=True)
        self._port_names = tuple(ports)

    @property
    def frequency(self):
        out = self._frequency.copy()
        out.setflags(write=False)
        return out

    @property
    def port_names(self):
        return self._port_names

    @classmethod
    def from_dict(cls, data):
        out = cls.__new__(cls)
        out._assign(data)
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

    def analyze(self):
        data = self.to_dict()
        source, _, frequency, ports = _source(data['network'])
        extraction = None if isinstance(source, LineNetwork) else source.analyze()
        original = source if extraction is None else extraction.network
        if original.port_names != ports or not np.array_equal(original.frequency, frequency):
            raise ValueError('extraction changed the documented frequency or port order')
        network = original
        for step in data['operations']:
            if step['kind'] == 'renormalize':
                network = network.renormalized(step['reference_ohms'])
            else:
                loads, _ = _loads(step['loads'], frequency, network.port_names)
                network = terminate_ports(network, loads)
        return NetworkTransformResult(network, original, self.dumps(), extraction)
