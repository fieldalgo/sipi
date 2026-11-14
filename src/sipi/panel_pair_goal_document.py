# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict saved inputs for explicit panel-current pair goals."""
import itertools
import json
from .document import _keys, _unique_object
from .sampling import _copy, _integer
from .pair_line_goal_document import ForwardPairDesignDocument, _pair_design_inputs, _GOAL_KEYS
from .panel_line import PanelTransmissionLineDocument
from .panel_pair_goal import seek_panel_forward_pair_impedances, _refinements
from .line_input import _line_from_values
from .study import ImpedanceStudyDocument

__all__ = ['PanelForwardPairDesignDocument']

_SCHEMA = 'sipi.panel-forward-pair-design/1'
_LAYERED_SCHEMA = 'sipi.panel-forward-pair-design/2'
_QUANTITIES = ('differential_forward_impedance_real','common_forward_impedance_real')


def _panel_input(design, panel, values=None, *, layered=False):
    options = dict(line_schema='sipi.transmission-line/7') if layered else {}
    line = _line_from_values(design['study'], design['conductor'], values, **options)
    schema = 'sipi.panel-transmission-line/2' if layered else 'sipi.panel-transmission-line/1'
    return PanelTransmissionLineDocument(line, **panel, schema=schema)


class PanelForwardPairDesignDocument:
    """Save explicit panel-current goals and their independent refinement controls.

    The existing constructor retains version 1 with a nested forward-pair-design/1.
    from_study selects version 2: flat source/control fields, transmission-line/7
    conductors and panel-line/2. It never constructs or runs a coated FEM goal.

    Both versions check nominal, initial/midpoint and four corner inputs,
    including future refinement documents, without field solves. This does not
    certify continuous-domain validity, an extremum or statistical accuracy.
    """
    def __init__(self,design,*,panels_per_edge=32,ground_modes=512,interpolation_degree=10):
        if not isinstance(design,ForwardPairDesignDocument):
            raise TypeError('design must be a ForwardPairDesignDocument')
        self._assign(dict(schema=_SCHEMA,design=design.to_dict(),panel=dict(
            panels_per_edge=panels_per_edge,ground_modes=ground_modes,interpolation_degree=interpolation_degree)))

    @classmethod
    def from_study(cls, study, *, conductor, targets, tolerances, initial=None,
                   max_evaluations=64, panels_per_edge=32, ground_modes=512,
                   interpolation_degree=10):
        """Explicit version 2 input, with fixed line/7 metal laws and panel currents."""
        if isinstance(study, ImpedanceStudyDocument):study=study.to_dict()
        return cls.from_dict(dict(schema=_LAYERED_SCHEMA, study=study, conductor=conductor,
            targets_ohm=targets, tolerances_ohm=tolerances, initial=initial,
            max_evaluations=max_evaluations, panel=dict(panels_per_edge=panels_per_edge,
                ground_modes=ground_modes, interpolation_degree=interpolation_degree)))

    def _assign(self,data):
        data=_copy(data)
        if not isinstance(data,dict):raise ValueError('panel forward pair design must be an object')
        schema=data.get('schema')
        if schema==_SCHEMA:
            _keys(data,('schema','design','panel'),where='panel forward pair design')
            design=ForwardPairDesignDocument.from_dict(data['design']).to_dict()
        elif schema==_LAYERED_SCHEMA:
            _keys(data,('schema',*_GOAL_KEYS,'panel'),where='panel forward pair design')
            design=_pair_design_inputs({key:data[key] for key in _GOAL_KEYS},
                                       line_schema='sipi.transmission-line/7')
        else:raise ValueError('unsupported panel-forward-pair-design schema')
        _integer(design['max_evaluations'],4,10000)
        _keys(data['panel'],('panels_per_edge','ground_modes','interpolation_degree'),where='panel controls')
        layered=schema==_LAYERED_SCHEMA
        nominal=_panel_input(design,data['panel'],layered=layered)
        panel=nominal.panel_options
        _refinements(nominal.dumps())
        bounds=[(v['lower'],v['upper']) for v in design['study']['sampling']['variables']]
        point=design['initial']
        if point is None:point=[lower+(upper-lower)/2 for lower,upper in bounds]
        for values in [point,*itertools.product(*bounds)]:
            doc=_panel_input(design,panel,values,layered=layered)
            _refinements(doc.dumps())
        self._data=(dict(schema=schema,**design,panel=panel) if layered else
                    dict(schema=schema,design=design,panel=panel))

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
    def design(self):
        """Legacy version 1 FEM source document; no implicit version 2 conversion."""
        if self._data['schema']!=_SCHEMA:
            raise TypeError('design is a version 1 accessor; use goal_input for version 2')
        return ForwardPairDesignDocument.from_dict(self.to_dict()['design'])
    @property
    def goal_input(self):
        """Fresh normalized source and goal controls, without a solver schema."""
        data=self.to_dict()
        if data['schema']==_SCHEMA:data=data['design']
        return {key:data[key] for key in _GOAL_KEYS}
    @property
    def panel_options(self):return dict(self._data['panel'])

    def solve(self):
        data=self.to_dict();design=self.goal_input;study=design['study']
        return seek_panel_forward_pair_impedances(
            lambda a,b:_panel_input(design,data['panel'],[a,b],layered=data['schema']==_LAYERED_SCHEMA),
            [[v['lower'],v['upper']] for v in study['sampling']['variables']],
            [design['targets_ohm'][q] for q in _QUANTITIES],
            tolerances=[design['tolerances_ohm'][q] for q in _QUANTITIES],
            initial=design['initial'],max_evaluations=design['max_evaluations'])
