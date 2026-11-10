# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Bounded single-parameter impedance design with a separate mesh check."""

from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
import math
import json
from numbers import Real
from meshine import MeshSizeLimitError

from .crosssection import CrossSection
from .document import CrossSectionDocument
from .impedance_material import _material_input, _analyze_material, _frequency

__all__ = ['ImpedanceDesign', 'DesignEvaluation', 'GoalSeekError',
           'GoalMeshSizeLimitError', 'seek_impedance']


@dataclass(frozen=True)
class DesignEvaluation:
    parameter: float
    impedance: float
    stage: str


@dataclass(frozen=True)
class ImpedanceDesign:
    """Successful target on both requested and refined meshes.

    impedances and residuals are in ohms; parameter has the units of the
    caller's factory. document is the requested-mesh input, not the refined
    one. This is a numerical check, not a certified manufacturing tolerance.
    material_evaluation_json, when present, stores the fixed frequency/models
    and must accompany document to reproduce the impedance.
    """
    parameter: float
    target: float
    impedance: float
    refined_impedance: float
    quantity: str
    document: CrossSectionDocument
    history: tuple[DesignEvaluation, ...]
    material_evaluation_json: str | None = None

    @property
    def residual(self):
        return self.impedance-self.target

    @property
    def refined_residual(self):
        return self.refined_impedance-self.target

    @property
    def mesh_change(self):
        return self.refined_impedance-self.impedance


class GoalSeekError(RuntimeError):
    """A bounded search failed; history contains completed solves only."""
    def __init__(self, message, history):
        super().__init__(message)
        self.history = tuple(history)


class GoalMeshSizeLimitError(GoalSeekError, MeshSizeLimitError):
    """A field mesh exceeded its point budget, retaining completed goal work.

    Catchable as either original exception family. parameter has the factory's
    units; stage is search or refinement. input_json contains the failed
    geometry with resolved mesh settings, without attempting another solve.
    """
    def __init__(self, message, history, *, parameter, stage, cause_type,
                 input_json, material_evaluation_json=None):
        super().__init__(message, history)
        self.parameter = parameter
        self.stage = stage
        self.attempts = len(self.history) + 1
        self.cause_type = cause_type
        self.input_json = input_json
        self.material_evaluation_json = material_evaluation_json


def _positive(name, value):
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or value <= 0:
        raise ValueError(f'{name} must be a positive finite real number')
    return float(value)


def seek_impedance(factory, bounds, target, *, quantity='z0', tolerance=0.1,
                   mesh=None, max_evaluations=40, frequency=None, materials=None,
                   material_factory=None):
    """Bisect a positive parameter range, then check a refined mesh.

    factory(parameter) returns a CrossSection. quantity is z0 (one signal),
    z_diff (a symmetric pair), or z_diff_forward (a pair's real lossless
    forward-current launch, Icommon=0). bounds have the factory parameter's units;
    target/tolerance are ohms. Factory errors propagate unchanged.
    A field MeshSizeLimitError becomes GoalMeshSizeLimitError with its original
    cause, completed history and failed input; other solver errors propagate.

    Both endpoints must be valid. Apart from an endpoint already within
    tolerance, their residuals must bracket zero. Reserve one solve for a final
    refinement (edge_size, far_size and grade halved). Both the requested and
    refined impedances must be within tolerance of target, or GoalSeekError is
    raised. Tighten mesh options and rerun if refinement misses the target.
    No function promises monotonicity for an arbitrary factory.

    Supply frequency (Hz) and materials together to evaluate fixed scalar or
    principal-axis models. Impedance still uses Re(C_complex) and vacuum L,
    not conductor R or a complex lossy characteristic impedance. The result's
    material_evaluation_json must accompany its geometry document for replay.
    Alternatively, material_factory(parameter) returns the model mapping at
    each search point. Supply a fixed frequency and omit materials. The chosen
    mapping is captured once and reused unchanged for the refinement solve.
    """
    if not callable(factory):
        raise TypeError('factory must be callable')
    if quantity not in ('z0', 'z_diff', 'z_diff_forward'):
        raise ValueError('quantity must be z0, z_diff or z_diff_forward')
    try:
        lower, upper = bounds
    except (TypeError, ValueError) as exc:
        raise ValueError('bounds must contain two positive finite numbers') from exc
    lower, upper = _positive('lower bound', lower), _positive('upper bound', upper)
    if lower >= upper:
        raise ValueError('lower bound must be smaller than upper bound')
    target, tolerance = _positive('target', target), _positive('tolerance', tolerance)
    if isinstance(max_evaluations, bool) or not isinstance(max_evaluations, int) or max_evaluations < 3:
        raise ValueError('max_evaluations must be an integer >= 3')
    options = {} if mesh is None else dict(mesh)
    if material_factory is not None:
        if not callable(material_factory) or materials is not None or frequency is None:
            raise ValueError('material_factory requires fixed frequency, is callable, and excludes materials')
        frequency = _frequency(frequency)
        material = None
    else:
        material = _material_input(frequency, materials)
    history = []

    @contextmanager
    def preserve_mesh_failure(parameter, stage, document, evaluated_material):
        try:
            yield
        except MeshSizeLimitError as exc:
            section = document.section
            failed = CrossSectionDocument(section,
                mesh=section.mesh_settings(**document.mesh_options))
            material_json = (None if evaluated_material is None else
                             json.dumps(evaluated_material, sort_keys=True, allow_nan=False))
            raise GoalMeshSizeLimitError(
                f'mesh point limit during {stage}: {exc}', history,
                parameter=parameter, stage=stage, cause_type=type(exc).__name__,
                input_json=failed.dumps(), material_evaluation_json=material_json) from exc

    def evaluate(parameter):
        if len(history) >= max_evaluations-1:
            raise GoalSeekError('evaluation limit reached before target convergence', history)
        section = factory(parameter)
        doc = CrossSectionDocument(section, mesh=options)
        evaluated_material = (material if material_factory is None else
                              _material_input(frequency, material_factory(parameter)))
        with preserve_mesh_failure(parameter, 'search', doc, evaluated_material):
            line = (doc.analyze() if evaluated_material is None
                    else _analyze_material(doc, evaluated_material, quantity))
        value = impedance(line)
        history.append(DesignEvaluation(parameter, value, 'search'))
        return value-target, doc, evaluated_material

    def impedance(line):
        value = line.even_odd()['z_diff'] if quantity == 'z_diff' else getattr(line, quantity)
        if not math.isfinite(value) or value <= 0:
            raise GoalSeekError('solver returned invalid impedance', history)
        return float(value)

    fl, dl, ml = evaluate(lower)
    fu, du, mu = evaluate(upper)
    if abs(fl) <= tolerance or abs(fu) <= tolerance:
        x, residual, doc, selected_material = ((lower, fl, dl, ml) if abs(fl) <= abs(fu)
                                                else (upper, fu, du, mu))
    else:
        if (fl > 0) == (fu > 0):
            raise GoalSeekError('target is not bracketed by the endpoint impedances', history)
        while True:
            x = lower+(upper-lower)/2
            if x == lower or x == upper:
                raise GoalSeekError('parameter resolution exhausted before target convergence', history)
            residual, doc, selected_material = evaluate(x)
            if abs(residual) <= tolerance:
                break
            if (residual > 0) == (fl > 0):
                lower, fl = x, residual
            else:
                upper = x

    section = doc.section
    fine = section.mesh_settings(**doc.mesh_options)
    for key in ('edge_size', 'far_size', 'grade'):
        fine[key] /= 2
    refined_doc = CrossSectionDocument(section, mesh=fine)
    with preserve_mesh_failure(x, 'refinement', refined_doc, selected_material):
        refined_line = (section.analyze(**fine) if selected_material is None
                        else _analyze_material(refined_doc, selected_material, quantity))
    refined = impedance(refined_line)
    history.append(DesignEvaluation(x, refined, 'refinement'))
    if abs(refined-target) > tolerance:
        raise GoalSeekError('refined mesh misses target; tighten mesh settings and rerun', history)
    saved = (None if selected_material is None else
             json.dumps(selected_material, sort_keys=True, allow_nan=False))
    return ImpedanceDesign(x, target, residual+target, refined, quantity, doc, tuple(history), saved)
