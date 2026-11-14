# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Piecewise metal conductivity: analytical limits and independent MQS forms."""
import importlib.metadata as metadata
import numpy as np
import pytest
from scipy.constants import mu_0
from scipy.special import iv, kv
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi.conductor_diffusion import conductor_impedance
from test_conductor_diffusion import A, B, C, F, SIGMA, coax_mesh, rectangular_groups


def coefficients(mesh, args):
    values = np.zeros(mesh.num_triangles)
    for indices in [*args['signals'].values(), args['ground']]:
        values[indices] = SIGMA
    return values


def edges_and_areas(mesh):
    p = mesh.nodes[mesh.triangles]
    a, b = p[:, 1]-p[:, 0], p[:, 2]-p[:, 0]
    areas = (a[:, 0]*b[:, 1]-a[:, 1]*b[:, 0])/2
    edges = np.maximum.reduce([np.linalg.norm(p[:, i]-p[:, j], axis=1)
                               for i, j in ((0, 1), (1, 2), (2, 0))])
    return edges, areas


def mixed_rectangles():
    mesh, args = rectangular_groups()
    x = mesh.nodes[mesh.triangles].mean(axis=1)[:, 0]
    values = np.zeros(mesh.num_triangles)
    left, right = args['signals'].values()
    values[left] = np.where(x[left] < .0015, 20e6, 60e6)
    values[right] = np.where(x[right] < .0045, 10e6, 30e6)
    values[args['ground']] = 10e6
    return mesh, dict(args, conductivity=values)


def mixed_coax_reference(f):
    # Separate exact diffusion solutions in two homogeneous metals; continuity
    # to the dielectric field gives the external logarithmic inductance.
    omega = 2*np.pi*np.asarray(f)
    ki = np.sqrt(1j*omega*mu_0*58e6)
    ko = np.sqrt(1j*omega*mu_0*20e6)
    inner = ki/(2*np.pi*A*58e6)*iv(0, ki*A)/iv(1, ki*A)
    outer = ko/(2*np.pi*B*20e6)*(iv(0, ko*B)*kv(1, ko*C)+iv(1, ko*C)*kv(0, ko*B))
    outer /= iv(1, ko*C)*kv(1, ko*B)-iv(1, ko*B)*kv(1, ko*C)
    return inner+outer+1j*omega*mu_0/(2*np.pi)*np.log(B/A)


def test_uniform_array_preserves_scalar_fields_and_input_snapshot():
    mesh, args = rectangular_groups()
    uniform = coefficients(mesh, args)
    before = uniform.copy()
    scalar = conductor_impedance(mesh, [0, 1e3, 1e5], **args, keep_fields=True)
    spatial = conductor_impedance(mesh, [0, 1e3, 1e5], **dict(args, conductivity=uniform), keep_fields=True)
    for name in ('Z', 'L', 'voltage_gradient', 'current_integrals', 'skin_depth',
                 'max_edge_over_skin_depth', 'vector_potential', 'current_density'):
        actual, expected = getattr(spatial, name), getattr(scalar, name)
        np.testing.assert_array_equal(np.isinf(actual), np.isinf(expected))
        finite = np.isfinite(expected)
        assert np.max(abs(actual[finite]-expected[finite]))/np.max(abs(expected[finite])) < 1e-13
    np.testing.assert_array_equal(uniform, before)
    uniform[:] = 0
    assert spatial.R[0, 0, 0] > 0 and not spatial.Z.flags.writeable


def test_piecewise_rectangles_exact_dc_current_and_energy():
    mesh, args = mixed_rectangles()
    result = conductor_impedance(mesh, [0, 1e3, 1e5], **args, keep_fields=True)
    # Each signal consists of equal-area left/right material halves.
    exact = np.diag([1/(40e6*.5e-6), 1/(20e6*.5e-6)])+np.ones((2, 2))/(10e6*2e-6)
    np.testing.assert_allclose(result.R[0], exact, rtol=1e-10, atol=0)
    _, areas = edges_and_areas(mesh)
    for g, indices in enumerate([*args['signals'].values(), args['ground']]):
        prescribed = np.eye(2)[g] if g < 2 else -np.ones(2)
        integral = np.sum(args['conductivity'][indices]*areas[indices])
        expected = args['conductivity'][indices, None]*prescribed/integral
        np.testing.assert_allclose(result.current_density[0, indices], expected, rtol=1e-10, atol=0)
    for matrices in (result.R, result.L):
        assert np.all(np.linalg.eigvalsh(matrices) > 0)
    assert max(result.current_error) < 1e-10
    assert max(result.power_error) < 1e-9
    assert max(result.magnetic_energy_error) < 1e-9
    np.testing.assert_allclose(result.Z, result.Z.swapaxes(1, 2), rtol=1e-10, atol=0)
    assert result.R[-1, 0, 0] > result.R[0, 0, 0]


def test_mixed_coax_bessel_mesh_and_outer_boundary(record_property):
    exact = mixed_coax_reference(F[1:])
    results, errors = [], []
    for nr in (16, 32, 64):
        mesh, args = coax_mesh(nr)
        values = coefficients(mesh, args)
        values[args['ground']] = 20e6
        result = conductor_impedance(mesh, F, **dict(args, conductivity=values))
        results.append(result)
        errors.append(max(np.max(abs(result.R[1:, 0, 0]/exact.real-1)),
                          np.max(abs(result.L[1:, 0, 0]/(exact.imag/(2*np.pi*F[1:]))-1)),
                          np.max(abs(result.Z[1:, 0, 0]/exact-1))))
        _, areas = edges_and_areas(mesh)
        dc = sum(1/np.sum(values[idx]*areas[idx]) for idx in [args['signals']['inner'], args['ground']])
        np.testing.assert_allclose(result.R[0, 0, 0], dc, rtol=1e-10, atol=0)
    assert errors[0] > errors[1] > errors[2] and errors[-1] < .01
    mesh, args = coax_mesh(16, outer=.006)
    values = coefficients(mesh, args)
    values[args['ground']] = 20e6
    enlarged = conductor_impedance(mesh, F, **dict(args, conductivity=values))
    outer_error = float(np.max(abs(enlarged.Z/results[0].Z-1)))
    assert outer_error < 1e-9
    record_property('mixed_coax', str(dict(errors=list(map(float, errors)), outer_error=outer_error)))


def test_independent_augmented_piecewise_conductivity_fields(record_property):
    skfem = require_tool('scikit-fem')
    from skfem.helpers import dot, grad
    from scipy.sparse import bmat, csc_matrix
    from scipy.sparse.linalg import spsolve
    mesh, args = mixed_rectangles()
    omega = 2*np.pi*1e4
    clock = Stopwatch()
    with clock('openphysics'):
        result = conductor_impedance(mesh, [1e4], **args, keep_fields=True)
    with clock('reference'):
        basis = skfem.Basis(skfem.MeshTri(mesh.nodes.T, mesh.triangles.T), skfem.ElementTriP1())
        @skfem.BilinearForm
        def stiffness(u, v, w):
            return dot(grad(u), grad(v))/mu_0
        @skfem.BilinearForm
        def mass(u, v, w):
            return w.sigma*u*v
        @skfem.LinearForm
        def load(v, w):
            return w.sigma*v
        sigma = args['conductivity']
        k = skfem.asm(stiffness, basis)
        m = skfem.asm(mass, basis, sigma=sigma[:, None])
        groups = [*args['signals'].values(), args['ground']]
        q = np.column_stack([skfem.asm(load, basis, sigma=np.where(
            np.isin(np.arange(mesh.num_triangles), group), sigma, 0)[:, None]) for group in groups])
        d = np.diag(q.sum(axis=0))
        free = np.setdiff1d(np.arange(basis.N), args['magnetic_boundary'])
        q = q[free]
        operator = bmat([[k[free][:, free]+1j*omega*m[free][:, free], csc_matrix(-q)],
                         [csc_matrix(-1j*omega*q.T), csc_matrix(d)]], format='csc')
        prescribed = np.vstack((np.eye(2), -np.ones((1, 2))))
        solved = spsolve(operator, np.vstack((np.zeros((len(free), 2)), prescribed)))
        expected_z = prescribed.T@solved[-3:]
        az = np.zeros((mesh.num_nodes, 2), complex)
        az[free] = solved[:-3]
        expected_j = np.zeros((mesh.num_triangles, 2), complex)
        for group, indices in enumerate(groups):
            expected_j[indices] = sigma[indices, None]*(solved[-3+group]-1j*omega*az[mesh.triangles[indices]].mean(axis=1))
    errors = [float(np.max(abs(actual-expected))/np.max(abs(expected))) for actual, expected in
              [(result.Z[0], expected_z), (result.current_density[0], expected_j), (result.vector_potential[0], az)]]
    assert max(errors) < 1e-9
    record_property('independent_piecewise', str(dict(z_j_az_errors=errors)))
    record = make_record(case='sipi-piecewise-metal-diffusion',
        physics='longitudinal magnetoquasistatic diffusion in piecewise conducting metal',
        api='sipi.conductor_diffusion.conductor_impedance', discretization='P1 volume fields and current Schur system',
        tool='scikit-fem', tool_discretization='independent P1 forms and augmented current-constraint solve',
        matched=['same mesh, piecewise triangle conductivity, uniform permeability, 10 kHz',
                 'two signals with material interfaces and one return, Az=0 exterior nodes',
                 'unit current columns with common negative return, exp(+j omega t)'],
        not_matched=['common-mesh agreement is not mesh or outer-boundary convergence'],
        observables=[observable(name, unit, 'normalized maximum difference', error, 1e-9)
                     for name, unit, error in zip(('Z', 'Jz', 'Az'), ('ohm/m', 'A/m^2', 'Wb/m'), errors)],
        analytical_acceptance='test_spatial_conductivity.py: piecewise DC and mixed-coax Bessel convergence',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi', version=metadata.version('sipi'))
    emit(record)


def test_resolution_uses_each_triangle_material_not_global_extrema():
    mesh, args = coax_mesh(4, 32)
    edges, _ = edges_and_areas(mesh)
    values = coefficients(mesh, args)
    metal = values > 0
    frequency = 1e4
    # Local skin depth is 1.1 times the corresponding edge; pairing the
    # largest edge with the smallest skin depth would wrongly reject this.
    values[metal] = 1/(np.pi*mu_0*frequency*(1.1*edges[metal])**2)
    result = conductor_impedance(mesh, [0, frequency], **dict(args, conductivity=values))
    assert max(edges[metal])/result.skin_depth[1] > 1
    np.testing.assert_allclose(result.max_edge_over_skin_depth, [0, 1/1.1], rtol=1e-13, atol=0)
    assert np.isinf(result.skin_depth[0])
    np.testing.assert_allclose(result.skin_depth[1], 1.1*min(edges[metal]), rtol=1e-13, atol=0)


@pytest.mark.parametrize('invalid', ['short', 'matrix', 'boolean', 'mixed_bool', 'complex', 'object',
                                    'nan', 'inf', 'negative', 'zero_metal', 'outside_metal', 'insulator', 'skin'])
def test_invalid_spatial_conductivity_rejected_before_assembly(monkeypatch, invalid):
    import sipi.conductor_diffusion as implementation
    mesh, args = coax_mesh(4, 32)
    values = coefficients(mesh, args)
    metal_index = args['signals']['inner'][0]
    if invalid == 'short': values = values[:-1]
    elif invalid == 'matrix': values = values[:, None]
    elif invalid == 'boolean': values = values > 0
    elif invalid == 'mixed_bool':
        values = list(values); values[metal_index] = True
    elif invalid == 'complex': values = values.astype(complex)
    elif invalid == 'object': values = values.astype(object)
    elif invalid in ('nan', 'inf', 'negative', 'zero_metal', 'insulator', 'skin'):
        values[metal_index] = {'nan': np.nan, 'inf': np.inf, 'negative': -1, 'zero_metal': 0,
                               'insulator': 1e-8, 'skin': 1e15}[invalid]
    elif invalid == 'outside_metal': values[np.flatnonzero(values == 0)[0]] = 1
    monkeypatch.setattr(implementation, 'assemble_load', lambda *a, **k: pytest.fail('Invalid material assembled'))
    with pytest.raises(ValueError):
        conductor_impedance(mesh, [1e4], **dict(args, conductivity=values))


def test_matched_volume_line_reuses_spatial_series_and_unchanged_dielectric():
    from test_volume_line import coax
    from sipi.dielectric import ConstantDielectric
    from sipi.volume_line import volume_line
    volume, _ = coax(8, 64)
    f = [0, 1e4]
    values = coefficients(volume.mesh, dict(signals=volume.signals, ground=volume.ground))
    values[volume.ground] = 20e6
    material = {'dielectric': ConstantDielectric(4, .02)}
    spatial = volume_line(volume, f, materials=material, conductivity=values, length=.1)
    scalar = volume_line(volume, f, materials=material, conductivity=SIGMA, length=.1)
    direct = volume.impedance(f, conductivity=values)
    np.testing.assert_array_equal(spatial.R, direct.R)
    np.testing.assert_array_equal(spatial.L, direct.L)
    np.testing.assert_array_equal(spatial.C_complex, scalar.C_complex)
    assert np.all(spatial.R[:, 0, 0] > scalar.R[:, 0, 0])
    assert np.max(np.linalg.svd(spatial.network.s, compute_uv=False)) <= 1+1e-10
    np.testing.assert_allclose(spatial.network.s, spatial.network.s.swapaxes(1, 2), atol=1e-10)


def test_saved_volume_v1_still_rejects_mesh_indexed_materials():
    from test_volume_line import document
    from sipi.volume_line import VolumeLineDocument
    saved = document().to_dict()
    saved['conductor']['conductivity'] = [58e6, 20e6]
    with pytest.raises(ValueError, match='scalar'):
        VolumeLineDocument.from_dict(saved)
