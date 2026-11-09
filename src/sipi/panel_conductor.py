# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit convex-panel PEC currents and per-boundary surface loss."""
from dataclasses import dataclass
from types import MappingProxyType
from collections.abc import Mapping
import numpy as np
from importlib import import_module
from inspect import signature
from .boundary_conductor import _boundary_samples, _boundary_from_factors
from .constants import epsilon_0
from .conductor import SurfaceCurrentFactors
from .crosssection import CrossSection


__all__ = ['PanelCurrentFactors', 'panel_surface_current_factors',
           'panel_conductor_loss_by_boundary']


@dataclass(frozen=True)
class PanelCurrentFactors(SurfaceCurrentFactors):
    """Vacuum current factors plus explicit grounded-trace and solve diagnostics."""
    ground_trace_names: tuple[str, ...]
    diagnostics: Mapping

    def __post_init__(self):
        super().__post_init__()
        for name in ('parts', 'current_integrals', 'C0'):
            value = getattr(self, name)
            object.__setattr__(self, name, np.frombuffer(value.tobytes(), dtype=value.dtype).reshape(value.shape))
        object.__setattr__(self, 'ground_trace_names', tuple(self.ground_trace_names))
        object.__setattr__(self, 'diagnostics', MappingProxyType(dict(self.diagnostics)))


def _panel_solver():
    try:
        solver = import_module('galerkin.laplace_boundary').solve_grounded_rectangle
    except (ImportError, AttributeError) as exc:
        raise RuntimeError('Panel currents require the exact shared development wheel identified in dependencies.json') from exc
    if 'interpolation_degree' not in signature(solver).parameters:
        raise RuntimeError('Panel currents require the shared wheel with explicit interpolation_degree support')
    return solver


def panel_surface_current_factors(section, *, panels_per_edge=32, ground_modes=512,
                                  interpolation_degree=10):
    """Vacuum PEC current factors, with bottom and explicit ground traces at zero voltage.

    Uniform longitudinal conductor currents are recovered from the vacuum dual.
    Layer permittivities and local dielectric regions do not enter this current
    solve. Match geometry before composing with independently extracted C/G.
    No volume mesh or field-gradient surface recovery is performed here.
    """
    if not isinstance(section, CrossSection):
        raise TypeError('section must be a CrossSection')
    checked = CrossSection(section.layers, section.traces, section.width,
                           bottom=section.bottom, top=section.top, sides=section.sides,
                           dielectric_regions=section.dielectric_regions)
    if (checked.bottom, checked.top, checked.sides) != ('ground', 'open', 'open'):
        raise ValueError('panel current factors require bottom ground and open top/sides')
    if any(t.thickness <= 0 for t in checked.traces):
        raise ValueError('panel current factors require positive conductor thickness')
    polygons = [t.corners()+np.array([checked.width/2, 0.]) for t in checked.traces]
    shared = _panel_solver()(polygons, width=checked.width, height=checked.height,
                                      panels_per_edge=panels_per_edge, ground_modes=ground_modes,
                                      interpolation_degree=interpolation_degree)
    signal = [i for i,t in enumerate(checked.traces) if not t.ground]
    grounded = [i for i,t in enumerate(checked.traces) if t.ground]
    names = tuple(checked.traces[i].name for i in signal)
    capacitance = shared.capacitance_per_permittivity
    css = capacitance[np.ix_(signal, signal)]
    # Zero-voltage ground traces remain in the full current basis. This
    # selects grounded potentials, not a floating-conductor Schur reduction.
    transform = np.linalg.solve(css.T, capacitance[:, signal].T).T
    parts = np.einsum('ai,kab,bj->kij', transform, shared.current_gram, transform)
    integrals = shared.current_integrals @ transform
    reference = grounded+[len(checked.traces)]
    grouped = np.concatenate((parts[signal], parts[reference].sum(axis=0,keepdims=True)))
    currents = np.vstack((integrals[signal], integrals[reference].sum(axis=0)))
    factors = SurfaceCurrentFactors(names, grouped, currents, epsilon_0*css)
    potential = np.linalg.solve(capacitance, transform)
    ground_voltage_error = (float(np.max(abs(potential[grounded]))/np.max(abs(potential)))
                            if grounded else 0.)
    if factors.current_error > 1e-10 or ground_voltage_error > 1e-10:
        raise ValueError('panel ground-voltage or current conservation residual exceeded')
    diagnostics = {name:getattr(shared,name) for name in [
        'panel_count','condition_bound','reciprocity_error','residual_error','current_error',
        'matrix_refinement_error','ground_refinement_error']}
    diagnostics['ground_voltage_error'] = ground_voltage_error
    return PanelCurrentFactors(factors.names, factors.parts, factors.current_integrals, factors.C0,
                               tuple(checked.traces[i].name for i in grounded), diagnostics)


def panel_conductor_loss_by_boundary(section, frequency, *, conductors, reference,
                                     ground_thickness, panels_per_edge=32,
                                     ground_modes=512, interpolation_degree=10):
    """Reuse per-boundary surface laws with explicit panel current factors.

    All reference surfaces share one material. Surface perturbation and each
    metal's minimum-dimension skin-depth restriction apply before field solve.
    """
    if not isinstance(section, CrossSection):
        raise TypeError('section must be a CrossSection')
    names, f, metals, depth, correction, zs = _boundary_samples(
        section, frequency, conductors, reference, ground_thickness)
    factors = panel_surface_current_factors(section, panels_per_edge=panels_per_edge,
        ground_modes=ground_modes, interpolation_degree=interpolation_degree)
    if factors.names != names:
        raise ValueError('panel solve changed signal boundary order')
    return _boundary_from_factors(factors, f, metals, depth, correction, zs)
