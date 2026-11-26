# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Recovered (volume shape-derivative) P1 currents: exact limits and refusals.

Criteria were fixed before the runs: plate factors exact to 1e-10; coax
observed order >= 1.8 for each surface over three refinements and finest
relative error < 1e-3; the same P1 basis and C0 as surface_current_factors.
PCB sections and the preregistered panel comparison are in
test_recovered_conductor_sections.py.
"""
import numpy as np
import pytest
from galerkin import annulus_mesh, rectangle_mesh
from sipi import microstrip
from sipi.conductor import surface_current_factors
from sipi.recovered_conductor import recovered_surface_current_factors


def test_parallel_plate_exact_and_same_basis():
    width, height = .002, .001
    mesh = rectangle_mesh(width, height, 8, 4)
    args = (mesh, {'signal': mesh.boundary['top']}, mesh.boundary['bottom'])
    result = recovered_surface_current_factors(*args)
    np.testing.assert_allclose(result.parts[:,0,0], [1/width, 1/width], rtol=1e-10)
    np.testing.assert_allclose(result.current_integrals, [[1],[-1]], atol=1e-10, rtol=0)
    assert result.current_error < 1e-10
    np.testing.assert_array_equal(result.C0, surface_current_factors(*args).C0)
    assert result.diagnostics['clearance'] == pytest.approx(height, rel=1e-12)
    assert result.diagnostics['corners'] == (0, 0)
    assert result.diagnostics['support_width'] == pytest.approx(.4*height, rel=1e-12)
    assert result.diagnostics['gradient_current_error'] < 1e-10
    assert not result.parts.flags.writeable
    with pytest.raises(TypeError):
        result.diagnostics['support_width'] = 0


def test_coax_converges_at_second_order_on_each_surface():
    a, b = .5e-3, 2e-3
    exact = np.array([1/(2*np.pi*a), 1/(2*np.pi*b)])
    errors = []
    for nr, nt in ((16, 64), (32, 128), (64, 256)):
        mesh = annulus_mesh(a, b, nr, nt)
        result = recovered_surface_current_factors(mesh, {'inner': mesh.boundary['inner']},
                                                   mesh.boundary['outer'])
        errors.append(abs(result.parts[:,0,0]/exact-1))
        assert result.current_error < 1e-10
    errors = np.array(errors)
    order = np.log2(errors[:-1]/errors[1:])
    assert np.all(order >= 1.8), order
    assert np.max(errors[-1]) < 1e-3, errors[-1]


@pytest.mark.parametrize('fraction', [0, .5, -.1, True, np.nan, '0.4'],
                         ids=['zero', 'half', 'negative', 'bool', 'nan', 'string'])
def test_support_fraction_outside_range_rejected(fraction):
    mesh = rectangle_mesh(.002, .001, 8, 4)
    with pytest.raises(ValueError, match='support_fraction'):
        recovered_surface_current_factors(mesh, {'s': mesh.boundary['top']},
                                          mesh.boundary['bottom'], support_fraction=fraction)


def test_unverified_corners_rejected():
    mesh = annulus_mesh(.5e-3, 2e-3, 8, 16)  # 22.5 degree turns: corners, not right angles
    with pytest.raises(ValueError, match='corners'):
        recovered_surface_current_factors(mesh, {'inner': mesh.boundary['inner']},
                                          mesh.boundary['outer'])
    section = microstrip(width=.3e-3, top_width=.25e-3, substrate_height=.2e-3, eps_r=4,
                         thickness=35e-6)
    meshed = section.mesh()
    with pytest.raises(ValueError, match='trapezoid'):
        recovered_surface_current_factors(meshed.mesh, meshed.signals, meshed.ground)


def test_support_with_normal_displacement_on_insulated_wall_rejected():
    mesh = rectangle_mesh(.002, .001, 8, 4)
    top = mesh.boundary['top']
    x = mesh.nodes[top, 0]
    with pytest.raises(ValueError, match='insulated wall'):
        recovered_surface_current_factors(mesh, {'s': top[x <= .001]}, mesh.boundary['bottom'])
