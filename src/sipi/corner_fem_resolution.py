# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Finite FEM mesh/outer comparisons retaining explicit corner resolution."""
from .corner_fem_line import CornerFEMShapeTransmissionLineDocument
from .fem_shape_resolution import _fem_resolution_inputs, _assess_fem_shape_resolution

__all__ = ['assess_corner_fem_shape_line_resolution']


def _corner_fem_resolution_inputs(line, outer_documents, tolerances, refinement_factor, max_solves):
    if not isinstance(line, CornerFEMShapeTransmissionLineDocument):
        raise TypeError('line must be a CornerFEMShapeTransmissionLineDocument')
    if not isinstance(outer_documents, (tuple, list)) or not outer_documents:
        raise ValueError('provide one or more explicit outer documents')
    if any(not isinstance(doc, CornerFEMShapeTransmissionLineDocument) for doc in outer_documents):
        raise TypeError('outer documents must be CornerFEMShapeTransmissionLineDocument objects')
    models, stages = _fem_resolution_inputs(line.line, [doc.line for doc in outer_documents],
        tolerances, refinement_factor, max_solves)
    refined_corner = line.corner_size * float(refinement_factor)
    if any(doc.corner_size != refined_corner for doc in outer_documents):
        raise ValueError('outer documents must preserve the refined corner_size')
    return models, [(stage, CornerFEMShapeTransmissionLineDocument(doc,
        line.corner_size if stage == 'base' else refined_corner)) for stage, doc in stages]


def assess_corner_fem_shape_line_resolution(line, *, outer_documents, tolerances,
                                           refinement_factor=.5, max_solves=4):
    """Compare explicit corner lines with unchanged per-entry SI allowances.

    Scale corner, edge, far and grade by the same refinement factor. Preserve
    the original physical-input and open-boundary admission rules; every outer
    input must retain all refined controls. Preflight all line attempts before
    fields. Current checks, typed partial failures and interruption semantics
    match the original FEM assessment. Completed disagreement remains unaccepted.
    Finite agreement is neither an absolute accuracy nor asymptotic certificate.
    """
    models, stages = _corner_fem_resolution_inputs(line, outer_documents, tolerances,
        refinement_factor, max_solves)
    return _assess_fem_shape_resolution(models, stages)
