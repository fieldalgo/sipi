# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict saved goals that explicitly select capacitance-shape currents."""
import itertools
import json

from .document import _keys, _unique_object
from .panel_pair_goal_document import (PanelForwardPairDesignDocument,
                                       _panel_input, _LAYERED_SCHEMA, _QUANTITIES)
from .shape_panel_line import ShapePanelTransmissionLineDocument
from .shape_panel_pair_goal import (_shape_refinements,
                                    seek_shape_panel_forward_pair_impedances)

__all__ = ['ShapePanelForwardPairDesignDocument']


class ShapePanelForwardPairDesignDocument:
    """Save a nested panel goal and explicit derivative step; normalize field-free."""
    def __init__(self, design, *, step_fraction=1e-3):
        if not isinstance(design, PanelForwardPairDesignDocument):
            raise TypeError('design must be a PanelForwardPairDesignDocument')
        self._data = self._validate(dict(schema='sipi.shape-panel-forward-pair-design/1',
                                        design=design.to_dict(), step_fraction=step_fraction))

    @staticmethod
    def _validate(data):
        _keys(data, ('schema','design','step_fraction'), where='shape panel forward pair design')
        if data['schema'] != 'sipi.shape-panel-forward-pair-design/1':
            raise ValueError('unsupported shape-panel-forward-pair-design schema')
        design = PanelForwardPairDesignDocument.from_dict(data['design'])
        goal = design.goal_input
        layered = design.to_dict()['schema'] == _LAYERED_SCHEMA
        def candidate(values=None):
            return ShapePanelTransmissionLineDocument(_panel_input(goal, design.panel_options,
                values, layered=layered), step_fraction=data['step_fraction'])
        nominal = candidate()
        _shape_refinements(nominal.dumps())
        bounds = [(v['lower'],v['upper']) for v in goal['study']['sampling']['variables']]
        point = goal['initial']
        if point is None:
            point = [lower+(upper-lower)/2 for lower,upper in bounds]
        for values in [point,*itertools.product(*bounds)]:
            _shape_refinements(candidate(values).dumps())
        return dict(schema=data['schema'], design=design.to_dict(),
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
        return PanelForwardPairDesignDocument.from_dict(self.to_dict()['design'])

    @property
    def goal_input(self):
        return self.design.goal_input

    def solve(self):
        data = self.to_dict()
        design = self.design
        goal = design.goal_input
        layered = data['design']['schema'] == _LAYERED_SCHEMA
        return seek_shape_panel_forward_pair_impedances(
            lambda a,b:ShapePanelTransmissionLineDocument(_panel_input(goal,
                design.panel_options, [a,b], layered=layered), step_fraction=data['step_fraction']),
            [[v['lower'],v['upper']] for v in goal['study']['sampling']['variables']],
            [goal['targets_ohm'][q] for q in _QUANTITIES],
            tolerances=[goal['tolerances_ohm'][q] for q in _QUANTITIES],
            initial=goal['initial'], max_evaluations=goal['max_evaluations'])
