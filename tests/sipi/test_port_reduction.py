# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Passive load feedback: analytic line ends, junctions and independent connect."""
import importlib.metadata as metadata
import numpy as np
import pytest
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import LineNetwork, rlgc_network, terminate_ports


def tee():
    return LineNetwork([0,1e6,1e9],np.tile(2/3*np.ones((3,3))-np.eye(3),(3,1,1)),
                       50,('left','right','branch'))


@pytest.mark.parametrize('load,gamma',[('open',1),('short',-1),(0,-1),(50,0),(150,.5)])
def test_uniform_line_end_reflection_at_dc_quarter_and_half_wave(load,gamma):
    f=np.array([0,1e9,5e9,10e9])
    length=.01;velocity=2e8
    line=rlgc_network(f,R=[[0]],L=[[250e-9]],G=[[0]],C=[[100e-12]],
                      length=length,z_ref=50,names=['trace'])
    reduced=terminate_ports(line,{'far:trace':load})
    expected=gamma*np.exp(-2j*2*np.pi*f/velocity*length)
    np.testing.assert_allclose(reduced.s[:,0,0],expected,rtol=0,atol=1e-12)
    assert reduced.port_names==('near:trace',)
    assert reduced.s.shape==(4,1,1)


@pytest.mark.parametrize('load,expected',[
    ('open',[[0,1],[1,0]]),('short',[[-1,0],[0,-1]]),
    (50,[[-1/3,2/3],[2/3,-1/3]])])
def test_ideal_junction_with_open_short_and_matched_shunt(load,expected):
    net=terminate_ports(tee(),{'branch':load})
    np.testing.assert_allclose(net.s,np.broadcast_to(expected,net.s.shape),rtol=0,atol=1e-12)


@pytest.mark.parametrize('basis',['single-ended','mixed-mode'])
def test_multiple_unequal_reference_complex_loads_against_independent_connect(basis):
    skrf=require_tool('scikit-rf')
    rng=np.random.default_rng(931)
    s=.07*(rng.normal(size=(3,5,5))+1j*rng.normal(size=(3,5,5)))
    refs=np.array([30.,45.,60.,75.,90.])
    names=('a','b','c','d','e')
    net=LineNetwork([0,1e6,1e9],s,refs,names,basis)
    loads={'e':np.array([25+10j,100-30j,0]),'b':'open','d':'short'}
    original=net.s.copy()
    clock=Stopwatch()
    with clock('openphysics'):
        actual=terminate_ports(net,loads)
        # Mapping insertion order must not alter the internal port ordering.
        reordered=terminate_ports(net,dict(reversed(list(loads.items()))))
    with clock('reference'):
        ref=skrf.Network(frequency=skrf.Frequency.from_f(net.frequency,unit='Hz'),s=s,z0=refs)
        ports=list(names)
        for name,load in loads.items():
            i=ports.index(name);zref=refs[names.index(name)]
            gamma=np.ones(3) if isinstance(load,str) and load=='open' else (
                -np.ones(3) if isinstance(load,str) else (load-zref)/(load+zref))
            termination=skrf.Network(frequency=ref.frequency,s=gamma[:,None,None],z0=zref)
            ref=skrf.network.connect(ref,i,termination,0)
            ports.pop(i)
    error=float(np.max(abs(actual.s-ref.s)))
    record=make_record(case='passive-port-reduction-'+basis,physics='loaded multiport network',
        api='sipi.terminate_ports',discretization='simultaneous loaded-port scattering feedback solve',
        tool='scikit-rf',tool_discretization='sequential connect to independent one-port loads',
        matched=['same nonreciprocal S samples, frequency and unequal real references',
                 'explicit open, short and frequency-dependent passive complex loads in the stated basis'],
        not_matched=['no electromagnetic geometry or time-domain interpretation'],
        observables=[observable('reduced S','1','max absolute difference',error,1e-10)],
        analytical_acceptance='lossless line end phase and ideal three-port junction identities',stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'))
    emit(record)
    assert error<1e-10
    np.testing.assert_array_equal(actual.s,reordered.s)
    np.testing.assert_array_equal(net.s,original)
    np.testing.assert_array_equal(actual.z_ref,[30,60])
    assert actual.port_names==('a','c') and actual.basis==basis
    assert not actual.s.flags.writeable and not np.shares_memory(net.s,actual.s)
    assert np.linalg.svd(actual.s,compute_uv=False).max()<1
    assert np.max(abs(actual.s-actual.s.swapaxes(1,2)))>.01


def test_loaded_port_order_can_be_noncontiguous_and_input_arrays_are_not_retained():
    load=np.array([50,100,150.])
    net=tee()
    a=terminate_ports(net,{'left':load,'branch':'open'})
    load[:]=0
    assert a.port_names==('right',)
    np.testing.assert_allclose(a.s[:,0,0],[0,1/3,.5],rtol=0,atol=1e-12)
    np.testing.assert_array_equal(a.frequency,net.frequency)


@pytest.mark.parametrize('scale',[1e-300,1e300,np.finfo(float).max])
def test_large_and_small_finite_loads_do_not_overflow_reference_sum(scale):
    through=LineNetwork([0],[[[0,1],[1,0]]],scale,('a','b'))
    with np.errstate(all='raise'):
        matched=terminate_ports(through,{'b':scale})
        reactive=terminate_ports(through,{'b':1j*scale})
    np.testing.assert_allclose(matched.s,0,rtol=0,atol=1e-14)
    np.testing.assert_allclose(reactive.s,1j,rtol=0,atol=1e-14)


@pytest.mark.parametrize('loads',[
    None,[],{}, {'unknown':50},{1:50},{'branch':'matched'}, {'branch':True},
    {'branch':None},{'branch':-1},{'branch':-1+1j},{'branch':np.inf},
    {'branch':np.nan},{'branch':[50,50]},{'branch':[[50,50,50]]},
    {'branch':[True,50,50]},{'left':50,'right':50,'branch':50},
])
def test_invalid_loads(loads):
    with pytest.raises(ValueError):terminate_ports(tee(),loads)


def test_network_type_and_singular_feedback_are_rejected():
    with pytest.raises(TypeError):terminate_ports({}, {'a':50})
    isolated=LineNetwork([0],[np.eye(2)],50,('retained','loaded'))
    with pytest.raises(ValueError,match='singular'):
        terminate_ports(isolated,{'loaded':'open'})
    s=np.diag([0,0,1-1e-14])
    ill=LineNetwork([0],[s],50,('keep','load1','load2'))
    with pytest.raises(ValueError,match='ill-conditioned'):
        terminate_ports(ill,{'load1':'open','load2':'open'})
