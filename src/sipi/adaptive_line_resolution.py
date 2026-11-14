# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Bounded mesh refinement with retained finite comparisons and outer checks."""
from dataclasses import dataclass
from types import MappingProxyType
from collections.abc import Mapping
import json

from .line_model import TransmissionLineDocument
from .line_resolution import (ResolutionEvaluation, ResolutionFailure, _compare,
                              _resolution_inputs, _outer_input)
from .sampling import _integer

__all__ = ['AdaptiveLineResolution', 'refine_line_resolution']


@dataclass(frozen=True)
class AdaptiveLineResolution:
    """Finite agreement history, not an absolute field error estimate.

    mesh_levels counts attempted finer meshes. A completed level-limited or
    outer-unaccepted assessment remains unaccepted. Budget exhaustion and
    field/setup failure leave completed=False. All evaluated inputs survive.
    """
    tolerances: Mapping
    evaluations: tuple
    comparisons: tuple
    mesh_levels: int
    expected_outer_evaluations: int
    stop_reason: str
    failure: ResolutionFailure | None = None

    def __post_init__(self):
        object.__setattr__(self,'tolerances',MappingProxyType(dict(self.tolerances)))
        object.__setattr__(self,'evaluations',tuple(self.evaluations))
        object.__setattr__(self,'comparisons',tuple(self.comparisons))

    @property
    def accepted(self):
        return self.stop_reason == 'accepted'

    @property
    def completed(self):
        return self.stop_reason in ('accepted','mesh-unaccepted','outer-unaccepted')

    @property
    def outer_completed(self):
        return (self.failure is None and
                sum(row.stage.startswith('outer:') for row in self.comparisons)
                == self.expected_outer_evaluations)

    @property
    def selected_evaluation(self):
        """Accepted finer result on the original domain, otherwise None."""
        if not self.accepted:
            return None
        return next((row for row in reversed(self.evaluations) if row.stage.startswith('mesh:')),None)


def refine_line_resolution(line, *, outer_documents, tolerances, refinement_factor=.5,
                           max_levels=4, max_solves=8):
    """Refine until two adjacent mesh comparisons pass, then check the domain.

    Uses existing TransmissionLineDocument extraction and the explicit SI
    ResolutionTolerance contract. Inputs to outer_documents describe fixed
    larger physical domains with the *first* finer mesh settings, as in
    assess_line_resolution. At the selected level, only their mesh settings
    are replaced by the current finer settings and retained in the history.

    Two consecutive finer-versus-previous comparisons must pass for every
    selected entry/frequency before outer checks run. Each outer result is
    compared with that selected finer result. An unmet outer tolerance stops
    the process; changing the physical domain is a separate user decision.
    Neither a finite difference nor two passes certify absolute accuracy.

    Each full line evaluation counts once. Before another finer solve, its
    cost plus all required outer evaluations must fit max_solves. Old results
    are reused. A failed field/setup step preserves completed results and the
    attempted input; interrupts propagate. No extraction default, numerical
    tolerance, geometry or material is repaired or silently changed.
    """
    levels = _integer(max_levels,2,8)
    limit = _integer(max_solves,4,16)
    tolerances, prepared = _resolution_inputs(line,outer_documents,tolerances,
                                               refinement_factor,limit)
    base, first_fine = prepared[0][1], prepared[1][1]
    outer_templates = [doc for _,doc in prepared[2:]]
    count_outer = len(outer_templates)
    if 3+count_outer > limit:
        raise ValueError('two mesh comparisons and required outer checks exceed budget before any field solve')
    factor = float(refinement_factor)
    evaluations, comparisons = [], []
    level = 0

    def finish(reason, failure=None):
        return AdaptiveLineResolution(tolerances,evaluations,comparisons,level,
                                      count_outer,reason,failure)

    def evaluate(stage, doc, reference_index=None):
        text = doc.dumps()
        try:
            result = doc.analyze()
            evaluations.append(ResolutionEvaluation(stage,text,result))
            if reference_index is not None:
                comparisons.append(_compare(evaluations[reference_index].result,result,tolerances,
                                             stage,reference_index,len(evaluations)-1))
        except Exception as error:
            return ResolutionFailure(stage,text,type(error).__name__,str(error))
        return None

    def preparation_failure(stage, raw, error):
        return ResolutionFailure(stage,json.dumps(raw,sort_keys=True,indent=2,ensure_ascii=False,
                                                  allow_nan=False),type(error).__name__,str(error))

    failure = evaluate('base',base)
    if failure is not None:
        return finish('field-failed',failure)
    previous_index, previous_document, consecutive = 0, base, 0
    for attempt in range(1,levels+1):
        if len(evaluations)+1+count_outer > limit:
            return finish('budget-exhausted')
        level = attempt
        stage = f'mesh:{level}'
        raw = previous_document.to_dict()
        for key in ('edge_size','far_size','grade'):
            raw['cross_section']['mesh'][key] *= factor
        try:
            doc = first_fine if level == 1 else TransmissionLineDocument.from_dict(raw)
        except Exception as error:
            return finish('field-failed',preparation_failure(stage,raw,error))
        failure = evaluate(stage,doc,previous_index)
        if failure is not None:
            return finish('field-failed',failure)
        consecutive = consecutive+1 if comparisons[-1].accepted else 0
        previous_index, previous_document = len(evaluations)-1, doc
        if consecutive < 2:
            continue
        for index, template in enumerate(outer_templates):
            stage = f'outer:{index}'
            raw = template.to_dict()
            raw['cross_section']['mesh'] = doc.to_dict()['cross_section']['mesh']
            try:
                outer = _outer_input(TransmissionLineDocument.from_dict(raw),doc)
            except Exception as error:
                return finish('field-failed',preparation_failure(stage,raw,error))
            failure = evaluate(stage,outer,previous_index)
            if failure is not None:
                return finish('field-failed',failure)
        accepted = all(row.accepted for row in comparisons[-count_outer:])
        return finish('accepted' if accepted else 'outer-unaccepted')
    return finish('mesh-unaccepted')
