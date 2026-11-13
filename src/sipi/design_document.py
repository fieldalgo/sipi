# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict, portable inputs for bounded single-parameter impedance design."""
from __future__ import annotations

import json

from .design import seek_impedance
from .document import _keys, _unique_object
from .study import ImpedanceStudyDocument, _copy, _integer, _parameters, _scalar, _TEMPLATES
from .impedance_material import _material_input, _models, _sample_material

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
    Version 2 preserves fixed-frequency material overrides; its named variable
    is geometry-only and its target retains the real quasi-static definition.
    Version 3 binds the single search variable to a numeric material-model leaf.
    Bounds remain positive, including for parameters that otherwise allow zero
    or signed values in a study. No global or multi-variable optimum is implied.
    """
    def __init__(self, template, parameters, *, variable, bounds, target, quantity='z0',
                 tolerance=.1, max_evaluations=40, mesh=None, fixed_pitch_m=None,
                 fixed_plane_spacing_m=None, frequency=None, materials=None, material_variables=None,
                 search_tolerance=None):
        data = dict(schema=_SCHEMA, template=template, parameters=parameters,
            variable=variable, bounds=bounds, target_ohm=target, quantity=quantity,
            tolerance_ohm=tolerance, max_evaluations=max_evaluations,
            mesh={} if mesh is None else mesh, fixed_pitch_m=fixed_pitch_m,
            fixed_plane_spacing_m=fixed_plane_spacing_m)
        evaluation = _material_input(frequency, materials)
        if evaluation is not None:
            data.update(schema='sipi.impedance-design/2', material_evaluation=evaluation)
        if material_variables is not None:
            data.update(schema='sipi.impedance-design/3', material_evaluation=evaluation,
                        material_variables=material_variables)
        if search_tolerance is not None:
            data.update(schema='sipi.impedance-design/4', search_tolerance_ohm=search_tolerance)
        self._data = self._validate(data)

    @staticmethod
    def _study(data):
        evaluation = data.get('material_evaluation')
        kwargs = ({} if evaluation is None else
                  dict(frequency=evaluation['frequency_hz'], materials=_models(evaluation)))
        if 'material_variables' in data:
            kwargs['material_variables'] = data['material_variables']
        return ImpedanceStudyDocument(data['template'], data['parameters'], quantity=data['quantity'],
            sampling=dict(kind='sweep', count=2, variables=[dict(name=data['variable'],
                          lower=data['bounds'][0], upper=data['bounds'][1])]), mesh=data['mesh'],
            fixed_pitch_m=data['fixed_pitch_m'], fixed_plane_spacing_m=data['fixed_plane_spacing_m'], **kwargs)

    @classmethod
    def _validate(cls, data):
        data = _copy(data)
        version4 = isinstance(data, dict) and data.get('schema') == 'sipi.impedance-design/4'
        material_version = isinstance(data, dict) and (data.get('schema') in ('sipi.impedance-design/2', 'sipi.impedance-design/3')
                            or version4 and ('material_evaluation' in data or 'material_variables' in data))
        version3 = isinstance(data, dict) and (data.get('schema') == 'sipi.impedance-design/3'
                    or version4 and 'material_variables' in data)
        fields = (*_FIELDS, 'material_evaluation') if material_version else _FIELDS
        if version3:
            fields = (*fields, 'material_variables')
        if version4:
            fields = (*fields, 'search_tolerance_ohm')
        _keys(data, fields, where='impedance design')
        if data['schema'] not in (_SCHEMA, 'sipi.impedance-design/2', 'sipi.impedance-design/3', 'sipi.impedance-design/4'):
            raise ValueError('unsupported impedance-design schema')
        if material_version:
            _keys(data['material_evaluation'], ('frequency_hz', 'materials'), where='material evaluation')
            if not isinstance(data['material_evaluation']['materials'], dict):
                raise ValueError('materials must be an object')
        if not isinstance(data['bounds'], list) or len(data['bounds']) != 2:
            raise ValueError('bounds must contain two positive numbers')
        data['bounds'] = [_scalar(x, positive=True) for x in data['bounds']]
        if data['bounds'][0] >= data['bounds'][1]:
            raise ValueError('lower bound must be below upper bound')
        data['target_ohm'] = _scalar(data['target_ohm'], positive=True)
        data['tolerance_ohm'] = _scalar(data['tolerance_ohm'], positive=True)
        if version4:
            data['search_tolerance_ohm'] = _scalar(data['search_tolerance_ohm'], positive=True)
            if data['search_tolerance_ohm'] > data['tolerance_ohm']:
                raise ValueError('search_tolerance must not exceed tolerance')
        data['max_evaluations'] = _integer(data['max_evaluations'], 3, 10000)
        if version3:
            bindings = data['material_variables']
            if not isinstance(data['variable'], str) or not isinstance(bindings, dict) or set(bindings) != {data['variable']}:
                raise ValueError('material design needs exactly one binding matching variable')
        study = cls._study(data).to_dict()
        for key in ('parameters', 'mesh', 'quantity', 'fixed_pitch_m'):
            data[key] = study[key]
        data['fixed_plane_spacing_m'] = study.get('fixed_plane_spacing_m')
        if material_version:
            data['material_evaluation'] = study['material_evaluation']
        if version3:
            data['material_variables'] = study['material_variables']
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
        evaluation = data.get('material_evaluation')
        kwargs = ({} if evaluation is None else
                  dict(frequency=evaluation['frequency_hz'], materials=_models(evaluation)))
        if 'material_variables' in data:
            kwargs = dict(frequency=evaluation['frequency_hz'],
                          material_factory=lambda value: _models(_sample_material(study, [value])))
        if 'search_tolerance_ohm' in data:
            kwargs['search_tolerance'] = data['search_tolerance_ohm']
        return seek_impedance(factory, data['bounds'], data['target_ohm'], quantity=data['quantity'],
            tolerance=data['tolerance_ohm'], max_evaluations=data['max_evaluations'], mesh=data['mesh'], **kwargs)
