# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Closed scalar, manufactured coordinate and independent state-space checks."""
from dataclasses import replace
import json

import numpy as np
import pytest
from numpy.testing import assert_allclose
from scipy.linalg import eig
from numpy.polynomial.legendre import leggauss

from sipi.forward_profile import ForwardWaveProfile, rlgc_forward_profile


def data(n=3):
    # Distinct noncommuting reciprocal tensors; all loss terms are SPD.
    a = np.arange(1, n*n+1, dtype=float).reshape(n, n)/(n*n)
    return dict(frequency=[1e9, 3e9, 10e9],
                R=np.eye(n)*2 + .3*a@a.T,
                L=(np.diag(np.linspace(2., 4., n))+.1*a@a.T)*1e-7,
                G=np.eye(n)*.002 + .0003*a.T@a,
                C=(np.diag(np.linspace(1., 1.6, n))+.08*a.T@a)*1e-10,
                launch_current=np.linspace(.01, .03, n)*(1+.3j),
                positions=[0., .003, .017], names=tuple(f's{i}' for i in range(n)))


@pytest.mark.parametrize('n', [1, 2, 3, 4])
@pytest.mark.parametrize('lossy', [False, True])
def test_diagonal_scalar_closed_forms(n, lossy, record_property):
    d = data(n)
    for key in ('R', 'L', 'G', 'C'):
        d[key] = np.diag(np.diag(d[key]))
    if not lossy:
        d['R'] *= 0; d['G'] *= 0
    out = rlgc_forward_profile(**d)
    omega = 2*np.pi*np.asarray(d['frequency'])[:, None]
    series = np.diag(d['R'])+1j*omega*np.diag(d['L'])
    shunt = np.diag(d['G'])+1j*omega*np.diag(d['C'])
    gamma = np.sqrt(series*shunt); zc = np.sqrt(series/shunt)
    current = np.asarray(d['launch_current'])[None, None, :]*np.exp(
        -gamma[:, None, :]*np.asarray(d['positions'])[None, :, None])
    voltage = zc[:, None, :]*current
    assert_allclose(out.current, current, rtol=1e-12, atol=0)
    assert_allclose(out.voltage, voltage, rtol=1e-12, atol=0)
    power = .5*np.sum(zc[:, None, :].real*abs(current)**2, axis=-1)
    qr = .5*np.sum(np.diag(d['R'])*abs(current)**2, axis=-1)
    qg = .5*np.sum(np.diag(d['G'])*abs(voltage)**2, axis=-1)
    for actual, expected in zip((out.power, out.conductor_loss, out.dielectric_loss),
                                (power, qr, qg)):
        assert_allclose(actual, expected, rtol=1e-12, atol=0)
    record_property('scalar_power', json.dumps(out.power.tolist()))


def test_nonorthogonal_power_dual_manufactured_line():
    t = np.array([[1., .3, -.1], [.2, 1.2, .4], [.1, -.2, .8]])
    inv = np.linalg.inv(t)
    diagonal = dict(R=np.diag([2., 4., 3.]), L=np.diag([2., 3., 4.])*1e-7,
                    G=np.diag([2., 3., 1.])*1e-3, C=np.diag([1., 2., 1.5])*1e-10)
    d = data()
    for key in ('R', 'L'): d[key] = t@diagonal[key]@t.T
    for key in ('G', 'C'): d[key] = inv.T@diagonal[key]@inv
    out = rlgc_forward_profile(**d)
    im0 = t.T@d['launch_current']
    for k, hz in enumerate(d['frequency']):
        z = np.diag(diagonal['R'])+2j*np.pi*hz*np.diag(diagonal['L'])
        y = np.diag(diagonal['G'])+2j*np.pi*hz*np.diag(diagonal['C'])
        im = im0[None, :]*np.exp(-np.asarray(d['positions'])[:, None]*np.sqrt(z*y))
        vm = np.sqrt(z/y)*im
        assert_allclose(out.current[k], im@inv, rtol=1e-10, atol=0)
        assert_allclose(out.voltage[k], vm@t.T, rtol=1e-10, atol=0)
        assert_allclose(out.power[k], .5*np.sum((vm.conj()*im).real, axis=-1), rtol=1e-10, atol=0)


@pytest.mark.parametrize('n', [3, 4])
def test_independent_2n_state_eigenspace(n, record_property):
    d = data(n); out = rlgc_forward_profile(**d); errors = []
    for k, hz in enumerate(d['frequency']):
        z = d['R']+2j*np.pi*hz*d['L']; y = d['G']+2j*np.pi*hz*d['C']
        state = np.block([[np.zeros_like(z), z], [y, np.zeros_like(y)]])
        roots, vectors = eig(state)
        selected = roots.imag > 0
        assert np.count_nonzero(selected) == n
        basis = vectors[:, selected]; roots = roots[selected]
        coefficient = np.linalg.solve(basis[n:], d['launch_current'])
        for j, distance in enumerate(d['positions']):
            expected = basis@(np.exp(-roots*distance)*coefficient)
            actual = np.r_[out.voltage[k, j], out.current[k, j]]
            # Separate voltage/current scales; never let volts mask ampere errors.
            for block in (slice(0, n), slice(n, 2*n)):
                error = np.max(abs(actual[block]-expected[block]))/np.max(abs(expected[block]))
                assert error < 1e-10; errors.append(float(error))
    record_property('state_eigenspace_max_relative', max(errors))


@pytest.mark.parametrize('n', [1, 3, 4])
def test_telegrapher_and_integrated_power_balance(n, record_property):
    d = data(n); out = rlgc_forward_profile(**d)
    for k, hz in enumerate(d['frequency']):
        z = d['R']+2j*np.pi*hz*d['L']; y = d['G']+2j*np.pi*hz*d['C']
        v, i = out.voltage[k], out.current[k]
        dv = -i@z.T; di = -v@y.T
        derivative = .5*np.sum((dv.conj()*i + v.conj()*di).real, axis=-1)
        assert_allclose(-derivative, out.conductor_loss[k]+out.dielectric_loss[k], rtol=1e-10, atol=0)
    nodes, weights = leggauss(48); length = d['positions'][-1]
    q = rlgc_forward_profile(**dict(d, positions=(nodes+1)*length/2))
    integrated = (q.conductor_loss+q.dielectric_loss)@(weights*length/2)
    difference = out.power[:, 0]-out.power[:, -1]
    assert_allclose(difference, integrated, rtol=1e-10, atol=0)
    assert np.all(np.diff(out.power, axis=1) < 0)
    record_property('integrated_dissipation', json.dumps(integrated.tolist()))


def test_permutation_complex_scaling_and_frequency_dependent_drive():
    d = data(); drive = np.stack([d['launch_current']*x for x in [1, 2j, -.3+.4j]])
    d['launch_current'] = drive; out = rlgc_forward_profile(**d)
    p = np.array([2, 0, 1]); permuted = dict(d)
    for key in ('R', 'L', 'G', 'C'): permuted[key] = d[key][p][:, p]
    permuted['launch_current'] = drive[:, p]; permuted['names'] = tuple(d['names'][i] for i in p)
    other = rlgc_forward_profile(**permuted)
    assert other.names == ('s2', 's0', 's1')
    assert_allclose(other.voltage, out.voltage[:, :, p], rtol=1e-10, atol=0)
    assert_allclose(other.current, out.current[:, :, p], rtol=1e-10, atol=0)
    factor = -.7+.2j; scaled = rlgc_forward_profile(**dict(d, launch_current=drive*factor))
    for key in ('voltage', 'current'): assert_allclose(getattr(scaled, key), getattr(out, key)*factor, rtol=1e-12, atol=0)
    for key in ('power', 'conductor_loss', 'dielectric_loss'):
        assert_allclose(getattr(other, key), getattr(out, key), rtol=1e-10, atol=0)
        assert_allclose(getattr(scaled, key), getattr(out, key)*abs(factor)**2, rtol=1e-12, atol=0)
    assert np.array_equal(out.current[:, 0], drive)


def test_zero_drive_and_lossless_coupled_power():
    d = data(); zero = rlgc_forward_profile(**dict(d, launch_current=np.zeros(3)))
    for key in ('voltage', 'current', 'power', 'conductor_loss', 'dielectric_loss'):
        assert np.count_nonzero(getattr(zero, key)) == 0
    out = rlgc_forward_profile(**dict(d, R=np.zeros((3, 3)), G=np.zeros((3, 3))))
    assert_allclose(out.power, np.repeat(out.power[:, :1], 3, axis=1), rtol=1e-12, atol=0)
    assert np.count_nonzero(out.conductor_loss) == np.count_nonzero(out.dielectric_loss) == 0


def test_inputs_and_result_arrays_are_snapshots():
    d = data(); out = rlgc_forward_profile(**d); voltage = out.voltage.copy()
    d['launch_current'][:] = 100; d['L'][:] = 0; d['positions'][0] = 2
    assert np.array_equal(out.voltage, voltage) and out.positions[0] == 0
    for key in ('frequency', 'positions', 'voltage', 'current', 'power', 'conductor_loss', 'dielectric_loss'):
        with pytest.raises(ValueError):getattr(out, key).flat[0] = 0
    mutable = voltage.copy(); copied = replace(out, voltage=mutable); mutable[:] = 0
    assert np.array_equal(copied.voltage, voltage)


@pytest.mark.parametrize('key,value', [
    ('frequency', [0]), ('frequency', [1e9, 1e9]),
    ('positions', []), ('positions', [-1]), ('positions', [0, 0]),
    ('positions', [1, 0]), ('positions', [True]), ('positions', [0, np.inf]),
    ('positions', [0j]), ('positions', [[0]]),
    ('launch_current', [1, True, 0]), ('launch_current', [1, 2]),
    ('launch_current', [[1, 2, 3]]), ('launch_current', [1, np.nan, 0]),
    ('launch_current', ['1', '2', '3']), ('launch_current', 1),
    ('names', ['a', 'a', 'b']), ('names', ['a', 'b']),
    ('R', -np.eye(3)), ('L', np.zeros((3, 3))),
    ('G', np.eye(2)), ('C', np.full((3, 3), np.inf)),
])
def test_invalid_inputs(key, value):
    with pytest.raises((ValueError, TypeError)):rlgc_forward_profile(**dict(data(), **{key: value}))


@pytest.mark.parametrize('amplitude', [1e160, 1e308])
def test_unrepresentable_launch_or_power_is_rejected(amplitude):
    with pytest.raises(ValueError, match='representable'):
        rlgc_forward_profile(**dict(data(), launch_current=np.full(3, amplitude)))


@pytest.mark.parametrize('key,value', [('power', [[1j]]), ('current', [[[True]]]),
                                      ('dielectric_loss', [[np.nan]]), ('voltage', [])])
def test_result_constructor_rejects_nonfinite_or_wrong_shapes(key, value):
    out = rlgc_forward_profile(**data())
    with pytest.raises(ValueError):replace(out, **{key: value})
