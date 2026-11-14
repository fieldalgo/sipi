# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit weak boundary-current averages from the existing vacuum P1 solve."""
from dataclasses import dataclass

import numpy as np

from .constants import epsilon_0
from .conductor import SurfaceCurrentFactors, _surface_current_basis
from .crosssection import CrossSection
from .boundary_conductor import _boundary_samples, _boundary_from_factors

__all__ = ['DualCellCurrentFactors', 'dual_cell_surface_current_factors',
           'dual_cell_conductor_loss_by_boundary']


@dataclass(frozen=True)
class DualCellCurrentFactors(SurfaceCurrentFactors):
    """Unit-current Gram factors from nodal reactions and boundary dual lengths.

    current_error is an algebraic conservation residual. It does not estimate
    boundary-current, resistance, geometry or outer-domain error. This result
    has the same units and ordered boundary groups as SurfaceCurrentFactors.
    """


def dual_cell_surface_current_factors(mesh, signals, ground):
    """Recover explicit boundary averages without changing the vacuum field.

    Let V contain the P1 voltage bases, r=K V their weak reactions, and D_i
    half the sum of incident metal-boundary edge lengths at node i. Set
    j_i=eps0*r_i*inv(C0), the integrated unit-current reaction. Each boundary
    contributes sum_i(j_i.T*j_i/D_i) to its Gram matrix in 1/m.

    These are averages over boundary dual lengths, not interpolated normal
    derivatives or the exact squared flux. Using approximate FEM reactions
    does not provide a rigorous upper/lower resistance bound. Check mesh,
    geometry and outer-domain refinement independently, including small
    mutual entries. A small algebraic current residual is not accuracy proof.

    The original gradient API and all saved-line defaults remain unchanged.
    Boundary admission and the shared galerkin P1 solve are reused. Every
    conductor node must belong to its own exterior metal edges. The exterior
    is isotropic/nonmagnetic and electrically insulated on open boundaries.
    """
    sets, edges, _, _, stiffness, voltage, c0, inverse = _surface_current_basis(mesh, signals, ground)
    points = mesh.nodes[mesh.triangles]
    determinant = ((points[:,1,0]-points[:,0,0])*(points[:,2,1]-points[:,0,1])
                   -(points[:,2,0]-points[:,0,0])*(points[:,1,1]-points[:,0,1]))
    if np.any(determinant <= 0):
        raise ValueError('surface-current mesh has nonpositive element area')
    lengths = np.linalg.norm(mesh.nodes[edges[:,1]]-mesh.nodes[edges[:,0]], axis=1)
    weights = np.zeros(mesh.num_nodes)
    np.add.at(weights, edges[:,0], lengths/2)
    np.add.at(weights, edges[:,1], lengths/2)
    reaction = stiffness@voltage
    parts, integrated = [], []
    for nodes in sets:
        local = weights[nodes]
        if np.any(local <= 0) or not np.all(np.isfinite(local)):
            raise ValueError('dual boundary lengths must be positive and finite')
        current = epsilon_0*reaction[nodes]@inverse
        gram = current.T@(current/local[:,None])
        parts.append((gram+gram.T)/2)
        integrated.append(current.sum(axis=0))
    result = DualCellCurrentFactors(tuple(signals), parts, integrated, c0)
    if result.current_error > 1e-10:
        raise ValueError('dual-cell algebraic current conservation residual exceeded')
    return result


def dual_cell_conductor_loss_by_boundary(section, frequency, *, conductors, reference,
                                       ground_thickness, **mesh_options):
    """Apply existing per-boundary metal laws to explicit dual-cell currents.

    Reuses the original finite-core/skin-depth and surface-perturbation guards,
    including fixed layered metals. A single mesh and voltage basis is used.
    All reference surfaces share one metal. This is an opt-in reconstruction;
    it does not replace gradient or face-specific saved-line calculations.
    """
    if not isinstance(section, CrossSection):
        raise TypeError('section must be a CrossSection')
    names, f, metals, depth, correction, zs = _boundary_samples(
        section, frequency, conductors, reference, ground_thickness)
    meshed = section.mesh(**mesh_options)
    factors = dual_cell_surface_current_factors(meshed.mesh, meshed.signals, meshed.ground)
    if factors.names != names:
        raise ValueError('dual-cell solve changed signal boundary order')
    return _boundary_from_factors(factors, f, metals, depth, correction, zs)
