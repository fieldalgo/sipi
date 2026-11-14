# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit gap interface, independent four-material fields and refinement."""
from dataclasses import replace
import numpy as np
import pytest
from sipi import CrossSectionDocument, split_gap_broadside_stripline, tapered_layered_broadside_stripline
from sipi.constants import epsilon_0, mu_0
from crosscheck import require_tool

PARAMS = dict(lower_width=.4e-3, upper_width=.7e-3,
              lower_top_width=.32e-3, upper_top_width=.55e-3,
              lower_thickness=25e-6, upper_thickness=45e-6,
              lower_height=.35e-3, upper_height=.55e-3, gap=.25e-3,
              gap_lower_height=.1e-3, offset=.15e-3,
              lower_eps_r=3., gap_lower_eps_r=3.2, gap_upper_eps_r=4.6, upper_eps_r=5.,
              lower_tan_delta=.01, gap_lower_tan_delta=.015,
              gap_upper_tan_delta=.025, upper_tan_delta=.03, box_width=.012)
COARSE = dict(edge_size=5e-6, far_size=.25e-3, grade=.2)
FINE = {k: v/2 for k, v in COARSE.items()}


def section(**changes):
    return split_gap_broadside_stripline(**dict(PARAMS, **changes))


def test_interface_location_and_copper_faces_survive_geometry_json():
    s = section()
    low, high = s.traces
    np.testing.assert_allclose([low.y, low.y1, high.y, high.y1, s.height],
                              [.35e-3, .375e-3, .625e-3, .67e-3, 1.22e-3], rtol=1e-14)
    np.testing.assert_allclose(np.cumsum([l.thickness for l in s.layers]),
                              [.375e-3, .475e-3, .625e-3, 1.22e-3], rtol=1e-14)
    assert [l.name for l in s.layers] == ['lower', 'gap_lower', 'gap_upper', 'upper']
    assert [(l.eps_r, l.tan_delta) for l in s.layers] == [(3., .01), (3.2, .015), (4.6, .025), (5., .03)]
    assert [(t.width, t.top_width) for t in s.traces] == [(.4e-3, .32e-3), (.7e-3, .55e-3)]
    assert s.bottom == s.top == 'ground' and s.sides == 'open'
    doc = CrossSectionDocument(s, mesh=COARSE)
    assert CrossSectionDocument.loads(doc.dumps()).dumps() == doc.dumps()


@pytest.mark.parametrize('change', [
    dict(gap_lower_height=0), dict(gap_lower_height=.25e-3), dict(gap_lower_height=.3e-3),
    dict(gap_lower_height=True), dict(gap_lower_height='0.0001'),
    dict(gap_lower_height=float('nan')), dict(gap_lower_height=float('inf')),
    dict(gap=0), dict(gap=-1), dict(gap_lower_eps_r=.5), dict(gap_upper_eps_r=.5),
    dict(gap_upper_eps_r=True), dict(gap_lower_tan_delta=-1), dict(gap_upper_tan_delta=-1),
    dict(gap_upper_tan_delta=float('nan')), dict(lower_thickness=0), dict(upper_thickness=0),
    dict(lower_top_width=0), dict(upper_top_width=.1), dict(offset=.1), dict(box_width=.1e-3),
])
def test_invalid_interface_material_and_copper_rejected(change):
    with pytest.raises((ValueError, TypeError)):
        section(**change)


@pytest.mark.parametrize('split', [.025e-3, .1e-3, .225e-3])
def test_moving_interface_preserves_metal_and_total_height(split):
    actual, base = section(gap_lower_height=split), section()
    assert actual.traces == base.traces and actual.width == base.width
    assert actual.height == pytest.approx(base.height, rel=1e-15)
    assert actual.layers[1].thickness == split
    assert actual.layers[2].thickness == PARAMS['gap']-split


@pytest.fixture(scope='module')
def fields():
    field = section().mesh(**COARSE)
    return field, field.line_parameters(), section().analyze(**FINE)


def test_independent_four_height_regions_complex_and_vacuum(fields, record_property):
    field, line, _ = fields
    sk = require_tool('scikit-fem')
    from skfem.helpers import dot, grad
    basis = sk.Basis(sk.MeshTri(field.mesh.nodes.T, field.mesh.triangles.T), sk.ElementTriP1())
    @sk.BilinearForm(dtype=complex)
    def form(u, v, w):
        return w.eps*dot(grad(u), grad(v))
    y = field.mesh.nodes[field.mesh.triangles].mean(axis=1)[:, 1]
    eps = np.select([y < .375e-3, y < .475e-3, y < .625e-3],
                    [3*(1-.01j), 3.2*(1-.015j), 4.6*(1-.025j)], 5*(1-.03j))
    # Check material assignment against independently prescribed physical heights.
    np.testing.assert_array_equal(field.eps_r, eps.real)
    np.testing.assert_allclose(field.tan_delta, -eps.imag/eps.real, rtol=1e-15)
    fixed = np.unique(np.concatenate([field.ground, *field.signals.values()]))
    matrices = []
    for coeff in (eps, np.ones_like(eps)):
        k = sk.asm(form, basis, eps=coeff[:, None])
        columns = []
        for nodes in field.signals.values():
            v = np.zeros(basis.N, complex)
            v[nodes] = 1.
            columns.append(sk.solve(*sk.condense(k, np.zeros(basis.N, complex), x=v, D=fixed)))
        u = np.array(columns).T
        matrices.append(epsilon_0*(u.T@(k@u)))
    errors = [float(np.max(abs(a-b))/np.max(abs(b))) for a, b in (
        (line.C, matrices[0].real), (line.C_loss, -matrices[0].imag), (line.C0, matrices[1].real))]
    record_property('independent_normalized_errors', str(errors))
    assert max(errors) <= 1e-10


def test_separate_mesh_and_box_gates(fields, record_property):
    _, coarse, fine = fields
    outer = section(box_width=.024).analyze(**FINE)
    errors = {}
    for name, other, gate in [('mesh', coarse, .01), ('box', outer, .005)]:
        errors[name] = max(float(np.max(abs(other.C-fine.C))/np.max(abs(fine.C))),
                           abs(other.z_diff_forward/fine.z_diff_forward-1))
        assert errors[name] <= gate
    record_property('mesh_outer_relative_changes', str(errors))
    for key in ('C', 'C0', 'C_loss', 'L'):
        m = getattr(fine, key)
        np.testing.assert_allclose(m, m.T, rtol=1e-12, atol=0)
        assert np.linalg.eigvalsh(m).min() > 0
    with pytest.raises(ValueError):
        fine.even_odd()


def test_uniform_and_vacuum_material_invariants(fields):
    field = fields[0]
    vacuum = replace(field, eps_r=np.ones_like(field.eps_r), tan_delta=np.zeros_like(field.tan_delta)).line_parameters()
    np.testing.assert_array_equal(vacuum.C, vacuum.C0)
    np.testing.assert_array_equal(vacuum.C_loss, np.zeros_like(vacuum.C))
    uniform = replace(field, eps_r=np.full_like(field.eps_r, 4.), tan_delta=np.full_like(field.tan_delta, .02)).line_parameters()
    np.testing.assert_allclose(uniform.C, 4*uniform.C0, rtol=1e-13, atol=0)
    np.testing.assert_allclose(uniform.C_loss, .02*uniform.C, rtol=1e-13, atol=0)
    np.testing.assert_allclose(uniform.C0@uniform.L, epsilon_0*mu_0*np.eye(2), rtol=1e-12, atol=1e-30)


def test_equal_gap_material_matches_three_layer_limit(record_property):
    p = {k: v for k, v in PARAMS.items() if not k.startswith('gap_')}
    p.update(gap_eps_r=4., gap_tan_delta=.02)
    original = tapered_layered_broadside_stripline(**p).analyze(**FINE)
    split = section(gap_lower_eps_r=4., gap_upper_eps_r=4.,
                    gap_lower_tan_delta=.02, gap_upper_tan_delta=.02).analyze(**FINE)
    errors = {k: float(np.max(abs(getattr(split, k)-getattr(original, k))) /
                      np.max(abs(getattr(original, k)))) for k in ('C', 'C_loss', 'C0')}
    record_property('equal_material_limit', str(errors))
    assert max(errors.values()) <= .005


def test_vertical_reflection_swaps_gap_materials_and_copper_faces(fields, record_property):
    p = dict(PARAMS, offset=-PARAMS['offset'], gap_lower_height=PARAMS['gap']-PARAMS['gap_lower_height'])
    for suffix in ('height', 'thickness', 'eps_r', 'tan_delta'):
        p['lower_'+suffix], p['upper_'+suffix] = PARAMS['upper_'+suffix], PARAMS['lower_'+suffix]
    for suffix in ('eps_r', 'tan_delta'):
        p['gap_lower_'+suffix], p['gap_upper_'+suffix] = PARAMS['gap_upper_'+suffix], PARAMS['gap_lower_'+suffix]
    p.update(lower_width=PARAMS['upper_top_width'], lower_top_width=PARAMS['upper_width'],
             upper_width=PARAMS['lower_top_width'], upper_top_width=PARAMS['lower_width'])
    actual, reference = section(**p).analyze(**FINE), fields[2]
    errors = {k: float(np.max(abs(getattr(actual, k)-getattr(reference, k)[::-1, ::-1])) /
                      np.max(abs(getattr(reference, k)))) for k in ('C', 'C_loss', 'C0')}
    record_property('vertical_reflection', str(errors))
    assert max(errors.values()) <= .005


def test_horizontal_reflection(fields, record_property):
    actual, reference = section(offset=-PARAMS['offset']).analyze(**FINE), fields[2]
    errors = {k: float(np.max(abs(getattr(actual, k)-getattr(reference, k))) /
                      np.max(abs(getattr(reference, k)))) for k in ('C', 'C_loss', 'C0')}
    errors['forward_z'] = abs(actual.z_diff_forward/reference.z_diff_forward-1)
    record_property('horizontal_reflection', str(errors))
    assert max(errors.values()) <= .005
