# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Fixed paired-impedance candidates with simultaneous joint-yield bounds."""
from dataclasses import dataclass
import json

from .document import _keys, _unique_object
from .sampling import _integer
from .panel_pair_study import PanelForwardPairStudyDocument, _QUANTITIES
from .panel_pair_yield import PanelPairYieldAssessment, assess_panel_pair_yield, _acceptance
from .yield_assessment import _scalar
from .yield_design import _candidate_confidence, _text

__all__ = ['PanelForwardPairSelectionDocument', 'PanelPairSelectionResult', 'PanelPairCandidateAssessment']

_SCHEMA = 'sipi.panel-forward-pair-selection/1'


@dataclass(frozen=True)
class PanelPairCandidateAssessment:
    name: str
    cost: float
    assessment: PanelPairYieldAssessment

    def to_dict(self):
        return dict(name=self.name, cost=self.cost, assessment=self.assessment.to_dict(),
                    study=json.loads(self.assessment.study.input_json))


@dataclass(frozen=True)
class PanelPairSelectionResult:
    """Every fixed candidate and the cheapest certified member, if any.

    A cheaper unresolved candidate may actually be feasible. Selection does
    not prove a continuous or global optimum. Family coverage does not require
    independent candidates, but does require fixed candidates and iid rows.
    """
    input_json: str
    candidates: tuple[PanelPairCandidateAssessment, ...]
    candidate_confidence: float

    def __post_init__(self):
        object.__setattr__(self, 'candidates', tuple(self.candidates))

    @property
    def selected_index(self):
        eligible = [i for i, candidate in enumerate(self.candidates)
                    if candidate.assessment.goal_status == 'pass']
        return min(eligible, key=lambda i: (self.candidates[i].cost, i)) if eligible else None

    @property
    def status(self):
        if self.selected_index is not None:
            return 'selected'
        return ('none-certified' if all(c.assessment.goal_status == 'fail' for c in self.candidates)
                else 'undetermined')

    @property
    def unresolved(self):
        return sum(candidate.assessment.unresolved for candidate in self.candidates)

    def to_dict(self):
        data = json.loads(self.input_json); index = self.selected_index
        selected = None if index is None else dict(index=index, name=self.candidates[index].name,
                                                   cost=self.candidates[index].cost)
        return dict(status=self.status, selected=selected, cost_unit=data['cost_unit'],
            quantities=list(_QUANTITIES), unit='ohm', acceptance=data['acceptance'],
            confidence=data['confidence'], candidate_confidence=self.candidate_confidence,
            simultaneous_method='bonferroni-clopper-pearson-unresolved-envelope',
            minimum_yield=data['minimum_yield'],
            scope='lowest-cost-certified-member-of-fixed-candidate-set',
            evaluations=sum(len(c.assessment.study.rows) for c in self.candidates),
            unresolved=self.unresolved, candidates=[c.to_dict() for c in self.candidates])


class PanelForwardPairSelectionDocument:
    """Strict fixed-candidate selection of joint paired-impedance acceptance.

    Each of 1..32 entries supplies a unique name, nonnegative cost and complete
    panel-forward-pair-study input. Every candidate uses the same positive
    frequency and common named limits. Its other explicit physical, sampling
    and panel settings remain visible. Costs share one caller-provided unit.

    Conservative exact-float Bonferroni allocation covers the candidate set;
    each paired row is one AND event, not two independent yield experiments.
    All planned samples count against the family budget, and every candidate's
    sample generation is checked before any fields. Each row and candidate is
    then attempted, retaining failures without resampling or early selection.
    """
    def __init__(self, candidates, *, cost_unit, acceptance, minimum_yield, confidence=.95):
        self._assign(dict(schema=_SCHEMA, candidates=candidates, cost_unit=cost_unit,
                          acceptance=acceptance, minimum_yield=minimum_yield, confidence=confidence))

    def _assign(self, data):
        _keys(data, ('schema', 'candidates', 'cost_unit', 'acceptance', 'confidence', 'minimum_yield'),
              where='panel pair selection')
        if data['schema'] != _SCHEMA:
            raise ValueError('unsupported panel-forward-pair-selection schema')
        limits, confidence, target = _acceptance(data['acceptance'], data['confidence'], data['minimum_yield'])
        if target is None:
            raise ValueError('paired selection requires minimum_yield')
        cost_unit = _text('cost_unit', data['cost_unit'])
        raw = data['candidates']
        if not isinstance(raw, list) or not 1 <= len(raw) <= 32:
            raise ValueError('candidates must be a list of 1..32 fixed entries')
        _candidate_confidence(confidence, len(raw))
        candidates, names, frequencies = [], set(), set()
        for entry in raw:
            _keys(entry, ('name', 'cost', 'study'), where='paired yield candidate')
            name = _text('candidate name', entry['name'])
            if name in names:
                raise ValueError('candidate names must be unique')
            names.add(name)
            cost = _scalar('candidate cost', entry['cost'], zero=True)
            study = PanelForwardPairStudyDocument.from_dict(entry['study']).to_dict()
            source = study['study']
            if source['sampling']['kind'] not in ('uniform', 'normal'):
                raise ValueError('paired candidates require iid uniform or normal sampling')
            frequencies.add(source['material_evaluation']['frequency_hz'])
            candidates.append(dict(name=name, cost=cost, study=study))
        if len(frequencies) != 1:
            raise ValueError('all paired candidates must use the same positive frequency')
        self._data = dict(schema=_SCHEMA, candidates=candidates, cost_unit=cost_unit,
                          acceptance=limits, minimum_yield=target, confidence=confidence)

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
        budget = _integer(max_evaluations, 2, 10000); data = self._data
        total = sum(c['study']['study']['sampling']['count'] for c in data['candidates'])
        if total > budget:
            raise ValueError('all candidate samples exceed max_evaluations before any solve')
        level = _candidate_confidence(data['confidence'], len(data['candidates']))
        documents = [PanelForwardPairStudyDocument.from_dict(c['study']) for c in data['candidates']]
        for document in documents:
            document.samples()
        candidates = []
        for candidate, document in zip(data['candidates'], documents):
            study = document.analyze(max_evaluations=budget)
            assessment = assess_panel_pair_yield(study, acceptance=data['acceptance'],
                confidence=level, minimum_yield=data['minimum_yield'])
            candidates.append(PanelPairCandidateAssessment(candidate['name'], candidate['cost'], assessment))
        return PanelPairSelectionResult(self.dumps(), tuple(candidates), level)
