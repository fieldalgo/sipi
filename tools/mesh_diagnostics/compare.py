# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Classify recorded first-triangulation differences without changing a mesh.

Exact rational predicates refer to the recorded binary64 coordinates, not to an
ideal decimal geometry. This is a diagnostic, not a triangulation validator or
an impedance/convergence acceptance criterion.
"""
import argparse
from fractions import Fraction
import hashlib
from itertools import combinations
import json
from pathlib import Path

import numpy as np


def orient(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])


def incircle(a, b, c, d):
    """Exact determinant; its sign is relative to the orientation of abc."""
    x, y, z = [[v-w for v, w in zip(p, d)] for p in (a, b, c)]
    u, v, w = [p[0]*p[0]+p[1]*p[1] for p in (x, y, z)]
    return (x[0]*(y[1]*w-v*z[1]) - x[1]*(y[0]*w-v*z[0])
            + u*(y[0]*z[1]-y[1]*z[0]))


def mesh_arrays(points, triangles):
    p, t = np.asarray(points, dtype=float), np.asarray(triangles)
    if p.ndim != 2 or p.shape[1] != 2 or not np.isfinite(p).all():
        raise ValueError('expected finite planar points')
    if t.ndim != 2 or t.shape[1] != 3 or t.dtype.kind not in 'iu':
        raise ValueError('expected integer triangle indices')
    if not len(t) or t.min() < 0 or t.max() >= len(p):
        raise ValueError('triangle index out of range')
    if len({tuple(v) for v in p}) != len(p):
        raise ValueError('duplicate points')
    exact = [[Fraction(float(v)) for v in q] for q in p]
    keys = [tuple(sorted(map(int, row))) for row in t]
    if len(set(keys)) != len(keys):
        raise ValueError('duplicate triangles')
    if any(len(set(row)) != 3 or orient(*(exact[i] for i in row)) == 0 for row in keys):
        raise ValueError('degenerate triangle')
    return p, t, exact


def edges(triangles):
    result = {}
    for row in triangles:
        for a, b in combinations(map(int, row), 2):
            result.setdefault(tuple(sorted((a, b))), []).append(int(next(v for v in row if v not in (a, b))))
    if any(len(v) > 2 for v in result.values()):
        raise ValueError('nonmanifold edge')
    return result


def compare_seeds(left_points, left_triangles, right_points, right_triangles):
    p, t, exact = mesh_arrays(left_points, left_triangles)
    q, u, _ = mesh_arrays(right_points, right_triangles)
    result = dict(points_equal=np.array_equal(p, q),
                  ordered_triangles_equal=np.array_equal(t, u))
    if not result['points_equal']:
        result['connectivity_equal'] = None
        result['reason'] = 'Coordinates differ; index-based edge predicates are not comparable.'
        return result
    canonical = lambda a: {tuple(sorted(map(int, row))) for row in a}
    result['connectivity_equal'] = canonical(t) == canonical(u)
    left, right = edges(t), edges(u)
    changes = []
    for side, own, other in (('left', left, right), ('right', right, left)):
        for (a, b), opposites in sorted(own.items()):
            if (a, b) in other:
                continue
            row = dict(side=side, edge=[a, b], opposites=opposites)
            if len(opposites) == 2:
                c, d = opposites
                det = incircle(exact[a], exact[b], exact[c], exact[d])
                convex = (orient(exact[a], exact[b], exact[c])*orient(exact[a], exact[b], exact[d]) < 0
                          and orient(exact[c], exact[d], exact[a])*orient(exact[c], exact[d], exact[b]) < 0)
                row.update(incircle_sign=int(det > 0)-int(det < 0), convex=convex,
                           exact_cocircular=det == 0,
                           alternate_edge_present=tuple(sorted((c, d))) in other)
            else:
                row['boundary_edge'] = True
            changes.append(row)
    result['changed_edges'] = changes
    return result


def checked_array(values, record, *, integer=False):
    raw = np.asarray(values)
    if integer and raw.dtype.kind not in 'iu':
        raise ValueError('noninteger recorded indices')
    a = np.asarray(raw, dtype='<i8' if integer else '<f8')
    if (list(a.shape) != record['shape'] or not np.isfinite(a).all()
            or hashlib.sha256(a.tobytes()).hexdigest() != record['sha256']):
        raise ValueError('recorded array checksum/shape mismatch')
    return a


def first_triangle(record):
    if not record.get('triangle_calls') or 'first_outputs' not in record['triangle_calls'][0]:
        return None
    row = record['triangle_calls'][0]
    p = checked_array(row['first_points'], row['points'])
    t = checked_array(row['first_triangles'], row['triangles'], integer=True)
    if len(row['first_outputs']) != 4 or len(row['outputs']) != 4:
        raise ValueError('expected four triangle-data outputs')
    outputs = [checked_array(a, h) for a, h in zip(row['first_outputs'], row['outputs'])]
    if [a.shape for a in outputs] != [(len(t), 2), (len(t),), (len(t), 3), (len(t), 2)]:
        raise ValueError('invalid triangle-data output shapes')
    return p, t, outputs


def compare_records(left, right):
    seeds = []
    for record in (left, right):
        row = record['rounds'][0]
        seeds.append((checked_array(row['first_points'], row['points']),
                      checked_array(row['first_simplices'], row['simplices'], integer=True)))
    result = dict(seed=compare_seeds(*seeds[0], *seeds[1]))
    a, b = first_triangle(left), first_triangle(right)
    if a is None or b is None:
        result['first_triangle'] = dict(available=False)
    else:
        same = np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1])
        result['first_triangle'] = dict(available=True, inputs_equal=same)
        if same:
            result['first_triangle']['outputs'] = [dict(
                equal=np.array_equal(x, y), different_entries=int(np.count_nonzero(x != y)),
                max_absolute_difference=float(np.max(np.abs(x-y), initial=0)))
                for x, y in zip(a[2], b[2])]
    return result


def compare_directories(left, right):
    def read(root):
        return {p.stem: json.loads(p.read_text(encoding='utf-8')) for p in Path(root).glob('*.json')
                if p.stem not in ('environment', 'comparison', 'failure', 'completed')}
    a, b = read(left), read(right)
    if not a or a.keys() != b.keys():
        raise ValueError('trace case sets differ or are empty')
    return {name: compare_records(a[name], b[name]) for name in sorted(a)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('left', type=Path)
    parser.add_argument('right', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    report = compare_directories(args.left, args.right)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
