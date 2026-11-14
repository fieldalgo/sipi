# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict saved finite FEM resolution requests with explicit SI allowances."""
import json
from .document import _keys, _unique_object
from .sampling import _integer
from .line_resolution import ResolutionTolerance
from .line_resolution_document import _SI, _API
from .fem_shape_line import FEMShapeTransmissionLineDocument
from .fem_shape_resolution import _fem_resolution_inputs, assess_fem_shape_line_resolution

__all__ = ['FEMShapeResolutionDocument']
_SCHEMA = 'sipi.fem-shape-resolution/1'


class FEMShapeResolutionDocument:
    """Explicit finite comparisons; preserving nonacceptance is part of the contract."""
    def __init__(self,line,*,outer_documents,tolerances,refinement_factor=.5,max_solves=4):
        models,stages=_fem_resolution_inputs(line,outer_documents,tolerances,refinement_factor,max_solves)
        self._data=dict(schema=_SCHEMA,line=stages[0][1].to_dict(),
            outer_lines=[doc.to_dict() for _,doc in stages[2:]],refinement_factor=float(refinement_factor),
            max_solves=max_solves,tolerances={_SI[k]:dict(relative=v.relative,absolute=v.absolute) for k,v in models.items()})

    @classmethod
    def from_dict(cls,data):
        _keys(data,('schema','line','outer_lines','refinement_factor','max_solves','tolerances'),where='FEM resolution')
        if data['schema']!=_SCHEMA:raise ValueError('unsupported FEM resolution schema')
        if not isinstance(data['outer_lines'],list):raise ValueError('outer_lines must be an explicit list')
        tolerances=data['tolerances']
        if not isinstance(tolerances,dict) or not tolerances or set(tolerances)-set(_API):
            raise ValueError('resolution tolerances require explicit supported SI quantity names')
        models={}
        for key,value in tolerances.items():
            _keys(value,('relative','absolute'),where='resolution tolerance')
            models[_API[key]]=ResolutionTolerance(**value)
        return cls(FEMShapeTransmissionLineDocument.from_dict(data['line']),
            outer_documents=[FEMShapeTransmissionLineDocument.from_dict(v) for v in data['outer_lines']],
            tolerances=models,refinement_factor=data['refinement_factor'],max_solves=data['max_solves'])

    @classmethod
    def loads(cls,text):
        def reject(value):raise ValueError('nonfinite JSON number: '+value)
        return cls.from_dict(json.loads(text,object_pairs_hook=_unique_object,parse_constant=reject))

    def dumps(self):return json.dumps(self._data,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)
    def to_dict(self):return json.loads(self.dumps())

    def analyze(self,*,max_evaluations=10000):
        budget=_integer(max_evaluations,2,10000);data=self.to_dict()
        if 2+len(data['outer_lines'])>budget:raise ValueError('resolution evaluation budget exceeded before any field solve')
        return assess_fem_shape_line_resolution(FEMShapeTransmissionLineDocument.from_dict(data['line']),
            outer_documents=[FEMShapeTransmissionLineDocument.from_dict(v) for v in data['outer_lines']],
            tolerances={_API[k]:ResolutionTolerance(**v) for k,v in data['tolerances'].items()},
            refinement_factor=data['refinement_factor'],max_solves=min(data['max_solves'],budget))
