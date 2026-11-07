# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Signal-face partition, independent field power and retained surface gates."""
from dataclasses import replace
from importlib import metadata

import numpy as np
import pytest

from sipi import CrossSection, Layer, PolygonTrace, microstrip, coupled_microstrip, stripline
from sipi.boundary_conductor import SurfaceMetal, surface_conductor_loss_by_boundary
from sipi.face_conductor import (TraceFaceMetals, FaceCurrentFactors, surface_conductor_loss_by_face,
                                 _face_samples, _face_from_mesh)
from sipi.constants import epsilon_0, mu_0
from sipi.roughness import CausalHuray, CannonballHuray, GroissRMS
from crosscheck import require_tool, Stopwatch, make_record, observable, emit

F = np.array([1e9, 4e9])
SMOOTH = SurfaceMetal(58e6)
COARSE = dict(edge_size=5e-6, far_size=.2e-3, grade=.1)
FINE = dict(edge_size=2.5e-6, far_size=.1e-3, grade=.05)


def section(**changes):
    return coupled_microstrip(**dict(dict(width=.5e-3, gap=.3e-3, substrate_height=.5e-3,
        thickness=50e-6, eps_r=4., top_width=.4e-3, air_height=2e-3, box_width=6e-3), **changes))


def assignments(s):
    names = [t.name for t in s.traces if not t.ground]
    return {names[0]: TraceFaceMetals(SurfaceMetal(58e6, roughness=CausalHuray([.2e-6], [2.])),
        SurfaceMetal(58e6, roughness_rms=.5e-6), SurfaceMetal(35e6),
        SurfaceMetal(58e6, roughness=GroissRMS(.8e-6))), names[1]: TraceFaceMetals.uniform(SMOOTH)}


@pytest.fixture(scope='module')
def coupled():
    s = section(); ref = SurfaceMetal(45e6, roughness=CannonballHuray(2e-6))
    sample = _face_samples(s, F, assignments(s), ref, 35e-6)
    mesh = s.mesh(**COARSE)
    coarse = _face_from_mesh(mesh, *sample)
    fine = surface_conductor_loss_by_face(s, F, conductors=assignments(s), reference=ref,
                                         ground_thickness=35e-6, **FINE)
    wide = section(box_width=12e-3)
    outer = surface_conductor_loss_by_face(wide, F, conductors=assignments(wide), reference=ref,
                                          ground_thickness=35e-6, **FINE)
    return s, mesh, coarse, fine, outer


def test_independent_complex_power_from_scikit_fem_gradients(coupled):
    skfem = require_tool('scikit-fem')
    from skfem.helpers import dot, grad
    s, m, actual, _, _ = coupled; clock = Stopwatch()
    with clock('openphysics'):
        actual = _face_from_mesh(m, *_face_samples(s, F, assignments(s),
            SurfaceMetal(45e6, roughness=CannonballHuray(2e-6)), 35e-6))
    with clock('reference'):
        basis = skfem.Basis(skfem.MeshTri(m.mesh.nodes.T, m.mesh.triangles.T), skfem.ElementTriP1())
        @skfem.BilinearForm
        def laplace(u, v, w): return dot(grad(u), grad(v))
        k = skfem.asm(laplace, basis)
        fixed = np.unique(np.concatenate([m.ground, *m.signals.values()])); fields = []
        for nodes in m.signals.values():
            v = np.zeros(basis.N); v[nodes] = 1
            fields.append(skfem.solve(*skfem.condense(k, np.zeros(basis.N), x=v, D=fixed)))
        v = np.array(fields).T
        c0 = epsilon_0*(v.T@(k@v))
        gradients = np.stack([basis.interpolate(v[:, i]).grad[:, :, 0].T for i in range(v.shape[1])], axis=-1)
        triangles = m.mesh.triangles
        edges_all = triangles[:, [[0, 1], [1, 2], [2, 0]]].reshape(-1, 2)
        _, first, count = np.unique(np.sort(edges_all, axis=1), axis=0, return_index=True, return_counts=True)
        indices = first[count == 1]; edges = edges_all[indices]
        tangent = m.mesh.nodes[edges[:, 1]]-m.mesh.nodes[edges[:, 0]]
        length = np.linalg.norm(tangent, axis=1)
        normal = np.c_[tangent[:, 1], -tangent[:, 0]]/length[:, None]
        currents = epsilon_0*np.einsum('ed,edn->en', normal, gradients[indices//3])@np.linalg.inv(c0)
        mid = m.mesh.nodes[edges].mean(axis=1)
        selections = []
        for trace, nodes in zip(s.traces, m.signals.values()):
            metal = np.isin(edges, nodes).all(axis=1)
            bottom = metal & np.isclose(mid[:, 1], trace.y, rtol=0, atol=1e-12)
            top = metal & np.isclose(mid[:, 1], trace.y1, rtol=0, atol=1e-12)
            side = metal & ~bottom & ~top
            selections.extend([bottom, top, side & (mid[:, 0] < trace.x), side & (mid[:, 0] > trace.x)])
        selections.append(np.isin(edges, m.ground).all(axis=1))
        expected = np.array([currents[mask].T@(length[mask, None]*currents[mask]) for mask in selections])
        integrals = np.array([np.sum(length[mask, None]*currents[mask], axis=0) for mask in selections])
    error = float(np.max(abs(expected-actual.factors.parts))/np.max(abs(expected)))
    flux_error = float(np.max(abs(integrals-actual.factors.current_integrals)))
    record = make_record(case='trace-face-surface-current', physics='PEC surface-current perturbation',
        api='sipi.face_conductor.surface_conductor_loss_by_face', discretization='one vacuum P1 solve and four trace faces',
        tool='scikit-fem', tool_discretization='independent P1 solve/interpolated gradients, face power integrals',
        matched=['same mesh, tapered two-signal geometry, grounds and unit-current normalization',
                 'bottom/top/left/right named in global section coordinates'],
        not_matched=['roughness empirical accuracy, bulk coating diffusion or reference-face separation'],
        observables=[observable('face current products', '1/m', 'max normalized matrix difference', error, 1e-10),
                     observable('face integrated current', '1', 'maximum absolute difference', flux_error, 1e-10)],
        analytical_acceptance='wide-stripline face currents, equal-face reduction, PSD and mesh/box loss gates', stopwatch=clock)
    record['openphysics'].update(distribution='sipi', version=metadata.version('sipi')); emit(record)
    assert error < 1e-10 and flux_error < 1e-10


def test_partition_conservation_psd_network_and_mesh_box_convergence(coupled):
    s, _, coarse, fine, outer = coupled
    assert fine.boundary_labels == tuple('signal:'+name+':'+face for name in ('positive', 'negative')
                                        for face in ('bottom', 'top', 'left', 'right'))+('reference',)
    for result in (coarse, fine, outer):
        factors = result.factors; n = len(factors.names)
        np.testing.assert_allclose(factors.parts[:-1].reshape(n, 4, n, n).sum(axis=1),
                                   factors.base.parts[:-1], rtol=1e-12, atol=1e-12)
        np.testing.assert_allclose(result.resistance_parts.sum(axis=1), result.R, rtol=1e-12, atol=1e-12)
        assert factors.current_error < .05
    changes = [float(np.max(abs(a.R-fine.R))/np.max(abs(fine.R))) for a in (coarse, outer)]
    assert max(changes) < .05
    for matrices in (fine.R, fine.L_internal, fine.factors.parts):
        np.testing.assert_allclose(matrices, matrices.swapaxes(-1, -2), rtol=0, atol=1e-10)
        assert np.linalg.eigvalsh(matrices).min() >= -1e-10
    cap = s.analyze(**FINE)
    net = fine.network(C=cap.C, G=np.zeros((2, 2)), length=.03)
    assert np.linalg.svd(net.s, compute_uv=False).max() <= 1+1e-10
    np.testing.assert_allclose(net.s, net.s.swapaxes(1, 2), rtol=0, atol=1e-10)
    for array in (fine.R, fine.L_internal, fine.factors.parts, fine.factors.current_integrals,
                  fine.surface_impedance, fine.skin_depth, fine.roughness_factor, fine.resistance_parts):
        assert not array.flags.writeable
    print('face loss mesh/box relative changes', changes, 'flux coarse/fine', coarse.factors.current_error, fine.factors.current_error)


@pytest.mark.parametrize('metal', [SMOOTH, SurfaceMetal(58e6, roughness_rms=.8e-6),
    SurfaceMetal(58e6, roughness=GroissRMS(.8e-6)), SurfaceMetal(58e6, roughness=CausalHuray([.2e-6], [2.])),
    SurfaceMetal(58e6, roughness=CannonballHuray(2e-6))])
def test_uniform_face_laws_reproduce_existing_whole_boundary_model(metal):
    s = microstrip(width=.5e-3, substrate_height=.5e-3, thickness=35e-6, eps_r=4,
                   air_height=1e-3, box_width=4e-3)
    kwargs = dict(reference=metal, ground_thickness=35e-6, **FINE)
    old = surface_conductor_loss_by_boundary(s, F, conductors={'signal': metal}, **kwargs)
    new = surface_conductor_loss_by_face(s, F, conductors={'signal': TraceFaceMetals.uniform(metal)}, **kwargs)
    for attr in ('R', 'L_internal'):
        np.testing.assert_allclose(getattr(new, attr), getattr(old, attr), rtol=1e-12)
    np.testing.assert_array_equal(new.factors.C0, old.factors.C0)


def test_wide_stripline_analytical_face_currents_and_distinct_metals():
    s = stripline(width=.01, plane_spacing=.000235, thickness=35e-6, eps_r=4, box_width=.014)
    # Rs ratios bottom/top/sides/reference = 1/3/2/1 at every frequency.
    faces = TraceFaceMetals(SMOOTH, SurfaceMetal(58e6/9), SurfaceMetal(58e6/4), SurfaceMetal(58e6/4))
    values = []
    for mesh in [dict(edge_size=4e-6, far_size=.2e-3, grade=.3),
                 dict(edge_size=2e-6, far_size=.1e-3, grade=.15)]:
        result = surface_conductor_loss_by_face(s, F, conductors={'signal': faces},
            reference=SMOOTH, ground_thickness=35e-6, **mesh)
        values.append(result)
    expected_r = 150*np.sqrt(np.pi*F*mu_0/58e6)
    np.testing.assert_allclose(values[-1].R[:, 0, 0], expected_r, rtol=.05)
    np.testing.assert_allclose(values[-1].L_internal[:, 0, 0], expected_r/(2*np.pi*F), rtol=.05)
    np.testing.assert_allclose(values[-1].factors.parts[[0, 1, 4], 0, 0], [25, 25, 50], rtol=.05)
    assert np.max(abs(values[0].R/values[1].R-1)) < .05
    print('wide stripline face Q', values[-1].factors.parts[:, 0, 0],
          'R error', np.max(abs(values[-1].R[:, 0, 0]/expected_r-1)))


def test_face_exchange_and_extra_roughness_preserve_power_order(coupled):
    s, m, _, _, _ = coupled
    names = list(m.signals)
    def solve(top=False):
        metals = {name: TraceFaceMetals.uniform(SMOOTH) for name in names}
        rough = SurfaceMetal(58e6, roughness_rms=2e-6)
        metals[names[0]] = replace(metals[names[0]], **{('top' if top else 'bottom'): rough})
        return _face_from_mesh(m, *_face_samples(s, F, metals, SMOOTH, 35e-6))
    bottom, top = solve(), solve(True)
    baseline = _face_from_mesh(m, *_face_samples(s, F,
        {name: TraceFaceMetals.uniform(SMOOTH) for name in names}, SMOOTH, 35e-6))
    assert np.linalg.eigvalsh(bottom.R-baseline.R).min() >= -1e-10
    assert np.linalg.eigvalsh(top.R-baseline.R).min() >= -1e-10
    for result, index in [(bottom, 0), (top, 1)]:
        expected = ((result.surface_impedance[:, index]-baseline.surface_impedance[:, index]).real[:, None, None]
                    *baseline.factors.parts[index])
        np.testing.assert_allclose(result.R-baseline.R, expected, rtol=1e-10, atol=1e-12)
    assert np.max(abs(bottom.R-top.R)) > 1e-3


@pytest.mark.parametrize('case', ['missing', 'extra', 'wrong_type', 'bad_face', 'bad_reference',
    'face_depth', 'reference_depth', 'ground_depth', 'zero_thickness', 'polygon', 'dc'])
def test_all_geometry_and_local_depth_gates_precede_meshing(monkeypatch, case):
    s = microstrip(width=.5e-3, substrate_height=.5e-3, thickness=0 if case == 'zero_thickness' else 35e-6,
                   eps_r=4, air_height=1e-3, box_width=4e-3)
    if case == 'polygon':
        s = CrossSection([Layer('d', 1e-3, 4)],
            [PolygonTrace('signal', [(-.2e-3, .4e-3), (.2e-3, .4e-3), (0, .5e-3)])], 4e-3)
    metals = {'signal': TraceFaceMetals.uniform(SMOOTH)}; reference = SMOOTH; f = F; thickness = 35e-6
    if case == 'missing': metals = {}
    if case == 'extra': metals['unknown'] = metals['signal']
    if case == 'wrong_type': metals['signal'] = SMOOTH
    if case == 'bad_reference': reference = {}
    if case == 'face_depth': metals['signal'] = replace(metals['signal'], top=SurfaceMetal(1e4))
    if case == 'reference_depth': reference = SurfaceMetal(1e4)
    if case == 'ground_depth': thickness = 1e-9
    if case == 'dc': f = [0]
    def forbidden(*args, **kwargs): pytest.fail('invalid face assignment reached meshing')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    with pytest.raises(ValueError):
        if case == 'bad_face': metals['signal'] = TraceFaceMetals(SMOOTH, {}, SMOOTH, SMOOTH)
        surface_conductor_loss_by_face(s, f, conductors=metals, reference=reference, ground_thickness=thickness, **FINE)


def test_partition_and_whole_conductor_flux_guards(coupled, monkeypatch):
    import sipi.face_conductor as implementation
    s, m, result, _, _ = coupled
    changed = np.array(result.factors.parts); changed[0] *= 2
    with pytest.raises(ValueError, match='partition'):
        FaceCurrentFactors(result.factors.base, changed, result.factors.current_integrals)
    raw = implementation._surface_current_data(m.mesh, m.signals, m.ground)
    bad = replace(raw[0], current_integrals=np.zeros_like(raw[0].current_integrals))
    monkeypatch.setattr(implementation, '_surface_current_data', lambda *args: (bad, *raw[1:]))
    with pytest.raises(ValueError, match='flux error'):
        _face_from_mesh(m, *_face_samples(s, F, assignments(s), SMOOTH, 35e-6))
