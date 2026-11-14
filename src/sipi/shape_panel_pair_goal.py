# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit shape-current pair goals over the existing bounded search contract."""
from dataclasses import dataclass

from .panel_pair_goal import (PanelPairRefinement, PanelForwardPairDesign,
                              _refinements, _seek_panel_pair_goal)
from .shape_panel_line import (ShapePanelTransmissionLineDocument,
                              ShapePanelTransmissionLineResult, shape_current_record)

__all__ = ['ShapePanelPairRefinement', 'ShapePanelForwardPairDesign',
           'seek_shape_panel_forward_pair_impedances']


def _shape_refinements(text):
    original = ShapePanelTransmissionLineDocument.loads(text)
    fraction = original.to_dict()['step_fraction']
    return {stage: ShapePanelTransmissionLineDocument(doc, step_fraction=fraction)
            for stage, doc in _refinements(original.line.dumps()).items()}


@dataclass(frozen=True)
class ShapePanelPairRefinement(PanelPairRefinement):
    result: ShapePanelTransmissionLineResult

    @property
    def document(self):
        return ShapePanelTransmissionLineDocument.loads(self.evaluation.input_json)


@dataclass(frozen=True)
class ShapePanelForwardPairDesign(PanelForwardPairDesign):
    result: ShapePanelTransmissionLineResult
    refinements: tuple[ShapePanelPairRefinement, ...]

    @property
    def document(self):
        return ShapePanelTransmissionLineDocument.loads(self.input_json)

    def to_dict(self):
        out = super().to_dict()
        out['scope'] = 'bounded-two-parameter-shape-panel-forward-pair-impedance-goal'
        out['current_solver'] = shape_current_record(self.result.current_factors,
                                                     self.result.panel_settings)
        for saved, row in zip(out['refinements'], self.refinements):
            saved['current_solver'] = shape_current_record(row.result.current_factors,
                                                           row.result.panel_settings)
        return out


def seek_shape_panel_forward_pair_impedances(factory, bounds, targets, *, tolerances,
                                            initial=None, max_evaluations=64):
    """Seek Re(Zdd), Re(Zcc) using explicitly selected shape-current line inputs.

    Two positive bounded parameters, one fixed positive frequency, two ordered
    signals and zero length are required. Panel controls and shape step_fraction
    stay fixed during search. Three actual reserved evaluations check the frozen
    chosen input with volume-only, panel-only and joint refinements. Every result
    must meet both targets and the existing 0.005 relative refinement limits.

    Budgets count complete uncached line attempts, including failed attempts and
    optimizer probes, not internal panel solves. The chosen and refined results
    retain complete current samples; search history retains inputs/impedances.
    ForwardPairGoalError retains partial history and its original cause chain,
    including ShapePanelLineError's partial-current details. Interrupts propagate.
    Outer-domain sufficiency, uniqueness and absolute accuracy are not certified.
    """
    return _seek_panel_pair_goal(factory, bounds, targets, tolerances=tolerances,
        initial=initial, max_evaluations=max_evaluations,
        document_type=ShapePanelTransmissionLineDocument, refinements=_shape_refinements,
        physical_line=lambda doc: doc.line.line, settings=lambda doc: doc.current_options,
        refinement_type=ShapePanelPairRefinement, design_type=ShapePanelForwardPairDesign)
