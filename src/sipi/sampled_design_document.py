# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict named two-parameter goals at explicit frequency samples."""
from itertools import product
import json

import numpy as np

from .document import _keys, _unique_object
from .impedance_material import _material_input, _models, _sample_material, _validate_material_input
from .network import _frequencies
from .sampling import _copy, _integer, _numbers, _scalar
from .sampled_design import seek_sampled_impedance
from .study import ImpedanceStudyDocument, _TEMPLATES, _parameters

__all__ = ['SampledImpedanceDesignDocument']

_SCHEMA = 'sipi.sampled-impedance-design/1'
_FIELDS = ('schema', 'template', 'parameters', 'variables', 'quantity', 'frequencies_hz',
           'targets_ohm', 'tolerances_ohm', 'initial', 'max_evaluations', 'mesh',
           'fixed_pitch_m', 'fixed_plane_spacing_m', 'materials', 'material_variables')


class SampledImpedanceDesignDocument:
    """Saved finite-frequency goals with named geometry/material variables.

    Exactly two positive bounded variables; one scalar or symmetric-pair real
    quantity at 2..64 ordered nonnegative frequencies. Explicit material-leaf
    bindings reuse the study contract, without serializing executable callbacks.
    Loading validates nominal/corner/initial geometry and material at every
    frequency without meshing or optimizing. This preflight is outside the
    batch-attempt budget and does not prove validity of every interior point.
    """
    def __init__(self, template, parameters, *, variables, bounds, frequencies, targets,
                 tolerances, quantity='z0', initial=None, max_evaluations=64, mesh=None,
                 fixed_pitch_m=None, fixed_plane_spacing_m=None, materials=None,
                 material_variables=None):
        ranges = _numbers(bounds)
        if not isinstance(variables, (list, tuple)) or len(variables) != 2 or ranges.shape != (2, 2):
            raise ValueError('variables and bounds must each contain two entries')
        self._data = self._validate(dict(schema=_SCHEMA, template=template, parameters=parameters,
            variables=[dict(name=name, bounds=list(bound)) for name, bound in zip(variables, ranges)],
            quantity=quantity, frequencies_hz=_frequencies(frequencies).tolist(),
            targets_ohm=_numbers(targets).tolist(), tolerances_ohm=_numbers(tolerances).tolist(),
            initial=None if initial is None else _numbers(initial).tolist(), max_evaluations=max_evaluations,
            mesh={} if mesh is None else mesh, fixed_pitch_m=fixed_pitch_m,
            fixed_plane_spacing_m=fixed_plane_spacing_m,
            materials=_material_input(0., {} if materials is None else materials)['materials'],
            material_variables={} if material_variables is None else material_variables))

    @staticmethod
    def _study(data):
        kwargs = {}
        # Empty overrides must not shadow geometry's dielectric parameters.
        if data['materials'] or data['material_variables']:
            kwargs.update(frequency=data['frequencies_hz'][0], materials=_models(data))
        if data['material_variables']:
            kwargs['material_variables'] = data['material_variables']
        return ImpedanceStudyDocument(data['template'], data['parameters'],
            quantity='z0' if data['quantity'] == 'z0' else 'z_diff',
            sampling=dict(kind='corners', variables=[dict(name=v['name'],
                lower=v['bounds'][0], upper=v['bounds'][1]) for v in data['variables']]),
            mesh=data['mesh'], fixed_pitch_m=data['fixed_pitch_m'],
            fixed_plane_spacing_m=data['fixed_plane_spacing_m'], **kwargs)

    @staticmethod
    def _validate_frequencies(data, section, materials):
        for frequency in data['frequencies_hz']:
            _validate_material_input(dict(frequency_hz=frequency, materials=materials), section,
                                     'z0' if data['quantity'] == 'z0' else 'z_diff')

    @classmethod
    def _validate(cls, data):
        data = _copy(data)
        _keys(data, _FIELDS, where='sampled impedance design')
        if data['schema'] != _SCHEMA:
            raise ValueError('unsupported sampled-impedance-design schema')
        if not isinstance(data['quantity'], str) or data['quantity'] not in ('z0', 'z_diff', 'z_common'):
            raise ValueError('quantity must be z0, z_diff or z_common')
        frequencies = _frequencies(data['frequencies_hz'])
        if not 2 <= len(frequencies) <= 64:
            raise ValueError('frequencies must contain 2 to 64 ordered samples')
        data['frequencies_hz'] = frequencies.tolist()
        for name in ('targets_ohm', 'tolerances_ohm'):
            values = _numbers(data[name])
            if values.shape != frequencies.shape or np.any(values <= 0):
                raise ValueError(f'{name} needs one positive finite value per frequency')
            data[name] = values.tolist()
        variables = data['variables']
        if not isinstance(variables, list) or len(variables) != 2:
            raise ValueError('variables must contain two named bounds')
        names = []
        for variable in variables:
            _keys(variable, ('name', 'bounds'), where='sampled design variable')
            name = variable['name']
            if not isinstance(name, str) or not name.strip() or name in names:
                raise ValueError('variable names must be distinct nonempty strings')
            names.append(name)
            bounds = variable['bounds']
            if not isinstance(bounds, list) or len(bounds) != 2:
                raise ValueError('bounds must contain two positive numbers')
            variable['bounds'] = [_scalar(x, positive=True) for x in bounds]
            if variable['bounds'][0] >= variable['bounds'][1]:
                raise ValueError('lower bound must be below upper bound')
        data['max_evaluations'] = _integer(data['max_evaluations'], 2, 10000)
        initial = data['initial']
        if initial is not None:
            if not isinstance(initial, list) or len(initial) != 2:
                raise ValueError('initial must be null or two ordered parameters')
            initial = [_scalar(x, positive=True) for x in initial]
            if any(not v['bounds'][0] <= x <= v['bounds'][1] for x, v in zip(initial, variables)):
                raise ValueError('initial must lie inside each variable bound')
            data['initial'] = initial
        if not isinstance(data['materials'], dict) or not isinstance(data['material_variables'], dict):
            raise ValueError('materials and material_variables must be objects')
        study = cls._study(data).to_dict()
        for key in ('parameters', 'mesh', 'fixed_pitch_m'):
            data[key] = study[key]
        data['fixed_plane_spacing_m'] = study.get('fixed_plane_spacing_m')
        data['materials'] = study.get('material_evaluation', {}).get('materials', {})
        data['material_variables'] = study.get('material_variables', {})
        # Study preflight is reused. These additional checks reuse each point's
        # constructed geometry across every frequency, without field work.
        factory = _TEMPLATES[data['template']]
        cls._validate_frequencies(data, factory(**data['parameters']), data['materials'])
        if initial is None:
            initial = [v['bounds'][0]+(v['bounds'][1]-v['bounds'][0])/2 for v in variables]
        for point in [*product(*(v['bounds'] for v in variables)), initial]:
            section = factory(**_parameters(study, point))
            evaluation = _sample_material(study, point)
            materials = data['materials'] if evaluation is None else evaluation['materials']
            cls._validate_frequencies(data, section, materials)
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
        kwargs = dict(materials=_models(data))
        if data['material_variables']:
            kwargs = dict(material_factory=lambda a, b: _models(_sample_material(study, [a, b])))
        return seek_sampled_impedance(factory, [v['bounds'] for v in data['variables']],
            data['frequencies_hz'], data['targets_ohm'], tolerances=data['tolerances_ohm'],
            quantity=data['quantity'], initial=data['initial'], max_evaluations=data['max_evaluations'],
            mesh=data['mesh'], **kwargs)
