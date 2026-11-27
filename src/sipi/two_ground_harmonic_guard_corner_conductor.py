# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit harmonic corner-density currents and existing surface-metal laws."""
from importlib import import_module
from inspect import signature
import numpy as np

from ._two_ground_current_reuse import _reuse_current_factors
from .face_conductor import ReferenceSurfaceMetals, FaceConductorLoss, _face_samples
from .two_ground_conductor import TwoGroundConductorLoss, _loss_samples
from .constants import epsilon_0
from .two_ground_conductor import TwoGroundCurrentFactors
from .two_ground_face_conductor import TwoGroundFaceCurrentFactors
from .boundary_conductor import SurfaceMetal
from .face_conductor import TraceFaceMetals
from .two_ground_conductor import _section
from .crosssection import Trace
from .panel_shape_conductor import _integer

__all__ = ['two_ground_harmonic_guard_corner_current_factors',
           'two_ground_harmonic_guard_corner_face_current_factors',
           'two_ground_harmonic_guard_corner_conductor_loss',
           'two_ground_harmonic_guard_corner_conductor_loss_by_face']


def _solver():
    try:
        solver = import_module('galerkin.panel_electrostatics').solve_two_ground_harmonic_corner_guard_edges
    except (ImportError, AttributeError) as exc:
        raise RuntimeError('Harmonic corner currents require the exact pinned galerkin development '
                           'wheel providing solve_two_ground_harmonic_corner_guard_edges') from exc
    if not {'signal_indices', 'ground_modes', 'interpolation_degree'} <= set(signature(solver).parameters):
        raise RuntimeError('Harmonic corner currents require explicit shared resolution controls')
    return solver


def _arguments(section, panels_per_edge, ground_modes, interpolation_degree):
    checked = _section(section)
    if len(checked.traces) != 3 or sum(t.ground for t in checked.traces) != 1:
        raise ValueError('harmonic corner currents require exactly two signals and one grounded trace')
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
        shared = solver(polygons, signal_indices=tuple(i for i,t in enumerate(checked.traces) if not t.ground),
            box_size=(checked.width, checked.height),
            panels_per_edge=count, ground_modes=modes, interpolation_degree=degree)
        return _extract_result(checked, polygons, shared, 'two-ground-harmonic-corner-fixed-guard')
    return _reuse_current_factors(checked, polygons,
        ('harmonic-fixed-guard-corner-faces', count, modes, degree), solver, compute)


def _extract_result(checked, polygons, shared, method):
    """Reorder direct fixed-voltage current coordinates without another reduction."""
    whole = shared.whole
    signals = [i for i,t in enumerate(checked.traces) if not t.ground]
    grounds = [i for i,t in enumerate(checked.traces) if t.ground]
    names = tuple(checked.traces[i].name for i in signals)
    ground_names = tuple(checked.traces[i].name for i in grounds)
    n = len(signals)
    indices = signals+[len(polygons),len(polygons)+1]+grounds
    parts, currents = whole.current_gram[indices], whole.current_integrals[indices]
    grouped_parts = np.concatenate((parts[:n],parts[n:].sum(axis=0,keepdims=True)))
    grouped_currents = np.concatenate((currents[:n],currents[n:].sum(axis=0,keepdims=True)))
    error = float(np.max(abs(grouped_currents-np.vstack((np.eye(n),-np.ones(n))))))
    if not np.isfinite(error) or error > 1e-10:
        raise ValueError('guard corner current conservation residual exceeded')
    diagnostics = {key:getattr(whole,key) for key in (
        'panel_count','condition_bound','reciprocity_error','residual_error',
        'current_error','matrix_refinement_error','ground_refinement_error',
        'minimum_scaled_eigenvalue')}
    # The shared API imposes guard V=0 directly in each selected RHS.
    diagnostics.update(ground_voltage_error=0.,method=method)
    labels = (tuple('signal:'+name for name in names)+('reference:bottom','reference:top')+
              tuple('reference:ground:'+name for name in ground_names))
    base = TwoGroundCurrentFactors(names,grouped_parts,grouped_currents,
        epsilon_0*whole.capacitance_per_permittivity,ground_names,diagnostics,labels,parts,currents)
    tolerance = 128*np.finfo(float).eps*max(checked.width,checked.height)
    order = []
    for owner in signals+grounds:
        candidates = np.flatnonzero(shared.edge_owners==owner)
        if len(candidates)!=4:
            raise ValueError('shared guard edges must preserve four edges per Trace')
        polygon = polygons[owner]
        selected_edges = []
        for edge in (0,2,3,1):
            start,end = polygon[edge],polygon[(edge+1)%4]
            same = np.maximum(np.max(abs(shared.edge_starts[candidates]-start),axis=1),
                              np.max(abs(shared.edge_ends[candidates]-end),axis=1))<=tolerance
            reverse = np.maximum(np.max(abs(shared.edge_ends[candidates]-start),axis=1),
                                 np.max(abs(shared.edge_starts[candidates]-end),axis=1))<=tolerance
            selected = candidates[same|reverse]
            if len(selected)!=1:
                raise ValueError('shared guard edges must uniquely match physical Trace faces')
            selected_edges.append(int(selected[0]))
        if len(set(selected_edges))!=4:
            raise ValueError('shared guard edges must cover every physical Trace face once')
        order.extend(selected_edges)
    face_parts = np.concatenate((shared.edge_current_gram[order[:4*n]],parts[n:n+2],
                                 shared.edge_current_gram[order[4*n:]]))
    face_integrals = np.concatenate((shared.edge_current_integrals[order[:4*n]],currents[n:n+2],
                                     shared.edge_current_integrals[order[4*n:]]))
    reference_labels = ('reference:bottom','reference:top')+tuple(
        'reference:ground:'+name+':'+face for name in ground_names
        for face in ('bottom','top','left','right'))
    return TwoGroundFaceCurrentFactors(base,face_parts,face_integrals,reference_labels)


def two_ground_harmonic_guard_corner_face_current_factors(section, *, panels_per_edge=32,
        ground_modes=256, interpolation_degree=24):
    """Vacuum harmonic currents for two active Traces and one fixed-potential guard.

    Both planes and the finite guard are grounded; side walls are open.
    Dielectric metadata does not enter this homogeneous magnetic-exterior
    current extraction. Every signal and the guard retain bottom/top/left/right faces.
    Defaults use 32 cubic subdivisions (26 physical panels per edge), 256
    actual fine Fourier modes and fixed interpolation degree 24. Each physical
    panel has two static spatial density modes; at most 512 physical panels are admitted.
    Refinement to 48 subdivisions fits three supported Traces. Refine
    panels and finite outer bounds independently for each current quantity.
    Existing methods and their defaults remain unchanged; no fallback occurs.
    """
    return _extract(*_arguments(section, panels_per_edge, ground_modes, interpolation_degree))


def two_ground_harmonic_guard_corner_current_factors(section, *, panels_per_edge=32,
        ground_modes=256, interpolation_degree=24):
    """Whole boundaries from the same explicit fixed-potential guard solve."""
    return two_ground_harmonic_guard_corner_face_current_factors(section, panels_per_edge=panels_per_edge,
        ground_modes=ground_modes, interpolation_degree=interpolation_degree).base


def two_ground_harmonic_guard_corner_conductor_loss(section, frequency, *, conductors, reference,
        ground_thickness, panels_per_edge=32, ground_modes=256, interpolation_degree=24):
    """Existing whole-surface metal laws with explicit fixed-potential guard currents.

    Keep the original skin-depth/remaining-core/coating/roughness restrictions.
    This is surface perturbation, not finite-metal diffusion or foil fitting.
    All material admission runs before the shared field solve.
    """
    checked, count, modes, degree, _ = _arguments(section, panels_per_edge,
                                                ground_modes, interpolation_degree)
    checked, names, f, metals, depth, correction, zs, labels = _loss_samples(
        checked, frequency, conductors, reference, ground_thickness)
    factors = two_ground_harmonic_guard_corner_current_factors(checked, panels_per_edge=count,
        ground_modes=modes, interpolation_degree=degree)
    if factors.names != names or factors.boundary_labels != labels:
        raise ValueError('corner extraction changed boundary order')
    resistance = np.einsum('fb,bij->fij', zs.real, factors.boundary_parts)
    internal = np.einsum('fb,bij->fij', zs.imag/(2*np.pi*f[:,None]), factors.boundary_parts)
    return TwoGroundConductorLoss(f, resistance, internal, depth, correction, zs, metals, factors)


def two_ground_harmonic_guard_corner_conductor_loss_by_face(section, frequency, *, conductors, reference,
        ground_thickness, panels_per_edge=32, ground_modes=256, interpolation_degree=24):
    """Existing face-metal laws with one fixed-potential guard field solve.

    Signals use TraceFaceMetals; ReferenceSurfaceMetals supplies both foils
    and the grounded trace, with no side law. A whole guard law is expanded
    uniformly to four faces; four guard laws remain separate. Keep all existing material/skin-depth
    restrictions. This does not resolve coating corners or finite-metal diffusion.
    """
    checked, count, modes, degree, _ = _arguments(section, panels_per_edge,
                                                ground_modes, interpolation_degree)
    if not isinstance(reference, ReferenceSurfaceMetals):
        raise TypeError('reference must be ReferenceSurfaceMetals')
    expanded = ReferenceSurfaceMetals(reference.bottom, reference.top, reference.sides,
        {name: TraceFaceMetals.uniform(metal) if isinstance(metal, SurfaceMetal) else metal
         for name, metal in reference.conductors.items()})
    traces, _, f, metals, depth, correction, zs, surfaces = _face_samples(
        checked, frequency, conductors, expanded, ground_thickness)
    factors = two_ground_harmonic_guard_corner_face_current_factors(checked, panels_per_edge=count,
        ground_modes=modes, interpolation_degree=degree)
    if factors.names != tuple(t.name for t in traces) or factors.reference_labels != tuple(s[0] for s in surfaces):
        raise ValueError('corner extraction changed face order')
    resistance = np.einsum('fb,bij->fij', zs.real, factors.parts)
    internal = np.einsum('fb,bij->fij', zs.imag/(2*np.pi*f[:,None]), factors.parts)
    return FaceConductorLoss(f, resistance, internal, depth, correction, zs, metals, factors)
