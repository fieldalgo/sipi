# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Fixed two-ground-face frequency-grid candidates with simultaneous joint bounds."""
from dataclasses import dataclass

from .sampled_panel_pair_selection import (SampledPanelForwardPairSelectionDocument,
    SampledPanelPairCandidateAssessment, SampledPanelPairSelectionResult,
    _sampled_selection_data, _analyze_sampled_selection)
from .two_ground_face_sampled_pair_study import TwoGroundFaceSampledForwardPairStudyDocument
from .two_ground_face_sampled_pair_yield import TwoGroundFaceSampledPairYieldAssessment, assess_two_ground_face_sampled_pair_yield

__all__ = ['TwoGroundFaceSampledForwardPairSelectionDocument',
           'TwoGroundFaceSampledPairCandidateAssessment', 'TwoGroundFaceSampledPairSelectionResult']
_SCHEMA = 'sipi.two-ground-face-sampled-forward-pair-selection/1'


@dataclass(frozen=True)
class TwoGroundFaceSampledPairCandidateAssessment(SampledPanelPairCandidateAssessment):
    assessment: TwoGroundFaceSampledPairYieldAssessment


@dataclass(frozen=True)
class TwoGroundFaceSampledPairSelectionResult(SampledPanelPairSelectionResult):
    candidates: tuple[TwoGroundFaceSampledPairCandidateAssessment, ...]


class TwoGroundFaceSampledForwardPairSelectionDocument(SampledPanelForwardPairSelectionDocument):
    """Explicit fixed-family selection on one finite two-ground-face frequency grid.

    Each of 1..32 candidates retains its source geometry, materials, metal laws,
    panel settings and iid sampling model. They share an exact frequency vector,
    named acceptance bounds and cost unit. Original Bonferroni allocation covers
    the fixed family; the row event is the intersection of all frequency limits.
    Every planned row counts against the budget, including unresolved rows.
    The cheapest certified member is not a global or continuous optimum.
    """
    def __init__(self, candidates, *, cost_unit, acceptance, minimum_yield, confidence=.95):
        self._assign(dict(schema=_SCHEMA, candidates=candidates, cost_unit=cost_unit,
                          acceptance=acceptance, minimum_yield=minimum_yield, confidence=confidence))

    def _assign(self, data):
        self._data = _sampled_selection_data(data, schema=_SCHEMA,
            source_type=TwoGroundFaceSampledForwardPairStudyDocument)

    def analyze(self, *, max_evaluations=128):
        return _analyze_sampled_selection(self._data, self.dumps, max_evaluations=max_evaluations,
            source_type=TwoGroundFaceSampledForwardPairStudyDocument, assess=assess_two_ground_face_sampled_pair_yield,
            candidate_type=TwoGroundFaceSampledPairCandidateAssessment, result_type=TwoGroundFaceSampledPairSelectionResult)
