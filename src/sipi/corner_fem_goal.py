# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Bounded line quantity goals with explicit corner-controlled FEM currents."""
from dataclasses import dataclass
from .corner_fem_line import CornerFEMShapeTransmissionLineDocument
from .line_goal import _seek_line_quantity
from .fem_shape_goal import (FEMShapeLineQuantityDesign, FEMShapeLineQuantityGoalError,
                             _decorate, _checked_refinement, _refine)

__all__ = ['CornerFEMShapeLineQuantityDesign', 'seek_corner_fem_shape_line_quantity']


def _refine_corner(data):
    data['line'] = _refine(data['line'])
    data['corner_size'] /= 2
    return data


@dataclass(frozen=True)
class CornerFEMShapeLineQuantityDesign(FEMShapeLineQuantityDesign):
    @property
    def document(self):
        return CornerFEMShapeTransmissionLineDocument.loads(self.result.input_json)

    @property
    def refined_document(self):
        return CornerFEMShapeTransmissionLineDocument.loads(self.refined_result.input_json)

    def to_dict(self):
        out = super().to_dict()
        out['scope'] = 'bounded-single-parameter-corner-fem-shape-line-goal'
        return out


def seek_corner_fem_shape_line_quantity(factory, bounds, target, *, quantity, tolerance,
                                        max_evaluations=40):
    """Seek a scalar or launched paired quantity with explicit corner inputs.

    The factory returns a CornerFEMShapeTransmissionLineDocument with one
    positive frequency and zero length. The existing identity, attempt budget,
    bracket and bisection rules apply. Refinement halves resolved edge/far/grade
    and corner settings on the frozen selected input, without recalling the
    factory. Both absolute target checks and the original 0.005 relative
    quantity-change check remain mandatory. Current derivative, flux and metal
    gates are unchanged; typed failures retain complete corner input/history.

    This bounded search does not certify weak mutual loss, outer boundaries,
    continuity, uniqueness or global accuracy. Saved factories are a separate
    contract; this function does not serialize a callable.
    """
    result = _seek_line_quantity(factory, bounds, target, quantity=quantity,
        tolerance=tolerance, max_evaluations=max_evaluations,
        document_type=CornerFEMShapeTransmissionLineDocument,
        design_type=CornerFEMShapeLineQuantityDesign,
        error_type=FEMShapeLineQuantityGoalError, refine_input=_refine_corner,
        decorate_error=_decorate, input_metadata=lambda data: data['line'])
    return _checked_refinement(result, quantity)
