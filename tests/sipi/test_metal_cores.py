# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit core/coat interfaces: geometry, DC, MQS convergence and reference."""
import importlib.metadata as metadata
import numpy as np
import pytest
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import CrossSection, Trace, PolygonTrace, microstrip
from sipi.conductor_mesh import mesh_conductor_section
from sipi.volume_line import volume_line
from sipi.dielectric import ConstantDielectric
from test_conductor_mesh import areas

CORE = ((-.18e-3, .52e-3), (.18e-3, .52e-3), (.18e-3, .58e-3), (-.18e-3, .58e-3))
OPTIONS = dict(ground_thickness=.1e-3, padding=.002, metal_size=25e-6, far_size=.25e-3, grade=.1)
F = [0, 1e3, 1e4, 1e5]


def section():
    return microstrip(width=.4e-3, substrate_height=.5e-3, thickness=.1e-3,
                     eps_r=4, tan_delta=.02, air_height=.5e-3, box_width=.002)


def volume(options=None, cs=None, cores=None):
    return mesh_conductor_section(section() if cs is None else cs,
        **(OPTIONS if options is None else options), dielectric_interfaces=True,
        metal_cores={'signal': CORE} if cores is None else cores)


def conductivity(v):
    values = np.zeros(v.mesh.num_triangles)
    for ids in v.signals.values(): values[ids] = 20e6
    values[v.ground] = 58e6
    for ids in v.core_triangles.values(): values[ids] = 58e6
    return values


@pytest.fixture(scope='module')
def rectangular():
    v = volume()
    return v, v.impedance(F, conductivity=conductivity(v), keep_fields=True)


def test_core_shell_area_interface_and_exact_dc_current(rectangular):
    v, result = rectangular
    a = areas(v)
    core = v.core_triangles['signal']
    shell = np.setdiff1d(v.signals['signal'], core)
    core_area, whole_area = .36e-3*.06e-3, .4e-3*.1e-3
    assert a[core].sum() == pytest.approx(core_area, rel=1e-10)
    assert a[shell].sum() == pytest.approx(whole_area-core_area, rel=1e-10)
    edges = np.sort(v.mesh.triangles[core][:, [[0, 1], [1, 2], [2, 0]]].reshape(-1, 2), axis=1)
    unique, counts = np.unique(edges, axis=0, return_counts=True)
    boundary = unique[counts == 1]
    nodes = v.mesh.nodes[boundary]
    midpoint = nodes.mean(axis=1)
    on_x = np.min(abs(midpoint[:, 0, None]-[-.18e-3, .18e-3]), axis=1) < 1e-14
    on_y = np.min(abs(midpoint[:, 1, None]-[.52e-3, .58e-3]), axis=1) < 1e-14
    assert np.all(on_x | on_y)
    assert np.linalg.norm(nodes[:, 1]-nodes[:, 0], axis=1).sum() == pytest.approx(2*(.36e-3+.06e-3), rel=1e-10)
    conductance = 58e6*core_area+20e6*(whole_area-core_area)
    expected = 1/conductance+1/(58e6*.002*.1e-3)
    assert result.R[0, 0, 0] == pytest.approx(expected, rel=1e-10)
    np.testing.assert_allclose(result.current_density[0, core, 0], 58e6/conductance, rtol=1e-10)
    np.testing.assert_allclose(result.current_density[0, shell, 0], 20e6/conductance, rtol=1e-10)
    assert np.max(result.current_error) < 1e-10
    assert not core.flags.writeable
    with pytest.raises(TypeError): v.settings['metal_cores']['signal'] = ()


def test_coating_mesh_and_magnetic_boundary_converge_separately(rectangular, record_property):
    coarse_v, coarse = rectangular
    fine_options = dict(OPTIONS, metal_size=12.5e-6, far_size=.125e-3, grade=.05)
    fine_v = volume(fine_options)
    fine = fine_v.impedance(F, conductivity=conductivity(fine_v))
    changes = {k: float(np.max(abs(getattr(coarse, k)-getattr(fine, k)))/np.max(abs(getattr(fine, k)))) for k in ('R', 'L')}
    large_v = volume(dict(fine_options, padding=.004))
    large = large_v.impedance(F, conductivity=conductivity(large_v))
    outer = float(np.max(abs(large.L-fine.L))/np.max(abs(large.L)))
    record_property('core_convergence', str(dict(mesh=changes, outer_L=outer,
        nodes=[v.mesh.num_nodes for v in (coarse_v, fine_v, large_v)])))
    assert max(changes.values()) < .01
    assert outer < .02


@pytest.mark.parametrize('kind', ['taper', 'polygon'])
def test_explicit_core_keeps_outer_nonrectangular_metal(kind):
    base = section()
    if kind == 'taper':
        trace = Trace('signal', 0, .4e-3, .5e-3, .1e-3, top_width=.3e-3)
    else:
        trace = PolygonTrace('signal', ((-.2e-3, .5e-3), (.2e-3, .5e-3), (.2e-3, .6e-3),
                                        (0., .64e-3), (-.2e-3, .6e-3)))
    cs = CrossSection(base.layers, [trace], base.width)
    core = ((-.12e-3, .52e-3), (.12e-3, .52e-3), (.12e-3, .58e-3), (-.12e-3, .58e-3))
    v = volume(cs=cs, cores={'signal': core})
    a = areas(v)
    expected = .035e-6 if kind == 'taper' else .048e-6
    assert a[v.signals['signal']].sum() == pytest.approx(expected, rel=1e-10)
    assert a[v.core_triangles['signal']].sum() == pytest.approx(.24e-3*.06e-3, rel=1e-10)


@pytest.mark.parametrize('name', ['_bottom', '_top', '_side'])
def test_trace_name_cannot_assign_a_core_to_generated_reference_plates(name):
    base = section()
    trace = Trace(name, 0, .4e-3, .5e-3, .1e-3)
    cs = CrossSection(base.layers, [trace], base.width)
    v = volume(cs=cs, cores={name: CORE})
    assert set(v.core_triangles) == {name}
    assert np.isin(v.core_triangles[name], v.signals[name]).all()
    assert not np.intersect1d(v.core_triangles[name], v.ground).size
    assert areas(v)[v.ground].sum() == pytest.approx(.002*.1e-3, rel=1e-10)


def test_ground_core_stays_in_one_common_return_group():
    base = section()
    shield = Trace('shield', .00065, .3e-3, .5e-3, .1e-3, ground=True)
    cs = CrossSection(base.layers, [*base.traces, shield], base.width)
    core = ((.00055, .00052), (.00075, .00052), (.00075, .00058), (.00055, .00058))
    v = volume(cs=cs, cores={'shield': core})
    ids = v.core_triangles['shield']
    assert np.isin(ids, v.ground).all() and 'shield' not in v.signals
    sigma = np.zeros(v.mesh.num_triangles)
    sigma[v.signals['signal']] = 58e6
    sigma[v.ground] = 20e6
    sigma[ids] = 58e6
    result = v.impedance([0], conductivity=sigma)
    core_area = .2e-3*.06e-3
    ground_area = (.002+.3e-3)*.1e-3
    expected = 1/(58e6*.4e-3*.1e-3)+1/(58e6*core_area+20e6*(ground_area-core_area))
    assert result.R[0, 0, 0] == pytest.approx(expected, rel=1e-10)


def test_same_conductivity_interface_retains_electric_geometry(rectangular):
    v, _ = rectangular
    sigma = conductivity(v)
    material = {l.name: ConstantDielectric(l.eps_r, l.tan_delta) for l in section().layers}
    mixed = volume_line(v, F, materials=material, conductivity=sigma, length=.1)
    homogeneous = volume_line(v, F, materials=material, conductivity=58e6, length=.1)
    np.testing.assert_array_equal(mixed.C_complex, homogeneous.C_complex)
    assert np.all(mixed.R[:, 0, 0] > homogeneous.R[:, 0, 0])
    assert np.max(np.linalg.svd(mixed.network.s, compute_uv=False)) <= 1+1e-10


@pytest.mark.parametrize('cores', [[], {'unknown': CORE}, {'signal': [(0, 0)]},
    {'signal': ((-.2e-3, .52e-3), (.18e-3, .52e-3), (.18e-3, .58e-3), (-.2e-3, .58e-3))},
    {'signal': ((-.3e-3, .52e-3), (.3e-3, .52e-3), (.3e-3, .58e-3), (-.3e-3, .58e-3))},
    {'signal': ((0., .52e-3), (0., .55e-3), (0., .58e-3))},
    {'signal': ((-.18e-3, .52e-3), (.18e-3, .58e-3), (.18e-3, .52e-3), (-.18e-3, .58e-3))},
    {'signal': ((False, .52e-3), (.18e-3, .52e-3), (.18e-3, .58e-3))},
    {'signal': ((float('nan'), .52e-3), (.18e-3, .52e-3), (.18e-3, .58e-3))},
], ids=['not-map', 'unknown', 'short', 'touch', 'outside', 'zero-area', 'self-cross', 'boolean', 'nonfinite'])
def test_invalid_cores_rejected_before_meshing(monkeypatch, cores):
    import sipi.conductor_mesh as implementation
    monkeypatch.setattr(implementation, 'generate', lambda *a, **k: pytest.fail('Invalid core meshed'))
    with pytest.raises(ValueError): volume(cores=cores)


def test_independent_piecewise_field_on_actual_core_interface(rectangular, record_property):
    sk = require_tool('scikit-fem')
    from skfem.helpers import dot, grad
    from scipy.constants import mu_0
    from scipy.sparse import bmat, csc_matrix
    from scipy.sparse.linalg import spsolve
    v, _ = rectangular
    mesh = v.mesh
    clock = Stopwatch()
    with clock('openphysics'):
        result = v.impedance([1e4], conductivity=conductivity(v), keep_fields=True)
    with clock('reference'):
        x, y = mesh.nodes[mesh.triangles].mean(axis=1).T
        # Independent physical masks do not reuse the implementation's core IDs.
        signal = (abs(x) < .2e-3) & (y > .5e-3) & (y < .6e-3)
        core = (abs(x) < .18e-3) & (y > .52e-3) & (y < .58e-3)
        ground = (abs(x) < .001) & (y > -.1e-3) & (y < 0)
        sigma = np.where(ground | core, 58e6, np.where(signal, 20e6, 0.))
        basis = sk.Basis(sk.MeshTri(mesh.nodes.T, mesh.triangles.T), sk.ElementTriP1())
        @sk.BilinearForm
        def stiffness(u, w, data):
            return dot(grad(u), grad(w))/mu_0
        @sk.BilinearForm
        def mass(u, w, data):
            return data.sigma*u*w
        @sk.LinearForm
        def load(w, data):
            return data.sigma*w
        k = sk.asm(stiffness, basis)
        m = sk.asm(mass, basis, sigma=sigma[:, None])
        q = np.column_stack([sk.asm(load, basis, sigma=np.where(mask, sigma, 0)[:, None])
                             for mask in (signal, ground)])
        d = np.diag(q.sum(axis=0))
        free = np.setdiff1d(np.arange(basis.N), v.magnetic_boundary)
        q = q[free]
        omega = 2*np.pi*1e4
        operator = bmat([[k[free][:, free]+1j*omega*m[free][:, free], csc_matrix(-q)],
                         [csc_matrix(-1j*omega*q.T), csc_matrix(d)]], format='csc')
        solved = spsolve(operator, np.r_[np.zeros(len(free)), 1., -1.])
        z = solved[-2]-solved[-1]
        az = np.zeros(mesh.num_nodes, complex)
        az[free] = solved[:-2]
        j = np.zeros(mesh.num_triangles, complex)
        for index, mask in enumerate((signal, ground)):
            j[mask] = sigma[mask]*(solved[-2+index]-1j*omega*az[mesh.triangles[mask]].mean(axis=1))
    errors = [float(np.max(abs(actual-expected))/np.max(abs(expected))) for actual, expected in
              [(result.Z[0, 0, 0], z), (result.current_density[0, :, 0], j), (result.vector_potential[0, :, 0], az)]]
    record_property('core_independent', str(dict(z_j_a_errors=errors)))
    assert max(errors) < 1e-9
    record = make_record(case='sipi-explicit-core-diffusion', physics='2D longitudinal coated-conductor current diffusion',
        api='sipi.conductor_mesh.mesh_conductor_section', discretization='conforming core/coat P1 volume field',
        tool='scikit-fem', tool_discretization='independent coordinate masks, P1 forms and augmented current constraints',
        matched=['actual mesh, rectangular core/coat interface, 58/20 MS/m, 10 kHz',
                 'same finite reference plate and Az=0 magnetic exterior, uniform permeability'],
        not_matched=['same-mesh agreement is separate from mesh/domain convergence and measured coatings'],
        observables=[observable(name, unit, 'normalized maximum difference', error, 1e-9)
            for name, unit, error in zip(('Z', 'Jz', 'Az'), ('ohm/m', 'A/m^2', 'Wb/m'), errors)],
        analytical_acceptance='test_metal_cores: exact DC, separate mesh/outer refinement and polygon area gates',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi', version=metadata.version('sipi'))
    emit(record)
