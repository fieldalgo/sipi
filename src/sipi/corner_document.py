# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""A separate saved contract for explicit corner mesh targets."""
from dataclasses import dataclass, field
import json

from .circuit_document import _json_copy
from .document import CrossSectionDocument, _keys, _number, _unique_object

__all__ = ['CornerCrossSectionDocument']
_SCHEMA = 'sipi.corner-cross-section/1'


def _validated(data):
    data = _json_copy(data)
    _keys(data, ('schema', 'cross_section', 'corner_size'), where='corner cross-section')
    if data['schema'] != _SCHEMA:
        raise ValueError('unsupported corner cross-section schema')
    original = CrossSectionDocument.from_dict(data['cross_section'])
    corner = _number(data['corner_size'], 'corner_size')
    original.section.mesh_settings(**original.mesh_options, corner_size=corner)
    return dict(schema=_SCHEMA, cross_section=original.to_dict(), corner_size=corner)


@dataclass(frozen=True, init=False)
class CornerCrossSectionDocument:
    """Store an original cross-section and an explicit corner target in metres.

    Existing cross-section schemas remain strict. This standalone snapshot
    does not implicitly enable the option in saved studies or line goals.
    Construction and decoding validate without generating a mesh.
    """
    _data_json: str = field(repr=False)

    def __init__(self, cross_section: CrossSectionDocument, corner_size):
        if not isinstance(cross_section, CrossSectionDocument):
            raise TypeError('cross_section must be a CrossSectionDocument')
        data = _validated(dict(schema=_SCHEMA, cross_section=cross_section.to_dict(),
                               corner_size=corner_size))
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
        def reject(value):
            raise ValueError(f'nonfinite JSON number: {value}')
        return cls.from_dict(json.loads(text, object_pairs_hook=_unique_object, parse_constant=reject))

    def dumps(self):
        return self._data_json

    def to_dict(self):
        return json.loads(self._data_json)

    @property
    def cross_section(self):
        return CrossSectionDocument.from_dict(self.to_dict()['cross_section'])

    @property
    def corner_size(self):
        return self.to_dict()['corner_size']

    @property
    def section(self):
        return self.cross_section.section

    @property
    def mesh_options(self):
        return dict(self.cross_section.mesh_options, corner_size=self.corner_size)

    def analyze(self):
        return self.section.analyze(**self.mesh_options)
