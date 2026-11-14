# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict saved finite comparisons for explicit shape-current line documents."""
from collections.abc import Mapping
import json

from .document import _keys, _unique_object
from .line_resolution import ResolutionTolerance
from .line_resolution_document import _SI, _API
from .shape_panel_line import ShapePanelTransmissionLineDocument
from .shape_panel_resolution import (assess_shape_panel_line_resolution,
                                      _shape_panel_resolution_inputs)
from .sampling import _integer

__all__ = ['ShapePanelResolutionDocument']


class ShapePanelResolutionDocument:
    """Explicit SI allowances and immutable planned inputs; normalization is field-free."""
    def __init__(self, line, *, refined_panel_options, outer_documents, tolerances,
                 refinement_factor=.5, max_solves=6):
        if not isinstance(line, ShapePanelTransmissionLineDocument):
            raise TypeError('line must be a ShapePanelTransmissionLineDocument')
        if (not isinstance(outer_documents, (list, tuple))
                or any(not isinstance(doc, ShapePanelTransmissionLineDocument) for doc in outer_documents)):
            raise TypeError('outer_documents must contain ShapePanelTransmissionLineDocument objects')
        if not isinstance(refined_panel_options, Mapping):
            raise ValueError('refined_panel_options must specify the three panel controls')
        if (not isinstance(tolerances, Mapping)
                or any(k not in _SI or not isinstance(v, ResolutionTolerance) for k, v in tolerances.items())):
            raise ValueError('tolerances must select named quantities with ResolutionTolerance values')
        self._data = self._validate(dict(schema='sipi.shape-panel-resolution/1', line=line.to_dict(),
            refined_panel=dict(refined_panel_options), outer_lines=[doc.to_dict() for doc in outer_documents],
            tolerances={_SI[k]:dict(relative=v.relative, absolute=v.absolute) for k,v in tolerances.items()},
            refinement_factor=refinement_factor, max_solves=max_solves))

    @staticmethod
    def _validate(data):
        _keys(data, ('schema','line','refined_panel','outer_lines','tolerances','refinement_factor','max_solves'),
              where='shape panel resolution')
        if data['schema'] != 'sipi.shape-panel-resolution/1':
            raise ValueError('unsupported shape-panel-resolution schema')
        if not isinstance(data['outer_lines'], list):
            raise ValueError('outer_lines must be an explicit list')
        line = ShapePanelTransmissionLineDocument.from_dict(data['line'])
        outer = [ShapePanelTransmissionLineDocument.from_dict(v) for v in data['outer_lines']]
        raw = data['tolerances']
        if not isinstance(raw, dict) or not raw or set(raw)-set(_API):
            raise ValueError('resolution tolerances must use explicit supported SI quantity names')
        models = {}
        for key, value in raw.items():
            _keys(value, ('relative','absolute'), where='resolution tolerance')
            models[_API[key]] = ResolutionTolerance(**value)
        models, stages = _shape_panel_resolution_inputs(line, data['refined_panel'], outer,
            models, data['refinement_factor'], data['max_solves'])
        return dict(schema=data['schema'], line=stages[0][1].to_dict(),
            refined_panel=stages[2][1].line.panel_options,
            outer_lines=[doc.to_dict() for _,doc,_ in stages[4:]],
            tolerances={_SI[k]:dict(relative=v.relative, absolute=v.absolute) for k,v in models.items()},
            refinement_factor=float(data['refinement_factor']), max_solves=int(data['max_solves']))

    @classmethod
    def from_dict(cls, data):
        out = cls.__new__(cls)
        out._data = cls._validate(data)
        return out

    @classmethod
    def loads(cls, text):
        def reject(value):
            raise ValueError('nonfinite JSON number: '+value)
        return cls.from_dict(json.loads(text, object_pairs_hook=_unique_object, parse_constant=reject))

    def dumps(self):
        return json.dumps(self._data, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)

    def to_dict(self):
        return json.loads(self.dumps())

    def analyze(self, *, max_evaluations=10000):
        budget = _integer(max_evaluations, 2, 10000)
        data = self.to_dict()
        if 4+len(data['outer_lines']) > budget:
            raise ValueError('shape resolution budget exceeded before any field solve')
        return assess_shape_panel_line_resolution(ShapePanelTransmissionLineDocument.from_dict(data['line']),
            refined_panel_options=data['refined_panel'],
            outer_documents=[ShapePanelTransmissionLineDocument.from_dict(v) for v in data['outer_lines']],
            tolerances={_API[k]:ResolutionTolerance(**v) for k,v in data['tolerances'].items()},
            refinement_factor=data['refinement_factor'], max_solves=min(data['max_solves'],budget))
