# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Norton/open boundary circuits against independent nodal and line solutions."""
from importlib import metadata

import numpy as np
import pytest

from sipi import LineNetwork, rlgc_network, terminate_norton_network
from sipi.termination import terminate_network
from crosscheck import Stopwatch, emit, make_record, observable, require_tool

GATE=1e-12


def network_from_y(frequency,y,refs,names):
    root=np.sqrt(refs)
    normalized=root[None,:,None]*y*root[None,None,:]
    eye=np.eye(len(refs))
    scattering=np.linalg.solve(eye+normalized,eye-normalized)
    return LineNetwork(frequency,scattering,refs,names)


def one_port():
    f=np.array([0.,1e7,4e8]);y=(.01+2j*np.pi*f*2e-12)[:,None,None]
    return network_from_y(f,y,np.array([50.]),('p',)),y[:,0,0]


def pi_network():
    f=np.array([0.,1e7,4e8]);omega=2*np.pi*f
    bridge=1/(17+1j*omega*2e-9)
    ya=1/83+1j*omega*1.2e-12;yb=1/97+1j*omega*.8e-12
    y=np.zeros((3,2,2),complex)
    y[:,0,0]=ya+bridge;y[:,1,1]=yb+bridge;y[:,0,1]=y[:,1,0]=-bridge
    return network_from_y(f,y,np.array([25.,90.]),('a','b')),y


def check_power(result):
    np.testing.assert_allclose(result.source_power,result.network_power+result.termination_power,atol=GATE,rtol=GATE)
    weight=np.where(result.frequency==0,1.,.5)
    wave=weight*np.sum(abs(result.a)**2-abs(result.b)**2,axis=1)
    np.testing.assert_allclose(result.network_power,wave,atol=GATE,rtol=GATE)
    assert result.termination_power.min()>=-GATE
    assert result.kcl_residual.max()<=1e-10 and result.wave_residual.max()<=1e-10


@pytest.mark.parametrize('load',[0.,.02,.01+.003j])
def test_analytic_rc_norton_divider_and_ideal_current_source(load):
    net,y=one_port();source=np.array([.002,.001+.003j,-.001j])
    solved=terminate_norton_network(net,source_currents={'p':source},termination_admittances={'p':load})
    v=source/(y+load)
    np.testing.assert_allclose(solved.voltage[:,0],v,atol=GATE,rtol=0)
    np.testing.assert_allclose(solved.current[:,0],y*v,atol=GATE,rtol=0)
    np.testing.assert_allclose(solved.source_currents,solved.current+solved.termination_admittances*solved.voltage,atol=GATE,rtol=0)
    check_power(solved)


def test_default_matched_admittance_missing_source_zero_and_snapshot():
    net,_=pi_network();source=np.array([.002,.001+.003j,-.001j])
    solved=terminate_norton_network(net,source_currents={'b':source})
    original=source.copy();source[:]=0
    np.testing.assert_array_equal(solved.source_currents[:,1],original)
    np.testing.assert_array_equal(solved.source_currents[:,0],0.)
    np.testing.assert_array_equal(solved.termination_admittances,np.broadcast_to(1/net.z_ref,(3,2)))
    np.testing.assert_allclose(solved.a,solved.source_currents*np.sqrt(net.z_ref)/2,atol=GATE,rtol=0)
    assert solved.network is not net
    assert solved.port_names==net.port_names and solved.basis==net.basis
    for field in ('source_currents','termination_admittances','a','b','voltage','current',
                  'condition_number','kcl_residual','wave_residual','network_power','termination_power','source_power'):
        assert not getattr(solved,field).flags.writeable
    check_power(solved)


@pytest.mark.parametrize('tool',['scipy','scikit-rf'])
def test_independent_nodal_pi_network_with_open_and_complex_loads(tool):
    ref=require_tool(tool);net,y=pi_network()
    currents=np.array([[.002,.001],[.001+.002j,0],[.002j,-.001j]])
    admittance=np.array([[.01,0],[.02+.003j,0],[.01-.002j,.03+.004j]])
    clock=Stopwatch()
    with clock('openphysics'):
        result=terminate_norton_network(net,source_currents=dict(zip(net.port_names,currents.T)),
            termination_admittances=dict(zip(net.port_names,admittance.T)))
    with clock('reference'):
        if tool=='scipy':
            from scipy.linalg import solve
            yn=y
        else:
            solve=np.linalg.solve
            yn=ref.network.s2y(net.s,z0=net.z_ref,s_def='power')
        expected_v=np.array([solve(matrix+np.diag(load),source)
            for matrix,load,source in zip(yn,admittance,currents)])
        expected_i=np.einsum('fij,fj->fi',yn,expected_v)
    errors=[float(np.max(abs(result.voltage-expected_v))),float(np.max(abs(result.current-expected_i)))]
    record=make_record(case='norton-open-pi-'+tool,physics='Norton-driven passive two-port pi circuit',
        api='sipi.terminate_norton_network',discretization='current-source wave feedback at explicit frequency samples',
        tool=tool,tool_discretization='direct nodal '+('analytic RLC admittance' if tool=='scipy' else 'independent s2y conversion'),
        matched=['same explicit RLC circuit, current sources, passive parallel loads and open port',
                 'same DC/positive frequency samples and unequal real port references'],
        not_matched=['no independent field extraction or measured accuracy','no causal transient or stability certificate'],
        observables=[observable(name,unit,'max absolute difference',value,GATE)
                     for name,unit,value in zip(('voltage','current'),('V','A'),errors)],
        analytical_acceptance='RC divider, lossless open-line transmission, Thevenin duality and average-power conservation',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    assert max(errors)<=GATE
    assert abs(result.current[1,1])<=GATE  # exact open boundary with zero source
    assert abs(result.current[0,1]-.001)<=GATE  # ideal current source, same Y=0
    check_power(result)


@pytest.mark.parametrize('mixed',[False,True])
def test_actual_coupled_rlgc_thevenin_equivalence_and_reference_invariance(mixed):
    net=rlgc_network([0.,1e8,1e9],R=[[3.,.2],[.2,4.]],
        L=np.array([[300.,40.],[40.,260.]])*1e-9,G=[[.004,-.001],[-.001,.003]],
        C=np.array([[100.,-20.],[-20.,90.]])*1e-12,length=.07)
    if mixed:net=net.mixed_mode()
    rng=np.random.default_rng(67);currents=.001*(rng.normal(size=(3,4))+1j*rng.normal(size=(3,4)))
    currents[0]=currents[0].real
    y=np.array([.02,.03,.01,.04])+2j*np.pi*net.frequency[:,None]*2e-12
    names=net.port_names
    result=terminate_norton_network(net,source_currents=dict(zip(names,currents.T)),
        termination_admittances=dict(zip(names,y.T)))
    other=terminate_network(net,source_voltages=dict(zip(names,(currents/y).T)),
        terminations=dict(zip(names,(1/y).T)))
    # Source conversion preserves external terminals, not internal source power
    # or series/shunt dissipation. Check each topology's power law separately.
    for name in ('voltage','current','a','b','network_power'):
        np.testing.assert_allclose(getattr(result,name),getattr(other,name),atol=GATE,rtol=GATE)
    weight=np.where(net.frequency==0,1.,.5)
    expected_shunt=weight*np.sum(y.real*abs(result.voltage)**2,axis=1)
    np.testing.assert_allclose(result.termination_power,expected_shunt,atol=GATE,rtol=GATE)
    np.testing.assert_allclose(other.source_power,other.network_power+other.termination_power,atol=GATE,rtol=GATE)
    changed=terminate_norton_network(net.renormalized([31.,43.,61.,79.]),
        source_currents=dict(zip(names,currents.T)),termination_admittances=dict(zip(names,y.T)))
    np.testing.assert_allclose(changed.voltage,result.voltage,atol=GATE,rtol=0)
    np.testing.assert_allclose(changed.current,result.current,atol=GATE,rtol=0)
    assert result.basis==net.basis
    check_power(result)


def test_open_lossless_line_voltage_current_and_input_impedance():
    f=np.array([1e8,2e8,5e8]);length=.1;z0=50.;theta=2*np.pi*f*length*5e-9
    net=rlgc_network(f,R=[[0.]],G=[[0.]],L=[[250e-9]],C=[[100e-12]],length=length)
    source=.002;ys=.02
    result=terminate_norton_network(net,source_currents={'near:1':source},
        termination_admittances={'near:1':ys,'far:1':0.})
    far=source/(ys*np.cos(theta)+1j*np.sin(theta)/z0)
    expected_v=np.column_stack((np.cos(theta)*far,far))
    expected_i=np.column_stack((1j*np.sin(theta)*far/z0,np.zeros(3)))
    np.testing.assert_allclose(result.voltage,expected_v,atol=GATE,rtol=0)
    np.testing.assert_allclose(result.current,expected_i,atol=GATE,rtol=0)
    np.testing.assert_allclose(result.voltage[:,0]/result.current[:,0],-1j*z0/np.tan(theta),atol=GATE,rtol=0)
    np.testing.assert_allclose(result.network_power,0.,atol=GATE,rtol=0)
    check_power(result)


def test_zero_sources_superposition_and_explicit_admittance_snapshot():
    net,_=pi_network();y=np.array([0.,.015,.03]);ya=np.array([.01,.03,.02])
    def solve(a,b):return terminate_norton_network(net,source_currents={'a':a,'b':b},
        termination_admittances={'a':ya,'b':y})
    ra,rb=solve(.001,0),solve(0,.002j)
    combined=solve(.002,-.0006j)
    np.testing.assert_allclose(combined.voltage,2*ra.voltage-.3*rb.voltage,atol=GATE,rtol=0)
    np.testing.assert_array_equal(solve(0,0).voltage,0.)
    original=y.copy();y[:]=.5
    np.testing.assert_array_equal(ra.termination_admittances[:,1],original)
    check_power(ra)


@pytest.mark.parametrize('value',[True,[0.,True,0.],None,'open',np.nan,np.inf,1j*np.inf,[1.,2.],[[1.,2.,3.]]])
def test_invalid_current_values(value):
    net,_=one_port()
    with pytest.raises(ValueError):terminate_norton_network(net,source_currents={'p':value})


@pytest.mark.parametrize('value',[True,[0.,True,0.],None,'open','short',np.nan,np.inf,-.01,[.01,-.01,.03],[1.,2.]])
def test_invalid_admittance_values(value):
    net,_=one_port()
    with pytest.raises(ValueError):terminate_norton_network(net,source_currents={'p':.001},termination_admittances={'p':value})


@pytest.mark.parametrize('sources,loads',[({},None),([],None),({'missing':0.},None),({1:0.},None),
    ({'p':0.},[]),({'p':0.},{'missing':0.})])
def test_invalid_mappings_and_ports(sources,loads):
    net,_=one_port()
    with pytest.raises(ValueError):terminate_norton_network(net,source_currents=sources,termination_admittances=loads)


def test_invalid_network():
    with pytest.raises(TypeError):terminate_norton_network(None,source_currents={'p':0.})


@pytest.mark.parametrize('reflection',[1.,1.-1e-13])
def test_floating_open_or_ill_conditioned_boundary_is_rejected(reflection):
    net=LineNetwork([0.],np.diag([reflection,0.])[None,:,:],[50.,50.],('a','b'))
    with pytest.raises(ValueError,match='ill-conditioned'):
        terminate_norton_network(net,source_currents={'b':.001},termination_admittances={'a':0.})


def test_active_supplied_network_is_not_silently_certified_passive():
    net=LineNetwork([0.,1e6],np.full((2,1,1),2.),[50.],('p',))
    result=terminate_norton_network(net,source_currents={'p':.001})
    assert np.all(result.network_power<0)
    check_power(result)


def test_numeric_and_average_power_overflow_are_explicit():
    net,_=one_port()
    for source,y in [(1e308,.01),(.001,1e308)]:
        with pytest.raises(ValueError,match='nonfinite'):
            terminate_norton_network(net,source_currents={'p':source},termination_admittances={'p':y})
    large=terminate_norton_network(net,source_currents={'p':1e154},termination_admittances={'p':.01})
    for name in ('network_power','termination_power','source_power'):
        with pytest.raises(ValueError,match='power overflow'):getattr(large,name)
