# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit corner-controlled samples with unchanged study accounting."""
from dataclasses import dataclass, field
import json

from .circuit_document import _json_copy
from .document import CrossSectionDocument, _keys, _number, _unique_object
from .corner_document import CornerCrossSectionDocument
from .study import ImpedanceStudyDocument, _TEMPLATES, _analyze_study

__all__ = ['CornerImpedanceStudyDocument']
_SCHEMA = 'sipi.corner-impedance-study/1'


def _validated(data):
    data = _json_copy(data)
    _keys(data, ('schema', 'study', 'corner_size'), where='corner impedance study')
    if data['schema'] != _SCHEMA:
        raise ValueError('unsupported corner impedance study schema')
    study = ImpedanceStudyDocument.from_dict(data['study'])
    corner = _number(data['corner_size'], 'corner_size')
    original = study.to_dict()
    nominal = _TEMPLATES[original['template']](**original['parameters'])
    CornerCrossSectionDocument(CrossSectionDocument(nominal, mesh=original['mesh']), corner)
    return dict(schema=_SCHEMA, study=original, corner_size=corner)


@dataclass(frozen=True, init=False)
class CornerImpedanceStudyDocument:
    """Retain a fixed corner target for every existing study sample.

    Sample generation, budget, failure handling and descriptive statistics
    retain the original study contract. Successful rows carry the explicit
    corner-section snapshot. No sample's convergence is inferred.
    """
    _data_json: str = field(repr=False)

    def __init__(self, study: ImpedanceStudyDocument, corner_size):
        if not isinstance(study, ImpedanceStudyDocument):
            raise TypeError('study must be an ImpedanceStudyDocument')
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
    def study(self): return ImpedanceStudyDocument.from_dict(self.to_dict()['study'])
    @property
    def corner_size(self): return self.to_dict()['corner_size']
    def samples(self): return self.study.samples()
    def sample_parameters(self): return self.study.sample_parameters()
    def sample_material_evaluations(self): return self.study.sample_material_evaluations()

    def analyze(self, *, max_evaluations=128):
        corner = self.corner_size
        def snapshot(section, *, mesh):
            return CornerCrossSectionDocument(CrossSectionDocument(section, mesh=mesh), corner)
        return _analyze_study(self.study, max_evaluations=max_evaluations,
                              document_factory=snapshot, input_json=self.dumps())
