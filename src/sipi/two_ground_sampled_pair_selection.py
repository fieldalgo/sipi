# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Fixed two-ground frequency-grid candidates with simultaneous joint bounds."""
from dataclasses import dataclass

from .sampled_panel_pair_selection import (SampledPanelForwardPairSelectionDocument,
    SampledPanelPairCandidateAssessment, SampledPanelPairSelectionResult,
    _sampled_selection_data, _analyze_sampled_selection)
from .two_ground_sampled_pair_study import TwoGroundSampledForwardPairStudyDocument
from .two_ground_sampled_pair_yield import TwoGroundSampledPairYieldAssessment, assess_two_ground_sampled_pair_yield

__all__ = ['TwoGroundSampledForwardPairSelectionDocument',
           'TwoGroundSampledPairCandidateAssessment', 'TwoGroundSampledPairSelectionResult']
_SCHEMA = 'sipi.two-ground-sampled-forward-pair-selection/1'


@dataclass(frozen=True)
class TwoGroundSampledPairCandidateAssessment(SampledPanelPairCandidateAssessment):
    assessment: TwoGroundSampledPairYieldAssessment


@dataclass(frozen=True)
class TwoGroundSampledPairSelectionResult(SampledPanelPairSelectionResult):
    candidates: tuple[TwoGroundSampledPairCandidateAssessment, ...]


class TwoGroundSampledForwardPairSelectionDocument(SampledPanelForwardPairSelectionDocument):
    """Explicit fixed-family selection on one finite two-ground frequency grid.

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
            source_type=TwoGroundSampledForwardPairStudyDocument)

    def analyze(self, *, max_evaluations=128):
        return _analyze_sampled_selection(self._data, self.dumps, max_evaluations=max_evaluations,
            source_type=TwoGroundSampledForwardPairStudyDocument, assess=assess_two_ground_sampled_pair_yield,
            candidate_type=TwoGroundSampledPairCandidateAssessment, result_type=TwoGroundSampledPairSelectionResult)
