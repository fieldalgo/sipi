# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Separate finite resolution observations for explicit shape-current lines."""
from dataclasses import dataclass
import json

from .panel_resolution import PanelResolutionAssessment, _panel_resolution_inputs
from .line_resolution import ResolutionFailure, ResolutionEvaluation, _compare
from .shape_panel_line import (ShapePanelTransmissionLineDocument, ShapePanelLineError,
                               shape_current_record)

__all__ = ['ShapePanelResolutionFailure', 'ShapePanelResolutionAssessment',
           'assess_shape_panel_line_resolution']


@dataclass(frozen=True)
class ShapePanelResolutionFailure(ResolutionFailure):
    """Exact failed input plus the saved line's immutable partial-current record."""
    details_json: str | None = None

    @property
    def details(self):
        return None if self.details_json is None else json.loads(self.details_json)


@dataclass(frozen=True)
class ShapePanelResolutionAssessment(PanelResolutionAssessment):
    """Finite per-entry comparisons, retaining complete current work on every axis."""
    def to_dict(self):
        from .line_resolution_document import resolution_record
        result = resolution_record(self)
        for saved, row in zip(result['evaluations'], self.evaluations):
            saved['current_solver'] = shape_current_record(row.result.current_factors,
                                                          row.result.panel_settings)
        if self.failure is not None:
            result['failure']['details'] = self.failure.details
        return result


def _shape_panel_resolution_inputs(line, refined_panel_options, outer_documents,
                                    tolerances, refinement_factor, max_solves):
    if not isinstance(line, ShapePanelTransmissionLineDocument):
        raise TypeError('line must be a ShapePanelTransmissionLineDocument')
    if (not isinstance(outer_documents, (list, tuple)) or not outer_documents
            or any(not isinstance(doc, ShapePanelTransmissionLineDocument) for doc in outer_documents)):
        raise ValueError('provide one or more explicit shape-panel outer documents')
    fraction = line.to_dict()['step_fraction']
    if any(doc.to_dict()['step_fraction'] != fraction for doc in outer_documents):
        raise ValueError('shape-current step_fraction must stay fixed across outer inputs')
    tolerances, plan = _panel_resolution_inputs(line.line, refined_panel_options,
        [doc.line for doc in outer_documents], tolerances, refinement_factor, max_solves)
    # Construct every offset request before beginning any field work. Nested
    # admission preserves physical inputs, resolved volume controls and domains.
    stages = [(stage, ShapePanelTransmissionLineDocument(doc, step_fraction=fraction), references)
              for stage, doc, references in plan]
    return tolerances, stages


def assess_shape_panel_line_resolution(line, *, refined_panel_options, outer_documents,
                                       tolerances, refinement_factor=.5, max_solves=6):
    """Compare independent panel, volume, joint and explicit outer evaluations.

    Reuses the existing finite-resolution admission and per-entry SI allowance
    contract. Two single-axis results compare with base; joint compares with
    each separately, and each outer result compares with joint. Every selected
    matrix entry/frequency must pass. There is no small-entry denominator floor.

    The shape difference fraction stays fixed and its two-step check remains
    active in every solve. max_solves counts complete line evaluations, not the
    multiple shared panel solves inside each. No field input is automatically
    repaired. Completed disagreement, partial failure and interruption remain
    distinct. Finite acceptance is not an absolute accuracy certificate.
    """
    tolerances, stages = _shape_panel_resolution_inputs(line, refined_panel_options,
        outer_documents, tolerances, refinement_factor, max_solves)
    evaluations, comparisons = [], []
    for stage, doc, references in stages:
        text = doc.dumps()
        try:
            result = doc.analyze()
            evaluations.append(ResolutionEvaluation(stage, text, result))
            for index, label in references:
                comparisons.append(_compare(evaluations[index].result, result, tolerances,
                                             label, index, len(evaluations)-1))
        except Exception as error:
            details = json.dumps(error.to_dict(), allow_nan=False) if isinstance(error, ShapePanelLineError) else None
            failure = ShapePanelResolutionFailure(stage, text, type(error).__name__, str(error), details)
            return ShapePanelResolutionAssessment(tolerances, evaluations, comparisons, len(stages), failure)
    return ShapePanelResolutionAssessment(tolerances, evaluations, comparisons, len(stages))
