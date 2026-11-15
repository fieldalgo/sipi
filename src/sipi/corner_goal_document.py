# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""A strict saved contract for explicit corner-controlled impedance goals."""
from dataclasses import dataclass, field
import json

from .circuit_document import _json_copy
from .document import _keys, _number, _unique_object
from .design_document import ImpedanceDesignDocument
from .corner_study import CornerImpedanceStudyDocument
from .corner_goal import seek_corner_impedance
from .study import _TEMPLATES, _parameters
from .impedance_material import _models, _sample_material

__all__ = ['CornerImpedanceDesignDocument']
_SCHEMA = 'sipi.corner-impedance-design/1'


def _validated(data):
    data = _json_copy(data)
    _keys(data, ('schema', 'design', 'corner_size'), where='corner impedance design')
    if data['schema'] != _SCHEMA:
        raise ValueError('unsupported corner impedance design schema')
    design = ImpedanceDesignDocument.from_dict(data['design'])
    corner = _number(data['corner_size'], 'corner_size')
    canonical = design.to_dict()
    CornerImpedanceStudyDocument(design._study(canonical), corner)
    return dict(schema=_SCHEMA, design=canonical, corner_size=corner)


@dataclass(frozen=True, init=False)
class CornerImpedanceDesignDocument:
    """Retain the original bounded design and a separate corner target.

    Normalization performs no field solves. The direct corner goal keeps
    selected-input refinement, original budgets and typed failure history.
    """
    _data_json: str = field(repr=False)

    def __init__(self, design: ImpedanceDesignDocument, corner_size):
        if not isinstance(design, ImpedanceDesignDocument):
            raise TypeError('design must be an ImpedanceDesignDocument')
        data = _validated(dict(schema=_SCHEMA, design=design.to_dict(), corner_size=corner_size))
        object.__setattr__(self, '_data_json', json.dumps(data, sort_keys=True, indent=2,
                                                       ensure_ascii=False, allow_nan=False))

    @classmethod
    def from_dict(cls, data):
        result = cls.__new__(cls)
        object.__setattr__(result, '_data_json', json.dumps(_validated(data), sort_keys=True,
                                                          indent=2, ensure_ascii=False, allow_nan=False))
        return result

    @classmethod
    def loads(cls, text):
        def reject(value): raise ValueError(f'nonfinite JSON number: {value}')
        return cls.from_dict(json.loads(text, object_pairs_hook=_unique_object, parse_constant=reject))

    def dumps(self): return self._data_json
    def to_dict(self): return json.loads(self._data_json)
    @property
    def design(self): return ImpedanceDesignDocument.from_dict(self.to_dict()['design'])
    @property
    def corner_size(self): return self.to_dict()['corner_size']

    def solve(self):
        design = self.design; data = design.to_dict(); study = design._study(data).to_dict()
        def factory(value):
            return _TEMPLATES[data['template']](**_parameters(study, [value]))
        evaluation = data.get('material_evaluation')
        options = ({} if evaluation is None else
                   dict(frequency=evaluation['frequency_hz'], materials=_models(evaluation)))
        if 'material_variables' in data:
            options = dict(frequency=evaluation['frequency_hz'],
                           material_factory=lambda value: _models(_sample_material(study, [value])))
        if 'search_tolerance_ohm' in data:
            options['search_tolerance'] = data['search_tolerance_ohm']
        return seek_corner_impedance(factory, data['bounds'], data['target_ohm'],
            corner_size=self.corner_size, quantity=data['quantity'], tolerance=data['tolerance_ohm'],
            max_evaluations=data['max_evaluations'], mesh=data['mesh'], **options)
