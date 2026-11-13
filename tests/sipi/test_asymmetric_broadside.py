# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Unequal broadside geometry, independent fields and explicit symmetry limits."""
from dataclasses import replace
import numpy as np
import pytest
from sipi import (CrossSectionDocument, asymmetric_layered_broadside_stripline,
                  layered_broadside_stripline)
from sipi.constants import epsilon_0, mu_0
from crosscheck import require_tool

PARAMS = dict(lower_width=.4e-3, upper_width=.7e-3, gap=.25e-3,
              lower_height=.35e-3, upper_height=.55e-3,
              lower_thickness=25e-6, upper_thickness=45e-6, offset=.15e-3,
              lower_eps_r=3., gap_eps_r=4., upper_eps_r=5.,
              lower_tan_delta=.01, gap_tan_delta=.02, upper_tan_delta=.03,
              box_width=.012)
COARSE = dict(edge_size=5e-6, far_size=.15e-3, grade=.15)
FINE = {k: v/2 for k, v in COARSE.items()}


def section(**changes):
    return asymmetric_layered_broadside_stripline(**dict(PARAMS, **changes))


def test_explicit_copper_clearances_layers_and_geometry_json():
    s = section()
    low, high = s.traces
    assert (low.name, high.name) == ('positive', 'negative')
    assert (low.x, high.x) == (-.15e-3/2, .15e-3/2)
    assert (low.width, high.width) == (.4e-3, .7e-3)
    assert (low.thickness, high.thickness) == (25e-6, 45e-6)
    assert low.y == .35e-3
    assert high.y-low.y1 == pytest.approx(.25e-3, rel=1e-12)
    assert s.height-high.y1 == pytest.approx(.55e-3, rel=1e-12)
    assert [(v.name, v.thickness, v.eps_r, v.tan_delta) for v in s.layers] == [
        ('lower', .35e-3+25e-6, 3., .01), ('gap', .25e-3, 4., .02),
        ('upper', .55e-3+45e-6, 5., .03)]
    assert s.bottom == s.top == 'ground' and s.sides == 'open'
    assert all(t.top_width is None and not t.ground for t in s.traces)
    doc = CrossSectionDocument(s, mesh=COARSE)
    assert CrossSectionDocument.loads(doc.dumps()).dumps() == doc.dumps()
    default = section(box_width=None)
    assert default.width == pytest.approx(max(12*s.height, 4*(.7e-3+.15e-3)), rel=1e-15)


@pytest.mark.parametrize('change', [
    dict(lower_width=0), dict(upper_width=-1), dict(lower_width=True),
    dict(lower_thickness=0), dict(upper_thickness=0), dict(lower_thickness=float('nan')),
    dict(lower_height=0), dict(upper_height=-1), dict(gap=0),
    dict(lower_eps_r=.5), dict(gap_eps_r=.5), dict(upper_eps_r=.5),
    dict(lower_tan_delta=-1), dict(gap_tan_delta=-1), dict(upper_tan_delta=-1),
    dict(offset=True), dict(offset=float('inf')), dict(offset='0'),
    dict(box_width=.1e-3), dict(offset=.1), dict(box_width=0),
])
def test_invalid_geometry_materials_and_clipped_copper(change):
    with pytest.raises((TypeError, ValueError)):
        section(**change)


@pytest.mark.parametrize('offset', [-.15e-3, 0., .15e-3])
@pytest.mark.parametrize('box', [None, .012])
def test_equal_width_and_thickness_reduces_to_original_factory_exactly(offset, box):
    p = dict(PARAMS, lower_width=.5e-3, upper_width=.5e-3,
             lower_thickness=35e-6, upper_thickness=35e-6, offset=offset, box_width=box)
    candidate = asymmetric_layered_broadside_stripline(**p)
    old = {k: v for k, v in p.items() if k not in (
        'lower_width', 'upper_width', 'lower_thickness', 'upper_thickness')}
    original = layered_broadside_stripline(width=.5e-3, thickness=35e-6, **old)
    assert CrossSectionDocument(candidate).dumps() == CrossSectionDocument(original).dumps()


@pytest.fixture(scope='module')
def fields():
    field = section().mesh(**COARSE)
    return field, field.line_parameters(), section().analyze(**FINE)


def test_independent_height_material_mask_complex_and_vacuum(fields, record_property):
    field, line, _ = fields
    sk = require_tool('scikit-fem')
    from skfem.helpers import dot, grad
    basis = sk.Basis(sk.MeshTri(field.mesh.nodes.T, field.mesh.triangles.T), sk.ElementTriP1())
    @sk.BilinearForm(dtype=complex)
    def form(u, v, w):
        return w.eps*dot(grad(u), grad(v))
    y = field.mesh.nodes[field.mesh.triangles].mean(axis=1)[:, 1]
    eps = np.where(y < .35e-3+25e-6, 3*(1-.01j),
                   np.where(y < .35e-3+25e-6+.25e-3, 4*(1-.02j), 5*(1-.03j)))
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


def test_requested_refined_and_separate_outer_gates(fields, record_property):
    _, coarse, fine = fields
    outer = section(box_width=.024).analyze(**FINE)
    changes = {}
    for name, other, gate in [('mesh', coarse, .01), ('box', outer, .005)]:
        changes[name] = max(float(np.max(abs(other.C-fine.C))/np.max(abs(fine.C))),
                            abs(other.z_diff_forward/fine.z_diff_forward-1))
        assert changes[name] <= gate, (name, changes[name])
    record_property('mesh_outer_relative_changes', str(changes))
    for matrix in (fine.C, fine.C0, fine.C_loss, fine.L):
        np.testing.assert_allclose(matrix, matrix.T, rtol=1e-12, atol=0)
        assert np.linalg.eigvalsh(matrix).min() > 0
    with pytest.raises(ValueError):
        fine.even_odd()


def test_vacuum_uniform_material_and_external_inductance_invariants(fields):
    field, _, _ = fields
    vacuum = replace(field, eps_r=np.ones_like(field.eps_r), tan_delta=np.zeros_like(field.tan_delta)).line_parameters()
    np.testing.assert_array_equal(vacuum.C, vacuum.C0)
    np.testing.assert_array_equal(vacuum.C_loss, np.zeros_like(vacuum.C))
    uniform = replace(field, eps_r=np.full_like(field.eps_r, 4.), tan_delta=np.full_like(field.tan_delta, .02)).line_parameters()
    np.testing.assert_allclose(uniform.C, 4*uniform.C0, rtol=1e-13, atol=0)
    np.testing.assert_allclose(uniform.C_loss, .02*uniform.C, rtol=1e-13, atol=0)
    np.testing.assert_allclose(uniform.C0@uniform.L, epsilon_0*mu_0*np.eye(2), rtol=1e-12, atol=1e-30)


def reflected_parameters():
    p = dict(PARAMS, offset=-PARAMS['offset'])
    for suffix in ('width', 'height', 'thickness', 'eps_r', 'tan_delta'):
        p['lower_'+suffix], p['upper_'+suffix] = PARAMS['upper_'+suffix], PARAMS['lower_'+suffix]
    return p


def test_vertical_reflection_swaps_materials_geometry_and_signal_order(fields, record_property):
    original = section()
    reflected = asymmetric_layered_broadside_stripline(**reflected_parameters())
    for a, b in zip(original.traces[::-1], reflected.traces):
        np.testing.assert_allclose([b.x, b.width, b.y, b.thickness],
                                   [a.x, a.width, original.height-a.y1, a.thickness], rtol=1e-12, atol=1e-18)
    assert [(l.eps_r, l.tan_delta) for l in reflected.layers] == [(l.eps_r, l.tan_delta) for l in original.layers[::-1]]
    actual, reference = reflected.analyze(**FINE), fields[2]
    changes = {key: float(np.max(abs(getattr(actual, key)-getattr(reference, key)[::-1, ::-1])) /
                          np.max(abs(getattr(reference, key)))) for key in ('C', 'C_loss', 'C0')}
    record_property('vertical_reflection_relative_changes', str(changes))
    assert max(changes.values()) <= .005


def test_horizontal_reflection_preserves_matrix_and_forward_launch(fields, record_property):
    actual, reference = section(offset=-PARAMS['offset']).analyze(**FINE), fields[2]
    changes = {key: float(np.max(abs(getattr(actual, key)-getattr(reference, key))) /
                          np.max(abs(getattr(reference, key)))) for key in ('C', 'C_loss', 'C0')}
    changes['forward_z'] = abs(actual.z_diff_forward/reference.z_diff_forward-1)
    record_property('horizontal_reflection_relative_changes', str(changes))
    assert max(changes.values()) <= .005
