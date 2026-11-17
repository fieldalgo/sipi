# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit harmonic corner-density currents and existing surface-metal laws."""
from importlib import import_module
from inspect import signature
import numpy as np

from ._two_ground_current_reuse import _reuse_current_factors
from .face_conductor import ReferenceSurfaceMetals, FaceConductorLoss, _face_samples
from .two_ground_conductor import TwoGroundConductorLoss, _loss_samples
from .two_ground_corner_conductor import _extract_result
from .two_ground_conductor import _section
from .crosssection import Trace
from .panel_shape_conductor import _integer

__all__ = ['two_ground_harmonic_three_active_corner_current_factors',
           'two_ground_harmonic_three_active_corner_face_current_factors',
           'two_ground_harmonic_three_active_corner_conductor_loss',
           'two_ground_harmonic_three_active_corner_conductor_loss_by_face']


def _solver():
    try:
        solver = import_module('galerkin.laplace_corner_harmonic_field').solve_two_ground_harmonic_corner_three_active_edges
    except (ImportError, AttributeError) as exc:
        raise RuntimeError('Harmonic corner currents require the exact pinned galerkin development '
                           'wheel providing solve_two_ground_harmonic_corner_three_active_edges') from exc
    if not {'ground_modes', 'interpolation_degree'} <= set(signature(solver).parameters):
        raise RuntimeError('Harmonic corner currents require explicit shared resolution controls')
    return solver


def _arguments(section, panels_per_edge, ground_modes, interpolation_degree):
    checked = _section(section)
    if len(checked.traces) != 3 or any(t.ground for t in checked.traces):
        raise ValueError('harmonic corner currents require exactly three signals and no grounded traces')
    if any(not isinstance(t, Trace) for t in checked.traces):
        raise ValueError('harmonic corner faces require finite rectangular or tapered Trace conductors')
    count = _integer(panels_per_edge, 'panels_per_edge', 10, 512)
    modes = _integer(ground_modes, 'ground_modes', 64, 4096)
    degree = _integer(interpolation_degree, 'interpolation_degree', 24, 24)
    if count % 2 or modes % 2:
        raise ValueError('harmonic corner subdivisions and ground modes must be even')
    if 4 * len(checked.traces) * (count - 6) > 512:
        raise ValueError('harmonic corner currents exceed 512 physical panels')
    polygons = [t.corners()+[checked.width/2, 0.] for t in checked.traces]
    return checked, count, modes, degree, polygons


def _extract(checked, count, modes, degree, polygons):
    solver = _solver()
    def compute():
        shared = solver(polygons, width=checked.width, height=checked.height,
            panels_per_edge=count, ground_modes=modes, interpolation_degree=degree)
        return _extract_result(checked, polygons, shared, 'two-ground-harmonic-corner-three-active')
    return _reuse_current_factors(checked, polygons,
        ('harmonic-three-active-corner-faces', count, modes, degree), solver, compute)


def two_ground_harmonic_three_active_corner_face_current_factors(section, *, panels_per_edge=32,
        ground_modes=256, interpolation_degree=24):
    """Vacuum harmonic corner-power currents for exactly three all-active finite Traces.

    Both planes are grounded, sides open, and grounded traces are refused.
    Dielectric metadata does not enter this homogeneous magnetic-exterior
    current extraction. Every signal retains bottom/top/left/right faces.
    Defaults use 32 cubic subdivisions (26 physical panels per edge), 256
    actual fine Fourier modes and fixed interpolation degree 24. Each physical
    panel has two static spatial density modes; at most 512 physical panels are admitted.
    Refinement to 48 subdivisions fits three supported Traces. Refine
    panels and finite outer bounds independently for each current quantity.
    Existing methods and their defaults remain unchanged; no fallback occurs.
    """
    return _extract(*_arguments(section, panels_per_edge, ground_modes, interpolation_degree))


def two_ground_harmonic_three_active_corner_current_factors(section, *, panels_per_edge=32,
        ground_modes=256, interpolation_degree=24):
    """Whole boundaries from the same explicit all-active corner-power solve."""
    return two_ground_harmonic_three_active_corner_face_current_factors(section, panels_per_edge=panels_per_edge,
        ground_modes=ground_modes, interpolation_degree=interpolation_degree).base


def two_ground_harmonic_three_active_corner_conductor_loss(section, frequency, *, conductors, reference,
        ground_thickness, panels_per_edge=32, ground_modes=256, interpolation_degree=24):
    """Existing whole-surface metal laws with explicit all-active corner currents.

    Keep the original skin-depth/remaining-core/coating/roughness restrictions.
    This is surface perturbation, not finite-metal diffusion or foil fitting.
    All material admission runs before the shared field solve.
    """
    checked, count, modes, degree, _ = _arguments(section, panels_per_edge,
                                                ground_modes, interpolation_degree)
    checked, names, f, metals, depth, correction, zs, labels = _loss_samples(
        checked, frequency, conductors, reference, ground_thickness)
    factors = two_ground_harmonic_three_active_corner_current_factors(checked, panels_per_edge=count,
        ground_modes=modes, interpolation_degree=degree)
    if factors.names != names or factors.boundary_labels != labels:
        raise ValueError('corner extraction changed boundary order')
    resistance = np.einsum('fb,bij->fij', zs.real, factors.boundary_parts)
    internal = np.einsum('fb,bij->fij', zs.imag/(2*np.pi*f[:,None]), factors.boundary_parts)
    return TwoGroundConductorLoss(f, resistance, internal, depth, correction, zs, metals, factors)


def two_ground_harmonic_three_active_corner_conductor_loss_by_face(section, frequency, *, conductors, reference,
        ground_thickness, panels_per_edge=32, ground_modes=256, interpolation_degree=24):
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
    factors = two_ground_harmonic_three_active_corner_face_current_factors(checked, panels_per_edge=count,
        ground_modes=modes, interpolation_degree=degree)
    if factors.names != tuple(t.name for t in traces) or factors.reference_labels != tuple(s[0] for s in surfaces):
        raise ValueError('corner extraction changed face order')
    resistance = np.einsum('fb,bij->fij', zs.real, factors.parts)
    internal = np.einsum('fb,bij->fij', zs.imag/(2*np.pi*f[:,None]), factors.parts)
    return FaceConductorLoss(f, resistance, internal, depth, correction, zs, metals, factors)
