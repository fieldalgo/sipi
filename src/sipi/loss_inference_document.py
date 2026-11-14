# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict saved scalar shunt-loss inference requests in explicit SI units."""
import json

from .circuit_document import _json_copy
from .document import _keys, _unique_object
from .loss_inference import _inference_inputs, infer_shunt_loss

__all__ = ['ShuntLossInferenceDocument']


class ShuntLossInferenceDocument:
    """Normalize without root or field solves; retain candidate acceptance at execution."""
    def __init__(self, frequency, *, alpha, R, L, C, max_error_np_per_m):
        f, a, r, l, c, limit = _inference_inputs(frequency, alpha, R, L, C, max_error_np_per_m)
        self._data = dict(schema='sipi.shunt-loss-inference/1', frequency_hz=f.tolist(),
            alpha_np_per_m=a.tolist(), R_ohm_per_m=r.tolist(), L_h_per_m=l.tolist(),
            C_f_per_m=c.tolist(), max_error_np_per_m=limit)

    @classmethod
    def from_dict(cls, data):
        data = _json_copy(data)
        _keys(data, ('schema', 'frequency_hz', 'alpha_np_per_m', 'R_ohm_per_m',
                    'L_h_per_m', 'C_f_per_m', 'max_error_np_per_m'), where='shunt loss inference')
        if data['schema'] != 'sipi.shunt-loss-inference/1':
            raise ValueError('unsupported shunt-loss-inference schema')
        return cls(data['frequency_hz'], alpha=data['alpha_np_per_m'], R=data['R_ohm_per_m'],
                   L=data['L_h_per_m'], C=data['C_f_per_m'], max_error_np_per_m=data['max_error_np_per_m'])

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
        return infer_shunt_loss(data['frequency_hz'], alpha=data['alpha_np_per_m'],
            R=data['R_ohm_per_m'], L=data['L_h_per_m'], C=data['C_f_per_m'],
            max_error_np_per_m=data['max_error_np_per_m'])
