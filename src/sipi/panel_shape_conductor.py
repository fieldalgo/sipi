# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit capacitance-shape derivatives for integrated PEC surface currents."""
from dataclasses import dataclass
from numbers import Integral, Real
from types import MappingProxyType

import numpy as np

from .boundary_conductor import _boundary_samples, _boundary_from_factors
from .constants import epsilon_0
from .crosssection import CrossSection, Layer
from .polygons import PolygonTrace
from .panel_conductor import PanelCurrentFactors, _panel_solver

__all__ = ['PanelShapeRequest', 'PanelShapeSample', 'PanelShapeCurrentFactors',
           'PanelShapeCurrentError', 'panel_shape_current_factors',
           'panel_shape_conductor_loss_by_boundary']

_DIAGNOSTICS = ('panel_count', 'condition_bound', 'reciprocity_error', 'residual_error',
                'current_error', 'matrix_refinement_error', 'ground_refinement_error')


def _frozen(value):
    array = np.asarray(value, dtype=float)
    if not np.all(np.isfinite(array)):
        raise ValueError('nonfinite panel shape-current result')
    return np.frombuffer(array.tobytes(), dtype=float).reshape(array.shape)


@dataclass(frozen=True)
class PanelShapeRequest:
    """Exact public boundary-solver request; polygons use its bottom-left frame."""
    stage: str
    polygons: tuple
    width: float
    height: float
    panels_per_edge: int
    ground_modes: int
    interpolation_degree: int

    def __post_init__(self):
        object.__setattr__(self, 'polygons', tuple(_frozen(p) for p in self.polygons))

    def arguments(self):
        """Return an independent, JSON-compatible request as saved records keep it.

        Saved records keep ``width`` and ``height``; ``solver_arguments`` gives the
        same numbers in the keywords of ``galerkin.panel_electrostatics``.
        """
        return dict(polygons=[p.tolist() for p in self.polygons], width=self.width,
                    height=self.height, panels_per_edge=self.panels_per_edge,
                    ground_modes=self.ground_modes, interpolation_degree=self.interpolation_degree)

    def solver_arguments(self):
        """Return ``arguments()`` as keywords of the public panel solver (``box_size`` in m)."""
        out = self.arguments()
        out['box_size'] = [out.pop('width'), out.pop('height')]
        return out


@dataclass(frozen=True)
class PanelShapeSample:
    request: PanelShapeRequest
    capacitance_per_permittivity: np.ndarray
    diagnostics: object

    def __post_init__(self):
        object.__setattr__(self, 'capacitance_per_permittivity', _frozen(self.capacitance_per_permittivity))
        object.__setattr__(self, 'diagnostics', MappingProxyType(dict(self.diagnostics)))


class PanelShapeCurrentError(ValueError):
    """A failed solve or derivative check, retaining completed samples and request."""
    def __init__(self, message, *, samples, request=None, step_parts=None, boundary_step_parts=None):
        super().__init__(message)
        self.samples = tuple(samples)
        self.request = request
        self.step_parts = None if step_parts is None else _frozen(step_parts)
        self.boundary_step_parts = None if boundary_step_parts is None else _frozen(boundary_step_parts)


@dataclass(frozen=True)
class PanelShapeCurrentFactors(PanelCurrentFactors):
    """Small-step integrated currents, with both step observations and all solves.

    Step agreement is not a panel/domain convergence or absolute error bound.
    Algebraic current conservation is also independent of resistance accuracy.
    """
    samples: tuple
    step_m: float
    step_parts: np.ndarray
    boundary_step_parts: np.ndarray

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, 'samples', tuple(self.samples))
        parts = _frozen(self.step_parts)
        if parts.shape != (2, *self.parts.shape):
            raise ValueError('shape-current observations need two boundary matrices')
        object.__setattr__(self, 'step_parts', parts)
        ungrouped = _frozen(self.boundary_step_parts)
        if ungrouped.shape != (2, len(self.names)+len(self.ground_trace_names)+1, len(self.names), len(self.names)):
            raise ValueError('shape-current boundary observations have incorrect shape')
        object.__setattr__(self, 'boundary_step_parts', ungrouped)


def _relative(a, b):
    denominator = np.maximum(abs(a), abs(b))
    values = np.zeros_like(denominator)
    np.divide(abs(a-b), denominator, out=values, where=denominator > 0)
    return float(np.max(values))


def _offset_velocity(points):
    """Continuous vertex velocities with unit inward normal on every edge."""
    edge = np.roll(points, -1, axis=0)-points
    lengths = np.linalg.norm(edge, axis=1)
    if np.any(lengths <= 0):
        raise ValueError('shape currents require resolved polygon edges')
    tangent = edge/lengths[:, None]
    following = np.roll(tangent, -1, axis=0)
    turns = tangent[:, 0]*following[:, 1]-tangent[:, 1]*following[:, 0]
    if np.all(turns < 0):
        return _offset_velocity(points[::-1])
    if not np.all(turns > 128*np.finfo(float).eps):
        raise ValueError('shape currents require strictly convex polygons')
    # PolygonTrace independently checks simplicity; these tests exclude concavity.
    normal = np.column_stack((tangent[:, 1], -tangent[:, 0]))
    previous = np.roll(normal, 1, axis=0)
    denominator = 1+np.sum(normal*previous, axis=1)
    if np.any(denominator <= 128*np.finfo(float).eps):
        raise ValueError('shape-current polygon corner is unresolved')
    return points, -(normal+previous)/denominator[:, None], lengths


def _integer(value, name, low, high):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral) or not low <= value <= high:
        raise ValueError(f'{name} must be an integer in [{low}, {high}]')
    return int(value)


def _prepare(section, panels_per_edge, ground_modes, interpolation_degree, step_fraction):
    if not isinstance(section, CrossSection):
        raise TypeError('section must be a CrossSection')
    checked = CrossSection(section.layers, section.traces, section.width,
                           bottom=section.bottom, top=section.top, sides=section.sides,
                           dielectric_regions=section.dielectric_regions)
    if (checked.bottom, checked.top, checked.sides) != ('ground', 'open', 'open'):
        raise ValueError('shape currents require bottom ground and open top/sides')
    count = _integer(panels_per_edge, 'panels_per_edge', 1, 256)
    modes = _integer(ground_modes, 'ground_modes', 64, 4096)
    degree = _integer(interpolation_degree, 'interpolation_degree', 10, 16)
    if degree % 2:
        raise ValueError('interpolation_degree must be one of 10, 12, 14, 16')
    if (isinstance(step_fraction, (bool, np.bool_)) or not isinstance(step_fraction, Real)
            or not np.isfinite(step_fraction) or not 1e-5 <= step_fraction <= 1e-2):
        raise ValueError('step_fraction must be finite in [1e-5, 1e-2]')
    if not 1 <= len(checked.traces) <= 16:
        raise ValueError('shape currents require 1..16 traces')
    shapes = []
    for trace in checked.traces:
        if trace.thickness <= 0:
            raise ValueError('shape currents require positive conductor thickness')
        shapes.append(_offset_velocity(trace.corners()+[checked.width/2, 0.]))
    if sum(len(p) for p, _, _ in shapes)*count > 2048:
        raise ValueError('total boundary panel count exceeds 2048')
    step = float(step_fraction)*min(float(length.min()) for _, _, length in shapes)
    polygons = [p for p, _, _ in shapes]
    specifications = [('base', polygons, checked.height)]
    for level, delta in enumerate((step, step/2)):
        for boundary in range(len(polygons)+1):
            for sign in (-1, 1):
                shifted = [p.copy() for p in polygons]
                height = checked.height
                if boundary < len(polygons):
                    shifted[boundary] += sign*delta*shapes[boundary][1]
                else:
                    for p in shifted:
                        p[:, 1] += sign*delta
                    height += sign*delta
                specifications.append((f'step-{level}/boundary-{boundary}/sign-{sign}', shifted, height))
    requests = []
    # Validate every offset shape before the first field solve. The shared solver
    # retains its own numerical and more restrictive domain-admission checks.
    for stage, points, height in specifications:
        traces = [PolygonTrace(t.name, p-[checked.width/2, 0.], ground=t.ground)
                  for t, p in zip(checked.traces, points)]
        CrossSection([Layer('vacuum', height, 1.)], traces, checked.width)
        for p in points:
            _offset_velocity(p)
        if not .25 <= checked.width/height <= 4:
            raise ValueError('every shape-current box needs width/height in [0.25, 4]')
        requests.append(PanelShapeRequest(stage, tuple(points), checked.width, height, count, modes, degree))
    return checked, step, tuple(requests)


def panel_shape_current_factors(section, *, panels_per_edge=32, ground_modes=512,
                                interpolation_degree=16, step_fraction=1e-3):
    """Explicit integrated surface currents from two capacitance difference steps.

    For each metal boundary, shrink it by h along its inward normals; for the
    bottom ground, move the ground outward while fixing other normal positions.
    -d(C/epsilon)/dh is the voltage-basis boundary Gram. Unit-current potential
    normalization and explicit zero-voltage ground traces are applied afterward.

    Uses 1+4*(number of traces+1) public shared solves at fixed panel controls.
    All entries of the two step results, including their sum, must agree to
    1e-4 relative, without an absolute denominator floor. This checks finite
    differencing only. Independently refine panels and the outer box; small
    mutual entries can require more resolution. No existing extraction default
    or saved-line schema is changed. Convex positive-thickness traces only.
    """
    section, step, requests = _prepare(section, panels_per_edge, ground_modes,
                                      interpolation_degree, step_fraction)
    solver = _panel_solver()
    samples = []
    base = None
    for request in requests:
        try:
            result = solver(**request.solver_arguments())
            sample = PanelShapeSample(request, result.capacitance_per_permittivity,
                                      {key: getattr(result, key) for key in _DIAGNOSTICS})
        except Exception as exc:
            raise PanelShapeCurrentError(f'{request.stage}: {type(exc).__name__}: {exc}',
                                        samples=samples, request=request) from exc
        samples.append(sample)
        if base is None:
            base = result
    signal = [i for i, t in enumerate(section.traces) if not t.ground]
    grounded = [i for i, t in enumerate(section.traces) if t.ground]
    reference = grounded+[len(section.traces)]
    cap = samples[0].capacitance_per_permittivity
    css = cap[np.ix_(signal, signal)]
    potential = np.zeros((len(section.traces), len(signal)))
    potential[signal] = np.linalg.inv(css)
    current = base.current_integrals@(cap@potential)
    currents = np.vstack((current[signal], current[reference].sum(axis=0)))
    rows, ungrouped = [], []
    position = 1
    for delta in (step, step/2):
        parts = []
        for _ in range(len(section.traces)+1):
            minus, plus = samples[position:position+2]
            raw = -(plus.capacitance_per_permittivity-minus.capacitance_per_permittivity)/(2*delta)
            value = potential.T@raw@potential
            if _relative(value, value.T) > 1e-10:
                raise PanelShapeCurrentError('shape-current matrix reciprocity residual exceeded', samples=samples)
            parts.append((value+value.T)/2)
            position += 2
        parts = np.array(parts)
        ungrouped.append(parts)
        rows.append(np.concatenate((parts[signal], parts[reference].sum(axis=0, keepdims=True))))
    rows, ungrouped = np.array(rows), np.array(ungrouped)
    difference = max(_relative(rows[0], rows[1]), _relative(ungrouped[0], ungrouped[1]),
                     _relative(rows[0].sum(axis=0), rows[1].sum(axis=0)))
    evidence = dict(samples=samples, step_parts=rows, boundary_step_parts=ungrouped)
    if not np.isfinite(difference) or difference > 1e-4:
        raise PanelShapeCurrentError('shape-current difference steps did not agree', **evidence)
    minimum = np.linalg.eigvalsh(ungrouped).min(axis=-1)
    if np.any(minimum < -1e-10*np.max(abs(ungrouped), axis=(-1, -2))):
        raise PanelShapeCurrentError('shape-current boundary matrix is not positive semidefinite', **evidence)
    if np.linalg.eigvalsh(rows.sum(axis=1)).min() <= 0:
        raise PanelShapeCurrentError('shape-current total matrix is not positive definite', **evidence)
    diagnostics = dict(samples[0].diagnostics)
    diagnostics.update(solve_count=len(samples), step_relative_change=difference,
                       ground_voltage_error=float(np.max(abs(potential[grounded]))) if grounded else 0.)
    factors = PanelShapeCurrentFactors(tuple(section.traces[i].name for i in signal), rows[-1], currents,
        epsilon_0*css, tuple(section.traces[i].name for i in grounded), diagnostics, tuple(samples), step, rows, ungrouped)
    if factors.current_error > 1e-10:
        raise PanelShapeCurrentError('shape-current algebraic conservation residual exceeded', **evidence)
    return factors


def panel_shape_conductor_loss_by_boundary(section, frequency, *, conductors, reference,
        ground_thickness, panels_per_edge=32, ground_modes=512, interpolation_degree=16,
        step_fraction=1e-3):
    """Apply existing per-boundary metal laws to explicit shape-current factors."""
    if not isinstance(section, CrossSection):
        raise TypeError('section must be a CrossSection')
    names, f, metals, depth, correction, zs = _boundary_samples(
        section, frequency, conductors, reference, ground_thickness)
    factors = panel_shape_current_factors(section, panels_per_edge=panels_per_edge,
        ground_modes=ground_modes, interpolation_degree=interpolation_degree, step_fraction=step_fraction)
    if factors.names != names:
        raise ValueError('shape-current solve changed signal boundary order')
    return _boundary_from_factors(factors, f, metals, depth, correction, zs)
