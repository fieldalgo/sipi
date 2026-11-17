# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict saved finite two-ground-linear-corner-face comparisons with explicit SI allowances."""
from collections.abc import Mapping
from ._validation import _json_copy,_keys
from .two_ground_resolution_document import TwoGroundResolutionDocument as _WholeResolution
from .line_resolution import ResolutionTolerance
from .line_resolution_document import _SI,_API
from .sampling import _integer
from .two_ground_linear_corner_face_panel_line import TwoGroundLinearCornerFacePanelTransmissionLineDocument as Line
from .two_ground_linear_corner_face_resolution import assess_two_ground_linear_corner_face_line_resolution,_two_ground_linear_corner_face_resolution_inputs

__all__=['TwoGroundLinearCornerFaceResolutionDocument']
_SCHEMA='sipi.two-ground-linear-corner-face-resolution/1'


class TwoGroundLinearCornerFaceResolutionDocument(_WholeResolution):
    """Saved separate volume/panel/joint/outer observations, not error bounds."""
    def __init__(self,line,*,refined_panel_options,outer_documents,tolerances,
                 refinement_factor=.5,max_solves=6):
        if not isinstance(line,Line):raise TypeError('line must be a TwoGroundLinearCornerFacePanelTransmissionLineDocument')
        if (not isinstance(outer_documents,(tuple,list)) or any(not isinstance(doc,Line) for doc in outer_documents)):
            raise TypeError('outer_documents must contain two-ground-linear-corner-face line documents')
        if (not isinstance(tolerances,Mapping) or not tolerances or
            any(k not in _SI or not isinstance(v,ResolutionTolerance) for k,v in tolerances.items())):
            raise ValueError('tolerances must select named quantities with ResolutionTolerance values')
        self._assign(dict(schema=_SCHEMA,line=line.to_dict(),refined_panel=dict(refined_panel_options),
            outer_lines=[doc.to_dict() for doc in outer_documents],refinement_factor=refinement_factor,
            max_solves=max_solves,tolerances={_SI[k]:dict(relative=v.relative,absolute=v.absolute) for k,v in tolerances.items()}))

    def _assign(self,data):
        data=_json_copy(data)
        _keys(data,('schema','line','refined_panel','outer_lines','refinement_factor','max_solves','tolerances'),where='two-ground-linear-corner-face resolution')
        if data['schema']!=_SCHEMA:raise ValueError('unsupported two-ground-linear-corner-face-resolution schema')
        if not isinstance(data['outer_lines'],list):raise ValueError('outer_lines must be an explicit list')
        documents=[Line.from_dict(raw) for raw in [data['line']]+data['outer_lines']]
        values=data['tolerances']
        if not isinstance(values,dict) or not values or set(values)-set(_API):
            raise ValueError('two-ground-linear-corner-face resolution tolerances require explicit SI quantity names')
        models={}
        for key,value in values.items():
            _keys(value,('relative','absolute'),where='two-ground-linear-corner-face resolution tolerance')
            models[_API[key]]=ResolutionTolerance(**value)
        models,stages=_two_ground_linear_corner_face_resolution_inputs(documents[0],data['refined_panel'],documents[1:],models,
            data['refinement_factor'],data['max_solves'])
        self._data=dict(schema=_SCHEMA,line=stages[0][1].to_dict(),refined_panel=stages[2][1].current_options,
            outer_lines=[doc.to_dict() for _,doc,_ in stages[4:]],refinement_factor=float(data['refinement_factor']),
            max_solves=data['max_solves'],tolerances={_SI[k]:dict(relative=v.relative,absolute=v.absolute) for k,v in models.items()})

    def analyze(self,*,max_evaluations=10000):
        budget=_integer(max_evaluations,2,10000);data=self.to_dict()
        if 4+len(data['outer_lines'])>budget:
            raise ValueError('two-ground-linear-corner-face resolution evaluation budget exceeded before any field solve')
        return assess_two_ground_linear_corner_face_line_resolution(Line.from_dict(data['line']),refined_panel_options=data['refined_panel'],
            outer_documents=[Line.from_dict(raw) for raw in data['outer_lines']],
            tolerances={_API[k]:ResolutionTolerance(**value) for k,value in data['tolerances'].items()},
            refinement_factor=data['refinement_factor'],max_solves=min(data['max_solves'],budget))
