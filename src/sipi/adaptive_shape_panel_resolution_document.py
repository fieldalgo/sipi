# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict saved plans for explicit bounded shape-current refinement."""
from collections.abc import Mapping
import json

from .document import _keys, _unique_object
from .shape_panel_line import ShapePanelTransmissionLineDocument
from .line_resolution import ResolutionTolerance
from .line_resolution_document import _SI, _API
from .adaptive_shape_panel_resolution import (ShapePanelResolutionRefinement,
    refine_shape_panel_line_resolution, _adaptive_shape_inputs)
from .sampling import _integer

__all__ = ['AdaptiveShapePanelResolutionDocument']


class AdaptiveShapePanelResolutionDocument:
    """Explicit finite comparisons and budgets, not a numerical error certificate."""
    def __init__(self, line, *, refinements, tolerances, refinement_factor=.5, max_solves=16):
        if not isinstance(line, ShapePanelTransmissionLineDocument):
            raise TypeError('line must be a ShapePanelTransmissionLineDocument')
        if (not isinstance(refinements, (tuple, list))
                or any(not isinstance(s, ShapePanelResolutionRefinement) for s in refinements)):
            raise TypeError('refinements must contain ShapePanelResolutionRefinement steps')
        if (not isinstance(tolerances, Mapping) or not tolerances
                or any(k not in _SI or not isinstance(v, ResolutionTolerance) for k,v in tolerances.items())):
            raise ValueError('tolerances must select named quantities with ResolutionTolerance values')
        self._data = self._validate(dict(schema='sipi.adaptive-shape-panel-resolution/1',
            line=line.to_dict(), refinements=[dict(refined_panel=dict(s.panel_options),
                outer_lines=[d.to_dict() for d in s.outer_documents]) for s in refinements],
            refinement_factor=refinement_factor, max_solves=max_solves,
            tolerances={_SI[k]:dict(relative=v.relative,absolute=v.absolute) for k,v in tolerances.items()}))

    @staticmethod
    def _validate(data):
        _keys(data, ('schema','line','refinements','tolerances','refinement_factor','max_solves'),
              where='adaptive panel resolution')
        if data['schema'] != 'sipi.adaptive-shape-panel-resolution/1':
            raise ValueError('unsupported adaptive-shape-panel-resolution schema')
        if not isinstance(data['refinements'], list) or not 2 <= len(data['refinements']) <= 4:
            raise ValueError('refinements must explicitly list two to four steps')

        def line(value):
            if not isinstance(value,dict) or value.get('schema') != 'sipi.shape-panel-transmission-line/1':
                raise ValueError('adaptive panel resolution requires explicit nested shape-panel lines')
            return ShapePanelTransmissionLineDocument.from_dict(value)

        base = line(data['line'])
        steps = []
        for step in data['refinements']:
            _keys(step, ('refined_panel','outer_lines'), where='panel refinement step')
            if not isinstance(step['outer_lines'],list):
                raise ValueError('outer_lines must be an explicit list')
            steps.append(ShapePanelResolutionRefinement(step['refined_panel'],
                [line(v) for v in step['outer_lines']]))
        values = data['tolerances']
        if not isinstance(values,dict) or not values or set(values)-set(_API):
            raise ValueError('adaptive resolution tolerances require explicit SI quantity names')
        models = {}
        for key,value in values.items():
            _keys(value, ('relative','absolute'), where='adaptive resolution tolerance')
            models[_API[key]] = ResolutionTolerance(**value)
        limit,models,plans = _adaptive_shape_inputs(base,steps,models,
            data['refinement_factor'],data['max_solves'])
        return dict(schema=data['schema'], line=plans[0][0][1].to_dict(),
            refinements=[dict(refined_panel=stages[2][1].line.panel_options,
                outer_lines=[doc.to_dict() for _,doc,_ in stages[4:]]) for stages in plans],
            refinement_factor=float(data['refinement_factor']),max_solves=limit,
            tolerances={_SI[k]:dict(relative=v.relative,absolute=v.absolute) for k,v in models.items()})

    @classmethod
    def from_dict(cls, data):
        out=cls.__new__(cls);out._data=cls._validate(data);return out

    @classmethod
    def loads(cls, text):
        def reject(value):raise ValueError('nonfinite JSON number: '+value)
        return cls.from_dict(json.loads(text,object_pairs_hook=_unique_object,parse_constant=reject))

    def dumps(self):
        return json.dumps(self._data,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)

    def to_dict(self):
        return json.loads(self.dumps())

    def analyze(self, *, max_evaluations=10000):
        budget=_integer(max_evaluations,2,10000);data=self.to_dict()
        if 7+len(data['refinements'][0]['outer_lines'])>budget:
            raise ValueError('adaptive panel budget exceeded before any field solve')
        steps=[ShapePanelResolutionRefinement(step['refined_panel'],
            [ShapePanelTransmissionLineDocument.from_dict(v) for v in step['outer_lines']])
            for step in data['refinements']]
        return refine_shape_panel_line_resolution(ShapePanelTransmissionLineDocument.from_dict(data['line']),
            refinements=steps,tolerances={_API[k]:ResolutionTolerance(**v) for k,v in data['tolerances'].items()},
            refinement_factor=data['refinement_factor'],max_solves=min(data['max_solves'],budget))
