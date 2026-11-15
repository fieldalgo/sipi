# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Bounded paired goals across explicit two-ground-face frequency grids."""
from dataclasses import dataclass

from ._two_ground_mesh_reuse import _mesh_reuse_scope

from .sampled_panel_pair_goal import (SampledPanelPairRefinement, SampledPanelForwardPairDesign,
                                     _seek_sampled_panel_pair_goal)
from .two_ground_face_pair_goal import _refinements
from .two_ground_face_panel_line import (TwoGroundFacePanelTransmissionLineDocument,
                                   TwoGroundFacePanelTransmissionLineResult)

__all__ = ['TwoGroundFaceSampledPairRefinement', 'TwoGroundFaceSampledForwardPairDesign',
           'seek_two_ground_face_sampled_forward_pair_impedances']


@dataclass(frozen=True)
class TwoGroundFaceSampledPairRefinement(SampledPanelPairRefinement):
    result: TwoGroundFacePanelTransmissionLineResult

    @property
    def document(self):
        return TwoGroundFacePanelTransmissionLineDocument.loads(self.evaluation.input_json)


@dataclass(frozen=True)
class TwoGroundFaceSampledForwardPairDesign(SampledPanelForwardPairDesign):
    result: TwoGroundFacePanelTransmissionLineResult
    refinements: tuple[TwoGroundFaceSampledPairRefinement, ...]

    @property
    def document(self):
        return TwoGroundFacePanelTransmissionLineDocument.loads(self.input_json)

    def to_dict(self):
        out = super().to_dict()
        out['scope'] = 'bounded-two-parameter-finite-frequency-two-ground-face-forward-pair-goal'
        out['current_solver'] = self.result.current_record()
        out['dielectric_mesh'] = self.result.mesh_record()
        for saved, row in zip(out['refinements'], self.refinements):
            saved['current_solver'] = row.result.current_record()
            saved['dielectric_mesh'] = row.result.mesh_record()
        return out


def seek_two_ground_face_sampled_forward_pair_impedances(factory, bounds, frequencies, targets, *,
                                                   tolerances, initial=None, max_evaluations=64):
    """Seek both forward impedances at every supplied frequency on one grid.

    Require two positive bounded parameters, 2..64 increasing positive
    frequencies, two ordered signals, zero length and positive (N,2) target
    and absolute-tolerance matrices. Frequency, signal order and current
    controls remain fixed. Three reserved attempts refine the frozen selected
    document on volume-only, panel-only and joint axes. Every target and the
    original 0.005 relative refinement limits must pass at every frequency.

    Budgets count uncached whole-line attempts, including failed attempts and
    optimizer probes. SampledPanelForwardPairGoalError retains history, exact
    failed input and the original typed cause chain; interrupts propagate.
    Selected and refined results retain actual current and dielectric meshes.
    No continuous-band, outer-domain, global optimum, uniqueness or absolute
    accuracy guarantee follows. A factory callable is not serialized.
    """
    with _mesh_reuse_scope():
        return _seek_sampled_panel_pair_goal(factory, bounds, frequencies, targets,
            tolerances=tolerances, initial=initial, max_evaluations=max_evaluations,
            document_type=TwoGroundFacePanelTransmissionLineDocument, refinements=_refinements,
            physical_line=lambda doc: doc, settings=lambda doc: doc.current_options,
            refinement_type=TwoGroundFaceSampledPairRefinement, design_type=TwoGroundFaceSampledForwardPairDesign)
