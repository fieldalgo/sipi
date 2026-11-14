# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit all-frequency joint acceptance of shape-current manufacturing rows."""
from dataclasses import dataclass
import json

from .document import _keys, _unique_object
from .sampling import _copy
from .sampled_panel_pair_study import SampledPanelForwardPairStudy
from .sampled_panel_pair_yield import SampledPanelPairYieldAssessment, assess_sampled_panel_pair_yield, _acceptance
from .shape_sampled_panel_pair_study import ShapeSampledPanelForwardPairStudy, ShapeSampledPanelForwardPairStudyDocument

__all__ = ['ShapeSampledPanelPairYieldAssessment', 'ShapeSampledPanelForwardPairYieldDocument',
           'assess_shape_sampled_panel_pair_yield']


def _statistical_view(study):
    """Reuse the original iid event validator without changing any field row."""
    if not isinstance(study, ShapeSampledPanelForwardPairStudy):
        raise ValueError('yield assessment requires a ShapeSampledPanelForwardPairStudy')
    source = ShapeSampledPanelForwardPairStudyDocument.loads(study.input_json)
    return SampledPanelForwardPairStudy(source.study.dumps(), study.frequencies, study.variable_names,
                                  study.rows, study.summary)


@dataclass(frozen=True)
class ShapeSampledPanelPairYieldAssessment(SampledPanelPairYieldAssessment):
    def to_dict(self):
        view = SampledPanelPairYieldAssessment(_statistical_view(self.study), self.acceptance,
            self.confidence, self.minimum_yield, self.classifications, self.confidence_interval)
        out = view.to_dict()
        out['scope'] = 'iid-stated-shape-current-frequency-grid-not-measured-production-yield'
        return out


def assess_shape_sampled_panel_pair_yield(study, *, acceptance, confidence=.95, minimum_yield=None):
    """Assess all frequency/quantity limits as one event per original row.

    The field-free statistical view reuses the existing iid event and exact
    binomial interval. It neither recomputes fields nor converts current methods.
    Numerical resolution and distribution accuracy are outside this interval.
    """
    result = assess_sampled_panel_pair_yield(_statistical_view(study), acceptance=acceptance,
        confidence=confidence, minimum_yield=minimum_yield)
    return ShapeSampledPanelPairYieldAssessment(study, result.acceptance, result.confidence,
        result.minimum_yield, result.classifications, result.confidence_interval)


class ShapeSampledPanelForwardPairYieldDocument:
    """Strict per-frequency bounds on an explicit iid shape-current grid study."""
    def __init__(self, study, *, acceptance, confidence=.95, minimum_yield=None):
        if not isinstance(study, ShapeSampledPanelForwardPairStudyDocument):
            raise ValueError('study must be a ShapeSampledPanelForwardPairStudyDocument')
        self._assign(dict(schema='sipi.shape-sampled-panel-forward-pair-yield/1',
            study=study.to_dict(), acceptance=acceptance, confidence=confidence,
            minimum_yield=minimum_yield))

    def _assign(self, data):
        data = _copy(data)
        _keys(data, ('schema','study','acceptance','confidence','minimum_yield'),
              where='shape sampled panel pair yield')
        if data['schema'] != 'sipi.shape-sampled-panel-forward-pair-yield/1':
            raise ValueError('unsupported shape-sampled-panel-forward-pair-yield schema')
        study = ShapeSampledPanelForwardPairStudyDocument.from_dict(data['study'])
        if study.study.to_dict()['study']['sampling']['kind'] not in ('uniform','normal'):
            raise ValueError('joint yield requires iid uniform or normal samples')
        limits, level, target = _acceptance(data['acceptance'], data['confidence'], data['minimum_yield'],
                                             len(study.study.to_dict()['frequency_hz']))
        self._data = dict(schema=data['schema'], study=study.to_dict(), acceptance=limits,
                          confidence=level, minimum_yield=target)

    @classmethod
    def from_dict(cls, data):
        out = cls.__new__(cls)
        out._assign(data)
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

    def analyze(self, *, max_evaluations=128):
        data = self.to_dict()
        study = ShapeSampledPanelForwardPairStudyDocument.from_dict(data['study']).analyze(max_evaluations=max_evaluations)
        return assess_shape_sampled_panel_pair_yield(study, **{key:data[key] for key in
            ('acceptance','confidence','minimum_yield')})
