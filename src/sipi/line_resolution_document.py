# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict saved finite-resolution checks with explicit SI tolerance keys."""
import json
from collections.abc import Mapping

from .document import _keys, _unique_object
from .line_model import TransmissionLineDocument
from .line_resolution import (ResolutionTolerance, LineResolutionAssessment,
                              assess_line_resolution, _resolution_inputs, _metric)
from .adaptive_line_resolution import (AdaptiveLineResolution, refine_line_resolution,
                                       _adaptive_inputs)
from .adaptive_panel_resolution import AdaptivePanelResolution
from .sampling import _integer

__all__ = ['LineResolutionDocument', 'resolution_record']

_SI = dict(R='R_ohm_per_m', L_internal='L_internal_h_per_m', L_external='L_external_h_per_m',
           C='C_f_per_m', G='G_s_per_m', C0='C0_f_per_m')
_API = {value:key for key,value in _SI.items()}


def resolution_record(result):
    """Return finite real arrays and exact inputs; acceptance has limited scope."""
    if not isinstance(result, (LineResolutionAssessment,AdaptiveLineResolution,AdaptivePanelResolution)):
        raise TypeError('result must be a line resolution assessment')
    failure = result.failure
    record = dict(completed=result.completed, accepted=result.accepted,
        expected_evaluations=getattr(result,'expected_evaluations',None),
        tolerances={_SI[k]:dict(relative=v.relative,absolute=v.absolute) for k,v in result.tolerances.items()},
        evaluations=[dict(stage=row.stage,input=json.loads(row.input_json),
            names=list(row.result.names),frequency_hz=row.result.frequency.tolist(),
            quantities={_SI[k]:_metric(row.result,k).tolist() for k in _SI})
            for row in result.evaluations],
        comparisons=[dict(stage=row.stage,reference_index=row.reference_index,
            evaluation_index=row.evaluation_index,accepted=row.accepted,
            differences={_SI[k]:v.tolist() for k,v in row.differences.items()},
            allowances={_SI[k]:v.tolist() for k,v in row.allowances.items()})
            for row in result.comparisons],
        failure=None if failure is None else dict(stage=failure.stage,input=json.loads(failure.input_json),
            kind=failure.kind,message=failure.message))
    if isinstance(result,(AdaptiveLineResolution,AdaptivePanelResolution)):
        record.pop('expected_evaluations')
        selected=result.selected_evaluation
        levels = (dict(refinement_levels=result.refinement_levels) if isinstance(result,AdaptivePanelResolution)
                  else dict(mesh_levels=result.mesh_levels))
        record.update(stop_reason=result.stop_reason, **levels,
            expected_outer_evaluations=result.expected_outer_evaluations,
            outer_completed=result.outer_completed,
            selected_evaluation_index=next((i for i,row in enumerate(result.evaluations)
                                           if row is selected),None))
    return record


class LineResolutionDocument:
    """Saved finite mesh/domain comparison; no numerical accuracy certificate.

    The strict request stores a nested line, explicit outer lines, the finer
    mesh factor, a full-evaluation budget and unit-bearing tolerance keys.
    Parsing reuses ordinary resolution admission without field solves.
    """
    def __init__(self, line, *, outer_documents, tolerances, refinement_factor=.5, max_solves=4,
                 schema='sipi.line-resolution/1', max_levels=None):
        if not isinstance(line, TransmissionLineDocument):
            raise TypeError('line must be a TransmissionLineDocument')
        if (not isinstance(outer_documents,(list,tuple))
                or any(not isinstance(doc,TransmissionLineDocument) for doc in outer_documents)):
            raise TypeError('outer_documents must contain TransmissionLineDocument objects')
        if (not isinstance(tolerances,Mapping) or any(k not in _SI or not isinstance(v,ResolutionTolerance)
                                                    for k,v in tolerances.items())):
            raise ValueError('tolerances must select named quantities with ResolutionTolerance values')
        data=dict(schema=schema,line=line.to_dict(),
            outer_lines=[doc.to_dict() for doc in outer_documents],refinement_factor=refinement_factor,
            max_solves=max_solves,tolerances={_SI[k]:dict(relative=v.relative,absolute=v.absolute)
                                            for k,v in tolerances.items()})
        if schema=='sipi.line-resolution/2':data['max_levels']=max_levels
        elif max_levels is not None:raise ValueError('max_levels requires line-resolution/2')
        self._data=self._validate(data)

    @staticmethod
    def _validate(data):
        schema=data.get('schema') if isinstance(data,dict) else None
        if schema not in ('sipi.line-resolution/1','sipi.line-resolution/2'):
            raise ValueError('unsupported line-resolution schema')
        keys=('schema','line','outer_lines','refinement_factor','max_solves','tolerances')
        _keys(data,keys+(('max_levels',) if schema=='sipi.line-resolution/2' else ()),
              where='line resolution')
        values = [data['line']]
        if not isinstance(data['outer_lines'],list):
            raise ValueError('outer_lines must be an explicit list')
        values.extend(data['outer_lines'])
        if any(not isinstance(v,dict) or v.get('schema') not in
               tuple(f'sipi.transmission-line/{i}' for i in range(1,8)) for v in values):
            raise ValueError('resolution requires nested transmission-line/1 through /7')
        documents = [TransmissionLineDocument.from_dict(value) for value in values]
        tolerances = data['tolerances']
        if not isinstance(tolerances,dict) or not tolerances or set(tolerances)-set(_API):
            raise ValueError('resolution tolerances must use explicit supported SI quantity names')
        models = {}
        for key, value in tolerances.items():
            _keys(value,('relative','absolute'),where='resolution tolerance')
            models[_API[key]] = ResolutionTolerance(**value)
        if schema=='sipi.line-resolution/2':
            levels,_,models,stages=_adaptive_inputs(documents[0],documents[1:],models,
                data['refinement_factor'],data['max_levels'],data['max_solves'])
        else:
            models, stages = _resolution_inputs(documents[0],documents[1:],models,
                                             data['refinement_factor'],data['max_solves'])
        normalized=dict(schema=data['schema'],line=stages[0][1].to_dict(),
            outer_lines=[doc.to_dict() for _,doc in stages[2:]],
            refinement_factor=float(data['refinement_factor']),max_solves=data['max_solves'],
            tolerances={_SI[k]:dict(relative=v.relative,absolute=v.absolute) for k,v in models.items()})
        if schema=='sipi.line-resolution/2':normalized['max_levels']=levels
        return normalized

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
        adaptive=data['schema']=='sipi.line-resolution/2'
        if (3 if adaptive else 2)+len(data['outer_lines'])>budget:
            raise ValueError('resolution evaluation budget exceeded before any field solve')
        options=dict(max_levels=data['max_levels']) if adaptive else {}
        operation=refine_line_resolution if adaptive else assess_line_resolution
        return operation(TransmissionLineDocument.from_dict(data['line']),
            outer_documents=[TransmissionLineDocument.from_dict(v) for v in data['outer_lines']],
            tolerances={_API[k]:ResolutionTolerance(**v) for k,v in data['tolerances'].items()},
            refinement_factor=data['refinement_factor'],max_solves=min(data['max_solves'],budget),**options)
