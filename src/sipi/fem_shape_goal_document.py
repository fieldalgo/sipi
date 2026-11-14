# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved one-variable factories for explicit checked FEM line goals."""
import json
from .document import _keys, _unique_object
from .network import _scalar
from .sampling import _integer
from .study import _parameters
from .impedance_material import _sample_material
from .fem_shape_study import FEMShapeLineQuantityStudyDocument, _line
from .fem_shape_goal import seek_fem_shape_line_quantity

__all__ = ['FEMShapeLineQuantityDesignDocument']
_SCHEMA = 'sipi.fem-shape-line-quantity-design/1'


class FEMShapeLineQuantityDesignDocument:
    """Strict saved factory using one positive-bounded study sweep variable.

    The nested FEM study defines the quantity, geometry/material models, fixed
    boundary metals and nominal mesh controls. Require count=2 and one variable;
    source samples are not analyzed before the bounded goal. Fixed pitch/height
    and dielectric numeric-leaf transformations retain their existing meanings.
    """
    def __init__(self, study, *, target, tolerance, max_evaluations=40):
        if not isinstance(study, FEMShapeLineQuantityStudyDocument):
            raise TypeError('study must be a FEMShapeLineQuantityStudyDocument')
        self._data = self._validate(dict(schema=_SCHEMA,study=study.to_dict(),
            target=target,tolerance=tolerance,max_evaluations=max_evaluations))

    @staticmethod
    def _validate(data):
        _keys(data, ('schema','study','target','tolerance','max_evaluations'), where='FEM shape line goal')
        if data['schema'] != _SCHEMA: raise ValueError('unsupported FEM shape line goal schema')
        study = FEMShapeLineQuantityStudyDocument.from_dict(data['study']).to_dict()
        sampling = study['study']['sampling']
        if sampling['kind'] != 'sweep' or sampling['count'] != 2 or len(sampling['variables']) != 1:
            raise ValueError('FEM goal study needs a sweep with count=2 and one variable')
        variable = sampling['variables'][0]
        lower, upper = (_scalar('parameter bound', variable[key]) for key in ('lower','upper'))
        if lower >= upper: raise ValueError('lower parameter bound must be below upper')
        return dict(schema=_SCHEMA,study=study,
            target=_scalar('target',data['target'],zero=study['quantity']=='attenuation'),
            tolerance=_scalar('tolerance',data['tolerance']),
            max_evaluations=_integer(data['max_evaluations'],3,10000))

    @classmethod
    def from_dict(cls, data):
        result = cls.__new__(cls);result._data = cls._validate(data);return result

    @classmethod
    def loads(cls, text):
        def reject(value):raise ValueError('nonfinite JSON number: '+value)
        return cls.from_dict(json.loads(text,object_pairs_hook=_unique_object,parse_constant=reject))

    def dumps(self):return json.dumps(self._data,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)
    def to_dict(self):return json.loads(self.dumps())

    @property
    def study(self):return FEMShapeLineQuantityStudyDocument.from_dict(self.to_dict()['study'])

    def solve(self):
        data=self.to_dict();model=data['study'];source=model['study'];variable=source['sampling']['variables'][0]
        def factory(value):
            return _line(source,_parameters(source,[value]),_sample_material(source,[value]),model)
        return seek_fem_shape_line_quantity(factory,[variable['lower'],variable['upper']],data['target'],
            quantity=model['quantity'],tolerance=data['tolerance'],max_evaluations=data['max_evaluations'])
