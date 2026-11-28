# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Shared input-coordinate rule and messages on every path that calls meshine.

The paths are CrossSection.mesh, mesh_conductor_section (volume current),
PowerPlane.mesh and EllipticalAperture.mesh. Inputs that mesh today keep
every array bit for bit: each case is hashed with the shared rules active and
with them replaced by the pass-through behaviour of the earlier code.
"""

import contextlib
import hashlib

import numpy as np
import pytest
from meshine import MeshInputError, MeshSizeLimitError

from sipi import (CrossSection, Layer, PowerPlane, Sink, Source, Trace, circle, edge,
                  grounded_coplanar, microstrip, rectangle_outline)
from sipi import _mesh_input, aperture_section, conductor_mesh, crosssection, plane
from sipi.aperture_section import EllipticalAperture, RoundConductor
from sipi.conductor_mesh import mesh_conductor_section

H = .5e-3
VOLUME = dict(ground_thickness=.1e-3, padding=2e-3, metal_size=50e-6, far_size=.5e-3, grade=.2)
CORE = [(-.1e-3, .52e-3), (.1e-3, .52e-3), (.1e-3, .58e-3), (-.1e-3, .58e-3)]
SIGMA = 58e6


def _sha(*arrays):
    digest = hashlib.sha256()
    for a in arrays:
        a = np.ascontiguousarray(a)
        digest.update(f'{a.dtype}{a.shape}'.encode() + a.tobytes())
    return digest.hexdigest()


def _passthrough(monkeypatch):
    """Replace the shared rules with what the paths did before they existed."""
    def plain(*_hints):
        return contextlib.nullcontext()
    for module in (crosssection, conductor_mesh, plane, aperture_section):
        monkeypatch.setattr(module, 'explained', plain)
    monkeypatch.setattr(crosssection.CrossSection, '_face_y', lambda self, y: y)
    monkeypatch.setattr(conductor_mesh, 'snap', lambda value, targets, tol: value)


def _microstrip(dy=0.0, thickness=.1e-3):
    return CrossSection([Layer('sub', H, 4), Layer('air', H)],
                        [Trace('signal', 0, .4e-3, H + dy, thickness)], 2e-3)


def _closed(height=.78e-3, plate=.1e-3):
    # low + (high - low) rounds one ulp below high for these numbers.
    section = CrossSection([Layer('dielectric', height, 4)],
                           [Trace('s', 0, .4e-3, height / 2 - .05e-3, .1e-3)], 2e-3,
                           top='ground', sides='ground')
    return section, dict(VOLUME, ground_thickness=plate)


def _terminals():
    return PowerPlane(rectangle_outline(0, 0, 40e-3, 30e-3), 35e-6,
                      holes=[rectangle_outline(15e-3, 10e-3, 25e-3, 20e-3)],
                      sources=[Source('vrm', circle((5e-3, 5e-3), 1e-3), 1.0)],
                      sinks=[Sink('cpu', circle((35e-3, 25e-3), 1e-3), 4.0),
                             Sink('mem', circle((35e-3, 5e-3), 0.6e-3), 1.5)])


def _pair():
    return EllipticalAperture(1.2e-3, .8e-3, [RoundConductor('p', .28e-3, -.25e-3),
                                              RoundConductor('n', .28e-3, .25e-3)], 3.96)


def _cross_section(case):
    section = {'strip': _microstrip(thickness=0.0),
               'tapered': microstrip(width=.4e-3, top_width=.2e-3, substrate_height=H,
                                     thickness=.1e-3, eps_r=4, air_height=H, box_width=2e-3),
               'coplanar': grounded_coplanar(width=.4e-3, gap=.2e-3, ground_width=.3e-3,
                                             substrate_height=H, thickness=.1e-3, eps_r=4,
                                             air_height=H, box_width=2e-3)}[case]
    m = section.mesh()
    lp = m.line_parameters()
    return _sha(m.mesh.nodes, m.mesh.triangles, m.eps_r, m.ground, *m.signals.values(), lp.C, lp.L)


def _volume(case):
    section, options, extra = _microstrip(), VOLUME, {}
    if case == 'layers':
        extra = dict(dielectric_interfaces=True)
    elif case == 'core':
        extra = dict(dielectric_interfaces=True, metal_cores={'signal': CORE})
    elif case == 'closed':
        section = CrossSection([Layer('dielectric', 1e-3, 4)], [Trace('signal', 0, .4e-3, .45e-3, .1e-3)],
                               2e-3, top='ground', sides='ground')
    v = mesh_conductor_section(section, **options, **extra)
    r = v.impedance([0, 1e5], conductivity=SIGMA)
    return _sha(v.mesh.nodes, v.mesh.triangles, v.ground, v.magnetic_boundary, *v.signals.values(),
                *(v.layer_triangles or {}).values(), r.R, r.L)


def _plane(case):
    r = _terminals().solve()
    return _sha(r.mesh.nodes, r.mesh.triangles, r.potential, r.current_density, np.array([r.power_loss]))


def _aperture(case):
    section = _pair()
    m = section.mesh()
    return _sha(m.mesh.nodes, m.mesh.triangles, *m.signals.values(), m.ground, section.capacitance())


CASES = [(_cross_section, 'strip'), (_cross_section, 'tapered'), (_cross_section, 'coplanar'),
         (_volume, 'plain'), (_volume, 'layers'), (_volume, 'core'), (_volume, 'closed'),
         (_plane, 'terminals'), (_aperture, 'pair')]


@pytest.mark.parametrize('build, case', CASES, ids=[f'{b.__name__[1:]}-{c}' for b, c in CASES])
def test_meshable_inputs_keep_every_array_bit_for_bit(build, case, monkeypatch):
    ruled = build(case)
    _passthrough(monkeypatch)
    assert build(case) == ruled


@pytest.mark.parametrize('dy', [1e-18, -1e-18, 1e-13], ids=['above', 'below', '1e-13'])
def test_volume_trace_face_within_merge_distance_meshes_on_layer_boundary(dy):
    # These inputs used to stop with "zero-length edge" once the layers were
    # resolved. The bottom face is placed on the boundary; the top face stays
    # dy higher, so the refined mesh differs. Measured at this coarse
    # metal_size: R(0) within 3e-5 and L within 1.4e-3 of the aligned trace.
    exact = mesh_conductor_section(_microstrip(), **VOLUME, dielectric_interfaces=True)
    near = mesh_conductor_section(_microstrip(dy), **VOLUME, dielectric_interfaces=True)
    p = near.mesh.nodes[near.mesh.triangles]
    a, b = p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]
    area = (a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]) / 2
    assert area[near.signals['signal']].sum() == pytest.approx(.4e-3 * .1e-3, rel=1e-10)
    assert set(near.layer_triangles) == {'sub', 'air'}
    r_exact = exact.impedance([0, 1e5], conductivity=SIGMA)
    r_near = near.impedance([0, 1e5], conductivity=SIGMA)
    np.testing.assert_allclose(r_near.R[0], r_exact.R[0], rtol=1e-4)
    np.testing.assert_allclose(r_near.L, r_exact.L, rtol=2e-3)


def test_volume_without_resolved_layers_keeps_the_face():
    # The layer boundary is not part of that construction, so nothing moves.
    section = _microstrip(1e-18)
    y = section.traces[0].y
    assert y != H
    volume = mesh_conductor_section(section, **VOLUME)
    assert np.any(volume.mesh.nodes[:, 1] == y)


@pytest.mark.parametrize('cores', [None, {'s': [(-.1e-3, .36e-3), (.1e-3, .36e-3), (.1e-3, .42e-3),
                                                (-.1e-3, .42e-3)]}], ids=['slabs', 'core'])
def test_side_plates_that_round_an_ulp_off_the_plate_face_mesh(cores):
    section, options = _closed()
    low, high = -options['ground_thickness'], section.height + options['ground_thickness']
    assert low + (high - low) != high
    volume = mesh_conductor_section(section, **options, metal_cores=cores)
    p = volume.mesh.nodes[volume.mesh.triangles]
    a, b = p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]
    area = (a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]) / 2
    t = options['ground_thickness']
    expected = 2 * section.width * t + 2 * t * (section.height + 2 * t)  # two plates, two sides
    assert area[volume.ground].sum() == pytest.approx(expected, rel=1e-10)
    signal = .4e-3 * .1e-3
    rdc = 1 / (SIGMA * signal) + 1 / (SIGMA * expected)
    np.testing.assert_allclose(volume.impedance([0], conductivity=SIGMA).R[0], [[rdc]], rtol=1e-10)


def test_volume_coordinates_closer_than_merge_distance_explain_the_fix():
    with pytest.raises(MeshInputError) as caught:
        mesh_conductor_section(_microstrip(1e-18), **VOLUME, dielectric_interfaces=True,
                               metal_cores={'signal': CORE})
    message = str(caught.value)
    assert type(caught.value.__cause__) is MeshInputError
    assert message.startswith(str(caught.value.__cause__))
    assert "layer boundary 1 (y = 0.0005 m) and trace 'signal' bottom" in message
    assert 'magnetic box diagonal' in message and 'exactly equal' in message
    assert 'not covered by that rule' in message


def _limited(monkeypatch, module, max_points=50):
    original = module.generate

    def bounded(*args, **kwargs):
        kwargs['max_points'] = max_points
        return original(*args, **kwargs)
    monkeypatch.setattr(module, 'generate', bounded)


def _limit_message(call):
    with pytest.raises(MeshSizeLimitError) as caught:
        call()
    assert type(caught.value) is MeshSizeLimitError
    assert type(caught.value.__cause__) is MeshSizeLimitError
    message = str(caught.value)
    assert message.startswith('more than 50 points')
    return message


def test_volume_point_limit_names_metal_size_and_skin_depth(monkeypatch):
    _limited(monkeypatch, conductor_mesh)
    message = _limit_message(lambda: mesh_conductor_section(_microstrip(), **VOLUME))
    assert 'metal_size 5e-05 m, far_size 0.0005 m, grade 0.2' in message
    assert 'metal area is' in message and 'raise metal_size first' in message
    assert 'max_edge_over_skin_depth' in message


def test_plane_point_limit_names_the_driving_terminal(monkeypatch):
    _limited(monkeypatch, plane)
    message = _limit_message(lambda: _terminals().mesh())
    assert "terminal 'mem' (0.0012 m) / 12" in message
    assert 'raise edge_size first' in message
    assert 'edge_size was given explicitly' in _limit_message(lambda: _terminals().mesh(edge_size=1e-3))
    strip = PowerPlane(rectangle_outline(0, 0, 50e-3, 5e-3), 35e-6,
                       sources=[Source('vrm', edge((0, 0), (0, 5e-3)), 1.0)],
                       sinks=[Sink('load', edge((50e-3, 0), (50e-3, 5e-3)), 3.0)])
    assert "terminal 'vrm' (0.005 m) / 12" in _limit_message(strip.mesh)


def test_aperture_point_limit_names_size(monkeypatch):
    _limited(monkeypatch, aperture_section)
    message = _limit_message(lambda: _pair().mesh())
    assert 'the default size is max(width, height) / 48' in message
    assert 'angular_divisions 128' in message and 'raise size first' in message
    assert 'size was given explicitly' in _limit_message(lambda: _pair().mesh(size=1e-4))


def test_plane_vertices_closer_than_merge_distance_are_named():
    tiny = PowerPlane(rectangle_outline(0, 0, 10e-3, 10e-3), 35e-6,
                      sources=[Source('vrm', circle((5e-3, 5e-3), 1e-3), 1.0)],
                      sinks=[Sink('l', circle((8e-3, 8e-3), 1e-14), 1.0)])
    with pytest.raises(MeshInputError) as caught:
        tiny.mesh()
    message = str(caught.value)
    assert type(caught.value.__cause__) is MeshInputError
    assert message.startswith(str(caught.value.__cause__))
    assert "SIPI: terminal 'l' vertex 0 (0.00800000000001, 0.008) m and terminal 'l' vertex 1" in message
    assert 'more pairs' in message and 'does not move them' in message


def test_aperture_vertices_closer_than_merge_distance_are_named_in_metres():
    with pytest.raises(MeshInputError) as caught:
        EllipticalAperture(1e-3, 1e-3, [RoundConductor('s', 1e-12)]).mesh()
    message = str(caught.value)
    assert type(caught.value.__cause__) is MeshInputError
    assert "SIPI: conductor 's' vertex 0 (5" in message and 'e-13, 0.0) m' in message
    assert 'merge distance 1.41e-12 m' in message and 'angular_divisions' in message


def test_shared_helpers():
    assert _mesh_input.snap(1.0 + 1e-12, [1.0], 1e-9) == 1.0
    assert _mesh_input.snap(1.0, [1.0], 1e-9) == 1.0
    assert _mesh_input.snap(1.0 + 1e-9, [1.0], 1e-9) == 1.0 + 1e-9
    assert _mesh_input.close_coordinates([('a', 'x', 0.0), ('b', 'y', 1e-12), ('c', 'x', 1e-12)],
                                         1e-9) == ['a (x = 0.0 m) and c (x = 1e-12 m) differ by 1e-12 m']
    assert _mesh_input.close_vertices([('a', [[0, 0], [1, 1]]), ('b', [[1, 1], [2e-10, 0]])], 1e-9) == [
        'a vertex 0 (0.0, 0.0) m and b vertex 1 (2e-10, 0.0) m differ by 2e-10 m in x and 0 m in y']
    assert _mesh_input.coincidence_message([], 1e-9, 'd', 'fix') == ''


def test_errors_without_close_coordinates_pass_through_unchanged():
    error = MeshInputError('a segment is shared by more than two regions; regions overlap')
    with pytest.raises(MeshInputError) as caught:
        with _mesh_input.explained(lambda: ''):
            raise error
    assert caught.value is error
    limit = MeshSizeLimitError('more than 4 points')
    with pytest.raises(MeshSizeLimitError) as caught:
        with _mesh_input.explained():
            raise limit
    assert caught.value is limit
