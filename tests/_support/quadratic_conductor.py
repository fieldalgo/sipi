# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent test-only P2 vacuum field and facet-normal current integrals."""
import numpy as np
from scipy.sparse.linalg import splu
from crosscheck import require_tool


def quadratic_surface_factors(mesh, signals, ground):
    sk = require_tool('scikit-fem')
    from skfem.helpers import dot, grad
    from scipy.constants import epsilon_0

    m = sk.MeshTri(mesh.nodes.T.copy(), mesh.triangles.T.copy())
    element = sk.ElementTriP2()
    basis = sk.Basis(m, element)
    facets = m.boundary_facets()
    boundaries = [facets[np.isin(m.facets[:, facets], nodes).all(axis=0)]
                  for nodes in [*signals.values(), ground]]
    groups = [basis.get_dofs(facets=f).all() for f in boundaries]
    assert all(len(g) for g in groups)
    fixed = np.unique(np.concatenate(groups))
    assert sum(map(len, groups)) == len(fixed)

    @sk.BilinearForm
    def stiffness(u, v, w):
        return dot(grad(u), grad(v))

    k = stiffness.assemble(basis).tocsc()
    potentials = np.zeros((basis.N, len(signals)))
    for column, nodes in enumerate(groups[:-1]):
        potentials[nodes, column] = 1.
    free = np.setdiff1d(np.arange(basis.N), fixed)
    factor = splu(k[free][:, free].tocsc())
    potentials[free] = factor.solve(-(k[free][:, fixed] @ potentials[fixed]))
    del factor
    c0 = epsilon_0 * (potentials.T @ (k @ potentials))
    inverse = np.linalg.inv(c0)
    parts, integrals = [], []
    for boundary in boundaries:
        face = sk.FacetBasis(m, element, facets=boundary, intorder=4)
        derivatives = np.stack([
            np.einsum('dfq,dfq->fq', face.normals, face.interpolate(potentials[:, i]).grad)
            for i in range(len(signals))], axis=-1)
        currents = epsilon_0 * derivatives @ inverse
        parts.append(np.einsum('fqi,fq,fqj->ij', currents, face.dx, currents))
        integrals.append(np.einsum('fqi,fq->i', currents, face.dx))
    target = np.vstack((np.eye(len(signals)), -np.ones((1, len(signals)))))
    return dict(C0=c0, parts=np.array(parts), current_integrals=np.array(integrals),
                current_error=float(np.max(abs(np.array(integrals)-target))),
                dofs=int(basis.N))
