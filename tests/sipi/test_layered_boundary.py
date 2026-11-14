# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Layered local surface laws, finite-core gates and independent field limits."""
import numpy as np
import pytest
from scipy.integrate import solve_ivp
from scipy.special import ive
from galerkin import rectangle_mesh

from sipi import CrossSection, MetalLayer, layered_surface_impedance, microstrip
from sipi.boundary_conductor import (SurfaceMetal, LayeredSurfaceMetal,
    _boundary_from_factors, surface_conductor_loss_by_boundary)
from sipi.face_conductor import TraceFaceMetals, ReferenceSurfaceMetals, surface_conductor_loss_by_face
from sipi.conductor import surface_current_factors
from sipi.constants import mu_0
from sipi.roughness import CausalHuray
from test_layered_metal import transfer, LAYERS, SIGMA

F = np.array([1e9, 4e9, 1e10])
COARSE = dict(edge_size=5e-6, far_size=.2e-3, grade=.1)
FINE = dict(edge_size=2.5e-6, far_size=.1e-3, grade=.05)


def metal(): return LayeredSurfaceMetal(SIGMA, coatings=LAYERS)


def test_plate_power_matches_independent_layer_transfer():
    width = .002
    mesh = rectangle_mesh(width, .001, 8, 4)
    factors = surface_current_factors(mesh, {'s': mesh.boundary['top']}, mesh.boundary['bottom'])
    metals = (metal(), SurfaceMetal(SIGMA))
    samples = [m._samples(F) for m in metals]
    result = _boundary_from_factors(factors, F, metals, *[np.column_stack([s[i] for s in samples]) for i in (1, 2, 3)])
    zs = np.array([transfer(f)+np.sqrt(2j*np.pi*f*mu_0/SIGMA) for f in F])
    expected = zs/width
    np.testing.assert_allclose(result.R[:, 0, 0]+2j*np.pi*F*result.L_internal[:, 0, 0], expected, rtol=1e-10)
    np.testing.assert_allclose(result.resistance_parts.sum(axis=1), result.R, rtol=1e-12)
    np.testing.assert_array_equal(result.roughness_factor, 1)


def cylindrical_surface(radius, frequency):
    omega = 2*np.pi*frequency
    scale = np.sqrt(omega*mu_0/(2*SIGMA))
    core = radius-sum(x.thickness_m for x in LAYERS)
    k = np.sqrt(1j*omega*mu_0*SIGMA)
    z = (1+1j)*scale*ive(0, k*core)/ive(1, k*core)
    inner = core
    for layer in reversed(LAYERS):
        mu, sigma = mu_0*layer.relative_permeability, layer.conductivity
        delta = np.sqrt(2/(omega*mu*sigma))
        def equation(u, y):
            r = inner+u*delta
            return delta*(1j*omega*mu/scale-sigma*scale*y*y+y/r)
        solution = solve_ivp(equation, (0., layer.thickness_m/delta), [z/scale],
                             method='DOP853', rtol=2e-11, atol=2e-12)
        assert solution.success
        z = solution.y[0, -1]*scale
        inner += layer.thickness_m
    return z


def test_independent_cylindrical_diffusion_approaches_planar_limit(record_property):
    plane = layered_surface_impedance([1e9], conductivity=SIGMA, layers=LAYERS).impedance[0]
    errors = [float(abs(cylindrical_surface(r, 1e9)/plane-1)) for r in (.1e-3, .2e-3, .4e-3)]
    for i, value in enumerate(errors): record_property(f'curvature_error_{i}', value)
    assert errors[2] < errors[1] < errors[0]
    assert errors[2] < .01


def section(**kwargs):
    return microstrip(width=.5e-3, substrate_height=1e-3, thickness=50e-6, eps_r=4., **kwargs)


def boundary(s, material, **options):
    return surface_conductor_loss_by_boundary(s, F, conductors={s.traces[0].name: material},
        reference=SurfaceMetal(SIGMA), ground_thickness=35e-6, **options)


@pytest.fixture(scope='module')
def line():
    s = section()
    coarse = boundary(s, metal(), **COARSE)
    fine = boundary(s, metal(), **FINE)
    wider = boundary(section(box_width=s.width*2), metal(), **FINE)
    return s, coarse, fine, wider


def test_mesh_outer_convergence_and_finite_network(line, record_property):
    s, coarse, fine, wider = line
    for key in ('R', 'L_internal'):
        a, b, c = (getattr(x, key) for x in (coarse, fine, wider))
        mesh = float(np.max(abs(a-b))/np.max(abs(b)))
        outer = float(np.max(abs(b-c))/np.max(abs(c)))
        record_property(key+'_mesh', mesh); record_property(key+'_outer', outer)
        assert mesh < .05 and outer < .05
        assert np.linalg.eigvalsh(b).min() >= 0
    dielectric = s.analyze(**FINE)
    network = fine.network(C=dielectric.C, G=np.zeros((1, 1)), length=.03)
    assert np.max(np.linalg.svd(network.s, compute_uv=False)) <= 1+1e-10
    np.testing.assert_allclose(network.s, network.s.swapaxes(1, 2), rtol=0, atol=1e-10)


def test_empty_and_zero_coatings_preserve_original_boundary_arrays():
    s = section(box_width=6e-3, air_height=3e-3)
    original = boundary(s, SurfaceMetal(SIGMA), **COARSE)
    for material in (LayeredSurfaceMetal(SIGMA), LayeredSurfaceMetal(SIGMA, coatings=[MetalLayer(0, 1e6)])):
        result = boundary(s, material, **COARSE)
        for key in ('R', 'L_internal', 'skin_depth', 'surface_impedance', 'roughness_factor'):
            np.testing.assert_array_equal(getattr(result, key), getattr(original, key))


def test_face_and_reference_paths_reuse_finished_geometry():
    s = section(box_width=6e-3, air_height=3e-3); name = s.traces[0].name
    material = metal()
    common = dict(ground_thickness=35e-6, **COARSE)
    whole = surface_conductor_loss_by_boundary(s, F, conductors={name: material}, reference=material, **common)
    faces = surface_conductor_loss_by_face(s, F, conductors={name: TraceFaceMetals.uniform(material)},
        reference=ReferenceSurfaceMetals(bottom=material, top=None, sides=None, conductors={}), **common)
    np.testing.assert_allclose(faces.R, whole.R, rtol=1e-12)
    np.testing.assert_allclose(faces.L_internal, whole.L_internal, rtol=1e-12)
    np.testing.assert_array_equal(faces.factors.C0, whole.factors.C0)


@pytest.mark.parametrize('where', ['signal', 'reference', 'face', 'reference-face'])
@pytest.mark.parametrize('thickness', [30e-6, 24.9e-6])
def test_core_and_skin_gates_precede_meshing(monkeypatch, where, thickness):
    s = section(); name = s.traces[0].name
    coated = LayeredSurfaceMetal(SIGMA, coatings=[MetalLayer(thickness, 14e6)])
    smooth = SurfaceMetal(SIGMA)
    monkeypatch.setattr(CrossSection, 'mesh', lambda *a, **k: pytest.fail('invalid coating reached mesh'))
    if where in ('face', 'reference-face'):
        conductors = {name: TraceFaceMetals.uniform(coated if where == 'face' else smooth)}
        reference = ReferenceSurfaceMetals(bottom=coated if where == 'reference-face' else smooth,
                                           top=None, sides=None, conductors={})
        function = surface_conductor_loss_by_face
    else:
        conductors = {name: coated if where == 'signal' else smooth}
        reference = coated if where == 'reference' else smooth
        function = surface_conductor_loss_by_boundary
    with pytest.raises(ValueError, match='skin depth'):
        function(s, F, conductors=conductors, reference=reference, ground_thickness=35e-6)


@pytest.mark.parametrize('kwargs', [dict(roughness_rms=1e-9), dict(roughness=CausalHuray([1e-6], [1.])),
    dict(coatings=None), dict(coatings=[{}]), dict(coatings=list(LAYERS)*17),
    dict(coatings=[MetalLayer(1e308, SIGMA)]*2)])
def test_ambiguous_or_invalid_layer_material_rejected(kwargs):
    with pytest.raises(ValueError): LayeredSurfaceMetal(SIGMA, **kwargs)


def test_layer_tuple_copied_and_penetration_scale_includes_active_materials_only():
    values = list(LAYERS); model = LayeredSurfaceMetal(SIGMA, coatings=values); values.clear()
    assert model.coatings == LAYERS
    raw = layered_surface_impedance(F, conductivity=SIGMA, layers=LAYERS)
    np.testing.assert_array_equal(model._samples(F)[1], np.max(raw.skin_depth, axis=1))
    assert model.coating_thickness == sum(x.thickness_m for x in LAYERS)


def test_explicit_ground_trace_face_coatings_preserve_partition():
    from test_ground_faces import boxed_pair
    s = boxed_pair(); smooth = SurfaceMetal(SIGMA); coated = metal()
    signals = {t.name: TraceFaceMetals.uniform(smooth) for t in s.traces if not t.ground}
    reference = ReferenceSurfaceMetals(smooth, smooth, smooth,
        {'guardL': TraceFaceMetals.uniform(coated), 'guardR': coated})
    faces = surface_conductor_loss_by_face(s, F, conductors=signals, reference=reference,
                                          ground_thickness=35e-6, **COARSE)
    whole = surface_conductor_loss_by_face(s, F, conductors=signals,
        reference=ReferenceSurfaceMetals(smooth, smooth, smooth, {'guardL': coated, 'guardR': coated}),
        ground_thickness=35e-6, **COARSE)
    np.testing.assert_allclose(faces.R, whole.R, rtol=1e-12)
    np.testing.assert_allclose(faces.L_internal, whole.L_internal, rtol=1e-12)
    np.testing.assert_array_equal(faces.factors.C0, whole.factors.C0)
    expected = np.array([transfer(f) for f in F])
    for index, label in enumerate(faces.factors.labels):
        if label.startswith('reference:ground:'):
            np.testing.assert_allclose(faces.surface_impedance[:, index], expected, rtol=1e-10)


@pytest.mark.parametrize('face', ['bottom', 'top', 'left', 'right'])
def test_explicit_ground_trace_coating_gate_precedes_mesh(monkeypatch, face):
    from test_ground_faces import boxed_pair
    s = boxed_pair(); smooth = SurfaceMetal(SIGMA)
    fields = {name: smooth for name in ('bottom', 'top', 'left', 'right')}
    fields[face] = LayeredSurfaceMetal(SIGMA, coatings=[MetalLayer(24.9e-6, 14e6)])
    reference = ReferenceSurfaceMetals(smooth, smooth, smooth,
        {'guardL': TraceFaceMetals(**fields), 'guardR': smooth})
    monkeypatch.setattr(CrossSection, 'mesh', lambda *a, **k: pytest.fail('ground coating reached mesh'))
    with pytest.raises(ValueError, match='skin depth'):
        surface_conductor_loss_by_face(s, F,
            conductors={t.name: TraceFaceMetals.uniform(smooth) for t in s.traces if not t.ground},
            reference=reference, ground_thickness=35e-6)
