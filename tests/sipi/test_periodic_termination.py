# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Direct harmonics, independent V/I circuits and periodic average-power checks."""
from importlib import metadata

import numpy as np
import pytest

from sipi import LineNetwork, periodic_terminated_response, rlgc_network
from sipi.termination import terminate_network
from crosscheck import Stopwatch, emit, make_record, observable, require_tool

GATE = 1e-12


def resistor(resistance=100., bins=5):
    s = (resistance-50)/(resistance+50)
    return LineNetwork(np.arange(bins)*1e6, np.full((bins, 1, 1), s), [50.], ('p',))


def phasors(values):
    # Explicit sums, not FFT: DC mean and positive-frequency peak phasors.
    count = len(values)
    out = np.array([sum(values[t]*np.exp(-2j*np.pi*k*t/count)
                        for t in range(count))/count for k in range((count+1)//2)])
    out[1:] *= 2
    out[0] = out[0].real
    return out


def samples(values, count):
    return np.array([values[0].real + sum((values[k]*np.exp(2j*np.pi*k*t/count)).real
        for k in range(1, len(values))) for t in range(count)])


def check_power(result):
    response = result.response
    harmonic = result.frequency_solution
    network = np.mean(np.sum(response.voltage*response.current, axis=1))
    series = np.mean(np.sum(result.termination_voltages*response.current, axis=1))
    source = np.mean(np.sum(result.source_voltages*response.current, axis=1))
    np.testing.assert_allclose(response.voltage+result.termination_voltages,
                               result.source_voltages, atol=GATE, rtol=0)
    np.testing.assert_allclose(response.voltage*response.current,
        response.incident**2-response.reflected**2, atol=GATE, rtol=0)
    np.testing.assert_allclose([network, series, source],
        [harmonic.network_power.sum(), harmonic.termination_power.sum(), harmonic.source_power.sum()],
        atol=GATE, rtol=0)
    assert abs(source-network-series) <= GATE
    assert series >= -GATE


def test_dc_resistor_divider_and_readonly_snapshots():
    net = resistor()
    result = periodic_terminated_response(net, source_voltages={'p':1.})
    np.testing.assert_allclose(result.response.voltage, 2/3, atol=GATE, rtol=0)
    np.testing.assert_allclose(result.response.current, 1/150, atol=GATE, rtol=0)
    np.testing.assert_allclose(result.frequency_solution.source_voltages[:, 0],
                               [1., 0, 0, 0, 0], atol=GATE, rtol=0)
    check_power(result)
    for array in (result.source_voltages, result.termination_voltages, result.response.voltage,
                  result.response.current, result.frequency_solution.a):
        assert not array.flags.writeable
    source = np.arange(9, dtype=float)
    result = periodic_terminated_response(net, source_voltages={'p':source})
    source[:] = -1
    np.testing.assert_array_equal(result.source_voltages[:, 0], np.arange(9))


def test_dc_plus_ac_peak_convention_and_power():
    t = np.arange(9)/9
    source = .4+2*np.cos(2*np.pi*t)+.3*np.sin(4*np.pi*t)
    result = periodic_terminated_response(resistor(), source_voltages={'p':source}, terminations={'p':20.})
    expected = [.4, 2., -.3j, 0., 0.]
    np.testing.assert_allclose(result.frequency_solution.source_voltages[:, 0], expected, atol=GATE, rtol=0)
    np.testing.assert_allclose(result.response.voltage[:, 0], source*100/120, atol=GATE, rtol=0)
    np.testing.assert_allclose(result.response.current[:, 0], source/120, atol=GATE, rtol=0)
    expected_mean_square = .4**2+(2**2+.3**2)/2
    assert abs(result.frequency_solution.network_power.sum()-100/120**2*expected_mean_square) <= GATE
    check_power(result)


def test_rl_series_drop_is_dynamic_not_pointwise_impedance():
    net = resistor(31.)
    omega = 2*np.pi*net.frequency
    inductance, series_r = 5e-6, 17.
    source_peaks = np.array([.2, 1., -.4j, 0, 0])[:, None]
    source = samples(source_peaks, 9)[:, 0]
    z = series_r+1j*omega*inductance
    result = periodic_terminated_response(net, source_voltages={'p':source}, terminations={'p':z})
    expected_i = source_peaks[:, 0]/(31.+z)
    current = samples(expected_i[:, None], 9)
    derivative = samples((1j*omega*expected_i)[:, None], 9)
    np.testing.assert_allclose(result.response.current, current, atol=GATE, rtol=0)
    np.testing.assert_allclose(result.termination_voltages,
                               series_r*current+inductance*derivative, atol=GATE, rtol=0)
    check_power(result)


def test_matched_line_delay_and_default_zero_source():
    bins, count, df = 5, 9, 1e8
    net = rlgc_network(np.arange(bins)*df, R=[[0.]], G=[[0.]], L=[[250e-9]],
                        C=[[100e-12]], length=2e8*2/(count*df))
    vs = .2+np.cos(2*np.pi*np.arange(count)/count)
    result = periodic_terminated_response(net, source_voltages={'near:1':vs})
    np.testing.assert_allclose(result.response.voltage[:, 0], vs/2, atol=GATE, rtol=0)
    np.testing.assert_allclose(result.response.voltage[:, 1], np.roll(vs, 2)/2, atol=GATE, rtol=0)
    np.testing.assert_array_equal(result.source_voltages[:, 1], 0.)
    np.testing.assert_allclose(result.frequency_solution.network_power, 0., atol=GATE, rtol=0)
    check_power(result)


@pytest.mark.parametrize('mixed', [False, True])
def test_coupled_network_direct_peak_harmonics_and_mode_references(mixed):
    net = rlgc_network(np.arange(5)*1e8, R=[[4., .4], [.4, 4.]],
        L=np.array([[300., 60.], [60., 300.]])*1e-9,
        G=[[.004, -.001], [-.001, .004]], C=np.array([[120., -30.], [-30., 120.]])*1e-12,
        length=.2)
    if mixed: net = net.mixed_mode()
    rng = np.random.default_rng(41)
    vs = rng.normal(size=(9, 4))
    z = np.array([25., 60., 80., 40.])[None, :]+2j*np.pi*net.frequency[:, None]*2e-9
    result = periodic_terminated_response(net, source_voltages=dict(zip(net.port_names, vs.T)),
                                          terminations=dict(zip(net.port_names, z.T)))
    reference = terminate_network(net, source_voltages=dict(zip(net.port_names, phasors(vs).T)),
                                   terminations=dict(zip(net.port_names, z.T)))
    for own, key in [('incident','a'), ('reflected','b'), ('voltage','voltage'), ('current','current')]:
        np.testing.assert_allclose(getattr(result.response, own), samples(getattr(reference, key),9),
                                   atol=GATE, rtol=0)
    assert result.response.basis == net.basis
    np.testing.assert_array_equal(result.response.z_ref, net.z_ref)
    check_power(result)


@pytest.mark.parametrize('tool', ['scipy', 'scikit-rf'])
def test_independent_vi_circuits_and_finite_harmonics(tool):
    ref = require_tool(tool)
    rng = np.random.default_rng(119)
    count, ports, bins = 9, 3, 5
    s = .08*(rng.normal(size=(bins, ports, ports))+1j*rng.normal(size=(bins, ports, ports)))
    s[0] = s[0].real
    refs = np.array([25., 60., 90.]); names = ('z', 'a', 'b')
    net = LineNetwork(np.arange(bins)*1e8, s, refs, names)
    vs = rng.normal(size=(count, ports))
    zt = np.array([30., 70., 15.])+2j*np.pi*net.frequency[:, None]*np.array([3., 1., 4.])*1e-9
    clock = Stopwatch()
    with clock('openphysics'):
        result = periodic_terminated_response(net, source_voltages=dict(zip(names,vs.T)),
                                              terminations=dict(zip(names,zt.T)))
    with clock('reference'):
        drives = phasors(vs)
        voltage, current = [], []
        if tool == 'scipy':
            from scipy.linalg import solve
            root = np.diag(np.sqrt(refs)); invroot = np.diag(1/np.sqrt(refs)); eye=np.eye(ports)
            for sk, zk, drive in zip(s, zt, drives):
                # Solve physical V/I directly, independently of wave feedback.
                matrix = np.block([[eye, np.diag(zk)], [(eye-sk)@invroot, -(eye+sk)@root]])
                answer = solve(matrix, np.r_[drive,np.zeros(ports)])
                voltage.append(answer[:ports]); current.append(answer[ports:])
        else:
            znet = ref.network.s2z(s, z0=refs, s_def='power')
            for impedance, zk, drive in zip(znet, zt, drives):
                value = np.linalg.solve(impedance+np.diag(zk), drive)
                current.append(value); voltage.append(impedance@value)
        expected_v, expected_i = samples(np.array(voltage),count), samples(np.array(current),count)
    errors = [float(np.max(abs(result.response.voltage-expected_v))),
              float(np.max(abs(result.response.current-expected_i)))]
    record = make_record(case='periodic-terminated-'+tool, physics='periodic finite terminated multiport',
        api='sipi.periodic_terminated_response', discretization='peak harmonic wave feedback and FFT',
        tool=tool, tool_discretization='direct finite harmonics with '+('V/I block solve' if tool=='scipy' else 's2z impedance circuit'),
        matched=['nonreciprocal S, unequal real references and real DC',
                 'same real periodic Thevenin drives and passive complex RL source/load samples'],
        not_matched=['no independent field extraction or measured accuracy', 'no causal startup or isolated-pulse response'],
        observables=[observable(name, unit, 'max absolute difference', error, GATE)
                     for name,unit,error in zip(('voltage','current'),('V','A'),errors)],
        analytical_acceptance='DC/AC divider, RL series drop, delay and time/frequency average-power identities',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    assert max(errors) <= GATE
    check_power(result)


def test_ideal_source_zero_drive_superposition_and_shift():
    net = resistor(); rng = np.random.default_rng(33)
    a, b = rng.normal(size=(2,9))
    def solve(value):return periodic_terminated_response(net,source_voltages={'p':value},terminations={'p':0.})
    ra, rb = solve(a), solve(b)
    np.testing.assert_allclose(ra.response.voltage[:, 0], a, atol=GATE, rtol=0)
    np.testing.assert_allclose(solve(2*a-.3*b).response.current,
                               2*ra.response.current-.3*rb.response.current, atol=GATE, rtol=0)
    np.testing.assert_allclose(solve(np.roll(a,2)).response.voltage,
                               np.roll(ra.response.voltage,2,axis=0), atol=GATE, rtol=0)
    np.testing.assert_array_equal(solve(0.).response.voltage, 0.)
    check_power(ra)


@pytest.mark.parametrize('bad', [{}, {'unknown':1.}, {'p':True}, {'p':1j},
    {'p':[0.]*5}, {'p':[[0.]*9]}, {'p':[True]*9}, {'p':float('inf')}, {'p':'1'}, []])
def test_invalid_sources(bad):
    with pytest.raises(ValueError): periodic_terminated_response(resistor(), source_voltages=bad)


@pytest.mark.parametrize('bad', [{'p':-1.}, {'p':True}, {'p':float('inf')}, {'p':'open'},
    {'p':1+.01j}, {'p':[1.]*4}, {'unknown':50.}, []])
def test_invalid_loads(bad):
    with pytest.raises(ValueError): periodic_terminated_response(resistor(), source_voltages={'p':1.}, terminations=bad)


def test_dc_grid_singular_and_numeric_scale_guards():
    for net in (LineNetwork([1,2], np.zeros((2,1,1)),50.,('p',)),
                LineNetwork([0,1,3],np.zeros((3,1,1)),50.,('p',)),
                LineNetwork([0,1],[[[1e-20j]],[[0]]],50.,('p',))):
        with pytest.raises(ValueError): periodic_terminated_response(net,source_voltages={'p':0.})
    short = LineNetwork([0,1],-np.ones((2,1,1)),50.,('p',))
    with pytest.raises(ValueError, match='condition|singular'):
        periodic_terminated_response(short, source_voltages={'p':1.}, terminations={'p':0.})
    with pytest.raises(ValueError):
        periodic_terminated_response(resistor(), source_voltages={'p':[1e308,-1e308]*4+[1e308]})
