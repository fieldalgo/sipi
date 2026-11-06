# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Versioned, explicit assembly of line networks and ideal junctions."""
from __future__ import annotations

from dataclasses import dataclass
import json

import numpy as np

from .circuit_document import _json_copy, _network_input
from .connection import _connection_layout, connect_networks, ideal_junction
from .document import _keys, _unique_object
from .network import LineNetwork, _references

__all__ = ['NetworkAssemblyDocument', 'NetworkAssemblyResult']
_KINDS = ('rlgc', 'touchstone', 'transmission-line', 'volume-line', 'lumped-network')


def _component(data):
    if not isinstance(data, dict):
        raise ValueError('assembly component must be an object')
    if data.get('kind') == 'ideal-junction':
        _keys(data, ('kind', 'frequency_hz', 'port_names', 'reference_ohms'), where='ideal junction')
        if not isinstance(data['port_names'], list):
            raise ValueError('junction port_names must be an explicit array')
        source = ideal_junction(data['frequency_hz'], port_names=data['port_names'],
                                z_ref=data['reference_ohms'])
        canonical = dict(kind='ideal-junction', frequency_hz=source.frequency.tolist(),
                         port_names=list(source.port_names), reference_ohms=source.z_ref.tolist())
        return source, canonical, source.frequency, source.port_names, source.z_ref
    if data.get('kind') not in _KINDS:
        raise ValueError('assembly components require base networks or ideal-junction; nesting is unsupported')
    source, canonical, frequency, ports = _network_input(data)
    references = (source.z_ref if isinstance(source, LineNetwork) else
                  _references(canonical['document']['reference_ohms'], len(ports)))
    return source, canonical, frequency, ports, references


@dataclass(frozen=True)
class NetworkAssemblyResult:
    """Assembled S, exact input and component networks/extractions in input order."""
    network: LineNetwork
    input_json: str
    source_networks: tuple[LineNetwork, ...]
    extractions: tuple[object | None, ...]


class NetworkAssemblyDocument:
    """sipi.network-assembly/1: a starting component and 1..32 ordered joins.

    Each join adds a new component through explicit current/new port pairs.
    Parsing validates all metadata without meshing. No nested assemblies,
    transformations, file/network I/O or expressions. Each geometry component
    is extracted once per analysis; existing model validity gates are retained.
    """
    def __init__(self, network, *, connections):
        self._assign(dict(schema='sipi.network-assembly/1', network=network,
                          connections=connections))

    def _assign(self, data):
        data = _json_copy(data)
        _keys(data, ('schema', 'network', 'connections'), where='network assembly')
        if data['schema'] != 'sipi.network-assembly/1':
            raise ValueError('unsupported network-assembly schema')
        _, source, frequency, ports, references = _component(data['network'])
        steps = data['connections']
        if not isinstance(steps, list) or not 1 <= len(steps) <= 32:
            raise ValueError('connections must contain 1..32 joins')
        connections = []
        for step in steps:
            _keys(step, ('network', 'ports'), ('port_names',), where='assembly connection')
            if 'port_names' in step and not isinstance(step['port_names'], list):
                raise ValueError('output port_names must be an explicit array')
            _, canonical, other_f, other_ports, other_refs = _component(step['network'])
            if not np.array_equal(frequency, other_f):
                raise ValueError('assembly components must have identical frequency samples')
            _, _, ports, references = _connection_layout(ports, references, other_ports,
                other_refs, step['ports'], step.get('port_names'))
            connections.append(dict(network=canonical, ports=step['ports'], port_names=list(ports)))
        self._data = dict(schema=data['schema'], network=source, connections=connections)
        self._frequency, self._references = np.array(frequency, copy=True), np.array(references, copy=True)
        self._port_names = ports

    @property
    def frequency(self):
        out = self._frequency.copy(); out.setflags(write=False)
        return out

    @property
    def z_ref(self):
        out = self._references.copy(); out.setflags(write=False)
        return out

    @property
    def port_names(self):
        return self._port_names

    @classmethod
    def from_dict(cls, data):
        out = cls.__new__(cls); out._assign(data)
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
        networks, extractions = [], []
        def extract(component):
            source, _, frequency, ports, references = _component(component)
            extraction = None if isinstance(source, LineNetwork) else source.analyze()
            network = source if extraction is None else extraction.network
            if (network.port_names != ports or not np.array_equal(network.frequency, frequency)
                    or not np.array_equal(network.z_ref, references)):
                raise ValueError('extraction changed documented frequency, port order or references')
            networks.append(network); extractions.append(extraction)
            return network
        network = extract(data['network'])
        for step in data['connections']:
            network = connect_networks(network, extract(step['network']), step['ports'],
                                       port_names=step['port_names'])
        return NetworkAssemblyResult(network, self.dumps(), tuple(networks), tuple(extractions))
