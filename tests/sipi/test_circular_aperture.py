# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Local eccentric-aperture references, discretization and strict inputs."""
from dataclasses import FrozenInstanceError
import importlib.metadata as metadata
import json

import numpy as np
import pytest
from scipy.constants import epsilon_0
from galerkin import Mesh
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import ApertureDocument, CircularAperture, capacitance_matrix


def exact(a, b, eccentricity, eps=3.96):
    # Bipolar-coordinate solution for two nonintersecting eccentric circles.
    factor = np.log(b/a) if eccentricity == 0 else np.arccosh((b*b+a*a-eccentricity**2)/(2*a*b))
    return 2*np.pi*epsilon_0*eps/factor


@pytest.mark.parametrize('fraction', [0., .5, .8])
def test_eccentric_closed_form_and_separate_radial_angular_convergence(fraction):
    a, b = .14e-3, .4e-3
    e = fraction*(b-a)
    section = CircularAperture(2*a, 2*b, offset_x=e, eps_r=3.96)
    reference = exact(a, b, e)
    values = [section.capacitance(radial_divisions=nr, angular_divisions=nt).real
              for nr, nt in [(16, 64), (32, 128), (64, 256), (128, 256), (128, 512)]]
    errors = [abs(v/reference-1) for v in values]
    assert errors[0] > errors[1] > errors[2]
    assert errors[-1] < .002
    radial = abs(values[2]/values[3]-1)
    polygon = abs(values[3]/values[4]-1)
    assert radial < .002 and polygon < .002
    print('eccentric aperture reference/radial/polygon', fraction, errors, radial, polygon)


def test_complex_capacitance_against_independent_fem():
    skfem = require_tool('scikit-fem')
    from skfem.helpers import dot, grad
    section = CircularAperture(.28e-3, .8e-3, offset_x=.16e-3, offset_y=.12e-3,
                               eps_r=3.96, tan_delta=.03)
    mesh = section.mesh(radial_divisions=48, angular_divisions=192)
    clock = Stopwatch()
    with clock('openphysics'):
        actual = section.capacitance(radial_divisions=48, angular_divisions=192)
    with clock('reference'):
        basis = skfem.Basis(skfem.MeshTri(mesh.nodes.T, mesh.triangles.T), skfem.ElementTriP1())

        @skfem.BilinearForm(dtype=complex)
        def energy(u, v, w):
            return 3.96*(1-.03j)*dot(grad(u), grad(v))

        k = skfem.asm(energy, basis)
        fixed = np.unique(np.concatenate([mesh.boundary['inner'], mesh.boundary['outer']]))
        voltage = np.zeros(basis.N, complex)
        voltage[mesh.boundary['inner']] = 1.
        u = skfem.solve(*skfem.condense(k, np.zeros(basis.N, complex), x=voltage, D=fixed))
        reference = epsilon_0*(u@(k@u))
    error = float(abs(actual/reference-1))
    assert error < 1e-9 and actual.real > 0 and actual.imag < 0
    record = make_record(case='eccentric-circular-aperture', physics='local homogeneous electrostatics',
        api='sipi.CircularAperture', discretization='mapped shared annulus P1 vacuum energy and homogeneous scaling',
        tool='scikit-fem', tool_discretization='independent complex P1 assembly and energy',
        matched=['same polygonized circles, offsets, material, mesh and Dirichlet boundaries'],
        not_matched=['not a via transition or total pad capacitance; same-mesh agreement is not convergence'],
        observables=[observable('complex C', 'F/m', 'relative difference', error, 1e-9)],
        analytical_acceptance='eccentric-circle exact solution with separate radial/angular refinement',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi', version=metadata.version('sipi'))
    emit(record)


def test_reflection_quarter_turn_uniform_scale_and_complex_material_laws():
    settings = dict(radial_divisions=24, angular_divisions=96)
    original = CircularAperture(.28e-3, .8e-3, .1e-3, .05e-3).capacitance(**settings)
    for scale, x, y in [(1., -.1, -.05), (1., -.05, .1), (.001, .1, .05), (1000., .1, .05)]:
        section = CircularAperture(.28e-3*scale, .8e-3*scale, x*1e-3*scale, y*1e-3*scale)
        assert abs(section.capacitance(**settings)/original-1) < 1e-10
    material = CircularAperture(.28e-3, .8e-3, .1e-3, .05e-3, 3.96, .03)
    assert abs(material.capacitance(**settings)/(original*3.96*(1-.03j))-1) < 1e-12
    mesh = material.mesh(**settings)
    angle = .371
    rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    rotated = Mesh(mesh.nodes@rotation.T, mesh.triangles.copy(), mesh.boundary)
    actual = capacitance_matrix(rotated, 3.96*(1-.03j), {'inner': mesh.boundary['inner']},
                                mesh.boundary['outer'])[0, 0]
    assert abs(actual/material.capacitance(**settings)-1) < 1e-10


def test_mesh_boundaries_represent_explicit_diameters_and_offset():
    section = CircularAperture(.28e-3, .8e-3, .1e-3, -.07e-3)
    mesh = section.mesh()
    inner, outer = mesh.nodes[mesh.boundary['inner']], mesh.nodes[mesh.boundary['outer']]
    np.testing.assert_allclose(np.linalg.norm(inner-[section.offset_x, section.offset_y], axis=1),
                               section.conductor_diameter/2, rtol=1e-12)
    np.testing.assert_allclose(np.linalg.norm(outer, axis=1), section.aperture_diameter/2, rtol=1e-12)
    with pytest.raises(FrozenInstanceError):
        section.offset_x = .2e-3


@pytest.mark.parametrize('scale', [1e-200, 1e200])
def test_unrepresentable_dimensional_areas_fail_before_field_solve(scale, monkeypatch):
    import sipi.aperture as module
    monkeypatch.setattr(module, 'capacitance_matrix', lambda *a, **kw: pytest.fail('unexpected solve'))
    with pytest.raises(ValueError, match='cell areas'):
        CircularAperture(2*scale, 6*scale).capacitance(radial_divisions=2, angular_divisions=16)


@pytest.mark.parametrize('eps', [1e-308, 1e308])
def test_uniform_material_extremes_do_not_overflow_the_field_problem(eps):
    settings = dict(radial_divisions=16, angular_divisions=64)
    reference = exact(.14e-3, .4e-3, 0, eps=1.)
    value = CircularAperture(.28e-3, .8e-3, eps_r=eps).capacitance(**settings)
    assert np.isfinite(value) and value.real > 0
    assert abs(value.real/(reference*eps)-1) < .002


def test_unrepresentable_capacitance_is_an_error_not_a_zero_result():
    with pytest.raises(ValueError, match='capacitance must'):
        CircularAperture(.28e-3, .8e-3, eps_r=np.nextafter(0., 1.)).capacitance(
            radial_divisions=2, angular_divisions=16)


@pytest.mark.parametrize('change', [
    {'conductor_diameter': 0.}, {'conductor_diameter': -.1}, {'conductor_diameter': True},
    {'conductor_diameter': np.nan}, {'conductor_diameter': 1.},
    {'aperture_diameter': 0.}, {'aperture_diameter': np.inf},
    {'offset_x': .4e-3}, {'offset_y': .4e-3}, {'offset_x': np.inf}, {'offset_y': False},
    {'eps_r': 0.}, {'eps_r': -1.}, {'eps_r': True}, {'eps_r': '4'},
    {'tan_delta': -.01}, {'tan_delta': np.nan}, {'tan_delta': 1j},
    {'eps_r': 1e308, 'tan_delta': 1e308}])
def test_invalid_geometry_and_material_rejected(change):
    parameters = dict(conductor_diameter=.28e-3, aperture_diameter=.8e-3)
    parameters.update(change)
    with pytest.raises(ValueError):
        CircularAperture(**parameters)


@pytest.mark.parametrize('options', [
    {'radial_divisions': 1}, {'radial_divisions': 32.}, {'radial_divisions': True},
    {'angular_divisions': 15}, {'angular_divisions': 128.}, {'angular_divisions': False}])
def test_invalid_mesh_controls_rejected_before_allocation(options, monkeypatch):
    import sipi.aperture as module
    monkeypatch.setattr(module, 'annulus_mesh', lambda *a, **kw: pytest.fail('unexpected mesh'))
    with pytest.raises(ValueError):
        CircularAperture(.28e-3, .8e-3).mesh(**options)


def test_polygon_clearance_guard_and_document_preflight(monkeypatch):
    import sipi.aperture as module
    section = CircularAperture(.28e-3, .8e-3, offset_x=.258e-3)
    assert section.mesh_settings(angular_divisions=64)['angular_divisions'] == 64
    monkeypatch.setattr(module, 'annulus_mesh', lambda *a, **kw: pytest.fail('unexpected mesh'))
    with pytest.raises(ValueError, match='angular resolution'):
        section.mesh(angular_divisions=16)
    with pytest.raises(ValueError, match='angular resolution'):
        ApertureDocument(section, mesh={'angular_divisions': 16})


def test_versioned_snapshot_replays_complex_result_without_sharing_mutable_input():
    section = CircularAperture(.28e-3, .8e-3, .1e-3, -.07e-3, 3.96, .03)
    options = {'radial_divisions': 24, 'angular_divisions': 96}
    doc = ApertureDocument(section, mesh=options)
    options['radial_divisions'] = 2
    data = doc.to_dict()
    assert data == dict(schema='sipi.circular-aperture/1', length_unit='m',
        geometry=dict(conductor_diameter=.28e-3, aperture_diameter=.8e-3, offset_x=.1e-3, offset_y=-.07e-3),
        dielectric=dict(eps_r=3.96, tan_delta=.03), mesh=dict(radial_divisions=24, angular_divisions=96))
    loaded = ApertureDocument.loads(doc.dumps())
    assert loaded.dumps() == doc.dumps() and loaded.section == section
    assert abs(loaded.analyze()/section.capacitance(radial_divisions=24, angular_divisions=96)-1) < 1e-12
    data['geometry']['offset_x'] = 0
    doc.mesh_options['radial_divisions'] = 2
    assert doc.section.offset_x == .1e-3 and doc.mesh_options['radial_divisions'] == 24
    with pytest.raises(TypeError):
        ApertureDocument({})


@pytest.mark.parametrize('path,value', [
    (('schema',), 'sipi.circular-aperture/2'), (('length_unit',), 'mm'),
    (('extra',), 1), (('geometry', 'radius'), .1), (('dielectric', 'eps_r'), True),
    (('mesh', 'edge_size'), 1e-6), (('mesh', 'radial_divisions'), 3.5),
    (('mesh',), None), (('geometry', 'offset_x'), float('nan'))])
def test_strict_document_rejects_unknown_fields_units_and_invalid_values(path, value):
    data = ApertureDocument(CircularAperture(.28e-3, .8e-3)).to_dict()
    parent = data
    for key in path[:-1]:
        parent = parent[key]
    parent[path[-1]] = value
    with pytest.raises(ValueError):
        ApertureDocument.from_dict(data)


@pytest.mark.parametrize('text', ['{"schema":1,"schema":2}', '{"value":NaN}', '{"value":Infinity}', '[]'])
def test_json_rejects_duplicates_nonfinite_and_wrong_root(text):
    with pytest.raises(ValueError):
        ApertureDocument.loads(text)
