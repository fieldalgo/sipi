# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit sampled S-magnitude limits; no interpolation or continuous-band claim."""
from __future__ import annotations

from dataclasses import dataclass
import json
import numpy as np

from .circuit_document import _json_copy, _network_input
from .document import _keys, _unique_object
from .network import LineNetwork, _real, _references

__all__ = ['db_to_magnitude', 'assess_band', 'BandCheck', 'BandAssessment', 'NetworkBandDocument']


def db_to_magnitude(value):
    """Convert finite amplitude dB to a representable positive linear |S| limit."""
    raw = _real('amplitude dB', value)
    if raw.ndim:
        raise ValueError('amplitude dB must be scalar')
    with np.errstate(over='ignore', under='ignore'):
        result = float(10.**(raw/20))
    if not np.isfinite(result) or result <= 0:
        raise ValueError('amplitude dB limit is not representable as a positive magnitude')
    return result


def _limits(limits, frequency, ports):
    limits = _json_copy(limits)
    if not isinstance(limits, list) or not 1 <= len(limits) <= 64:
        raise ValueError('limits must contain 1..64 explicit constraints')
    names = set()
    for limit in limits:
        _keys(limit, ('name', 'input_port', 'output_port', 'frequency_hz', 'minimum', 'maximum'),
              where='band limit')
        name = limit['name']
        if (not isinstance(name, str) or not name.strip() or '\n' in name or '\r' in name or name in names):
            raise ValueError('limit names must be unique nonempty single-line strings')
        names.add(name)
        if any(not isinstance(limit[key], str) or limit[key] not in ports
               for key in ('input_port', 'output_port')):
            raise ValueError('band limit must name existing input/output ports')
        band = _real('frequency_hz band', limit['frequency_hz'])
        if band.shape != (2,) or band[0] >= band[1] or not all(x in frequency for x in band):
            raise ValueError('band requires two increasing endpoints present exactly in the frequency grid')
        limit['frequency_hz'] = band.tolist()
        for key in ('minimum', 'maximum'):
            if limit[key] is not None:
                value = _real(key+' magnitude', limit[key])
                if value.ndim or value < 0:
                    raise ValueError('magnitude limits must be nonnegative finite scalars or null')
                limit[key] = float(value)
        low, high = limit['minimum'], limit['maximum']
        if low is None and high is None or low is not None and high is not None and low > high:
            raise ValueError('at least one limit is required, with minimum <= maximum')
    return limits


@dataclass(frozen=True)
class BandCheck:
    name: str
    input_port: str
    output_port: str
    frequency_hz: tuple[float, ...]
    magnitude: tuple[float, ...]
    margin: tuple[float, ...]
    minimum: float | None
    maximum: float | None

    @property
    def passed(self):
        return all(x >= 0 for x in self.margin)

    @property
    def worst_index(self):
        return int(np.argmin(self.margin))

    def to_dict(self):
        i = self.worst_index
        return dict(name=self.name, input_port=self.input_port, output_port=self.output_port,
            frequency_hz=list(self.frequency_hz), magnitude=list(self.magnitude), margin=list(self.margin),
            minimum=self.minimum, maximum=self.maximum, passed=self.passed,
            failed_indices=[j for j, x in enumerate(self.margin) if x < 0],
            worst_index=i, worst_frequency_hz=self.frequency_hz[i], minimum_margin=self.margin[i])


@dataclass(frozen=True)
class BandAssessment:
    network: LineNetwork
    checks: tuple[BandCheck, ...]
    input_json: str | None = None
    extraction: object | None = None

    @property
    def passed(self):
        return all(check.passed for check in self.checks)

    @property
    def minimum_margin(self):
        return min(min(check.margin) for check in self.checks)

    def to_dict(self):
        return dict(passed=self.passed, basis=self.network.basis, port_names=list(self.network.port_names),
            reference_ohms=self.network.z_ref.tolist(), minimum_margin=self.minimum_margin,
            checks=[check.to_dict() for check in self.checks], coverage='frequency-samples-only')


def assess_band(network, limits):
    """Check inclusive linear |S[output,input]| limits on stored frequency samples.

    No passivity, causality, uncertainty, interpolation or global extrema are
    inferred. Other ports use the network's real power-wave reference loads.
    Zero transmission/reflection is represented exactly without dB infinities.
    """
    if not isinstance(network, LineNetwork):
        raise ValueError('assessment requires a LineNetwork')
    canonical = _limits(limits, network.frequency, network.port_names)
    checks = []
    for limit in canonical:
        low, high = limit['frequency_hz']
        selected = (network.frequency >= low) & (network.frequency <= high)
        output, input_ = (network.port_names.index(limit[key]) for key in ('output_port', 'input_port'))
        with np.errstate(over='ignore', invalid='ignore'):
            values = np.abs(network.s[selected, output, input_])
        if not np.all(np.isfinite(values)):
            raise ValueError('network magnitude is not numerically representable')
        margins = []
        if limit['minimum'] is not None:
            margins.append(values-limit['minimum'])
        if limit['maximum'] is not None:
            margins.append(limit['maximum']-values)
        margin = np.minimum.reduce(margins)
        checks.append(BandCheck(limit['name'], limit['input_port'], limit['output_port'],
            tuple(map(float, network.frequency[selected])), tuple(map(float, values)),
            tuple(map(float, margin)), limit['minimum'], limit['maximum']))
    return BandAssessment(network, tuple(checks))


def _metadata(data):
    source, canonical, frequency, ports = _network_input(data)
    references = (source.z_ref if hasattr(source, 'z_ref') else
                  _references(canonical['document']['reference_ohms'], len(ports)))
    return source, canonical, frequency, ports, references


class NetworkBandDocument:
    """sipi.network-band/1: saved source, explicit output basis and magnitude limits.

    Field-source normalization never meshes. RLGC, Touchstone and lumped source
    validators can perform small algebra. Existing model gates remain active.
    """
    def __init__(self, network, *, limits, basis='single-ended'):
        self._assign(dict(schema='sipi.network-band/1', network=network, limits=limits, basis=basis))

    def _assign(self, data):
        data = _json_copy(data)
        _keys(data, ('schema', 'network', 'limits', 'basis'), where='network band')
        if data['schema'] != 'sipi.network-band/1':
            raise ValueError('unsupported network-band schema')
        source, canonical, frequency, ports, refs = _metadata(data['network'])
        if data['basis'] == 'mixed-mode':
            if len(ports) != 4 or not np.all(refs == refs[0]):
                raise ValueError('mixed-mode requires four equal-reference single-ended ports')
            ports = ('d_near', 'd_far', 'c_near', 'c_far')
        elif data['basis'] != 'single-ended':
            raise ValueError('basis must be single-ended or mixed-mode')
        limits = _limits(data['limits'], frequency, ports)
        self._data = dict(schema=data['schema'], network=canonical, limits=limits, basis=data['basis'])

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

    def analyze(self):
        source, _, frequency, ports, refs = _metadata(self._data['network'])
        extraction = None if isinstance(source, LineNetwork) else source.analyze()
        network = source if extraction is None else extraction.network
        if (network.port_names != ports or not np.array_equal(network.frequency, frequency)
                or not np.array_equal(network.z_ref, refs) or network.basis != 'single-ended'):
            raise ValueError('network extraction changed the saved frequency/ports/references/basis')
        if self._data['basis'] == 'mixed-mode':
            network = network.mixed_mode()
        result = assess_band(network, self._data['limits'])
        return BandAssessment(network, result.checks, self.dumps(), extraction)
