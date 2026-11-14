# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved explicit finite-frequency panel-current pair goals."""
import itertools
import json
import numpy as np
from sipi.document import _keys, _unique_object
from sipi.sampling import _copy, _integer, _numbers
from sipi.network import _frequencies
from sipi.study import ImpedanceStudyDocument
from sipi.pair_line_goal_document import ForwardPairDesignDocument, _pair_design_inputs
from sipi.line_input import _line_from_values
from sipi.line_model import TransmissionLineDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.panel_pair_goal import _refinements
from sipi.sampled_panel_pair_goal import seek_sampled_panel_forward_pair_impedances

_SCHEMA='sipi.sampled-panel-forward-pair-design/1'
_LAYERED_SCHEMA='sipi.sampled-panel-forward-pair-design/2'
_QUANTITIES=('differential_forward_impedance_real','common_forward_impedance_real')


def _panel_document(study,conductor,panel,frequencies,values=None,*,layered=False):
    options=dict(line_schema='sipi.transmission-line/7') if layered else {}
    raw=_line_from_values(study,conductor,values,**options).to_dict()
    raw['frequency_hz']=frequencies
    schema='sipi.panel-transmission-line/2' if layered else 'sipi.panel-transmission-line/1'
    return PanelTransmissionLineDocument(TransmissionLineDocument.from_dict(raw),**panel,schema=schema)


class SampledPanelForwardPairDesignDocument:
    """Finite frequency samples and named pair goals over two template/material variables.

    Version 1 retains its line/6 and panel-line/1 inputs. Explicit version 2
    uses line/7 fixed metal laws and panel-line/2 without constructing a coated
    FEM goal. Nominal, initial and corner admission includes the full frequency
    vector and all three future refinements; it is not a continuous-band bound.
    """
    def __init__(self,study,*,conductor,frequencies,targets,tolerances,initial=None,
                 max_evaluations=64,panels_per_edge=32,ground_modes=512,interpolation_degree=10,
                 schema=_SCHEMA):
        if isinstance(study,ImpedanceStudyDocument):study=study.to_dict()
        self._assign(dict(schema=schema,study=study,conductor=conductor,frequency_hz=frequencies,
            targets_ohm=targets,tolerances_ohm=tolerances,initial=initial,max_evaluations=max_evaluations,
            panel=dict(panels_per_edge=panels_per_edge,ground_modes=ground_modes,interpolation_degree=interpolation_degree)))

    def _assign(self,data):
        data=_copy(data)
        _keys(data,('schema','study','conductor','panel','frequency_hz','targets_ohm',
                    'tolerances_ohm','initial','max_evaluations'),where='sampled panel forward pair design')
        schema=data['schema']
        if schema not in (_SCHEMA,_LAYERED_SCHEMA):raise ValueError('unsupported sampled-panel-forward-pair-design schema')
        layered=schema==_LAYERED_SCHEMA
        frequencies=_frequencies(data['frequency_hz'])
        if not 2<=len(frequencies)<=64 or np.any(frequencies<=0):
            raise ValueError('frequencies must contain 2..64 increasing positive values')
        values={}
        for key in ['targets_ohm','tolerances_ohm']:
            _keys(data[key],_QUANTITIES,where=key);values[key]={}
            for q in _QUANTITIES:
                array=_numbers(data[key][q])
                if array.shape!=frequencies.shape or np.any(array<=0):
                    raise ValueError(key+' needs one positive finite value per frequency for each quantity')
                values[key][q]=array.tolist()
        budget=_integer(data['max_evaluations'],4,10000)
        goal_input=dict(study=data['study'],conductor=data['conductor'],
            targets_ohm={q:values['targets_ohm'][q][0] for q in _QUANTITIES},
            tolerances_ohm={q:values['tolerances_ohm'][q][0] for q in _QUANTITIES},
            initial=data['initial'],max_evaluations=budget)
        design=(_pair_design_inputs(goal_input,line_schema='sipi.transmission-line/7') if layered else
                ForwardPairDesignDocument.from_dict(dict(schema='sipi.forward-pair-design/1',**goal_input)).to_dict())
        study=design['study'];conductor=design['conductor']
        if study['material_evaluation']['frequency_hz']!=frequencies[0]:raise ValueError('study frequency must equal the first requested frequency')
        _keys(data['panel'],('panels_per_edge','ground_modes','interpolation_degree'),where='panel controls')
        frequencies=frequencies.tolist()
        nominal=_panel_document(study,conductor,data['panel'],frequencies,layered=layered)
        panel=nominal.panel_options;_refinements(nominal.dumps())
        bounds=[(v['lower'],v['upper']) for v in study['sampling']['variables']]
        point=design['initial']
        if point is None:point=[lo+(hi-lo)/2 for lo,hi in bounds]
        for pair in [point,*itertools.product(*bounds)]:
            _refinements(_panel_document(study,conductor,panel,frequencies,pair,layered=layered).dumps())
        self._data=dict(schema=schema,study=study,conductor=conductor,panel=panel,frequency_hz=frequencies,
            **values,initial=design['initial'],max_evaluations=budget)

    @classmethod
    def from_dict(cls,data):
        out=cls.__new__(cls);out._assign(data);return out

    @classmethod
    def loads(cls,text):
        def reject(value):raise ValueError('nonfinite JSON number: '+value)
        return cls.from_dict(json.loads(text,object_pairs_hook=_unique_object,parse_constant=reject))

    def dumps(self):return json.dumps(self._data,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)
    def to_dict(self):return json.loads(self.dumps())

    def solve(self):
        data=self.to_dict();study=data['study']
        return seek_sampled_panel_forward_pair_impedances(
            lambda a,b:_panel_document(study,data['conductor'],data['panel'],data['frequency_hz'],[a,b],
                                      layered=data['schema']==_LAYERED_SCHEMA),
            [[v['lower'],v['upper']] for v in study['sampling']['variables']],data['frequency_hz'],
            np.array([data['targets_ohm'][q] for q in _QUANTITIES]).T,
            tolerances=np.array([data['tolerances_ohm'][q] for q in _QUANTITIES]).T,
            initial=data['initial'],max_evaluations=data['max_evaluations'])
