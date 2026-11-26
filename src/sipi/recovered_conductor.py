# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Auxiliary P1 surface currents recovered from a volume shape derivative.

The boundary integral of a product of normal derivatives is replaced by its
domain (Hadamard) form, evaluated with the same P1 potential basis and C0 as
``surface_current_factors``. This is Wheeler's incremental-inductance rule:
each conductor wall moves by a unit normal displacement. It is an auxiliary
method; the existing P1 boundary-gradient factors, the panel default and saved
documents and results are not changed.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from numbers import Real
from types import MappingProxyType

import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

from .conductor import SurfaceCurrentFactors, _surface_current_basis
from .constants import epsilon_0

__all__ = ['RecoveredCurrentFactors', 'recovered_surface_current_factors']

# Adjacent edge normals turning by more than this make a corner. Corners other
# than convex right angles (trapezoid, acute, re-entrant) have not been
# characterised and are refused.
_CORNER_DEGREES = 20.
_RIGHT_ANGLE_TOLERANCE = 1e-6
_TANGENT_TOLERANCE = 1e-9
_CHUNK = 64


@dataclass(frozen=True)
class RecoveredCurrentFactors(SurfaceCurrentFactors):
    """Vacuum current factors from the volume shape derivative, with diagnostics."""
    diagnostics: Mapping

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, 'diagnostics', MappingProxyType(dict(self.diagnostics)))


def _psi(s):
    """C1 cutoff: 1 with zero slope at s=0, 0 with zero slope at s>=1."""
    s = np.clip(s, 0.0, 1.0)
    return (1-s)**2*(1+2*s)


def _miter(n1, n2):
    if np.dot(n1, n2) > 1-1e-9:
        return n1.copy()
    return np.linalg.solve(np.array([n1, n2]), np.ones(2))


def _clearance(xy, edges):
    """Minimum node distance between distinct connected conductor boundaries."""
    nodes = np.unique(edges)
    index = {v: i for i, v in enumerate(nodes)}
    graph = sp.coo_matrix((np.ones(len(edges)), ([index[v] for v in edges[:, 0]],
                                                 [index[v] for v in edges[:, 1]])),
                          shape=(len(nodes),)*2)
    count, component = connected_components(graph, directed=False)
    if count < 2:
        raise ValueError('recovered currents need at least two separate conductor boundaries')
    points = xy[nodes]
    best = np.inf
    for c in range(count):
        distance, _ = cKDTree(points[component == c]).query(points[component != c])
        best = min(best, distance.min())
    return best


def _boundary_displacement(xy, edges, normal, width):
    """Mitred, corner-blended displacement on one group's boundary nodes."""
    flat = edges.ravel()
    order = np.argsort(flat, kind='stable')
    verts, first, degree = np.unique(flat[order], return_index=True, return_counts=True)
    if np.any(degree > 2):
        raise ValueError('recovered currents require each conductor boundary to be a simple curve')
    k1 = order[first]//2
    k2 = np.where(degree == 2, order[np.minimum(first+1, len(order)-1)]//2, k1)
    other = lambda k, v: np.where(edges[k, 0] == v, edges[k, 1], edges[k, 0])
    n1, n2 = normal[k1], normal[k2]
    dot = np.einsum('vd,vd->v', n1, n2)
    miter = n1.copy()
    bend = (degree == 2) & ~(dot > 1-1e-9)
    if np.any(bend):
        miter[bend] = np.linalg.solve(np.stack((n1[bend], n2[bend]), axis=1), np.ones((np.count_nonzero(bend), 2, 1)))[..., 0]
    is_corner = (degree == 2) & (dot < np.cos(np.radians(_CORNER_DEGREES)))
    if np.any(is_corner):
        # Normals point into the dielectric. At a convex metal corner each
        # neighbour lies on the metal side of the other edge.
        c = np.flatnonzero(is_corner)
        e1, e2 = other(k1[c], verts[c]), other(k2[c], verts[c])
        convex = ((np.einsum('vd,vd->v', xy[e1]-xy[verts[c]], n2[c]) < 0)
                  & (np.einsum('vd,vd->v', xy[e2]-xy[verts[c]], n1[c]) < 0))
        if not np.all(convex) or np.any(abs(dot[c]) > _RIGHT_ANGLE_TOLERANCE):
            raise ValueError('recovered currents admit smooth walls and convex right-angle '
                             'corners only; trapezoid, acute and re-entrant corners are unverified')
    position = {v: i for i, v in enumerate(verts.tolist())}
    corner = set(verts[is_corner].tolist())
    first_n = other(k1, verts).tolist()
    second_n = other(k2, verts).tolist()
    neighbours = {v: ([first_n[i], second_n[i]] if degree[i] == 2 else [first_n[i]])
                  for v, i in position.items()}
    pairs_v, pairs_c, radius = [], [], {}
    for c in corner:
        sides = []
        for start in neighbours[c]:
            chain, prev, cur, length = [], c, start, np.linalg.norm(xy[start]-xy[c])
            while cur not in corner and len(neighbours[cur]) == 2:
                chain.append(cur)
                nxt = neighbours[cur][0] if neighbours[cur][1] == prev else neighbours[cur][1]
                length += np.linalg.norm(xy[nxt]-xy[cur])
                prev, cur = cur, nxt
            pairs_v.extend(chain)
            pairs_c.extend([c]*len(chain))
            sides.append(length)
        radius[c] = min(width, .5*min(sides))
    theta = np.zeros_like(xy)
    theta[verts] = miter
    if pairs_v:
        # Accumulate per vertex in the order its corners were visited.
        pv, pc = np.array(pairs_v), np.array(pairs_c)
        iv = np.array([position[v] for v in pairs_v])
        ic = np.array([position[c] for c in pairs_c])
        r = np.array([radius[c] for c in pairs_c])
        weight = _psi(np.linalg.norm(xy[pv]-xy[pc], axis=1)/r)
        np.add.at(theta, pv, weight[:, None]*(miter[ic]-miter[iv]))
    return theta, len(corner)


def _nearest(x, a, ab, idx):
    """Nearest point on candidate segments idx (C,K) for points x (C,2)."""
    sa, sab = a[idx], ab[idx]
    s = np.clip(np.einsum('ckd,ckd->ck', x[:, None]-sa, sab)/np.einsum('ckd,ckd->ck', sab, sab), 0, 1)
    p = sa+s[..., None]*sab
    d = np.linalg.norm(x[:, None]-p, axis=2)
    j = np.argmin(d, axis=1)
    r = np.arange(len(x))
    return s[r, j], idx[r, j], d[r, j]


def _displacement(xy, edges, boundary, width, candidates_per_node=12):
    """Extend boundary values to mesh nodes by nearest-edge projection and cutoff.

    Candidates are the nearest edge midpoints. When those cannot prove the
    nearest edge (the farthest candidate midpoint is within half the longest
    edge of the found distance), every edge with a sample close enough to be
    nearer is checked and replaces the candidate only if strictly nearer.
    """
    segment = xy[edges]
    a, ab = segment[:, 0], segment[:, 1]-segment[:, 0]
    tree = cKDTree(segment.mean(axis=1))
    length = np.linalg.norm(ab, axis=1)
    half = .5*np.max(length)
    # Samples at most `spacing` apart on every edge: an edge within distance r
    # of a node has a sample within r+spacing/2 of it.
    spacing = float(np.median(length))
    pieces = np.ceil(length/spacing).astype(int)
    owner = np.repeat(np.arange(len(edges)), pieces)
    fraction = (np.arange(len(owner))-np.repeat(np.cumsum(pieces)-pieces, pieces)+.5)/pieces[owner]
    samples = cKDTree(a[owner]+fraction[:, None]*ab[owner])
    # Nodes at or beyond `width` from every edge have zero cutoff.
    cand = np.flatnonzero(samples.query(xy, distance_upper_bound=width+.5*spacing)[0] < np.inf)
    k = min(candidates_per_node, len(edges))
    reach, idx = tree.query(xy[cand], k=k)
    idx, reach = idx.reshape(len(cand), -1), reach.reshape(len(cand), -1)
    sj, ej, dj = _nearest(xy[cand], a, ab, idx)
    if k < len(edges):
        open_ = np.flatnonzero(reach[:, -1]-half <= dj)
        rivals = samples.query_ball_point(xy[cand[open_]], dj[open_]+.5*spacing)
        counts = np.fromiter(map(len, rivals), dtype=int, count=len(rivals))
        if counts.sum():
            row = np.repeat(np.arange(len(open_)), counts)
            edge = owner[np.concatenate(rivals).astype(int)]
            x = xy[cand[open_[row]]]
            sa, sab = a[edge], ab[edge]
            s2 = np.clip(np.einsum('cd,cd->c', x-sa, sab)/np.einsum('cd,cd->c', sab, sab), 0, 1)
            d2 = np.linalg.norm(x-(sa+s2[:, None]*sab), axis=1)
            start = np.cumsum(counts)-counts
            smallest = np.repeat(np.minimum.reduceat(d2, start), counts)
            hit = np.flatnonzero(d2 == smallest)
            first = hit[np.r_[True, row[hit][1:] != row[hit][:-1]]]
            rows = open_[row[first]]
            closer = d2[first] < dj[rows]
            take, rows = first[closer], rows[closer]
            sj[rows], ej[rows], dj[rows] = s2[take], edge[take], d2[take]
    tb = (1-sj)[:, None]*boundary[edges[ej, 0]]+sj[:, None]*boundary[edges[ej, 1]]
    theta, cutoff = np.zeros_like(xy), np.zeros(len(xy))
    cutoff[cand] = _psi(dj/width)
    theta[cand] = cutoff[cand][:, None]*tb
    return theta, cutoff


def recovered_surface_current_factors(mesh, signals, ground, *, support_fraction=0.4):
    """P1 surface-current factors from the volume form of the boundary integral.

    Accepts the same dielectric-only P1 mesh and conductor node sets as
    ``surface_current_factors`` and solves the same vacuum basis and C0. For
    each surface group (each signal, then all references) a P1 displacement
    theta has unit normal component on the group's edges (mitred at vertices,
    blended near corners), decays with the C1 cutoff (1-s)^2(1+2s) over
    ``support_fraction`` times the minimum node distance between separate
    conductor boundaries, and must be tangent to insulated walls it reaches.
    Then ``integral dnVa dnVb ds = integral grad Va.(div I-D-D^T)theta grad Vb dx``.
    Integrated currents weight the P1 flux with the same cutoff.
    Refused: fractions outside (0, 0.5), corners other than convex right
    angles, a support reaching another conductor, and a support meeting an
    insulated wall with a normal displacement component.
    """
    if (isinstance(support_fraction, (bool, np.bool_)) or not isinstance(support_fraction, Real)
            or not 0 < float(support_fraction) < .5):
        raise ValueError('support_fraction must be a real number in (0, 0.5)')
    fraction = float(support_fraction)
    sets, edges, owners, group, k, v, c0, inverse = _surface_current_basis(mesh, signals, ground)
    xy, t, count = mesh.nodes, mesh.triangles, len(signals)

    p = xy[t]
    det = ((p[:, 1, 0]-p[:, 0, 0])*(p[:, 2, 1]-p[:, 0, 1]) - (p[:, 2, 0]-p[:, 0, 0])*(p[:, 1, 1]-p[:, 0, 1]))
    if np.any(det <= 0):
        raise ValueError('surface-current mesh has nonpositive element area')
    g = np.stack((np.stack((p[:, 1, 1]-p[:, 2, 1], p[:, 2, 0]-p[:, 1, 0]), axis=1),
                  np.stack((p[:, 2, 1]-p[:, 0, 1], p[:, 0, 0]-p[:, 2, 0]), axis=1),
                  np.stack((p[:, 0, 1]-p[:, 1, 1], p[:, 1, 0]-p[:, 0, 0]), axis=1)), axis=1)
    shape_grad = g/det[:, None, None]
    area = det/2
    grad_v = np.einsum('tad,tan->tdn', shape_grad, v[t])

    def inward(edge_nodes, owner):
        tangent = xy[edge_nodes[:, 1]]-xy[edge_nodes[:, 0]]
        length = np.linalg.norm(tangent, axis=1)
        normal = np.column_stack((tangent[:, 1], -tangent[:, 0]))/length[:, None]
        third = t[owner].sum(axis=1)-edge_nodes.sum(axis=1)
        mid = xy[edge_nodes].mean(axis=1)
        normal[np.einsum('ed,ed->e', xy[third]-mid, normal) < 0] *= -1
        return normal, length

    normal, lengths = inward(edges, owners)
    all_edges = t[:, [[0, 1], [1, 2], [2, 0]]].reshape(-1, 2)
    n = np.int64(len(xy))
    key = np.min(all_edges, axis=1).astype(np.int64)*n+np.max(all_edges, axis=1)
    _, first, multiplicity = np.unique(key, return_index=True, return_counts=True)
    exterior = first[multiplicity == 1]
    metal_key = np.min(edges, axis=1).astype(np.int64)*n+np.max(edges, axis=1)
    wall = exterior[~np.isin(key[exterior], metal_key)]
    walls = all_edges[wall].reshape(-1, 2)
    wall_normal = inward(walls, wall//3)[0] if len(walls) else np.zeros((0, 2))

    clearance = _clearance(xy, edges)
    width = fraction*clearance
    reaction = k@v
    labels = np.full(len(xy), -1)
    for label, nodes in enumerate(sets):
        labels[nodes] = label
    gram, flux, support, corners = [], [], [], []
    for label in range(count+1):
        selected = group == label
        boundary, corner_count = _boundary_displacement(xy, edges[selected], normal[selected], width)
        theta, cutoff = _displacement(xy, edges[selected], boundary, width)
        if np.any(theta[(labels >= 0) & (labels != label)] != 0):
            raise ValueError('recovered-current support reaches another conductor; reduce support_fraction')
        for end in range(2):
            value = theta[walls[:, end]]
            normal_part = np.abs(np.einsum('ed,ed->e', value, wall_normal))
            if np.any(normal_part > _TANGENT_TOLERANCE*np.linalg.norm(value, axis=1)):
                raise ValueError('recovered-current support meets an insulated wall with a normal '
                                 'displacement; reduce support_fraction or enlarge the box')
        th = theta[t]
        active = np.any(th != 0, axis=(1, 2))
        G = shape_grad[active]
        D = np.einsum('tai,taj->tij', th[active], G)
        div = D[:, 0, 0]+D[:, 1, 1]
        B = div[:, None, None]*np.eye(2)-D-np.swapaxes(D, 1, 2)
        gv = grad_v[active]
        s = np.einsum('t,tin,tij,tjm->nm', area[active], gv, B, gv)
        gram.append((s+s.T)/2)
        # Consistent P1 flux: integral grad(cutoff).grad(V) = boundary flux of V.
        flux.append(cutoff@reaction)
        support.append(int(np.count_nonzero(active)))
        corners.append(corner_count)

    parts = np.array([epsilon_0**2*inverse.T@s@inverse for s in gram])
    parts = (parts+np.swapaxes(parts, 1, 2))/2
    integrals = np.array([epsilon_0*f@inverse for f in flux])
    target = np.vstack((np.eye(count), -np.ones((1, count))))
    derivative = -np.einsum('ed,edn->en', normal, grad_v[owners])
    currents = epsilon_0*derivative@inverse
    gradient_integrals = np.array([np.sum(lengths[group == label, None]*currents[group == label], axis=0)
                                   for label in range(count+1)])
    diagnostics = {
        'support_fraction': fraction,
        'support_width': float(width),
        'clearance': float(clearance),
        'support_triangles': tuple(support),
        'corners': tuple(corners),
        'gradient_current_error': float(np.max(abs(gradient_integrals-target))),
    }
    return RecoveredCurrentFactors(tuple(signals), parts, integrals, c0, diagnostics)
