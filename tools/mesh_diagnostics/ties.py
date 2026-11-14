# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Unshipped exact cocircular tie experiment for recorded triangulations.

Input must already be a valid, unconstrained triangulation. This diagnostic
neither validates the full domain nor repairs non-Delaunay triangles. Only
exact rational zero determinants of convex quadrilaterals permit a flip.
The product mesher and its legacy/stable candidate-order contracts do not
call this module. No tolerance, point location or physical gate is changed.
"""
from fractions import Fraction
from itertools import combinations
import numpy as np


def orient(a,b,c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def incircle(a,b,c,d):
    x,y,z=[[v-w for v,w in zip(p,d)] for p in (a,b,c)]
    u,v,w=[p[0]*p[0]+p[1]*p[1] for p in (x,y,z)]
    return x[0]*(y[1]*w-v*z[1])-x[1]*(y[0]*w-v*z[0])+u*(y[0]*z[1]-y[1]*z[0])


def canonical_ties(points,triangles):
    """Return canonical CCW triangles and the number of exact-tie flips.

    Rank vertices by their coordinate pairs, not input indices. Among exactly
    cocircular convex quadrilaterals prefer the lexicographically smaller
    diagonal. Every flip strictly decreases the sorted multiset of edge ranks,
    so there is no cycle. Canonicalize vertex and triangle order afterward.
    Fraction predicates use the exact input binary64 values, not decimal
    approximations or a proximity tolerance. Neither input array is mutated.
    The result is a diagnostic candidate, not a convergence certificate.
    """
    p=np.asarray(points,dtype=float);t=np.asarray(triangles)
    if p.ndim!=2 or p.shape[1]!=2 or not np.all(np.isfinite(p)):
        raise ValueError('finite planar points required')
    if t.ndim!=2 or t.shape[1]!=3 or t.dtype.kind not in 'iu' or not len(t) or t.min()<0 or t.max()>=len(p):
        raise ValueError('integer triangle indices required')
    if len(set(map(tuple,p)))!=len(p):raise ValueError('duplicate points')
    rank=np.empty(len(p),int);rank[np.lexsort((p[:,1],p[:,0]))]=np.arange(len(p))
    exact=[tuple(Fraction(float(v)) for v in row) for row in p]
    triangles={i:set(map(int,row)) for i,row in enumerate(t)}
    if len(set(map(tuple,np.sort(t,axis=1))))!=len(t):raise ValueError('duplicate triangles')
    for row in triangles.values():
        if len(row)!=3 or not orient(*(exact[i] for i in row)):raise ValueError('degenerate triangle')
    adjacent={}
    def add(i):
        for edge in combinations(sorted(triangles[i]),2):adjacent.setdefault(edge,set()).add(i)
    def remove(i):
        for edge in combinations(sorted(triangles[i]),2):
            adjacent[edge].remove(i)
            if not adjacent[edge]:del adjacent[edge]
    for i in triangles:add(i)
    if any(len(v)>2 for v in adjacent.values()):raise ValueError('nonmanifold edge')
    pending=list(adjacent);flips=0
    while pending:
        edge=pending.pop();owners=adjacent.get(edge,())
        if len(owners)!=2:continue
        i,j=sorted(owners);a,b=edge
        c=next(iter(triangles[i]-set(edge)));d=next(iter(triangles[j]-set(edge)))
        # Each accepted flip strictly decreases the multiset of ranked edges.
        if tuple(sorted((rank[c],rank[d])))>=tuple(sorted((rank[a],rank[b]))):continue
        pa,pb,pc,pd=[exact[v] for v in (a,b,c,d)]
        if incircle(pa,pb,pc,pd)!=0:continue
        if orient(pa,pb,pc)*orient(pa,pb,pd)>=0 or orient(pc,pd,pa)*orient(pc,pd,pb)>=0:continue
        alternate=tuple(sorted((c,d)))
        if alternate in adjacent:raise ValueError('alternate diagonal already exists')
        remove(i);remove(j)
        triangles[i]={c,d,a};triangles[j]={c,d,b}
        add(i);add(j);flips+=1
        pending.extend(combinations(sorted(triangles[i]),2));pending.extend(combinations(sorted(triangles[j]),2))
    ordered=[]
    for row in triangles.values():
        a,b,c=sorted(row,key=lambda i:rank[i])
        if orient(exact[a],exact[b],exact[c])<0:b,c=c,b
        ordered.append((a,b,c))
    ordered.sort(key=lambda row:tuple(rank[i] for i in row))
    return np.asarray(ordered,dtype=np.int64),flips
