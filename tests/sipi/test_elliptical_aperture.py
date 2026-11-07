# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent panel/FEM references for local grounded aperture matrices."""
from dataclasses import replace
import importlib.metadata as metadata
import json

import numpy as np
import pytest
from scipy.constants import epsilon_0
from scipy.linalg import solve
from galerkin import Mesh
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import (RoundConductor, EllipticalAperture, ApertureSectionDocument,
                  CircularAperture, ApertureDocument, capacitance_matrix)


def boundary_panel_reference(section, n):
    """Constant line-charge panels with analytic self integration and net Q=0.

    An independent 2D single-layer log potential. Its additive constant is an
    unknown, with total boundary charge constrained to zero; outer V is zero.
    The geometry and linear solve do not use the production mesh or assembler.
    """
    scale = max(section.width, section.height)
    theta = np.arange(n)*2*np.pi/n
    direction = np.column_stack([np.cos(theta), np.sin(theta)])
    loops = [direction*np.array([section.width, section.height])/2/scale]
    loops += [(direction*c.diameter/2+[c.x, c.y])/scale for c in section.conductors]
    starts = np.vstack(loops)
    ends = np.vstack([np.roll(p, -1, axis=0) for p in loops])
    lengths = np.linalg.norm(ends-starts, axis=1)
    mid = (starts+ends)/2
    nodes, weights = np.polynomial.legendre.leggauss(16)
    quadrature = mid[:, None, :]+(ends-starts)[:, None, :]*nodes[None, :, None]/2
    m = len(starts)
    kernel = np.empty((m, m))
    for i, point in enumerate(mid):
        distances = np.linalg.norm(quadrature-point, axis=2)
        kernel[i] = -np.sum(np.log(distances)*weights, axis=1)*lengths/(4*np.pi)
        kernel[i, i] = lengths[i]*(1-np.log(lengths[i]/2))/(2*np.pi)
    system = np.zeros((m+1, m+1))
    system[:m, :m] = kernel
    system[:m, -1] = 1.
    system[-1, :m] = lengths
    rhs = np.zeros((m+1, len(section.conductors)))
    for j in range(len(section.conductors)):
        rhs[n*(j+1):n*(j+2), j] = 1.
    density = solve(system, rhs)
    c = np.array([lengths[n*(j+1):n*(j+2)]@density[n*(j+1):n*(j+2)]
                  for j in range(len(section.conductors))])
    return epsilon_0*section.eps_r*(1-1j*section.tan_delta)*c


def section(case='pair', loss=0.):
    if case == 'circle':
        return EllipticalAperture(.8e-3, .8e-3, [RoundConductor('s', .28e-3, .2e-3)], 3.96, loss)
    if case == 'single':
        return EllipticalAperture(.73e-3, .53e-3, [RoundConductor('s', .28e-3)], 3.96, loss)
    return EllipticalAperture(1.2e-3, .8e-3,
        [RoundConductor('p', .28e-3, -.25e-3), RoundConductor('n', .28e-3, .25e-3)], 3.96, loss)


def relative(a, b):
    return np.linalg.norm(a-b)/np.linalg.norm(b)


@pytest.mark.parametrize('case', ['circle', 'single', 'pair'])
def test_independent_boundary_panels_and_separate_field_polygon_convergence(case):
    s = section(case)
    references = [boundary_panel_reference(s, n) for n in (128, 256)]
    values = [s.capacitance(size=size, angular_divisions=n)
              for n, size in [(128, s.width/24), (128, s.width/48), (256, s.width/48)]]
    reference_step = relative(*references)
    mesh_step = relative(values[0], values[1])
    polygon_step = relative(values[1], values[2])
    error = relative(values[-1], references[-1])
    assert reference_step < .002
    assert mesh_step < .005 and polygon_step < .005
    assert error < .01
    if case == 'circle':
        a, b, e = .14e-3, .4e-3, .2e-3
        exact = 2*np.pi*epsilon_0*3.96/np.arccosh((b*b+a*a-e*e)/(2*a*b))
        assert abs(values[-1][0, 0]/exact-1) < .002
        old = CircularAperture(2*a, 2*b, offset_x=e, eps_r=3.96).capacitance(
            radial_divisions=64, angular_divisions=256)
        assert abs(values[-1][0, 0]/old-1) < .002
    if case == 'pair':
        t = np.array([[.5, 1.], [-.5, 1.]])
        assert abs((t.T@values[-1]@t)[0, 0]/(t.T@references[-1]@t)[0, 0]-1) < .01
        # A non-mirror-symmetric triangulation has finite symmetry error.
        assert abs(values[-1][0, 0]/values[-1][1, 1]-1) < .005
    print('aperture panel/field/polygon/reference', case,
          reference_step, mesh_step, polygon_step, error, values[-1])


def test_independent_complex_matrix_assembly_and_power_dual_coordinates():
    skfem = require_tool('scikit-fem')
    from skfem.helpers import dot, grad
    s = replace(section(loss=.03), conductors=[RoundConductor('p', .28e-3, -.25e-3),
                                               RoundConductor('n', .20e-3, .25e-3, .03e-3)])
    extracted = s.mesh()
    mesh = extracted.mesh
    clock = Stopwatch()
    with clock('openphysics'):
        actual = s.capacitance()
    with clock('reference'):
        basis = skfem.Basis(skfem.MeshTri(mesh.nodes.T, mesh.triangles.T), skfem.ElementTriP1())

        @skfem.BilinearForm(dtype=complex)
        def form(u, v, w):
            return 3.96*(1-.03j)*dot(grad(u), grad(v))

        k = skfem.asm(form, basis)
        fixed = np.unique(np.concatenate([extracted.ground, *extracted.signals.values()]))
        potentials = []
        for nodes in extracted.signals.values():
            v = np.zeros(basis.N, complex)
            v[nodes] = 1.
            potentials.append(skfem.solve(*skfem.condense(k, np.zeros(basis.N, complex), x=v, D=fixed)))
        u = np.array(potentials).T
        expected = epsilon_0*u.T@(k@u)
    error = float(relative(actual, expected))
    assert error < 1e-9
    np.testing.assert_allclose(actual, actual.T, rtol=1e-12, atol=0)
    assert np.linalg.eigvalsh(actual.real).min() > 0
    assert np.linalg.eigvalsh(-actual.imag).min() > 0
    mixed = s.mixed_capacitance()
    vm = np.array([.7+.2j, .1-.3j])
    v = np.array([vm[1]+vm[0]/2, vm[1]-vm[0]/2])
    q = actual@v
    qm = np.array([(q[0]-q[1])/2, q[0]+q[1]])
    np.testing.assert_allclose(mixed@vm, qm, rtol=1e-10, atol=0)
    assert abs(np.vdot(vm, qm)/np.vdot(v, q)-1) < 1e-10
    assert abs(mixed[0, 1])/np.linalg.norm(mixed) > .001
    record = make_record(case='paired-elliptical-aperture', physics='local multiconductor electrostatics',
        api='sipi.EllipticalAperture', discretization='polygonized circular conductors, ellipse and shared P1 energy',
        tool='scikit-fem', tool_discretization='independent complex P1 matrix energy',
        matched=['same polygons, mesh, conductor voltages and homogeneous complex material'],
        not_matched=['same-mesh assembly does not prove geometry convergence or three-dimensional via behavior'],
        observables=[observable('complex C matrix', 'F/m', 'relative Frobenius difference', error, 1e-9)],
        analytical_acceptance='eccentric circular limit, independent log-kernel panels and separate refinement',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi', version=metadata.version('sipi')); emit(record)


def test_order_material_binary_scale_and_rigid_mesh_rotation_invariants():
    s = section(loss=.03)
    original = s.capacitance()
    swapped = replace(s, conductors=s.conductors[::-1])
    np.testing.assert_allclose(swapped.capacitance(), original[::-1, ::-1], rtol=1e-10, atol=0)
    a, b = s.mesh(), swapped.mesh()
    np.testing.assert_array_equal(a.mesh.nodes, b.mesh.nodes)
    np.testing.assert_array_equal(a.mesh.triangles, b.mesh.triangles)
    vacuum = replace(s, eps_r=1., tan_delta=0.).capacitance()
    np.testing.assert_allclose(original, vacuum*3.96*(1-.03j), rtol=1e-12, atol=0)
    for scale in (2.**-10, 2.**10):
        scaled = replace(s, width=s.width*scale, height=s.height*scale,
            conductors=[replace(c, diameter=c.diameter*scale, x=c.x*scale, y=c.y*scale) for c in s.conductors])
        np.testing.assert_allclose(scaled.capacitance(), original, rtol=1e-10, atol=0)
    angle = .371
    q = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    rotated = Mesh(a.mesh.nodes@q.T, a.mesh.triangles.copy(), a.mesh.boundary)
    result = capacitance_matrix(rotated, 3.96*(1-.03j), a.signals, a.ground)
    np.testing.assert_allclose(result, original, rtol=1e-10, atol=0)


def test_snapshot_replay_and_legacy_circular_bytes():
    s = section(loss=.03)
    options = {'size': s.width/32, 'angular_divisions': 64}
    doc = ApertureSectionDocument(s, mesh=options)
    text = doc.dumps(); data = doc.to_dict()
    assert data['schema'] == 'sipi.aperture-section/1' and data['length_unit'] == 'm'
    assert data['aperture'] == {'width': 1.2e-3, 'height': .8e-3}
    assert data['conductors'][0] == {'name': 'p', 'diameter': .28e-3, 'x': -.25e-3, 'y': 0.}
    loaded = ApertureSectionDocument.loads(text)
    assert loaded.dumps() == text and loaded.section == s
    np.testing.assert_allclose(loaded.analyze(), s.capacitance(**options), rtol=1e-12, atol=0)
    options['angular_divisions'] = 16
    data['conductors'][0]['diameter'] = 0
    doc.mesh_options['angular_divisions'] = 16
    assert doc.dumps() == text
    legacy = ApertureDocument(CircularAperture(.28e-3, .8e-3)).dumps()
    assert ApertureDocument.loads(legacy).dumps() == legacy
    with pytest.raises(ValueError):
        ApertureSectionDocument.loads(legacy)
    with pytest.raises(ValueError):
        ApertureDocument.loads(text)
    with pytest.raises(TypeError):
        ApertureSectionDocument({})


@pytest.mark.parametrize('kwargs', [dict(name=''), dict(name='ground'), dict(name='a\nb'), dict(name=True),
    dict(diameter=0), dict(diameter=-1), dict(diameter=True), dict(diameter=float('nan')),
    dict(x=float('inf')), dict(y=False)])
def test_invalid_round_conductors(kwargs):
    parameters = dict(name='a', diameter=.1e-3)
    parameters.update(kwargs)
    with pytest.raises(ValueError):
        RoundConductor(**parameters)


@pytest.mark.parametrize('kwargs', [dict(width=0), dict(height=True), dict(width=np.inf),
    dict(eps_r=0), dict(tan_delta=-1), dict(eps_r=True), dict(eps_r=1e308, tan_delta=1e308),
    dict(conductors=[]), dict(conductors=None), dict(conductors=['a']),
    dict(conductors=[RoundConductor('a', .1e-3)]*2),
    dict(conductors=[RoundConductor('a', .1e-3), RoundConductor('b', .1e-3)]),
    dict(conductors=[RoundConductor('a', 2e-3)])])
def test_invalid_sections(kwargs):
    with pytest.raises(ValueError):
        replace(section(), **kwargs)


@pytest.mark.parametrize('options', [dict(size=0), dict(size=True), dict(size=np.inf),
    dict(angular_divisions=15), dict(angular_divisions=128.), dict(angular_divisions=False)])
def test_invalid_mesh_controls_before_generation(options, monkeypatch):
    import sipi.aperture_section as module
    monkeypatch.setattr(module, 'generate', lambda *a, **kw: pytest.fail('unexpected mesh'))
    with pytest.raises(ValueError):
        section().mesh(**options)


def test_containment_outside_ellipse_but_inside_box_and_polygon_clearance(monkeypatch):
    import sipi.aperture_section as module
    monkeypatch.setattr(module, 'generate', lambda *a, **kw: pytest.fail('unexpected mesh'))
    invalid = EllipticalAperture(1., 1., [RoundConductor('a', .1, .4, .4)])
    with pytest.raises(ValueError, match='polygon'):
        invalid.mesh()
    with pytest.raises(ValueError, match='polygon'):
        ApertureSectionDocument(invalid)
    centre_inside = EllipticalAperture(1., 1., [RoundConductor('a', .06, .35, .35)])
    with pytest.raises(ValueError, match='polygon'):
        centre_inside.mesh()
    near = EllipticalAperture(.8e-3, .8e-3, [RoundConductor('a', .28e-3, .258e-3)])
    assert near.mesh_settings(angular_divisions=64)['angular_divisions'] == 64
    with pytest.raises(ValueError, match='polygon'):
        near.mesh(angular_divisions=16)
    with pytest.raises(ValueError, match='two conductors'):
        section('single').mixed_capacitance()


@pytest.mark.parametrize('scale', [1e-200, 1e200])
def test_dimensional_area_limits_fail_before_field_solve(scale, monkeypatch):
    import sipi.aperture_section as module
    monkeypatch.setattr(module, 'capacitance_matrix', lambda *a, **kw: pytest.fail('unexpected solve'))
    s = EllipticalAperture(6*scale, 4*scale, [RoundConductor('a', scale)])
    with pytest.raises(ValueError, match='dimensional mesh areas'):
        s.capacitance(size=scale, angular_divisions=16)


@pytest.mark.parametrize('eps', [1e-308, 1e308])
def test_homogeneous_material_extremes_remain_finite(eps):
    s = section('single')
    c = replace(s, eps_r=eps).capacitance()
    reference = replace(s, eps_r=1.).capacitance()*eps
    assert np.isfinite(c).all() and c.real[0, 0] > 0
    np.testing.assert_allclose(c, reference, rtol=1e-12, atol=0)


def test_zero_underflow_capacitance_is_rejected():
    with pytest.raises(ValueError, match='capacitance must'):
        replace(section('single'), eps_r=np.nextafter(0., 1.)).capacitance()


@pytest.mark.parametrize('path,value', [
    (('schema',), 'sipi.aperture-section/2'), (('length_unit',), 'mm'), (('extra',), 1),
    (('aperture','radius'), .1), (('dielectric','eps_r'), True), (('mesh','radial_divisions'), 32),
    (('conductors',), {}), (('conductors',), [{'name':'s','diameter':.1e-3,'x':0,'y':0,'extra':1}]),
    (('mesh','size'), float('nan'))])
def test_strict_schema(path, value):
    data = ApertureSectionDocument(section()).to_dict()
    parent = data
    for key in path[:-1]:
        parent = parent[key]
    parent[path[-1]] = value
    with pytest.raises(ValueError):
        ApertureSectionDocument.from_dict(data)


@pytest.mark.parametrize('text', ['{"schema":1,"schema":2}', '{"x":NaN}', '{"x":Infinity}', '[]'])
def test_strict_json(text):
    with pytest.raises(ValueError):
        ApertureSectionDocument.loads(text)
