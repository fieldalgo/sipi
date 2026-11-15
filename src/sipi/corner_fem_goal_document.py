# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""A strict saved contract for explicit corner-controlled FEM line goals."""
from dataclasses import dataclass, field
import json

from .circuit_document import _json_copy
from .document import _keys, _number, _unique_object
from .fem_shape_goal_document import FEMShapeLineQuantityDesignDocument
from .corner_fem_study import CornerFEMShapeLineQuantityStudyDocument
from .corner_fem_goal import seek_corner_fem_shape_line_quantity
from .corner_fem_line import CornerFEMShapeTransmissionLineDocument
from .fem_shape_study import _line
from .study import _parameters
from .impedance_material import _sample_material

__all__ = ['CornerFEMShapeLineQuantityDesignDocument']
_SCHEMA = 'sipi.corner-fem-shape-line-quantity-design/1'


def _validated(data):
    data = _json_copy(data)
    _keys(data, ('schema', 'design', 'corner_size'), where='corner FEM line design')
    if data['schema'] != _SCHEMA:
        raise ValueError('unsupported corner FEM line design schema')
    design = FEMShapeLineQuantityDesignDocument.from_dict(data['design'])
    corner = _number(data['corner_size'], 'corner_size')
    canonical = design.to_dict()
    CornerFEMShapeLineQuantityStudyDocument(design.study, corner)
    return dict(schema=_SCHEMA, design=canonical, corner_size=corner)


@dataclass(frozen=True, init=False)
class CornerFEMShapeLineQuantityDesignDocument:
    """Retain the original bounded design and a separate corner target.

    Normalization performs no field solves. The direct corner goal keeps
    selected-input refinement, original budgets and typed failure history.
    """
    _data_json: str = field(repr=False)

    def __init__(self, design: FEMShapeLineQuantityDesignDocument, corner_size):
        if not isinstance(design, FEMShapeLineQuantityDesignDocument):
            raise TypeError('design must be an FEMShapeLineQuantityDesignDocument')
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
    def design(self): return FEMShapeLineQuantityDesignDocument.from_dict(self.to_dict()['design'])
    @property
    def corner_size(self): return self.to_dict()['corner_size']

    def solve(self):
        data = self.design.to_dict(); model = data['study']; source = model['study']
        variable = source['sampling']['variables'][0]
        def factory(value):
            line = _line(source, _parameters(source, [value]), _sample_material(source, [value]), model)
            return CornerFEMShapeTransmissionLineDocument(line, self.corner_size)
        return seek_corner_fem_shape_line_quantity(factory, [variable['lower'], variable['upper']],
            data['target'], quantity=model['quantity'], tolerance=data['tolerance'],
            max_evaluations=data['max_evaluations'])
