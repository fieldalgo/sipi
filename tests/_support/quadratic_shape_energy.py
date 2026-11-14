# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent test-only P2 potential with supplied geometric velocity fields."""
import numpy as np
from scipy.sparse.linalg import splu
from crosscheck import require_tool


def quadratic_shape_energy(mesh, signals, ground, velocities):
    sk = require_tool('scikit-fem')
    from skfem.helpers import dot, grad
    from scipy.constants import epsilon_0
    m = sk.MeshTri(mesh.nodes.T.copy(), mesh.triangles.T.copy())
    basis = sk.Basis(m, sk.ElementTriP2(), intorder=4)
    facets = m.boundary_facets()
    groups = [basis.get_dofs(facets=facets[np.isin(m.facets[:, facets], nodes).all(axis=0)]).all()
              for nodes in [*signals.values(), ground]]
    fixed = np.unique(np.concatenate(groups))
    assert all(map(len, groups)) and sum(map(len, groups)) == len(fixed)
    @sk.BilinearForm
    def stiffness(u, v, w): return dot(grad(u), grad(v))
    k = stiffness.assemble(basis).tocsc()
    potential = np.zeros((basis.N, len(signals)))
    for i, nodes in enumerate(groups[:-1]): potential[nodes, i] = 1.
    free = np.setdiff1d(np.arange(basis.N), fixed)
    if len(free):
        factor = splu(k[free][:, free].tocsc())
        potential[free] = factor.solve(-(k[free][:, fixed]@potential[fixed]))
        del factor
    reaction = k@potential
    c0 = epsilon_0*(potential.T@reaction)
    residual = float(np.max(abs(reaction[free]), initial=0.)/np.max(abs(reaction[fixed])))
    charge = epsilon_0*potential[fixed].T@reaction[fixed]
    energy_error = float(np.max(abs(c0-charge))/np.max(abs(c0)))
    results = []; local_errors = []
    for order in (4, 6):
        p2 = sk.Basis(m, sk.ElementTriP2(), intorder=order)
        p1 = sk.Basis(m, sk.ElementTriP1(), intorder=order)
        g = np.stack([p2.interpolate(potential[:, j]).grad for j in range(len(signals))], axis=-1).transpose(1, 2, 0, 3)
        energy = epsilon_0*np.einsum('eqdi,eq,eqdj->ij', g, p2.dx, g)
        local_errors.append(float(np.max(abs(energy-c0))/np.max(abs(c0))))
        g = g@(epsilon_0*np.linalg.inv(c0)); gg = np.einsum('eqdi,eqdj->eqij', g, g)
        rows = []
        for extension in velocities:
            parts = []
            for velocity in extension:
                dv = np.stack([p1.interpolate(velocity[:, j]).grad for j in range(2)]).transpose(2, 3, 0, 1)
                div = np.trace(dv, axis1=-2, axis2=-1)
                stretch = np.einsum('tqdi,tqdk,tqkj->tqij', g, dv+dv.swapaxes(-1, -2), g)
                parts.append(-np.einsum('eq,eqij->ij', p2.dx, div[:, :, None, None]*gg-stretch))
            rows.append(parts)
        results.append(np.array(rows))
    quad = float(np.max(abs(results[0]-results[1]))/np.max(abs(results[1])))
    assert max(residual, energy_error, *local_errors, quad) <= 1e-10
    return dict(C0=c0, parts=results[0], residual=residual, energy_error=energy_error,
                local_errors=local_errors, quadrature=quad)
