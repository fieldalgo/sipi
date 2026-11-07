# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved periodic power-wave requests; no file/network I/O or implicit sources."""
from __future__ import annotations

from dataclasses import dataclass
import json

import numpy as np

from .band import _metadata
from .circuit_document import _json_copy
from .document import _keys, _unique_object
from .network import LineNetwork, _real
from .periodic import (PeriodicResponse, PeriodicImpulse, _grid, _time_grid,
                       periodic_response, periodic_impulse)
from .sampling import _integer

__all__ = ['PeriodicNetworkDocument', 'PeriodicNetworkResult']


def _ports(basis, ports, refs):
    if basis == 'single-ended':
        return ports
    if basis != 'mixed-mode':
        raise ValueError('basis must be single-ended or mixed-mode')
    if len(ports) != 4 or not np.all(refs == refs[0]):
        raise ValueError('mixed-mode requires four equal-reference single-ended ports')
    return ('d_near', 'd_far', 'c_near', 'c_far')


def _extract(data):
    """Extract once and enforce saved metadata before changing the wave basis."""
    source, _, frequency, ports, refs = _metadata(data['network'])
    extraction = None if isinstance(source, LineNetwork) else source.analyze()
    original = source if extraction is None else extraction.network
    if (original.port_names != ports or not np.array_equal(original.frequency, frequency)
            or not np.array_equal(original.z_ref, refs) or original.basis != 'single-ended'):
        raise ValueError('network extraction changed the saved frequency/ports/references/basis')
    network = original.mixed_mode() if data['basis'] == 'mixed-mode' else original
    return original, network, extraction


@dataclass(frozen=True)
class PeriodicNetworkResult:
    """Canonical input, retained source/extraction and explicit periodic outputs."""
    input_json: str
    source_network: LineNetwork
    network: LineNetwork
    extraction: object | None
    response: PeriodicResponse
    impulse: PeriodicImpulse | None


class PeriodicNetworkDocument:
    """sipi.periodic-network/1; all incident ports explicitly named in final basis.

    Parsing checks metadata and samples without field solves. Existing source
    validators may do small RLGC/lumped calculations. Analysis checks the time
    sample budget before field extraction or Fourier transforms.
    """
    def __init__(self, network, *, incident, basis='single-ended', include_impulse=False):
        self._assign(dict(schema='sipi.periodic-network/1', network=network,
            incident=incident, basis=basis, include_impulse=include_impulse))

    def _assign(self, data):
        data = _json_copy(data)
        _keys(data, ('schema', 'network', 'incident', 'basis', 'include_impulse'),
              where='periodic network')
        if data['schema'] != 'sipi.periodic-network/1':
            raise ValueError('unsupported periodic-network schema')
        if type(data['include_impulse']) is not bool:
            raise ValueError('include_impulse must be boolean')
        source, canonical, frequency, ports, refs = _metadata(data['network'])
        count, _, _, _ = _time_grid(frequency)
        if isinstance(source, LineNetwork):
            _grid(source)
        output_ports = _ports(data['basis'], ports, refs)
        incident = data['incident']
        if not isinstance(incident, dict) or set(incident) != set(output_ports):
            raise ValueError('incident must explicitly name every output-basis port exactly once')
        table = {}
        for name in output_ports:
            values = _real('incident '+name, incident[name])
            if values.shape != (count,):
                raise ValueError('each incident port needs 2*frequencies-1 real samples')
            table[name] = values.tolist()
        self._data = dict(schema=data['schema'], network=canonical, incident=table,
            basis=data['basis'], include_impulse=data['include_impulse'])
        self._sample_count = count

    @property
    def sample_count(self):
        return self._sample_count

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

    def analyze(self, *, max_evaluations=128):
        budget = _integer(max_evaluations, 2, 10000)
        if self.sample_count > budget:
            raise ValueError('periodic time sample count exceeds max_evaluations before field/FFT work')
        data = self._data
        original, network, extraction = _extract(data)
        incident = np.column_stack([data['incident'][name] for name in network.port_names])
        response = periodic_response(network, incident)
        impulse = periodic_impulse(network) if data['include_impulse'] else None
        return PeriodicNetworkResult(self.dumps(), original, network, extraction, response, impulse)
