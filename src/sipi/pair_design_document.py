# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict saved two-parameter symmetric-pair impedance goals."""
import json

from .document import _keys, _unique_object
from .sampling import _copy, _integer, _scalar
from .study import ImpedanceStudyDocument, _parameters, _TEMPLATES
from .impedance_material import _material_input, _models
from .pair_design import seek_pair_impedances

__all__ = ['PairImpedanceDesignDocument']

_SCHEMA = 'sipi.pair-impedance-design/1'
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
    rules. No parameter-dependent material mapping is serialized.
    The attempt budget applies to solving; unmeshed geometry preflight is
    outside that count and does not run an impedance study.
    """
    def __init__(self, template, parameters, *, variables, bounds, targets,
                 tolerances, initial=None, max_evaluations=64, mesh=None,
                 fixed_pitch_m=None, fixed_plane_spacing_m=None,
                 frequency=None, materials=None):
        if (not isinstance(variables, (tuple, list)) or len(variables) != 2
                or not isinstance(bounds, (tuple, list)) or len(bounds) != 2):
            raise ValueError('variables and bounds must each contain two entries')
        self._data = self._validate(dict(schema=_SCHEMA, template=template,
            parameters=parameters, variables=[dict(name=name, bounds=bound)
                                              for name, bound in zip(variables, bounds)],
            targets_ohm=targets, tolerances_ohm=tolerances, initial=initial,
            max_evaluations=max_evaluations, mesh={} if mesh is None else mesh,
            fixed_pitch_m=fixed_pitch_m, fixed_plane_spacing_m=fixed_plane_spacing_m,
            material_evaluation=_material_input(frequency, materials)))

    @staticmethod
    def _study(data):
        evaluation = data['material_evaluation']
        kwargs = {} if evaluation is None else dict(
            frequency=evaluation['frequency_hz'], materials=_models(evaluation))
        return ImpedanceStudyDocument(data['template'], data['parameters'], quantity='z_diff',
            sampling=dict(kind='corners', variables=[dict(name=v['name'],
                lower=v['bounds'][0], upper=v['bounds'][1]) for v in data['variables']]),
            mesh=data['mesh'], fixed_pitch_m=data['fixed_pitch_m'],
            fixed_plane_spacing_m=data['fixed_plane_spacing_m'], **kwargs)

    @classmethod
    def _validate(cls, data):
        data = _copy(data)
        _keys(data, _FIELDS, where='pair impedance design')
        if data['schema'] != _SCHEMA:
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
        if evaluation is not None:
            _keys(evaluation, ('frequency_hz', 'materials'), where='material evaluation')
            if not isinstance(evaluation['materials'], dict):
                raise ValueError('materials must be an object')
        study = cls._study(data).to_dict()
        for key in ('parameters', 'mesh', 'fixed_pitch_m'):
            data[key] = study[key]
        data['fixed_plane_spacing_m'] = study.get('fixed_plane_spacing_m')
        data['material_evaluation'] = study.get('material_evaluation')
        if initial is None:
            initial = [v['bounds'][0]+(v['bounds'][1]-v['bounds'][0])/2 for v in variables]
        _TEMPLATES[data['template']](**_parameters(study, initial))
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
        return seek_pair_impedances(factory, [v['bounds'] for v in data['variables']],
            [data['targets_ohm'][q] for q in _QUANTITIES],
            tolerances=[data['tolerances_ohm'][q] for q in _QUANTITIES],
            initial=data['initial'], max_evaluations=data['max_evaluations'], mesh=data['mesh'], **kwargs)
