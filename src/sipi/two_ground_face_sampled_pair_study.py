# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Ordered manufacturing samples across finite two-ground-face frequency grids."""
from dataclasses import dataclass
import json

from ._two_ground_mesh_reuse import _mesh_reuse_scope

import numpy as np

from ._validation import _json_copy, _keys
from .network import _frequencies
from .two_ground_sampled_pair_study import (TwoGroundSampledForwardPairStudyDocument as _WholeStudy,
    TwoGroundSampledForwardPairStudyRow as _WholeRow)
from .study import ImpedanceStudyDocument
from .sampled_panel_pair_study import (SampledPanelForwardPairStudy,
    _run_sampled_panel_study)
from .two_ground_face_input import _source_inputs, _line_from_inputs, _line_from_values
from .two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument, TwoGroundFacePanelLineError

__all__ = ['TwoGroundFaceSampledForwardPairStudyDocument', 'TwoGroundFaceSampledForwardPairStudy',
           'TwoGroundFaceSampledForwardPairStudyRow']
_SCHEMA = 'sipi.two-ground-face-sampled-forward-pair-study/1'


def _full_grid(line, frequencies):
    data = line.to_dict()
    data['frequency_hz'] = frequencies
    return TwoGroundFacePanelTransmissionLineDocument.from_dict(data)


def _sampled_line(data, parameters, evaluation):
    return _full_grid(_line_from_inputs(data, parameters, evaluation), data['frequency_hz'])


@dataclass(frozen=True)
class TwoGroundFaceSampledForwardPairStudyRow(_WholeRow):
    pass


def _sampled_row(*args, cause=None):
    details = json.dumps(cause.to_dict(), allow_nan=False) if isinstance(cause, TwoGroundFacePanelLineError) else None
    return TwoGroundFaceSampledForwardPairStudyRow(*args, cause_details_json=details)


@dataclass(frozen=True)
class TwoGroundFaceSampledForwardPairStudy(SampledPanelForwardPairStudy):
    def to_dict(self):
        out = super().to_dict()
        out['scope'] = 'stated-two-ground-face-paired-frequency-samples-descriptive-not-production-yield'
        return out


class TwoGroundFaceSampledForwardPairStudyDocument(_WholeStudy):
    """Keep each manufactured sample fixed across 2..64 stated frequencies.

    The source study anchors the first frequency. One current extraction and
    dielectric mesh serve the complete grid for a row. Metal laws stay fixed;
    sampled dielectric models retain their frequency dependence. Failed grids
    remain atomic unknown rows. There is no interpolation between frequencies,
    resampling, automatic refinement or production-yield claim.
    """
    def __init__(self, study, *, frequencies, conductors, reference, ground_thickness,
                 panels_per_edge=32, ground_modes=128, interpolation_degree=16):
        if isinstance(study, ImpedanceStudyDocument):
            study = study.to_dict()
        self._data = self._validate(dict(schema=_SCHEMA, study=study, frequency_hz=frequencies,
            conductors=conductors, reference=reference, ground_thickness_m=ground_thickness,
            panel=dict(panels_per_edge=panels_per_edge, ground_modes=ground_modes,
                       interpolation_degree=interpolation_degree)))

    @staticmethod
    def _validate(data):
        data = _json_copy(data)
        _keys(data, ('schema', 'study', 'frequency_hz', 'conductors', 'reference',
                    'ground_thickness_m', 'panel'), where='two-ground-face sampled pair study')
        if data['schema'] != _SCHEMA:
            raise ValueError('unsupported two-ground-face-sampled-forward-pair-study schema')
        frequencies = _frequencies(data['frequency_hz'])
        if not 2 <= len(frequencies) <= 64 or np.any(frequencies <= 0):
            raise ValueError('frequencies must contain 2..64 increasing positive values')
        source = _source_inputs(data)
        if source['study']['material_evaluation']['frequency_hz'] != frequencies[0]:
            raise ValueError('study frequency must equal first requested frequency')
        frequencies = frequencies.tolist()
        _full_grid(_line_from_values(source), frequencies)
        return dict(schema=_SCHEMA, frequency_hz=frequencies, **source)

    def analyze(self, *, max_evaluations=128):
        with _mesh_reuse_scope():
            return _run_sampled_panel_study(self, max_evaluations=max_evaluations,
                make_line=_sampled_line, physical_line=lambda doc: doc,
                row_factory=_sampled_row, result_factory=TwoGroundFaceSampledForwardPairStudy,
                input_text=self.dumps)
