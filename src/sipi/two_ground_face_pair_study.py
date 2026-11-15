# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Ordered two-ground manufacturing samples with original failures retained."""
from dataclasses import dataclass
import json

from ._two_ground_mesh_reuse import _mesh_reuse_scope

from ._validation import _json_copy, _keys
from .two_ground_pair_study import (TwoGroundForwardPairStudyDocument as _WholeStudy,
    TwoGroundForwardPairStudyRow as _WholeRow)
from .study import ImpedanceStudyDocument
from .panel_pair_study import PanelForwardPairStudy, _run_panel_pair_study
from .two_ground_face_input import _source_inputs, _line_from_inputs
from .two_ground_face_panel_line import TwoGroundFacePanelLineError

__all__ = ['TwoGroundFaceForwardPairStudyDocument', 'TwoGroundFaceForwardPairStudy',
           'TwoGroundFaceForwardPairStudyRow']
_SCHEMA = 'sipi.two-ground-face-forward-pair-study/1'


@dataclass(frozen=True)
class TwoGroundFaceForwardPairStudyRow(_WholeRow):
    pass


def _study_row(*args, cause=None):
    details = json.dumps(cause.to_dict(), allow_nan=False) if isinstance(cause, TwoGroundFacePanelLineError) else None
    return TwoGroundFaceForwardPairStudyRow(*args, cause_details_json=details)


@dataclass(frozen=True)
class TwoGroundFaceForwardPairStudy(PanelForwardPairStudy):
    def to_dict(self):
        out = super().to_dict()
        out['scope'] = 'stated-two-ground-face-paired-samples-descriptive-not-production-yield'
        return out


class TwoGroundFaceForwardPairStudyDocument(_WholeStudy):
    """Use one explicit two-ground face-current extraction for both forward launch values.

    Ordered study/3 or /4 samples retain geometry/material correlation and
    fixed geometry constraints. Physical-face metal laws remain fixed. Invalid samples and
    failed extractions are recorded, never clipped, retried or resampled.
    Both quantities succeed together; summaries require every row to succeed.
    """
    def __init__(self, study, *, conductors, reference, ground_thickness,
                 panels_per_edge=32, ground_modes=128, interpolation_degree=16):
        if isinstance(study, ImpedanceStudyDocument):
            study = study.to_dict()
        self._data = self._validate(dict(schema=_SCHEMA, study=study, conductors=conductors,
            reference=reference, ground_thickness_m=ground_thickness,
            panel=dict(panels_per_edge=panels_per_edge, ground_modes=ground_modes,
                       interpolation_degree=interpolation_degree)))

    @staticmethod
    def _validate(data):
        data = _json_copy(data)
        _keys(data, ('schema', 'study', 'conductors', 'reference', 'ground_thickness_m', 'panel'),
              where='two-ground paired study')
        if data['schema'] != _SCHEMA:
            raise ValueError('unsupported two-ground-forward-pair-study schema')
        return dict(schema=_SCHEMA, **_source_inputs(data))

    def analyze(self, *, max_evaluations=128):
        with _mesh_reuse_scope():
            return _run_panel_pair_study(self, max_evaluations=max_evaluations,
                make_line=_line_from_inputs, physical_line=lambda doc:doc,
                row_factory=_study_row, result_factory=TwoGroundFaceForwardPairStudy,
                input_text=self.dumps)
