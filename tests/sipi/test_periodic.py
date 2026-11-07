# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Finite DFT, analytic harmonics and independent-tool periodic-response checks."""
from importlib import metadata

import numpy as np
import pytest

from sipi import LineNetwork, periodic_impulse, periodic_response, rlgc_network
from crosscheck import Stopwatch, emit, make_record, observable, require_tool

GATE = 1e-12


def network(count=5, ports=3):
    rng = np.random.default_rng(149)
    s = (rng.normal(size=(count, ports, ports))
         + 1j*rng.normal(size=(count, ports, ports)))/10
    s[0] = s[0].real
    return LineNetwork(np.arange(count)*2., s, np.arange(ports)*25.+25,
                       tuple(f'p{i}' for i in range(ports)))


def direct_weights(net):
    # Explicit finite harmonic sum, without FFT and without any production helper.
    count = 2*len(net.frequency)-1
    return np.array([(net.s[0].real + 2*sum(
        (net.s[k]*np.exp(2j*np.pi*k*t/count)).real
        for k in range(1, len(net.frequency))))/count for t in range(count)])


def direct_response(net, incident):
    count, ports = incident.shape
    positive = []
    for k in range(len(net.frequency)):
        a = sum(incident[t]*np.exp(-2j*np.pi*k*t/count) for t in range(count))
        positive.append([sum(net.s[k, i, j]*a[j] for j in range(ports))
                         for i in range(ports)])
    positive = np.array(positive)
    return np.array([(positive[0].real + 2*sum(
        (positive[k]*np.exp(2j*np.pi*k*t/count)).real
        for k in range(1, len(net.frequency))))/count for t in range(count)])


def record(tool, clock, error):
    r = make_record(case='periodic-network-'+tool,
        physics='sampled periodic power-wave network response',
        api='sipi.periodic_response / sipi.periodic_impulse',
        discretization='odd Hermitian spectrum; no window or extrapolation',
        tool=tool, tool_discretization=('Network.impulse_response odd lowpass no window'
            if tool == 'scikit-rf' else 'signal.convolve method=direct folded circularly'),
        matched=['DC and uniform harmonics; same S, real references and port order',
                 'odd transform length, unwindowed discrete weights and periodic input'],
        not_matched=['no material/geometry extraction or causal transient validation',
                     'scikit-rf shares NumPy FFT; separate finite-sum reference also required'],
        observables=[observable('response', '1', 'max absolute difference', error, GATE)],
        analytical_acceptance='finite direct DFT, pure delay, RC harmonics and power identity, abs 1e-12',
        stopwatch=clock)
    r['openphysics'].update(distribution='sipi', version=metadata.version('sipi'))
    emit(r)
    assert error <= GATE


@pytest.mark.parametrize('ports', [1, 2, 4])
@pytest.mark.parametrize('bins', [2, 5, 9])
def test_direct_dft_and_immutable_input_output(ports, bins):
    net = network(bins, ports)
    count = 2*bins-1
    incident = np.random.default_rng(9).normal(size=(count, ports))
    snapshot = incident.copy()
    result = periodic_response(net, incident)
    impulse = periodic_impulse(net)
    np.testing.assert_allclose(result.reflected, direct_response(net, incident), atol=GATE, rtol=0)
    np.testing.assert_allclose(impulse.weights,
        np.fft.fftshift(direct_weights(net), axes=0), atol=GATE, rtol=0)
    np.testing.assert_allclose(impulse.weights.sum(axis=0), net.s[0].real, atol=GATE, rtol=0)
    np.testing.assert_array_equal(result.incident, snapshot)
    incident[:] = 42
    np.testing.assert_array_equal(result.incident, snapshot)
    assert result.port_names == impulse.port_names == net.port_names
    assert result.basis == impulse.basis == net.basis
    np.testing.assert_array_equal(result.z_ref, net.z_ref)
    assert result.period == .5 and result.dt == .5/count
    for values in (result.time, result.incident, result.reflected, result.voltage,
                   result.current, result.z_ref, impulse.lag, impulse.weights, impulse.z_ref):
        assert not values.flags.writeable


@pytest.mark.parametrize('coefficient', [-1., 0., .2, 1., 2.])
def test_constant_reflection_voltage_current(coefficient):
    net = LineNetwork([0., 1., 2.], np.full((3, 1, 1), coefficient), [75.], ('p',))
    a = np.array([1., -.3, .2, -.8, .4])[:, None]
    result = periodic_response(net, a)
    np.testing.assert_allclose(result.reflected, coefficient*a, atol=GATE, rtol=0)
    np.testing.assert_allclose(result.voltage, np.sqrt(75)*(1+coefficient)*a, atol=GATE, rtol=0)
    np.testing.assert_allclose(result.current, (1-coefficient)*a/np.sqrt(75), atol=GATE, rtol=0)
    # Real instantaneous power; no RMS/phasor factor 1/2 in time samples.
    np.testing.assert_allclose(result.voltage*result.current,
        a*a-result.reflected**2, atol=GATE, rtol=0)


@pytest.mark.parametrize('delay', [0, 1, 4, 8, 10])
def test_integer_delay_wrap_and_highest_bin_phase(delay):
    count = 9
    phase = np.exp(-2j*np.pi*np.arange(5)*delay/count)
    s = np.zeros((5, 2, 2), complex)
    s[:, 0, 1] = s[:, 1, 0] = phase
    net = LineNetwork(np.arange(5), s, [50., 50.], ('near', 'far'))
    a = np.random.default_rng(7).normal(size=(count, 2))
    result = periodic_response(net, a)
    expected = np.roll(a[:, ::-1], delay, axis=0)
    np.testing.assert_allclose(result.reflected, expected, atol=GATE, rtol=0)
    h = np.fft.ifftshift(periodic_impulse(net).weights, axes=0)
    expected_h = np.zeros_like(h)
    expected_h[delay % count, 0, 1] = expected_h[delay % count, 1, 0] = 1
    np.testing.assert_allclose(h, expected_h, atol=GATE, rtol=0)


def test_superposition_shift_passive_energy_and_real_power():
    net = network(9, 4)
    assert np.max(np.linalg.svd(net.s, compute_uv=False)) < 1
    rng = np.random.default_rng(10)
    a, c = rng.normal(size=(2, 17, 4))
    ra, rc = periodic_response(net, a), periodic_response(net, c)
    combined = periodic_response(net, 2*a-.3*c)
    np.testing.assert_allclose(combined.reflected, 2*ra.reflected-.3*rc.reflected, atol=GATE, rtol=0)
    np.testing.assert_allclose(periodic_response(net, np.roll(a, 3, axis=0)).reflected,
                               np.roll(ra.reflected, 3, axis=0), atol=GATE, rtol=0)
    assert np.sum(ra.reflected**2) <= np.sum(a*a)+GATE
    np.testing.assert_allclose(ra.voltage*ra.current, a*a-ra.reflected**2, atol=GATE, rtol=0)


@pytest.mark.parametrize('period,bins', [(1., 9), (1., 17), (2., 17), (2., 33)])
def test_rc_known_harmonics_under_period_and_resolution_changes(period, bins):
    # H=1/(1+j*omega*tau) is the reflection transfer here, not a voltage divider.
    tau = .13
    f = np.arange(bins)/period
    s = 1/(1+2j*np.pi*f*tau)
    net = LineNetwork(f, s[:, None, None], 50., ('p',))
    count = 2*bins-1
    time = np.arange(count)*period/count
    a = .2 + .7*np.cos(2*np.pi*2*time) + .3*np.sin(2*np.pi*3*time)
    expected = (.2 + (.7/(1+2j*np.pi*2*tau)*np.exp(2j*np.pi*2*time)).real
                + (-.3j/(1+2j*np.pi*3*tau)*np.exp(2j*np.pi*3*time)).real)
    np.testing.assert_allclose(periodic_response(net, a[:, None]).reflected[:, 0],
                               expected, atol=GATE, rtol=0)


def test_skrf_impulse_and_scipy_direct_convolution():
    skrf = require_tool('scikit-rf')
    require_tool('scipy')
    from scipy.signal import convolve
    net = network(9, 3)
    a = np.random.default_rng(4).normal(size=(17, 3))
    clock = Stopwatch()
    with clock('openphysics'):
        impulse = periodic_impulse(net)
        response = periodic_response(net, a)
    with clock('reference'):
        ref = skrf.Network(frequency=skrf.Frequency.from_f(net.frequency, unit='hz'),
                           s=net.s, z0=net.z_ref)
        lag, weights = ref.impulse_response(n=17, window=None, bandpass=False, squeeze=False)
    error = max(np.max(abs(lag-impulse.lag)), np.max(abs(weights-impulse.weights)))
    record('scikit-rf', clock, error)
    clock = Stopwatch()
    with clock('openphysics'):
        response = periodic_response(net, a)
    with clock('reference'):
        h = direct_weights(net)
        expected = np.zeros_like(a)
        for i in range(3):
            for j in range(3):
                linear = convolve(h[:, i, j], a[:, j], mode='full', method='direct')
                for k, value in enumerate(linear):
                    expected[k % len(a), i] += value
    record('scipy', clock, np.max(abs(expected-response.reflected)))


def test_lossless_rlgc_mixed_mode_time_normalization():
    count, bins = 17, 9
    df, delay = 1e8, 2
    velocity = 2e8
    # Uncoupled identical 50-ohm lines: voltage/current normalization still differs by mode.
    net = rlgc_network(np.arange(bins)*df, R=np.zeros((2, 2)), G=np.zeros((2, 2)),
        L=np.eye(2)*250e-9, C=np.eye(2)*100e-12,
        length=velocity*delay/(count*df), names=('positive', 'negative')).mixed_mode()
    a = np.random.default_rng(1).normal(size=(count, 4))
    result = periodic_response(net, a)
    assert result.basis == 'mixed-mode'
    assert result.port_names == ('d_near', 'd_far', 'c_near', 'c_far')
    np.testing.assert_array_equal(result.z_ref, [100., 100., 25., 25.])
    np.testing.assert_allclose(result.reflected, np.roll(a[:, [1, 0, 3, 2]], delay, axis=0),
                               atol=GATE, rtol=0)
    np.testing.assert_allclose(result.voltage*result.current, a*a-result.reflected**2,
                               atol=GATE, rtol=0)


@pytest.mark.parametrize('frequency', [[1., 2.], [0.], [0., 1., 2.001], [0., 1e-320]])
def test_reject_missing_dc_irregular_grid_and_unrepresentable_period(frequency):
    net = LineNetwork(frequency, np.zeros((len(frequency), 1, 1)), 50., ('p',))
    for method in (periodic_impulse, lambda n: periodic_response(n, [[0.]])):
        with pytest.raises(ValueError): method(net)


@pytest.mark.parametrize('imaginary', [1e-30, .1])
def test_complex_dc_is_not_silently_discarded(imaginary):
    net = LineNetwork([0., 1.], [[[1+imaginary*1j]], [[.1+.4j]]], 50., ('p',))
    with pytest.raises(ValueError, match='exactly real'): periodic_impulse(net)
    with pytest.raises(ValueError, match='exactly real'): periodic_response(net, [[1.], [0.], [0.]])


@pytest.mark.parametrize('bad', [True, [1., 2., 3.], [[1.], [2.]], [[True], [0.], [0.]],
    [[1+0j], [0.], [0.]], [[np.nan], [0.], [0.]], [[np.inf], [0.], [0.]], [['1'], ['0'], ['0']]])
def test_invalid_incident(bad):
    with pytest.raises(ValueError): periodic_response(network(2, 1), bad)


def test_invalid_network_and_transform_overflow():
    with pytest.raises(ValueError, match='LineNetwork'): periodic_impulse(None)
    net = LineNetwork([0., 1.], np.full((2, 1, 1), 1e308), 50., ('p',))
    with pytest.raises(ValueError, match='numeric scale'): periodic_response(net, [[1e308]]*3)
    with pytest.raises(ValueError, match='numeric scale'): periodic_impulse(net)


def test_grid_roundoff_acceptance_without_interpolation():
    net = network(5, 1)
    f = net.frequency.copy(); f[3] += f[-1]*.5e-12
    accepted = LineNetwork(f, net.s, net.z_ref, net.port_names)
    np.testing.assert_array_equal(periodic_impulse(accepted).weights, periodic_impulse(net).weights)
    f[3] += f[-1]*2e-12
    with pytest.raises(ValueError, match='uniformly'):
        periodic_impulse(LineNetwork(f, net.s, net.z_ref, net.port_names))
