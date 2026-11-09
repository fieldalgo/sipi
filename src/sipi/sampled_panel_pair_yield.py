# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""IID joint acceptance of paired forward impedances, retaining unknown rows."""
from dataclasses import dataclass
import json
from types import MappingProxyType

import numpy as np

from sipi.document import _keys, _unique_object
from sipi.sampled_panel_pair_study import (
    SampledPanelForwardPairStudy, SampledPanelForwardPairStudyDocument, SampledPanelForwardPairStudyRow, _QUANTITIES)
from sipi.sampling import _copy
from sipi.yield_assessment import _criteria, _interval, _scalar

__all__ = ['SampledPanelPairYieldAssessment', 'SampledPanelForwardPairYieldDocument', 'assess_sampled_panel_pair_yield']

_SCHEMA = 'sipi.sampled-panel-forward-pair-yield/1'


def _acceptance(acceptance, confidence, minimum_yield, count):
    _keys(acceptance, _QUANTITIES, where='sampled paired acceptance')
    limits = {}
    for quantity in _QUANTITIES:
        item = acceptance[quantity]
        _keys(item, ('minimum', 'maximum'), where=quantity+' acceptance')
        if any(not isinstance(item[k], (list, tuple)) or len(item[k]) != count
               for k in ('minimum', 'maximum')):
            raise ValueError('each bound must explicitly contain one entry per frequency')
        lows, highs = [], []
        for low, high in zip(item['minimum'], item['maximum']):
            low, high, level, target = _criteria(low, high, confidence, minimum_yield,
                quantity_name=quantity)
            lows.append(low); highs.append(high)
        limits[quantity] = dict(minimum=lows, maximum=highs)
    return limits, level, target


@dataclass(frozen=True)
class SampledPanelPairYieldAssessment:
    """Joint iid counts and conservative bounds with every original row retained."""
    study: SampledPanelForwardPairStudy
    acceptance: object
    confidence: float
    minimum_yield: float | None
    classifications: tuple[str, ...]
    confidence_interval: tuple[float, float]

    def __post_init__(self):
        object.__setattr__(self, 'acceptance', MappingProxyType(
            {key: MappingProxyType({bound: tuple(values) for bound, values in value.items()})
             for key, value in self.acceptance.items()}))
        object.__setattr__(self, 'classifications', tuple(self.classifications))
        object.__setattr__(self, 'confidence_interval', tuple(self.confidence_interval))

    @property
    def passed(self):
        return self.classifications.count('pass')

    @property
    def failed(self):
        return self.classifications.count('fail')

    @property
    def unresolved(self):
        return self.classifications.count('unresolved')

    @property
    def sample_fraction_bounds(self):
        count = len(self.classifications)
        return self.passed/count, (self.passed+self.unresolved)/count

    @property
    def goal_status(self):
        if self.minimum_yield is None:
            return 'not-requested'
        low, high = self.confidence_interval
        return ('pass' if low >= self.minimum_yield else
                'fail' if high < self.minimum_yield else 'undetermined')

    def to_dict(self):
        return dict(quantities=list(_QUANTITIES), unit='ohm', frequencies_hz=list(self.study.frequencies),
            acceptance={key: {bound: list(values) for bound, values in value.items()}
                        for key, value in self.acceptance.items()},
            sampling_model=json.loads(self.study.input_json)['study']['sampling'],
            count=len(self.classifications), passed=self.passed, failed=self.failed,
            unresolved=self.unresolved, sample_fraction_bounds=list(self.sample_fraction_bounds),
            confidence=self.confidence, confidence_interval=list(self.confidence_interval),
            minimum_yield=self.minimum_yield, goal_status=self.goal_status,
            interval_method='clopper-pearson-unresolved-envelope',
            event='all-sampled-paired-forward-impedance-limits',
            scope='iid-stated-distribution-not-measured-production-yield',
            rows=[dict(row.to_dict(), classification=label)
                  for row, label in zip(self.study.rows, self.classifications)])


def assess_sampled_panel_pair_yield(study, *, acceptance, confidence=.95, minimum_yield=None):
    """Assess one fixed joint event across both quantities and all frequency samples.

    One manufactured iid row is one trial, with arbitrary within-row correlation.
    Failed whole batches stay unresolved in the original denominator. The existing
    interval envelopes unknown labels, not model/numerical errors or post-selection.
    Exact source/grid/sample/value checks do not authenticate manually built fields.
    """
    if not isinstance(study, SampledPanelForwardPairStudy):
        raise ValueError('yield assessment requires a SampledPanelForwardPairStudy')
    source = SampledPanelForwardPairStudyDocument.loads(study.input_json)
    data = source.to_dict(); sampling = data['study']['sampling']
    if (any(isinstance(f, (bool, np.bool_)) for f in study.frequencies)
            or study.frequencies != tuple(data['frequency_hz'])):
        raise ValueError('study must retain its exact ordered frequency vector')
    limits, level, target = _acceptance(acceptance, confidence, minimum_yield, len(study.frequencies))
    if sampling['kind'] not in ('uniform', 'normal'):
        raise ValueError('joint yield requires iid uniform or normal samples, not sweep/corners')
    if (len(study.rows) != sampling['count'] or
            study.variable_names != tuple(v['name'] for v in sampling['variables'])):
        raise ValueError('study must retain its variables and every planned row')
    samples = source.samples(); labels = []
    for index, row in enumerate(study.rows):
        if (not isinstance(row, SampledPanelForwardPairStudyRow) or type(row.index) is not int
                or row.index != index or not isinstance(row.sample_values, tuple)
                or any(isinstance(value, (bool, np.bool_)) for value in row.sample_values)
                or not np.array_equal(row.sample_values, samples[index])):
            raise ValueError('study must retain original sample vectors and row order')
        if row.complete:
            if row.error_type is not None or row.phase != 'complete':
                raise ValueError('complete row must have complete phase and no error type')
            if (not isinstance(row.values, tuple) or len(row.values) != len(study.frequencies)
                    or any(not isinstance(pair, tuple) or len(pair) != 2 for pair in row.values)):
                raise ValueError('complete row requires an ordered frequency-by-two value matrix')
            values = tuple(tuple(_scalar('completed '+q, value) for q, value in zip(_QUANTITIES, pair))
                           for pair in row.values)
            accepted = all((limits[q]['minimum'][f] is None or value >= limits[q]['minimum'][f])
                and (limits[q]['maximum'][f] is None or value <= limits[q]['maximum'][f])
                for f, pair in enumerate(values) for q, value in zip(_QUANTITIES, pair))
            labels.append('pass' if accepted else 'fail')
        else:
            if (row.values is not None or not isinstance(row.error, str)
                    or not isinstance(row.error_type, str)
                    or row.phase not in ('parameters', 'materials', 'input', 'extraction', 'diagnostic')):
                raise ValueError('unresolved row must retain its failed phase, error and no pair values')
            labels.append('unresolved')
    bounds = _interval(labels.count('pass'), labels.count('unresolved'), len(labels), level)
    return SampledPanelPairYieldAssessment(study, limits, level, target, tuple(labels), bounds)


class SampledPanelForwardPairYieldDocument:
    """Strict fixed named arrays over one finite-frequency paired iid study.

    Every quantity/frequency needs an inclusive minimum and/or maximum. Parsing
    is field-free; all original manufactured rows and failed batches are retained.
    Existing single-frequency and single-quantity schemas remain unchanged.
    """
    def __init__(self, study, *, acceptance, confidence=.95, minimum_yield=None):
        if not isinstance(study, SampledPanelForwardPairStudyDocument):
            raise ValueError('study must be a SampledPanelForwardPairStudyDocument')
        self._assign(dict(schema=_SCHEMA, study=study.to_dict(), acceptance=acceptance,
                          confidence=confidence, minimum_yield=minimum_yield))

    def _assign(self, data):
        data = _copy(data)
        _keys(data, ('schema', 'study', 'acceptance', 'confidence', 'minimum_yield'), where='panel pair yield')
        if data['schema'] != _SCHEMA:
            raise ValueError('unsupported panel-forward-pair-yield schema')
        study = SampledPanelForwardPairStudyDocument.from_dict(data['study']).to_dict()
        if study['study']['sampling']['kind'] not in ('uniform', 'normal'):
            raise ValueError('joint yield requires iid uniform or normal samples')
        acceptance, level, target = _acceptance(data['acceptance'], data['confidence'], data['minimum_yield'], len(study['frequency_hz']))
        self._data = dict(schema=_SCHEMA, study=study, acceptance=acceptance,
                          confidence=level, minimum_yield=target)

    @classmethod
    def from_dict(cls, data):
        out = cls.__new__(cls); out._assign(data); return out

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
        data = self._data
        study = SampledPanelForwardPairStudyDocument.from_dict(data['study']).analyze(max_evaluations=max_evaluations)
        return assess_sampled_panel_pair_yield(study, **{key: data[key] for key in
            ('acceptance', 'confidence', 'minimum_yield')})
