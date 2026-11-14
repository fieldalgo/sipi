# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Bounded, independently checked volume and panel refinement plans."""
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from .line_resolution import ResolutionEvaluation, ResolutionFailure, _compare
from .panel_line import PanelTransmissionLineDocument
from .panel_resolution import _panel_resolution_inputs
from .sampling import _integer

__all__ = ['PanelResolutionRefinement', 'AdaptivePanelResolution',
           'refine_panel_line_resolution']


@dataclass(frozen=True)
class PanelResolutionRefinement:
    """Explicit next panel settings and outer documents at that mesh level.

    Construction takes isolated snapshots; complete physical admission occurs
    before refinement starts. Outer domains keep the same size and order at
    every step. No unspecified future panel setting is inferred.
    """
    panel_options: Mapping
    outer_documents: tuple

    def __post_init__(self):
        if not isinstance(self.panel_options, Mapping):
            raise ValueError('panel_options must specify all three controls')
        if (not isinstance(self.outer_documents, (tuple, list)) or not self.outer_documents
                or any(not isinstance(d, PanelTransmissionLineDocument) for d in self.outer_documents)):
            raise ValueError('each refinement needs explicit panel outer documents')
        object.__setattr__(self, 'panel_options', MappingProxyType(dict(self.panel_options)))
        object.__setattr__(self, 'outer_documents', tuple(
            PanelTransmissionLineDocument.loads(d.dumps()) for d in self.outer_documents))


@dataclass(frozen=True)
class AdaptivePanelResolution:
    """Finite agreement history; no absolute error or convergence certificate."""
    tolerances: Mapping
    evaluations: tuple
    comparisons: tuple
    refinement_levels: int
    expected_outer_evaluations: int
    stop_reason: str
    failure: ResolutionFailure | None = None

    def __post_init__(self):
        object.__setattr__(self, 'tolerances', MappingProxyType(dict(self.tolerances)))
        object.__setattr__(self, 'evaluations', tuple(self.evaluations))
        object.__setattr__(self, 'comparisons', tuple(self.comparisons))

    @property
    def accepted(self):
        return self.stop_reason == 'accepted'

    @property
    def completed(self):
        return self.stop_reason in ('accepted', 'resolution-unaccepted', 'outer-unaccepted')

    @property
    def outer_completed(self):
        return (self.failure is None and sum(row.stage.startswith('outer:')
                for row in self.comparisons) == self.expected_outer_evaluations)

    @property
    def selected_evaluation(self):
        if not self.accepted:
            return None
        return next(row for row in reversed(self.evaluations) if row.stage.endswith(':joint'))


def _adaptive_panel_inputs(line, refinements, tolerances, factor, max_solves):
    limit = _integer(max_solves, 8, 32)
    if (not isinstance(refinements, (tuple, list)) or not 2 <= len(refinements) <= 4
            or any(not isinstance(step, PanelResolutionRefinement) for step in refinements)):
        raise ValueError('provide two to four explicit PanelResolutionRefinement steps')
    current, plans, domains = line, [], None
    for step in refinements:
        checked, stages = _panel_resolution_inputs(current, step.panel_options,
            step.outer_documents, tolerances, factor, 16)
        # Admission above already proves only open-domain sizes differ.
        sizes = tuple((doc.line.to_dict()['cross_section']['box']['width'],
                       doc.line.to_dict()['cross_section']['layers'][-1]['thickness'])
                      for _, doc, _ in stages[4:])
        if domains is not None and sizes != domains:
            raise ValueError('outer domain sizes and order must remain fixed across refinements')
        domains = sizes
        plans.append(stages)
        current = stages[3][1]
    if 7 + len(domains) > limit:
        raise ValueError('two refinement steps and all outer checks exceed budget before any field solve')
    return limit, checked, tuple(plans)


def refine_panel_line_resolution(line, *, refinements, tolerances,
                                 refinement_factor=.5, max_solves=16):
    """Execute an explicit plan until two consecutive four-way checks pass.

    Each step evaluates volume-only, panel-only and joint refinements relative
    to the previous joint result. Volume/base, panel/base, joint/volume and
    joint/panel must all pass for every selected matrix entry and frequency.
    Two consecutive accepted steps precede the selected step's outer checks.
    The previous joint is reused, with no repeated base field evaluation.

    Each step specifies panel controls and outer documents at its exact mesh
    resolution. Only edge_size, far_size and grade decrease by the fixed
    refinement_factor. All planned inputs are validated without solving.
    No material, physical domain, port or tolerance is automatically repaired.

    max_solves counts complete line batches, not internal linear solves. Before
    each step, three batches plus all outer checks must fit. Failed fields keep
    prior results and the exact attempted input; interrupts propagate. An
    outer mismatch stops without trying to disguise it with finer panels.
    Accepted finite comparisons are not a bound on physical numerical error.
    """
    limit, tolerances, plans = _adaptive_panel_inputs(
        line, refinements, tolerances, refinement_factor, max_solves)
    return _run_adaptive_panel_resolution(limit, tolerances, plans,
        result_type=AdaptivePanelResolution,
        failure_factory=lambda stage,text,error:ResolutionFailure(
            stage, text, type(error).__name__, str(error)))


def _run_adaptive_panel_resolution(limit, tolerances, plans, *, result_type, failure_factory):
    """Shared finite-plan state machine; admission selects the physical method."""
    evaluations, comparisons = [], []
    count_outer = len(plans[0])-4
    level = 0

    def finish(reason, failure=None):
        return result_type(tolerances, evaluations, comparisons, level,
                                       count_outer, reason, failure)

    def evaluate(stage, doc, references=()):
        text = doc.dumps()
        try:
            result = doc.analyze()
            evaluations.append(ResolutionEvaluation(stage, text, result))
            for index, label in references:
                comparisons.append(_compare(evaluations[index].result, result, tolerances,
                                             label, index, len(evaluations)-1))
        except Exception as error:
            return failure_factory(stage, text, error)
        return None

    failure = evaluate('base', plans[0][0][1])
    if failure is not None:
        return finish('field-failed', failure)
    previous, consecutive = 0, 0
    for attempt, stages in enumerate(plans, 1):
        if len(evaluations)+3+count_outer > limit:
            return finish('budget-exhausted')
        level = attempt
        indices = [previous]
        start = len(comparisons)
        for name, doc, references in stages[1:4]:
            failure = evaluate(f'level:{level}:{name}', doc,
                tuple((indices[index], f'level:{level}:{label}') for index, label in references))
            if failure is not None:
                return finish('field-failed', failure)
            indices.append(len(evaluations)-1)
        consecutive = consecutive+1 if all(row.accepted for row in comparisons[start:]) else 0
        previous = indices[3]
        if consecutive < 2:
            continue
        for name, doc, _ in stages[4:]:
            failure = evaluate(name, doc, ((previous, name),))
            if failure is not None:
                return finish('field-failed', failure)
        accepted = all(row.accepted for row in comparisons[-count_outer:])
        return finish('accepted' if accepted else 'outer-unaccepted')
    return finish('resolution-unaccepted')
