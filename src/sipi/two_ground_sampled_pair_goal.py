# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Bounded paired goals across explicit two-ground frequency grids."""
from dataclasses import dataclass

from .sampled_panel_pair_goal import (SampledPanelPairRefinement, SampledPanelForwardPairDesign,
                                     _seek_sampled_panel_pair_goal)
from .two_ground_pair_goal import _refinements
from .two_ground_panel_line import (TwoGroundPanelTransmissionLineDocument,
                                   TwoGroundPanelTransmissionLineResult)

__all__ = ['TwoGroundSampledPairRefinement', 'TwoGroundSampledForwardPairDesign',
           'seek_two_ground_sampled_forward_pair_impedances']


@dataclass(frozen=True)
class TwoGroundSampledPairRefinement(SampledPanelPairRefinement):
    result: TwoGroundPanelTransmissionLineResult

    @property
    def document(self):
        return TwoGroundPanelTransmissionLineDocument.loads(self.evaluation.input_json)


@dataclass(frozen=True)
class TwoGroundSampledForwardPairDesign(SampledPanelForwardPairDesign):
    result: TwoGroundPanelTransmissionLineResult
    refinements: tuple[TwoGroundSampledPairRefinement, ...]

    @property
    def document(self):
        return TwoGroundPanelTransmissionLineDocument.loads(self.input_json)

    def to_dict(self):
        out = super().to_dict()
        out['scope'] = 'bounded-two-parameter-finite-frequency-two-ground-forward-pair-goal'
        out['current_solver'] = self.result.current_record()
        out['dielectric_mesh'] = self.result.mesh_record()
        for saved, row in zip(out['refinements'], self.refinements):
            saved['current_solver'] = row.result.current_record()
            saved['dielectric_mesh'] = row.result.mesh_record()
        return out


def seek_two_ground_sampled_forward_pair_impedances(factory, bounds, frequencies, targets, *,
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
    return _seek_sampled_panel_pair_goal(factory, bounds, frequencies, targets,
        tolerances=tolerances, initial=initial, max_evaluations=max_evaluations,
        document_type=TwoGroundPanelTransmissionLineDocument, refinements=_refinements,
        physical_line=lambda doc: doc, settings=lambda doc: doc.current_options,
        refinement_type=TwoGroundSampledPairRefinement, design_type=TwoGroundSampledForwardPairDesign)
