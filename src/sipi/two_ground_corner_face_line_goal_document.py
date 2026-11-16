# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict saved single-variable goals with explicit two-ground-corner-face line inputs."""
from .two_ground_line_goal_document import TwoGroundLineQuantityDesignDocument as _WholeGoal
from ._validation import _json_copy, _keys
from .network import _scalar
from .sampling import _integer
from .two_ground_corner_face_line_study import TwoGroundCornerFaceLineQuantityStudyDocument
from ._two_ground_corner_face_input import _line_from_values
from .two_ground_corner_face_line_goal import _refinements
from .two_ground_corner_face_line_goal import seek_two_ground_corner_face_line_quantity

__all__ = ['TwoGroundCornerFaceLineQuantityDesignDocument']
_SCHEMA = 'sipi.two-ground-corner-face-line-quantity-design/1'


class TwoGroundCornerFaceLineQuantityDesignDocument(_WholeGoal):
    """Persist a one-variable factory with a fixed quantity and surface laws.

    The nested study supplies one positive sweep interval with count=2. The
    nominal source, endpoints, midpoint and their three refinement inputs are
    checked without fields. This does not prove interior feasibility. Solving
    uses the original direct budget and gates, not a preceding source study.
    """
    def __init__(self, study, *, target, tolerance, max_evaluations=40):
        if not isinstance(study, TwoGroundCornerFaceLineQuantityStudyDocument):
            raise TypeError('study must be a TwoGroundCornerFaceLineQuantityStudyDocument')
        self._data=self._validate(dict(schema=_SCHEMA,study=study.to_dict(),
            target=target,tolerance=tolerance,max_evaluations=max_evaluations))

    @staticmethod
    def _validate(data):
        data=_json_copy(data)
        _keys(data,('schema','study','target','tolerance','max_evaluations'),where='two-ground-corner-face line goal')
        if data['schema']!=_SCHEMA:raise ValueError('unsupported two-ground-corner-face line goal schema')
        study=TwoGroundCornerFaceLineQuantityStudyDocument.from_dict(data['study']).to_dict()
        sampling=study['study']['sampling']
        if sampling['kind']!='sweep' or sampling['count']!=2 or len(sampling['variables'])!=1:
            raise ValueError('two-ground-corner-face goal study needs a sweep with count=2 and one variable')
        variable=sampling['variables'][0]
        lower,upper=(_scalar('parameter bound',variable[key]) for key in ('lower','upper'))
        if lower>=upper:raise ValueError('lower parameter bound must be below upper')
        target=_scalar('target',data['target'],zero=study['quantity']=='attenuation')
        tolerance=_scalar('tolerance',data['tolerance'])
        budget=_integer(data['max_evaluations'],5,10000)
        for values in (None,[lower],[lower+(upper-lower)/2],[upper]):
            _refinements(_line_from_values(study,values).dumps())
        return dict(schema=_SCHEMA,study=study,target=target,tolerance=tolerance,max_evaluations=budget)

    @property
    def study(self):return TwoGroundCornerFaceLineQuantityStudyDocument.from_dict(self.to_dict()['study'])

    def solve(self):
        data=self.to_dict();model=data['study'];variable=model['study']['sampling']['variables'][0]
        return seek_two_ground_corner_face_line_quantity(lambda value:_line_from_values(model,[value]),
            [variable['lower'],variable['upper']],data['target'],quantity=model['quantity'],
            tolerance=data['tolerance'],max_evaluations=data['max_evaluations'])
