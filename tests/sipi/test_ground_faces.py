# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Ground trace face laws, independent currents, conservation and foil limits."""
from dataclasses import replace
from importlib import metadata

import numpy as np
import pytest

from sipi import CrossSection, Layer, Trace, PolygonTrace, coupled_microstrip
from sipi.boundary_conductor import SurfaceMetal
from sipi.face_conductor import (TraceFaceMetals, ReferenceSurfaceMetals,
    surface_conductor_loss_by_face, _face_from_mesh, _face_samples)
from sipi.roughness import CausalHuray
from sipi.constants import epsilon_0, mu_0
from crosscheck import require_tool, Stopwatch, emit, make_record, observable

F = np.array([1e9, 4e9])
METAL = SurfaceMetal(58e6)
COARSE = dict(edge_size=5e-6, far_size=.2e-3, grade=.1)
FINE = dict(edge_size=2.5e-6, far_size=.1e-3, grade=.05)
FACES = ('bottom', 'top', 'left', 'right')


def signals(section):
    return {t.name: TraceFaceMetals.uniform(METAL) for t in section.traces if not t.ground}


def boxed_pair(width=6e-3):
    old = coupled_microstrip(width=.5e-3, gap=.3e-3, substrate_height=.5e-3,
        thickness=50e-6, eps_r=4., air_height=1.5e-3, box_width=width)
    grounds = [Trace('guardL', -2e-3, .4e-3, .5e-3, 50e-6, ground=True, top_width=.3e-3),
               Trace('guardR', 2e-3, .4e-3, .5e-3, 50e-6, ground=True, top_width=.5e-3)]
    return CrossSection(old.layers, [*old.traces, *grounds], old.width,
                        bottom='ground', top='ground', sides='ground')


def reference(section, *, uniform=False, whole=False):
    faces = (TraceFaceMetals.uniform(METAL) if uniform else
        TraceFaceMetals(METAL, SurfaceMetal(58e6/4), SurfaceMetal(45e6, roughness_rms=.5e-6),
                       SurfaceMetal(58e6, roughness=CausalHuray((.5e-6,), (1.2,)))))
    return ReferenceSurfaceMetals(
        METAL if section.bottom == 'ground' else None,
        METAL if section.top == 'ground' else None,
        METAL if section.sides == 'ground' else None,
        {t.name: METAL if whole else faces for t in section.traces if t.ground})


def solve(section, ref=None, **mesh):
    return surface_conductor_loss_by_face(section, F, conductors=signals(section),
        reference=reference(section) if ref is None else ref, ground_thickness=35e-6, **mesh)


@pytest.fixture(scope='module')
def enclosed():
    section = boxed_pair(); mesh = section.mesh(**FINE)
    result = _face_from_mesh(mesh, *_face_samples(section, F, signals(section), reference(section), 35e-6))
    return section, mesh, result


def test_independent_tapered_ground_face_currents_and_power(enclosed):
    skfem = require_tool('scikit-fem')
    from skfem.helpers import dot, grad
    section, mesh, _ = enclosed; clock = Stopwatch()
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
        values = np.array(fields).T; c0 = epsilon_0*values.T@(k@values)
        gradients = np.stack([basis.interpolate(v).grad[:, :, 0].T for v in fields], axis=-1)
        all_edges = mesh.mesh.triangles[:, [[0, 1], [1, 2], [2, 0]]].reshape(-1, 2)
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
        for trace, side in zip([t for t in section.traces if t.ground], [mid[:, 0] < 0, mid[:, 0] > 0]):
            selected = interior & side
            width = trace.width+(trace.top_width-trace.width)*(mid[:, 1]-trace.y)/trace.thickness
            masks.extend([selected & np.isclose(mid[:, 1], trace.y, rtol=0, atol=1e-12),
                          selected & np.isclose(mid[:, 1], trace.y1, rtol=0, atol=1e-12),
                          selected & np.isclose(mid[:, 0], trace.x-width/2, rtol=0, atol=1e-12),
                          selected & np.isclose(mid[:, 0], trace.x+width/2, rtol=0, atol=1e-12)])
        assert np.array_equal(np.sum(masks, axis=0), ground.astype(int))
        q = np.array([currents[m].T@(lengths[m, None]*currents[m]) for m in masks])
        integrated = np.array([np.sum(lengths[m, None]*currents[m], axis=0) for m in masks])
    error = float(np.max(abs(q-actual.factors.parts[8:]))/np.max(abs(q)))
    flux = float(np.max(abs(integrated-actual.factors.current_integrals[8:])))
    record = make_record(case='ground-trace-face-currents', physics='PEC surface perturbation',
        api='sipi.face_conductor.ReferenceSurfaceMetals', discretization='one vacuum extraction; tapered ground faces',
        tool='scikit-fem', tool_discretization='independent P1 solve and midpoint face classification',
        matched=['same mesh, two signals, three plane/wall groups and two tapered grounds',
                 'same unit-current normalization; independent ground-face grouping'],
        not_matched=['finite-metal diffusion, coating thickness or measured foil loss'],
        observables=[observable('ground-face current products', '1/m', 'max normalized matrix difference', error, 1e-10),
                     observable('ground-face integrated current', '1', 'max absolute difference', flux, 1e-10)],
        analytical_acceptance='wide opposing ground foil Q and weighted R, unchanged whole-trace reduction and mesh/box gates',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi', version=metadata.version('sipi')); emit(record)
    assert error < 1e-10 and flux < 1e-10


def test_uniform_face_expansion_reduces_to_whole_traces_and_preserves_partitions(enclosed):
    section, mesh, _ = enclosed
    expanded = _face_from_mesh(mesh, *_face_samples(section, F, signals(section), reference(section, uniform=True), 35e-6))
    whole = _face_from_mesh(mesh, *_face_samples(section, F, signals(section), reference(section, whole=True), 35e-6))
    for key in ('R', 'L_internal'):
        np.testing.assert_allclose(getattr(expanded, key), getattr(whole, key), rtol=1e-12)
    np.testing.assert_array_equal(expanded.factors.C0, whole.factors.C0)
    assert whole.factors.reference_labels == ('reference:bottom', 'reference:top', 'reference:sides',
                                             'reference:ground:guardL', 'reference:ground:guardR')
    assert expanded.factors.reference_labels == whole.factors.reference_labels[:3]+tuple(
        'reference:ground:'+name+':'+face for name in ('guardL', 'guardR') for face in FACES)
    for key in ('parts', 'current_integrals'):
        a, b = getattr(expanded.factors, key), getattr(whole.factors, key)
        np.testing.assert_array_equal(a[:11], b[:11])
        np.testing.assert_allclose(a[11:15].sum(axis=0), b[11], rtol=1e-12, atol=1e-12)
        np.testing.assert_allclose(a[15:19].sum(axis=0), b[12], rtol=1e-12, atol=1e-12)
        np.testing.assert_allclose(a[8:].sum(axis=0), getattr(expanded.factors.base, key)[-1], rtol=1e-12, atol=1e-12)


def test_distinct_faces_retain_laws_power_and_passive_network(enclosed):
    _, mesh, result = enclosed
    labels = result.boundary_labels
    for face, factor in [('bottom', 1.), ('top', 2.)]:
        index = labels.index('reference:ground:guardL:'+face)
        expected = factor*(1+1j)*np.sqrt(np.pi*F*mu_0/58e6)
        np.testing.assert_allclose(result.surface_impedance[:, index], expected, rtol=1e-12)
    rough = labels.index('reference:ground:guardL:right')
    delta = np.sqrt(1/(np.pi*F*mu_0*58e6))
    expected = (1+1j)*np.sqrt(np.pi*F*mu_0/58e6)*result.metals[rough].roughness.factor(delta)
    np.testing.assert_allclose(result.surface_impedance[:, rough], expected, rtol=1e-12)
    np.testing.assert_allclose(result.resistance_parts.sum(axis=1), result.R, rtol=1e-12)
    for value in (result.R, result.L_internal, result.factors.parts):
        np.testing.assert_allclose(value, value.swapaxes(-1, -2), atol=1e-10)
        assert np.linalg.eigvalsh(value).min() > -1e-10
    dielectric = mesh.line_parameters()
    network = result.network(C=dielectric.C, G=np.zeros((2, 2)), length=.02)
    np.testing.assert_allclose(network.s, network.s.swapaxes(1, 2), atol=1e-10)
    assert np.linalg.svd(network.s, compute_uv=False).max() <= 1+1e-10
    assert not result.factors.parts.flags.writeable and not result.R.flags.writeable
    assert result.factors.current_error < .05


def test_mixed_whole_and_face_grounds_and_mapping_snapshot(enclosed):
    section, mesh, _ = enclosed
    mapping = {'guardL': TraceFaceMetals.uniform(METAL), 'guardR': METAL}
    ref = ReferenceSurfaceMetals(METAL, METAL, METAL, mapping); mapping.clear()
    with pytest.raises(TypeError): ref.conductors['guardR'] = TraceFaceMetals.uniform(METAL)
    result = _face_from_mesh(mesh, *_face_samples(section, F, signals(section), ref, 35e-6))
    assert result.factors.reference_labels[-5:] == tuple('reference:ground:guardL:'+face for face in FACES)+('reference:ground:guardR',)
    whole = _face_from_mesh(mesh, *_face_samples(section, F, signals(section), reference(section, whole=True), 35e-6))
    np.testing.assert_allclose(result.R, whole.R, rtol=1e-12)


def test_one_shared_current_extraction_for_all_faces(monkeypatch):
    import sipi.face_conductor as module
    count = []; original = module._surface_current_data
    def recorded(*args): count.append(1); return original(*args)
    monkeypatch.setattr(module, '_surface_current_data', recorded)
    solve(boxed_pair(), **COARSE)
    assert len(count) == 1  # One extraction still has one voltage solution per signal.


@pytest.mark.parametrize('case', ['thin', 'polygon', 'bad_face', 'skin_bottom', 'skin_top',
    'skin_left', 'skin_right', 'missing', 'extra', 'collision', 'dc'])
def test_invalid_face_assignment_and_depth_reject_before_mesh(monkeypatch, case):
    s = boxed_pair(); ref = reference(s); frequency = F
    def forbidden(*args, **kwargs): pytest.fail('invalid ground-face input reached meshing')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    with pytest.raises((ValueError, TypeError)):
        if case == 'thin':
            ground = replace(s.traces[-1], thickness=0., top_width=None)
            s = CrossSection(s.layers, [*s.traces[:-1], ground], s.width, top='ground', sides='ground')
        if case == 'polygon':
            ground = PolygonTrace('guardR', [(1.8e-3, .5e-3), (2.2e-3, .5e-3),
                                  (2.25e-3, .55e-3), (1.75e-3, .55e-3)], ground=True)
            s = CrossSection(s.layers, [*s.traces[:-1], ground], s.width, top='ground', sides='ground')
        if case == 'bad_face': ref = replace(ref, conductors={**ref.conductors, 'guardR': {'bottom': METAL}})
        if case.startswith('skin_'):
            faces = replace(ref.conductors['guardR'], **{case[5:]: SurfaceMetal(1e4)})
            ref = replace(ref, conductors={**ref.conductors, 'guardR': faces})
        if case == 'missing': ref = replace(ref, conductors={'guardL': ref.conductors['guardL']})
        if case == 'extra': ref = replace(ref, conductors={**ref.conductors, 'unused': METAL})
        if case == 'collision':
            s = CrossSection(s.layers, [*s.traces[:-1], replace(s.traces[-1], name='guardL:bottom')],
                             s.width, top='ground', sides='ground')
            ref = replace(ref, conductors={'guardL': TraceFaceMetals.uniform(METAL), 'guardL:bottom': METAL})
        if case == 'dc': frequency = [0.]
        surface_conductor_loss_by_face(s, frequency, conductors=signals(s), reference=ref,
                                       ground_thickness=35e-6)


def test_ground_face_resistance_mesh_and_outer_convergence():
    # Open outer sides isolate domain truncation from the physical side-ground widths.
    def section(width):
        base = boxed_pair(width)
        return CrossSection(base.layers, base.traces, width, top='ground', sides='open')
    # The 5 -> 2.5 um edge meshes changed R by 6.78%, failing the 5% gate.
    # Keep the physical case and gate; refine every mesh control once more.
    refined = {key: value/2 for key, value in FINE.items()}
    coarse = solve(section(6e-3), **FINE)
    fine = solve(section(6e-3), **refined)
    outer = solve(section(12e-3), **refined)
    changes = [float(np.max(abs(v.R-fine.R))/np.max(abs(fine.R))) for v in (coarse, outer)]
    print('ground face R mesh/box changes', changes)
    assert max(changes) < .05
    assert max(v.factors.current_error for v in (coarse, fine, outer)) < .05


def test_saved_line5_does_not_silently_accept_new_ground_face_records(monkeypatch):
    from sipi import CrossSectionDocument
    from sipi.dielectric import ConstantDielectric
    from sipi.line_model import TransmissionLineDocument
    section = boxed_pair()
    metal = dict(conductivity=58e6, relative_permeability=1., roughness=dict(kind='smooth'))
    faces = {face: metal for face in FACES}
    ref = dict(kind='surfaces', bottom=metal, top=metal, sides=metal,
               conductors={'guardL': metal, 'guardR': metal})
    conductor = dict(kind='surface-faces', conductors={name: faces for name in signals(section)},
                     reference=ref, ground_thickness=35e-6)
    def forbidden(*args, **kwargs): pytest.fail('saved input parsing reached meshing')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    def document():
        return TransmissionLineDocument(CrossSectionDocument(section, mesh=COARSE), F,
            materials={layer.name: ConstantDielectric(layer.eps_r) for layer in section.layers},
            conductor=conductor, length=.02, schema='sipi.transmission-line/5')
    old = document()
    assert TransmissionLineDocument.loads(old.dumps()).dumps() == old.dumps()
    ref['conductors']['guardL'] = dict(kind='faces', **faces)
    with pytest.raises(ValueError): document()


def test_wide_opposing_ground_foil_faces_and_weighted_resistance():
    w, t, gap, y = .02, 35e-6, .1e-3, .4e-3
    s = CrossSection([Layer('d', 2*y+3*t+2*gap, 4.)],
        [Trace('signal', 0., w, y+t+gap, t), Trace('lower', 0., w, y, t, ground=True),
         Trace('upper', 0., w, y+2*t+2*gap, t, ground=True)], .028, bottom='open', top='open')
    lower = replace(TraceFaceMetals.uniform(METAL), top=SurfaceMetal(58e6/4))
    upper = replace(TraceFaceMetals.uniform(METAL), bottom=SurfaceMetal(58e6/9))
    ref = ReferenceSurfaceMetals(None, None, None, {'lower': lower, 'upper': upper})
    values = [solve(s, ref, **opts) for opts in [dict(edge_size=8e-6, far_size=.4e-3, grade=.2),
                                               dict(edge_size=4e-6, far_size=.2e-3, grade=.1)]]
    fine = values[-1]
    indexes = [fine.boundary_labels.index(label) for label in
        ['signal:signal:bottom', 'signal:signal:top', 'reference:ground:lower:top', 'reference:ground:upper:bottom']]
    np.testing.assert_allclose(fine.factors.parts[indexes, 0, 0], 1/(4*w), rtol=.05)
    np.testing.assert_allclose(fine.factors.current_integrals[indexes[-2:], 0], -.5, rtol=.05)
    expected = 7/(4*w)*np.sqrt(np.pi*F*mu_0/58e6)
    np.testing.assert_allclose(fine.R[:, 0, 0], expected, rtol=.05)
    np.testing.assert_allclose(fine.L_internal[:, 0, 0], expected/(2*np.pi*F), rtol=.05)
    assert np.max(abs(values[0].R/fine.R-1)) < .05
    assert max(v.factors.current_error for v in values) < .05
    print('ground foil Q', fine.factors.parts[indexes, 0, 0], 'weighted R error', np.max(abs(fine.R[:, 0, 0]/expected-1)))
