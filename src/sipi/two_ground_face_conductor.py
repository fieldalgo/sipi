# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit two-ground straight-face currents and existing local metal laws."""
from dataclasses import dataclass
from importlib import import_module
from inspect import signature

import numpy as np

from .boundary_conductor import SurfaceMetal
from .crosssection import Trace
from .face_conductor import (TraceFaceMetals, ReferenceSurfaceMetals,
    FaceCurrentFactors, FaceConductorLoss, _face_samples)
from .panel_shape_conductor import _frozen, _relative
from .two_ground_conductor import (TwoGroundCurrentFactors, _current_arguments,
    _solve_current_factors)

__all__ = ['TwoGroundFaceCurrentFactors', 'two_ground_face_current_factors',
           'two_ground_conductor_loss_by_face']
_FACES = ('bottom', 'top', 'left', 'right')
_EDGES = (0, 2, 3, 1)


def _solver():
    try:
        solver = import_module('galerkin.panel_electrostatics').solve_two_ground_rectangle_edges
    except (ImportError, AttributeError) as exc:
        raise RuntimeError('Two-ground face currents require the pinned galerkin '
                           'development wheel with solve_two_ground_rectangle_edges') from exc
    if not {'ground_modes', 'interpolation_degree'} <= set(signature(solver).parameters):
        raise RuntimeError('Two-ground face currents require explicit shared resolution controls')
    return solver


def _arguments(section, panels_per_edge, ground_modes, interpolation_degree):
    args = _current_arguments(section, panels_per_edge, ground_modes, interpolation_degree)
    if any(not isinstance(t, Trace) for t in args[0].traces):
        raise ValueError('two-ground faces require finite rectangular or tapered Trace conductors')
    return args


@dataclass(frozen=True)
class TwoGroundFaceCurrentFactors(FaceCurrentFactors):
    """Four faces per signal, bottom/top planes, then four per ground trace.

    Each trace uses bottom/top/left/right in global cross-section coordinates.
    Ground traces remain at zero voltage, rather than floating potentials.
    """
    def __post_init__(self):
        if not isinstance(self.base, TwoGroundCurrentFactors):
            raise TypeError('base must retain whole two-ground currents')
        expected = ('reference:bottom', 'reference:top') + tuple(
            'reference:ground:'+name+':'+face
            for name in self.base.ground_trace_names for face in _FACES)
        if tuple(self.reference_labels) != expected:
            raise ValueError('reference labels must preserve two-ground face order')
        super().__post_init__()
        n = len(self.names)
        for key in ('parts', 'current_integrals'):
            value = _frozen(getattr(self, key))
            if not np.isfinite(value).all():
                raise ValueError('face current factors must be finite')
            object.__setattr__(self, key, value)
            tail = value.shape[1:]
            grouped = np.concatenate((value[:4*n].reshape(n, 4, *tail).sum(axis=1),
                value[4*n:4*n+2],
                value[4*n+2:].reshape(len(self.base.ground_trace_names), 4, *tail).sum(axis=1)))
            whole = getattr(self.base, 'boundary_parts' if key == 'parts' else 'boundary_integrals')
            error = _relative(grouped, whole) if key == 'parts' else float(np.max(abs(grouped-whole)))
            if not np.isfinite(error) or error > 1e-10:
                raise ValueError('face partition must preserve every whole two-ground boundary')
        symmetry = _relative(self.parts, self.parts.swapaxes(-1, -2))
        scale = np.max(abs(self.parts), axis=(-1, -2))
        eigenvalues = np.linalg.eigvalsh(self.parts)
        scaled = np.divide(eigenvalues, scale[:, None], out=np.zeros_like(eigenvalues),
                           where=scale[:, None] != 0)
        if symmetry > 1e-10 or np.min(scaled) < -1e-10:
            raise ValueError('face current Gram must be reciprocal and positive semidefinite')


def two_ground_face_current_factors(section, *, panels_per_edge=32,
        ground_modes=128, interpolation_degree=12):
    """Extract four straight-face current factors from one shared checked solve.

    All traces must be finite rectangular/tapered Trace objects, between two
    grounded planes and open sides. Dielectric metadata does not enter this
    vacuum current calculation. Grounded traces remain at zero potential.
    Existing extraction defaults are unchanged; missing shared capability is
    an error, with no fallback. Refine panels and outer bounds per face quantity.
    """
    checked, count, modes, degree, polygons = _arguments(
        section, panels_per_edge, ground_modes, interpolation_degree)
    shared = _solver()(polygons, box_size=(checked.width, checked.height),
        panels_per_edge=count, ground_modes=modes, interpolation_degree=degree)
    # Reuse the original reduction and diagnostics with the already computed
    # whole result; this adapter performs no second field solve.
    base = _solve_current_factors(checked, count, modes, degree, polygons,
                                 lambda *args, **kwargs: shared.whole)
    signal = [i for i, t in enumerate(checked.traces) if not t.ground]
    grounded = [i for i, t in enumerate(checked.traces) if t.ground]
    cap = shared.whole.capacitance_per_permittivity
    transform = np.linalg.solve(cap[np.ix_(signal, signal)].T, cap[:, signal].T).T
    parts = np.einsum('ai,kab,bj->kij', transform, shared.edge_current_gram, transform)
    currents = shared.edge_current_integrals @ transform
    tolerance = 128*np.finfo(float).eps*max(checked.width, checked.height)
    order = []
    for owner in signal+grounded:
        candidates = np.flatnonzero(shared.edge_owners == owner)
        if len(candidates) != 4:
            raise ValueError('shared edges must preserve four edges per Trace')
        p = polygons[owner]
        matches = []
        for edge in _EDGES:
            start, end = p[edge], p[(edge+1) % 4]
            same = np.maximum(np.max(abs(shared.edge_starts[candidates]-start), axis=1),
                              np.max(abs(shared.edge_ends[candidates]-end), axis=1)) <= tolerance
            reverse = np.maximum(np.max(abs(shared.edge_ends[candidates]-start), axis=1),
                                 np.max(abs(shared.edge_starts[candidates]-end), axis=1)) <= tolerance
            selected = candidates[same | reverse]
            if len(selected) != 1:
                raise ValueError('shared edges must uniquely match physical Trace faces')
            matches.append(int(selected[0]))
        if len(set(matches)) != 4:
            raise ValueError('shared edges must cover every physical Trace face once')
        order.extend(matches)
    n = len(signal)
    values = np.concatenate((parts[order[:4*n]], base.boundary_parts[n:n+2], parts[order[4*n:]]))
    integrals = np.concatenate((currents[order[:4*n]], base.boundary_integrals[n:n+2], currents[order[4*n:]]))
    labels = ('reference:bottom', 'reference:top') + tuple(
        'reference:ground:'+name+':'+face for name in base.ground_trace_names for face in _FACES)
    return TwoGroundFaceCurrentFactors(base, values, integrals, labels)


def two_ground_conductor_loss_by_face(section, frequency, *, conductors,
        reference, ground_thickness, panels_per_edge=32, ground_modes=128,
        interpolation_degree=12):
    """Apply local metals to signal faces, two foils and ground-trace faces.

    Signals require TraceFaceMetals. ReferenceSurfaceMetals specifies both
    foils, no side law and exactly the ground traces. A ground-trace SurfaceMetal
    is expanded uniformly to four faces; TraceFaceMetals retains its four laws.
    All original frequency, skin-depth, remaining-core, coating and roughness
    restrictions run before fields. This perturbative model does not resolve
    finite-metal diffusion, coating corners or measured-foil behavior.
    """
    checked, count, modes, degree, _ = _arguments(
        section, panels_per_edge, ground_modes, interpolation_degree)
    if not isinstance(reference, ReferenceSurfaceMetals):
        raise TypeError('reference must be ReferenceSurfaceMetals')
    expanded = ReferenceSurfaceMetals(reference.bottom, reference.top, reference.sides,
        {name: TraceFaceMetals.uniform(metal) if isinstance(metal, SurfaceMetal) else metal
         for name, metal in reference.conductors.items()})
    traces, _, f, metals, depth, correction, zs, surfaces = _face_samples(
        checked, frequency, conductors, expanded, ground_thickness)
    factors = two_ground_face_current_factors(checked, panels_per_edge=count,
        ground_modes=modes, interpolation_degree=degree)
    if factors.names != tuple(t.name for t in traces) or factors.reference_labels != tuple(s[0] for s in surfaces):
        raise ValueError('two-ground extraction changed face order')
    resistance = np.einsum('fb,bij->fij', zs.real, factors.parts)
    internal = np.einsum('fb,bij->fij', zs.imag/(2*np.pi*f[:, None]), factors.parts)
    return FaceConductorLoss(f, resistance, internal, depth, correction, zs, metals, factors)
