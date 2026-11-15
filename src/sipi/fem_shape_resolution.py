# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Finite mesh/open-domain observations for explicit checked FEM-current lines."""
from dataclasses import dataclass
import json
from .line_resolution import (ResolutionFailure,ResolutionEvaluation,LineResolutionAssessment,
                              _resolution_inputs,_compare)
from .fem_shape_line import FEMShapeTransmissionLineDocument,FEMShapeLineError

__all__ = ['FEMShapeResolutionFailure','FEMShapeResolutionAssessment','assess_fem_shape_line_resolution']


@dataclass(frozen=True)
class FEMShapeResolutionFailure(ResolutionFailure):
    details_json: str | None = None

    @property
    def details(self):return None if self.details_json is None else json.loads(self.details_json)


@dataclass(frozen=True)
class FEMShapeResolutionAssessment(LineResolutionAssessment):
    def to_dict(self):
        from .line_resolution_document import resolution_record
        out=resolution_record(self)
        for saved,row in zip(out['evaluations'],self.evaluations):
            saved['current_solver']=row.result.current_record()
        if self.failure is not None:out['failure']['details']=self.failure.details
        return out


def _fem_resolution_inputs(line,outer_documents,tolerances,refinement_factor,max_solves):
    return _resolution_inputs(line,outer_documents,tolerances,refinement_factor,max_solves,
                              document_type=FEMShapeTransmissionLineDocument)


def assess_fem_shape_line_resolution(line,*,outer_documents,tolerances,refinement_factor=.5,max_solves=4):
    """Compare base/finer/open-domain lines with explicit per-entry SI allowances.

    Preflight all inputs and the complete-line budget before fields. Require
    explicit edge_size/far_size/grade and scale only these settings. Each outer
    input uses the refined mesh settings and expands an open side or topmost
    layer beneath an open top, preserving physical geometry, interfaces, metals,
    materials, frequency and ports. Moving a grounded plane is not refinement.

    Reuse ResolutionTolerance for R, L_internal, L_external, C, G and C0. Every
    selected entry/frequency uses absolute + relative*max(abs(base),abs(actual)),
    with no small-entry floor. Mesh compares with base; each outer compares with
    the finer input. Every line retains its current derivative and original
    gradient/metal gates. The budget counts line attempts, not internal solves.

    A completed disagreement is unaccepted. A field/comparison failure retains
    previous work and its exact input/stage, including typed current evidence,
    then stops; interruption propagates. Finite accepted observations are not
    absolute accuracy, asymptotic convergence or empirical-validity certificates.
    """
    tolerances,stages=_fem_resolution_inputs(line,outer_documents,tolerances,refinement_factor,max_solves)
    return _assess_fem_shape_resolution(tolerances, stages)


def _assess_fem_shape_resolution(tolerances, stages):
    evaluations=[];comparisons=[]
    for stage,doc in stages:
        text=doc.dumps()
        try:
            result=doc.analyze();evaluations.append(ResolutionEvaluation(stage,text,result))
            if stage!='base':
                index=0 if stage=='mesh' else 1
                comparisons.append(_compare(evaluations[index].result,result,tolerances,
                                            stage,index,len(evaluations)-1))
        except Exception as error:
            details=json.dumps(error.to_dict(),allow_nan=False) if isinstance(error,FEMShapeLineError) else None
            failure=FEMShapeResolutionFailure(stage,text,type(error).__name__,str(error),details)
            return FEMShapeResolutionAssessment(tolerances,evaluations,comparisons,len(stages),failure)
    return FEMShapeResolutionAssessment(tolerances,evaluations,comparisons,len(stages))
