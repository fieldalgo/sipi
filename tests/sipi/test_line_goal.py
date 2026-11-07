# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Loss-aware goal contracts, closed-form limits, field convergence and failures."""
import json
from importlib import metadata
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.constants import epsilon_0, mu_0
from scipy.optimize import brentq

from sipi import CrossSection, CrossSectionDocument, stripline, coupled_microstrip
from sipi.line_model import TransmissionLineDocument
from sipi.line_goal import seek_line_quantity, LineQuantityGoalError
from crosscheck import require_tool, Stopwatch, emit, make_record, observable

MESH = dict(edge_size=2.5e-6, far_size=.1e-3, grade=.05)
THIN = dict(edge_size=.5e-6, far_size=.125e-3, grade=.075)


def document(width=.5e-3, *, loss=.02, metal=False, mesh=None, box=4e-3):
    section = stripline(width=width, plane_spacing=1e-3, thickness=50e-6 if metal else 0.,
                       eps_r=4., tan_delta=loss, box_width=box)
    conductor = (dict(kind='surface', conductivity=58e6, relative_permeability=1.,
                      roughness_rms=.5e-6, ground_thickness=35e-6) if metal else dict(kind='perfect'))
    return TransmissionLineDocument(CrossSectionDocument(section, mesh=MESH if mesh is None else mesh),
        [1e9], materials={}, conductor=conductor, length=0., z_ref=75.)


def test_lossy_thin_width_goal_matches_independent_cohn_root():
    from test_sipi_references import stripline_z0
    loss = .1; target = 50.
    expected = brentq(lambda width: (stripline_z0(width, 1e-3, 4.)/np.sqrt(1-1j*loss)).real-target,
                      .3e-3, .8e-3, xtol=1e-14)
    result = seek_line_quantity(lambda width: document(width, loss=loss, mesh=THIN, box=12e-3),
        [.3e-3, .8e-3], target, quantity='impedance_real', tolerance=.1, max_evaluations=24)
    assert result.parameter == pytest.approx(expected, rel=.01)
    assert max(abs(result.residual), abs(result.refined_residual)) <= .1
    assert result.unit == 'ohm'
    z = result.result.propagation().z_characteristic[0, 0]
    assert result.value == z.real and abs(z.imag) > 1.
    assert abs(abs(z)-result.value) > .01
    lossless = result.document.to_dict()
    lossless['cross_section']['layers'][0]['tan_delta'] = 0.
    pure = TransmissionLineDocument.from_dict(lossless).analyze()
    assert pure.propagation().z_characteristic[0, 0].real == pytest.approx(
        result.document.cross_section.analyze().z0, rel=1e-10)
    replay = result.document.analyze()
    np.testing.assert_allclose(replay.C, result.result.C, rtol=1e-12)
    assert result.refined_document.to_dict()['cross_section']['mesh']['min_angle'] == 28.
    print(json.dumps(dict(case='lossy-cohn-goal', width_m=result.parameter,
        analytical_width_m=expected, width_relative_error=abs(result.parameter/expected-1),
        requested_residual_ohm=result.residual, refined_residual_ohm=result.refined_residual)))


def test_dielectric_attenuation_goal_matches_closed_form():
    # Homogeneous PEC line: gamma = j*w*sqrt(mu*eps)*sqrt(1-j*tan_delta).
    # s=alpha/(w*sqrt(mu*eps)); tan_delta=2*s*sqrt(1+s*s).
    target = 1.; scale = 2*np.pi*1e9*np.sqrt(mu_0*epsilon_0*4)
    s = target/scale; expected = 2*s*np.sqrt(1+s*s)
    result = seek_line_quantity(lambda loss: document(loss=loss), [.01, .1], target,
        quantity='attenuation', tolerance=.001, max_evaluations=24)
    assert result.unit == 'Np/m'
    assert result.parameter == pytest.approx(expected, rel=.005)
    assert max(abs(result.residual), abs(result.refined_residual)) <= .001
    assert result.value == result.result.propagation().gamma[0, 0].real
    np.testing.assert_allclose(result.result.propagation().alpha_conductor, 0, atol=0)
    print(json.dumps(dict(case='dielectric-attenuation-goal', loss_tangent=result.parameter,
        analytical_loss_tangent=float(expected), relative_error=float(abs(result.parameter/expected-1)),
        requested_residual_np_per_m=result.residual, refined_residual_np_per_m=result.refined_residual)))


@pytest.fixture(scope='module')
def finite_goal():
    return seek_line_quantity(lambda width: document(width, metal=True), [.3e-3, .8e-3], 50.,
        quantity='impedance_real', tolerance=.5, max_evaluations=24)


def test_finite_metal_goal_refined_and_outer_domain_acceptance(finite_goal):
    result = finite_goal
    assert max(abs(result.residual), abs(result.refined_residual)) <= .5
    raw = result.refined_document.to_dict(); raw['cross_section']['box']['width'] *= 2
    outer = TransmissionLineDocument.from_dict(raw).analyze().propagation().z_characteristic[0, 0].real
    assert abs(outer-result.target) <= .5
    assert abs(outer/result.refined_value-1) <= .005
    assert result.result.R[0, 0, 0] > 0 and result.result.G[0, 0, 0] > 0
    assert all(row.stage == 'search' for row in result.history[:-1])
    assert result.history[-1].stage == 'refinement'
    print(json.dumps(dict(case='finite-metal-goal', width_m=result.parameter,
        requested_residual_ohm=result.residual, refined_residual_ohm=result.refined_residual,
        outer_residual_ohm=float(outer-result.target),
        outer_relative_change=float(abs(outer/result.refined_value-1)))))


def test_independent_skrf_checks_full_lossy_goal_quantities(finite_goal):
    skrf = require_tool('scikit-rf'); clock = Stopwatch(); line = finite_goal.result
    with clock('openphysics'): actual = line.propagation()
    with clock('reference'):
        medium = skrf.media.DistributedCircuit(skrf.Frequency.from_f(line.frequency, unit='hz'),
            R=line.R[:, 0, 0], L=line.L[:, 0, 0], G=line.G[:, 0, 0], C=line.C[:, 0, 0])
        expected_z, expected_gamma = medium.z0, medium.gamma
    errors = [float(np.max(abs(actual.z_characteristic[:, 0]/expected_z-1))),
              float(np.max(abs(actual.gamma[:, 0]/expected_gamma-1)))]
    record = make_record(case='lossy-scalar-goal-propagation', physics='uniform scalar lossy line',
        api='sipi.line_goal.seek_line_quantity', discretization='bounded goal using extracted RLGC',
        tool='scikit-rf', tool_discretization='DistributedCircuit at identical extracted RLGC',
        matched=['same frequency, scalar RLGC and exp(+jwt) forward branch'],
        not_matched=['timings exclude field search; this is propagation validation, not independent extraction',
                     'no measured manufacturing accuracy or global optimum'],
        observables=[observable(name, unit, 'relative difference', error, 1e-10)
            for name, unit, error in zip(('Zc', 'gamma'), ('ohm', '1/m'), errors)],
        analytical_acceptance='homogeneous lossy Cohn width and closed-form attenuation; refined and doubled-domain targets',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi', version=metadata.version('sipi')); emit(record)
    assert max(errors) < 1e-10


def install_fake(monkeypatch, metric=lambda x: 1/x, *, refined_offset=0., broken=None):
    calls = []
    def analyze(self):
        data = self.to_dict(); calls.append(data)
        if broken == 'extraction': raise ArithmeticError('retained extraction cause')
        x = data['cross_section']['traces'][0]['width']/1e-3
        value = metric(x)
        if data['cross_section']['mesh']['edge_size'] == MESH['edge_size']/2:
            value += refined_offset
        def propagation():
            if broken == 'diagnostic': raise ArithmeticError('retained diagnostic cause')
            return SimpleNamespace(frequency=np.array(data['frequency_hz']), modes=('single',),
                gamma=np.array([[complex(value, 50.)]]), z_characteristic=np.array([[complex(value, 7.)]]))
        return SimpleNamespace(frequency=np.array(data['frequency_hz']), names=('signal',),
                               input_json=self.dumps(), propagation=propagation)
    monkeypatch.setattr(TransmissionLineDocument, 'analyze', analyze)
    return calls


def factory(x):
    return document(x*1e-3)


def test_bisection_snapshot_budget_and_no_factory_recall_for_refinement(monkeypatch):
    calls = install_fake(monkeypatch); factory_calls = []
    def counted(x): factory_calls.append(x); return factory(x)
    result = seek_line_quantity(counted, [1., 2.], .7, quantity='impedance_real', tolerance=1e-6)
    assert result.parameter == pytest.approx(10/7, abs=3e-6)
    assert len(factory_calls)+1 == len(calls) == len(result.history) <= 40
    chosen = result.document.to_dict(); refined = result.refined_document.to_dict()
    for key in ('edge_size', 'far_size', 'grade'): chosen['cross_section']['mesh'][key] /= 2
    assert chosen == refined
    raw = result.to_dict(); raw['input']['length_m'] = 999
    assert result.document.to_dict()['length_m'] == 0
    json.dumps(result.to_dict(), allow_nan=False)
    for row in result.history: assert row.to_dict()['input'] == json.loads(row.input_json)


@pytest.mark.parametrize('quantity,target', [('impedance_real', 1.), ('attenuation', 0.)])
def test_endpoint_goal_can_use_minimum_budget(monkeypatch, quantity, target):
    install_fake(monkeypatch, metric=lambda x: target/x)
    result = seek_line_quantity(factory, [1., 2.], target, quantity=quantity, tolerance=1e-10, max_evaluations=3)
    assert result.parameter == 1. and len(result.history) == 3


@pytest.mark.parametrize('case', ['unbracketed', 'budget', 'precision', 'refinement'])
def test_search_failures_keep_completed_rows_and_attempts(monkeypatch, case):
    install_fake(monkeypatch, refined_offset=1. if case == 'refinement' else 0.)
    target = 2. if case == 'unbracketed' else 1. if case == 'refinement' else .7
    bounds = [1., 2.]
    if case == 'precision':
        bounds = [1., np.nextafter(1., 2.)]
        install_fake(monkeypatch, metric=lambda x: 1. if x == 1. else 2.)
        target = 1.5
    with pytest.raises(LineQuantityGoalError) as caught:
        seek_line_quantity(factory, bounds, target, quantity='impedance_real', tolerance=1e-12,
                           max_evaluations=3 if case == 'budget' else 40)
    error = caught.value
    assert error.attempts == len(error.history) == (3 if case == 'refinement' else 2)
    assert error.stage == {'unbracketed': 'bracket', 'budget': 'budget', 'precision': 'precision',
                            'refinement': 'refinement/acceptance'}[case]
    assert error.cause_type is None and error.unit == 'ohm'


@pytest.mark.parametrize('broken', ['factory', 'wrong_type', 'extraction', 'diagnostic'])
def test_failed_attempts_are_counted_and_original_cause_preserved(monkeypatch, broken):
    install_fake(monkeypatch, broken=broken)
    def bad(x):
        if broken == 'factory': raise ArithmeticError('retained factory cause')
        return None if broken == 'wrong_type' else factory(x)
    with pytest.raises(LineQuantityGoalError) as caught:
        seek_line_quantity(bad, [1., 2.], .7, quantity='attenuation', tolerance=.01)
    error = caught.value
    assert error.attempts == 1 and error.history == () and error.failed_parameter == 1.
    assert error.cause_type == ('TypeError' if broken == 'wrong_type' else 'ArithmeticError')
    assert error.__cause__ is not None
    assert (error.input_json is not None) == (broken in ('extraction', 'diagnostic'))


@pytest.mark.parametrize('stage', ['second-endpoint', 'refinement'])
def test_later_extraction_failure_keeps_prior_success_and_failed_attempt(monkeypatch, stage):
    calls = install_fake(monkeypatch)
    old = TransmissionLineDocument.analyze
    def fail_later(self):
        if ((stage == 'second-endpoint' and len(calls) == 1) or
                self.cross_section.mesh_options['edge_size'] == MESH['edge_size']/2):
            raise ArithmeticError('later extraction failed')
        return old(self)
    monkeypatch.setattr(TransmissionLineDocument, 'analyze', fail_later)
    with pytest.raises(LineQuantityGoalError) as caught:
        seek_line_quantity(factory, [1., 2.], 1., quantity='impedance_real', tolerance=.01)
    n = 1 if stage == 'second-endpoint' else 2
    assert caught.value.attempts == n+1 and len(caught.value.history) == n
    assert caught.value.stage == ('search/extraction' if n == 1 else 'refinement/extraction')
    assert caught.value.input_json and caught.value.cause_type == 'ArithmeticError'


@pytest.mark.parametrize('case', ['pair', 'dc', 'grid', 'length', 'frequency_change', 'name_change'])
def test_unsupported_source_or_changing_identity_rejects_before_its_field_solve(monkeypatch, case):
    calls = install_fake(monkeypatch)
    def changed(x):
        raw = factory(x).to_dict()
        if case == 'pair': raw['cross_section'] = CrossSectionDocument(coupled_microstrip(
            width=.3e-3, gap=.2e-3, substrate_height=1e-3, eps_r=4), mesh=MESH).to_dict()
        if case == 'dc': raw['frequency_hz'] = [0.]
        if case == 'grid': raw['frequency_hz'] = [1e9, 2e9]
        if case == 'length': raw['length_m'] = .1
        if case == 'frequency_change' and x == 2.: raw['frequency_hz'] = [2e9]
        if case == 'name_change' and x == 2.: raw['cross_section']['traces'][0]['name'] = 'renamed'
        return TransmissionLineDocument.from_dict(raw)
    with pytest.raises(LineQuantityGoalError) as caught:
        seek_line_quantity(changed, [1., 2.], .7, quantity='impedance_real', tolerance=.01)
    n = 1 if case.endswith('change') else 0
    assert len(calls) == len(caught.value.history) == n and caught.value.attempts == n+1
    assert caught.value.stage == 'search/validation'


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -1., 0.])
def test_invalid_metric_is_not_a_success(monkeypatch, value):
    install_fake(monkeypatch, metric=lambda x: value)
    with pytest.raises(LineQuantityGoalError, match='invalid goal quantity') as caught:
        seek_line_quantity(factory, [1., 2.], 1., quantity='impedance_real', tolerance=.01)
    assert caught.value.attempts == 1 and not caught.value.history


@pytest.mark.parametrize('changes', [dict(bounds=[2, 1]), dict(bounds=[0, 1]), dict(bounds=[1, np.inf]),
    dict(bounds=[1, 2, 3]), dict(bounds=None), dict(bounds=[True, 2]), dict(target=True),
    dict(target=-1), dict(target=0), dict(tolerance=0), dict(tolerance=np.nan), dict(quantity='z0'),
    dict(quantity=[]), dict(max_evaluations=True), dict(max_evaluations=2), dict(max_evaluations=10001)])
def test_invalid_controls_do_not_invoke_factory(changes):
    def forbidden(x): pytest.fail('invalid controls invoked factory')
    kwargs = dict(bounds=[1., 2.], target=1., quantity='impedance_real', tolerance=.01)
    kwargs.update(changes)
    with pytest.raises(ValueError): seek_line_quantity(forbidden, **kwargs)


def test_factory_must_be_callable():
    with pytest.raises(TypeError):
        seek_line_quantity(None, [1, 2], 1, quantity='impedance_real', tolerance=.01)
