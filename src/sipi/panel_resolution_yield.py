# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Joint acceptance across fixed resolutions, without a discretization error bound."""
from dataclasses import dataclass
import json

from sipi.panel_pair_study import PanelForwardPairStudy, PanelForwardPairStudyDocument, _QUANTITIES
from sipi.panel_pair_yield import assess_panel_pair_yield
from sipi.yield_assessment import _interval

__all__ = ['PanelPairResolutionYieldAssessment', 'assess_panel_pair_resolution_yield']


@dataclass(frozen=True)
class PanelPairResolutionYieldAssessment:
    """One iid sample denominator and every supplied resolution's original rows."""
    assessments: tuple
    classifications: tuple[str, ...]
    confidence_interval: tuple[float, float]

    def __post_init__(self):
        object.__setattr__(self, 'assessments', tuple(self.assessments))
        object.__setattr__(self, 'classifications', tuple(self.classifications))
        object.__setattr__(self, 'confidence_interval', tuple(self.confidence_interval))

    @property
    def acceptance(self):return self.assessments[0].acceptance
    @property
    def confidence(self):return self.assessments[0].confidence
    @property
    def minimum_yield(self):return self.assessments[0].minimum_yield
    @property
    def passed(self):return self.classifications.count('pass')
    @property
    def failed(self):return self.classifications.count('fail')
    @property
    def unresolved(self):return self.classifications.count('unresolved')
    @property
    def sample_fraction_bounds(self):
        n=len(self.classifications)
        return self.passed/n, (self.passed+self.unresolved)/n
    @property
    def goal_status(self):
        if self.minimum_yield is None:return 'not-requested'
        low,high=self.confidence_interval
        return 'pass' if low>=self.minimum_yield else ('fail' if high<self.minimum_yield else 'undetermined')

    def to_dict(self):
        return dict(quantities=list(_QUANTITIES),unit='ohm',
            acceptance={key:dict(value) for key,value in self.acceptance.items()},
            count=len(self.classifications),resolution_count=len(self.assessments),
            passed=self.passed,failed=self.failed,unresolved=self.unresolved,
            sample_fraction_bounds=list(self.sample_fraction_bounds),
            confidence=self.confidence,confidence_interval=list(self.confidence_interval),
            minimum_yield=self.minimum_yield,goal_status=self.goal_status,
            interval_method='clopper-pearson-unresolved-envelope',
            event='paired-limits-with-resolution-disagreement-unresolved',
            scope='iid-finite-resolution-envelope-not-a-discretization-error-bound',
            resolutions=[dict(input=json.loads(a.study.input_json),assessment=a.to_dict()) for a in self.assessments],
            rows=[dict(index=i,sample_values=list(self.assessments[0].study.rows[i].sample_values),
                       classification=label,labels_by_resolution=[a.classifications[i] for a in self.assessments])
                  for i,label in enumerate(self.classifications)])


def assess_panel_pair_resolution_yield(studies, *, acceptance, confidence=.95, minimum_yield=None):
    """Compare 2..8 fixed resolutions of the same iid paired study, without fields.

    Same schema/current method, geometry, material, frequency, sampling and
    constraints are required; only the explicit volume mesh and panel controls
    may differ. Duplicate resolution documents are refused. No resolution order,
    convergence rate or error bound is inferred. Every supplied study first
    passes the original iid row/acceptance validation.

    A sample passes if all resolutions pass, fails if all fail, and otherwise
    remains unresolved (including any original failed row). The denominator is
    the number of manufactured samples, not samples times resolutions. The
    confidence envelope describes these fixed evaluated models only. Agreement
    cannot detect a shared systematic error or establish measured production yield.
    Manually assembled field records are structurally checked, not authenticated.
    """
    if not isinstance(studies,(list,tuple)) or not 2<=len(studies)<=8:
        raise ValueError('resolution comparison requires 2..8 paired studies')
    if any(not isinstance(study,PanelForwardPairStudy) for study in studies):
        raise ValueError('each resolution must be a PanelForwardPairStudy')
    reference=None;seen=set();assessments=[]
    for study in studies:
        data=PanelForwardPairStudyDocument.loads(study.input_json).to_dict()
        settings=dict(mesh=data['study'].pop('mesh'),panel=data.pop('panel'))
        signature=json.dumps(settings,sort_keys=True,allow_nan=False)
        if signature in seen:raise ValueError('resolution controls must be distinct')
        seen.add(signature)
        if reference is None:reference=data
        elif data!=reference:
            raise ValueError('resolution studies must preserve physical inputs and sampling')
        assessments.append(assess_panel_pair_yield(study,acceptance=acceptance,
            confidence=confidence,minimum_yield=minimum_yield))
    labels=[]
    for i in range(len(assessments[0].classifications)):
        row=tuple(a.classifications[i] for a in assessments)
        labels.append('pass' if all(x=='pass' for x in row) else
                      ('fail' if all(x=='fail' for x in row) else 'unresolved'))
    bounds=_interval(labels.count('pass'),labels.count('unresolved'),len(labels),assessments[0].confidence)
    return PanelPairResolutionYieldAssessment(tuple(assessments),tuple(labels),bounds)
