# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Elementwise finite agreement along separate panel, volume and domain axes."""
from dataclasses import dataclass
from collections.abc import Mapping

from .panel_line import PanelTransmissionLineDocument
from .line_resolution import (LineResolutionAssessment, ResolutionEvaluation,
                              ResolutionFailure, _resolution_inputs, _compare)
from .sampling import _integer

__all__ = ['PanelResolutionAssessment', 'assess_panel_line_resolution']


@dataclass(frozen=True)
class PanelResolutionAssessment(LineResolutionAssessment):
    """Separate finite panel/volume comparisons and joint-to-outer checks.

    Each selected matrix entry and frequency must meet its explicit absolute
    plus relative tolerance. No small-entry denominator floor is used.
    Acceptance is finite agreement, not an absolute error certificate.
    """


def assess_panel_line_resolution(line, *, refined_panel_options, outer_documents,
                                 tolerances, refinement_factor=.5, max_solves=6):
    """Evaluate base, volume-only, panel-only, joint and explicit outer inputs.

    The three panel controls are explicit; none may decrease and at least one
    must increase. Volume refinement changes only edge_size, far_size and
    grade. Outer inputs keep joint mesh/panel settings except ground_modes,
    which may increase to resolve the larger domain. All physical admission
    rules and resource limits of the selected panel line remain active.

    Volume and panel results each compare with base. The joint result compares
    separately with both; each outer result compares with joint. Every full
    line evaluation runs once. A field failure retains prior results and its
    exact input/stage, then stops. User interrupts propagate. Inputs, budgets
    and physically unchanged outer domains are checked before any field solve.
    """
    if not isinstance(line,PanelTransmissionLineDocument):
        raise TypeError('line must be a PanelTransmissionLineDocument')
    if (not isinstance(outer_documents,(list,tuple)) or not outer_documents
            or any(not isinstance(doc,PanelTransmissionLineDocument) for doc in outer_documents)):
        raise ValueError('provide one or more explicit panel outer documents')
    limit=_integer(max_solves,5,16)
    count=4+len(outer_documents)
    if count>limit:
        raise ValueError('panel resolution budget exceeded before any field solve')
    if not isinstance(refined_panel_options,Mapping):
        raise ValueError('refined_panel_options must explicitly specify all three panel controls')
    base=PanelTransmissionLineDocument.loads(line.dumps())
    raw=base.to_dict();raw['panel']=dict(refined_panel_options)
    panel=PanelTransmissionLineDocument.from_dict(raw)
    old,new=base.panel_options,panel.panel_options
    if any(new[k]<old[k] for k in old) or new==old:
        raise ValueError('panel controls must not decrease and at least one must increase')
    for outer in outer_documents:
        data=outer.to_dict();options=outer.panel_options
        if (data['schema']!=raw['schema'] or options['panels_per_edge']!=new['panels_per_edge']
                or options['interpolation_degree']!=new['interpolation_degree']
                or options['ground_modes']<new['ground_modes']):
            raise ValueError('outer documents must preserve the joint panel method and resolution')
    tolerances, prepared=_resolution_inputs(base.line,[doc.line for doc in outer_documents],
                                             tolerances,refinement_factor,limit)
    raw=base.to_dict();raw['line']=prepared[1][1].to_dict()
    volume=PanelTransmissionLineDocument.from_dict(raw)
    raw['panel']=new
    joint=PanelTransmissionLineDocument.from_dict(raw)
    stages=[('base',base,()),('volume',volume,((0,'volume'),)),
            ('panel',panel,((0,'panel'),)),
            ('joint',joint,((1,'joint:panel'),(2,'joint:volume')))]
    stages.extend((f'outer:{i}',PanelTransmissionLineDocument.loads(doc.dumps()),
                   ((3,f'outer:{i}'),)) for i,doc in enumerate(outer_documents))
    evaluations,comparisons=[],[]
    for stage,doc,references in stages:
        text=doc.dumps()
        try:
            result=doc.analyze()
            evaluations.append(ResolutionEvaluation(stage,text,result))
            for index,label in references:
                comparisons.append(_compare(evaluations[index].result,result,tolerances,
                                             label,index,len(evaluations)-1))
        except Exception as error:
            failure=ResolutionFailure(stage,text,type(error).__name__,str(error))
            return PanelResolutionAssessment(tolerances,evaluations,comparisons,count,failure)
    return PanelResolutionAssessment(tolerances,evaluations,comparisons,count)
