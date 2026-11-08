# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Physical hybrid wave constraints and qualified independent RF comparisons."""
import importlib.metadata as metadata
import numpy as np
import pytest
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import hybrid_network, inverse_hybrid_network, impedance_network, admittance_network
from sipi.termination import terminate_network
import sipi.hybrid_parameters as module

APIS = {'h': hybrid_network, 'g': inverse_hybrid_network}


def physical_to_hybrid(a):
    out = np.empty_like(a)
    out[:, 0, 0] = a[:, 0, 0]-a[:, 0, 1]*a[:, 1, 0]/a[:, 1, 1]
    out[:, 0, 1] = a[:, 0, 1]/a[:, 1, 1]
    out[:, 1, 0] = -a[:, 1, 0]/a[:, 1, 1]
    out[:, 1, 1] = 1/a[:, 1, 1]
    return out


def samples(kind, refs, parameter):
    d = np.sqrt(refs)
    base = np.array([[1.4+.1j, .12+.04j], [.12+.04j, 1.8+.2j]])
    if kind == 'nonreciprocal': base[0, 1] += .2-.07j
    elif kind == 'diagonal': base = np.diag(np.diag(base))
    elif kind == 'rank-one': base = (.3+.1j)*np.array([[1., 2.], [2., 4.]])
    matrix = base/d[:, None]/d[None, :] if parameter == 'g' else base*d[:, None]*d[None, :]
    physical = np.stack([matrix, matrix*(1+.2j), matrix*(.7-.1j)])
    return np.array([0., 1e6, 1e9]), physical_to_hybrid(physical), physical


def physical_constraint(network, values, parameter):
    eye = np.eye(2); d = np.sqrt(network.z_ref)
    voltage = d[None, :, None]*(eye+network.s)
    current = (eye-network.s)/d[None, :, None]
    lhs = np.stack([current[:, 0], voltage[:, 1]], axis=1) if parameter == 'g' else np.stack([voltage[:, 0], current[:, 1]], axis=1)
    given = np.stack([voltage[:, 0], current[:, 1]], axis=1) if parameter == 'g' else np.stack([current[:, 0], voltage[:, 1]], axis=1)
    rhs = values@given
    norm = np.maximum(np.max(abs(lhs), axis=2), np.max(abs(rhs), axis=2))
    return float(np.max(np.max(abs(lhs-rhs), axis=2)/np.maximum(norm, np.finfo(float).tiny)))


@pytest.mark.parametrize('parameter', ['h', 'g'])
@pytest.mark.parametrize('kind', ['nonreciprocal', 'reciprocal', 'diagonal', 'rank-one'])
@pytest.mark.parametrize('refs', [[1., 1.], [31., 73.], [1e-3, 2e3], [1e4, 1e-2]])
def test_qualified_independent_rf_conversion_and_physical_equations(parameter, kind, refs):
    rf = require_tool('scikit-rf'); refs = np.array(refs)
    f, values, physical = samples(kind, refs, parameter); clock = Stopwatch()
    with clock('openphysics'): net = APIS[parameter](f, values, z_ref=refs)
    # g2s forms H then divides by H22 to form Z. Rank-one Y has no finite Z.
    # Use direct Y conversion plus a closed form for these four explicit cases.
    reference = 'y2s' if parameter == 'g' and kind == 'rank-one' else parameter+'2s'
    with clock('reference'):
        expected = rf.network.y2s(physical, z0=refs, s_def='power') if reference == 'y2s' else getattr(rf.network, reference)(values, z0=refs)
    error = float(np.max(abs(net.s-expected))); vi = physical_constraint(net, values, parameter)
    assert error < 1e-12 and vi < 1e-10
    replay = (admittance_network if parameter == 'g' else impedance_network)(f, physical, z_ref=refs)
    np.testing.assert_allclose(net.s, replay.s, atol=1e-12, rtol=0.)
    if parameter == 'g' and kind == 'rank-one':
        a = (.3+.1j)*np.array([1., 1+.2j, .7-.1j])
        exact = np.eye(2)-2*a[:, None, None]/(1+5*a[:, None, None])*np.array([[1., 2.], [2., 4.]])
        np.testing.assert_allclose(net.s, exact, atol=1e-12, rtol=0.)
    record = make_record(case=f'physical-{parameter}-{kind}-{refs[0]}-{refs[1]}',
        physics='explicit two-port hybrid voltage/current constraints', api=APIS[parameter].__name__,
        discretization='three physical matrices; scaled direct wave left solve', tool='scikit-rf',
        tool_discretization=f'network.{reference}; direct Y for rank-one G cases with inadmissible Z intermediate',
        matched=['physical constraints', 'frequency', 'positive real references', 'power-wave convention'],
        not_matched=['implementation and conditioning', 'g2s is not valid reference for the four rank-one Y cases'],
        observables=[observable('S', '1', 'max_absolute', error, 1e-12), observable('row-wise physical VI', '1', 'relative', vi, 1e-10)],
        analytical_acceptance='Zero H/G, ideal transformers, rank-one closed form and loaded KCL; network algebra has no spatial mesh convergence.', stopwatch=clock)
    record['openphysics'].update(distribution='sipi', version=metadata.version('sipi')); emit(record)


@pytest.mark.parametrize('parameter', ['h', 'g'])
def test_zero_and_singular_physical_matrices_do_not_require_inversion(parameter):
    zero = APIS[parameter]([0.], np.zeros((1, 2, 2)), z_ref=[31., 73.])
    expected = np.diag([1., -1.]) if parameter == 'g' else np.diag([-1., 1.])
    np.testing.assert_array_equal(zero.s[0], expected)
    value = np.diag([0., .02 if parameter == 'h' else 80.])[None]
    result = APIS[parameter]([0.], value, z_ref=[31., 73.])
    diagonal = [1., (80.-73.)/(80.+73.)] if parameter == 'g' else [-1., (1.-73.*.02)/(1.+73.*.02)]
    np.testing.assert_allclose(result.s[0], np.diag(diagonal), atol=1e-12, rtol=0.)


@pytest.mark.parametrize('parameter', ['h', 'g'])
@pytest.mark.parametrize('turns', [.5, 1., 2., -2.])
@pytest.mark.parametrize('refs', [[50., 50.], [31., 73.], [1e-3, 2e3]])
def test_ideal_through_and_transformer_analytic_power_conservation(parameter, turns, refs):
    t = turns; z1, z2 = refs
    values = np.array([[[0., -1/t], [1/t, 0.]]]) if parameter == 'g' else np.array([[[0., t], [-t, 0.]]])
    net = APIS[parameter]([0.], values, z_ref=refs)
    denominator = z1+t*t*z2; q = (t*t*z2-z1)/denominator; c = 2*t*np.sqrt(z1*z2)/denominator
    np.testing.assert_allclose(net.s[0], [[q, c], [c, -q]], atol=1e-12, rtol=0.)
    np.testing.assert_allclose(net.s[0].conj().T@net.s[0], np.eye(2), atol=1e-12, rtol=0.)


@pytest.mark.parametrize('parameter', ['h', 'g'])
@pytest.mark.parametrize('inductance', [0., 100e-9])
def test_loaded_passive_rlc_network_matches_independent_kcl(parameter, inductance):
    f = np.array([0., 1e6, 1e9])
    branch = 1/(500.+2j*np.pi*f*inductance)
    y = np.diag([.005, .007])+branch[:, None, None]*np.array([[1., -1.], [-1., 1.]])+2j*np.pi*f[:, None, None]*np.array([[8., -2.], [-2., 11.]])*1e-12
    physical = y if parameter == 'g' else np.linalg.inv(y)
    net = APIS[parameter](f, physical_to_hybrid(physical), z_ref=[31., 73.], names=['a', 'b'])
    source = np.array([1.+.2j, -.3+.1j]); resistance = np.array([23., 41.])
    result = terminate_network(net, source_voltages=dict(zip(['a', 'b'], source)), terminations=dict(zip(['a', 'b'], resistance)))
    expected = np.linalg.solve(y+np.diag(1/resistance), np.broadcast_to(source/resistance, (3, 2))[..., None])[..., 0]
    np.testing.assert_allclose(result.voltage, expected, atol=1e-12, rtol=0.)
    np.testing.assert_allclose(result.current, (y@expected[..., None])[..., 0], atol=1e-12, rtol=0.)
    assert np.max(np.linalg.svd(net.s, compute_uv=False)) <= 1+1e-12
    np.testing.assert_allclose(net.s, net.s.swapaxes(1, 2), atol=1e-12, rtol=0.)


@pytest.mark.parametrize('parameter', ['h', 'g'])
def test_reference_change_consistent_unit_scaling_and_active_input(parameter):
    refs = np.array([31., 73.]); f, values, _ = samples('nonreciprocal', refs, parameter)
    net = APIS[parameter](f, values, z_ref=refs)
    changed = APIS[parameter](f, values, z_ref=[47., 29.])
    np.testing.assert_allclose(changed.s, net.renormalized([47., 29.]).s, atol=1e-12, rtol=0.)
    factor = 1e7; scaled = values.copy()
    scaled[:, 0, 0] *= 1/factor if parameter == 'g' else factor
    scaled[:, 1, 1] *= factor if parameter == 'g' else 1/factor
    np.testing.assert_allclose(APIS[parameter](f, scaled, z_ref=refs*factor).s, net.s, atol=1e-12, rtol=0.)
    active = APIS[parameter]([0.], np.diag([-.5, .5])[None], z_ref=1.)
    assert abs(active.s[0, 0, 0]) > 1  # Conversion does not fabricate passivity.


@pytest.mark.parametrize('parameter', ['h', 'g'])
def test_detached_readonly_results_and_names(parameter):
    refs = np.array([31., 73.]); f, values, _ = samples('reciprocal', refs, parameter); names = ['a', 'b']
    net = APIS[parameter](f, values, z_ref=refs, names=names); before = net.s.copy()
    f[:] = 9; values[:] = 9; refs[:] = 9; names[0] = 'other'
    assert net.port_names == ('a', 'b') and net.basis == 'single-ended'
    assert net.frequency[0] == 0 and net.z_ref[0] == 31
    np.testing.assert_array_equal(net.s, before)
    for value in [net.frequency, net.z_ref, net.s]:
        assert not value.flags.writeable
        with pytest.raises(ValueError): value.flat[0] = 0


@pytest.mark.parametrize('parameter', ['h', 'g'])
@pytest.mark.parametrize('bad', [True, [[[True, 1], [1, 2]]], [[['1', '0'], ['0', '1']]], np.full((1, 2, 2), np.nan), np.full((1, 2, 2), complex(0, np.inf)), None, {}, [], [1], np.eye(2), np.zeros((1, 0, 0)), np.zeros((1, 1, 1)), np.zeros((1, 3, 3)), np.zeros((2, 2, 2))])
def test_strict_two_port_physical_samples(parameter, bad):
    with pytest.raises((ValueError, TypeError)): APIS[parameter]([0.], bad, z_ref=50.)


@pytest.mark.parametrize('parameter', ['h', 'g'])
@pytest.mark.parametrize('bad', [[], [True], [np.nan], [-1.], [1., 1.], [2., 1.], [[0.]]])
def test_strict_frequency(parameter, bad):
    with pytest.raises((ValueError, TypeError)): APIS[parameter](bad, np.zeros((1, 2, 2)), z_ref=50.)


@pytest.mark.parametrize('parameter', ['h', 'g'])
@pytest.mark.parametrize('bad', [0., -1., True, complex(50), np.inf, [50, True], [[50, 50]], [50], [50, 50, 50]])
def test_explicit_positive_real_references(parameter, bad):
    with pytest.raises((ValueError, TypeError)): APIS[parameter]([0.], np.zeros((1, 2, 2)), z_ref=bad)


@pytest.mark.parametrize('parameter', ['h', 'g'])
@pytest.mark.parametrize('bad', ['ab', [], ['a'], ['a', 'a'], ['a', ''], ['a', 'b\nc'], ['a', 2]])
def test_unique_explicit_names(parameter, bad):
    with pytest.raises((ValueError, TypeError)): APIS[parameter]([0.], np.zeros((1, 2, 2)), z_ref=50., names=bad)


@pytest.mark.parametrize('parameter', ['h', 'g'])
@pytest.mark.parametrize('case', ['singular', 'cancel', 'conditioning', 'normalization'])
def test_numerical_failure_gates(parameter, case):
    values = np.diag([-1., 1.])[None].astype(complex); ref = 1.
    if case == 'cancel': values[0, 0, 0] += 5e-14
    elif case == 'conditioning': values = np.diag([1., 1e14])[None]
    elif case == 'normalization':
        values = np.full((1, 2, 2), 1e308); ref = 1e300
    with pytest.raises(ValueError): APIS[parameter]([0.], values, z_ref=ref)


@pytest.mark.parametrize('parameter', ['h', 'g'])
def test_large_finite_values_are_scaled_before_addition(parameter):
    values = np.diag([1.4e308+1.4e308j, 1.4e308+1.4e308j])[None]
    result = APIS[parameter]([0.], values, z_ref=1.)
    expected = np.diag([-1., 1.]) if parameter == 'g' else np.diag([1., -1.])
    np.testing.assert_allclose(result.s[0], expected, atol=1e-14, rtol=0.)


@pytest.mark.parametrize('parameter', ['h', 'g'])
@pytest.mark.parametrize('failure', ['residual', 'nonfinite', 'singular'])
def test_corrupted_or_failed_solve_is_rejected(parameter, failure, monkeypatch):
    def broken(a, b):
        if failure == 'singular': raise np.linalg.LinAlgError('deliberate')
        return np.full_like(b, np.nan if failure == 'nonfinite' else 7.)
    monkeypatch.setattr(module.np.linalg, 'solve', broken)
    with pytest.raises(ValueError): APIS[parameter]([0.], np.eye(2)[None]*2, z_ref=1.)
