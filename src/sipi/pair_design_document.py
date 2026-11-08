# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict saved two-parameter symmetric-pair impedance goals."""
import json

from .document import _keys, _unique_object
from .sampling import _copy, _integer, _scalar
from .study import ImpedanceStudyDocument, _parameters, _TEMPLATES
from .impedance_material import (_material_input, _models, _sample_material,
                                 _validate_material_input)
from .pair_design import seek_pair_impedances

__all__ = ['PairImpedanceDesignDocument']

_SCHEMA = 'sipi.pair-impedance-design/1'
_MATERIAL_SCHEMA = 'sipi.pair-impedance-design/2'
_QUANTITIES = ('z_diff', 'z_common')
_FIELDS = ('schema', 'template', 'parameters', 'variables', 'targets_ohm',
           'tolerances_ohm', 'initial', 'max_evaluations', 'mesh',
           'fixed_pitch_m', 'fixed_plane_spacing_m', 'material_evaluation')


class PairImpedanceDesignDocument:
    """Named template variables and two explicit modal targets, without code IO.

    variables and bounds contain two ordered entries. targets/tolerances are
    objects with exactly z_diff/z_common keys, in ohms. Parsing validates the
    nominal, four corner and initial geometries without meshing or optimizing.
    The corner check is not a worst-case or statistical assessment. Fixed pitch,
    fixed plane spacing and fixed material overrides reuse the existing study
    rules. Version 2 adds explicit numeric material-leaf bindings, using the
    same two ordered variables for geometry and material. Preflight also
    validates the sampled initial material, without assuming valid corners
    establish validity throughout the domain. Callbacks are not serialized.
    The attempt budget applies to solving; unmeshed geometry preflight is
    outside that count and does not run an impedance study.
    """
    def __init__(self, template, parameters, *, variables, bounds, targets,
                 tolerances, initial=None, max_evaluations=64, mesh=None,
                 fixed_pitch_m=None, fixed_plane_spacing_m=None,
                 frequency=None, materials=None, material_variables=None):
        if (not isinstance(variables, (tuple, list)) or len(variables) != 2
                or not isinstance(bounds, (tuple, list)) or len(bounds) != 2):
            raise ValueError('variables and bounds must each contain two entries')
        data = dict(schema=_SCHEMA, template=template,
            parameters=parameters, variables=[dict(name=name, bounds=bound)
                                              for name, bound in zip(variables, bounds)],
            targets_ohm=targets, tolerances_ohm=tolerances, initial=initial,
            max_evaluations=max_evaluations, mesh={} if mesh is None else mesh,
            fixed_pitch_m=fixed_pitch_m, fixed_plane_spacing_m=fixed_plane_spacing_m,
            material_evaluation=_material_input(frequency, materials))
        if material_variables is not None:
            data.update(schema=_MATERIAL_SCHEMA, material_variables=material_variables)
        self._data = self._validate(data)

    @staticmethod
    def _study(data):
        evaluation = data['material_evaluation']
        kwargs = {} if evaluation is None else dict(
            frequency=evaluation['frequency_hz'], materials=_models(evaluation))
        if 'material_variables' in data:
            kwargs['material_variables'] = data['material_variables']
        return ImpedanceStudyDocument(data['template'], data['parameters'], quantity='z_diff',
            sampling=dict(kind='corners', variables=[dict(name=v['name'],
                lower=v['bounds'][0], upper=v['bounds'][1]) for v in data['variables']]),
            mesh=data['mesh'], fixed_pitch_m=data['fixed_pitch_m'],
            fixed_plane_spacing_m=data['fixed_plane_spacing_m'], **kwargs)

    @classmethod
    def _validate(cls, data):
        data = _copy(data)
        version2 = isinstance(data, dict) and data.get('schema') == _MATERIAL_SCHEMA
        _keys(data, (*_FIELDS, 'material_variables') if version2 else _FIELDS,
              where='pair impedance design')
        if data['schema'] not in (_SCHEMA, _MATERIAL_SCHEMA):
            raise ValueError('unsupported pair-impedance-design schema')
        variables = data['variables']
        if not isinstance(variables, list) or len(variables) != 2:
            raise ValueError('variables must contain two named bounds')
        names = []
        for variable in variables:
            _keys(variable, ('name', 'bounds'), where='pair design variable')
            name = variable['name']
            if not isinstance(name, str) or not name.strip() or name in names:
                raise ValueError('variable names must be distinct nonempty strings')
            names.append(name)
            bounds = variable['bounds']
            if not isinstance(bounds, list) or len(bounds) != 2:
                raise ValueError('each bound must contain two positive numbers')
            variable['bounds'] = [_scalar(x, positive=True) for x in bounds]
            if variable['bounds'][0] >= variable['bounds'][1]:
                raise ValueError('lower bound must be below upper bound')
        for name in ('targets_ohm', 'tolerances_ohm'):
            _keys(data[name], _QUANTITIES, where=name)
            data[name] = {q: _scalar(data[name][q], positive=True) for q in _QUANTITIES}
        data['max_evaluations'] = _integer(data['max_evaluations'], 2, 10000)
        initial = data['initial']
        if initial is not None:
            if not isinstance(initial, list) or len(initial) != 2:
                raise ValueError('initial must be null or two ordered parameters')
            initial = [_scalar(x, positive=True) for x in initial]
            for value, variable in zip(initial, variables):
                if not variable['bounds'][0] <= value <= variable['bounds'][1]:
                    raise ValueError('initial must lie inside each variable bound')
            data['initial'] = initial
        evaluation = data['material_evaluation']
        if version2 and evaluation is None:
            raise ValueError('material variables require a fixed frequency and material evaluation')
        if evaluation is not None:
            _keys(evaluation, ('frequency_hz', 'materials'), where='material evaluation')
            if not isinstance(evaluation['materials'], dict):
                raise ValueError('materials must be an object')
        study = cls._study(data).to_dict()
        for key in ('parameters', 'mesh', 'fixed_pitch_m'):
            data[key] = study[key]
        data['fixed_plane_spacing_m'] = study.get('fixed_plane_spacing_m')
        data['material_evaluation'] = study.get('material_evaluation')
        if version2:
            data['material_variables'] = study['material_variables']
        if initial is None:
            initial = [v['bounds'][0]+(v['bounds'][1]-v['bounds'][0])/2 for v in variables]
        section = _TEMPLATES[data['template']](**_parameters(study, initial))
        if evaluation is not None:
            _validate_material_input(_sample_material(study, initial), section, 'z_diff')
        return data

    @classmethod
    def from_dict(cls, data):
        out = cls.__new__(cls); out._data = cls._validate(data); return out

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
        data = self.to_dict(); study = self._study(data).to_dict()
        def factory(a, b):
            return _TEMPLATES[data['template']](**_parameters(study, [a, b]))
        evaluation = data['material_evaluation']
        kwargs = {} if evaluation is None else dict(
            frequency=evaluation['frequency_hz'], materials=_models(evaluation))
        if 'material_variables' in data:
            kwargs = dict(frequency=evaluation['frequency_hz'],
                material_factory=lambda a, b: _models(_sample_material(study, [a, b])))
        return seek_pair_impedances(factory, [v['bounds'] for v in data['variables']],
            [data['targets_ohm'][q] for q in _QUANTITIES],
            tolerances=[data['tolerances_ohm'][q] for q in _QUANTITIES],
            initial=data['initial'], max_evaluations=data['max_evaluations'], mesh=data['mesh'], **kwargs)
