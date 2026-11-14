# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict saved fixed-radius surface-impedance fitting requests."""
import json

from .circuit_document import _json_copy
from .document import _keys, _unique_object
from .roughness_fit import _fit_inputs, fit_huray

__all__ = ['HurayFitDocument']


class HurayFitDocument:
    """Field-free normalization; identifiability and fitting occur at analyze.

    A completed fit retains its own sampled accepted flag. Numerical/input
    failures propagate as errors and never fabricate a candidate.
    """
    def __init__(self, frequency, *, resistance, reactance, radii_m, conductivity,
                 max_error_ratio, relative_permeability=1., weights=None):
        f, real, imag, radii, sigma, mu_r, limit, w, _, _ = _fit_inputs(
            frequency, resistance, reactance, radii_m, conductivity,
            relative_permeability, max_error_ratio, weights)
        self._data = dict(schema='sipi.roughness-fit/1', frequency_hz=f.tolist(),
            resistance_ohms_per_square=real.tolist(), reactance_ohms_per_square=imag.tolist(),
            radii_m=radii.tolist(), conductivity=sigma, relative_permeability=mu_r,
            weights=w.tolist(), max_error_ratio=limit)

    @classmethod
    def from_dict(cls, data):
        data = _json_copy(data)
        _keys(data, ('schema', 'frequency_hz', 'resistance_ohms_per_square', 'reactance_ohms_per_square',
                    'radii_m', 'conductivity', 'relative_permeability', 'weights', 'max_error_ratio'),
              where='roughness fit')
        if data['schema'] != 'sipi.roughness-fit/1':
            raise ValueError('unsupported roughness-fit schema')
        if data['weights'] is None:
            raise ValueError('saved weights must explicitly match every frequency')
        return cls(data['frequency_hz'], resistance=data['resistance_ohms_per_square'],
            reactance=data['reactance_ohms_per_square'], radii_m=data['radii_m'],
            conductivity=data['conductivity'], relative_permeability=data['relative_permeability'],
            weights=data['weights'], max_error_ratio=data['max_error_ratio'])

    @classmethod
    def loads(cls, text):
        def reject(value): raise ValueError(f'nonfinite JSON number: {value}')
        return cls.from_dict(json.loads(text, object_pairs_hook=_unique_object, parse_constant=reject))

    def dumps(self):
        return json.dumps(self._data, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)

    def to_dict(self):
        return json.loads(self.dumps())

    def analyze(self):
        data = self.to_dict()
        return fit_huray(data['frequency_hz'], resistance=data['resistance_ohms_per_square'],
            reactance=data['reactance_ohms_per_square'], radii_m=data['radii_m'],
            conductivity=data['conductivity'], relative_permeability=data['relative_permeability'],
            max_error_ratio=data['max_error_ratio'], weights=data['weights'])
