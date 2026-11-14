# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Bounded paired goals across a finite grid using explicit shape currents."""
from dataclasses import dataclass
from .sampled_panel_pair_goal import (SampledPanelPairRefinement,SampledPanelForwardPairDesign,
                                     _seek_sampled_panel_pair_goal)
from .shape_panel_pair_goal import _shape_refinements
from .shape_panel_line import (ShapePanelTransmissionLineDocument,
                              ShapePanelTransmissionLineResult,shape_current_record)

__all__ = ['ShapeSampledPanelPairRefinement','ShapeSampledPanelForwardPairDesign',
           'seek_shape_sampled_panel_forward_pair_impedances']


@dataclass(frozen=True)
class ShapeSampledPanelPairRefinement(SampledPanelPairRefinement):
    result: ShapePanelTransmissionLineResult

    @property
    def document(self):
        return ShapePanelTransmissionLineDocument.loads(self.evaluation.input_json)


@dataclass(frozen=True)
class ShapeSampledPanelForwardPairDesign(SampledPanelForwardPairDesign):
    result: ShapePanelTransmissionLineResult
    refinements: tuple[ShapeSampledPanelPairRefinement,...]

    @property
    def document(self):
        return ShapePanelTransmissionLineDocument.loads(self.input_json)

    def to_dict(self):
        out=super().to_dict()
        out['scope']='bounded-two-parameter-finite-frequency-shape-panel-forward-pair-goal'
        out['current_solver']=shape_current_record(self.result.current_factors,self.result.panel_settings)
        for saved,row in zip(out['refinements'],self.refinements):
            saved['current_solver']=shape_current_record(row.result.current_factors,row.result.panel_settings)
        return out


def seek_shape_sampled_panel_forward_pair_impedances(factory,bounds,frequencies,targets,*,tolerances,
                                                     initial=None,max_evaluations=64):
    """Seek Re(Zdd), Re(Zcc) at every supplied frequency on one frozen grid.

    Two positive bounded parameters, 2..64 increasing positive frequencies,
    two ordered signals, zero length and explicit positive (N,2) target and
    tolerance matrices are required. Frequency, signal order, panel controls
    and the shape step remain fixed. Three reserved actual line batches check
    volume-only, panel-only and joint refinements against every target and the
    unchanged 0.005 relative refinement limits.

    Budgets count uncached whole-line attempts, including failed attempts and
    optimizer probes. History preserves inputs/values; selected and refined
    results also retain complete current records. SampledPanelForwardPairGoalError
    keeps the original history, attempts and cause chain, including detailed
    shape-line failures. Interrupts propagate. A finite grid is not a continuous
    band, outer-domain, global optimum, uniqueness or absolute accuracy guarantee.
    """
    return _seek_sampled_panel_pair_goal(factory,bounds,frequencies,targets,
        tolerances=tolerances,initial=initial,max_evaluations=max_evaluations,
        document_type=ShapePanelTransmissionLineDocument,refinements=_shape_refinements,
        physical_line=lambda doc:doc.line.line,settings=lambda doc:doc.current_options,
        refinement_type=ShapeSampledPanelPairRefinement,design_type=ShapeSampledPanelForwardPairDesign)
