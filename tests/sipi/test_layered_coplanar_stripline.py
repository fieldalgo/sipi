# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Two-dielectric buried coplanar fields, limits and constrained saved studies."""
from dataclasses import replace
from importlib import metadata
import json

import numpy as np
import pytest

from sipi import (CrossSection, CrossSectionDocument, Layer, Trace,
                  layered_coplanar_stripline, coupled_layered_coplanar_stripline,
                  coplanar_stripline, coupled_coplanar_stripline, ImpedanceDesignDocument)
from sipi.constants import epsilon_0, mu_0
from sipi.study import ImpedanceStudyDocument
from sipi.dielectric import ConstantDielectric
from sipi.execution import execute_saved, normalize_saved
from sipi.yield_assessment import ImpedanceYieldDocument
from crosscheck import require_tool, Stopwatch, make_record, observable, emit

PAIR = dict(width=.3e-3, gap=.3e-3, ground_gap=.3e-3, ground_width=.8e-3,
    lower_height=.4e-3, upper_height=.6e-3, lower_eps_r=3., upper_eps_r=5.,
    thickness=35e-6, lower_tan_delta=.01, upper_tan_delta=.03, box_width=6e-3)
SINGLE = {k: v for k, v in PAIR.items() if k != 'ground_gap'}
COARSE = dict(edge_size=10e-6, far_size=.25e-3, grade=.3)
FINE = dict(edge_size=5e-6, far_size=.125e-3, grade=.15)


def factory(pair):
    return coupled_layered_coplanar_stripline if pair else layered_coplanar_stripline


def section(pair=True, **changes):
    return factory(pair)(**dict(PAIR if pair else SINGLE, **changes))


def impedance(line):
    return line.z_diff_forward if len(line.C) == 2 else line.z0


def study(pair=True, **changes):
    kwargs = dict(quantity='z_diff' if pair else 'z0', mesh=COARSE,
        sampling=dict(kind='uniform', count=2, seed=17,
            variables=[dict(name='width', lower=.28e-3, upper=.32e-3)]))
    kwargs.update(changes)
    return ImpedanceStudyDocument(factory(pair).__name__, PAIR if pair else SINGLE, **kwargs)


@pytest.mark.parametrize('pair', [False, True])
def test_explicit_interface_geometry_and_roundtrip(pair):
    s = section(pair, top_width=.2e-3)
    signals = ([Trace('positive', -.3e-3, .3e-3, .4e-3, 35e-6, top_width=.2e-3),
                Trace('negative', .3e-3, .3e-3, .4e-3, 35e-6, top_width=.2e-3)] if pair else
               [Trace('signal', 0., .3e-3, .4e-3, 35e-6, top_width=.2e-3)])
    offset = 1.15e-3 if pair else .85e-3
    explicit = CrossSection([Layer('lower', .4e-3, 3., .01), Layer('upper', .6e-3, 5., .03)], signals +
        [Trace('ground_left', -offset, .8e-3, .4e-3, 35e-6, ground=True),
         Trace('ground_right', offset, .8e-3, .4e-3, 35e-6, ground=True)], 6e-3, top='ground')
    np.testing.assert_allclose([[t.x, t.y, t.width, t.thickness] for t in s.traces],
                              [[t.x, t.y, t.width, t.thickness] for t in explicit.traces], rtol=1e-15)
    assert s.layers == explicit.layers and s.height == pytest.approx(1e-3, rel=1e-15)
    assert all(t.y == .4e-3 and t.y1 < s.height for t in s.traces)
    assert all(t.top_width == (.2e-3 if not t.ground else None) for t in s.traces)
    doc = CrossSectionDocument(s, mesh=COARSE)
    assert CrossSectionDocument.loads(doc.dumps()).dumps() == doc.dumps()
    default = section(pair, box_width=None)
    assert default.width >= 12*default.height
    assert default.traces[-1].xmax < default.width/2


@pytest.mark.parametrize('pair', [False, True])
@pytest.mark.parametrize('change', [dict(width=0), dict(gap=0), dict(ground_width=0),
    dict(ground_width=True), dict(lower_height=0), dict(upper_height=0),
    dict(upper_height=35e-6), dict(upper_height=30e-6), dict(thickness=-1),
    dict(lower_eps_r=.5), dict(upper_eps_r=True), dict(lower_tan_delta=-.1),
    dict(upper_tan_delta=float('nan')), dict(box_width=2e-3), dict(top_width=3e-3)])
def test_invalid_geometry_and_coefficients(pair, change):
    with pytest.raises(ValueError): section(pair, **change)


@pytest.mark.parametrize('gap', [0, -1, True, None, float('nan')])
def test_invalid_outer_pair_gap(gap):
    with pytest.raises(ValueError): section(ground_gap=gap)


@pytest.fixture(scope='module', params=[False, True], ids=['single', 'pair'])
def fields(request):
    pair = request.param; m = section(pair).mesh(**COARSE)
    return pair, m, m.line_parameters(), section(pair).analyze(**FINE), section(pair, box_width=12e-3).analyze(**FINE)


def test_independent_piecewise_complex_and_vacuum_energy(fields):
    skfem = require_tool('scikit-fem')
    from skfem.helpers import dot, grad
    pair, m, _, _, _ = fields; clock = Stopwatch()
    with clock('openphysics'): actual = m.line_parameters()
    with clock('reference'):
        basis = skfem.Basis(skfem.MeshTri(m.mesh.nodes.T, m.mesh.triangles.T), skfem.ElementTriP1())
        @skfem.BilinearForm(dtype=complex)
        def form(u, v, w): return w.eps*dot(grad(u), grad(v))
        fixed = np.unique(np.concatenate([m.ground, *m.signals.values()]))
        expected = []
        for eps in (m.eps_r*(1-1j*m.tan_delta), np.ones_like(m.eps_r)):
            k = skfem.asm(form, basis, eps=eps[:, None]); columns = []
            for nodes in m.signals.values():
                v = np.zeros(basis.N, complex); v[nodes] = 1
                columns.append(skfem.solve(*skfem.condense(k, np.zeros(basis.N, complex), x=v, D=fixed)))
            u = np.array(columns).T; expected.append(epsilon_0*(u.T@(k@u)))
    errors = [float(np.max(abs(a-b))/np.max(abs(b))) for a, b in
        [(actual.C, expected[0].real), (actual.C_loss, -expected[0].imag), (actual.C0, expected[1].real)]]
    record = make_record(case='layered-coplanar-stripline-'+('pair' if pair else 'single'),
        physics='piecewise lossy electrostatics', api='sipi.templates',
        discretization='conforming P1, buried coplanar traces at a two-material interface',
        tool='scikit-fem', tool_discretization='independent piecewise complex/vacuum P1 assembly and energy',
        matched=['same mesh and interface coefficients, grounded planes/side traces and insulated walls'],
        not_matched=['no measured material or three-dimensional ground connection'],
        observables=[observable(name, 'F/m', 'max normalized matrix difference', error, 1e-10)
                     for name, error in zip(['C', 'C_loss', 'C0'], errors)],
        analytical_acceptance='two-half-space thin CPW limit, uniform reduction, thin reflection, separate mesh/box gates',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi', version=metadata.version('sipi')); emit(record)
    assert max(errors) < 1e-10


def test_convergence_passivity_and_uniform_material_scaling(fields):
    pair, m, coarse, fine, outer = fields; changes = []
    for other, limit in [(coarse, .015), (outer, .005)]:
        error = [float(np.max(abs(other.C-fine.C))/np.max(abs(fine.C))),
                 float(abs(impedance(other)/impedance(fine)-1))]
        changes.append(error); assert max(error) < limit
    for matrix in (fine.C, fine.C0, fine.L, fine.C_loss):
        np.testing.assert_allclose(matrix, matrix.T, rtol=1e-12)
        assert np.linalg.eigvalsh(matrix).min() > 0
    a = m.line_parameters(); b = replace(m, eps_r=4*m.eps_r).line_parameters()
    np.testing.assert_allclose(b.C, 4*a.C, rtol=1e-12)
    np.testing.assert_allclose(b.C_loss, 4*a.C_loss, rtol=1e-12)
    np.testing.assert_array_equal(a.C0, b.C0)
    assert impedance(b) == pytest.approx(impedance(a)/2, rel=1e-12)
    common_loss = replace(m, tan_delta=np.full_like(m.tan_delta, .02)).line_parameters()
    np.testing.assert_allclose(common_loss.C_loss, .02*common_loss.C, rtol=1e-12)
    print('layered coplanar pair', pair, 'mesh/outer C,Z', changes, 'fine ohm', impedance(fine))


@pytest.mark.parametrize('pair', [False, True])
def test_equal_materials_reduce_to_homogeneous_template(pair):
    new = section(pair, lower_eps_r=4., upper_eps_r=4., lower_tan_delta=.02, upper_tan_delta=.02).analyze(**FINE)
    p = {k: v for k, v in (PAIR if pair else SINGLE).items()
         if k not in ('lower_height', 'upper_height', 'lower_eps_r', 'upper_eps_r', 'lower_tan_delta', 'upper_tan_delta')}
    old = (coupled_coplanar_stripline if pair else coplanar_stripline)(**p,
        plane_spacing=1e-3, trace_height=.4e-3, eps_r=4., tan_delta=.02).analyze(**FINE)
    error = [float(np.max(abs(new.C-old.C))/np.max(abs(old.C))), float(abs(impedance(new)/impedance(old)-1))]
    print('layered homogeneous reduction', pair, error)
    assert max(error) < .005


@pytest.mark.parametrize('pair', [False, True])
def test_zero_thickness_vertical_reflection_swaps_materials(pair):
    a = section(pair, thickness=0.).analyze(**FINE)
    b = section(pair, thickness=0., lower_height=.6e-3, upper_height=.4e-3,
        lower_eps_r=5., upper_eps_r=3., lower_tan_delta=.03, upper_tan_delta=.01).analyze(**FINE)
    # Finite copper extends only into the upper layer; that geometry is not
    # invariant under swapping the two layer heights/materials.
    for attr in ('C', 'C0', 'L', 'C_loss'):
        np.testing.assert_allclose(getattr(a, attr), getattr(b, attr), rtol=.005)
    assert impedance(a) == pytest.approx(impedance(b), rel=.005)


def test_two_half_space_thin_cpw_elliptic_integral_limit():
    require_tool('scipy')
    from scipy.special import ellipk
    w, gap = 1e-3, .5e-3; k = w/(w+2*gap)
    eps, eps_loss = (2.+6.)/2, (2.*.01+6.*.03)/2
    factor = 4*epsilon_0*ellipk(k*k)/ellipk(1-k*k)
    target = np.array([factor*eps, factor*eps_loss,
        np.sqrt(mu_0/epsilon_0)/(4*np.sqrt(eps))*ellipk(1-k*k)/ellipk(k*k)])
    s = section(False, width=w, gap=gap, ground_width=20*w, lower_height=20*w, upper_height=20*w,
        thickness=0., lower_eps_r=2., upper_eps_r=6., lower_tan_delta=.01, upper_tan_delta=.03, box_width=100*w)
    errors = []
    for edge, far, grade in [(w/50, w, .2), (w/100, w/2, .1)]:
        line = s.analyze(edge_size=edge, far_size=far, grade=grade)
        errors.append(abs(np.array([line.C[0, 0], line.C_loss[0, 0], line.z0])/target-1).tolist())
    print('two-half-space CPW C,Closs,Z errors', errors)
    assert max(errors[-1]) < .02
    assert all(b < a for a, b in zip(errors[0], errors[1]))


@pytest.mark.parametrize('pair', [False, True])
@pytest.mark.parametrize('height', ['lower_height', 'upper_height'])
def test_saved_fixed_stack_height_and_actual_rows(pair, height):
    doc = study(pair, fixed_plane_spacing_m=1e-3,
        sampling=dict(kind='uniform', count=2, seed=17,
            variables=[dict(name=height, lower=.35e-3, upper=.55e-3)]))
    assert doc.to_dict()['schema'] == 'sipi.impedance-study/2'
    assert normalize_saved(doc.dumps()) == doc.dumps()
    result = doc.analyze()
    assert result.failed == 0
    for row in result.rows:
        assert row.parameters['lower_height']+row.parameters['upper_height'] == pytest.approx(1e-3, rel=1e-12)
        direct = row.document.analyze()
        expected = direct.even_odd()['z_diff'] if pair else direct.z0
        assert row.impedance == pytest.approx(expected, rel=1e-12)


def test_pitch_and_stack_constraints_compose_with_correlated_normal_sampling():
    doc = study(fixed_plane_spacing_m=1e-3, fixed_pitch_m=.6e-3,
        sampling=dict(kind='normal', count=3, seed=19, correlation=[[1., .6], [.6, 1.]],
            variables=[dict(name='lower_height', mean=.4e-3, std=.02e-3),
                       dict(name='width', mean=.3e-3, std=.01e-3)]))
    assert ImpedanceStudyDocument.loads(doc.dumps()).dumps() == doc.dumps()
    for params in doc.sample_parameters():
        s = factory(True)(**params)
        assert s.height == pytest.approx(1e-3, rel=1e-12)
        assert s.traces[1].x-s.traces[0].x == pytest.approx(.6e-3, rel=1e-12)
        assert s.traces[-1].x0-s.traces[1].x1 == pytest.approx(params['ground_gap'], rel=1e-12)
    bad = study(fixed_plane_spacing_m=1e-3,
        sampling=dict(kind='normal', count=2, seed=19, correlation=[[1.]],
            variables=[dict(name='lower_height', mean=1.1e-3, std=1e-9)]))
    out = bad.analyze()
    assert out.failed == 2 and len(out.rows) == 2
    assert all(row.error_type == 'ValueError' and row.document is None for row in out.rows)
    with pytest.raises(ValueError): study(False, fixed_pitch_m=.6e-3)
    with pytest.raises(ValueError): study(fixed_plane_spacing_m=1e-3)
    with pytest.raises(ValueError): study(fixed_plane_spacing_m=2e-3,
        sampling=dict(kind='sweep', count=2, variables=[dict(name='lower_height', lower=.3e-3, upper=.5e-3)]))


@pytest.mark.parametrize('pair', [False, True])
def test_saved_material_binding_and_iid_yield(pair):
    doc = study(pair, quantity='z_diff_forward' if pair else 'z0', frequency=1e9,
        materials={'lower': ConstantDielectric(3.), 'upper': ConstantDielectric(5.)},
        material_variables={'upper_dk': dict(region='upper', path=['eps_r'])},
        sampling=dict(kind='uniform', count=2, seed=17,
            variables=[dict(name='upper_dk', lower=4.8, upper=5.2)]))
    assert normalize_saved(doc.dumps()) == doc.dumps()
    direct = doc.analyze()
    out = execute_saved(ImpedanceYieldDocument(doc, minimum=1., maximum=1000.).dumps(), max_evaluations=2)
    assert out['status'] == 'complete' and out['result']['passed'] == 2
    for row, expected in zip(out['result']['rows'], direct.rows):
        assert row['impedance_ohm'] == pytest.approx(expected.impedance, rel=1e-12)
        assert set(row['material_evaluation']['materials']) == {'lower', 'upper'}
    json.dumps(out, allow_nan=False)


def test_fixed_pitch_100ohm_width_goal_on_both_meshes():
    doc = ImpedanceDesignDocument(factory(True).__name__, dict(PAIR, gap=.5e-3),
        variable='width', bounds=[.15e-3, .65e-3], target=100., quantity='z_diff',
        fixed_pitch_m=.8e-3, tolerance=.5, max_evaluations=24, mesh=FINE)
    assert normalize_saved(doc.dumps()) == doc.dumps()
    result = doc.solve()
    assert abs(result.residual) <= .5 and abs(result.refined_residual) <= .5
    print('layered coplanar 100ohm width', result.parameter, 'residual/refined', result.residual, result.refined_residual)
