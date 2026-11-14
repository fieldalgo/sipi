# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Piecewise linear permeability: independent fields and cylindrical limits."""
import importlib.metadata as metadata
import numpy as np
import pytest
from scipy.constants import mu_0
from scipy.special import iv, kv
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi.conductor_diffusion import conductor_impedance
from test_conductor_diffusion import A, B, C, coax_mesh, rectangular_groups
from test_spatial_conductivity import coefficients, edges_and_areas, mixed_rectangles

F = np.array([0, 100, 1e4, 1e5])


def magnetic_coax(nr=16, outer=.003):
    mesh, args = coax_mesh(nr, outer=outer)
    sigma = coefficients(mesh, args)
    sigma[args['ground']] = 20e6
    mu = np.ones(mesh.num_triangles)
    for region, value in enumerate((2., 3., 5., 1.)):
        mu[mesh.regions == region] = value
    return mesh, dict(args, conductivity=sigma, relative_permeability=mu)


def coax_reference(f):
    omega = 2*np.pi*np.asarray(f)
    ki = np.sqrt(1j*omega*mu_0*2*58e6)
    ko = np.sqrt(1j*omega*mu_0*5*20e6)
    inner = ki/(2*np.pi*A*58e6)*iv(0, ki*A)/iv(1, ki*A)
    outer = ko/(2*np.pi*B*20e6)*(iv(0, ko*B)*kv(1, ko*C)+iv(1, ko*C)*kv(0, ko*B))
    outer /= iv(1, ko*C)*kv(1, ko*B)-iv(1, ko*B)*kv(1, ko*C)
    return inner+outer+1j*omega*mu_0*3/(2*np.pi)*np.log(B/A)


def test_magnetic_coax_bessel_dc_and_domain_convergence(record_property):
    # Independently integrate mu*H_phi**2 over the solid centre, dielectric,
    # and finite return tube with uniform DC currents. Exterior net I is zero.
    dc_l = mu_0*2/(8*np.pi)+mu_0*3/(2*np.pi)*np.log(B/A)
    dc_l += mu_0*5/(2*np.pi*(C*C-B*B)**2)*(C**4*np.log(C/B)-C*C*(C*C-B*B)+(C**4-B**4)/4)
    exact = coax_reference(F[1:])
    results, errors, dc_errors = [], [], []
    for nr in (16, 32, 64):
        mesh, args = magnetic_coax(nr)
        result = conductor_impedance(mesh, F, **args)
        results.append(result)
        errors.append(float(max(np.max(abs(result.R[1:, 0, 0]/exact.real-1)),
            np.max(abs(result.L[1:, 0, 0]/(exact.imag/(2*np.pi*F[1:]))-1)),
            np.max(abs(result.Z[1:, 0, 0]/exact-1)))))
        dc_errors.append(float(abs(result.L[0, 0, 0]/dc_l-1)))
        _, areas = edges_and_areas(mesh)
        dc_r = sum(1/np.sum(args['conductivity'][ids]*areas[ids])
                   for ids in [args['signals']['inner'], args['ground']])
        assert result.R[0, 0, 0] == pytest.approx(dc_r, rel=1e-10)
    mesh, args = magnetic_coax(16, outer=.006)
    enlarged = conductor_impedance(mesh, F, **args)
    outer_error = float(np.max(abs(enlarged.Z/results[0].Z-1)))
    record_property('magnetic_coax', str(dict(ac_errors=errors, dc_l_errors=dc_errors, outer_error=outer_error)))
    assert errors[0] > errors[1] > errors[2] and errors[-1] < .01
    assert dc_errors[-1] < .001
    assert outer_error < 1e-9


def test_uniform_permeability_array_preserves_scalar_values_and_input():
    mesh, args = rectangular_groups()
    mu = np.full(mesh.num_triangles, 2.)
    before = mu.copy()
    scalar = conductor_impedance(mesh, [0, 1e3, 1e4], **args, relative_permeability=2., keep_fields=True)
    spatial = conductor_impedance(mesh, [0, 1e3, 1e4], **args, relative_permeability=mu, keep_fields=True)
    for name in ('Z', 'L', 'voltage_gradient', 'current_integrals', 'skin_depth',
                 'max_edge_over_skin_depth', 'vector_potential', 'current_density'):
        actual, expected = getattr(spatial, name), getattr(scalar, name)
        np.testing.assert_array_equal(np.isinf(actual), np.isinf(expected))
        finite = np.isfinite(expected)
        assert np.max(abs(actual[finite]-expected[finite]))/np.max(abs(expected[finite])) < 1e-13
    np.testing.assert_array_equal(mu, before)
    mu[:] = 0
    assert spatial.L[0, 0, 0] > 0 and not spatial.L.flags.writeable


def test_local_skin_uses_colocated_mu_sigma_not_independent_maxima():
    mesh, args = mixed_rectangles()
    sigma = args['conductivity']
    metal = sigma > 0
    lengths, _ = edges_and_areas(mesh)
    mu = np.ones(mesh.num_triangles)
    mu[metal] = 60e6/sigma[metal]
    f = .9**2/(np.pi*mu_0*60e6*max(lengths[metal])**2)
    result = conductor_impedance(mesh, [0, f], **args, relative_permeability=mu)
    assert result.max_edge_over_skin_depth[-1] == pytest.approx(.9, rel=1e-12)
    assert result.skin_depth[-1] == pytest.approx(max(lengths[metal])/.9, rel=1e-12)
    # A product of separate maxima would reject this valid-resolution case.
    assert max(lengths[metal])*np.sqrt(np.pi*f*mu_0*max(mu[metal])*max(sigma[metal])) > 1
    with pytest.raises(ValueError, match='skin depth'):
        conductor_impedance(mesh, [f*(1.01/.9)**2], **args, relative_permeability=mu)


def test_dc_magnetic_energy_increases_without_changing_resistance():
    mesh, args = rectangular_groups()
    mu = np.ones(mesh.num_triangles)
    ordinary = conductor_impedance(mesh, [0], **args)
    mu[args['signals']['left']] = 4.
    magnetic = conductor_impedance(mesh, [0], **args, relative_permeability=mu)
    np.testing.assert_array_equal(magnetic.R, ordinary.R)
    assert np.linalg.eigvalsh(magnetic.L[0]-ordinary.L[0]).min() > 0
    assert max(magnetic.magnetic_energy_error) < 1e-9


def test_volume_line_changes_magnetic_field_without_changing_cg():
    from sipi.dielectric import ConstantDielectric
    from sipi.volume_line import volume_line
    from test_metal_cores import volume, section, conductivity
    v = volume()
    mu = np.ones(v.mesh.num_triangles)
    mu[v.signals['signal']] = 5.
    mu[v.core_triangles['signal']] = 2.
    args = dict(materials={l.name: ConstantDielectric(l.eps_r, l.tan_delta)
                          for l in section().layers}, conductivity=conductivity(v), length=.1)
    ordinary = volume_line(v, [0, 1e4], **args)
    magnetic = volume_line(v, [0, 1e4], **args, relative_permeability=mu)
    np.testing.assert_array_equal(magnetic.C, ordinary.C)
    np.testing.assert_array_equal(magnetic.G, ordinary.G)
    np.testing.assert_array_equal(magnetic.R[0], ordinary.R[0])
    assert np.all(magnetic.L > ordinary.L)
    assert np.max(np.linalg.svd(magnetic.network.s, compute_uv=False)) <= 1+1e-10


def test_existing_volume_json_rejects_permeability_arrays():
    from sipi.volume_line import VolumeLineDocument
    from test_core_document import document
    data = document().to_dict()
    for schema in (1, 2, 3):
        candidate = dict(data, schema=f'sipi.volume-line/{schema}',
            conductor=dict(data['conductor'], relative_permeability=[1., 2.]))
        if schema != 3: candidate.pop('metal_cores')
        if schema == 1: candidate['conductor']['conductivity'] = 58e6
        with pytest.raises(ValueError): VolumeLineDocument.from_dict(candidate)


@pytest.mark.parametrize('bad', [0, -1, True, float('nan'), float('inf'), 1+1j,
    [], [1.], [[1., 2.]], [1., False]], ids=['zero', 'negative', 'bool', 'nan', 'inf',
    'complex', 'empty', 'short', 'matrix', 'mixed-bool'])
def test_invalid_permeability_rejected_before_assembly(monkeypatch, bad):
    import sipi.conductor_diffusion as implementation
    mesh, args = rectangular_groups()
    monkeypatch.setattr(implementation, 'assemble_load', lambda *a, **k: pytest.fail('Invalid mu assembled'))
    with pytest.raises(ValueError): conductor_impedance(mesh, [0], **args, relative_permeability=bad)


@pytest.mark.parametrize('value', [0., -1., float('nan'), float('inf')])
def test_invalid_nonmetal_permeability_is_not_ignored(value):
    mesh, args = magnetic_coax(4)
    mu = args['relative_permeability']
    mu[mesh.regions == 3] = value
    with pytest.raises(ValueError): conductor_impedance(mesh, [0], **args)


def test_independent_piecewise_magnetic_augmented_fields(record_property):
    sk = require_tool('scikit-fem')
    from skfem.helpers import dot, grad
    from scipy.sparse import bmat, csc_matrix
    from scipy.sparse.linalg import spsolve
    mesh, args = mixed_rectangles()
    x, y = mesh.nodes[mesh.triangles].mean(axis=1).T
    mu = np.where(x < .003, 2., 5.)
    sigma = args['conductivity']
    omega = 2*np.pi*1e4
    clock = Stopwatch()
    with clock('openphysics'):
        result = conductor_impedance(mesh, [1e4], **args, relative_permeability=mu, keep_fields=True)
    with clock('reference'):
        basis = sk.Basis(sk.MeshTri(mesh.nodes.T, mesh.triangles.T), sk.ElementTriP1())
        @sk.BilinearForm
        def stiffness(u, v, w): return dot(grad(u), grad(v))/(mu_0*w.mu)
        @sk.BilinearForm
        def mass(u, v, w): return w.sigma*u*v
        @sk.LinearForm
        def load(v, w): return w.sigma*v
        k = sk.asm(stiffness, basis, mu=mu[:, None])
        m = sk.asm(mass, basis, sigma=sigma[:, None])
        q = np.column_stack([sk.asm(load, basis, sigma=np.where(np.isin(np.arange(mesh.num_triangles), ids), sigma, 0)[:, None])
                            for ids in [*args['signals'].values(), args['ground']]])
        d = np.diag(q.sum(axis=0))
        free = np.setdiff1d(np.arange(basis.N), args['magnetic_boundary'])
        q = q[free]
        operator = bmat([[k[free][:, free]+1j*omega*m[free][:, free], csc_matrix(-q)],
                         [csc_matrix(-1j*omega*q.T), csc_matrix(d)]], format='csc')
        prescribed = np.vstack((np.eye(2), -np.ones((1, 2))))
        solved = spsolve(operator, np.vstack((np.zeros((len(free), 2)), prescribed)))
        z = prescribed.T@solved[-3:]
        az = np.zeros((mesh.num_nodes, 2), complex)
        az[free] = solved[:-3]
        j = np.zeros((mesh.num_triangles, 2), complex)
        for group, ids in enumerate([*args['signals'].values(), args['ground']]):
            j[ids] = sigma[ids, None]*(solved[-3+group]-1j*omega*az[mesh.triangles[ids]].mean(axis=1))
    errors = [float(np.max(abs(a-b))/np.max(abs(b))) for a,b in
              [(result.Z[0], z), (result.vector_potential[0], az), (result.current_density[0], j)]]
    record_property('magnetic_reference', str(dict(zip(('Z', 'A', 'J'), errors))))
    assert max(errors) < 1e-9
    record = make_record(case='sipi-piecewise-magnetic-diffusion',
        physics='longitudinal magnetoquasistatic diffusion with spatial permeability',
        api='sipi.conductor_diffusion.conductor_impedance', discretization='P1 volume fields and current Schur system',
        tool='scikit-fem', tool_discretization='independent P1 forms and augmented current-constraint solve',
        matched=['same mesh, piecewise triangle conductivity and permeability, 10 kHz',
                 'two signals and common return, Az=0 exterior, exp(+j omega t)'],
        not_matched=['common-mesh agreement does not establish discretization or outer convergence'],
        observables=[observable(name, unit, 'normalized maximum difference', error, 1e-9)
                     for name, unit, error in zip(('Z', 'Az', 'Jz'), ('ohm/m', 'Wb/m', 'A/m^2'), errors)],
        analytical_acceptance='test_spatial_permeability.py: coax DC energy and Bessel/domain convergence',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi', version=metadata.version('sipi'))
    emit(record)
