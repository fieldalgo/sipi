# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit bounded volume/panel refinement plans for two-ground face-current lines."""
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
import json

from .adaptive_panel_resolution import AdaptivePanelResolution, _run_adaptive_panel_resolution
from .two_ground_face_resolution import _two_ground_face_resolution_inputs
from .fem_shape_resolution import FEMShapeResolutionFailure
from .two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument, TwoGroundFacePanelLineError
from .sampling import _integer

__all__ = ['TwoGroundFaceResolutionRefinement','AdaptiveTwoGroundFaceResolution',
           'refine_two_ground_face_line_resolution']


@dataclass(frozen=True)
class TwoGroundFaceResolutionRefinement:
    """Snapshot explicit next panel settings and outer inputs at that mesh level."""
    panel_options: Mapping
    outer_documents: tuple

    def __post_init__(self):
        if not isinstance(self.panel_options, Mapping):
            raise ValueError('panel_options must specify all three controls')
        if (not isinstance(self.outer_documents, (tuple,list)) or not self.outer_documents
                or any(not isinstance(d, TwoGroundFacePanelTransmissionLineDocument) for d in self.outer_documents)):
            raise ValueError('each refinement needs explicit two-ground face outer documents')
        object.__setattr__(self, 'panel_options', MappingProxyType(dict(self.panel_options)))
        object.__setattr__(self, 'outer_documents', tuple(
            TwoGroundFacePanelTransmissionLineDocument.loads(d.dumps()) for d in self.outer_documents))


@dataclass(frozen=True)
class AdaptiveTwoGroundFaceResolution(AdaptivePanelResolution):
    """Finite agreement history retaining complete and partial current work."""
    def to_dict(self):
        from .line_resolution_document import resolution_record
        out = resolution_record(self)
        out['scope'] = 'two-ground-face-adaptive-finite-resolution-not-absolute-accuracy'
        for saved,row in zip(out['evaluations'],self.evaluations):
            saved['current_solver'] = row.result.current_record()
            saved['dielectric_mesh'] = row.result.mesh_record()
        if self.failure is not None:
            out['failure']['details'] = self.failure.details
        return out


def _adaptive_two_ground_face_inputs(line, refinements, tolerances, factor, max_solves):
    limit = _integer(max_solves, 8, 32)
    if (not isinstance(refinements, (tuple,list)) or not 2 <= len(refinements) <= 4
            or any(not isinstance(step, TwoGroundFaceResolutionRefinement) for step in refinements)):
        raise ValueError('provide two to four explicit TwoGroundFaceResolutionRefinement steps')
    current,plans,domains = line,[],None
    for step in refinements:
        checked,stages = _two_ground_face_resolution_inputs(current,step.panel_options,
            step.outer_documents,tolerances,factor,16)
        sizes = tuple((doc.to_dict()['cross_section']['box']['width'],
                       doc.to_dict()['cross_section']['layers'][-1]['thickness'])
                      for _,doc,_ in stages[4:])
        if domains is not None and sizes != domains:
            raise ValueError('outer domain sizes and order must remain fixed across refinements')
        domains = sizes
        plans.append(stages)
        current = stages[3][1]
    if 7 + len(domains) > limit:
        raise ValueError('two refinement steps and all outer checks exceed budget before any field solve')
    return limit,checked,tuple(plans)


def refine_two_ground_face_line_resolution(line, *, refinements, tolerances,
                                      refinement_factor=.5, max_solves=16):
    """Require two consecutive four-way passes before explicit outer checks.

    All two to four planned levels are admitted before fields. Every selected
    entry/frequency uses the existing absolute-plus-relative SI allowance,
    without a small-entry floor. Previous joint results are reused. Three
    next-step batches plus outer checks are reserved within max_solves (8..32).
    Physical ground planes, face laws and reference metals remain fixed.
    Each extraction retains its original current and material gates.

    Field failure retains the exact attempted input, prior work and original
    typed cause and actual dielectric mesh. Interrupts propagate. Outer disagreement stops the
    plan; no further refinement disguises it. Finite accepted comparisons are
    not an absolute accuracy, continuous-band or physical-model certificate.
    """
    limit,checked,plans = _adaptive_two_ground_face_inputs(line,refinements,tolerances,
        refinement_factor,max_solves)
    def failure(stage,text,error):
        details = json.dumps(error.to_dict(),allow_nan=False) if isinstance(error,TwoGroundFacePanelLineError) else None
        return FEMShapeResolutionFailure(stage,text,type(error).__name__,str(error),details)
    return _run_adaptive_panel_resolution(limit,checked,plans,
        result_type=AdaptiveTwoGroundFaceResolution,failure_factory=failure)
