# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Coplanar pair geometry, independent image-charge integral and FEM convergence."""
import numpy as np
import pytest
from scipy.constants import epsilon_0, c
from scipy.integrate import quad
from scipy.linalg import solve
from scipy.special import xlogy

from sipi import CrossSectionDocument, coupled_grounded_coplanar, seek_impedance
from sipi.study import ImpedanceStudyDocument

PARAMS = dict(width=.5e-3, gap=.3e-3, ground_gap=.2e-3, ground_width=1e-3,
              substrate_height=.5e-3, eps_r=1, air_height=6e-3, box_width=12e-3)
COARSE = dict(edge_size=8e-6, far_size=.25e-3, grade=.3)
FINE = dict(edge_size=2e-6, far_size=.125e-3, grade=.15)


def image_primitive(u, height):
    """Integral of log(sqrt(u**2+(2h)**2)/abs(u)); u and h share units."""
    a = 2*height
    return .5*u*np.log(u*u+a*a)-xlogy(u, abs(u))+a*np.arctan(u/a)


def panel_reference(intervals, height, count):
    """Independent zero-thickness vacuum strips over an infinite ground plane.

    Piecewise constant charge, midpoint collocation, analytic image-Green panel
    integrals, cosine edge clustering. No SIPI geometry, mesh or solver is used.
    All lengths are divided by height to avoid unit-dependent logarithms.
    Return charges/voltages of all strips; grounds are subsequently set to 0 V.
    """
    left, right, owners = [], [], []
    unit = .5*(1-np.cos(np.linspace(0, np.pi, count+1)))
    for i, (lo, hi) in enumerate(intervals):
        edges = (lo+(hi-lo)*unit)/height
        left.extend(edges[:-1]); right.extend(edges[1:]); owners.extend([i]*count)
    left, right, owners = np.array(left), np.array(right), np.array(owners)
    mid = (left+right)/2
    matrix = (image_primitive(right[None, :]-mid[:, None], 1)
              - image_primitive(left[None, :]-mid[:, None], 1))/(right-left)
    voltages = (owners[:, None] == np.arange(len(intervals))).astype(float)
    charges = solve(matrix, 2*np.pi*epsilon_0*voltages)
    return np.array([charges[owners == i].sum(axis=0) for i in range(len(intervals))])


def reference_modes(count):
    # Explicit intervals from the stated dimensions, independent of the factory.
    cap = panel_reference([(-.65e-3, -.15e-3), (.15e-3, .65e-3),
                           (-1.85e-3, -.85e-3), (.85e-3, 1.85e-3)], .5e-3, count)
    return 1/(c*np.array([cap[0, 0]+cap[0, 1], cap[0, 0]-cap[0, 1]]))


@pytest.mark.parametrize('left,right', [(-.2, .2), (.1, .8), (-2, -.1)])
def test_image_integral_matches_independent_quadrature(left, right):
    expected = quad(lambda u: .5*np.log1p(4/u**2), left, right,
                    points=[0] if left < 0 < right else None, epsabs=1e-12)[0]
    assert image_primitive(right, 1)-image_primitive(left, 1) == pytest.approx(expected, rel=1e-11)


def test_panel_reference_reciprocity_scaling_and_resolution():
    intervals = [(-.65, -.15), (.15, .65), (-1.85, -.85), (.85, 1.85)]
    cap = panel_reference(intervals, .5, 80)
    np.testing.assert_allclose(cap, cap.T, rtol=1e-4)
    assert np.linalg.eigvalsh((cap+cap.T)/2).min() > 0
    np.testing.assert_allclose(panel_reference(np.array(intervals)*1e-3, .5e-3, 80), cap, rtol=1e-10)
    np.testing.assert_allclose(reference_modes(80), reference_modes(160), rtol=.003)


def test_panel_normalization_matches_single_microstrip_reference():
    # Remove coplanar grounds and the second signal: the independent standard
    # microstrip formula provides a normalization check, using its existing 1% gate.
    from test_sipi_references import hammerstad_jensen
    capacitance = panel_reference([(-.25e-3, .25e-3)], .5e-3, 160)[0, 0]
    assert 1/(c*capacitance) == pytest.approx(hammerstad_jensen(1, 1)[0], rel=.01)


def test_coplanar_pair_matches_image_integral_with_mesh_and_domain_convergence():
    exact = reference_modes(160)
    results = []
    for mesh in (COARSE, FINE):
        line = coupled_grounded_coplanar(**PARAMS).analyze(**mesh)
        modes = line.even_odd()
        results.append(np.array([modes['z_even'], modes['z_odd']]))
        assert line.names == ('positive', 'negative')
        np.testing.assert_allclose(line.C, line.C0, rtol=1e-12)
    errors = [abs(values/exact-1) for values in results]
    assert np.all(errors[-1] < .02)
    assert np.all(errors[-1] < errors[0])
    wide = coupled_grounded_coplanar(**dict(PARAMS, box_width=24e-3, air_height=12e-3)).analyze(**FINE).even_odd()
    expanded = np.array([wide['z_even'], wide['z_odd']])
    np.testing.assert_allclose(expanded, results[-1], rtol=.01)
    print('reference modes', exact, 'FEM', results, 'relative errors', errors, 'expanded', expanded)


def test_geometry_ground_positions_taper_and_document_roundtrip():
    section = coupled_grounded_coplanar(**dict(PARAMS, eps_r=4), thickness=.035e-3, top_width=.4e-3)
    assert [t.ground for t in section.traces] == [False, False, True, True]
    np.testing.assert_allclose([t.x for t in section.traces], [-.4e-3, .4e-3, -1.35e-3, 1.35e-3], rtol=1e-15)
    assert section.traces[0].top_width == .4e-3
    assert section.traces[2].top_width is None
    doc = CrossSectionDocument(section, mesh=COARSE)
    restored = CrossSectionDocument.loads(doc.dumps())
    assert doc.dumps() == restored.dumps()
    np.testing.assert_array_equal(doc.analyze().C, restored.analyze().C)


@pytest.mark.parametrize('change', [dict(gap=0), dict(ground_gap=-1), dict(ground_width=True),
    dict(box_width=3e-3), dict(air_height=0), dict(thickness=-1),
    dict(thickness=.035e-3, top_width=1e-3), dict(ground_gap=float('nan'))])
def test_invalid_coplanar_dimensions_are_rejected(change):
    with pytest.raises(ValueError):
        coupled_grounded_coplanar(**dict(PARAMS, **change))


@pytest.mark.parametrize('kind', ['sweep', 'corners', 'uniform', 'normal'])
def test_coplanar_study_json_and_fixed_pitch(kind):
    spec = dict(kind=kind, variables=[dict(name='width', lower=.45e-3, upper=.55e-3)])
    if kind != 'corners': spec['count'] = 2
    if kind in ('uniform', 'normal'): spec['seed'] = 221
    if kind == 'normal':
        spec['variables'] = [dict(name='width', mean=.5e-3, std=.01e-3)]
        spec['correlation'] = [[1]]
    plan = ImpedanceStudyDocument('coupled_grounded_coplanar', PARAMS, sampling=spec,
        quantity='z_diff', fixed_pitch_m=.8e-3, mesh=COARSE)
    replay = ImpedanceStudyDocument.loads(plan.dumps())
    np.testing.assert_array_equal(plan.samples(), replay.samples())
    for params in replay.sample_parameters():
        section = coupled_grounded_coplanar(**params)
        np.testing.assert_allclose([t.x for t in section.traces[:2]], [-.4e-3, .4e-3], rtol=1e-15)
        assert section.traces[3].x0-section.traces[1].x1 == pytest.approx(.2e-3, rel=1e-12)
    if kind == 'sweep':
        result = replay.analyze()
        assert result.failed == 0 and result.summary is not None


def test_coplanar_width_goal_has_separate_mesh_confirmation():
    # Target is derived from the independent integral, not a FEM-generated golden.
    target = 2*reference_modes(160)[1]
    result = seek_impedance(lambda width: coupled_grounded_coplanar(**dict(PARAMS, width=width)),
                            (.4e-3, .6e-3), target, quantity='z_diff', tolerance=1.0, mesh=FINE)
    assert abs(result.residual) <= 1.0 and abs(result.refined_residual) <= 1.0
    assert result.history[-1].stage == 'refinement'
    assert result.parameter == pytest.approx(.5e-3, rel=.04)


def test_coplanar_study_requires_differential_quantity():
    with pytest.raises(ValueError, match='quantity=z_diff'):
        ImpedanceStudyDocument('coupled_grounded_coplanar', PARAMS, quantity='z0',
            sampling=dict(kind='sweep', count=2,
                          variables=[dict(name='width', lower=.45e-3, upper=.55e-3)]))
