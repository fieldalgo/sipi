# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""IID impedance-yield assessment retaining unresolved samples in the denominator."""
from __future__ import annotations

from dataclasses import dataclass
import json

import numpy as np
from scipy.special import betaincinv

from .document import _keys, _unique_object
from .network import _scalar as _network_scalar
from .study import ImpedanceStudy, ImpedanceStudyDocument, StudyRow

__all__ = ['YieldAssessment', 'ImpedanceYieldDocument', 'assess_impedance_yield']


def _scalar(name, value, *, zero=False):
    try:
        return _network_scalar(name, value, zero=zero)
    except (TypeError, OverflowError) as exc:
        raise ValueError(f'{name} must be a representable finite real scalar') from exc


def _criteria(minimum, maximum, confidence, minimum_yield, *, quantity_name='impedance'):
    low = None if minimum is None else _scalar('minimum '+quantity_name, minimum, zero=True)
    high = None if maximum is None else _scalar('maximum '+quantity_name, maximum, zero=True)
    if low is None and high is None or low is not None and high is not None and low > high:
        raise ValueError(f'at least one {quantity_name} limit is required, with minimum <= maximum')
    level = _scalar('confidence', confidence)
    if not 0 < level < 1 or not 0 < (1-level)/2 < .5:
        raise ValueError('confidence must be strictly between zero and one at float precision')
    target = None if minimum_yield is None else _scalar('minimum_yield', minimum_yield, zero=True)
    if target is not None and target > 1:
        raise ValueError('minimum_yield must be in [0, 1]')
    return low, high, level, target


def _interval(passed, unresolved, count, confidence):
    """Union of equal-tailed exact binomial intervals for all unresolved labels.

    Reflect the upper tail to avoid rounding 1-alpha/2 to one. Explicit
    zero/all-success endpoints are mathematical values, not clipped results.
    """
    tail = (1-confidence)/2
    low = 0. if passed == 0 else float(betaincinv(passed, count-passed+1, tail))
    best = passed+unresolved
    high = 1. if best == count else 1-float(betaincinv(count-best, best+1, tail))
    if not np.isfinite([low, high]).all() or not 0 <= low <= high <= 1:
        raise ValueError('binomial confidence interval is not representable')
    return low, high


@dataclass(frozen=True)
class YieldAssessment:
    """Counts and conservative binomial bounds for the stated sampling model.

    This accounts for finite iid sampling and unresolved labels, not solver,
    mesh, material-fit or manufacturing-distribution error. The source study
    and every row remain available; unresolved rows are never resampled.
    """
    study: ImpedanceStudy
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
        return dict(quantity=self.study.quantity, unit='ohm',
            acceptance=dict(minimum=self.minimum, maximum=self.maximum),
            sampling_model=json.loads(self.study.input_json)['sampling'],
            count=len(self.classifications), passed=self.passed, failed=self.failed, unresolved=self.unresolved,
            sample_fraction_bounds=list(self.sample_fraction_bounds),
            confidence=self.confidence, confidence_interval=list(self.confidence_interval),
            interval_method='clopper-pearson-unresolved-envelope',
            minimum_yield=self.minimum_yield, goal_status=self.goal_status,
            scope='iid-stated-distribution-not-measured-production-yield',
            rows=[dict(index=r.index, classification=label, parameters=dict(r.parameters),
                impedance_ohm=None if r.impedance is None else float(r.impedance), error_type=r.error_type, error=r.error,
                document=None if r.document is None else r.document.to_dict(),
                material_evaluation=None if r.material_evaluation_json is None else json.loads(r.material_evaluation_json))
                for r, label in zip(self.study.rows, self.classifications)])


def assess_impedance_yield(study, *, minimum=None, maximum=None, confidence=.95, minimum_yield=None):
    """Assess inclusive impedance limits on all rows of a random impedance study.

    Only uniform/normal sampling is accepted: sweep/corners are not iid yield
    experiments. Correlation between variables within a normal row is allowed.
    Externally constructed study objects are not evidence of authentic solves.
    """
    low, high, level, target = _criteria(minimum, maximum, confidence, minimum_yield)
    if not isinstance(study, ImpedanceStudy):
        raise ValueError('yield assessment requires an ImpedanceStudy')
    data = ImpedanceStudyDocument.loads(study.input_json).to_dict()
    sampling = data['sampling']
    if sampling['kind'] not in ('uniform', 'normal'):
        raise ValueError('yield assessment requires iid uniform or normal samples, not sweep/corners')
    if (len(study.rows) != sampling['count'] or study.quantity != data['quantity']
            or any(not isinstance(row, StudyRow) or type(row.index) is not int or row.index != i
                   for i, row in enumerate(study.rows))):
        raise ValueError('study must retain its quantity and every planned row in order')
    labels = []
    for row in study.rows:
        if row.complete:
            if row.error_type is not None:
                raise ValueError('complete row must not retain an error type')
            value = _scalar('completed row impedance', row.impedance)
            labels.append('pass' if (low is None or value >= low) and (high is None or value <= high) else 'fail')
        else:
            if row.impedance is not None or not isinstance(row.error, str) or not isinstance(row.error_type, str):
                raise ValueError('unresolved row must retain its error and no impedance value')
            labels.append('unresolved')
    bounds = _interval(labels.count('pass'), labels.count('unresolved'), len(labels), level)
    return YieldAssessment(study, low, high, level, target, tuple(labels), bounds)


class ImpedanceYieldDocument:
    """Strict sipi.impedance-yield/1 with a complete nested random study input."""

    def __init__(self, study, *, minimum=None, maximum=None, confidence=.95, minimum_yield=None):
        if not isinstance(study, ImpedanceStudyDocument):
            raise ValueError('study must be an ImpedanceStudyDocument')
        self._assign(dict(schema='sipi.impedance-yield/1', study=study.to_dict(),
            minimum=minimum, maximum=maximum, confidence=confidence, minimum_yield=minimum_yield))

    def _assign(self, data):
        _keys(data, ('schema', 'study', 'minimum', 'maximum', 'confidence', 'minimum_yield'), where='impedance yield')
        if data['schema'] != 'sipi.impedance-yield/1':
            raise ValueError('unsupported impedance-yield schema')
        study = ImpedanceStudyDocument.from_dict(data['study']).to_dict()
        if study['sampling']['kind'] not in ('uniform', 'normal'):
            raise ValueError('yield assessment requires iid uniform or normal samples')
        low, high, level, target = _criteria(data['minimum'], data['maximum'], data['confidence'], data['minimum_yield'])
        self._data = dict(schema=data['schema'], study=study, minimum=low, maximum=high,
                          confidence=level, minimum_yield=target)

    @classmethod
    def from_dict(cls, data):
        result = cls.__new__(cls); result._assign(data)
        return result

    @classmethod
    def loads(cls, text):
        if not isinstance(text, str):
            raise TypeError('saved input must be JSON text')
        def reject(value):
            raise ValueError(f'nonfinite JSON number: {value}')
        return cls.from_dict(json.loads(text, object_pairs_hook=_unique_object, parse_constant=reject))

    def dumps(self):
        return json.dumps(self._data, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)

    def to_dict(self):
        return json.loads(self.dumps())

    def analyze(self, *, max_evaluations=128):
        data = self._data
        study = ImpedanceStudyDocument.from_dict(data['study']).analyze(max_evaluations=max_evaluations)
        return assess_impedance_yield(study, **{key: data[key] for key in
            ('minimum', 'maximum', 'confidence', 'minimum_yield')})
