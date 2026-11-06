# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Power-wave reference changes: analytic circuits and independent scikit-rf."""
import importlib.metadata as metadata
import numpy as np
import pytest
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import LineNetwork, rlgc_network


def test_complex_load_matches_reflection_formula():
    loads = np.array([50., 80+30j, 25-20j])
    old, new = 50., 75.
    source = LineNetwork([0, 1e6, 2e6], ((loads-old)/(loads+old))[:,None,None], old, ('load',))
    expected = (loads-new)/(loads+new)
    np.testing.assert_allclose(source.renormalized(new).s[:,0,0], expected, rtol=0, atol=1e-12)


@pytest.mark.parametrize('sign', [1., -1.])
def test_exact_open_and_short_do_not_require_an_impedance_inverse(sign):
    s = np.broadcast_to(sign*np.eye(2), (2,2,2))
    net = LineNetwork([0, 1e9], s, [50, 75], ('a','b'))
    for target in ([25, 100], [1e-100, 1e100]):
        np.testing.assert_allclose(net.renormalized(target).s, s, rtol=0, atol=1e-12)


def test_ideal_through_with_unequal_references_is_analytic_and_lossless():
    net = LineNetwork([0], [[[0,1],[1,0]]], 50, ('near','far'))
    result = net.renormalized([25,100])
    expected = np.array([[.6,.8],[.8,-.6]])
    np.testing.assert_allclose(result.s[0], expected, rtol=0, atol=1e-12)
    np.testing.assert_allclose(result.s[0].conj().T@result.s[0], np.eye(2), rtol=0, atol=1e-12)


def test_identity_roundtrip_immutability_and_metadata():
    rng = np.random.default_rng(107)
    values = (rng.normal(size=(3,4,4))+1j*rng.normal(size=(3,4,4)))*.03
    net = LineNetwork([1e3,1e6,1e9], values, [25,40,75,100], ('d1','d2','c1','c2'), 'mixed-mode')
    np.testing.assert_array_equal(net.renormalized(net.z_ref).s, net.s)
    target = np.array([40.,50.,80.,90.])
    changed = net.renormalized(target)
    target[:] = 1
    np.testing.assert_allclose(changed.renormalized(net.z_ref).s, net.s, rtol=0, atol=1e-12)
    np.testing.assert_array_equal(net.s, values)
    np.testing.assert_array_equal(changed.frequency, net.frequency)
    np.testing.assert_array_equal(changed.z_ref, [40,50,80,90])
    assert changed.port_names == net.port_names and changed.basis == net.basis
    assert not changed.s.flags.writeable and not changed.z_ref.flags.writeable
    assert not np.shares_memory(changed.s, net.s)


def test_physical_line_preserves_reciprocity_and_passivity():
    skrf = require_tool('scikit-rf')
    net = rlgc_network([1e3,1e6,1e9], R=[[2]], L=[[400e-9]], G=[[.002]], C=[[100e-12]], length=.12)
    clock = Stopwatch()
    with clock('openphysics'):
        changed = net.renormalized([30,90])
    with clock('reference'):
        expected = skrf.network.renormalize_s(net.s,net.z_ref,[30,90],s_def='power')
    difference = float(np.max(abs(changed.s-expected)))
    record = make_record(case='s-renormalization-lossy-line',physics='power-wave reference transformation',
        api='sipi.LineNetwork.renormalized',discretization='direct incident/reflected wave linear solve',
        tool='scikit-rf',tool_discretization='network.renormalize_s with power waves',
        matched=['identical lossy-line S samples and 50 to 30/90 ohm port references'],not_matched=[],
        observables=[observable('S','1','max absolute difference',difference,1e-10)],
        analytical_acceptance='reciprocity, passivity and reference roundtrip; not material validation',stopwatch=clock)
    record['openphysics']['distribution']='sipi'
    record['openphysics']['version']=metadata.version('sipi')
    emit(record)
    assert difference <= 1e-10
    np.testing.assert_allclose(changed.s, changed.s.swapaxes(-1,-2), rtol=0, atol=1e-12)
    assert np.max(np.linalg.svd(changed.s,compute_uv=False)) <= 1+1e-12
    np.testing.assert_allclose(changed.renormalized(50).s, net.s, rtol=0, atol=1e-12)


@pytest.mark.parametrize('target', [0,-1,True,50+1j,np.nan,np.inf,[50],[[50,75]],
                                   [50,True],[50,0],[50,np.inf]])
def test_invalid_reference_rejected(target):
    net = LineNetwork([0], np.zeros((1,2,2)), 50, ('a','b'))
    with pytest.raises(ValueError,match='z_ref'):
        net.renormalized(target)


def test_singular_active_network_change_is_not_regularized():
    net = LineNetwork([0], [[[5/3]]], 50, ('active',))
    with pytest.raises(ValueError,match='singular'):
        net.renormalized(200)


def test_unrepresentable_reference_ratio_is_rejected():
    net = LineNetwork([0], [[[0]]], 1e308, ('a',))
    with pytest.raises(ValueError,match='representable'):
        net.renormalized(5e-324)


@pytest.mark.parametrize('ports', [1,2,4])
@pytest.mark.parametrize('target_kind', ['scalar','vector'])
def test_independent_skrf_renormalization(ports,target_kind):
    skrf = require_tool('scikit-rf')
    f = np.array([1e3,1e6,1e9])
    rng = np.random.default_rng(711+ports)
    s = (rng.normal(size=(3,ports,ports))+1j*rng.normal(size=(3,ports,ports)))*.05
    # Deliberately nonreciprocal data detects transposes and incorrect row scaling.
    old = np.linspace(30,90,ports)
    target = 75 if target_kind == 'scalar' else np.linspace(25,110,ports)
    net = LineNetwork(f,s,old,tuple(f'p{i+1}' for i in range(ports)))
    clock = Stopwatch()
    with clock('openphysics'):
        changed = net.renormalized(target)
    with clock('reference'):
        expected = skrf.network.renormalize_s(s,old,target,s_def='power')
    error = float(np.max(abs(changed.s-expected)))
    record = make_record(case=f's-renormalization-{ports}-{target_kind}',
        physics='power-wave reference transformation',api='sipi.LineNetwork.renormalized',
        discretization='direct incident/reflected wave linear solve',tool='scikit-rf',
        tool_discretization='network.renormalize_s with power waves',
        matched=['identical complex S samples, port ordering and positive real references',
                 'frequency-independent per-port reference impedances'],not_matched=[],
        observables=[observable('S','1','max absolute difference',error,1e-10)],
        analytical_acceptance='complex load, ideal through, open/short, reciprocity and passivity; no FEM accuracy inferred',
        stopwatch=clock)
    record['openphysics']['distribution']='sipi'
    record['openphysics']['version']=metadata.version('sipi')
    emit(record)
    assert error <= 1e-10
