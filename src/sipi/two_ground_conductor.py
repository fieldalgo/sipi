# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit two-ground boundary currents and whole-surface metal laws."""
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import import_module
from inspect import signature

import numpy as np

from .boundary_conductor import SurfaceMetal, _remaining_dimension
from .constants import epsilon_0
from .crosssection import CrossSection
from .face_conductor import ReferenceSurfaceMetals, _reference_parts
from .network import _frequencies, _scalar, rlgc_network
from .panel_conductor import PanelCurrentFactors
from .panel_shape_conductor import _frozen, _integer, _offset_velocity

__all__ = ['TwoGroundCurrentFactors', 'TwoGroundConductorLoss',
           'two_ground_current_factors', 'two_ground_conductor_loss']


def _solver():
    try:
        solver = import_module('galerkin.laplace_two_ground').solve_two_ground_rectangle
    except (ImportError, AttributeError) as exc:
        raise RuntimeError('Two-ground currents require the galerkin development wheel '
                           'providing laplace_two_ground; installed capability is unavailable') from exc
    if not {'ground_modes', 'interpolation_degree'} <= set(signature(solver).parameters):
        raise RuntimeError('Two-ground currents require explicit ground_modes and interpolation_degree controls')
    return solver


def _section(section):
    if not isinstance(section, CrossSection):
        raise TypeError('section must be a CrossSection')
    checked = CrossSection(section.layers, section.traces, section.width,
                           bottom=section.bottom, top=section.top, sides=section.sides,
                           dielectric_regions=section.dielectric_regions)
    if (checked.bottom, checked.top, checked.sides) != ('ground', 'ground', 'open'):
        raise ValueError('two-ground currents require grounded bottom/top and open sides')
    if not 1 <= len(checked.traces) <= 16 or any(t.thickness <= 0 for t in checked.traces):
        raise ValueError('two-ground currents require 1..16 finite-thickness traces')
    if not .25 <= checked.width/checked.height <= 16:
        raise ValueError('two-ground width/height must lie in [0.25, 16]')
    for trace in checked.traces:
        _offset_velocity(trace.corners())
    return checked


@dataclass(frozen=True)
class TwoGroundCurrentFactors(PanelCurrentFactors):
    """Grouped currents plus separate signals, bottom, top, grounded traces.

    All geometrical surfaces remain at their original physical coordinates.
    Grounded traces have zero potential, not a floating-conductor reduction.
    """
    boundary_labels: tuple[str, ...]
    boundary_parts: np.ndarray
    boundary_integrals: np.ndarray

    def __post_init__(self):
        super().__post_init__()
        expected = (tuple('signal:'+s for s in self.names)+
                    ('reference:bottom', 'reference:top')+
                    tuple('reference:ground:'+s for s in self.ground_trace_names))
        if tuple(self.boundary_labels) != expected:
            raise ValueError('two-ground boundary labels have incorrect order')
        object.__setattr__(self, 'boundary_labels', expected)
        n = len(self.names)
        for key, shape, grouped in (
            ('boundary_parts', (len(expected), n, n), self.parts),
            ('boundary_integrals', (len(expected), n), self.current_integrals),
        ):
            value = _frozen(getattr(self, key))
            if value.shape != shape:
                raise ValueError(key+' has incorrect shape')
            recombined = np.concatenate((value[:n], value[n:].sum(axis=0, keepdims=True)))
            if not np.array_equal(recombined, grouped):
                raise ValueError('separate two-ground boundaries must preserve grouped factors')
            object.__setattr__(self, key, value)


def _current_arguments(section, panels_per_edge, ground_modes, interpolation_degree):
    checked = _section(section)
    count = _integer(panels_per_edge, 'panels_per_edge', 1, 256)
    modes = _integer(ground_modes, 'ground_modes', 64, 4096)
    degree = _integer(interpolation_degree, 'interpolation_degree', 10, 16)
    if degree % 2:
        raise ValueError('interpolation_degree must be one of 10, 12, 14, 16')
    polygons = [t.corners()+[checked.width/2, 0.] for t in checked.traces]
    if sum(len(p) for p in polygons)*count > 2048:
        raise ValueError('total boundary panel count exceeds 2048')
    return checked, count, modes, degree, polygons


def two_ground_current_factors(section, *, panels_per_edge=32, ground_modes=128,
                               interpolation_degree=12):
    """Vacuum unit-current factors using an explicit two-ground shared API.

    Dielectric metadata does not enter the vacuum current solve. This is a
    homogeneous magnetic-exterior model, not anisotropic or spatially magnetic
    field extraction. Independently refine panels and finite outer dimensions.
    Existing extraction defaults stay unchanged. The pinned shared capability
    is required; an absent capability raises RuntimeError without fallback.
    """
    checked, count, modes, degree, polygons = _current_arguments(
        section, panels_per_edge, ground_modes, interpolation_degree)
    shared = _solver()(polygons, width=checked.width, height=checked.height,
                       panels_per_edge=count, ground_modes=modes, interpolation_degree=degree)
    signal = [i for i, t in enumerate(checked.traces) if not t.ground]
    grounded = [i for i, t in enumerate(checked.traces) if t.ground]
    names = tuple(checked.traces[i].name for i in signal)
    ground_names = tuple(checked.traces[i].name for i in grounded)
    cap = shared.capacitance_per_permittivity
    css = cap[np.ix_(signal, signal)]
    transform = np.linalg.solve(css.T, cap[:, signal].T).T
    all_parts = np.einsum('ai,kab,bj->kij', transform, shared.current_gram, transform)
    all_currents = shared.current_integrals @ transform
    indices = signal+[len(checked.traces), len(checked.traces)+1]+grounded
    parts = all_parts[indices]
    currents = all_currents[indices]
    n = len(names)
    grouped_parts = np.concatenate((parts[:n], parts[n:].sum(axis=0, keepdims=True)))
    grouped_currents = np.concatenate((currents[:n], currents[n:].sum(axis=0, keepdims=True)))
    potential = np.linalg.solve(cap, transform)
    ground_error = (float(np.max(abs(potential[grounded]))/np.max(abs(potential)))
                    if grounded else 0.)
    current_error = float(np.max(abs(grouped_currents-np.vstack((np.eye(n), -np.ones(n))))))
    if max(ground_error, current_error) > 1e-10:
        raise ValueError('two-ground zero-voltage or current conservation residual exceeded')
    diagnostics = {key: getattr(shared, key) for key in (
        'panel_count', 'condition_bound', 'reciprocity_error', 'residual_error',
        'current_error', 'matrix_refinement_error', 'ground_refinement_error',
        'minimum_scaled_eigenvalue')}
    diagnostics['ground_voltage_error'] = ground_error
    labels = (tuple('signal:'+s for s in names)+('reference:bottom', 'reference:top')+
              tuple('reference:ground:'+s for s in ground_names))
    return TwoGroundCurrentFactors(names, grouped_parts, grouped_currents, epsilon_0*css,
                                    ground_names, diagnostics, labels, parts, currents)


@dataclass(frozen=True)
class TwoGroundConductorLoss:
    """Frequency-dependent whole-surface loss with separate grounded foils."""
    frequency: np.ndarray
    R: np.ndarray
    L_internal: np.ndarray
    skin_depth: np.ndarray
    roughness_factor: np.ndarray
    surface_impedance: np.ndarray
    metals: tuple[SurfaceMetal, ...]
    factors: TwoGroundCurrentFactors

    def __post_init__(self):
        if not isinstance(self.factors, TwoGroundCurrentFactors):
            raise TypeError('factors must retain explicit two-ground currents')
        f = _frequencies(self.frequency)
        n, count = len(self.factors.names), len(self.factors.boundary_labels)
        metals = tuple(self.metals)
        if len(metals) != count or not all(isinstance(m, SurfaceMetal) for m in metals):
            raise ValueError('one whole-surface metal is required per ordered boundary')
        object.__setattr__(self, 'metals', metals)
        for key, shape in (
            ('frequency', f.shape), ('R', (len(f), n, n)), ('L_internal', (len(f), n, n)),
            ('skin_depth', (len(f), count)), ('roughness_factor', (len(f), count)),
            ('surface_impedance', (len(f), count)),
        ):
            value = np.asarray(getattr(self, key), dtype=complex if key == 'surface_impedance' else float)
            if value.shape != shape or not np.isfinite(value).all():
                raise ValueError(key+' must have its finite ordered shape')
            value = np.frombuffer(value.tobytes(), dtype=value.dtype).reshape(value.shape)
            object.__setattr__(self, key, value)

    @property
    def boundary_labels(self): return self.factors.boundary_labels

    @property
    def resistance_parts(self):
        return _frozen(self.surface_impedance.real[:, :, None, None]*self.factors.boundary_parts[None])

    def network(self, *, C, G, length, z_ref=50.):
        return rlgc_network(self.frequency, R=self.R, L=self.factors.L_external+self.L_internal,
                            C=C, G=G, length=length, z_ref=z_ref, names=self.factors.names)


def _loss_samples(section, frequency, conductors, reference, ground_thickness):
    checked = _section(section)
    signals = tuple(t for t in checked.traces if not t.ground)
    names = tuple(t.name for t in signals)
    if not isinstance(conductors, Mapping) or set(conductors) != set(names):
        raise ValueError('conductors must map exactly every signal name to a SurfaceMetal')
    if not all(isinstance(conductors[name], SurfaceMetal) for name in names):
        raise ValueError('every signal needs a whole-surface metal')
    if not isinstance(reference, ReferenceSurfaceMetals):
        raise TypeError('reference must be ReferenceSurfaceMetals')
    if any(not isinstance(m, SurfaceMetal) for m in reference.conductors.values()):
        raise ValueError('grounded traces require whole-surface metals')
    ref_metals, dimensions, surfaces = _reference_parts(
        checked, reference, _scalar('ground_thickness', ground_thickness))
    metals = tuple(conductors[name] for name in names)+ref_metals
    dimensions = [min(t.minimum_dimension, checked.width) for t in signals]+dimensions
    labels = tuple('signal:'+s for s in names)+tuple(s[0] for s in surfaces)
    f = _frequencies(frequency)
    samples = [m._samples(f) for m in metals]
    depth = np.column_stack([s[1] for s in samples])
    for i, dimension in enumerate(dimensions):
        remaining = _remaining_dimension(metals[i], dimension)
        if remaining <= 0 or np.max(depth[:, i]) > remaining/5:
            raise ValueError(labels[i]+': skin depth must be <= minimum remaining conductor dimension / 5')
    correction = np.column_stack([s[2] for s in samples])
    zs = np.column_stack([s[3] for s in samples])
    return checked, names, f, metals, depth, correction, zs, labels


def two_ground_conductor_loss(section, frequency, *, conductors, reference,
                               ground_thickness, panels_per_edge=32, ground_modes=128,
                               interpolation_degree=12):
    """Apply explicit signal, bottom/top foil and grounded-trace surface laws.

    ReferenceSurfaceMetals specifies both foils, no side law, and exactly the
    whole-perimeter grounded trace laws. Local coatings, roughness and remaining
    core/skin-depth restrictions are the existing surface-perturbation model.
    These laws do not resolve finite metal diffusion or coating corners.
    """
    checked, names, f, metals, depth, correction, zs, labels = _loss_samples(
        section, frequency, conductors, reference, ground_thickness)
    factors = two_ground_current_factors(checked, panels_per_edge=panels_per_edge,
        ground_modes=ground_modes, interpolation_degree=interpolation_degree)
    if factors.names != names or factors.boundary_labels != labels:
        raise ValueError('two-ground extraction changed boundary order')
    resistance = np.einsum('fb,bij->fij', zs.real, factors.boundary_parts)
    internal = np.einsum('fb,bij->fij', zs.imag/(2*np.pi*f[:, None]), factors.boundary_parts)
    return TwoGroundConductorLoss(f, resistance, internal, depth, correction, zs, metals, factors)
