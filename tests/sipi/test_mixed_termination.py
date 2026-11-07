# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Mixed ideal and finite boundaries against independent nodal circuits."""
from importlib import metadata

import numpy as np
import pytest

from sipi import (LineNetwork, rlgc_network,
                  terminate_norton_network, terminate_mixed_network)
from sipi.termination import terminate_network
from test_norton_termination import network_from_y
from crosscheck import Stopwatch, emit, make_record, observable, require_tool

GATE = 1e-12


def thevenin(voltage=0., impedance=50.):
    return dict(kind='thevenin',source_voltage=voltage,impedance=impedance)


def norton(current=0., admittance=.02):
    return dict(kind='norton',source_current=current,admittance=admittance)


def coupled(mixed=False):
    net=rlgc_network([0.,1e8,2e8],R=[[3.,.2],[.2,4.]],
        L=np.array([[300.,40.],[40.,260.]])*1e-9,G=[[.004,-.001],[-.001,.003]],
        C=np.array([[100.,-20.],[-20.,90.]])*1e-12,length=.07)
    return net.mixed_mode() if mixed else net


def power_check(result):
    np.testing.assert_allclose(result.source_power,result.network_power+result.termination_power,atol=GATE,rtol=GATE)
    weight=np.where(result.frequency==0,1.,.5)
    expected=weight*np.sum(abs(result.a)**2-abs(result.b)**2,axis=1)
    np.testing.assert_allclose(result.network_power,expected,atol=GATE,rtol=GATE)
    assert np.min(result.termination_power)>=-GATE
    assert np.max(result.boundary_residual)<=1e-10
    assert np.max(result.wave_residual)<=1e-10


@pytest.mark.parametrize('mixed',[False,True])
@pytest.mark.parametrize('kind',['thevenin','norton'])
def test_homogeneous_boundaries_match_existing_api_and_same_topology_power(mixed,kind):
    net=coupled(mixed);rng=np.random.default_rng(193)
    source=rng.normal(size=(3,4))*.01+1j*rng.normal(size=(3,4))*.001
    load=.03+.01j*np.arange(3)[:,None]+np.arange(4)*.005
    if kind=='thevenin':load=1/load
    boundaries={name:(thevenin if kind=='thevenin' else norton)(s,z)
                for name,s,z in zip(net.port_names,source.T,load.T)}
    actual=terminate_mixed_network(net,boundaries)
    expected=(terminate_network(net,source_voltages=dict(zip(net.port_names,source.T)),
                               terminations=dict(zip(net.port_names,load.T))) if kind=='thevenin'
              else terminate_norton_network(net,source_currents=dict(zip(net.port_names,source.T)),
                                            termination_admittances=dict(zip(net.port_names,load.T))))
    for name in ('a','b','voltage','current','network_power','source_power','termination_power'):
        np.testing.assert_allclose(getattr(actual,name),getattr(expected,name),atol=GATE,rtol=GATE)
    assert actual.kinds==(kind,)*4 and actual.basis==net.basis
    power_check(actual)


@pytest.mark.parametrize('mixed',[False,True])
def test_mixed_finite_sources_equivalent_external_response_and_renormalization(mixed):
    net=coupled(mixed);p=net.port_names
    boundary={p[0]:thevenin(1+.2j,30+2j),p[1]:norton(.003-.001j,.02+.005j),
              p[2]:thevenin(.1,75),p[3]:norton(0,.01)}
    result=terminate_mixed_network(net,boundary)
    voltages={p[0]:1+.2j,p[1]:(.003-.001j)/(.02+.005j),p[2]:.1,p[3]:0}
    loads={p[0]:30+2j,p[1]:1/(.02+.005j),p[2]:75,p[3]:100}
    equivalent=terminate_network(net,source_voltages=voltages,terminations=loads)
    for key in ('a','b','voltage','current','network_power'):
        np.testing.assert_allclose(getattr(result,key),getattr(equivalent,key),atol=GATE,rtol=GATE)
    renormalized=terminate_mixed_network(net.renormalized([25.,70.,40.,90.]),boundary)
    for key in ('voltage','current','network_power','termination_power','source_power'):
        np.testing.assert_allclose(getattr(result,key),getattr(renormalized,key),atol=GATE,rtol=GATE)
    power_check(result);power_check(renormalized)


def test_ideal_voltage_and_open_lossless_line_including_dc():
    f=np.array([0.,1e8,2e8]);net=rlgc_network(f,R=[[0.]],G=[[0.]],L=[[250e-9]],C=[[100e-12]],length=.1)
    result=terminate_mixed_network(net,{'near:1':thevenin(1.,0.),'far:1':norton(0.,0.)})
    theta=2*np.pi*f*.1*5e-9
    expected_v=np.column_stack((np.ones(3),1/np.cos(theta)))
    expected_i=np.column_stack((1j*np.tan(theta)/50,np.zeros(3)))
    np.testing.assert_allclose(result.voltage,expected_v,atol=GATE,rtol=0)
    np.testing.assert_allclose(result.current,expected_i,atol=GATE,rtol=0)
    np.testing.assert_allclose(result.source_power,0,atol=GATE,rtol=0)
    assert result.kinds==('thevenin','norton')
    power_check(result)


def test_ideal_voltage_source_and_short_resistive_bridge():
    conductance=1/37.
    y=np.tile([[conductance,-conductance],[-conductance,conductance]],(3,1,1))
    net=network_from_y(np.array([0.,1e8,2e8]),y,np.array([25.,90.]),('a','b'))
    result=terminate_mixed_network(net,{'a':thevenin(.7,0),'b':thevenin(0,0)})
    np.testing.assert_allclose(result.voltage,[[.7,0]]*3,atol=GATE,rtol=0)
    np.testing.assert_allclose(result.current,[[.7/37,-.7/37]]*3,atol=GATE,rtol=0)
    power_check(result)


@pytest.mark.parametrize('tool',['scipy','scikit-rf'])
@pytest.mark.parametrize('load',[0.,.02])
def test_independent_rlc_pi_with_ideal_voltage_and_norton_free_node(tool,load):
    reference=require_tool(tool);f=np.array([0.,1e7,7e7,2e8]);omega=2*np.pi*f
    bridge=1/(17+1j*omega*2e-9)
    y=np.zeros((4,2,2),complex)
    y[:,0,0]=1/83+1j*omega*1.2e-12+bridge
    y[:,1,1]=1/97+1j*omega*.8e-12+bridge;y[:,0,1]=y[:,1,0]=-bridge
    net=network_from_y(f,y,np.array([25.,90.]),('a','b'))
    drive=np.array([.5,.6+.1j,.4-.2j,.7+.1j]);injected=np.array([0.,.001j,-.002,0.])
    # load=0 covers an exactly open DC port and ideal AC current injection.
    shunt=load+1j*omega*load*1e-10
    boundary={'a':thevenin(drive,0.),'b':norton(injected,shunt)}
    timer=Stopwatch()
    with timer('openphysics'):actual=terminate_mixed_network(net,boundary)
    with timer('reference'):
        if tool=='scipy':
            from scipy.linalg import solve
            nodal=y
        else:
            solve=np.linalg.solve;nodal=reference.network.s2y(net.s,z0=net.z_ref,s_def='power')
        v=np.empty((4,2),complex);v[:,0]=drive
        for k in range(4):
            v[k,1]=solve(np.array([[nodal[k,1,1]+shunt[k]]]),
                         np.array([injected[k]-nodal[k,1,0]*drive[k]]))[0]
        current=np.einsum('fij,fj->fi',nodal,v)
    errors=[float(np.max(abs(actual.voltage-v))),float(np.max(abs(actual.current-current)))]
    rec=make_record(case=f'mixed-terminal-pi-{tool}-{load}',physics='RLC pi with fixed voltage and open/current/shunt terminal',
        api='sipi.terminate_mixed_network',discretization='mixed Thevenin/Norton wave feedback',
        tool=tool,tool_discretization='fixed-voltage/free-node '+('analytic RLC nodal solve' if tool=='scipy' else 's2y nodal solve'),
        matched=['same RLC pi, frequency grid and reference impedances','same ideal voltage and finite or zero Norton shunt'],
        not_matched=['no measured or new field accuracy','no time-domain startup or network passivity certificate'],
        observables=[observable(name,unit,'max absolute difference',error,GATE)
                     for name,unit,error in zip(('voltage','current'),('V','A'),errors)],
        analytical_acceptance='ideal-voltage/open lossless line, resistor short current and source/load power balance',stopwatch=timer)
    rec['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(rec)
    assert max(errors)<=GATE
    power_check(actual)


def test_superposition_snapshots_and_boundary_residual_units():
    net=coupled();p=net.port_names;source=np.array([1.,2.,3.])
    boundary={p[0]:thevenin(source,0),p[1]:norton(0,0),p[2]:thevenin(.1,50),p[3]:norton(.003,.02)}
    result=terminate_mixed_network(net,boundary);source[:]=0
    np.testing.assert_array_equal(result.source_voltages[:,0],[1,2,3])
    assert result.boundary_residual.shape==(3,4)
    for key in ('source_voltages','series_impedances','source_currents','shunt_admittances','a','b',
                'voltage','current','condition_number','boundary_residual','wave_residual','source_power'):
        assert not getattr(result,key).flags.writeable
    first=terminate_mixed_network(net,{p[0]:thevenin([1,2,3],0),p[1]:norton(0,0),p[2]:thevenin(0,50),p[3]:norton(0,.02)})
    second=terminate_mixed_network(net,boundary)
    np.testing.assert_allclose(result.voltage,first.voltage+second.voltage,atol=GATE,rtol=GATE)
    # KVL and KCL are checked independently, including cancellation at the open.
    np.testing.assert_allclose(result.voltage[:,0],[1,2,3],atol=GATE,rtol=0)
    np.testing.assert_allclose(result.current[:,1],0,atol=GATE,rtol=0)
    power_check(result)


@pytest.mark.parametrize('boundary',[
    {},[],{'bad':thevenin()}, {'p':'open'}, {'p':dict(kind='wrong')},
    {'p':dict(kind='thevenin',source_voltage=1)},
    {'p':dict(kind='norton',source_current=1)},
    {'p':dict(kind='thevenin',source_voltage=1,impedance=0,admittance=0)},
    {'p':thevenin(True)}, {'p':norton(True)}, {'p':thevenin(1,True)}, {'p':norton(1,True)},
    {'p':thevenin(1,-1)}, {'p':norton(1,-1)},
    {'p':thevenin(float('inf'))}, {'p':norton(float('nan'))},
    {'p':thevenin(0,float('inf'))}, {'p':norton(0,float('inf'))},
    {'p':thevenin([1,2,3])}, {'p':norton(1,[1,2,3])}, {'p':thevenin(1,'short')}
])
def test_strict_explicit_boundaries(boundary):
    net=LineNetwork([0,1],np.zeros((2,1,1)),50.,('p',))
    with pytest.raises(ValueError):terminate_mixed_network(net,boundary)


def test_floating_open_inconsistent_short_and_numeric_overflow():
    for s,boundary in [(1.,norton(0,0)),(-1.,thevenin(1,0))]:
        net=LineNetwork([0,1],np.full((2,1,1),s),50.,('p',))
        with pytest.raises(ValueError,match='condition|singular'):terminate_mixed_network(net,{'p':boundary})
    net=LineNetwork([0,1],np.zeros((2,1,1)),50.,('p',))
    with pytest.raises(ValueError,match='nonfinite'):
        terminate_mixed_network(net,{'p':norton(1,1e308)})
    response=terminate_mixed_network(net,{'p':thevenin(1e200,50)})
    with pytest.raises(ValueError,match='power overflow'):_=response.source_power
    with pytest.raises(TypeError):terminate_mixed_network(None,{'p':thevenin()})


def test_finite_ill_conditioned_feedback_and_impedance_sum_overflow():
    s=np.tile(np.diag([1-1e-14,0.]),(2,1,1))
    net=LineNetwork([0,1],s,50.,('a','b'))
    with pytest.raises(ValueError,match='condition'):
        terminate_mixed_network(net,{'a':norton(0,0),'b':thevenin(0,50)})
    huge=LineNetwork([0,1],np.zeros((2,1,1)),1e308,('p',))
    with pytest.raises(ValueError,match='nonfinite'):
        terminate_mixed_network(huge,{'p':thevenin(0,1e308)})
