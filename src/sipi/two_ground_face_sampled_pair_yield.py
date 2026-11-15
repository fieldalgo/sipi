# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit all-frequency joint iid acceptance of two-ground-face manufacturing rows."""
from dataclasses import dataclass

from .two_ground_sampled_pair_yield import TwoGroundSampledForwardPairYieldDocument as _WholeYield
from ._validation import _json_copy, _keys
from .sampled_panel_pair_yield import SampledPanelPairYieldAssessment, _acceptance, _assess_sampled_pair_yield
from .two_ground_face_sampled_pair_study import TwoGroundFaceSampledForwardPairStudy, TwoGroundFaceSampledForwardPairStudyDocument, TwoGroundFaceSampledForwardPairStudyRow

__all__ = ['TwoGroundFaceSampledPairYieldAssessment', 'TwoGroundFaceSampledForwardPairYieldDocument',
           'assess_two_ground_face_sampled_pair_yield']
_SCHEMA = 'sipi.two-ground-face-sampled-forward-pair-yield/1'


@dataclass(frozen=True)
class TwoGroundFaceSampledPairYieldAssessment(SampledPanelPairYieldAssessment):
    def to_dict(self):
        out = super().to_dict()
        out['scope'] = 'iid-stated-two-ground-face-frequency-grid-not-measured-production-yield'
        return out


def assess_two_ground_face_sampled_pair_yield(study, *, acceptance, confidence=.95, minimum_yield=None):
    """Joint inclusive limits across both quantities and every stated frequency.

    One manufactured row is one trial. Every unresolved whole-grid row stays
    in the original denominator, regardless of the number of frequency points.

    Uniform/normal iid draws may correlate variables within one row. The
    conservative interval envelopes possible unknown labels, not numerical,
    distribution or measurement error. No field solve occurs in this function.
    """
    return _assess_sampled_pair_yield(study, acceptance=acceptance, confidence=confidence,
        minimum_yield=minimum_yield, study_type=TwoGroundFaceSampledForwardPairStudy,
        source_type=TwoGroundFaceSampledForwardPairStudyDocument, row_type=TwoGroundFaceSampledForwardPairStudyRow,
        assessment_type=TwoGroundFaceSampledPairYieldAssessment)


class TwoGroundFaceSampledForwardPairYieldDocument(_WholeYield):
    """Strict saved joint acceptance of an explicit two-ground-face finite grid.

    Each named quantity requires a lower and/or upper bound at each frequency.
    This contract makes no assertion about frequencies between the samples."""
    def __init__(self, study, *, acceptance, confidence=.95, minimum_yield=None):
        if not isinstance(study, TwoGroundFaceSampledForwardPairStudyDocument):
            raise ValueError('study must be a TwoGroundFaceSampledForwardPairStudyDocument')
        self._assign(dict(schema=_SCHEMA, study=study.to_dict(), acceptance=acceptance,
                          confidence=confidence, minimum_yield=minimum_yield))

    def _assign(self, data):
        data = _json_copy(data)
        _keys(data, ('schema', 'study', 'acceptance', 'confidence', 'minimum_yield'),
              where='two-ground-face pair yield')
        if data['schema'] != _SCHEMA:
            raise ValueError('unsupported two-ground-face-sampled-forward-pair-yield schema')
        study = TwoGroundFaceSampledForwardPairStudyDocument.from_dict(data['study']).to_dict()
        if study['study']['sampling']['kind'] not in ('uniform', 'normal'):
            raise ValueError('joint yield requires iid uniform or normal samples')
        acceptance, level, target = _acceptance(data['acceptance'], data['confidence'], data['minimum_yield'], len(study['frequency_hz']))
        self._data = dict(schema=_SCHEMA, study=study, acceptance=acceptance,
                          confidence=level, minimum_yield=target)

    def analyze(self, *, max_evaluations=128):
        data = self.to_dict()
        study = TwoGroundFaceSampledForwardPairStudyDocument.from_dict(data['study']).analyze(max_evaluations=max_evaluations)
        return assess_two_ground_face_sampled_pair_yield(study, **{key:data[key] for key in
            ('acceptance', 'confidence', 'minimum_yield')})
