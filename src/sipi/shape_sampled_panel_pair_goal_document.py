# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict saved finite-frequency goals with explicit shape-current extraction."""
import itertools
import json
import numpy as np

from .document import _keys, _unique_object
from .sampled_panel_pair_goal_document import (SampledPanelForwardPairDesignDocument,
    _panel_document, _LAYERED_SCHEMA, _QUANTITIES)
from .shape_panel_line import ShapePanelTransmissionLineDocument
from .shape_panel_pair_goal import _shape_refinements
from .shape_sampled_panel_pair_goal import seek_shape_sampled_panel_forward_pair_impedances

__all__ = ['ShapeSampledPanelForwardPairDesignDocument']


class ShapeSampledPanelForwardPairDesignDocument:
    """Save a finite grid, two bounded variables and an explicit derivative step.

    Admission checks nominal, initial/midpoint, corners and future refinements
    without solving fields. This retains finite-domain and finite-grid scope.
    """
    def __init__(self, design, *, step_fraction=1e-3):
        if not isinstance(design, SampledPanelForwardPairDesignDocument):
            raise TypeError('design must be a SampledPanelForwardPairDesignDocument')
        self._data = self._validate(dict(schema='sipi.shape-sampled-panel-forward-pair-design/1',
                                        design=design.to_dict(), step_fraction=step_fraction))

    @staticmethod
    def _validate(data):
        _keys(data, ('schema','design','step_fraction'), where='shape sampled panel pair design')
        if data['schema'] != 'sipi.shape-sampled-panel-forward-pair-design/1':
            raise ValueError('unsupported shape-sampled-panel-forward-pair-design schema')
        design = SampledPanelForwardPairDesignDocument.from_dict(data['design']).to_dict()
        def candidate(values=None):
            return ShapePanelTransmissionLineDocument(_panel_document(design['study'],
                design['conductor'], design['panel'], design['frequency_hz'], values,
                layered=design['schema']==_LAYERED_SCHEMA), step_fraction=data['step_fraction'])
        nominal = candidate()
        _shape_refinements(nominal.dumps())
        bounds = [(v['lower'],v['upper']) for v in design['study']['sampling']['variables']]
        point = design['initial']
        if point is None:
            point = [lower+(upper-lower)/2 for lower,upper in bounds]
        for values in [point,*itertools.product(*bounds)]:
            _shape_refinements(candidate(values).dumps())
        return dict(schema=data['schema'], design=design,
                    step_fraction=nominal.to_dict()['step_fraction'])

    @classmethod
    def from_dict(cls, data):
        out = cls.__new__(cls)
        out._data = cls._validate(data)
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

    @property
    def design(self):
        return SampledPanelForwardPairDesignDocument.from_dict(self.to_dict()['design'])

    def solve(self):
        data = self.to_dict()
        design = data['design']
        return seek_shape_sampled_panel_forward_pair_impedances(
            lambda a,b:ShapePanelTransmissionLineDocument(_panel_document(design['study'],
                design['conductor'], design['panel'], design['frequency_hz'], [a,b],
                layered=design['schema']==_LAYERED_SCHEMA), step_fraction=data['step_fraction']),
            [[v['lower'],v['upper']] for v in design['study']['sampling']['variables']],
            design['frequency_hz'], np.array([design['targets_ohm'][q] for q in _QUANTITIES]).T,
            tolerances=np.array([design['tolerances_ohm'][q] for q in _QUANTITIES]).T,
            initial=design['initial'], max_evaluations=design['max_evaluations'])
