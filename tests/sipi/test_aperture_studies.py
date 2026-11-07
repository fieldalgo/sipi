# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Analytic statistics, saved capacitance goals, failure retention and replay."""
from dataclasses import replace
import numpy as np
import pytest
from scipy import stats
from scipy.constants import epsilon_0

from sipi import (RoundConductor, EllipticalAperture, ApertureSectionDocument,
                  ApertureStudyDocument, ApertureDesignDocument, CapacitanceGoalError)


def source(pair=False, *, mesh=None):
    section = (EllipticalAperture(1.2e-3, .8e-3,
        [RoundConductor('p', .28e-3, -.25e-3), RoundConductor('n', .28e-3, .25e-3)], eps_r=3.96)
        if pair else EllipticalAperture(.8e-3, .8e-3, [RoundConductor('s', .28e-3)], eps_r=3.96))
    return ApertureSectionDocument(section, mesh=mesh)


def sampling(kind='sweep', count=3):
    spec = dict(kind=kind, variables=[dict(name='eps_r', lower=3., upper=5.)])
    if kind != 'corners':
        spec['count'] = count
    if kind in ('normal', 'uniform'):
        spec['seed'] = 771
    if kind == 'normal':
        spec.update(variables=[dict(name='width', mean=.8e-3, std=.02e-3),
                               dict(name='eps_r', mean=3.96, std=.1)], correlation=[[1., .6], [.6, 1.]])
    return spec


def goal(**kw):
    options = dict(variable='conductor_0_diameter', bounds=[.2e-3, .35e-3],
                   target=200e-12, tolerance=.5e-12)
    options.update(kw)
    return ApertureDesignDocument(source(), **options)


@pytest.mark.parametrize('kind', ['sweep', 'corners', 'uniform', 'normal'])
def test_saved_sampling_is_reproducible_read_only_and_detached(kind):
    spec = sampling(kind, 100)
    doc = ApertureStudyDocument(source(), sampling=spec)
    text = doc.dumps()
    restored = ApertureStudyDocument.loads(text)
    assert restored.dumps() == text
    np.testing.assert_array_equal(doc.samples(), restored.samples())
    assert not doc.samples().flags.writeable
    spec['variables'][0]['name'] = 'bad'
    doc.to_dict()['sampling']['variables'][0]['name'] = 'bad'
    assert doc.dumps() == text
    assert doc.sample_parameters()[0]['conductor_0_diameter'] == .28e-3


def test_correlated_samples_against_independent_normal_distribution():
    spec = sampling('normal', 10000)
    doc = ApertureStudyDocument(source(), sampling=spec)
    z = (doc.samples()-[.8e-3, 3.96])/[.02e-3, .1]
    reference = stats.multivariate_normal([0., 0.], spec['correlation']).rvs(
        size=10000, random_state=np.random.default_rng(817))
    for sample in (z, reference):
        assert abs(sample.mean(axis=0)).max() < 6/np.sqrt(len(sample))
        assert abs(np.cov(sample.T)-spec['correlation']).max() < .08
        for column in sample.T:
            assert stats.kstest(column, 'norm').statistic < .03
    singular = sampling('normal', 100)
    singular['correlation'] = [[1., -1.], [-1., 1.]]
    values = ApertureStudyDocument(source(), sampling=singular).samples()
    normalized = (values-[.8e-3, 3.96])/[.02e-3, .1]
    np.testing.assert_allclose(normalized[:, 0], -normalized[:, 1], rtol=1e-10, atol=1e-12)


def test_uniform_material_sweep_statistics_match_analytic_coax_scaling():
    doc = ApertureStudyDocument(source(), sampling=sampling())
    result = doc.analyze()
    c0 = 2*np.pi*epsilon_0/np.log(.8/.28)
    assert result.failed == 0 and result.input_json == doc.dumps()
    expected = dict(minimum=3*c0, maximum=5*c0, mean=4*c0, sample_std=c0, p05=3.1*c0, p95=4.9*c0)
    for name, value in expected.items():
        assert result.summary[name] == pytest.approx(value, rel=.002)
    for row, eps in zip(result.rows, [3., 4., 5.]):
        assert row.capacitance == pytest.approx(eps*c0, rel=.002)
        assert row.document.section.eps_r == eps and row.complete
        assert row.document.analyze()[0, 0].real == pytest.approx(row.capacitance, rel=1e-12)
        with pytest.raises(TypeError):
            row.parameters['eps_r'] = 99
    with pytest.raises(TypeError):
        result.summary['mean'] = 0


@pytest.mark.parametrize('quantity', ['c11', 'c22', 'mutual', 'differential', 'common'])
def test_pair_quantity_routes_to_explicit_voltage_charge_energy(quantity):
    spec = sampling(count=2)
    doc = ApertureStudyDocument(source(pair=True), sampling=spec, quantity=quantity)
    result = doc.analyze()
    assert result.failed == 0
    for row in result.rows:
        c = row.document.analyze().real
        if quantity == 'mutual':
            expected = -(c@np.array([0., 1.]))[0]
        else:
            v = {'c11': [1., 0.], 'c22': [0., 1.], 'differential': [.5, -.5], 'common': [1., 1.]}[quantity]
            expected = np.asarray(v)@c@v
        assert row.capacitance == pytest.approx(expected, rel=1e-12)


def test_invalid_normal_geometry_is_retained_without_resampling():
    spec = dict(kind='normal', count=3, seed=771, correlation=[[1.]],
                variables=[dict(name='conductor_0_diameter', mean=-.1e-3, std=1e-9)])
    doc = ApertureStudyDocument(source(), sampling=spec)
    result = doc.analyze()
    assert result.failed == 3 and result.summary is None
    for row, sample in zip(result.rows, doc.samples()):
        assert row.parameters['conductor_0_diameter'] == sample[0]
        assert row.document is None and row.capacitance is None and row.error_type == 'ValueError'


def crossing_source():
    return ApertureSectionDocument(EllipticalAperture(1.2e-3, .8e-3,
        [RoundConductor('p', .1e-3, -.25e-3), RoundConductor('n', .1e-3, .1e-3)], eps_r=3.96))


def test_valid_bound_corners_do_not_hide_invalid_interior_geometry():
    spec = dict(kind='sweep', count=3,
                variables=[dict(name='conductor_0_x', lower=-.25e-3, upper=.35e-3)])
    result = ApertureStudyDocument(crossing_source(), sampling=spec).analyze()
    assert result.failed == 1 and result.summary is None
    assert result.rows[0].complete and result.rows[2].complete
    assert result.rows[1].error_type == 'ValueError' and 'overlap' in result.rows[1].error


def test_budget_and_bounded_invalid_corners_rejected_before_meshing(monkeypatch):
    monkeypatch.setattr(EllipticalAperture, 'mesh', lambda *a, **kw: pytest.fail('unexpected mesh'))
    with pytest.raises(ValueError, match='max_evaluations'):
        ApertureStudyDocument(source(), sampling=sampling(count=3)).analyze(max_evaluations=2)
    with pytest.raises(ValueError):
        ApertureStudyDocument(source(), sampling=dict(kind='sweep', count=3,
            variables=[dict(name='conductor_0_diameter', lower=-.1e-3, upper=.3e-3)]))


def test_saved_goal_matches_analytic_circular_diameter_and_refines():
    doc = goal()
    restored = ApertureDesignDocument.loads(doc.dumps())
    assert restored.dumps() == doc.dumps()
    result = restored.solve()
    expected = .8e-3*np.exp(-2*np.pi*epsilon_0*3.96/200e-12)
    assert abs(result.parameter/expected-1) < .005
    assert abs(result.residual) <= .5e-12 and abs(result.refined_residual) <= .5e-12
    assert result.history[-1].stage == 'refinement'
    assert result.document.section.conductors[0].diameter == result.parameter
    assert result.input_json == doc.dumps()
    print('circular C goal', result.parameter, expected, result.residual, result.refined_residual)


def test_pair_differential_goal_and_negative_offset_bounds():
    pair = ApertureDesignDocument(source(pair=True, mesh={'size':20e-6, 'angular_divisions':128}),
        variable='conductor_0_diameter', bounds=[.2e-3, .35e-3], target=130e-12,
        quantity='differential', tolerance=1e-12).solve()
    assert abs(pair.residual) <= 1e-12 and abs(pair.refined_residual) <= 1e-12
    negative = goal(variable='conductor_0_x', bounds=[-.2e-3, -.05e-3], target=250e-12,
                    tolerance=1e-12).solve()
    assert negative.parameter < 0
    assert abs(negative.residual) <= 1e-12 and abs(negative.refined_residual) <= 1e-12
    print('pair Cdd goal', pair.parameter, pair.residual, pair.refined_residual)


def test_unbracketed_and_budget_failures_preserve_completed_history():
    for doc, message in [(goal(target=1e-12), 'not bracketed'), (goal(max_evaluations=3), 'evaluation limit')]:
        with pytest.raises(CapacitanceGoalError, match=message) as caught:
            doc.solve()
        assert len(caught.value.history) == 2


def test_coarse_requested_goal_does_not_hide_refined_miss():
    coarse = source(mesh={'size':.1e-3, 'angular_divisions':16})
    doc = ApertureDesignDocument(coarse, variable='conductor_0_diameter', bounds=[.2e-3,.35e-3],
                                 target=200e-12, tolerance=1e-14)
    with pytest.raises(CapacitanceGoalError, match='refined mesh misses') as caught:
        doc.solve()
    history = caught.value.history
    assert abs(history[-2].capacitance-200e-12) <= 1e-14
    assert abs(history[-1].capacitance-200e-12) > 1e-14
    assert history[-1].stage == 'refinement'
    print('preserved coarse refinement miss', history[-2:], caught.value.parameter)


def test_intermediate_invalid_goal_geometry_preserves_failed_parameter():
    base = crossing_source()
    left = base.analyze()[0,0].real
    shifted = base.to_dict(); shifted['conductors'][0]['x'] = .35e-3
    right = ApertureSectionDocument.from_dict(shifted).analyze()[0,0].real
    target = (left+right)/2
    doc = ApertureDesignDocument(base, variable='conductor_0_x', bounds=[-.25e-3,.35e-3],
                                 target=target, tolerance=abs(left-right)/1000)
    with pytest.raises(CapacitanceGoalError, match='overlap') as caught:
        doc.solve()
    assert caught.value.parameter == pytest.approx(.05e-3)
    assert len(caught.value.history) == 2


@pytest.mark.parametrize('edit', [
    lambda d:d.update(schema='sipi.aperture-study/2'), lambda d:d.update(extra=1),
    lambda d:d.update(quantity='z_diff'), lambda d:d.update(quantity='c22'),
    lambda d:d['sampling'].update(count=True), lambda d:d['sampling'].update(count=1),
    lambda d:d['sampling']['variables'][0].update(name='conductor_2_x'),
    lambda d:d['sampling']['variables'][0].update(lower=True), lambda d:d['sampling'].update(seed=1),
    lambda d:d['section'].update(length_unit='mm')])
def test_invalid_study_input(edit):
    data = ApertureStudyDocument(source(), sampling=sampling()).to_dict()
    edit(data)
    with pytest.raises(ValueError):
        ApertureStudyDocument.from_dict(data)


@pytest.mark.parametrize('edit', [
    lambda d:d.update(schema='sipi.aperture-design/2'), lambda d:d.update(extra=1),
    lambda d:d.update(variable='unknown'), lambda d:d.update(bounds=[1]),
    lambda d:d.update(bounds=[.35e-3,.2e-3]), lambda d:d.update(bounds=[True,.35e-3]),
    lambda d:d.update(target_f_per_m=0), lambda d:d.update(target_f_per_m=float('nan')),
    lambda d:d.update(tolerance_f_per_m=-1), lambda d:d.update(max_evaluations=True),
    lambda d:d.update(quantity='z0')])
def test_invalid_goal_input(edit):
    data = goal().to_dict(); edit(data)
    with pytest.raises(ValueError):
        ApertureDesignDocument.from_dict(data)


@pytest.mark.parametrize('cls', [ApertureStudyDocument, ApertureDesignDocument])
@pytest.mark.parametrize('text', ['{"schema":1,"schema":2}', '{"x":NaN}', '{"x":Infinity}', '[]'])
def test_strict_json(cls, text):
    with pytest.raises(ValueError):
        cls.loads(text)
