# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent affine integrals and analytic plates for P1 energy extraction."""
import numpy as np
import pytest
from galerkin import Mesh, rectangle_mesh
from sipi import capacitance_matrix
from sipi.constants import epsilon_0
from sipi.quasistatic import _capacitance_energy


@pytest.mark.parametrize('kind', ['scalar', 'cells', 'tensor', 'tensor_cells'])
@pytest.mark.parametrize('complex_fields', [False, True])
def test_affine_integral_and_triangle_permutation(kind, complex_fields):
    width, height = .013, .002
    mesh = rectangle_mesh(width, height, 12, 8)
    gradient = np.array([[1/width, .3/width, -.4/width],
                         [.25/height, -1/height, .8/height]])
    if complex_fields:
        gradient = gradient * np.array([1, .8+.2j, 1+.1j])
    potentials = mesh.nodes @ gradient + np.array([.2, .7, .1])
    left = mesh.nodes[mesh.triangles].mean(axis=1)[:, 0] < width/2
    if kind in ('scalar', 'cells'):
        a, b = 4*(1-.03j), 2*(1-.07j)
        eps = a if kind == 'scalar' else np.where(left, a, b)
        mean = (a if kind == 'scalar' else (a+b)/2) * np.eye(2)
    else:
        a = np.array([[3, .4], [.4, 5]]) - 1j*np.array([[.03, .01], [.01, .05]])
        b = np.array([[4, -.2], [-.2, 2]]) - 1j*np.diag([.06, .02])
        eps = (np.broadcast_to(a, (mesh.num_triangles, 2, 2)) if kind == 'tensor'
               else np.where(left[:, None, None], a, b))
        mean = a if kind == 'tensor' else (a+b)/2
    # The two material regions each occupy exactly half the rectangle.
    expected = epsilon_0*width*height*(gradient.T @ mean @ gradient)
    original = potentials.copy()
    actual = _capacitance_energy(mesh, eps, potentials)
    np.testing.assert_allclose(actual, expected, rtol=1e-13, atol=0)
    np.testing.assert_array_equal(actual, actual.T)
    np.testing.assert_array_equal(potentials, original)
    if complex_fields:
        hermitian = epsilon_0*width*height*(gradient.conj().T @ mean @ gradient)
        assert np.max(abs(actual-hermitian)) > .01*np.max(abs(expected))
    order = np.random.default_rng(71).permutation(mesh.num_triangles)
    reordered = Mesh(mesh.nodes.copy(), mesh.triangles[order], mesh.boundary)
    coefficient = eps if np.ndim(eps) == 0 else eps[order]
    np.testing.assert_array_equal(_capacitance_energy(reordered, coefficient, potentials), actual)


@pytest.mark.parametrize('height', [.002, .00001, .000001])
@pytest.mark.parametrize('loss', [0., .03])
def test_parallel_plate_charge_from_the_analytic_linear_field(height, loss):
    width = .01
    mesh = rectangle_mesh(width, height, 32, 8)
    eps = 4*(1-1j*loss)
    actual = capacitance_matrix(mesh, eps, {'top': mesh.boundary['top']},
                                mesh.boundary['bottom'])[0, 0]
    expected = epsilon_0*width*eps/height
    assert actual == pytest.approx(expected, rel=1e-10, abs=0)
