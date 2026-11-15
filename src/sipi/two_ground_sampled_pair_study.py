# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Ordered manufacturing samples across finite two-ground frequency grids."""
from dataclasses import dataclass
import json

from ._two_ground_current_reuse import _current_reuse_scope
from ._two_ground_mesh_reuse import _mesh_reuse_scope

import numpy as np

from ._validation import _json_copy, _keys, _unique_object
from .network import _frequencies
from .study import ImpedanceStudyDocument
from .sampled_panel_pair_study import (SampledPanelForwardPairStudy,
    SampledPanelForwardPairStudyRow, _run_sampled_panel_study)
from .two_ground_input import _source_inputs, _line_from_inputs, _line_from_values
from .two_ground_panel_line import TwoGroundPanelTransmissionLineDocument, TwoGroundPanelLineError

__all__ = ['TwoGroundSampledForwardPairStudyDocument', 'TwoGroundSampledForwardPairStudy',
           'TwoGroundSampledForwardPairStudyRow']
_SCHEMA = 'sipi.two-ground-sampled-forward-pair-study/1'


def _full_grid(line, frequencies):
    data = line.to_dict()
    data['frequency_hz'] = frequencies
    return TwoGroundPanelTransmissionLineDocument.from_dict(data)


def _sampled_line(data, parameters, evaluation):
    return _full_grid(_line_from_inputs(data, parameters, evaluation), data['frequency_hz'])


@dataclass(frozen=True)
class TwoGroundSampledForwardPairStudyRow(SampledPanelForwardPairStudyRow):
    cause_details_json: str | None = None

    @property
    def cause_details(self):
        return None if self.cause_details_json is None else json.loads(self.cause_details_json)

    def to_dict(self):
        out = super().to_dict()
        out['cause_details'] = self.cause_details
        out['current_solver'] = None if self.result is None else self.result.current_record()
        out['dielectric_mesh'] = None if self.result is None else self.result.mesh_record()
        return out


def _sampled_row(*args, cause=None):
    details = json.dumps(cause.to_dict(), allow_nan=False) if isinstance(cause, TwoGroundPanelLineError) else None
    return TwoGroundSampledForwardPairStudyRow(*args, cause_details_json=details)


@dataclass(frozen=True)
class TwoGroundSampledForwardPairStudy(SampledPanelForwardPairStudy):
    def to_dict(self):
        out = super().to_dict()
        out['scope'] = 'stated-two-ground-paired-frequency-samples-descriptive-not-production-yield'
        return out


class TwoGroundSampledForwardPairStudyDocument:
    """Keep each manufactured sample fixed across 2..64 stated frequencies.

    The source study anchors the first frequency. One current extraction and
    dielectric mesh serve the complete grid for a row. Metal laws stay fixed;
    sampled dielectric models retain their frequency dependence. Failed grids
    remain atomic unknown rows. There is no interpolation between frequencies,
    resampling, automatic refinement or production-yield claim.
    """
    def __init__(self, study, *, frequencies, conductors, reference, ground_thickness,
                 panels_per_edge=32, ground_modes=128, interpolation_degree=12):
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
                    'ground_thickness_m', 'panel'), where='two-ground sampled pair study')
        if data['schema'] != _SCHEMA:
            raise ValueError('unsupported two-ground-sampled-forward-pair-study schema')
        frequencies = _frequencies(data['frequency_hz'])
        if not 2 <= len(frequencies) <= 64 or np.any(frequencies <= 0):
            raise ValueError('frequencies must contain 2..64 increasing positive values')
        source = _source_inputs(data)
        if source['study']['material_evaluation']['frequency_hz'] != frequencies[0]:
            raise ValueError('study frequency must equal first requested frequency')
        frequencies = frequencies.tolist()
        _full_grid(_line_from_values(source), frequencies)
        return dict(schema=_SCHEMA, frequency_hz=frequencies, **source)

    @classmethod
    def from_dict(cls, data):
        result = cls.__new__(cls)
        result._data = cls._validate(data)
        return result

    @classmethod
    def loads(cls, text):
        def reject(value):
            raise ValueError('nonfinite JSON number: ' + value)
        return cls.from_dict(json.loads(text, object_pairs_hook=_unique_object, parse_constant=reject))

    def dumps(self):
        return json.dumps(self._data, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)

    def to_dict(self):
        return json.loads(self.dumps())

    def samples(self):
        return ImpedanceStudyDocument.from_dict(self._data['study']).samples()

    def analyze(self, *, max_evaluations=128):
        with _current_reuse_scope(), _mesh_reuse_scope():
            return _run_sampled_panel_study(self, max_evaluations=max_evaluations,
                make_line=_sampled_line, physical_line=lambda doc: doc,
                row_factory=_sampled_row, result_factory=TwoGroundSampledForwardPairStudy,
                input_text=self.dumps)
