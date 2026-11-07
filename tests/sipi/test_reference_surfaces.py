# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Reference partition power, independent fields and distinct-plane limits."""
from dataclasses import replace
from importlib import metadata

import numpy as np
import pytest

from sipi import CrossSection, Layer, Trace, PolygonTrace, stripline, coupled_microstrip
from sipi.boundary_conductor import SurfaceMetal
from sipi.face_conductor import (TraceFaceMetals, ReferenceSurfaceMetals, FaceCurrentFactors,
    surface_conductor_loss_by_face, _face_from_mesh, _face_samples)
from sipi.constants import epsilon_0, mu_0
from crosscheck import require_tool, Stopwatch, emit, make_record, observable

F = np.array([1e9, 4e9])
METAL = SurfaceMetal(58e6)
COARSE = dict(edge_size=5e-6, far_size=.2e-3, grade=.1)
FINE = dict(edge_size=2.5e-6, far_size=.1e-3, grade=.05)


def signals(section):
    return {t.name: TraceFaceMetals.uniform(METAL) for t in section.traces if not t.ground}


def reference(section, uniform=False):
    return ReferenceSurfaceMetals(
        METAL if section.bottom == 'ground' else None,
        (METAL if uniform else SurfaceMetal(58e6/4)) if section.top == 'ground' else None,
        (METAL if uniform else SurfaceMetal(45e6)) if section.sides == 'ground' else None,
        {t.name: METAL if uniform else SurfaceMetal(58e6, roughness_rms=.5e-6)
         for t in section.traces if t.ground})


def solve(section, ref=None, **mesh):
    return surface_conductor_loss_by_face(section, F, conductors=signals(section),
        reference=reference(section) if ref is None else ref, ground_thickness=35e-6, **mesh)


def boxed_pair():
    old = coupled_microstrip(width=.5e-3, gap=.3e-3, substrate_height=.5e-3,
        thickness=50e-6, eps_r=4., air_height=1.5e-3, box_width=6e-3)
    ground = [Trace('guardL', -2e-3, .4e-3, .5e-3, 50e-6, ground=True),
              Trace('guardR', 2e-3, .4e-3, .5e-3, 50e-6, ground=True)]
    return CrossSection(old.layers, [*old.traces, *ground], old.width,
                        bottom='ground', top='ground', sides='ground')


@pytest.fixture(scope='module')
def enclosed():
    section = boxed_pair(); meshed = section.mesh(**FINE)
    result = _face_from_mesh(meshed, *_face_samples(section, F, signals(section), reference(section), 35e-6))
    return section, meshed, result


def test_independent_reference_currents_and_power(enclosed):
    skfem = require_tool('scikit-fem')
    from skfem.helpers import dot, grad
    section, mesh, known = enclosed; clock = Stopwatch()
    with clock('openphysics'):
        actual = _face_from_mesh(mesh, *_face_samples(section, F, signals(section), reference(section), 35e-6))
    with clock('reference'):
        basis = skfem.Basis(skfem.MeshTri(mesh.mesh.nodes.T, mesh.mesh.triangles.T), skfem.ElementTriP1())
        @skfem.BilinearForm
        def laplace(u, v, w): return dot(grad(u), grad(v))
        k = skfem.asm(laplace, basis)
        fixed = np.unique(np.concatenate([mesh.ground, *mesh.signals.values()]))
        fields = []
        for nodes in mesh.signals.values():
            v = np.zeros(basis.N); v[nodes] = 1.
            fields.append(skfem.solve(*skfem.condense(k, np.zeros(basis.N), x=v, D=fixed)))
        values = np.array(fields).T
        c0 = epsilon_0*values.T@(k@values)
        gradients = np.stack([basis.interpolate(v).grad[:, :, 0].T for v in fields], axis=-1)
        triangles = mesh.mesh.triangles
        all_edges = triangles[:, [[0, 1], [1, 2], [2, 0]]].reshape(-1, 2)
        _, first, count = np.unique(np.sort(all_edges, axis=1), axis=0, return_index=True, return_counts=True)
        at = first[count == 1]; edges = all_edges[at]
        tangent = mesh.mesh.nodes[edges[:, 1]]-mesh.mesh.nodes[edges[:, 0]]
        lengths = np.linalg.norm(tangent, axis=1)
        normals = np.c_[tangent[:, 1], -tangent[:, 0]]/lengths[:, None]
        currents = epsilon_0*np.einsum('ed,edn->en', normals, gradients[at//3])@np.linalg.inv(c0)
        mid = mesh.mesh.nodes[edges].mean(axis=1)
        ground = np.isin(edges, mesh.ground).all(axis=1)
        masks = [ground & np.isclose(mid[:, 1], 0, rtol=0, atol=1e-12),
                 ground & np.isclose(mid[:, 1], section.height, rtol=0, atol=1e-12),
                 ground & np.isclose(abs(mid[:, 0]), section.width/2, rtol=0, atol=1e-12)]
        interior = ground & ~np.any(masks, axis=0)
        masks.extend([interior & (mid[:, 0] < 0), interior & (mid[:, 0] > 0)])
        assert np.array_equal(np.sum(masks, axis=0), ground.astype(int))
        q = np.array([currents[m].T@(lengths[m, None]*currents[m]) for m in masks])
        integrals = np.array([np.sum(lengths[m, None]*currents[m], axis=0) for m in masks])
    error = float(np.max(abs(q-actual.factors.parts[8:]))/np.max(abs(q)))
    flux = float(np.max(abs(integrals-actual.factors.current_integrals[8:])))
    record = make_record(case='reference-surface-currents', physics='PEC reference surface perturbation',
        api='sipi.face_conductor.ReferenceSurfaceMetals', discretization='one vacuum P1 field; planes/walls/ground traces',
        tool='scikit-fem', tool_discretization='independent P1 solve and midpoint-classified ground power',
        matched=['same two-signal mesh, ground planes, side walls and two explicit ground traces',
                 'same unit-current normalization and complete ground perimeter'],
        not_matched=['finite metal diffusion, ground trace face separation or empirical foil accuracy'],
        observables=[observable('reference current products', '1/m', 'max normalized matrix difference', error, 1e-10),
                     observable('reference integrated current', '1', 'max absolute difference', flux, 1e-10)],
        analytical_acceptance='distinct-plane wide stripline, uniform reduction, PSD, whole-ground sum and mesh/box limits',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi', version=metadata.version('sipi')); emit(record)
    assert error < 1e-10 and flux < 1e-10
    assert known.boundary_labels[-5:] == ('reference:bottom', 'reference:top', 'reference:sides',
                                         'reference:ground:guardL', 'reference:ground:guardR')


def test_uniform_reference_reduction_conservation_and_passive_network(enclosed):
    section, mesh, result = enclosed
    uniform = _face_from_mesh(mesh, *_face_samples(section, F, signals(section), reference(section, True), 35e-6))
    common = _face_from_mesh(mesh, *_face_samples(section, F, signals(section), METAL, 35e-6))
    for key in ('R', 'L_internal'):
        np.testing.assert_allclose(getattr(uniform, key), getattr(common, key), rtol=1e-12)
    np.testing.assert_array_equal(uniform.factors.C0, common.factors.C0)
    for key in ('parts', 'current_integrals'):
        value = getattr(result.factors, key)
        np.testing.assert_allclose(value[8:].sum(axis=0), getattr(result.factors.base, key)[-1], rtol=1e-12, atol=1e-12)
    assert result.factors.current_error < .05
    np.testing.assert_allclose(result.resistance_parts.sum(axis=1), result.R, rtol=1e-12)
    for matrix in (result.R, result.L_internal, result.factors.parts):
        assert np.linalg.eigvalsh(matrix).min() > -1e-10
        np.testing.assert_allclose(matrix, matrix.swapaxes(-1, -2), atol=1e-10)
    assert np.linalg.eigvalsh(result.R-uniform.R).min() > -1e-10
    cap = mesh.line_parameters()
    net = result.network(C=cap.C, G=np.zeros((2, 2)), length=.02)
    assert np.linalg.svd(net.s, compute_uv=False).max() <= 1+1e-10
    np.testing.assert_allclose(net.s, net.s.swapaxes(1, 2), atol=1e-10)
    assert not result.factors.parts.flags.writeable


def test_reference_mesh_and_outer_convergence():
    def section(width):
        return CrossSection([Layer('d', 1e-3, 4.)],
            [Trace('signal', 0., .5e-3, .575e-3, 50e-6)], width, top='ground')
    small, wide = section(4e-3), section(8e-3)
    coarse = solve(small, **COARSE); fine = solve(small, **FINE); outer = solve(wide, **FINE)
    changes = [float(np.max(abs(v.R-fine.R))/np.max(abs(fine.R))) for v in (coarse, outer)]
    assert max(changes) < .05
    assert max(v.factors.current_error for v in (coarse, fine, outer)) < .05
    print('reference R mesh/box changes', changes)


def test_wide_centered_stripline_separate_plane_power():
    section = stripline(width=.01, plane_spacing=.000235, thickness=35e-6, eps_r=4., box_width=.014)
    refs = ReferenceSurfaceMetals(METAL, SurfaceMetal(58e6/9), None, {})
    values = [solve(section, refs, **opts) for opts in
        [dict(edge_size=4e-6, far_size=.2e-3, grade=.3), dict(edge_size=2e-6, far_size=.1e-3, grade=.15)]]
    fine = values[-1]
    # Equal vacuum return currents: each signal and reference horizontal face has Q=1/(4w).
    np.testing.assert_allclose(fine.factors.parts[[0, 1, 4, 5], 0, 0], [25]*4, rtol=.05)
    expected = 150*np.sqrt(np.pi*F*mu_0/58e6)
    np.testing.assert_allclose(fine.R[:, 0, 0], expected, rtol=.05)
    np.testing.assert_allclose(fine.L_internal[:, 0, 0], expected/(2*np.pi*F), rtol=.05)
    assert np.max(abs(values[0].R/fine.R-1)) < .05
    print('reference plate Q', fine.factors.parts[:, 0, 0], 'R relative error', np.max(abs(fine.R[:, 0, 0]/expected-1)))


@pytest.mark.parametrize('boundary', ['bottom', 'top', 'sides', 'trace', 'polygon'])
def test_each_reference_kind_can_be_the_only_ground(boundary):
    trace = Trace('signal', 0, .5e-3, .475e-3, 50e-6)
    traces = [trace]
    if boundary == 'trace': traces.append(Trace('return', 1e-3, .4e-3, .475e-3, 50e-6, ground=True))
    if boundary == 'polygon':
        traces.append(PolygonTrace('return', [(x*1e-3, y*1e-3) for x, y in
            [(0.8, .475), (1.2, .475), (1.15, .525), (.85, .525)]], ground=True))
    section = CrossSection([Layer('d', 1e-3, 4)], traces, 4e-3,
        **{side: 'ground' if side == boundary else 'open' for side in ('bottom', 'top', 'sides')})
    result = solve(section, reference(section, True), **FINE)
    expected = 'reference:'+('ground:return' if boundary in ('trace', 'polygon') else boundary)
    assert result.factors.reference_labels == (expected,)
    np.testing.assert_allclose(result.factors.parts[-1], result.factors.base.parts[-1], rtol=1e-12)


@pytest.mark.parametrize('case', ['missing_plane', 'open_plane', 'missing_trace', 'extra_trace',
    'bad_metal', 'bad_map', 'bad_key', 'plane_depth', 'trace_depth', 'dc'])
def test_reference_input_and_skin_gates_before_meshing(monkeypatch, case):
    section = boxed_pair(); ref = reference(section); frequency = F
    def forbidden(*args, **kwargs): pytest.fail('invalid reference input reached meshing')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    with pytest.raises(ValueError):
        if case == 'missing_plane': ref = replace(ref, top=None)
        if case == 'open_plane':
            section = CrossSection(section.layers, section.traces, section.width, top='open', sides='ground')
        if case == 'missing_trace': ref = replace(ref, conductors={})
        if case == 'extra_trace': ref = replace(ref, conductors={**ref.conductors, 'extra': METAL})
        if case == 'bad_metal': ref = replace(ref, bottom=35.)
        if case == 'bad_map': ref = replace(ref, conductors=[])
        if case == 'bad_key': ref = replace(ref, conductors={3: METAL})
        if case == 'plane_depth': ref = replace(ref, top=SurfaceMetal(1e4))
        if case == 'trace_depth': ref = replace(ref, conductors={**ref.conductors, 'guardL': SurfaceMetal(1e4)})
        if case == 'dc': frequency = [0.]
        surface_conductor_loss_by_face(section, frequency, conductors=signals(section), reference=ref, ground_thickness=35e-6)


def test_reference_assignment_detaches_mapping_and_rejects_partition_loss(enclosed):
    section, _, result = enclosed
    mapping = {'guardL': METAL, 'guardR': METAL}
    ref = ReferenceSurfaceMetals(METAL, METAL, METAL, mapping)
    mapping.clear()
    assert set(ref.conductors) == {'guardL', 'guardR'}
    with pytest.raises(TypeError): ref.conductors['guardL'] = SurfaceMetal(1e6)
    parts = np.array(result.factors.parts); parts[-1] *= 2.
    with pytest.raises(ValueError, match='partition'):
        FaceCurrentFactors(result.factors.base, parts, result.factors.current_integrals, result.factors.reference_labels)
