# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit corner resolution for saved whole-boundary FEM shape lines."""
from dataclasses import dataclass, field
import json

from .document import _keys, _number, _unique_object
from .circuit_document import _json_copy
from .corner_document import CornerCrossSectionDocument
from .fem_shape_line import FEMShapeTransmissionLineDocument, _analyze_fem_shape_line

__all__ = ['CornerFEMShapeTransmissionLineDocument']
_SCHEMA = 'sipi.corner-fem-shape-transmission-line/1'


def _validated(data):
    data = _json_copy(data)
    _keys(data, ('schema', 'line', 'corner_size'), where='corner FEM shape line')
    if data['schema'] != _SCHEMA:
        raise ValueError('unsupported corner FEM shape line schema')
    line = FEMShapeTransmissionLineDocument.from_dict(data['line'])
    corner = _number(data['corner_size'], 'corner_size')
    CornerCrossSectionDocument(line.cross_section, corner)
    return dict(schema=_SCHEMA, line=line.to_dict(), corner_size=corner)


@dataclass(frozen=True, init=False)
class CornerFEMShapeTransmissionLineDocument:
    """Preserve the original line contract and a separate corner target.

    This changes mesh control, not the current method or its acceptance gates.
    Both vacuum and material calculations use the same actual mesh.
    """
    _data_json: str = field(repr=False)

    def __init__(self, line: FEMShapeTransmissionLineDocument, corner_size):
        if not isinstance(line, FEMShapeTransmissionLineDocument):
            raise TypeError('line must be a FEMShapeTransmissionLineDocument')
        data = _validated(dict(schema=_SCHEMA, line=line.to_dict(), corner_size=corner_size))
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
    def line(self): return FEMShapeTransmissionLineDocument.from_dict(self.to_dict()['line'])
    @property
    def corner_size(self): return self.to_dict()['corner_size']
    @property
    def cross_section(self): return CornerCrossSectionDocument(self.line.cross_section, self.corner_size)

    def analyze(self):
        return _analyze_fem_shape_line(self, self.cross_section, self.line.to_dict())
