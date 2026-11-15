# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit bounded FEM-current line goals with retained field evidence."""
from dataclasses import dataclass
import json
from .line_goal import LineQuantityDesign, LineQuantityGoalError, _seek_line_quantity
from .fem_shape_line import FEMShapeTransmissionLineDocument, FEMShapeLineError

__all__ = ['FEMShapeLineQuantityDesign', 'FEMShapeLineQuantityGoalError',
           'seek_fem_shape_line_quantity']


class FEMShapeLineQuantityGoalError(LineQuantityGoalError):
    """Completed attempts plus typed line evidence or completed diagnostic fields."""
    _details_json = None
    _current_json = None

    @property
    def cause_details(self):
        return None if self._details_json is None else json.loads(self._details_json)

    @property
    def current_solver(self):
        return None if self._current_json is None else json.loads(self._current_json)

    def to_dict(self):
        return dict(type=type(self).__name__, message=str(self), attempts=self.attempts,
            quantity=self.quantity, unit=self.unit, failed_parameter=self.failed_parameter,
            stage=self.stage, cause_type=self.cause_type,
            input=None if self.input_json is None else json.loads(self.input_json),
            history=[row.to_dict() for row in self.history], cause_details=self.cause_details,
            current_solver=self.current_solver)


def _decorate(error, cause, line):
    if isinstance(cause, FEMShapeLineError):
        error._details_json = json.dumps(cause.to_dict(), allow_nan=False)
    if line is not None:
        error._current_json = json.dumps(line.current_record(), allow_nan=False)


def _refine(data):
    doc = FEMShapeTransmissionLineDocument.from_dict(data)
    cross = doc.cross_section
    settings = cross.section.mesh_settings(**cross.mesh_options)
    for key in ('edge_size', 'far_size', 'grade'): settings[key] /= 2
    data['cross_section']['mesh'] = settings
    return data


@dataclass(frozen=True)
class FEMShapeLineQuantityDesign(LineQuantityDesign):
    @property
    def document(self): return FEMShapeTransmissionLineDocument.loads(self.result.input_json)

    @property
    def refined_document(self): return FEMShapeTransmissionLineDocument.loads(self.refined_result.input_json)

    def to_dict(self):
        out = super().to_dict()
        out['scope'] = 'bounded-single-parameter-fem-shape-line-goal'
        out['current_solver'] = self.result.current_record()
        out['refined_current_solver'] = self.refined_result.current_record()
        return out


def seek_fem_shape_line_quantity(factory, bounds, target, *, quantity, tolerance, max_evaluations=40):
    """Seek Re(Zc), alpha, Re(Zdd) or Re(Zcc) with explicit FEM shape currents.

    The factory returns a FEMShapeTransmissionLineDocument with one positive
    frequency, zero length and one scalar or two ordered paired signals.
    Identity stays fixed. Both endpoints must succeed; otherwise a bracketing
    sign change is required for bisection. Reserve one complete line attempt
    to halve resolved edge_size/far_size/grade on the frozen chosen input.
    Both values must meet the same absolute tolerance and the relative change
    abs(refined-value)/refined must not exceed 0.005 (both zero is zero change).

    Every attempted factory, field and diagnostic counts, including failures;
    internal capacitance and velocity solves are not separately budgeted.
    No factory recall for refinement, retry, clipping or silent fallback.
    Original gradient, current-derivative and metal admission gates remain.
    Typed partial fields and complete diagnostic fields survive errors;
    interrupts propagate. This does not certify outer-domain sufficiency,
    continuity, uniqueness, global optimality or empirical accuracy.
    """
    result = _seek_line_quantity(factory, bounds, target, quantity=quantity,
        tolerance=tolerance, max_evaluations=max_evaluations,
        document_type=FEMShapeTransmissionLineDocument, design_type=FEMShapeLineQuantityDesign,
        error_type=FEMShapeLineQuantityGoalError, refine_input=_refine, decorate_error=_decorate)
    return _checked_refinement(result, quantity)


def _checked_refinement(result, quantity):
    change = abs(result.refined_value-result.value)
    relative = change/result.refined_value if result.refined_value else (0. if change == 0 else float('inf'))
    if relative > .005:
        error = FEMShapeLineQuantityGoalError('refined FEM mesh changes quantity beyond 0.005; tighten mesh and rerun',
            result.history, attempts=len(result.history), quantity=quantity, failed_parameter=result.parameter,
            stage='refinement/mesh-change', input_json=result.refined_result.input_json)
        _decorate(error, None, result.refined_result)
        raise error
    return result
