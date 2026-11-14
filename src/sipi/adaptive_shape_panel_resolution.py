# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit bounded volume/panel refinement plans for shape-current lines."""
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
import json

from .adaptive_panel_resolution import AdaptivePanelResolution, _run_adaptive_panel_resolution
from .shape_panel_resolution import _shape_panel_resolution_inputs, ShapePanelResolutionFailure
from .shape_panel_line import ShapePanelTransmissionLineDocument, ShapePanelLineError, shape_current_record
from .sampling import _integer

__all__ = ['ShapePanelResolutionRefinement','AdaptiveShapePanelResolution',
           'refine_shape_panel_line_resolution']


@dataclass(frozen=True)
class ShapePanelResolutionRefinement:
    """Snapshot explicit next panel settings and outer inputs at that mesh level."""
    panel_options: Mapping
    outer_documents: tuple

    def __post_init__(self):
        if not isinstance(self.panel_options, Mapping):
            raise ValueError('panel_options must specify all three controls')
        if (not isinstance(self.outer_documents, (tuple,list)) or not self.outer_documents
                or any(not isinstance(d, ShapePanelTransmissionLineDocument) for d in self.outer_documents)):
            raise ValueError('each refinement needs explicit shape-panel outer documents')
        object.__setattr__(self, 'panel_options', MappingProxyType(dict(self.panel_options)))
        object.__setattr__(self, 'outer_documents', tuple(
            ShapePanelTransmissionLineDocument.loads(d.dumps()) for d in self.outer_documents))


@dataclass(frozen=True)
class AdaptiveShapePanelResolution(AdaptivePanelResolution):
    """Finite agreement history retaining complete and partial current work."""
    def to_dict(self):
        from .line_resolution_document import resolution_record
        out = resolution_record(self)
        for saved,row in zip(out['evaluations'],self.evaluations):
            saved['current_solver'] = shape_current_record(row.result.current_factors,row.result.panel_settings)
        if self.failure is not None:
            out['failure']['details'] = self.failure.details
        return out


def _adaptive_shape_inputs(line, refinements, tolerances, factor, max_solves):
    limit = _integer(max_solves, 8, 32)
    if (not isinstance(refinements, (tuple,list)) or not 2 <= len(refinements) <= 4
            or any(not isinstance(step, ShapePanelResolutionRefinement) for step in refinements)):
        raise ValueError('provide two to four explicit ShapePanelResolutionRefinement steps')
    current,plans,domains = line,[],None
    for step in refinements:
        checked,stages = _shape_panel_resolution_inputs(current,step.panel_options,
            step.outer_documents,tolerances,factor,16)
        sizes = tuple((doc.line.line.to_dict()['cross_section']['box']['width'],
                       doc.line.line.to_dict()['cross_section']['layers'][-1]['thickness'])
                      for _,doc,_ in stages[4:])
        if domains is not None and sizes != domains:
            raise ValueError('outer domain sizes and order must remain fixed across refinements')
        domains = sizes
        plans.append(stages)
        current = stages[3][1]
    if 7 + len(domains) > limit:
        raise ValueError('two refinement steps and all outer checks exceed budget before any field solve')
    return limit,checked,tuple(plans)


def refine_shape_panel_line_resolution(line, *, refinements, tolerances,
                                      refinement_factor=.5, max_solves=16):
    """Require two consecutive four-way passes before explicit outer checks.

    All two to four planned levels are admitted before fields. Every selected
    entry/frequency uses the existing absolute-plus-relative SI allowance,
    without a small-entry floor. Previous joint results are reused. Three
    next-step batches plus outer checks are reserved within max_solves (8..32).
    The shape fraction remains fixed; each extraction retains its two-step gate.

    Field failure retains the exact attempted input, prior work and original
    partial-current cause. Interrupts propagate. Outer disagreement stops the
    plan; no further refinement disguises it. Finite accepted comparisons are
    not an absolute accuracy, continuous-band or physical-model certificate.
    """
    limit,checked,plans = _adaptive_shape_inputs(line,refinements,tolerances,
        refinement_factor,max_solves)
    def failure(stage,text,error):
        details = json.dumps(error.to_dict(),allow_nan=False) if isinstance(error,ShapePanelLineError) else None
        return ShapePanelResolutionFailure(stage,text,type(error).__name__,str(error),details)
    return _run_adaptive_panel_resolution(limit,checked,plans,
        result_type=AdaptiveShapePanelResolution,failure_factory=failure)
