# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""IID yield for explicit lossy line quantities, retaining unresolved samples."""
from dataclasses import dataclass
import json

import numpy as np

from .document import _keys, _unique_object
from .line_study import LineQuantityStudy, LineQuantityStudyDocument, LineQuantityStudyRow
from .sampling import _copy
from .yield_assessment import _criteria, _interval, _scalar

__all__ = ['LineYieldAssessment', 'LineQuantityYieldDocument', 'assess_line_yield']


@dataclass(frozen=True)
class LineYieldAssessment:
    """Finite iid sampling bounds for a fixed stated model, not production yield.

    Unknown rows stay in the denominator. The interval does not include mesh,
    solver, material-fit or distribution error. Study rows retain full line
    results and replayable inputs; no adaptive or selected-candidate inference.
    """
    study: LineQuantityStudy
    minimum: float | None
    maximum: float | None
    confidence: float
    minimum_yield: float | None
    classifications: tuple[str, ...]
    confidence_interval: tuple[float, float]

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
        n = len(self.classifications)
        return self.passed/n, (self.passed+self.unresolved)/n

    @property
    def goal_status(self):
        if self.minimum_yield is None:
            return 'not-requested'
        low, high = self.confidence_interval
        return ('pass' if low >= self.minimum_yield else
                'fail' if high < self.minimum_yield else 'undetermined')

    def to_dict(self):
        return dict(quantity=self.study.quantity, unit=self.study.unit,
            acceptance=dict(minimum=self.minimum, maximum=self.maximum),
            sampling_model=json.loads(self.study.input_json)['study']['sampling'],
            count=len(self.classifications), passed=self.passed, failed=self.failed, unresolved=self.unresolved,
            sample_fraction_bounds=list(self.sample_fraction_bounds), confidence=self.confidence,
            confidence_interval=list(self.confidence_interval), minimum_yield=self.minimum_yield,
            goal_status=self.goal_status, interval_method='clopper-pearson-unresolved-envelope',
            scope='iid-stated-distribution-not-measured-production-yield',
            rows=[dict(row.to_dict(), classification=label)
                  for row, label in zip(self.study.rows, self.classifications)])


def assess_line_yield(study, *, minimum=None, maximum=None, confidence=.95, minimum_yield=None):
    """Inclusive quantity limits on every original iid uniform/normal sample.

    Limits use the study quantity's unit: ohm for Re(Zc)/forward Re(Zdd), Np/m
    for scalar attenuation. A completed attenuation may be zero. Correlation
    between variables within a normal row is allowed. Sweep/corners reject.
    Counts, order and exact regenerated sample vectors are checked. These
    structural checks do not authenticate manually constructed solver results.
    """
    low, high, level, target = _criteria(minimum, maximum, confidence, minimum_yield,
                                        quantity_name='line quantity')
    if not isinstance(study, LineQuantityStudy):
        raise ValueError('yield assessment requires a LineQuantityStudy')
    source = LineQuantityStudyDocument.loads(study.input_json); data = source.to_dict()
    sampling = data['study']['sampling']
    if sampling['kind'] not in ('uniform', 'normal'):
        raise ValueError('yield assessment requires iid uniform or normal samples, not sweep/corners')
    if (len(study.rows) != sampling['count'] or study.quantity != data['quantity'] or
            study.variable_names != tuple(v['name'] for v in sampling['variables'])):
        raise ValueError('study must retain its quantity, variables and every planned row')
    samples = source.samples(); labels = []
    for i, row in enumerate(study.rows):
        if (not isinstance(row, LineQuantityStudyRow) or type(row.index) is not int or row.index != i
                or not isinstance(row.sample_values, tuple)
                or any(isinstance(value, (bool, np.bool_)) for value in row.sample_values)
                or not np.array_equal(row.sample_values, samples[i])):
            raise ValueError('study must retain original sample vectors and row order')
        if row.complete:
            if row.error_type is not None or row.phase != 'complete':
                raise ValueError('complete row must have complete phase and no error type')
            value = _scalar('completed line quantity', row.value, zero=study.quantity == 'attenuation')
            labels.append('pass' if (low is None or value >= low) and (high is None or value <= high) else 'fail')
        else:
            if (row.value is not None or not isinstance(row.error, str) or not isinstance(row.error_type, str)
                    or row.phase not in ('parameters', 'materials', 'input', 'extraction', 'diagnostic')):
                raise ValueError('unresolved row must retain its failed phase, error and no value')
            labels.append('unresolved')
    bounds = _interval(labels.count('pass'), labels.count('unresolved'), len(labels), level)
    return LineYieldAssessment(study, low, high, level, target, tuple(labels), bounds)


class LineQuantityYieldDocument:
    """Strict line-quantity-yield/1 for one fixed random line-quantity study."""
    def __init__(self, study, *, minimum=None, maximum=None, confidence=.95, minimum_yield=None):
        if not isinstance(study, LineQuantityStudyDocument):
            raise ValueError('study must be a LineQuantityStudyDocument')
        self._assign(dict(schema='sipi.line-quantity-yield/1', study=study.to_dict(),
            minimum=minimum, maximum=maximum, confidence=confidence, minimum_yield=minimum_yield))

    def _assign(self, data):
        data = _copy(data)
        _keys(data, ('schema', 'study', 'minimum', 'maximum', 'confidence', 'minimum_yield'), where='line quantity yield')
        if data['schema'] != 'sipi.line-quantity-yield/1':
            raise ValueError('unsupported line-quantity-yield schema')
        study = LineQuantityStudyDocument.from_dict(data['study']).to_dict()
        if study['study']['sampling']['kind'] not in ('uniform', 'normal'):
            raise ValueError('yield assessment requires iid uniform or normal samples')
        low, high, level, target = _criteria(data['minimum'], data['maximum'], data['confidence'],
                                             data['minimum_yield'], quantity_name='line quantity')
        self._data = dict(schema=data['schema'], study=study, minimum=low, maximum=high,
                          confidence=level, minimum_yield=target)

    @classmethod
    def from_dict(cls, data):
        out = cls.__new__(cls); out._assign(data); return out

    @classmethod
    def loads(cls, text):
        def reject(value):
            raise ValueError(f'nonfinite JSON number: {value}')
        return cls.from_dict(json.loads(text, object_pairs_hook=_unique_object, parse_constant=reject))

    def dumps(self):
        return json.dumps(self._data, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)

    def to_dict(self):
        return json.loads(self.dumps())

    def analyze(self, *, max_evaluations=128):
        data = self._data
        study = LineQuantityStudyDocument.from_dict(data['study']).analyze(max_evaluations=max_evaluations)
        return assess_line_yield(study, **{key: data[key] for key in
            ('minimum', 'maximum', 'confidence', 'minimum_yield')})
