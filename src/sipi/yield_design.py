# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Fixed-candidate impedance-yield selection with simultaneous confidence."""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import json
import math

from .document import _keys, _unique_object
from .sampling import _integer
from .study import ImpedanceStudyDocument
from .yield_assessment import YieldAssessment, assess_impedance_yield, _criteria, _scalar

__all__ = ['YieldDesignDocument', 'YieldDesignResult', 'YieldCandidateAssessment']


def _text(name, value):
    if (not isinstance(value, str) or not 1 <= len(value) <= 128
            or value != value.strip() or any(not c.isprintable() for c in value)):
        raise ValueError(f'{name} must be nonempty single-line text of at most 128 characters')
    return value


def _candidate_confidence(confidence, count):
    """Round conservatively so the exact float family failure budget is met."""
    alpha = 1-Fraction(confidence)
    exact = 1-alpha/count
    level = float(exact)
    if Fraction(level) < exact:
        level = math.nextafter(level, 1.)
    if not 0 < level < 1 or (1-Fraction(level))*count > alpha:
        raise ValueError('simultaneous confidence is not representable for this candidate count')
    return level


@dataclass(frozen=True)
class YieldCandidateAssessment:
    name: str
    cost: float
    assessment: YieldAssessment

    def to_dict(self):
        return dict(name=self.name, cost=self.cost, assessment=self.assessment.to_dict(),
                    study=json.loads(self.assessment.study.input_json))


@dataclass(frozen=True)
class YieldDesignResult:
    """Every predeclared candidate and the cheapest certified member, if any.

    Selection does not exclude a cheaper unresolved candidate from actually
    being feasible, or prove a continuous/global optimum. The family coverage
    assumes fixed candidates and iid rows, not independent candidates.
    """
    input_json: str
    candidates: tuple[YieldCandidateAssessment, ...]
    candidate_confidence: float

    @property
    def selected_index(self):
        eligible = [i for i, c in enumerate(self.candidates) if c.assessment.goal_status == 'pass']
        return min(eligible, key=lambda i: (self.candidates[i].cost, i)) if eligible else None

    @property
    def status(self):
        if self.selected_index is not None:
            return 'selected'
        return ('none-certified' if all(c.assessment.goal_status == 'fail' for c in self.candidates)
                else 'undetermined')

    @property
    def unresolved(self):
        return sum(c.assessment.unresolved for c in self.candidates)

    def to_dict(self):
        data = json.loads(self.input_json)
        index = self.selected_index
        selected = None if index is None else dict(index=index, name=self.candidates[index].name,
                                                   cost=self.candidates[index].cost)
        return dict(status=self.status, selected=selected, cost_unit=data['cost_unit'],
            confidence=data['confidence'], candidate_confidence=self.candidate_confidence,
            simultaneous_method='bonferroni-clopper-pearson-unresolved-envelope',
            minimum_yield=data['minimum_yield'],
            scope='lowest-cost-certified-member-of-fixed-candidate-set',
            quantity=self.candidates[0].assessment.study.quantity,
            evaluations=sum(len(c.assessment.study.rows) for c in self.candidates),
            unresolved=self.unresolved, candidates=[c.to_dict() for c in self.candidates])


class YieldDesignDocument:
    """Strict sipi.yield-design/1; enumerate a fixed set before any field work.

    Each candidate is exactly {name, cost, study}, where study is a saved random
    impedance-study dictionary. Cost is supplied by the caller in one explicit
    common unit; no executable objective or hidden geometric optimization runs.
    """
    def __init__(self, candidates, *, cost_unit, minimum_yield, minimum=None, maximum=None, confidence=.95):
        self._assign(dict(schema='sipi.yield-design/1', candidates=candidates, cost_unit=cost_unit,
            minimum=minimum, maximum=maximum, minimum_yield=minimum_yield, confidence=confidence))

    def _assign(self, data):
        _keys(data, ('schema', 'candidates', 'cost_unit', 'minimum', 'maximum', 'minimum_yield', 'confidence'),
              where='yield design')
        if data['schema'] != 'sipi.yield-design/1':
            raise ValueError('unsupported yield-design schema')
        low, high, confidence, target = _criteria(data['minimum'], data['maximum'],
                                                data['confidence'], data['minimum_yield'])
        if target is None:
            raise ValueError('yield design requires minimum_yield')
        cost_unit = _text('cost_unit', data['cost_unit'])
        raw = data['candidates']
        if not isinstance(raw, list) or not 1 <= len(raw) <= 32:
            raise ValueError('candidates must be a list of 1..32 fixed entries')
        _candidate_confidence(confidence, len(raw))
        candidates, names, quantities = [], set(), set()
        for entry in raw:
            _keys(entry, ('name', 'cost', 'study'), where='yield candidate')
            name = _text('candidate name', entry['name'])
            if name in names:
                raise ValueError('candidate names must be unique')
            names.add(name)
            cost = _scalar('candidate cost', entry['cost'], zero=True)
            study = ImpedanceStudyDocument.from_dict(entry['study']).to_dict()
            if study['sampling']['kind'] not in ('uniform', 'normal'):
                raise ValueError('yield candidates require iid uniform or normal sampling')
            quantities.add(study['quantity'])
            candidates.append(dict(name=name, cost=cost, study=study))
        if len(quantities) != 1:
            raise ValueError('all candidates must use the same impedance quantity')
        self._data = dict(schema=data['schema'], candidates=candidates, cost_unit=cost_unit,
                         minimum=low, maximum=high, confidence=confidence, minimum_yield=target)

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
        budget = _integer(max_evaluations, 2, 10000)
        data = self._data
        total = sum(c['study']['sampling']['count'] for c in data['candidates'])
        if total > budget:
            raise ValueError('all candidate samples exceed max_evaluations before any solve')
        level = _candidate_confidence(data['confidence'], len(data['candidates']))
        candidates = []
        for candidate in data['candidates']:
            study = ImpedanceStudyDocument.from_dict(candidate['study']).analyze(max_evaluations=budget)
            assessment = assess_impedance_yield(study, minimum=data['minimum'], maximum=data['maximum'],
                confidence=level, minimum_yield=data['minimum_yield'])
            candidates.append(YieldCandidateAssessment(candidate['name'], candidate['cost'], assessment))
        return YieldDesignResult(self.dumps(), tuple(candidates), level)
