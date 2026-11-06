# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Named wiring, Kirchhoff nodes and one-dimensional shunt-stub circuits."""
import importlib.metadata as metadata
import numpy as np
import pytest
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import (LineNetwork, connect_networks, ideal_junction, rlgc_network,
                  cascade_networks, terminate_ports)


F = np.array([0., 1e8, 1e9, 5e9, 10e9])


def reference_network(tool, network):
    return tool.Network(frequency=tool.Frequency.from_f(network.frequency, unit='Hz'),
                        s=network.s.copy(), z0=network.z_ref)


def report(case, error, clock):
    record = make_record(case=case, physics='explicit single-ended circuit connections',
        api='sipi.connect_networks/ideal_junction',
        discretization='internal power-wave feedback and Kirchhoff junction',
        tool='scikit-rf', tool_discretization='connect, innerconnect and splitter',
        matched=['same S samples, explicit wiring, real references and port order'],
        not_matched=['no physical junction, via, pad or three-dimensional transition model'],
        observables=[observable('connected S', '1', 'max absolute difference', error, 1e-10)],
        analytical_acceptance='KCL, common voltage, unitarity and lossless shunt-stub closed forms',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi', version=metadata.version('sipi'))
    emit(record)
    assert error < 1e-10


@pytest.mark.parametrize('references', [[50,50], [25,50,120], [25,50,120,80]])
def test_junction_kirchhoff_reciprocity_unitarity_and_independent_splitter(references):
    tool = require_tool('scikit-rf'); clock = Stopwatch()
    n = len(references); names = tuple('p'+str(i) for i in range(n))
    with clock('openphysics'):
        actual = ideal_junction(F, port_names=names, z_ref=references)
    with clock('reference'):
        medium = tool.media.DefinedGammaZ0(frequency=tool.Frequency.from_f(F, unit='Hz'), z0=50)
        expected = medium.splitter(n, z0=references)
    report('junction-'+str(n), float(abs(actual.s-expected.s).max()), clock)
    np.testing.assert_allclose(actual.s @ actual.s.swapaxes(-1,-2),
                              np.broadcast_to(np.eye(n), actual.s.shape), rtol=0, atol=1e-12)
    np.testing.assert_allclose(actual.s, actual.s.swapaxes(-1,-2), rtol=0, atol=1e-12)
    incident = np.arange(1,n+1)+1j*np.arange(n)
    reflected = actual.s @ incident
    voltage = np.sqrt(actual.z_ref)*(incident+reflected)
    current = (incident-reflected)/np.sqrt(actual.z_ref)
    np.testing.assert_allclose(voltage, np.broadcast_to(voltage[:, :1], voltage.shape), rtol=0, atol=1e-12)
    np.testing.assert_allclose(current.sum(axis=1), 0, rtol=0, atol=1e-12)
    if n == 2:
        np.testing.assert_allclose(actual.s, np.broadcast_to([[0,1],[1,0]],actual.s.shape), atol=1e-12)
    assert actual.port_names == names and not actual.s.flags.writeable


def test_junction_extreme_references_do_not_overflow():
    refs = [np.nextafter(0.,1.), np.finfo(float).max]
    with np.errstate(over='raise', invalid='raise', divide='raise'):
        network = ideal_junction([0], port_names=['a','b'], z_ref=refs)
    assert np.all(np.isfinite(network.s))
    np.testing.assert_allclose(network.s[0]@network.s[0],np.eye(2),rtol=0,atol=1e-12)


def test_joined_junctions_form_one_common_voltage_node_with_unequal_references():
    a = ideal_junction(F,port_names=['a','b','link'],z_ref=[25,75,50])
    b = ideal_junction(F,port_names=['link','c','d'],z_ref=[50,90,120])
    joined = connect_networks(a,b,[('link','link')])
    expected = ideal_junction(F,port_names=['a','b','c','d'],z_ref=[25,75,90,120])
    np.testing.assert_allclose(joined.s,expected.s,rtol=0,atol=1e-12)


def random_network(prefix, refs, seed):
    rng = np.random.default_rng(seed); n = len(refs)
    s = .09*(rng.normal(size=(len(F),n,n))+1j*rng.normal(size=(len(F),n,n)))
    return LineNetwork(F,s,refs,tuple(prefix+str(i) for i in range(n)))


def test_simultaneous_crossed_pairs_against_independent_sequential_connection():
    tool = require_tool('scikit-rf'); clock = Stopwatch()
    a = random_network('a',[25,55,90,70],131)
    b = random_network('b',[70,40,55,110],137)
    pairs = [('a1','b2'),('a3','b0')]
    with clock('openphysics'):
        actual = connect_networks(a,b,pairs)
        reversed_pairs = connect_networks(a,b,pairs[::-1])
    with clock('reference'):
        first = tool.network.connect(reference_network(tool,a),1,reference_network(tool,b),2)
        expected = tool.network.innerconnect(first,2,3)
    report('crossed-multiple-pairs',float(abs(actual.s-expected.s).max()),clock)
    np.testing.assert_allclose(actual.s,reversed_pairs.s,rtol=0,atol=1e-12)
    assert actual.port_names == ('a0','a2','b1','b3')
    np.testing.assert_array_equal(actual.z_ref,[25,90,40,110])
    np.testing.assert_array_equal(actual.frequency,F)
    assert np.linalg.svd(actual.s,compute_uv=False).max() <= 1+1e-12
    assert not actual.s.flags.writeable and not np.shares_memory(actual.s,a.s)


@pytest.mark.parametrize('n',[1,2])
def test_near_far_connections_recover_cascade_and_uniform_line(n):
    eye = np.eye(n)
    def line(length):
        return rlgc_network(F,R=3*eye,L=250e-9*eye,G=.002*eye,C=100e-12*eye,length=length)
    a,b = line(.02),line(.03)
    joined = connect_networks(a,b,list(zip(a.port_names[n:],b.port_names[:n])))
    np.testing.assert_allclose(joined.s,cascade_networks(a,b).s,rtol=0,atol=1e-12)
    np.testing.assert_allclose(joined.s,line(.05).s,rtol=0,atol=1e-10)


@pytest.mark.parametrize('ending',['open','short'])
@pytest.mark.parametrize('stub_z',[35.,50.,85.])
def test_shunt_stub_dc_quarter_and_half_wave_closed_forms(ending,stub_z):
    # v=2e8 m/s and length=.01 m: 5 GHz quarter-wave, 10 GHz half-wave.
    stub = rlgc_network(F,R=[[0]],G=[[0]],L=[[stub_z/2e8]],C=[[1/(stub_z*2e8)]],
                         length=.01,z_ref=50,names=['stub'])
    node = ideal_junction(F,port_names=['input','output','branch'])
    connected = connect_networks(node,stub,[('branch','near:stub')])
    result = terminate_ports(connected,{'far:stub':ending})
    angle = 2*np.pi*F*.01/2e8
    if ending == 'open':
        d = 2*stub_z*np.cos(angle)+1j*50*np.sin(angle)
        reflection = -1j*50*np.sin(angle)/d
        transmission = 2*stub_z*np.cos(angle)/d
    else:
        d = 2j*stub_z*np.sin(angle)+50*np.cos(angle)
        reflection = -50*np.cos(angle)/d
        transmission = 2j*stub_z*np.sin(angle)/d
    np.testing.assert_allclose(result.s[:,0,0],reflection,rtol=0,atol=1e-12)
    np.testing.assert_allclose(result.s[:,1,0],transmission,rtol=0,atol=1e-12)
    np.testing.assert_allclose(result.s,result.s.swapaxes(-1,-2),rtol=0,atol=1e-12)
    np.testing.assert_allclose(result.s.conj().swapaxes(-1,-2)@result.s,
                              np.broadcast_to(np.eye(2),result.s.shape),rtol=0,atol=1e-12)
    # Eliminating the stub end before or after joining describes the same circuit.
    reduced_stub = terminate_ports(stub,{'far:stub':ending})
    alternate = connect_networks(node,reduced_stub,[('branch','near:stub')])
    np.testing.assert_allclose(alternate.s,result.s,rtol=0,atol=1e-12)


def test_lossy_loaded_stub_against_input_admittance_and_independent_connect():
    tool = require_tool('scikit-rf'); clock = Stopwatch()
    r,l,g,c,length = 4.,300e-9,.003,100e-12,.025
    load = 75+10j
    stub = rlgc_network(F,R=[[r]],L=[[l]],G=[[g]],C=[[c]],length=length,names=['stub'])
    node = ideal_junction(F,port_names=['input','output','branch'])
    with clock('openphysics'):
        actual = terminate_ports(connect_networks(node,stub,[('branch','near:stub')]),{'far:stub':load})
    with clock('reference'):
        junction = tool.media.DefinedGammaZ0(frequency=tool.Frequency.from_f(F,unit='Hz'),z0=50).splitter(3)
        combined = tool.network.connect(junction,2,reference_network(tool,stub),0)
        termination = tool.Network(frequency=junction.frequency,s=np.full((len(F),1,1),(load-50)/(load+50)),z0=50)
        expected = tool.network.connect(combined,2,termination,0)
    report('lossy-loaded-shunt-stub',float(abs(actual.s-expected.s).max()),clock)
    z,y = r+2j*np.pi*F*l,g+2j*np.pi*F*c
    zc,gamma = np.sqrt(z/y),np.sqrt(z*y)
    t = np.tanh(gamma*length)
    yin = (zc+load*t)/(zc*(load+zc*t))
    np.testing.assert_allclose(actual.s[:,0,0],-50*yin/(2+50*yin),rtol=0,atol=1e-12)
    np.testing.assert_allclose(actual.s[:,1,0],2/(2+50*yin),rtol=0,atol=1e-12)


@pytest.mark.parametrize('pairs',[None,[],{},'a0,b0',[('a0',)],[('a0','b0','b1')],
    [(False,'b0')],[('absent','b0')],[('a0','absent')],
    [('a0','b0'),('a0','b1')],[('a0','b0'),('a1','b0')],
    [('a0','b0'),('a1','b1')]])
def test_invalid_wiring_rejected(pairs):
    a,b = random_network('a',[50,50],1),random_network('b',[50,50],2)
    with pytest.raises(ValueError):connect_networks(a,b,pairs)


@pytest.mark.parametrize('change',['frequency','reference','basis','type'])
def test_incompatible_inputs_rejected(change):
    a,b = random_network('a',[50,50],1),random_network('b',[50,50],2)
    if change=='frequency':b=LineNetwork(F+1,b.s,b.z_ref,b.port_names)
    elif change=='reference':b=b.renormalized(75)
    elif change=='basis':b=LineNetwork(F,b.s,b.z_ref,b.port_names,'mixed-mode')
    else:b=object()
    with pytest.raises((ValueError,TypeError)):connect_networks(a,b,[('a1','b0')])


@pytest.mark.parametrize('names,refs',[(None,50),('abc',50),(['a'],50),(['a','a'],50),
    (['a',''],50),(['a','b'],True),(['a','b'],[50]),(['a','b'],[50,0]),(['a','b'],np.inf)])
def test_invalid_junction_rejected(names,refs):
    with pytest.raises(ValueError):ideal_junction(F,port_names=names,z_ref=refs)


def test_name_collisions_need_explicit_names_and_one_external_port_is_allowed():
    a = ideal_junction(F,port_names=['outside','inside'])
    b = ideal_junction(F,port_names=['inside','outside'])
    with pytest.raises(ValueError,match='unique'):connect_networks(a,b,[('inside','inside')])
    result = connect_networks(a,b,[('inside','inside')],port_names=['left','right'])
    assert result.port_names==('left','right')
    one = LineNetwork(F,np.zeros((len(F),1,1)),50,('load',))
    reduced = connect_networks(a,one,[('inside','load')])
    assert reduced.port_names==('outside',)
    np.testing.assert_allclose(reduced.s,0,atol=1e-12)


@pytest.mark.parametrize('reflection',[1.,1-1e-13])
def test_singular_and_ill_conditioned_closed_loops_rejected(reflection):
    a = LineNetwork([0],[np.diag([0,reflection])],50,('out','loop'))
    b = LineNetwork([0],[[[reflection]]],50,('loop',))
    with pytest.raises(ValueError,match='singular|ill-conditioned'):
        connect_networks(a,b,[('loop','loop')])


def test_nonfinite_feedback_output_is_rejected():
    a = LineNetwork([0],[[[0,1e308],[0,0]]],50,('out','join'))
    b = LineNetwork([0],[[[0,1e308],[0,0]]],50,('join','out2'))
    with pytest.raises(ValueError,match='nonfinite'):
        connect_networks(a,b,[('join','join')])
