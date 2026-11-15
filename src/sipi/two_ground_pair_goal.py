# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Bounded forward-pair impedance goals with explicit two-ground currents."""
from dataclasses import dataclass
import json

from ._two_ground_current_reuse import _current_reuse_scope
from ._two_ground_mesh_reuse import _mesh_reuse_scope

from .panel_pair_goal import PanelPairRefinement, PanelForwardPairDesign, _seek_panel_pair_goal
from .two_ground_panel_line import TwoGroundPanelTransmissionLineDocument, TwoGroundPanelTransmissionLineResult

__all__ = ['TwoGroundPairRefinement', 'TwoGroundForwardPairDesign',
           'seek_two_ground_forward_pair_impedances']


def _refinements(text):
    out = {}
    for stage in ('volume-refinement', 'panel-refinement', 'joint-refinement'):
        data = json.loads(text)
        if stage != 'panel-refinement':
            for key in ('edge_size', 'far_size', 'grade'):
                data['cross_section']['mesh'][key] /= 2
        if stage != 'volume-refinement':
            data['panel']['panels_per_edge'] *= 2
        out[stage] = TwoGroundPanelTransmissionLineDocument.from_dict(data)
    return out


@dataclass(frozen=True)
class TwoGroundPairRefinement(PanelPairRefinement):
    result: TwoGroundPanelTransmissionLineResult

    @property
    def document(self):
        return TwoGroundPanelTransmissionLineDocument.loads(self.evaluation.input_json)


@dataclass(frozen=True)
class TwoGroundForwardPairDesign(PanelForwardPairDesign):
    result: TwoGroundPanelTransmissionLineResult
    refinements: tuple[TwoGroundPairRefinement, ...]

    @property
    def document(self):
        return TwoGroundPanelTransmissionLineDocument.loads(self.input_json)

    def to_dict(self):
        out = super().to_dict()
        out['scope'] = 'bounded-two-parameter-two-ground-forward-pair-impedance-goal'
        out['current_solver'] = self.result.current_record()
        out['dielectric_mesh'] = self.result.mesh_record()
        for saved, row in zip(out['refinements'], self.refinements):
            saved['current_solver'] = row.result.current_record()
            saved['dielectric_mesh'] = row.result.mesh_record()
        return out


def seek_two_ground_forward_pair_impedances(factory, bounds, targets, *, tolerances,
                                           initial=None, max_evaluations=64):
    """Seek Re(Zdd), Re(Zcc) with the existing bounded two-parameter search.

    The factory returns a TwoGroundPanelTransmissionLineDocument with two
    ordered signals, one positive frequency, zero length and fixed panel
    controls. Full forward characteristic matrices retain asymmetric coupling.
    The two targets describe separate Ic=0 and Id=0 mixed-coordinate launches.

    Reserve three actual attempts for volume-only, panel-only and joint
    refinements of the frozen selected input. Halve resolved edge/far/grade
    and double panel count on their respective axes, keeping other controls.
    Every refined result must meet both absolute targets. The existing 0.005
    relative limits apply against nominal and joint versus each single-axis
    refinement. Admit all refined inputs before the first search field solve.

    Every uncached failed attempt and optimizer probe counts. ForwardPairGoalError
    retains history and the original typed TwoGroundPanelLineError cause;
    interrupts propagate. The unchanged budget bounds attempts, not time or
    memory. Outer-domain adequacy, uniqueness, global optimum and empirical
    accuracy are separate questions. This API does not serialize a callable.
    """
    with _current_reuse_scope(), _mesh_reuse_scope():
        return _seek_panel_pair_goal(factory, bounds, targets, tolerances=tolerances,
            initial=initial, max_evaluations=max_evaluations,
            document_type=TwoGroundPanelTransmissionLineDocument, refinements=_refinements,
            physical_line=lambda doc: doc, settings=lambda doc: doc.current_options,
            refinement_type=TwoGroundPairRefinement, design_type=TwoGroundForwardPairDesign)
