# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Analytical TEM propagation, independent edge FEM, invariants and rejection."""
from dataclasses import replace
from importlib import metadata

import numpy as np
import pytest
from galerkin.mesh import annulus_mesh
from galerkin.mesh3d import Mesh3D
from galerkin.assembly import assemble_stiffness
from galerkin.edge3d import EdgeSpace3D
from galerkin.core.spaces import edge_ids
from meshine.mesh import TriMesh
from meshine.extrude import extrude
from scipy.sparse.linalg import splu, spsolve
from sipi.constants import epsilon_0, mu_0
from sipi.ports3d import TEMPort3D, solve_tem_ports_3d
from crosscheck import require_tool, Stopwatch, emit, make_record, observable

A, B, LENGTH, EPS = .25e-3, 1e-3, 5e-3, 4.


def coax(nr=1, nt=12, nz=2):
    base = annulus_mesh(A, B, nr, nt)
    footprint = TriMesh(base.nodes, base.triangles, np.zeros(len(base.triangles), int),
                        ['dielectric'], base.boundary_edges)
    raw = extrude(footprint, [0, LENGTH], divisions=nz)
    mesh = Mesh3D(raw.nodes, raw.tetrahedra)
    faces = mesh.boundary_faces()
    ports = []
    for name, z in [('near', 0.), ('far', LENGTH)]:
        selected = faces[np.all(mesh.nodes[faces, 2] == z, axis=1)]
        nodes = np.unique(selected)
        ports.append(TEMPort3D(name, selected, np.intersect1d(nodes, raw.boundary_nodes['inner']),
                              np.intersect1d(nodes, raw.boundary_nodes['outer'])))
    return mesh, ports, base


def solve(mesh, ports, frequency=(1e9,), **kw):
    return solve_tem_ports_3d(mesh, ports=ports, frequency=frequency, eps_r=EPS, **kw)


def test_coax_analytic_complex_transmission_and_reflection_refine():
    errors = []
    for config in [(1, 12, 2), (2, 24, 4), (4, 48, 8)]:
        mesh, ports, _ = coax(*config)
        result = solve(mesh, ports)
        s = result.network.s[0]
        exact = np.exp(-2j*np.pi*1e9*np.sqrt(mu_0*epsilon_0*EPS)*LENGTH)
        errors.append(abs(s[1, 0]-exact))
        assert result.linear_residual.max() < 1e-8
        assert result.power_balance.max() < 1e-8
        assert result.reciprocity.max() < 1e-8
        assert result.num_tets == len(mesh.tets)
        assert result.num_edges == EdgeSpace3D(mesh).num_edges
        # Full outgoing power is conserved. TEM-only S need not be unitary.
        np.testing.assert_allclose(np.sum(abs(s)**2, axis=0)+result.unprojected_port_power[0],
                                   np.ones(2), rtol=0, atol=1e-8)
    assert errors[0] > errors[1] > errors[2]
    assert errors[-1] < .02
    assert max(abs(s[0, 0]), abs(s[1, 1])) < .02
    exact_z = np.sqrt(mu_0/(epsilon_0*EPS))*np.log(B/A)/(2*np.pi)
    assert abs(result.network.z_ref[0]/exact_z-1) < .02


def test_independent_edge_fem_same_mesh_ports_and_power_projection():
    skfem = require_tool('scikit-fem')
    from skfem.helpers import dot, curl
    mesh, ports, base = coax()
    clock = Stopwatch()
    with clock('openphysics'):
        result = solve(mesh, ports)
    with clock('reference'):
        peer = skfem.MeshTet(mesh.nodes.T, mesh.tets.T, sort_t=False)
        basis = skfem.Basis(peer, skfem.ElementTetN1())
        @skfem.BilinearForm
        def stiffness(u, v, w): return dot(curl(u), curl(v))
        @skfem.BilinearForm
        def mass(u, v, w): return dot(u, v)
        @skfem.BilinearForm
        def boundary(u, v, w): return dot(u, v)-dot(u, w.n)*dot(v, w.n)
        lookup = {tuple(sorted(face)): i for i, face in enumerate(peer.facets.T)}
        matrices = [skfem.asm(boundary, skfem.FacetBasis(peer, skfem.ElementTetN1(),
            facets=np.array([lookup[tuple(sorted(face))] for face in port.faces]), intorder=2))
            for port in ports]
        # Independent port potential construction on the extruded footprint.
        k = assemble_stiffness(base)
        phi = np.zeros(len(base.nodes)); phi[base.boundary['inner']] = 1.
        fixed = np.r_[base.boundary['inner'], base.boundary['outer']]
        free = np.setdiff1d(np.arange(len(phi)), fixed)
        if len(free): phi[free] = spsolve(k[free][:, free], -k[free][:, fixed]@phi[fixed])
        values = {tuple(x): p for x, p in zip(base.nodes, phi)}
        potential = np.array([values[tuple(x[:2])] for x in mesh.nodes])
        electric = potential[peer.edges[0]]-potential[peer.edges[1]]
        port_faces = {tuple(sorted(face)) for port in ports for face in port.faces}
        wall_faces = np.array([face for face in mesh.boundary_faces() if tuple(sorted(face)) not in port_faces])
        wall_pairs = np.sort(np.concatenate([wall_faces[:, [0, 1]], wall_faces[:, [0, 2]], wall_faces[:, [1, 2]]]), axis=1)
        wall_set = {tuple(edge) for edge in wall_pairs}
        pec = [i for i, edge in enumerate(peer.edges.T) if tuple(sorted(edge)) in wall_set]
        free = np.setdiff1d(np.arange(basis.N), pec)
        beta = 2*np.pi*1e9*np.sqrt(mu_0*epsilon_0*EPS)
        system = skfem.asm(stiffness, basis)-beta**2*skfem.asm(mass, basis)+1j*beta*sum(matrices)
        rhs = 2j*beta*np.column_stack([b@electric for b in matrices])
        fields = np.zeros((basis.N, 2), complex)
        fields[free] = splu(system[free][:, free].tocsc()).solve(rhs[free])
        norms = np.array([electric@b@electric for b in matrices])
        expected = np.array([[electric@b@fields[:, q]/norms[p]-(p == q)
                              for q in range(2)] for p, b in enumerate(matrices)])
        expected *= np.sqrt(norms[:, None]/norms[None, :])
    difference = float(np.max(abs(expected-result.network.s[0])))
    record = make_record(case='bounded_tem3d_coax', physics='homogeneous bounded Maxwell fields',
        api='sipi.ports3d.solve_tem_ports_3d', discretization='tetrahedral Whitney edges, planar P1 TEM ports',
        tool='scikit-fem', tool_discretization='independent ElementTetN1 volume and FacetBasis assembly/solve',
        matched=['same conforming tetrahedra, PEC walls and local TEM-admittance boundary',
                 'same power projection, exp(+jwt), homogeneous real epsilon and physical constants'],
        not_matched=['continuous-geometry accuracy and arbitrary transition accuracy',
                     'full multimode ports, radiation, conductor loss and heterogeneous dielectric'],
        observables=[observable('S', '1', 'maximum absolute complex difference', difference, 1e-9)],
        analytical_acceptance='separate coax refinement: complex transmission/reflection <.02; raw full-boundary power/residual/reciprocity <1e-8',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi', version=metadata.version('sipi'))
    emit(record)
    assert difference < 1e-9


def test_port_order_rotation_scale_frequency_and_orientation_invariants():
    mesh, ports, _ = coax(2, 16, 3)
    base = solve(mesh, ports, (5e8, 1e9))
    q, _ = np.linalg.qr(np.array([[1., 2., 3.], [2., -3., 1.], [4., 1., -2.]]))
    transformed = Mesh3D(7*mesh.nodes@q+[.02, -.01, .03], mesh.tets[:, [1, 0, 2, 3]])
    reordered = [replace(p, faces=p.faces[::-1, ::-1], signal=p.signal[::-1], ground=p.ground[::-1])
                 for p in ports[::-1]]
    result = solve(transformed, reordered, np.array([5e8, 1e9])/7)
    np.testing.assert_allclose(result.network.s, base.network.s[:, ::-1, ::-1], rtol=0, atol=1e-9)
    np.testing.assert_allclose(result.network.z_ref, base.network.z_ref[::-1], rtol=1e-9)
    assert result.network.port_names == ('far', 'near')
    for name in ('port_norm', 'linear_residual', 'power_balance', 'reciprocity',
                 'projected_unitarity', 'unprojected_port_power'):
        assert not getattr(result, name).flags.writeable
    snapshot = result.network.s.copy(); mesh.nodes[:] = 0
    np.testing.assert_array_equal(snapshot, result.network.s)


@pytest.mark.parametrize('frequency', [[0], [-1], [1e9, 1e9], [1e9, 1e8], [], [np.nan], [True], [[1e9]]])
def test_bad_frequency_rejected(frequency):
    mesh, ports, _ = coax()
    with pytest.raises(ValueError): solve(mesh, ports, frequency)


@pytest.mark.parametrize('eps', [True, 0, -1, float('nan'), float('inf'), 1+0j, [4.]])
def test_nonuniform_or_invalid_material_rejected(eps):
    mesh, ports, _ = coax()
    with pytest.raises(ValueError): solve_tem_ports_3d(mesh, ports=ports, frequency=[1e9], eps_r=eps)


@pytest.mark.parametrize('change', ['duplicate', 'interior', 'float', 'empty', 'removed',
                                    'partial_signal', 'same_loops', 'wrong_signal', 'nonplanar'])
def test_invalid_port_faces_or_perimeters_rejected(change):
    mesh, ports, _ = coax(2, 12, 2)
    p = ports[0]
    if change == 'duplicate': p = replace(p, faces=np.vstack([p.faces, p.faces[:1]]))
    if change == 'interior': p = replace(p, faces=mesh.tets[:1, :3])
    if change == 'float': p = replace(p, faces=p.faces.astype(float))
    if change == 'empty': p = replace(p, faces=np.empty((0, 3), int))
    if change == 'removed': p = replace(p, faces=p.faces[1:])
    if change == 'partial_signal': p = replace(p, signal=p.signal[:-1])
    if change == 'same_loops': p = replace(p, ground=p.signal)
    if change == 'wrong_signal': p = replace(p, signal=ports[1].signal)
    if change == 'nonplanar': mesh.nodes[p.signal[0], 2] += 1e-5
    with pytest.raises(ValueError): solve(mesh, [p, ports[1]])


def test_overlap_names_and_count_rejected():
    mesh, ports, _ = coax()
    for bad in ([ports[0]], [], [ports[0], ports[1], ports[1]], [ports[0], object()],
                [ports[0], replace(ports[0], name='other')], [ports[0], replace(ports[1], name='near')]):
        with pytest.raises(ValueError): solve(mesh, bad)
    for name in ('', ' ', 'bad\nport'):
        with pytest.raises(ValueError): replace(ports[0], name=name)


def test_invalid_volume_and_disconnected_mesh_rejected():
    mesh, ports, _ = coax()
    count = mesh.num_nodes
    for bad in (Mesh3D(mesh.nodes, np.vstack([mesh.tets, mesh.tets[:1]])),
                Mesh3D(np.vstack([mesh.nodes, [1, 2, 3]]), mesh.tets),
                Mesh3D(np.vstack([mesh.nodes, mesh.nodes+[1., 0, 0]]), np.vstack([mesh.tets, mesh.tets+count]))):
        with pytest.raises(ValueError): solve(bad, ports)


def test_boolean_indices_and_numerically_unrepresentable_frequency_rejected():
    mesh, ports, _ = coax()
    for key, value in [('signal', [0, True]), ('ground', [False]), ('faces', [[0, 1, True]])]:
        with pytest.raises(ValueError): replace(ports[0], **{key: value})
    with np.errstate(over='ignore', invalid='ignore'):
        with pytest.raises(ValueError): solve(mesh, ports, [1e300])
