# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit convex-panel PEC currents for sections with no ground plane.

All outer boundaries are open (zero normal flux); the grounded traces are the
only reference conductors, as in the unbacked coplanar templates.
"""
from importlib import import_module

import numpy as np

from .boundary_conductor import _boundary_samples, _boundary_from_factors
from .constants import epsilon_0
from .crosssection import CrossSection
from .panel_conductor import PanelCurrentFactors


__all__ = ['open_panel_surface_current_factors', 'open_panel_conductor_loss_by_boundary']


def _open_solver():
    try:
        return import_module('galerkin.laplace_open_box').solve_open_rectangle
    except (ImportError, AttributeError) as exc:
        raise RuntimeError('Open-box panel currents require the exact shared development wheel '
                           'identified in dependencies.json') from exc


def _section(section):
    if not isinstance(section, CrossSection):
        raise TypeError('section must be a CrossSection')
    checked = CrossSection(section.layers, section.traces, section.width,
                           bottom=section.bottom, top=section.top, sides=section.sides,
                           dielectric_regions=section.dielectric_regions)
    if (checked.bottom, checked.top, checked.sides) != ('open', 'open', 'open'):
        raise ValueError('open-box panel current factors require open bottom, top and sides')
    if any(t.thickness <= 0 for t in checked.traces):
        raise ValueError('open-box panel current factors require positive conductor thickness')
    return checked


def open_panel_surface_current_factors(section, *, panels_per_edge=32, interpolation_degree=12):
    """Vacuum PEC current factors with every grounded trace at zero voltage.

    The section's outer boundaries all have zero normal flux, matching the
    open boundaries of the volume mesh. The grounded traces together form the
    reference boundary. Layer permittivities and local dielectric regions do
    not enter this current solve. No volume mesh is used here.
    """
    checked = _section(section)
    polygons = [t.corners()+np.array([checked.width/2, 0.]) for t in checked.traces]
    signal = [i for i, t in enumerate(checked.traces) if not t.ground]
    grounded = [i for i, t in enumerate(checked.traces) if t.ground]
    shared = _open_solver()(polygons, width=checked.width, height=checked.height, grounds=grounded,
                            panels_per_edge=panels_per_edge, interpolation_degree=interpolation_degree)
    if tuple(shared.signal_indices) != tuple(signal) or tuple(shared.ground_indices) != tuple(grounded):
        raise ValueError('open-box panel solve changed conductor order')
    names = tuple(checked.traces[i].name for i in signal)
    parts = np.concatenate((shared.current_gram[signal], shared.current_gram[grounded].sum(axis=0, keepdims=True)))
    currents = np.vstack((shared.current_integrals[signal], shared.current_integrals[grounded].sum(axis=0)))
    diagnostics = {name: getattr(shared, name) for name in [
        'panel_count', 'condition_bound', 'reciprocity_error', 'residual_error', 'charge_sum_error',
        'current_error', 'matrix_refinement_error', 'minimum_scaled_eigenvalue',
        'smooth_interpolation_boxes']}
    factors = PanelCurrentFactors(names, parts, currents, epsilon_0*shared.capacitance_per_permittivity,
                                  tuple(checked.traces[i].name for i in grounded), diagnostics)
    if factors.current_error > 1e-10:
        raise ValueError('open-box panel current conservation residual exceeded')
    return factors


def open_panel_conductor_loss_by_boundary(section, frequency, *, conductors, reference,
                                          ground_thickness, panels_per_edge=32, interpolation_degree=12):
    """Per-boundary surface laws with open-box panel current factors.

    One metal per signal and one reference metal shared by all grounded
    traces. ground_thickness enters the same reference skin-depth gate as the
    volume route; the section has no ground plane.
    """
    checked = _section(section)
    names, f, metals, depth, correction, zs = _boundary_samples(
        checked, frequency, conductors, reference, ground_thickness)
    factors = open_panel_surface_current_factors(checked, panels_per_edge=panels_per_edge,
                                                 interpolation_degree=interpolation_degree)
    if factors.names != names:
        raise ValueError('open-box panel solve changed signal boundary order')
    return _boundary_from_factors(factors, f, metals, depth, correction, zs)
