# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit shape-current paired samples with complete and partial evidence."""
from dataclasses import dataclass
import json

from .document import _keys, _unique_object
from .panel_pair_study import (PanelForwardPairStudyDocument, PanelForwardPairStudyRow,
    PanelForwardPairStudy, _run_panel_pair_study, _panel_study_line)
from .line_input import _line_from_values
from .panel_line import PanelTransmissionLineDocument
from .shape_panel_line import (ShapePanelTransmissionLineDocument, ShapePanelLineError,
                               shape_current_record)

__all__ = ['ShapePanelForwardPairStudyDocument', 'ShapePanelForwardPairStudy',
           'ShapePanelForwardPairStudyRow']


@dataclass(frozen=True)
class ShapePanelForwardPairStudyRow(PanelForwardPairStudyRow):
    cause_details_json: str | None = None

    @property
    def cause_details(self):
        return None if self.cause_details_json is None else json.loads(self.cause_details_json)

    def to_dict(self):
        out = super().to_dict()
        out['cause_details'] = self.cause_details
        out['current_solver'] = (None if self.result is None else
            shape_current_record(self.result.current_factors, self.result.panel_settings))
        return out


def _shape_study_row(*args, cause=None):
    details = json.dumps(cause.to_dict(), allow_nan=False) if isinstance(cause, ShapePanelLineError) else None
    return ShapePanelForwardPairStudyRow(*args, cause_details_json=details)


@dataclass(frozen=True)
class ShapePanelForwardPairStudy(PanelForwardPairStudy):
    def to_dict(self):
        out = super().to_dict()
        out['scope'] = 'stated-shape-current-paired-samples-descriptive-not-production-yield'
        return out


class ShapePanelForwardPairStudyDocument:
    """Save an explicit current method, retaining every original sampled row.

    Nominal offset admission is field-free. Invalid sampled geometry, material,
    offsets and field work remain failed rows; later rows still run. Summaries
    require all rows to succeed and do not certify mesh accuracy or yield.
    """
    def __init__(self, study, *, step_fraction=1e-3):
        if not isinstance(study, PanelForwardPairStudyDocument):
            raise TypeError('study must be a PanelForwardPairStudyDocument')
        self._data = self._validate(dict(schema='sipi.shape-panel-forward-pair-study/1',
                                        study=study.to_dict(), step_fraction=step_fraction))

    @staticmethod
    def _validate(data):
        _keys(data, ('schema','study','step_fraction'), where='shape panel forward pair study')
        if data['schema'] != 'sipi.shape-panel-forward-pair-study/1':
            raise ValueError('unsupported shape-panel-forward-pair-study schema')
        study = PanelForwardPairStudyDocument.from_dict(data['study'])
        raw = study.to_dict()
        layered = raw['schema'] == 'sipi.panel-forward-pair-study/2'
        line_options = dict(line_schema='sipi.transmission-line/7') if layered else {}
        panel_options = dict(schema='sipi.panel-transmission-line/2') if layered else {}
        nominal = ShapePanelTransmissionLineDocument(PanelTransmissionLineDocument(
            _line_from_values(raw['study'], raw['conductor'], **line_options),
            **raw['panel'], **panel_options), step_fraction=data['step_fraction'])
        return dict(schema=data['schema'], study=study.to_dict(),
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
    def study(self):
        return PanelForwardPairStudyDocument.from_dict(self.to_dict()['study'])

    def samples(self):
        return self.study.samples()

    def analyze(self, *, max_evaluations=128):
        fraction = self.to_dict()['step_fraction']
        return _run_panel_pair_study(self.study, max_evaluations=max_evaluations,
            make_line=lambda data,p,e:ShapePanelTransmissionLineDocument(
                _panel_study_line(data,p,e), step_fraction=fraction),
            physical_line=lambda doc:doc.line.line,
            row_factory=_shape_study_row, result_factory=ShapePanelForwardPairStudy,
            input_text=self.dumps)
