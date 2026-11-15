# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""IID limits for explicit two-ground-face scalar or selected paired quantities."""
from dataclasses import dataclass
from .two_ground_line_yield import TwoGroundLineQuantityYieldDocument as _WholeYield
from ._validation import _json_copy, _keys
from .line_yield import LineYieldAssessment, _assess_line_yield
from .yield_assessment import _criteria
from .two_ground_face_line_study import TwoGroundFaceLineQuantityStudy,TwoGroundFaceLineQuantityStudyDocument

__all__ = ['TwoGroundFaceLineYieldAssessment', 'TwoGroundFaceLineQuantityYieldDocument',
           'assess_two_ground_face_line_yield']
_SCHEMA='sipi.two-ground-face-line-quantity-yield/1'


@dataclass(frozen=True)
class TwoGroundFaceLineYieldAssessment(LineYieldAssessment):
    def to_dict(self):
        out=super().to_dict()
        out['scope']='iid-stated-two-ground-face-line-distribution-not-measured-production-yield'
        return out


def assess_two_ground_face_line_yield(study,*,minimum=None,maximum=None,confidence=.95,minimum_yield=None):
    """Keep every original iid row, including zero attenuation and unknowns."""
    return _assess_line_yield(study,minimum=minimum,maximum=maximum,confidence=confidence,
        minimum_yield=minimum_yield,study_type=TwoGroundFaceLineQuantityStudy,
        source_type=TwoGroundFaceLineQuantityStudyDocument,assessment_type=TwoGroundFaceLineYieldAssessment,
        source_schemas=('sipi.two-ground-face-line-quantity-study/1',),
        schema_error='yield assessment requires two-ground-face-line-quantity-study/1')


class TwoGroundFaceLineQuantityYieldDocument(_WholeYield):
    """Strict iid acceptance on one saved two-ground-face quantity study.

    Bounds use the original quantity unit. Unknown calculations remain in the
    original denominator and confidence envelope; no sample is resampled.
    Parsing, assessment of existing rows and record reopening do not solve.
    """
    def __init__(self,study,*,minimum=None,maximum=None,confidence=.95,minimum_yield=None):
        if not isinstance(study,TwoGroundFaceLineQuantityStudyDocument):
            raise ValueError('study must be a TwoGroundFaceLineQuantityStudyDocument')
        self._assign(dict(schema=_SCHEMA,study=study.to_dict(),minimum=minimum,maximum=maximum,
            confidence=confidence,minimum_yield=minimum_yield))

    def _assign(self,data):
        data=_json_copy(data)
        _keys(data,('schema','study','minimum','maximum','confidence','minimum_yield'),where='two-ground-face line yield')
        if data['schema']!=_SCHEMA:raise ValueError('unsupported two-ground-face line yield schema')
        study=TwoGroundFaceLineQuantityStudyDocument.from_dict(data['study']).to_dict()
        if study['study']['sampling']['kind'] not in ('uniform','normal'):
            raise ValueError('yield assessment requires iid uniform or normal samples')
        low,high,level,target=_criteria(data['minimum'],data['maximum'],data['confidence'],data['minimum_yield'],quantity_name='line quantity')
        self._data=dict(schema=_SCHEMA,study=study,minimum=low,maximum=high,confidence=level,minimum_yield=target)

    def analyze(self,*,max_evaluations=128):
        data=self.to_dict()
        study=TwoGroundFaceLineQuantityStudyDocument.from_dict(data['study']).analyze(max_evaluations=max_evaluations)
        return assess_two_ground_face_line_yield(study,**{key:data[key] for key in
            ('minimum','maximum','confidence','minimum_yield')})
