"""Exact tie experiments preserve geometry and reject approximate ties."""
import importlib.util
from itertools import permutations
from pathlib import Path

import numpy as np
import pytest

spec = importlib.util.spec_from_file_location('mesh_ties',
    Path(__file__).resolve().parents[1] / 'mesh_diagnostics/ties.py')
ties = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ties)

SQUARE = np.array([[0., 0.], [1., 0.], [1., 1.], [0., 1.]])
A = np.array([[0, 1, 2], [0, 2, 3]])
B = np.array([[0, 1, 3], [1, 2, 3]])


@pytest.mark.parametrize('scale,shift', [(1., 0.), (2.**-30, 2.**-20), (2.**30, -2.**40)])
def test_same_rectangle_from_all_index_vertex_and_triangle_orders(scale, shift):
    base = SQUARE*scale+shift
    expected = base[ties.canonical_ties(base, A)[0]]
    for order in permutations(range(4)):
        order = np.array(order)
        inverse = np.argsort(order)
        for triangles in (A, B):
            for reverse in (False, True):
                t = inverse[triangles]
                if reverse:
                    t = t[::-1, ::-1]
                before_p, before_t = base[order].copy(), t.copy()
                result, _ = ties.canonical_ties(before_p, t)
                np.testing.assert_array_equal(before_p[result], expected)
                np.testing.assert_array_equal(before_p, base[order])
                np.testing.assert_array_equal(t, before_t)


def test_all_exact_radius_five_polygon_fans_have_same_result():
    points = np.array([(5, 0), (4, 3), (3, 4), (0, 5), (-3, 4), (-4, 3),
                       (-5, 0), (-4, -3), (-3, -4), (0, -5), (3, -4), (4, -3)], float)
    expected = None
    for root in range(len(points)):
        ring = list(range(root, len(points)))+list(range(root))
        triangles = np.array([[ring[0], ring[j], ring[j+1]] for j in range(1, len(points)-1)])
        for seed in range(5):
            rng = np.random.default_rng(seed)
            order = rng.permutation(len(points))
            inverse = np.argsort(order)
            t = inverse[triangles[rng.permutation(len(triangles))]]
            result, _ = ties.canonical_ties(points[order], t)
            actual = points[order][result]
            if expected is None:
                expected = actual
            np.testing.assert_array_equal(actual, expected)


def test_one_ulp_nontie_is_not_flipped_even_when_diagonal_rank_prefers_it():
    points = SQUARE.copy()
    points[2, 1] = np.nextafter(1., 2.)
    for triangles in (A, B):
        result, flips = ties.canonical_ties(points, triangles)
        assert flips == 0
        assert set(map(tuple, np.sort(result, axis=1))) == set(map(tuple, np.sort(triangles, axis=1)))
    # The non-Delaunay input remains non-Delaunay: this helper is not a repair.


def test_flip_preserves_exterior_edges_area_and_ccw_orientation():
    def boundary(t):
        e = np.sort(t[:, [[0, 1], [1, 2], [2, 0]]].reshape(-1, 2), axis=1)
        values, counts = np.unique(e, return_counts=True, axis=0)
        return values[counts == 1]
    result, flips = ties.canonical_ties(SQUARE, B)
    assert flips == 1
    np.testing.assert_array_equal(boundary(result), boundary(B))
    p = SQUARE[result]
    a, b = p[:, 1]-p[:, 0], p[:, 2]-p[:, 0]
    areas = (a[:, 0]*b[:, 1]-a[:, 1]*b[:, 0])/2
    assert np.all(areas > 0) and areas.sum() == 1
    again, more = ties.canonical_ties(SQUARE, result)
    np.testing.assert_array_equal(again, result)
    assert more == 0


@pytest.mark.parametrize('points,triangles', [
    (SQUARE, [[0., 1., 2.]]), (SQUARE, [[0, 1, 8]]), (SQUARE, [[0, 1, 1]]),
    (SQUARE, [[0, 1, 2], [2, 0, 1]]), (SQUARE, []),
    ([[0., 0.], [1., 0.], [2., 0.]], [[0, 1, 2]]),
    ([[0., 0.], [0., 0.], [1., 1.]], [[0, 1, 2]]),
    ([[0., 0.], [1., 0.], [0., float('nan')]], [[0, 1, 2]]),
    ([[0., 0.], [1., 0.], [0., 1.], [0., -1.], [1., 1.]], [[0, 1, 2], [0, 1, 3], [0, 1, 4]]),
], ids=['float-indices', 'outside', 'repeated-vertex', 'duplicate-triangle', 'empty',
        'collinear', 'duplicate-point', 'nonfinite', 'nonmanifold'])
def test_invalid_record_inputs_are_rejected(points, triangles):
    with pytest.raises(ValueError):
        ties.canonical_ties(points, triangles)
