# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Auxiliary P1 surface currents recovered from a volume shape derivative.

The boundary integral of a product of normal derivatives is replaced by its
domain (Hadamard) form, evaluated with the same P1 potential basis and C0 as
``surface_current_factors``. This is Wheeler's incremental-inductance rule:
each conductor wall recedes by a unit normal displacement. It is an auxiliary
method; the existing P1 boundary-gradient factors and saved results are not
changed.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from numbers import Real
from types import MappingProxyType

import numpy as np
from scipy.spatial import cKDTree

from .conductor import SurfaceCurrentFactors, _surface_current_basis
from .constants import epsilon_0

__all__ = ['RecoveredCurrentFactors', 'recovered_surface_current_factors']

# A turn of at most this angle between adjacent edges of one conductor is a
# discretised smooth wall; the only other admitted vertex is a convex
# right-angle metal corner. Trapezoid, acute and re-entrant corners are refused.
_SMOOTH_TURN = np.deg2rad(10.)
_RIGHT_ANGLE_TOLERANCE = 1e-6
_TANGENT_TOLERANCE = 1e-9


@dataclass(frozen=True)
class RecoveredCurrentFactors(SurfaceCurrentFactors):
    """Vacuum current factors from the volume shape derivative, with diagnostics."""
    diagnostics: Mapping

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, 'diagnostics', MappingProxyType(dict(self.diagnostics)))


def _cutoff(s):
    """C1 cutoff: 1 with zero slope at s=0, 0 with zero slope at s>=1."""
    s = np.clip(s, 0., 1.)
    return 1-s*s*(3-2*s)


def _segment_distance(points, start, end):
    """Distances and segment parameters, shape (P,E), from points to segments."""
    d = end-start
    length2 = np.einsum('ed,ed->e', d, d)
    r = points[:, None, :]-start[None, :, :]
    t = np.clip(np.einsum('ped,ed->pe', r, d)/length2, 0., 1.)
    gap = r-t[..., None]*d[None]
    return np.sqrt(np.einsum('ped,ped->pe', gap, gap)), t


def _minimum_distance(points_a, start_b, end_b, chunk=512):
    best = np.inf
    for i in range(0, len(points_a), chunk):
        best = min(best, float(np.min(_segment_distance(points_a[i:i+chunk], start_b, end_b)[0])))
    return best


def _miters(nodes, edges, normal, group, label):
    """Per-node displacement with unit normal component on every adjacent edge."""
    selected = np.flatnonzero(group == label)
    miter = {}
    incoming, outgoing = {}, {}
    for e in selected:
        a, b = edges[e]
        if b in incoming or a in outgoing:
            raise ValueError('recovered currents require each conductor boundary to be a simple curve')
        incoming[b], outgoing[a] = e, e
    for p in np.unique(edges[selected]):
        adjacent = [e for e in (incoming.get(p), outgoing.get(p)) if e is not None]
        if len(adjacent) == 1:
            miter[p] = normal[adjacent[0]]
            continue
        e1, e2 = adjacent
        n1, n2 = normal[e1], normal[e2]
        cosine = float(np.clip(n1@n2, -1., 1.))
        turn = np.arccos(cosine)
        t1 = nodes[edges[e1, 1]]-nodes[edges[e1, 0]]
        t2 = nodes[edges[e2, 1]]-nodes[edges[e2, 0]]
        convex_metal = t1[0]*t2[1]-t1[1]*t2[0] < 0
        if not (turn <= _SMOOTH_TURN or
                (convex_metal and abs(turn-np.pi/2) <= _RIGHT_ANGLE_TOLERANCE)):
            raise ValueError('recovered currents admit smooth walls and convex right-angle '
                             'corners only; trapezoid, acute and re-entrant corners are unverified')
        miter[p] = (n1+n2)/(1+cosine)
    return miter


def recovered_surface_current_factors(mesh, signals, ground, *, support_fraction=0.4):
    """P1 surface-current factors from the volume form of the boundary integral.

    Accepts the same dielectric-only P1 mesh and conductor node sets as
    ``surface_current_factors`` and solves the same vacuum basis and C0. For
    each conductor group a P1 displacement theta has unit outward normal
    component on its boundary (mitred at corners), decays with a C1 cutoff
    over ``support_fraction`` times the minimum distance between distinct
    conductors, and is tangent to insulated walls it reaches. Then
    ``integral dnVa dnVb ds = integral grad Va.(D+D^T-div)theta grad Vb dx``.
    Integrated currents use the same cutoff as a scalar weight.
    Refused: fractions outside (0, 0.5), a single conductor group, corners
    other than convex right angles or smooth turns, and a support that meets
    an insulated wall with a normal displacement component.
    """
    if (isinstance(support_fraction, (bool, np.bool_)) or not isinstance(support_fraction, Real)
            or not 0 < float(support_fraction) < .5):
        raise ValueError('support_fraction must be a real number in (0, 0.5)')
    fraction = float(support_fraction)
    sets, edges, owners, group, _, v, c0, inverse = _surface_current_basis(mesh, signals, ground)
    nodes, t, count = np.asarray(mesh.nodes, dtype=float), mesh.triangles, len(signals)

    p = nodes[t]
    determinant = ((p[:,1,0]-p[:,0,0])*(p[:,2,1]-p[:,0,1])
                   -(p[:,2,0]-p[:,0,0])*(p[:,1,1]-p[:,0,1]))
    if np.any(determinant <= 0):
        raise ValueError('surface-current mesh has nonpositive element area')
    gradients = np.stack((np.stack((p[:,1,1]-p[:,2,1],p[:,2,0]-p[:,1,0]),axis=1),
                          np.stack((p[:,2,1]-p[:,0,1],p[:,0,0]-p[:,2,0]),axis=1),
                          np.stack((p[:,0,1]-p[:,1,1],p[:,1,0]-p[:,0,0]),axis=1)),axis=1)
    gradients /= determinant[:,None,None]
    area = determinant/2
    grad_v = np.einsum('tad,tan->tdn',gradients,v[t])

    def outward(edge_nodes):
        tangent = nodes[edge_nodes[:,1]]-nodes[edge_nodes[:,0]]
        length = np.linalg.norm(tangent,axis=1)
        return np.column_stack((tangent[:,1],-tangent[:,0]))/length[:,None], length

    normal, lengths = outward(edges)
    all_edges = t[:,[[0,1],[1,2],[2,0]]].reshape(-1,2)
    _, first, multiplicity = np.unique(np.sort(all_edges,axis=1),axis=0,
                                      return_index=True,return_counts=True)
    exterior = all_edges[first[multiplicity == 1]]
    metal = {tuple(e) for e in edges}
    walls = np.array([e for e in exterior if tuple(e) not in metal], dtype=int).reshape(-1,2)
    wall_normal = outward(walls)[0] if len(walls) else np.zeros((0,2))

    labels = range(count+1)
    spacing = np.inf
    for a in labels:
        for b in labels:
            if a != b:
                target = edges[group == b]
                spacing = min(spacing, _minimum_distance(nodes[sets[a]], nodes[target[:,0]],
                                                         nodes[target[:,1]]))
    if not np.isfinite(spacing) or spacing <= 0:
        raise ValueError('recovered currents need separated signal and reference conductors')
    width = fraction*spacing

    gram, flux, support = [], [], []
    for label in labels:
        miter = _miters(nodes, edges, normal, group, label)
        own = edges[group == label]
        ids = np.array(sorted(miter))
        tree = cKDTree(nodes[ids])
        reach = width+np.max(lengths[group == label])
        near, _ = tree.query(nodes, distance_upper_bound=reach)
        candidates = np.flatnonzero(np.isfinite(near))
        theta, weight = np.zeros((len(nodes),2)), np.zeros(len(nodes))
        start, end = nodes[own[:,0]], nodes[own[:,1]]
        m0 = np.array([miter[i] for i in own[:,0]])
        m1 = np.array([miter[i] for i in own[:,1]])
        for i in range(0, len(candidates), 512):
            chunk = candidates[i:i+512]
            distance, parameter = _segment_distance(nodes[chunk], start, end)
            nearest = np.argmin(distance, axis=1)
            d = distance[np.arange(len(chunk)), nearest]
            s = parameter[np.arange(len(chunk)), nearest][:,None]
            chi = _cutoff(d/width)
            weight[chunk] = chi
            theta[chunk] = chi[:,None]*((1-s)*m0[nearest]+s*m1[nearest])
        theta[ids] = np.array([miter[i] for i in ids])
        weight[ids] = 1.
        if len(walls):
            for k in range(2):
                value = theta[walls[:,k]]
                normal_part = np.abs(np.einsum('ed,ed->e', value, wall_normal))
                if np.any(normal_part > _TANGENT_TOLERANCE*np.linalg.norm(value,axis=1)):
                    raise ValueError('recovered-current support meets an insulated wall with a normal '
                                     'displacement; reduce support_fraction or enlarge the box')
        active = np.flatnonzero(np.any(weight[t] > 0, axis=1))
        support.append(int(active.size))
        g, gv, A = gradients[active], grad_v[active], area[active]
        jacobian = np.einsum('tai,taj->tij', theta[t[active]], g)
        operator = jacobian+np.swapaxes(jacobian,1,2)
        operator -= np.trace(jacobian,axis1=1,axis2=2)[:,None,None]*np.eye(2)
        value = np.einsum('t,tia,tij,tjb->ab', A, gv, operator, gv)
        gram.append((value+value.T)/2)
        flux.append(np.einsum('t,ti,tia->a', A, np.einsum('ta,tai->ti', weight[t[active]], g), gv))

    parts = [epsilon_0**2*inverse.T@g@inverse for g in gram]
    integrals = [epsilon_0*f@inverse for f in flux]
    # Boundary-gradient flux of the same P1 basis, for under-resolution checks.
    derivative = np.einsum('ed,edn->en', normal, grad_v[owners])
    edge_currents = epsilon_0*derivative@inverse
    gradient_integrals = np.array([np.sum(lengths[group == label,None]*edge_currents[group == label],axis=0)
                                   for label in labels])
    target = np.vstack((np.eye(count), -np.ones((1,count))))
    diagnostics = {
        'support_fraction': fraction,
        'support_width': float(width),
        'minimum_spacing': float(spacing),
        'support_triangles': tuple(support),
        'gradient_current_error': float(np.max(abs(gradient_integrals-target))),
    }
    return RecoveredCurrentFactors(tuple(signals), parts, integrals, c0, diagnostics)
