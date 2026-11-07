# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict saved scalar lossy goals reusing a one-variable study specification."""
import json

from .document import _keys, _unique_object
from .study import ImpedanceStudyDocument
from .sampling import _copy, _integer
from .line_goal import seek_line_quantity
from .line_input import _source_study, _line_from_values
from .network import _scalar

__all__ = ['LineQuantityDesignDocument']


class LineQuantityDesignDocument:
    """sipi.line-quantity-design/1: saved geometry/material factory and lossy target.

    study is a /3 or /4 ImpedanceStudyDocument (or its dictionary), with z0,
    one positive fixed frequency, sweep count=2 and one positive-bounded variable.
    It specifies inputs only: no preliminary study or quasi-static goal runs.
    The goal uses full lossy scalar RLGC through seek_line_quantity.

    conductor is the exact transmission-line/6 record, fixed across the search.
    Normalization retains the study's endpoint geometry/material preflight and
    adds the nominal conductor guards, without meshing. Later candidate failures
    (such as endpoint skin depth or an invalid interior) count as factory attempts;
    they are not silently repaired.
    Selected and refined inputs retain zero-length line/6 documents at 50 ohms;
    that network reference does not define the characteristic target quantity.
    """
    def __init__(self, study, *, conductor, quantity, target, tolerance, max_evaluations=40):
        if isinstance(study, ImpedanceStudyDocument):
            study = study.to_dict()
        self._assign(dict(schema='sipi.line-quantity-design/1', study=study,
            conductor=conductor, quantity=quantity, target=target, tolerance=tolerance,
            max_evaluations=max_evaluations))

    def _assign(self, data):
        data = _copy(data)
        _keys(data, ('schema', 'study', 'conductor', 'quantity', 'target', 'tolerance',
                     'max_evaluations'), where='line quantity design')
        if data['schema'] != 'sipi.line-quantity-design/1':
            raise ValueError('unsupported line-quantity-design schema')
        quantity = data['quantity']
        if not isinstance(quantity, str) or quantity not in ('impedance_real', 'attenuation'):
            raise ValueError('quantity must be impedance_real or attenuation')
        target = _scalar('target', data['target'], zero=quantity == 'attenuation')
        tolerance = _scalar('tolerance', data['tolerance'])
        budget = _integer(data['max_evaluations'], 3, 10000)
        study = _source_study(data['study'])
        sampling = study['sampling']
        if sampling['kind'] != 'sweep' or sampling['count'] != 2 or len(sampling['variables']) != 1:
            raise ValueError('goal study requires a sweep with count=2 and exactly one variable')
        variable = sampling['variables'][0]
        lower, upper = (_scalar('parameter bound', variable[key]) for key in ('lower', 'upper'))
        if lower >= upper:
            raise ValueError('lower parameter bound must be below upper')
        nominal = _line_from_values(study, data['conductor'])
        self._data = dict(schema=data['schema'], study=study,
            conductor=nominal.to_dict()['conductor'], quantity=quantity, target=target,
            tolerance=tolerance, max_evaluations=budget)

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

    def solve(self):
        data = self.to_dict(); study = data['study']; variable = study['sampling']['variables'][0]
        return seek_line_quantity(lambda value: _line_from_values(study, data['conductor'], [value]),
            [variable['lower'], variable['upper']], data['target'], quantity=data['quantity'],
            tolerance=data['tolerance'], max_evaluations=data['max_evaluations'])
