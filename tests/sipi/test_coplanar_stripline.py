# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Buried coplanar geometry, independent fields and saved manufacturing studies."""
from dataclasses import replace
from importlib import metadata
import json

import numpy as np
import pytest

from sipi import (CrossSection, CrossSectionDocument, Layer, Trace,
                  coplanar_stripline, coupled_coplanar_stripline, ImpedanceDesignDocument)
from sipi.templates import offset_stripline, coupled_stripline
from sipi.constants import epsilon_0, mu_0
from sipi.study import ImpedanceStudyDocument
from sipi.dielectric import ConstantDielectric
from sipi.execution import execute_saved, normalize_saved
from sipi.yield_assessment import ImpedanceYieldDocument
from crosscheck import require_tool, Stopwatch, make_record, observable, emit

PAIR = dict(width=.3e-3, gap=.3e-3, ground_gap=.3e-3, ground_width=.8e-3,
    plane_spacing=1e-3, trace_height=.4e-3, eps_r=4., thickness=35e-6,
    tan_delta=.02, box_width=6e-3)
SINGLE = {k: v for k, v in PAIR.items() if k != 'ground_gap'}
COARSE = dict(edge_size=10e-6, far_size=.25e-3, grade=.3)
FINE = dict(edge_size=5e-6, far_size=.125e-3, grade=.15)


def section(pair=True, **changes):
    return (coupled_coplanar_stripline if pair else coplanar_stripline)(
        **dict(PAIR if pair else SINGLE, **changes))


def study(pair=True, **changes):
    kwargs = dict(quantity='z_diff' if pair else 'z0', mesh=COARSE,
        sampling=dict(kind='uniform', count=2, seed=17,
            variables=[dict(name='width', lower=.28e-3, upper=.32e-3)]))
    kwargs.update(changes)
    return ImpedanceStudyDocument('coupled_coplanar_stripline' if pair else 'coplanar_stripline',
                                  PAIR if pair else SINGLE, **kwargs)


@pytest.mark.parametrize('pair', [False, True])
def test_explicit_geometry_and_saved_roundtrip(pair):
    s = section(pair)
    signals = ([Trace('positive', -.3e-3, .3e-3, .4e-3, 35e-6),
                Trace('negative', .3e-3, .3e-3, .4e-3, 35e-6)] if pair else
               [Trace('signal', 0., .3e-3, .4e-3, 35e-6)])
    offset = 1.15e-3 if pair else .85e-3
    explicit = CrossSection([Layer('dielectric', 1e-3, 4., .02)], signals +
        [Trace('ground_left', -offset, .8e-3, .4e-3, 35e-6, ground=True),
         Trace('ground_right', offset, .8e-3, .4e-3, 35e-6, ground=True)], 6e-3, top='ground')
    a, b = CrossSectionDocument(s, mesh=COARSE), CrossSectionDocument(explicit, mesh=COARSE)
    # Decimal construction can differ by a final binary digit.
    np.testing.assert_allclose([[t.x, t.y, t.width, t.thickness] for t in s.traces],
                              [[t.x, t.y, t.width, t.thickness] for t in explicit.traces], rtol=1e-15)
    assert [t.name for t in s.traces] == [t.name for t in explicit.traces]
    assert [t.ground for t in s.traces] == [t.ground for t in explicit.traces]
    assert a.to_dict()['layers'] == b.to_dict()['layers']
    assert CrossSectionDocument.loads(a.dumps()).dumps() == a.dumps()
    default = section(pair, box_width=None)
    assert default.width >= 12*default.height
    assert default.traces[-1].x+default.traces[-1].width/2 < default.width/2
    tapered = section(pair, top_width=.2e-3)
    assert all(t.top_width == .2e-3 for t in tapered.traces if not t.ground)
    assert all(t.top_width is None for t in tapered.traces if t.ground)
    assert all(t.thickness == 0. for t in section(pair, thickness=0.).traces)


@pytest.mark.parametrize('pair', [False, True])
@pytest.mark.parametrize('change', [dict(width=0), dict(gap=0), dict(ground_width=0),
    dict(ground_width=True), dict(ground_width=float('inf')), dict(trace_height=None),
    dict(trace_height=0), dict(trace_height=.98e-3), dict(plane_spacing=0),
    dict(thickness=-1), dict(thickness=True), dict(eps_r=.5), dict(tan_delta=-.1),
    dict(box_width=2e-3), dict(top_width=3e-3)])
def test_invalid_geometry_and_clipping_reject(pair, change):
    with pytest.raises(ValueError): section(pair, **change)


@pytest.mark.parametrize('value', [0, -1, True, None, float('nan')])
def test_pair_ground_gap_rejects_invalid_values(value):
    with pytest.raises(ValueError): section(ground_gap=value)


@pytest.fixture(scope='module', params=[False, True], ids=['single', 'pair'])
def fields(request):
    pair = request.param
    mesh = section(pair).mesh(**COARSE)
    return pair, mesh, mesh.line_parameters(), section(pair).analyze(**FINE), section(pair, box_width=12e-3).analyze(**FINE)


def impedance(result):
    return result.z0 if len(result.C) == 1 else result.z_diff_forward


def test_independent_complex_and_vacuum_energy(fields):
    skfem = require_tool('scikit-fem')
    from skfem.helpers import dot, grad
    pair, m, _, _, _ = fields
    clock = Stopwatch()
    with clock('openphysics'): actual = m.line_parameters()
    with clock('reference'):
        basis = skfem.Basis(skfem.MeshTri(m.mesh.nodes.T, m.mesh.triangles.T), skfem.ElementTriP1())
        @skfem.BilinearForm(dtype=complex)
        def form(u, v, w): return w.eps*dot(grad(u), grad(v))
        fixed = np.unique(np.concatenate([m.ground, *m.signals.values()]))
        expected = []
        for eps in (m.eps_r*(1-1j*m.tan_delta), np.ones_like(m.eps_r)):
            k = skfem.asm(form, basis, eps=eps[:, None]); solutions = []
            for nodes in m.signals.values():
                v = np.zeros(basis.N, complex); v[nodes] = 1
                solutions.append(skfem.solve(*skfem.condense(k, np.zeros(basis.N, complex), x=v, D=fixed)))
            u = np.array(solutions).T
            expected.append(epsilon_0*(u.T@(k@u)))
    errors = [float(np.max(abs(a-b))/np.max(abs(b))) for a, b in
        [(actual.C, expected[0].real), (actual.C_loss, -expected[0].imag), (actual.C0, expected[1].real)]]
    record = make_record(case='coplanar-stripline-'+('pair' if pair else 'single'),
        physics='lossy homogeneous electrostatics', api='sipi.templates',
        discretization='conforming P1, buried signals and finite coplanar grounds between planes',
        tool='scikit-fem', tool_discretization='independent complex/vacuum P1 assembly and Dirichlet energy',
        matched=['same mesh, uniform material, grounded top/bottom and side traces, insulated side walls'],
        not_matched=['no measured material or three-dimensional return-path transition'],
        observables=[observable(name, 'F/m', 'max normalized matrix difference', error, 1e-10)
                     for name, error in zip(['C', 'C_loss', 'C0'], errors)],
        analytical_acceptance='elliptic-integral thin CPW limit and far-ground stripline reduction; separate mesh/box gates',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi', version=metadata.version('sipi')); emit(record)
    assert max(errors) < 1e-10


def test_mesh_outer_convergence_reciprocity_and_passivity(fields):
    pair, _, coarse, fine, outer = fields
    changes = []
    for other, limit in [(coarse, .015), (outer, .005)]:
        c = float(np.max(abs(other.C-fine.C))/np.max(abs(fine.C)))
        z = float(abs(impedance(other)/impedance(fine)-1))
        changes.append([c, z]); assert max(c, z) < limit
    for matrix in (fine.C, fine.C0, fine.C_loss, fine.L):
        np.testing.assert_allclose(matrix, matrix.T, rtol=1e-12)
        assert np.linalg.eigvalsh(matrix).min() > 0
    if pair: assert fine.even_odd()['z_diff'] == pytest.approx(fine.z_diff_forward, rel=.005)
    print('coplanar stripline pair', pair, 'mesh/outer C,Z', changes, 'fine ohm', impedance(fine))


def test_vertical_reflection_and_identical_mesh_material_scaling(fields):
    pair, m, _, fine, _ = fields
    mirror = section(pair, trace_height=PAIR['plane_spacing']-PAIR['trace_height']-PAIR['thickness']).analyze(**FINE)
    for attr in ('C', 'C0', 'L', 'C_loss'):
        np.testing.assert_allclose(getattr(mirror, attr), getattr(fine, attr), rtol=.005)
    assert impedance(mirror) == pytest.approx(impedance(fine), rel=.005)
    a = replace(m, eps_r=np.full_like(m.eps_r, 2.), tan_delta=np.full_like(m.tan_delta, .02)).line_parameters()
    b = replace(m, eps_r=np.full_like(m.eps_r, 8.), tan_delta=np.full_like(m.tan_delta, .02)).line_parameters()
    np.testing.assert_allclose(b.C, 4*a.C, rtol=1e-12)
    np.testing.assert_allclose(b.C_loss, .02*b.C, rtol=1e-12)
    np.testing.assert_array_equal(b.C0, a.C0)
    assert impedance(b) == pytest.approx(impedance(a)/2, rel=1e-12)


@pytest.mark.parametrize('pair', [False, True])
def test_far_side_ground_limit_reduces_to_stripline(pair):
    params = dict(PAIR if pair else SINGLE, box_width=16e-3, ground_width=.5e-3, tan_delta=0.)
    params['ground_gap' if pair else 'gap'] = 5e-3
    new = (coupled_coplanar_stripline if pair else coplanar_stripline)(**params).analyze(**FINE)
    old = (coupled_stripline if pair else offset_stripline)(**{k: v for k, v in params.items()
        if k not in ('ground_width', 'ground_gap' if pair else 'gap')}).analyze(**FINE)
    error_c = np.max(abs(new.C-old.C))/np.max(abs(old.C))
    error_z = abs(impedance(new)/impedance(old)-1)
    print('far-ground limit', pair, error_c, error_z)
    assert max(error_c, error_z) < .02


def test_thin_homogeneous_cpw_elliptic_integral_limit():
    require_tool('scipy')
    from scipy.special import ellipk
    w, gap = 1e-3, .5e-3; k = w/(w+2*gap)
    target_c = 4*epsilon_0*4*ellipk(k*k)/ellipk(1-k*k)
    target_z = np.sqrt(mu_0/epsilon_0)/8*ellipk(1-k*k)/ellipk(k*k)
    s = coplanar_stripline(width=w, gap=gap, ground_width=20*w, plane_spacing=40*w,
                           trace_height=20*w, eps_r=4., box_width=100*w)
    errors = []
    for edge, far, grade in [(w/50, w, .2), (w/100, w/2, .1)]:
        r = s.analyze(edge_size=edge, far_size=far, grade=grade)
        errors.append([float(abs(r.C[0, 0]/target_c-1)), float(abs(r.z0/target_z-1))])
    print('thin homogeneous CPW C,Z errors', errors)
    assert max(errors[-1]) < .02
    assert all(b < a for a, b in zip(errors[0], errors[1]))


@pytest.mark.parametrize('pair', [False, True])
def test_saved_iid_yield_and_material_binding_replay(pair):
    doc = study(pair)
    assert normalize_saved(doc.dumps()) == doc.dumps()
    report = execute_saved(ImpedanceYieldDocument(doc, minimum=1., maximum=1000.).dumps(), max_evaluations=2)
    assert report['status'] == 'complete' and report['result']['passed'] == 2
    for row in report['result']['rows']:
        direct = (coupled_coplanar_stripline if pair else coplanar_stripline)(**row['parameters']).analyze(**COARSE)
        expected = direct.even_odd()['z_diff'] if pair else direct.z0
        assert row['impedance_ohm'] == pytest.approx(expected, rel=1e-12)
    material = study(pair, frequency=1e9, materials={'dielectric': ConstantDielectric(4.)},
        material_variables={'dk': dict(region='dielectric', path=['eps_r'])},
        sampling=dict(kind='uniform', count=2, seed=18, variables=[dict(name='dk', lower=3.8, upper=4.2)]))
    out = execute_saved(material.dumps(), max_evaluations=2)
    assert out['status'] == 'complete'
    assert all('dielectric' in row['material_evaluation']['materials'] for row in out['result']['rows'])
    json.dumps(out, allow_nan=False)


def test_fixed_pitch_correlated_normal_and_failed_rows():
    doc = study(fixed_pitch_m=.6e-3, sampling=dict(kind='normal', count=3, seed=17,
        variables=[dict(name='width', mean=.3e-3, std=.01e-3),
                   dict(name='ground_gap', mean=.3e-3, std=.02e-3)], correlation=[[1., .6], [.6, 1.]]))
    assert ImpedanceStudyDocument.loads(doc.dumps()).dumps() == doc.dumps()
    for params in doc.sample_parameters():
        s = coupled_coplanar_stripline(**params); a, b, _, right_ground = s.traces
        assert b.x-a.x == pytest.approx(.6e-3, rel=1e-12)
        assert right_ground.x-right_ground.width/2-(b.x+b.width/2) == pytest.approx(params['ground_gap'], rel=1e-12)
    invalid = study(sampling=dict(kind='normal', count=2, seed=18, correlation=[[1.]],
        variables=[dict(name='ground_gap', mean=-.1e-3, std=1e-9)]))
    out = invalid.analyze()
    assert out.failed == 2 and len(out.rows) == 2
    assert all(row.document is None and row.error_type == 'ValueError' for row in out.rows)
    for kwargs in [dict(quantity='z0'), dict(fixed_plane_spacing_m=1e-3)]:
        with pytest.raises(ValueError): study(**kwargs)
    for kwargs in [dict(quantity='z_diff'), dict(fixed_pitch_m=.8e-3)]:
        with pytest.raises(ValueError): study(False, **kwargs)


def test_saved_forward_quantity_replays_without_even_odd_conversion():
    doc = study(quantity='z_diff_forward')
    assert normalize_saved(doc.dumps()) == doc.dumps()
    result = doc.analyze()
    assert result.failed == 0 and result.quantity == 'z_diff_forward'
    for row in result.rows:
        expected = row.document.analyze().z_diff_forward
        assert row.impedance == pytest.approx(expected, rel=1e-12)


def test_saved_fixed_pitch_width_goal_and_refined_acceptance():
    doc = ImpedanceDesignDocument('coupled_coplanar_stripline', dict(PAIR, gap=.5e-3),
        variable='width', bounds=[.15e-3, .65e-3], target=100., quantity='z_diff',
        fixed_pitch_m=.8e-3, tolerance=.5, max_evaluations=24, mesh=FINE)
    assert normalize_saved(doc.dumps()) == doc.dumps()
    result = doc.solve()
    assert abs(result.residual) <= .5 and abs(result.refined_residual) <= .5
    assert .15e-3 <= result.parameter <= .65e-3
    print('100-ohm coplanar pair width', result.parameter, 'residual/refined', result.residual, result.refined_residual)
