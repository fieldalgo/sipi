# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Finite-grid joint acceptance across explicit numerical resolutions."""
from dataclasses import dataclass
import json

from sipi.panel_resolution_yield import PanelPairResolutionYieldAssessment
from sipi.two_ground_face_sampled_pair_study import TwoGroundFaceSampledForwardPairStudy, TwoGroundFaceSampledForwardPairStudyDocument
from sipi.two_ground_face_sampled_pair_yield import assess_two_ground_face_sampled_pair_yield
from sipi.yield_assessment import _interval

__all__ = ['TwoGroundFaceSampledPairResolutionYieldAssessment', 'assess_two_ground_face_sampled_pair_resolution_yield']


@dataclass(frozen=True)
class TwoGroundFaceSampledPairResolutionYieldAssessment(PanelPairResolutionYieldAssessment):
    """One manufactured sample is one trial across the entire finite grid."""
    @property
    def frequencies(self):return self.assessments[0].study.frequencies

    def to_dict(self):
        data = super().to_dict()
        data.update(frequencies_hz=list(self.frequencies),
            acceptance=self.assessments[0].to_dict()['acceptance'],
            event='all-sampled-paired-limits-with-resolution-disagreement-unresolved',
            scope='iid-finite-frequency-resolution-envelope-not-a-discretization-error-bound')
        return data


def _resolution_documents(documents):
    """Require the same ordered grid and physical/sample contract before fields."""
    if not isinstance(documents, (list, tuple)) or not 2 <= len(documents) <= 8:
        raise ValueError('resolution comparison requires 2..8 sampled paired studies')
    if any(not isinstance(doc, TwoGroundFaceSampledForwardPairStudyDocument) for doc in documents):
        raise ValueError('each resolution must be a TwoGroundFaceSampledForwardPairStudyDocument')
    reference = None
    seen = set()
    for doc in documents:
        data = doc.to_dict()
        controls = dict(mesh=data['study'].pop('mesh'), panel=data.pop('panel'))
        signature = json.dumps(controls, sort_keys=True, allow_nan=False)
        if signature in seen:
            raise ValueError('resolution controls must be distinct')
        seen.add(signature)
        if reference is None:
            reference = data
        elif data != reference:
            raise ValueError('resolution studies must preserve physical inputs, frequency grid and sampling')
    return tuple(documents)


def assess_two_ground_face_sampled_pair_resolution_yield(studies, *, acceptance, confidence=.95, minimum_yield=None):
    """Compare 2..8 completed iid studies without running new field calculations.

    Only volume mesh and panel controls may differ. Each supplied study retains
    its explicit version, complete ordered frequency grid, material/geometry,
    sampling and every original row. Both quantities and every frequency must
    satisfy their limits within a resolution. A manufactured sample passes if
    all resolutions pass, fails if all fail, and otherwise remains unresolved,
    including any failed original batch. The denominator is the sample count.

    The confidence envelope describes these fixed evaluated models. Resolution
    agreement does not detect common systematic error, bound discretization
    error, prove acceptance between frequency samples or establish measured
    manufacturing yield. Manual records are checked structurally, not authenticated.
    """
    if not isinstance(studies, (list, tuple)) or not 2 <= len(studies) <= 8:
        raise ValueError('resolution comparison requires 2..8 sampled paired studies')
    if any(not isinstance(study, TwoGroundFaceSampledForwardPairStudy) for study in studies):
        raise ValueError('each resolution must be a TwoGroundFaceSampledForwardPairStudy')
    _resolution_documents(tuple(TwoGroundFaceSampledForwardPairStudyDocument.loads(study.input_json) for study in studies))
    assessments = tuple(assess_two_ground_face_sampled_pair_yield(study, acceptance=acceptance,
        confidence=confidence, minimum_yield=minimum_yield) for study in studies)
    labels = []
    for index in range(len(assessments[0].classifications)):
        row = tuple(a.classifications[index] for a in assessments)
        labels.append('pass' if all(label == 'pass' for label in row) else
                      ('fail' if all(label == 'fail' for label in row) else 'unresolved'))
    bounds = _interval(labels.count('pass'), labels.count('unresolved'), len(labels), assessments[0].confidence)
    return TwoGroundFaceSampledPairResolutionYieldAssessment(assessments, tuple(labels), bounds)
