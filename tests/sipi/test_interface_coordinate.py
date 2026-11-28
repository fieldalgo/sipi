# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Trace faces within the mesher's merge distance of a layer boundary."""

import numpy as np
import pytest
from meshine import MeshInputError

from sipi import CrossSection, Layer, Trace
from sipi.polygons import DielectricRegion

H = 1e-3
OPTIONS = dict(edge_size=H / 50, far_size=2 * H)


def _microstrip(dy, thickness, extra=()):
    layers = [Layer("sub", H, 4.3), Layer("air", 20 * H)]
    return CrossSection(layers, [Trace("s", 0.0, H, H + dy, thickness), *extra], 40 * H)


def _arrays(meshed):
    lp = meshed.line_parameters()
    return (meshed.mesh.nodes, meshed.mesh.triangles, meshed.eps_r, meshed.ground,
            *meshed.signals.values(), lp.C, lp.L)


@pytest.mark.parametrize("thickness", [0.0, 35e-6], ids=["thin", "35um"])
@pytest.mark.parametrize("dy", [1e-18, -1e-18, 1e-13], ids=["above", "below", "1e-13"])
def test_face_within_merge_distance_meshes_on_boundary(dy, thickness):
    # These inputs used to stop with "zero-length edge". The bottom face is
    # placed on the boundary. A strip then matches the aligned line exactly;
    # a solid trace keeps its top face dy higher, which changes the refined
    # mesh, so it agrees only to discretization noise (measured 2-3e-5).
    exact = _microstrip(0.0, thickness).analyze(**OPTIONS)
    near = _microstrip(dy, thickness).analyze(**OPTIONS)
    if thickness == 0:
        assert near.z0 == exact.z0 and near.eps_eff == exact.eps_eff
    else:
        assert near.z0 == pytest.approx(exact.z0, rel=1e-4)
        assert near.eps_eff == pytest.approx(exact.eps_eff, rel=1e-4)


def test_tapered_section_thin_strip_near_boundary():
    tapered = Trace("t", 3 * H, H, H, 35e-6, top_width=0.8 * H)
    exact = _microstrip(0.0, 0.0, [tapered]).analyze(**OPTIONS)
    near = _microstrip(1e-18, 0.0, [tapered]).analyze(**OPTIONS)
    np.testing.assert_allclose(near.C, exact.C, rtol=1e-9)


@pytest.mark.parametrize("case", ["thin", "35um", "tapered"])
def test_meshable_inputs_are_bit_identical(case, monkeypatch):
    # A face that already meshes is never moved: replacing the rule with the
    # identity reproduces every array bit for bit.
    extra = [Trace("t", 3 * H, H, H, 35e-6, top_width=0.8 * H)] if case == "tapered" else []
    section = _microstrip(0.0, 35e-6 if case == "35um" else 0.0, extra)
    ruled = _arrays(section.mesh(**OPTIONS))
    monkeypatch.setattr(CrossSection, "_face_y", lambda self, y: y)
    plain = _arrays(section.mesh(**OPTIONS))
    assert len(ruled) == len(plain)
    for a, b in zip(ruled, plain):
        np.testing.assert_array_equal(a, b)


def test_two_trace_coordinates_closer_than_merge_distance_explain_the_fix():
    layers = [Layer("sub", H, 4.3), Layer("air", 20 * H)]
    section = CrossSection(layers, [Trace("s", 0.0, H, 1.5 * H, 0.0),
                                    Trace("t", 3 * H, H, 1.5 * H + 1e-18, 0.0)], 40 * H)
    with pytest.raises(MeshInputError, match=r"zero-length edge.*trace 's' .*trace 't' .*"
                                             r"differ by 1\.08e-18 m.*exactly equal"):
        section.mesh(**OPTIONS)


def test_polygonal_section_names_the_boundary_and_fix():
    region = DielectricRegion("r", ((5 * H, 0.2 * H), (6 * H, 0.2 * H),
                                    (6 * H, 0.5 * H), (5 * H, 0.5 * H)), 3.0)
    layers = [Layer("sub", H, 4.3), Layer("air", 20 * H)]
    section = CrossSection(layers, [Trace("s", 0.0, H, H + 1e-18, 0.0)], 40 * H,
                           dielectric_regions=[region])
    with pytest.raises(MeshInputError, match=r"layer boundary 1 .*trace 's' .*exactly equal"):
        section.mesh(**OPTIONS)
