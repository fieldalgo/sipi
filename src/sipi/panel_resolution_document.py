# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict saved panel, volume and outer comparisons with explicit SI tolerances."""
import json
from collections.abc import Mapping

from .document import _keys,_unique_object
from .panel_line import PanelTransmissionLineDocument
from .panel_resolution import assess_panel_line_resolution,_panel_resolution_inputs
from .line_resolution import ResolutionTolerance
from .line_resolution_document import _SI,_API
from .sampling import _integer

__all__ = ['PanelResolutionDocument']


class PanelResolutionDocument:
    """Saved finite elementwise agreement, not an absolute field-error bound."""
    def __init__(self,line,*,refined_panel_options,outer_documents,tolerances,
                 refinement_factor=.5,max_solves=6):
        if not isinstance(line,PanelTransmissionLineDocument):
            raise TypeError('line must be a PanelTransmissionLineDocument')
        if (not isinstance(outer_documents,(list,tuple))
                or any(not isinstance(doc,PanelTransmissionLineDocument) for doc in outer_documents)):
            raise TypeError('outer_documents must contain panel line documents')
        if (not isinstance(tolerances,Mapping) or not tolerances
                or any(k not in _SI or not isinstance(v,ResolutionTolerance) for k,v in tolerances.items())):
            raise ValueError('tolerances must select named quantities with ResolutionTolerance values')
        self._data=self._validate(dict(schema='sipi.panel-resolution/1',line=line.to_dict(),
            refined_panel=refined_panel_options,outer_lines=[doc.to_dict() for doc in outer_documents],
            refinement_factor=refinement_factor,max_solves=max_solves,
            tolerances={_SI[k]:dict(relative=v.relative,absolute=v.absolute) for k,v in tolerances.items()}))

    @staticmethod
    def _validate(data):
        _keys(data,('schema','line','refined_panel','outer_lines','refinement_factor','max_solves','tolerances'),
              where='panel resolution')
        if data['schema']!='sipi.panel-resolution/1':raise ValueError('unsupported panel-resolution schema')
        if not isinstance(data['outer_lines'],list):raise ValueError('outer_lines must be an explicit list')
        values=[data['line']]+data['outer_lines']
        if any(not isinstance(v,dict) or v.get('schema') not in
               ('sipi.panel-transmission-line/1','sipi.panel-transmission-line/2') for v in values):
            raise ValueError('panel resolution requires nested panel-transmission-line/1 or /2')
        documents=[PanelTransmissionLineDocument.from_dict(v) for v in values]
        values=data['tolerances']
        if not isinstance(values,dict) or not values or set(values)-set(_API):
            raise ValueError('panel resolution tolerances require explicit SI quantity names')
        models={}
        for key,value in values.items():
            _keys(value,('relative','absolute'),where='panel resolution tolerance')
            models[_API[key]]=ResolutionTolerance(**value)
        models,stages=_panel_resolution_inputs(documents[0],data['refined_panel'],documents[1:],
            models,data['refinement_factor'],data['max_solves'])
        return dict(schema=data['schema'],line=stages[0][1].to_dict(),
            refined_panel=stages[2][1].panel_options,outer_lines=[doc.to_dict() for _,doc,_ in stages[4:]],
            refinement_factor=float(data['refinement_factor']),max_solves=data['max_solves'],
            tolerances={_SI[k]:dict(relative=v.relative,absolute=v.absolute) for k,v in models.items()})

    @classmethod
    def from_dict(cls,data):
        out=cls.__new__(cls);out._data=cls._validate(data);return out

    @classmethod
    def loads(cls,text):
        def reject(value):raise ValueError('nonfinite JSON number: '+value)
        return cls.from_dict(json.loads(text,object_pairs_hook=_unique_object,parse_constant=reject))

    def dumps(self):
        return json.dumps(self._data,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)

    def to_dict(self):
        return json.loads(self.dumps())

    def analyze(self,*,max_evaluations=10000):
        budget=_integer(max_evaluations,2,10000);data=self.to_dict()
        if 4+len(data['outer_lines'])>budget:
            raise ValueError('panel resolution evaluation budget exceeded before any field solve')
        return assess_panel_line_resolution(PanelTransmissionLineDocument.from_dict(data['line']),
            outer_documents=[PanelTransmissionLineDocument.from_dict(v) for v in data['outer_lines']],
            refined_panel_options=data['refined_panel'],
            tolerances={_API[k]:ResolutionTolerance(**v) for k,v in data['tolerances'].items()},
            refinement_factor=data['refinement_factor'],max_solves=min(data['max_solves'],budget))
