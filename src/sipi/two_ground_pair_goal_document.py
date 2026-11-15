# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict saved paired impedance goals with separate top/bottom surface metals."""
import itertools
import json

from ._validation import _json_copy, _keys, _unique_object
from .sampling import _integer, _scalar
from .study import ImpedanceStudyDocument
from .two_ground_input import _source_inputs, _line_from_values
from .two_ground_pair_goal import _refinements, seek_two_ground_forward_pair_impedances

__all__ = ['TwoGroundForwardPairDesignDocument']
_SCHEMA = 'sipi.two-ground-forward-pair-design/1'
_QUANTITIES = ('differential_forward_impedance_real', 'common_forward_impedance_real')
_SOURCE_KEYS = ('study', 'conductors', 'reference', 'ground_thickness_m', 'panel')
_GOAL_KEYS = ('targets_ohm', 'tolerances_ohm', 'initial', 'max_evaluations')


class TwoGroundForwardPairDesignDocument:
    """Two ordered source variables and two full-complex forward-launch targets.

    Study/3 or /4 provides geometry/material bindings at one positive frequency.
    Nominal, initial/midpoint and four bound corners, including three future
    refinements, are admitted before field work. This is not a proof of valid
    interior geometry or an optimum. Each uncached solve/failure remains an
    attempt; the direct goal's original budget and refinement criteria apply.
    """
    def __init__(self, study, *, conductors, reference, ground_thickness,
                 targets, tolerances, initial=None, max_evaluations=64,
                 panels_per_edge=32, ground_modes=128, interpolation_degree=12):
        if isinstance(study, ImpedanceStudyDocument):
            study = study.to_dict()
        self._data = self._validate(dict(schema=_SCHEMA, study=study,
            conductors=conductors, reference=reference, ground_thickness_m=ground_thickness,
            targets_ohm=targets, tolerances_ohm=tolerances, initial=initial,
            max_evaluations=max_evaluations, panel=dict(panels_per_edge=panels_per_edge,
                ground_modes=ground_modes, interpolation_degree=interpolation_degree)))

    @staticmethod
    def _validate(data):
        data = _json_copy(data)
        _keys(data, ('schema', *_SOURCE_KEYS, *_GOAL_KEYS), where='two-ground forward pair design')
        if data['schema'] != _SCHEMA:
            raise ValueError('unsupported two-ground-forward-pair-design schema')
        for key in ('targets_ohm', 'tolerances_ohm'):
            _keys(data[key], _QUANTITIES, where=key)
            data[key] = {q:_scalar(data[key][q], positive=True) for q in _QUANTITIES}
        budget = _integer(data['max_evaluations'], 4, 10000)
        source = _source_inputs(data)
        sampling = source['study']['sampling']
        if sampling['kind'] != 'corners' or len(sampling['variables']) != 2:
            raise ValueError('two-ground pair source requires corners with exactly two variables')
        bounds = []
        for variable in sampling['variables']:
            lower, upper = (_scalar(variable[key], positive=True) for key in ('lower', 'upper'))
            if lower >= upper:
                raise ValueError('lower parameter bound must be below upper')
            bounds.append((lower, upper))
        initial = data['initial']
        if initial is not None:
            if not isinstance(initial, list) or len(initial) != 2:
                raise ValueError('initial must be null or two ordered parameters')
            initial = [_scalar(x, positive=True) for x in initial]
            if any(x < lo or x > hi for x, (lo, hi) in zip(initial, bounds)):
                raise ValueError('initial must lie inside each variable bound')
        point = [lo+(hi-lo)/2 for lo, hi in bounds] if initial is None else initial
        for values in [None, point, *itertools.product(*bounds)]:
            _refinements(_line_from_values(source, values).dumps())
        return dict(schema=_SCHEMA, **source, targets_ohm=data['targets_ohm'],
                    tolerances_ohm=data['tolerances_ohm'], initial=initial, max_evaluations=budget)

    @classmethod
    def from_dict(cls, data):
        result = cls.__new__(cls)
        result._data = cls._validate(data)
        return result

    @classmethod
    def loads(cls, text):
        def reject(value):
            raise ValueError('nonfinite JSON number: '+value)
        return cls.from_dict(json.loads(text, object_pairs_hook=_unique_object, parse_constant=reject))

    def dumps(self):
        return json.dumps(self._data, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)

    def to_dict(self):
        return json.loads(self.dumps())

    @property
    def goal_input(self):
        return {key:value for key,value in self.to_dict().items() if key != 'schema'}

    def solve(self):
        data = self.to_dict()
        return seek_two_ground_forward_pair_impedances(
            lambda a,b:_line_from_values(data, [a,b]),
            [[v['lower'],v['upper']] for v in data['study']['sampling']['variables']],
            [data['targets_ohm'][q] for q in _QUANTITIES],
            tolerances=[data['tolerances_ohm'][q] for q in _QUANTITIES],
            initial=data['initial'], max_evaluations=data['max_evaluations'])
