# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit bounded refinement of checked FEM-current lines."""
from dataclasses import dataclass
import json
from .adaptive_line_resolution import AdaptiveLineResolution,_refine_line_resolution
from .fem_shape_resolution import FEMShapeResolutionFailure
from .fem_shape_line import FEMShapeTransmissionLineDocument,FEMShapeLineError

__all__ = ['FEMShapeAdaptiveResolution','refine_fem_shape_line_resolution']


@dataclass(frozen=True)
class FEMShapeAdaptiveResolution(AdaptiveLineResolution):
    def to_dict(self):
        from .line_resolution_document import resolution_record
        out=resolution_record(self)
        for saved,row in zip(out['evaluations'],self.evaluations):
            saved['current_solver']=row.result.current_record()
        if self.failure is not None:out['failure']['details']=self.failure.details
        return out


def _fem_failure(stage,text,error):
    details=json.dumps(error.to_dict(),allow_nan=False) if isinstance(error,FEMShapeLineError) else None
    return FEMShapeResolutionFailure(stage,text,type(error).__name__,str(error),details)


def refine_fem_shape_line_resolution(line,*,outer_documents,tolerances,refinement_factor=.5,
                                     max_levels=4,max_solves=8):
    """Require two consecutive finer-mesh passes, then all explicit outer checks.

    The exact ResolutionTolerance entrywise rule and every selected frequency
    apply without floors. Refine only edge_size/far_size/grade; retain physical
    geometry and all current/material gates. Outer templates use the first finer
    mesh recipe; replace only that recipe with the selected finer settings.

    Count whole line attempts, reserving all outer attempts before each finer
    solve. Completed level-limited/outer disagreement stays unaccepted. Budget
    exhaustion and extraction/setup failure stay incomplete. Retain every input,
    current observation, comparison and typed partial cause; propagate interrupts.
    A selected result exists only after two passes and all outer checks. This
    finite procedure is not an accuracy certificate and changes no default method.
    """
    return _refine_line_resolution(line,outer_documents=outer_documents,tolerances=tolerances,
        refinement_factor=refinement_factor,max_levels=max_levels,max_solves=max_solves,
        document_type=FEMShapeTransmissionLineDocument,assessment_type=FEMShapeAdaptiveResolution,
        failure_factory=_fem_failure)
