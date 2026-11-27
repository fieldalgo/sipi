# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit all-active corner currents and existing local surface-metal laws."""
from importlib import import_module
from inspect import signature
import numpy as np

from .constants import epsilon_0
from .crosssection import Trace
from .face_conductor import (ReferenceSurfaceMetals, FaceConductorLoss, _face_samples)
from .panel_shape_conductor import _integer
from .two_ground_conductor import (TwoGroundCurrentFactors, TwoGroundConductorLoss,
    _section, _loss_samples)
from .two_ground_face_conductor import TwoGroundFaceCurrentFactors

__all__ = ['two_ground_corner_current_factors', 'two_ground_corner_face_current_factors',
           'two_ground_corner_conductor_loss', 'two_ground_corner_conductor_loss_by_face']


def _solver():
    try:
        solver = import_module('galerkin.panel_electrostatics').solve_two_ground_corner_rectangle_edges
    except (ImportError, AttributeError) as exc:
        raise RuntimeError('Corner currents require the exact pinned galerkin development '
                           'wheel providing solve_two_ground_corner_rectangle_edges') from exc
    if not {'ground_modes', 'interpolation_degree'} <= set(signature(solver).parameters):
        raise RuntimeError('Corner currents require explicit shared resolution controls')
    return solver


def _arguments(section, panels_per_edge, ground_modes, interpolation_degree):
    checked = _section(section)
    if not 1 <= len(checked.traces) <= 2 or any(t.ground for t in checked.traces):
        raise ValueError('corner currents require one or two signals and no grounded traces')
    if any(not isinstance(t, Trace) for t in checked.traces):
        raise ValueError('corner faces require finite rectangular or tapered Trace conductors')
    count = _integer(panels_per_edge, 'panels_per_edge', 16, 512)
    modes = _integer(ground_modes, 'ground_modes', 64, 4096)
    degree = _integer(interpolation_degree, 'interpolation_degree', 24, 24)
    if count % 2 or modes % 2:
        raise ValueError('corner subdivisions and ground modes must be even')
    polygons = [t.corners()+[checked.width/2, 0.] for t in checked.traces]
    return checked, count, modes, degree, polygons


def _extract(checked, count, modes, degree, polygons):
    shared = _solver()(polygons, box_size=(checked.width, checked.height),
        panels_per_edge=count, ground_modes=modes, interpolation_degree=degree)
    return _extract_result(checked, polygons, shared, 'two-ground-corner-power-all-active')


def _extract_result(checked, polygons, shared, method):
    """Convert an admitted shared result without changing its active basis."""
    whole = shared.whole
    names = tuple(t.name for t in checked.traces)
    n = len(names)
    # Every conductor is already an active current basis. Keep its factors
    # directly: no solve(C, C) identity approximation or congruence transform.
    parts, currents = whole.current_gram, whole.current_integrals
    grouped_parts = np.concatenate((parts[:n], parts[n:].sum(axis=0, keepdims=True)))
    grouped_currents = np.concatenate((currents[:n], currents[n:].sum(axis=0, keepdims=True)))
    error = float(np.max(abs(grouped_currents-np.vstack((np.eye(n), -np.ones(n))))))
    if not np.isfinite(error) or error > 1e-10:
        raise ValueError('corner current conservation residual exceeded')
    diagnostics = {key:getattr(whole, key) for key in (
        'panel_count', 'condition_bound', 'reciprocity_error', 'residual_error',
        'current_error', 'matrix_refinement_error', 'ground_refinement_error',
        'minimum_scaled_eigenvalue')}
    diagnostics.update(ground_voltage_error=0., method=method)
    labels = tuple('signal:'+name for name in names)+('reference:bottom', 'reference:top')
    base = TwoGroundCurrentFactors(names, grouped_parts, grouped_currents,
        epsilon_0*whole.capacitance_per_permittivity, (), diagnostics, labels, parts, currents)
    tolerance = 128*np.finfo(float).eps*max(checked.width, checked.height)
    order = []
    for owner, polygon in enumerate(polygons):
        candidates = np.flatnonzero(shared.edge_owners == owner)
        if len(candidates) != 4:
            raise ValueError('shared corner edges must preserve four edges per Trace')
        selected_edges = []
        for edge in (0, 2, 3, 1):
            start, end = polygon[edge], polygon[(edge+1) % 4]
            same = np.maximum(np.max(abs(shared.edge_starts[candidates]-start), axis=1),
                              np.max(abs(shared.edge_ends[candidates]-end), axis=1)) <= tolerance
            reverse = np.maximum(np.max(abs(shared.edge_ends[candidates]-start), axis=1),
                                 np.max(abs(shared.edge_starts[candidates]-end), axis=1)) <= tolerance
            selected = candidates[same | reverse]
            if len(selected) != 1:
                raise ValueError('shared corner edges must uniquely match physical Trace faces')
            selected_edges.append(int(selected[0]))
        if len(set(selected_edges)) != 4:
            raise ValueError('shared corner edges must cover every physical Trace face once')
        order.extend(selected_edges)
    face_parts = np.concatenate((shared.edge_current_gram[order], parts[n:]))
    face_integrals = np.concatenate((shared.edge_current_integrals[order], currents[n:]))
    return TwoGroundFaceCurrentFactors(base, face_parts, face_integrals,
                                      ('reference:bottom', 'reference:top'))


def two_ground_corner_face_current_factors(section, *, panels_per_edge=128,
        ground_modes=256, interpolation_degree=24):
    """Vacuum corner-power currents for one or two all-active finite Traces.

    Both planes are grounded, sides open, and grounded traces are refused.
    Dielectric metadata does not enter this homogeneous magnetic-exterior
    current extraction. Every signal retains bottom/top/left/right faces.
    Defaults use 128 cubic subdivisions (122 actual panels per edge), 256
    actual fine Fourier modes and fixed interpolation degree 24. Refine
    panels and finite outer bounds independently for each current quantity.
    Existing methods and their defaults remain unchanged; no fallback occurs.
    """
    return _extract(*_arguments(section, panels_per_edge, ground_modes, interpolation_degree))


def two_ground_corner_current_factors(section, *, panels_per_edge=128,
        ground_modes=256, interpolation_degree=24):
    """Whole boundaries from the same explicit all-active corner-power solve."""
    return two_ground_corner_face_current_factors(section, panels_per_edge=panels_per_edge,
        ground_modes=ground_modes, interpolation_degree=interpolation_degree).base


def two_ground_corner_conductor_loss(section, frequency, *, conductors, reference,
        ground_thickness, panels_per_edge=128, ground_modes=256, interpolation_degree=24):
    """Existing whole-surface metal laws with explicit all-active corner currents.

    Keep the original skin-depth/remaining-core/coating/roughness restrictions.
    This is surface perturbation, not finite-metal diffusion or foil fitting.
    All material admission runs before the shared field solve.
    """
    checked, count, modes, degree, _ = _arguments(section, panels_per_edge,
                                                ground_modes, interpolation_degree)
    checked, names, f, metals, depth, correction, zs, labels = _loss_samples(
        checked, frequency, conductors, reference, ground_thickness)
    factors = two_ground_corner_current_factors(checked, panels_per_edge=count,
        ground_modes=modes, interpolation_degree=degree)
    if factors.names != names or factors.boundary_labels != labels:
        raise ValueError('corner extraction changed boundary order')
    resistance = np.einsum('fb,bij->fij', zs.real, factors.boundary_parts)
    internal = np.einsum('fb,bij->fij', zs.imag/(2*np.pi*f[:,None]), factors.boundary_parts)
    return TwoGroundConductorLoss(f, resistance, internal, depth, correction, zs, metals, factors)


def two_ground_corner_conductor_loss_by_face(section, frequency, *, conductors, reference,
        ground_thickness, panels_per_edge=128, ground_modes=256, interpolation_degree=24):
    """Existing face-metal laws with one all-active corner-power field solve.

    Signals use TraceFaceMetals; ReferenceSurfaceMetals supplies the two foils
    and no side or grounded-trace laws. Keep all existing material/skin-depth
    restrictions. This does not resolve coating corners or finite-metal diffusion.
    """
    checked, count, modes, degree, _ = _arguments(section, panels_per_edge,
                                                ground_modes, interpolation_degree)
    if not isinstance(reference, ReferenceSurfaceMetals):
        raise TypeError('reference must be ReferenceSurfaceMetals')
    traces, _, f, metals, depth, correction, zs, surfaces = _face_samples(
        checked, frequency, conductors, reference, ground_thickness)
    factors = two_ground_corner_face_current_factors(checked, panels_per_edge=count,
        ground_modes=modes, interpolation_degree=degree)
    if factors.names != tuple(t.name for t in traces) or factors.reference_labels != tuple(s[0] for s in surfaces):
        raise ValueError('corner extraction changed face order')
    resistance = np.einsum('fb,bij->fij', zs.real, factors.parts)
    internal = np.einsum('fb,bij->fij', zs.imag/(2*np.pi*f[:,None]), factors.parts)
    return FaceConductorLoss(f, resistance, internal, depth, correction, zs, metals, factors)
