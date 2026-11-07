# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict saved 1D conductivity-profile inputs, independent of transport/UI."""
from __future__ import annotations

import json

import numpy as np

from .circuit_document import _json_copy
from .conductivity_profile import (GaussianConductivityProfile, ConductivityProfileResult,
                                   _cutoff, _samples)
from .document import _keys, _unique_object
from .network import _frequencies
from .sampling import _integer

__all__ = ['ConductivityProfileDocument']


class ConductivityProfileDocument:
    """sipi.conductivity-profile/1, preserving model and exterior-port cutoff.

    Parsing validates every scale without an ODE solve. Analysis counts one
    evaluation per frequency before calling the bounded constitutive kernel.
    This is not a transmission-line conductor record or a roughness multiplier.
    """
    def __init__(self, profile, frequency, *, cutoff_rms=8.0):
        if not isinstance(profile, GaussianConductivityProfile):
            raise TypeError('profile must be a GaussianConductivityProfile')
        self._assign(dict(schema='sipi.conductivity-profile/1',
            model=dict(kind='gaussian-conductivity', conductivity_s_per_m=profile.conductivity,
                       rms_m=profile.rms_m),
            frequency_hz=_frequencies(frequency).tolist(), cutoff_rms=cutoff_rms))

    def _assign(self, data):
        try:
            data = _json_copy(data)
        except ValueError as exc:
            raise ValueError('profile input must contain only finite JSON values') from exc
        _keys(data, ('schema', 'model', 'frequency_hz', 'cutoff_rms'), where='conductivity profile')
        if data['schema'] != 'sipi.conductivity-profile/1':
            raise ValueError('unsupported conductivity-profile schema')
        model = data['model']
        _keys(model, ('kind', 'conductivity_s_per_m', 'rms_m'), where='profile model')
        if model['kind'] != 'gaussian-conductivity':
            raise ValueError('profile model must explicitly select gaussian-conductivity')
        profile = GaussianConductivityProfile(conductivity=model['conductivity_s_per_m'],
                                               rms_m=model['rms_m'])
        cutoff = _cutoff(data['cutoff_rms'])
        f, _, _, _, _ = _samples(profile, data['frequency_hz'], cutoff)
        self._profile = profile
        self._data = dict(schema=data['schema'], model=dict(kind=model['kind'],
            conductivity_s_per_m=profile.conductivity, rms_m=profile.rms_m),
            frequency_hz=f.tolist(), cutoff_rms=cutoff)

    @property
    def profile(self):
        return self._profile

    @property
    def frequency(self):
        return np.array(self._data['frequency_hz'], dtype=float)

    @property
    def cutoff_rms(self):
        return self._data['cutoff_rms']

    @property
    def sample_count(self):
        return len(self._data['frequency_hz'])

    @classmethod
    def from_dict(cls, data):
        out = cls.__new__(cls)
        out._assign(data)
        return out

    @classmethod
    def loads(cls, text):
        def reject(value):
            raise ValueError(f'nonfinite JSON number: {value}')
        return cls.from_dict(json.loads(text, object_pairs_hook=_unique_object,
                                       parse_constant=reject))

    def dumps(self):
        return json.dumps(self._data, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)

    def to_dict(self):
        return json.loads(self.dumps())

    def analyze(self, *, max_evaluations=128):
        budget = _integer(max_evaluations, 2, 10000)
        if self.sample_count > budget:
            raise ValueError('profile frequency count exceeds max_evaluations before integration')
        result = self.profile.analyze(self.frequency, cutoff_rms=self.cutoff_rms)
        if (not isinstance(result, ConductivityProfileResult) or result.profile != self.profile
                or not np.array_equal(result.frequency, self.frequency)
                or result.cutoff_rms != self.cutoff_rms):
            raise ValueError('profile solve changed the saved model/frequency/reference-plane contract')
        return result
