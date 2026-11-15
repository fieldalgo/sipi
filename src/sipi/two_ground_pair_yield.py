# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit joint iid acceptance of two-ground manufacturing rows."""
from dataclasses import dataclass
import json

from ._validation import _json_copy, _keys, _unique_object
from .panel_pair_yield import PanelPairYieldAssessment, _acceptance, _assess_pair_yield
from .two_ground_pair_study import TwoGroundForwardPairStudy, TwoGroundForwardPairStudyDocument

__all__ = ['TwoGroundPairYieldAssessment', 'TwoGroundForwardPairYieldDocument',
           'assess_two_ground_pair_yield']
_SCHEMA = 'sipi.two-ground-forward-pair-yield/1'


@dataclass(frozen=True)
class TwoGroundPairYieldAssessment(PanelPairYieldAssessment):
    def to_dict(self):
        out = super().to_dict()
        out['scope'] = 'iid-stated-two-ground-distribution-not-measured-production-yield'
        return out


def assess_two_ground_pair_yield(study, *, acceptance, confidence=.95, minimum_yield=None):
    """Joint inclusive limits with every unresolved row in the denominator.

    Uniform/normal iid draws may correlate variables within one row. The
    conservative interval envelopes possible unknown labels, not numerical,
    distribution or measurement error. No field solve occurs in this function.
    """
    return _assess_pair_yield(study, acceptance=acceptance, confidence=confidence,
        minimum_yield=minimum_yield, study_type=TwoGroundForwardPairStudy,
        source_type=TwoGroundForwardPairStudyDocument, assessment_type=TwoGroundPairYieldAssessment)


class TwoGroundForwardPairYieldDocument:
    """Strict saved acceptance of one explicit two-ground iid sampling model."""
    def __init__(self, study, *, acceptance, confidence=.95, minimum_yield=None):
        if not isinstance(study, TwoGroundForwardPairStudyDocument):
            raise ValueError('study must be a TwoGroundForwardPairStudyDocument')
        self._assign(dict(schema=_SCHEMA, study=study.to_dict(), acceptance=acceptance,
                          confidence=confidence, minimum_yield=minimum_yield))

    def _assign(self, data):
        data = _json_copy(data)
        _keys(data, ('schema', 'study', 'acceptance', 'confidence', 'minimum_yield'),
              where='two-ground pair yield')
        if data['schema'] != _SCHEMA:
            raise ValueError('unsupported two-ground-forward-pair-yield schema')
        study = TwoGroundForwardPairStudyDocument.from_dict(data['study']).to_dict()
        if study['study']['sampling']['kind'] not in ('uniform', 'normal'):
            raise ValueError('joint yield requires iid uniform or normal samples')
        acceptance, level, target = _acceptance(data['acceptance'], data['confidence'], data['minimum_yield'])
        self._data = dict(schema=_SCHEMA, study=study, acceptance=acceptance,
                          confidence=level, minimum_yield=target)

    @classmethod
    def from_dict(cls, data):
        out = cls.__new__(cls)
        out._assign(data)
        return out

    @classmethod
    def loads(cls, text):
        def reject(value):
            raise ValueError('nonfinite JSON number: '+value)
        return cls.from_dict(json.loads(text, object_pairs_hook=_unique_object, parse_constant=reject))

    def dumps(self):
        return json.dumps(self._data, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)

    def to_dict(self):
        return json.loads(self.dumps())

    def analyze(self, *, max_evaluations=128):
        data = self.to_dict()
        study = TwoGroundForwardPairStudyDocument.from_dict(data['study']).analyze(max_evaluations=max_evaluations)
        return assess_two_ground_pair_yield(study, **{key:data[key] for key in
            ('acceptance', 'confidence', 'minimum_yield')})
