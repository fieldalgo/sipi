# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict saved inputs for explicit panel-current pair goals."""
import itertools
import json
from .document import _keys, _unique_object
from .sampling import _copy, _integer
from .pair_line_goal_document import ForwardPairDesignDocument
from .panel_line import PanelTransmissionLineDocument
from .panel_pair_goal import seek_panel_forward_pair_impedances, _refinements
from .line_input import _line_from_values

__all__ = ['PanelForwardPairDesignDocument']

_SCHEMA='sipi.panel-forward-pair-design/1'
_QUANTITIES=('differential_forward_impedance_real','common_forward_impedance_real')


class PanelForwardPairDesignDocument:
    """Save explicit panel-current pair goals without changing prior methods.

    The nested canonical forward-pair-design/1 supplies study/3 or /4,
    ordered geometry/material variables, explicit conductor laws and goals.
    Its attempt budget must be at least four. Panel controls are explicit.

    Normalization checks nominal, initial/midpoint and four corner inputs,
    including the three future refinement documents, without field solves.
    This does not certify shared geometric/skin-depth admission or validity
    throughout a continuous search domain. Only the panel line's supported
    reference boundaries and conductor models are admitted; no fallback runs.
    """
    def __init__(self,design,*,panels_per_edge=32,ground_modes=512,interpolation_degree=10):
        if not isinstance(design,ForwardPairDesignDocument):
            raise TypeError('design must be a ForwardPairDesignDocument')
        self._assign(dict(schema=_SCHEMA,design=design.to_dict(),panel=dict(
            panels_per_edge=panels_per_edge,ground_modes=ground_modes,interpolation_degree=interpolation_degree)))

    def _assign(self,data):
        data=_copy(data)
        _keys(data,('schema','design','panel'),where='panel forward pair design')
        if data['schema']!=_SCHEMA:raise ValueError('unsupported panel-forward-pair-design schema')
        design=ForwardPairDesignDocument.from_dict(data['design']).to_dict()
        _integer(design['max_evaluations'],4,10000)
        _keys(data['panel'],('panels_per_edge','ground_modes','interpolation_degree'),where='panel controls')
        study=design['study'];conductor=design['conductor']
        nominal=PanelTransmissionLineDocument(_line_from_values(study,conductor),**data['panel'])
        panel=nominal.panel_options
        _refinements(nominal.dumps())
        bounds=[(v['lower'],v['upper']) for v in study['sampling']['variables']]
        point=design['initial']
        if point is None:point=[lower+(upper-lower)/2 for lower,upper in bounds]
        for values in [point,*itertools.product(*bounds)]:
            doc=PanelTransmissionLineDocument(_line_from_values(study,conductor,values),**panel)
            _refinements(doc.dumps())
        self._data=dict(schema=_SCHEMA,design=design,panel=panel)

    @classmethod
    def from_dict(cls,data):
        out=cls.__new__(cls);out._assign(data);return out

    @classmethod
    def loads(cls,text):
        def reject(value):raise ValueError('nonfinite JSON number: '+value)
        return cls.from_dict(json.loads(text,object_pairs_hook=_unique_object,parse_constant=reject))

    def dumps(self):return json.dumps(self._data,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)
    def to_dict(self):return json.loads(self.dumps())
    @property
    def design(self):return ForwardPairDesignDocument.from_dict(self.to_dict()['design'])
    @property
    def panel_options(self):return dict(self._data['panel'])

    def solve(self):
        data=self.to_dict();design=data['design'];study=design['study']
        return seek_panel_forward_pair_impedances(
            lambda a,b:PanelTransmissionLineDocument(_line_from_values(study,design['conductor'],[a,b]),**data['panel']),
            [[v['lower'],v['upper']] for v in study['sampling']['variables']],
            [design['targets_ohm'][q] for q in _QUANTITIES],
            tolerances=[design['tolerances_ohm'][q] for q in _QUANTITIES],
            initial=design['initial'],max_evaluations=design['max_evaluations'])
