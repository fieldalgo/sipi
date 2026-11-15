# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict saved two-ground-face paired targets across a finite frequency grid."""
import itertools
import numpy as np

from ._validation import _json_copy, _keys
from .two_ground_sampled_pair_goal_document import TwoGroundSampledForwardPairDesignDocument as _WholeGoal
from .network import _frequencies
from .sampling import _numbers
from .study import ImpedanceStudyDocument
from .two_ground_face_input import _line_from_values
from .two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument
from .two_ground_face_pair_goal import _refinements
from .two_ground_face_pair_goal_document import (TwoGroundFaceForwardPairDesignDocument,
                                          _SOURCE_KEYS, _GOAL_KEYS, _QUANTITIES)
from .two_ground_face_sampled_pair_goal import seek_two_ground_face_sampled_forward_pair_impedances

__all__ = ['TwoGroundFaceSampledForwardPairDesignDocument']
_SCHEMA = 'sipi.two-ground-face-sampled-forward-pair-design/1'


def _grid_line(data, values=None):
    line = _line_from_values(data, values).to_dict()
    line['frequency_hz'] = data['frequency_hz']
    return TwoGroundFacePanelTransmissionLineDocument.from_dict(line)


class TwoGroundFaceSampledForwardPairDesignDocument(_WholeGoal):
    """Save two bounded variables with named targets at every stated frequency.

    Nominal, initial/midpoint and four bound corners, including all three
    future refinements, are admitted across the full grid before field work.
    This is not a proof of interior feasibility or continuous-band accuracy.
    The original direct search, attempt budget and refinement gates apply.
    """
    def __init__(self, study, *, frequencies, conductors, reference, ground_thickness,
                 targets, tolerances, initial=None, max_evaluations=64,
                 panels_per_edge=32, ground_modes=128, interpolation_degree=16):
        if isinstance(study, ImpedanceStudyDocument):
            study = study.to_dict()
        self._data = self._validate(dict(schema=_SCHEMA, study=study, frequency_hz=frequencies,
            conductors=conductors, reference=reference, ground_thickness_m=ground_thickness,
            targets_ohm=targets, tolerances_ohm=tolerances, initial=initial,
            max_evaluations=max_evaluations, panel=dict(panels_per_edge=panels_per_edge,
                ground_modes=ground_modes, interpolation_degree=interpolation_degree)))

    @staticmethod
    def _validate(data):
        data = _json_copy(data)
        _keys(data, ('schema', 'frequency_hz', *_SOURCE_KEYS, *_GOAL_KEYS),
              where='two-ground-face sampled forward pair design')
        if data['schema'] != _SCHEMA:
            raise ValueError('unsupported two-ground-face-sampled-forward-pair-design schema')
        frequencies = _frequencies(data['frequency_hz'])
        if not 2 <= len(frequencies) <= 64 or np.any(frequencies <= 0):
            raise ValueError('frequencies must contain 2..64 increasing positive values')
        arrays = {}
        for key in ('targets_ohm', 'tolerances_ohm'):
            _keys(data[key], _QUANTITIES, where=key)
            arrays[key] = {}
            for quantity in _QUANTITIES:
                values = _numbers(data[key][quantity])
                if values.shape != frequencies.shape or np.any(values <= 0):
                    raise ValueError(key+' needs one positive finite value per frequency for each quantity')
                arrays[key][quantity] = values.tolist()
        single = TwoGroundFaceForwardPairDesignDocument.from_dict(dict(
            schema='sipi.two-ground-face-forward-pair-design/1',
            **{key: data[key] for key in _SOURCE_KEYS},
            **{key: {q: arrays[key][q][0] for q in _QUANTITIES}
               for key in ('targets_ohm', 'tolerances_ohm')},
            initial=data['initial'], max_evaluations=data['max_evaluations'])).to_dict()
        if single['study']['material_evaluation']['frequency_hz'] != frequencies[0]:
            raise ValueError('study frequency must equal first requested frequency')
        out = dict(schema=_SCHEMA, frequency_hz=frequencies.tolist(),
            **{key: single[key] for key in _SOURCE_KEYS}, **arrays,
            initial=single['initial'], max_evaluations=single['max_evaluations'])
        bounds = [(v['lower'], v['upper']) for v in out['study']['sampling']['variables']]
        point = out['initial']
        if point is None:
            point = [lo+(hi-lo)/2 for lo,hi in bounds]
        for values in [None, point, *itertools.product(*bounds)]:
            _refinements(_grid_line(out, values).dumps())
        return out

    def solve(self):
        data = self.to_dict()
        return seek_two_ground_face_sampled_forward_pair_impedances(
            lambda a,b: _grid_line(data, [a,b]),
            [[v['lower'],v['upper']] for v in data['study']['sampling']['variables']],
            data['frequency_hz'], np.array([data['targets_ohm'][q] for q in _QUANTITIES]).T,
            tolerances=np.array([data['tolerances_ohm'][q] for q in _QUANTITIES]).T,
            initial=data['initial'], max_evaluations=data['max_evaluations'])
