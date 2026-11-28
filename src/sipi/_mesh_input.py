# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Shared input-coordinate rules and error messages for SIPI's meshine calls.

meshine merges two input vertices when both coordinates differ by no more
than its merge distance, 1e-9 of the diagonal of the bounding box of every
input vertex, and then refuses a loop with a zero-length edge
(``MeshInputError``). It also stops before passing ``max_points``
(``MeshSizeLimitError``). Every SIPI path that calls ``meshine.generate``
uses these helpers so that the coordinate rule, the coordinate report and
the point-limit report read the same way. Errors keep their type and chain
the original exception; the original text comes first.
"""
from __future__ import annotations

from contextlib import contextmanager

import numpy as np
from meshine import MeshInputError, MeshSizeLimitError

__all__ = ['MERGE_EPS', 'merge_distance', 'snap', 'close_coordinates',
           'close_vertices', 'coincidence_message', 'explained']

#: meshine's dimensionless vertex merge distance (a fraction of the input diagonal).
MERGE_EPS = 1e-9

#: Close vertex pairs listed in one message before the rest are counted.
_LISTED = 5


def merge_distance(diagonal: float) -> float:
    """meshine's vertex merge distance for an input with this bounding-box diagonal."""
    return MERGE_EPS * float(diagonal)


def snap(value: float, targets, tol: float) -> float:
    """Return value, or the first target it lies strictly within tol of.

    A face strictly within the merge distance of a slab boundary leaves a slab
    thinner than that distance, which meshine always refuses; a value that
    meshes today is never moved.
    """
    for target in targets:
        if 0.0 < abs(value - target) < tol:
            return float(target)
    return value


def close_coordinates(named, tol: float) -> list[str]:
    """Pairs of distinct same-axis coordinates no more than tol apart.

    named holds (label, axis, value in m) rows; the result is one sentence
    fragment per pair, in input order.
    """
    found = []
    for i, (a, axis_a, va) in enumerate(named):
        for b, axis_b, vb in named[i + 1:]:
            if axis_a == axis_b and 0.0 < abs(va - vb) <= tol:
                found.append(f"{a} ({axis_a} = {va!r} m) and {b} ({axis_b} = {vb!r} m) "
                             f"differ by {abs(va - vb):.3g} m")
    return found


def close_vertices(named_loops, tol: float, scale: float = 1.0) -> list[str]:
    """Pairs of distinct vertices whose x and y both differ by no more than tol.

    named_loops holds (label, vertices) rows; vertices are an (n, 2) array in
    the mesher's units, and scale converts them to metres for the message.
    """
    from scipy.spatial import cKDTree
    labels, points = [], []
    for label, vertices in named_loops:
        vertices = np.asarray(vertices, dtype=float).reshape(-1, 2)
        labels += [f"{label} vertex {k}" for k in range(len(vertices))]
        points.append(vertices)
    if not points:
        return []
    p = np.concatenate(points)
    pairs = sorted(cKDTree(p).query_pairs(tol, p=np.inf))
    found = []
    for i, j in pairs:
        d = np.abs(p[i] - p[j])
        if not d.any():
            continue
        a, b = (tuple(float(v) * scale for v in p[k]) for k in (i, j))
        found.append(f"{labels[i]} ({a[0]!r}, {a[1]!r}) m and {labels[j]} ({b[0]!r}, {b[1]!r}) m "
                     f"differ by {float(d[0]) * scale:.3g} m in x and {float(d[1]) * scale:.3g} m in y")
    if len(found) > _LISTED:
        found = found[:_LISTED] + [f"{len(found) - _LISTED} more pairs"]
    return found


def coincidence_message(found, tol: float, diagonal: str, fix: str, rule: str = "") -> str:
    """The SIPI addition to a MeshInputError for coordinates closer than the merge distance."""
    if not found:
        return ""
    text = ("SIPI: " + "; ".join(found) + f". Coordinates closer than the mesher's merge "
            f"distance {tol:.3g} m (1e-9 of {diagonal}) become one point and leave a "
            f"zero-length edge. {fix}")
    return f"{text} {rule}" if rule else text


@contextmanager
def explained(coincidences=None, point_limit=None):
    """Re-raise meshine input and point-limit errors with SIPI's explanation.

    coincidences() returns the text added to a MeshInputError, or '' to leave
    the error untouched; point_limit() returns the text added to a
    MeshSizeLimitError. Both are called only on failure. The new exception has
    the same type, starts with meshine's text and is chained to it.
    """
    try:
        yield
    except MeshInputError as error:
        hint = coincidences() if coincidences is not None else ""
        if not hint:
            raise
        raise MeshInputError(f"{error} {hint}") from error
    except MeshSizeLimitError as error:
        if point_limit is None:
            raise
        raise MeshSizeLimitError(f"{error}. {point_limit()}") from error
