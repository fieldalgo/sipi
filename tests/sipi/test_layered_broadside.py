# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Three-layer broadside geometry, independent fields and saved workflows."""
from dataclasses import replace
from importlib import metadata
import json

import numpy as np
import pytest

from sipi import (CrossSection, CrossSectionDocument, Layer, Trace, layered_broadside_stripline,
                  ImpedanceDesignDocument)
from sipi.templates import broadside_stripline
from sipi.constants import epsilon_0, mu_0
from sipi.study import ImpedanceStudyDocument
from sipi.dielectric import ConstantDielectric
from sipi.execution import execute_saved, normalize_saved
from sipi.yield_assessment import ImpedanceYieldDocument
from crosscheck import require_tool, Stopwatch, make_record, observable, emit

PARAMS = dict(width=.35e-3, gap=.15e-3, lower_height=.25e-3, upper_height=.45e-3,
    lower_eps_r=3., gap_eps_r=4., upper_eps_r=5., thickness=35e-6, offset=.12e-3,
    lower_tan_delta=.01, gap_tan_delta=.02, upper_tan_delta=.03, box_width=6e-3)
COARSE = dict(edge_size=8e-6, far_size=.25e-3, grade=.3)
FINE = dict(edge_size=2e-6, far_size=.125e-3, grade=.15)


def section(**changes):
    return layered_broadside_stripline(**dict(PARAMS, **changes))


def study(**changes):
    kwargs = dict(quantity='z_diff_forward', mesh=COARSE,
        sampling=dict(kind='uniform', count=2, seed=17,
            variables=[dict(name='offset', lower=-.1e-3, upper=.1e-3)]))
    kwargs.update(changes)
    return ImpedanceStudyDocument('layered_broadside_stripline', PARAMS, **kwargs)


def test_three_layers_and_metal_faces_match_explicit_geometry():
    s = section(); a, b = s.traces
    np.testing.assert_allclose([layer.thickness for layer in s.layers], [.285e-3, .15e-3, .485e-3], rtol=1e-15)
    assert [layer.name for layer in s.layers] == ['lower', 'gap', 'upper']
    assert [layer.eps_r for layer in s.layers] == [3, 4, 5]
    assert a.y == PARAMS['lower_height']
    assert b.y-a.y1 == pytest.approx(PARAMS['gap'], rel=1e-15)
    assert s.height-b.y1 == pytest.approx(PARAMS['upper_height'], rel=1e-15)
    assert (a.x, b.x) == (-.06e-3, .06e-3)
    explicit = CrossSection([Layer('lower', .25e-3+35e-6, 3, .01), Layer('gap', .15e-3, 4, .02),
        Layer('upper', .45e-3+35e-6, 5, .03)],
        [Trace('positive', -.06e-3, .35e-3, .25e-3, 35e-6),
         Trace('negative', .06e-3, .35e-3, .25e-3+35e-6+.15e-3, 35e-6)], 6e-3, top='ground')
    doc = CrossSectionDocument(s, mesh=COARSE)
    assert doc.dumps() == CrossSectionDocument(explicit, mesh=COARSE).dumps()
    assert CrossSectionDocument.loads(doc.dumps()).dumps() == doc.dumps()
    default = section(box_width=None)
    assert default.width == pytest.approx(max(12*default.height, 4*(PARAMS['width']+abs(PARAMS['offset']))))


@pytest.mark.parametrize('change', [dict(width=0), dict(gap=0), dict(lower_height=0), dict(upper_height=-1),
    dict(thickness=0), dict(thickness=True), dict(lower_eps_r=.5), dict(gap_eps_r=float('nan')),
    dict(upper_eps_r=True), dict(lower_tan_delta=-.1), dict(gap_tan_delta=float('inf')),
    dict(upper_tan_delta=True), dict(offset=float('nan')), dict(offset=True), dict(box_width=.2e-3)])
def test_invalid_geometry_materials_and_box_reject(change):
    with pytest.raises(ValueError): section(**change)


@pytest.fixture(scope='module')
def fields():
    m = section().mesh(**COARSE)
    coarse = m.line_parameters()
    fine = section().analyze(**FINE)
    outer = section(box_width=12e-3).analyze(**FINE)
    return m, coarse, fine, outer


def test_independent_complex_and_vacuum_energy(fields):
    skfem = require_tool('scikit-fem')
    from skfem.helpers import dot, grad
    m, actual, _, _ = fields
    clock = Stopwatch()
    with clock('openphysics'):
        actual = m.line_parameters()
    with clock('reference'):
        basis = skfem.Basis(skfem.MeshTri(m.mesh.nodes.T, m.mesh.triangles.T), skfem.ElementTriP1())
        @skfem.BilinearForm(dtype=complex)
        def form(u, v, w): return w.eps*dot(grad(u), grad(v))
        fixed = np.unique(np.concatenate([m.ground, *m.signals.values()]))
        expected = []
        for eps in (m.eps_r*(1-1j*m.tan_delta), np.ones_like(m.eps_r)):
            k = skfem.asm(form, basis, eps=eps[:, None]); fields_ref = []
            for nodes in m.signals.values():
                v = np.zeros(basis.N, complex); v[nodes] = 1
                fields_ref.append(skfem.solve(*skfem.condense(k, np.zeros(basis.N, complex), x=v, D=fixed)))
            u = np.array(fields_ref).T
            expected.append(epsilon_0*(u.T@(k@u)))
    errors = [float(np.max(abs(a-b))/np.max(abs(b))) for a, b in
        [(actual.C, expected[0].real), (actual.C_loss, -expected[0].imag), (actual.C0, expected[1].real)]]
    record = make_record(case='layered-broadside-three-dielectrics', physics='lossy layered electrostatics',
        api='sipi.layered_broadside_stripline', discretization='conforming P1, finite rectangular pair and three layers',
        tool='scikit-fem', tool_discretization='independent complex/vacuum P1 assembly and Dirichlet energy',
        matched=['same mesh, named lower/gap/upper coefficients, grounded top/bottom and insulated sides'],
        not_matched=['no measured material model, three-dimensional transition or arbitrary-geometry convergence'],
        observables=[observable(name, 'F/m', 'max normalized matrix difference', error, 1e-10)
                     for name, error in zip(['C', 'C_loss', 'C0'], errors)],
        analytical_acceptance='parallel-plate limit, homogeneous reduction, mirror/scaling and separate mesh/box gates',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi', version=metadata.version('sipi')); emit(record)
    assert max(errors) < 1e-10


def test_mesh_outer_convergence_and_asymmetric_passive_matrices(fields):
    _, coarse, fine, outer = fields
    changes = []
    for a, bound in [(coarse, .015), (outer, .005)]:
        c = np.max(abs(a.C-fine.C))/np.max(abs(fine.C))
        z = abs(a.z_diff_forward/fine.z_diff_forward-1)
        changes.append([float(c), float(z)])
        assert max(c, z) < bound
    for matrix in (fine.C, fine.C0, fine.L, fine.C_loss):
        np.testing.assert_allclose(matrix, matrix.T, rtol=1e-12)
        assert np.linalg.eigvalsh(matrix).min() > 0
    with pytest.raises(ValueError): fine.even_odd()
    print('layered broadside mesh/outer C,Z changes', changes, 'fine forward ohm', fine.z_diff_forward)


def test_vertical_and_lateral_mirrors_preserve_forward_impedance(fields):
    _, _, original, _ = fields
    lateral = section(offset=-PARAMS['offset']).analyze(**FINE)
    vertical = section(lower_height=PARAMS['upper_height'], upper_height=PARAMS['lower_height'],
        lower_eps_r=PARAMS['upper_eps_r'], upper_eps_r=PARAMS['lower_eps_r'],
        lower_tan_delta=PARAMS['upper_tan_delta'], upper_tan_delta=PARAMS['lower_tan_delta'],
        offset=-PARAMS['offset']).analyze(**FINE)
    # Independently generated unstructured meshes are not exact reflected copies.
    for result, permutation in [(lateral, [0, 1]), (vertical, [1, 0])]:
        for attr in ('C', 'C_loss', 'C0', 'L'):
            expected = getattr(original, attr)[np.ix_(permutation, permutation)]
            np.testing.assert_allclose(getattr(result, attr), expected, rtol=.005)
        assert result.z_diff_forward == pytest.approx(original.z_diff_forward, rel=.005)


def test_uniform_material_scaling_and_constant_loss_on_identical_mesh(fields):
    m, _, _, _ = fields
    a = replace(m, eps_r=np.full_like(m.eps_r, 2.), tan_delta=np.full_like(m.tan_delta, .02)).line_parameters()
    b = replace(m, eps_r=np.full_like(m.eps_r, 8.), tan_delta=np.full_like(m.tan_delta, .02)).line_parameters()
    np.testing.assert_allclose(b.C, 4*a.C, rtol=1e-12)
    np.testing.assert_allclose(b.C_loss, .02*b.C, rtol=1e-12)
    np.testing.assert_array_equal(b.C0, a.C0)
    assert b.z_diff_forward == pytest.approx(a.z_diff_forward/2, rel=1e-12)


def test_homogeneous_symmetric_reduction_to_existing_broadside():
    p = dict(PARAMS, lower_height=.35e-3, upper_height=.35e-3,
             lower_eps_r=4., gap_eps_r=4., upper_eps_r=4.,
             lower_tan_delta=.02, gap_tan_delta=.02, upper_tan_delta=.02)
    new = layered_broadside_stripline(**p)
    old = broadside_stripline(width=p['width'], gap=p['gap'], plane_spacing=new.height,
        eps_r=4., thickness=p['thickness'], offset=p['offset'], tan_delta=.02, box_width=p['box_width'])
    np.testing.assert_allclose([[t.x, t.y, t.width, t.thickness] for t in new.traces],
                               [[t.x, t.y, t.width, t.thickness] for t in old.traces], rtol=1e-15)
    a, b = new.analyze(**FINE), old.analyze(**FINE)
    np.testing.assert_allclose(a.C, b.C, rtol=.005)
    assert a.z_diff_forward == pytest.approx(b.z_diff_forward, rel=.005)
    assert a.z_diff_forward == pytest.approx(a.even_odd()['z_diff'], rel=.005)


def test_wide_parallel_plate_limit_with_mesh_refinement():
    s = section(width=1e-3, gap=10e-6, lower_height=1e-3, upper_height=1e-3,
        lower_eps_r=2., upper_eps_r=2., gap_eps_r=4., offset=0,
        lower_tan_delta=0., gap_tan_delta=0., upper_tan_delta=0., box_width=8e-3)
    target_c = epsilon_0*4*1e-3/10e-6
    target_z = np.sqrt(mu_0/(epsilon_0*4))*10e-6/1e-3
    errors, values = [], []
    d = np.array([1., -1.])
    for mesh in [dict(edge_size=5e-6, far_size=.2e-3, grade=.3),
                 dict(edge_size=1e-6, far_size=.1e-3, grade=.15)]:
        line = s.analyze(**mesh)
        cap = float(d@line.C@d/4)
        values.append([cap, line.z_diff_forward])
        errors.append([abs(cap/target_c-1), abs(line.z_diff_forward/target_z-1)])
    assert max(errors[-1]) < .05
    assert max(abs(np.array(values[1])/values[0]-1)) < .015
    print('parallel plate C,Z targets', target_c, target_z, 'FEM', values, 'errors', errors)


def test_saved_random_study_yield_and_material_binding_replay():
    doc = study()
    assert normalize_saved(doc.dumps()) == doc.dumps()
    result = execute_saved(ImpedanceYieldDocument(doc, minimum=1., maximum=1000.).dumps(), max_evaluations=2)
    assert result['status'] == 'complete'
    assert result['result']['quantity'] == 'z_diff_forward' and result['result']['passed'] == 2
    for row in result['result']['rows']:
        direct = layered_broadside_stripline(**row['parameters']).analyze(**COARSE)
        assert row['impedance_ohm'] == pytest.approx(direct.z_diff_forward, rel=1e-12)
    material = study(frequency=1e9, materials={'gap': ConstantDielectric(4.)},
        material_variables={'dk': dict(region='gap', path=['eps_r'])},
        sampling=dict(kind='uniform', count=2, seed=18, variables=[dict(name='dk', lower=3.8, upper=4.2)]))
    out = execute_saved(material.dumps(), max_evaluations=2)
    assert out['status'] == 'complete'
    assert all('gap' in row['material_evaluation']['materials'] for row in out['result']['rows'])
    json.dumps(out, allow_nan=False)


def test_nonphysical_random_rows_and_inapplicable_symmetry_constraints_are_retained_or_rejected():
    for kwargs in [dict(quantity='z_diff'), dict(quantity='z0'), dict(fixed_pitch_m=.5e-3),
                   dict(fixed_plane_spacing_m=.7e-3)]:
        with pytest.raises(ValueError): study(**kwargs)
    invalid = study(sampling=dict(kind='normal', count=2, seed=18, correlation=[[1]],
        variables=[dict(name='gap', mean=-.1e-3, std=1e-9)]))
    result = invalid.analyze()
    assert result.failed == 2 and len(result.rows) == 2
    assert all(row.document is None and row.error_type == 'ValueError' for row in result.rows)


def test_saved_width_goal_keeps_asymmetric_forward_definition_and_refined_gate(fields):
    target = fields[2].z_diff_forward
    doc = ImpedanceDesignDocument('layered_broadside_stripline', PARAMS,
        variable='width', bounds=[.25e-3, .45e-3], target=target, quantity='z_diff_forward',
        tolerance=.2, max_evaluations=24, mesh=FINE)
    assert normalize_saved(doc.dumps()) == doc.dumps()
    result = doc.solve()
    assert abs(result.residual) <= .2 and abs(result.refined_residual) <= .2
    assert result.parameter == pytest.approx(PARAMS['width'], rel=.015)
    assert result.quantity == 'z_diff_forward'
