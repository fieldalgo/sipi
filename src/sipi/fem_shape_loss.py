# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit whole-boundary metal laws on checked FEM geometry-energy currents."""
from .crosssection import CrossSection
from .boundary_conductor import _boundary_samples, _boundary_from_factors
from .fem_shape_conductor import fem_shape_current_factors

__all__ = ['fem_shape_conductor_loss_by_boundary']


def fem_shape_conductor_loss_by_boundary(section, frequency, *, conductors,
                                         reference, ground_thickness, **mesh_options):
    """Apply one surface metal per signal and one common reference metal.

    Reuse the original finite-core, skin-depth and good-conductor admission
    before meshing. The explicit FEM geometry-energy current API checks two
    harmonic extensions and both capacitance steps. All original gradient
    flux evidence is retained, including the existing 5% flux-error rejection.
    A small flux residual does not establish resistance accuracy.

    All reference planes and finite grounds share the same material. No
    separate foil faces, dielectric calculation or full diffusion is implied.
    Check mesh, outer domain and the metal law separately. Existing current
    APIs, loss APIs and saved-line defaults are unchanged. Typed current errors
    retain their original evidence; cancellation propagates.
    """
    if not isinstance(section, CrossSection):
        raise TypeError('section must be a CrossSection')
    names, f, metals, depth, correction, zs = _boundary_samples(
        section, frequency, conductors, reference, ground_thickness)
    if not 1 <= len(names) <= 4:
        raise ValueError('FEM shape currents need 1..4 named signals')
    field = section.mesh(**mesh_options)
    factors = fem_shape_current_factors(field.mesh, field.signals, field.ground)
    if factors.names != names:
        raise ValueError('FEM shape solve changed signal boundary order')
    return _boundary_from_factors(factors, f, metals, depth, correction, zs)
