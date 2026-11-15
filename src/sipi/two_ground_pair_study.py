# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Ordered two-ground manufacturing samples with original failures retained."""
from dataclasses import dataclass
import json

from ._two_ground_current_reuse import _current_reuse_scope
from ._two_ground_mesh_reuse import _mesh_reuse_scope

from ._validation import _json_copy, _keys, _unique_object
from .study import ImpedanceStudyDocument
from .panel_pair_study import PanelForwardPairStudy, PanelForwardPairStudyRow, _run_panel_pair_study
from .two_ground_input import _source_inputs, _line_from_inputs
from .two_ground_panel_line import TwoGroundPanelLineError

__all__ = ['TwoGroundForwardPairStudyDocument', 'TwoGroundForwardPairStudy',
           'TwoGroundForwardPairStudyRow']
_SCHEMA = 'sipi.two-ground-forward-pair-study/1'


@dataclass(frozen=True)
class TwoGroundForwardPairStudyRow(PanelForwardPairStudyRow):
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


def _study_row(*args, cause=None):
    details = json.dumps(cause.to_dict(), allow_nan=False) if isinstance(cause, TwoGroundPanelLineError) else None
    return TwoGroundForwardPairStudyRow(*args, cause_details_json=details)


@dataclass(frozen=True)
class TwoGroundForwardPairStudy(PanelForwardPairStudy):
    def to_dict(self):
        out = super().to_dict()
        out['scope'] = 'stated-two-ground-paired-samples-descriptive-not-production-yield'
        return out


class TwoGroundForwardPairStudyDocument:
    """Use one explicit two-ground extraction for both forward launch values.

    Ordered study/3 or /4 samples retain geometry/material correlation and
    fixed geometry constraints. Metal laws remain fixed. Invalid samples and
    failed extractions are recorded, never clipped, retried or resampled.
    Both quantities succeed together; summaries require every row to succeed.
    """
    def __init__(self, study, *, conductors, reference, ground_thickness,
                 panels_per_edge=32, ground_modes=128, interpolation_degree=12):
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

    @classmethod
    def from_dict(cls, data):
        result = cls.__new__(cls)
        result._data = cls._validate(data)
        return result

    @classmethod
    def loads(cls, text):
        def reject(value):
            raise ValueError('nonfinite JSON number: '+value)
        return cls.from_dict(json.loads(text, object_pairs_hook=_unique_object, parse_constant=reject))

    def dumps(self):
        return json.dumps(self._data, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)

    def to_dict(self):
        return json.loads(self.dumps())

    def samples(self):
        return ImpedanceStudyDocument.from_dict(self._data['study']).samples()

    def analyze(self, *, max_evaluations=128):
        with _current_reuse_scope(), _mesh_reuse_scope():
            return _run_panel_pair_study(self, max_evaluations=max_evaluations,
                make_line=_line_from_inputs, physical_line=lambda doc:doc,
                row_factory=_study_row, result_factory=TwoGroundForwardPairStudy,
                input_text=self.dumps)
