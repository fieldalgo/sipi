# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved FEM line quantity samples with separate corner resolution."""
from dataclasses import dataclass, field
import json

from .document import _keys, _number, _unique_object
from .circuit_document import _json_copy
from .corner_fem_line import CornerFEMShapeTransmissionLineDocument
from . import fem_shape_study as _original

__all__ = ['CornerFEMShapeLineQuantityStudyDocument']
_SCHEMA = 'sipi.corner-fem-shape-line-quantity-study/1'


def _validated(data):
    data = _json_copy(data)
    _keys(data, ('schema', 'study', 'corner_size'), where='corner FEM quantity study')
    if data['schema'] != _SCHEMA:
        raise ValueError('unsupported corner FEM quantity study schema')
    study = _original.FEMShapeLineQuantityStudyDocument.from_dict(data['study'])
    corner = _number(data['corner_size'], 'corner_size')
    canonical = study.to_dict(); source = canonical['study']
    nominal = _original._line(source, source['parameters'], source['material_evaluation'], canonical)
    CornerFEMShapeTransmissionLineDocument(nominal, corner)
    return dict(schema=_SCHEMA, study=canonical, corner_size=corner)


@dataclass(frozen=True, init=False)
class CornerFEMShapeLineQuantityStudyDocument:
    """Retain every attempted sample and original descriptive statistics.

    The corner target is fixed across rows. A row's extraction retains all
    original current checks; samples do not certify convergence or yield.
    """
    _data_json: str = field(repr=False)

    def __init__(self, study: _original.FEMShapeLineQuantityStudyDocument, corner_size):
        if not isinstance(study, _original.FEMShapeLineQuantityStudyDocument):
            raise TypeError('study must be a FEMShapeLineQuantityStudyDocument')
        data = _validated(dict(schema=_SCHEMA, study=study.to_dict(), corner_size=corner_size))
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
    def study(self): return _original.FEMShapeLineQuantityStudyDocument.from_dict(self.to_dict()['study'])
    @property
    def corner_size(self): return self.to_dict()['corner_size']
    def samples(self): return self.study.samples()

    def analyze(self, *, max_evaluations=128):
        def factory(source, parameters, evaluation, data):
            return CornerFEMShapeTransmissionLineDocument(
                _original._line(source, parameters, evaluation, data), self.corner_size)
        return _original._analyze_fem_shape_study(self, max_evaluations=max_evaluations,
            data=self.study.to_dict(), line_factory=factory)
