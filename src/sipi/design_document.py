# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict, portable inputs for bounded single-parameter impedance design."""
from __future__ import annotations

import json

from .design import seek_impedance
from .document import _keys, _unique_object
from .study import ImpedanceStudyDocument, _copy, _integer, _parameters, _scalar, _TEMPLATES

__all__ = ['ImpedanceDesignDocument']

_SCHEMA = 'sipi.impedance-design/1'
_FIELDS = ('schema', 'template', 'parameters', 'variable', 'bounds', 'target_ohm',
           'quantity', 'tolerance_ohm', 'max_evaluations', 'mesh', 'fixed_pitch_m',
           'fixed_plane_spacing_m')


class ImpedanceDesignDocument:
    """Saved goal, positive search interval and nominally resolved mesh settings.

    Loading validates geometry but never meshes or solves. solve() uses the
    existing bounded design routine and returns its ImpedanceDesign unchanged.
    Save this input JSON separately from the result's cross-section document.
    """
    def __init__(self, template, parameters, *, variable, bounds, target, quantity='z0',
                 tolerance=.1, max_evaluations=40, mesh=None, fixed_pitch_m=None,
                 fixed_plane_spacing_m=None):
        self._data = self._validate(dict(schema=_SCHEMA, template=template, parameters=parameters,
            variable=variable, bounds=bounds, target_ohm=target, quantity=quantity,
            tolerance_ohm=tolerance, max_evaluations=max_evaluations,
            mesh={} if mesh is None else mesh, fixed_pitch_m=fixed_pitch_m,
            fixed_plane_spacing_m=fixed_plane_spacing_m))

    @staticmethod
    def _study(data):
        return ImpedanceStudyDocument(data['template'], data['parameters'], quantity=data['quantity'],
            sampling=dict(kind='sweep', count=2, variables=[dict(name=data['variable'],
                          lower=data['bounds'][0], upper=data['bounds'][1])]), mesh=data['mesh'],
            fixed_pitch_m=data['fixed_pitch_m'], fixed_plane_spacing_m=data['fixed_plane_spacing_m'])

    @classmethod
    def _validate(cls, data):
        data = _copy(data)
        _keys(data, _FIELDS, where='impedance design')
        if data['schema'] != _SCHEMA:
            raise ValueError('unsupported impedance-design schema')
        if not isinstance(data['bounds'], list) or len(data['bounds']) != 2:
            raise ValueError('bounds must contain two positive numbers')
        data['bounds'] = [_scalar(x, positive=True) for x in data['bounds']]
        if data['bounds'][0] >= data['bounds'][1]:
            raise ValueError('lower bound must be below upper bound')
        data['target_ohm'] = _scalar(data['target_ohm'], positive=True)
        data['tolerance_ohm'] = _scalar(data['tolerance_ohm'], positive=True)
        data['max_evaluations'] = _integer(data['max_evaluations'], 3, 10000)
        study = cls._study(data).to_dict()
        for key in ('parameters', 'mesh', 'quantity', 'fixed_pitch_m'):
            data[key] = study[key]
        data['fixed_plane_spacing_m'] = study.get('fixed_plane_spacing_m')
        return data

    @classmethod
    def from_dict(cls, data):
        out = cls.__new__(cls)
        out._data = cls._validate(data)
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

    def solve(self):
        """Evaluate the saved bracket and verify the candidate on a refined mesh.

        GoalSeekError and its completed evaluation history propagate unchanged.
        This method performs no file IO and no dynamic code evaluation.
        """
        data = self.to_dict()
        study = self._study(data).to_dict()
        def factory(value):
            return _TEMPLATES[data['template']](**_parameters(study, [value]))
        return seek_impedance(factory, data['bounds'], data['target_ohm'], quantity=data['quantity'],
            tolerance=data['tolerance_ohm'], max_evaluations=data['max_evaluations'], mesh=data['mesh'])
