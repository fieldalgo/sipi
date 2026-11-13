# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Geometric face conventions and independently assembled broadside fields."""
import numpy as np
import pytest
from sipi import (CrossSectionDocument, asymmetric_layered_broadside_stripline,
                  tapered_layered_broadside_stripline)
from test_asymmetric_broadside import (
    PARAMS as RECTANGULAR, COARSE, FINE,
    test_independent_height_material_mask_complex_and_vacuum as _independent_field,
    test_vacuum_uniform_material_and_external_inductance_invariants as _uniform,
)

PARAMS = dict(RECTANGULAR, lower_top_width=.32e-3, upper_top_width=.55e-3)


def section(**changes):
    return tapered_layered_broadside_stripline(**dict(PARAMS, **changes))


@pytest.mark.parametrize('tops', [(.32e-3, .55e-3), (.48e-3, .85e-3)])
def test_geometric_top_faces_clearances_and_document(tops):
    s = section(lower_top_width=tops[0], upper_top_width=tops[1])
    low, high = s.traces
    np.testing.assert_allclose(low.corners(), [
        [-.275e-3, .35e-3], [.125e-3, .35e-3],
        [-.075e-3+tops[0]/2, .375e-3], [-.075e-3-tops[0]/2, .375e-3]],
        rtol=1e-14, atol=1e-18)
    np.testing.assert_allclose(high.corners(), [
        [-.275e-3, .625e-3], [.425e-3, .625e-3],
        [.075e-3+tops[1]/2, .67e-3], [.075e-3-tops[1]/2, .67e-3]],
        rtol=1e-14, atol=1e-18)
    assert (low.name, high.name) == ('positive', 'negative')
    assert high.y-low.y1 == pytest.approx(.25e-3, rel=1e-12)
    assert s.height-high.y1 == pytest.approx(.55e-3, rel=1e-12)
    assert s.top == s.bottom == 'ground' and s.sides == 'open'
    assert [(l.eps_r, l.tan_delta) for l in s.layers] == [(3., .01), (4., .02), (5., .03)]
    doc = CrossSectionDocument(s, mesh=COARSE)
    assert CrossSectionDocument.loads(doc.dumps()).dumps() == doc.dumps()


def test_default_box_includes_widest_top_face():
    s = section(upper_top_width=.02, box_width=None)
    assert s.width == 4*(.02+.15e-3)
    assert s.traces[1].xmax < s.width/2


@pytest.mark.parametrize('change', [
    dict(lower_top_width=0), dict(upper_top_width=-1), dict(lower_top_width=True),
    dict(upper_top_width=float('inf')), dict(lower_top_width=float('nan')),
    dict(upper_top_width='0.001'), dict(upper_top_width=None),
    dict(lower_width=0), dict(upper_thickness=0), dict(lower_thickness=0),
    dict(gap=0), dict(lower_height=0), dict(upper_height=-1),
    dict(offset=True), dict(lower_top_width=.1), dict(upper_top_width=.1),
    dict(gap_eps_r=.5), dict(upper_tan_delta=-1),
])
def test_invalid_or_clipped_copper_rejected(change):
    with pytest.raises((TypeError, ValueError)):
        section(**change)


@pytest.mark.parametrize('offset', [-.15e-3, 0., .15e-3])
@pytest.mark.parametrize('box', [None, .012])
def test_rectangular_limit_preserves_exact_geometry(offset, box):
    actual = section(lower_top_width=.4e-3, upper_top_width=.7e-3,
                     offset=offset, box_width=box)
    expected = asymmetric_layered_broadside_stripline(**dict(RECTANGULAR, offset=offset, box_width=box))
    assert CrossSectionDocument(actual).dumps() == CrossSectionDocument(expected).dumps()


@pytest.fixture(scope='module')
def fields():
    field = section().mesh(**COARSE)
    return field, field.line_parameters(), section().analyze(**FINE)


def test_independent_complex_and_vacuum_assembly(fields, record_property):
    # Same independently prescribed dielectric heights as the rectangular case;
    # the actual mesh and signal boundaries here belong to the trapezoids.
    _independent_field(fields, record_property)


def test_vacuum_uniform_and_external_inductance_invariants(fields):
    _uniform(fields)


def test_mesh_and_separate_outer_width_gates(fields, record_property):
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


def test_vertical_reflection_reverses_top_bottom_faces(fields, record_property):
    p = dict(PARAMS, offset=-PARAMS['offset'])
    for suffix in ('height', 'thickness', 'eps_r', 'tan_delta'):
        p['lower_'+suffix], p['upper_'+suffix] = PARAMS['upper_'+suffix], PARAMS['lower_'+suffix]
    p.update(lower_width=PARAMS['upper_top_width'], lower_top_width=PARAMS['upper_width'],
             upper_width=PARAMS['lower_top_width'], upper_top_width=PARAMS['lower_width'])
    original, mirrored = section(), section(**p)
    for a, b in zip(original.traces[::-1], mirrored.traces):
        expected = a.corners()[[3, 2, 1, 0]].copy()
        expected[:, 1] = original.height-expected[:, 1]
        np.testing.assert_allclose(b.corners(), expected, rtol=1e-12, atol=1e-18)
    actual, reference = mirrored.analyze(**FINE), fields[2]
    errors = {k: float(np.max(abs(getattr(actual, k)-getattr(reference, k)[::-1, ::-1])) /
                       np.max(abs(getattr(reference, k)))) for k in ('C', 'C_loss', 'C0')}
    record_property('vertical_reflection_relative_changes', str(errors))
    assert max(errors.values()) <= .005


def test_horizontal_reflection_keeps_forward_launch(fields, record_property):
    actual, reference = section(offset=-PARAMS['offset']).analyze(**FINE), fields[2]
    errors = {k: float(np.max(abs(getattr(actual, k)-getattr(reference, k))) /
                       np.max(abs(getattr(reference, k)))) for k in ('C', 'C_loss', 'C0')}
    errors['forward_z'] = abs(actual.z_diff_forward/reference.z_diff_forward-1)
    record_property('horizontal_reflection_relative_changes', str(errors))
    assert max(errors.values()) <= .005
