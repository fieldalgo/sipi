# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict saved network transformations using existing extraction contracts."""
from __future__ import annotations

from dataclasses import dataclass
import json

import numpy as np

from .circuit_document import _complex_value, _json_copy, _network_input
from .connection import _connection_layout, cascade_networks, deembed_network
from .document import _keys, _unique_object
from .network import LineNetwork, _references
from .termination import terminate_ports

__all__ = ['NetworkTransformDocument', 'NetworkTransformResult']
_BASE_KINDS = ('rlgc', 'touchstone', 'transmission-line', 'volume-line', 'network-assembly', 'lumped-network')
_FIXTURE_KINDS = ('rlgc', 'touchstone', 'transmission-line', 'volume-line', 'lumped-network')


def _source(value):
    if not isinstance(value, dict) or value.get('kind') not in _BASE_KINDS:
        raise ValueError('network requires rlgc, touchstone, transmission-line, volume-line, network-assembly or lumped-network')
    return _network_input(value)


def _metadata(value):
    source, canonical, frequency, ports = _source(value)
    references = (source.z_ref if isinstance(source, LineNetwork) or value['kind'] == 'network-assembly'
                  else _references(canonical['document']['reference_ohms'], len(ports)))
    return source, canonical, frequency, ports, references


def _fixture(value, frequency, ports):
    if not isinstance(value, dict) or value.get('kind') not in _FIXTURE_KINDS:
        raise ValueError('fixtures require base networks; assembly and transformation nesting is unsupported')
    _, canonical, other_f, other_ports, other_refs = _metadata(value)
    if not np.array_equal(frequency, other_f):
        raise ValueError('fixture must have identical frequency samples')
    if len(ports) % 2 or len(other_ports) != len(ports):
        raise ValueError('fixture operations require equal single-ended 2N port counts, ordered near then far')
    return canonical, other_ports, other_refs


def _output_names(step, defaults):
    names = step.get('port_names', list(defaults))
    if (not isinstance(names, list) or len(names) != len(defaults)
            or any(not isinstance(p, str) or not p.strip() or '\n' in p or '\r' in p for p in names)
            or len(set(names)) != len(names)):
        raise ValueError('port_names must be an array of unique nonempty single-line output names')
    return tuple(names)


def _cascade_step(step, frequency, ports, references):
    _keys(step, ('kind', 'side', 'network'), ('port_names',), where='cascade operation')
    if step['side'] not in ('left', 'right'):
        raise ValueError('cascade side must be left or right')
    fixture, other_ports, other_refs = _fixture(step['network'], frequency, ports)
    left_p, left_r, right_p, right_r = ports, references, other_ports, other_refs
    if step['side'] == 'left':
        left_p, left_r, right_p, right_r = other_ports, other_refs, ports, references
    n = len(ports)//2
    names = _output_names(step, left_p[:n]+right_p[n:])
    _, _, names, refs = _connection_layout(left_p, left_r, right_p, right_r,
        list(zip(left_p[n:], right_p[:n])), names)
    return dict(kind='cascade', side=step['side'], network=fixture, port_names=list(names)), names, refs


def _deembed_step(step, frequency, ports, references):
    _keys(step, ('kind', 'left', 'right'), ('port_names',), where='deembed operation')
    if len(ports) % 2:
        raise ValueError('fixture operations require single-ended 2N ports ordered near then far')
    if step['left'] is None and step['right'] is None:
        raise ValueError('at least one known fixture is required')
    n = len(ports)//2
    near_p, far_p = ports[:n], ports[n:]
    near_r, far_r = references[:n], references[n:]
    canonical = dict(kind='deembed', left=None, right=None)
    for side in ('left', 'right'):
        if step[side] is None:
            continue
        fixture, other_p, other_r = _fixture(step[side], frequency, ports)
        outer = slice(None, n) if side == 'left' else slice(n, None)
        inner = slice(n, None) if side == 'left' else slice(None, n)
        if not np.array_equal(references[outer], other_r[outer]):
            raise ValueError('fixture outer references must match current ports; renormalize explicitly first')
        if side == 'left':
            near_p, near_r = other_p[inner], other_r[inner]
        else:
            far_p, far_r = other_p[inner], other_r[inner]
        canonical[side] = fixture
    names = _output_names(step, near_p+far_p)
    canonical['port_names'] = list(names)
    return canonical, names, np.r_[near_r, far_r]


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
    fixture_networks: tuple[LineNetwork, ...] = ()
    fixture_extractions: tuple[object | None, ...] = ()


class NetworkTransformDocument:
    """One base input and 1..32 ordered operations; v1 is the default.

    v1 supports renormalize and terminate-ports; explicit v2 also saves cascade
    and known-fixture removal. No recursive fixtures, file/network I/O or
    expressions. Parsing validates current port metadata without meshing;
    analysis extracts each geometry occurrence once.
    """
    def __init__(self, network, *, operations, schema='sipi.network-transforms/1'):
        self._assign(dict(schema=schema, network=network,
                          operations=operations))

    def _assign(self, data):
        data = _json_copy(data)
        _keys(data, ('schema', 'network', 'operations'), where='network transforms')
        if data['schema'] not in ('sipi.network-transforms/1', 'sipi.network-transforms/2'):
            raise ValueError('unsupported network-transforms schema')
        _, source, frequency, ports, references = _metadata(data['network'])
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
                references = refs
            elif kind == 'terminate-ports':
                _keys(step, ('kind', 'loads'), where='terminate-ports operation')
                _, loads = _loads(step['loads'], frequency, ports)
                operations.append(dict(kind=kind, loads=loads))
                references = references[[i for i, p in enumerate(ports) if p not in loads]]
                ports = tuple(p for p in ports if p not in loads)
            elif kind in ('cascade', 'deembed'):
                if data['schema'] != 'sipi.network-transforms/2':
                    raise ValueError('fixture operations require sipi.network-transforms/2')
                operation = _cascade_step if kind == 'cascade' else _deembed_step
                canonical, ports, references = operation(step, frequency, ports, references)
                operations.append(canonical)
            else:
                raise ValueError('unsupported network operation')
        self._data = dict(schema=data['schema'], network=source, operations=operations)
        self._frequency = np.array(frequency, copy=True)
        self._port_names = tuple(ports)
        self._references = np.array(references, copy=True)

    @property
    def frequency(self):
        out = self._frequency.copy()
        out.setflags(write=False)
        return out

    @property
    def port_names(self):
        return self._port_names

    @property
    def z_ref(self):
        out = self._references.copy()
        out.setflags(write=False)
        return out

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
        def extract(value):
            source, _, frequency, ports, references = _metadata(value)
            extraction = None if isinstance(source, LineNetwork) else source.analyze()
            network = source if extraction is None else extraction.network
            if (network.port_names != ports or not np.array_equal(network.frequency, frequency)
                    or not np.array_equal(network.z_ref, references)):
                raise ValueError('extraction changed the documented frequency, port order or references')
            return network, extraction
        original, extraction = extract(data['network'])
        fixture_networks, fixture_extractions = [], []
        def fixture(value):
            if value is None:
                return None
            network, result = extract(value)
            fixture_networks.append(network)
            fixture_extractions.append(result)
            return network
        network = original
        for step in data['operations']:
            if step['kind'] == 'renormalize':
                network = network.renormalized(step['reference_ohms'])
            elif step['kind'] == 'terminate-ports':
                loads, _ = _loads(step['loads'], network.frequency, network.port_names)
                network = terminate_ports(network, loads)
            elif step['kind'] == 'cascade':
                other = fixture(step['network'])
                left, right = (other, network) if step['side'] == 'left' else (network, other)
                network = cascade_networks(left, right, port_names=step['port_names'])
            else:
                network = deembed_network(network, left=fixture(step['left']), right=fixture(step['right']),
                                          port_names=step['port_names'])
        if (network.port_names != self.port_names or not np.array_equal(network.z_ref, self.z_ref)
                or not np.array_equal(network.frequency, self.frequency)):
            raise ValueError('transformation changed the documented final port metadata')
        return NetworkTransformResult(network, original, self.dumps(), extraction,
                                      tuple(fixture_networks), tuple(fixture_extractions))
