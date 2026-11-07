# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Periodic current boundaries, independent nodal harmonics and time power."""
from importlib import metadata

import numpy as np
import pytest

from sipi import LineNetwork, rlgc_network, periodic_norton_response, terminate_norton_network
from test_periodic_termination import phasors, samples
from test_norton_termination import network_from_y
from crosscheck import Stopwatch, emit, make_record, observable, require_tool

GATE=1e-12


def resistor(resistance=100.,bins=5,df=1e7):
    return LineNetwork(np.arange(bins)*df,np.full((bins,1,1),(resistance-50)/(resistance+50)),[50.],('p',))


def check_power(result):
    response=result.response;harmonic=result.frequency_solution
    np.testing.assert_allclose(result.source_currents,response.current+result.termination_currents,atol=GATE,rtol=0)
    np.testing.assert_allclose(response.voltage*response.current,
        response.incident**2-response.reflected**2,atol=GATE,rtol=0)
    network=np.mean(np.sum(response.voltage*response.current,axis=1))
    shunt=np.mean(np.sum(response.voltage*result.termination_currents,axis=1))
    source=np.mean(np.sum(response.voltage*result.source_currents,axis=1))
    np.testing.assert_allclose([network,shunt,source],
        [harmonic.network_power.sum(),harmonic.termination_power.sum(),harmonic.source_power.sum()],atol=GATE,rtol=0)
    assert abs(source-network-shunt)<=GATE and shunt>=-GATE


@pytest.mark.parametrize('admittance',[0.,.02])
def test_dc_and_ac_current_division_ideal_source_and_snapshots(admittance):
    t=np.arange(9)/9;drive=.001+.002*np.cos(2*np.pi*t)+.0006*np.sin(4*np.pi*t)
    original=drive.copy()
    result=periodic_norton_response(resistor(),source_currents={'p':drive},
        termination_admittances={'p':admittance})
    drive[:]=0
    np.testing.assert_array_equal(result.source_currents[:,0],original)
    np.testing.assert_allclose(result.response.voltage[:,0],original/(.01+admittance),atol=GATE,rtol=0)
    np.testing.assert_allclose(result.response.current[:,0],original*.01/(.01+admittance),atol=GATE,rtol=0)
    np.testing.assert_allclose(result.frequency_solution.source_currents[:,0],
        [.001,.002,-.0006j,0,0],atol=GATE,rtol=0)
    for array in (result.source_currents,result.termination_currents,result.response.voltage,
                  result.response.current,result.frequency_solution.a):
        assert not array.flags.writeable
    check_power(result)


def test_reactive_shunt_current_uses_capacitor_time_derivative():
    net=resistor();omega=2*np.pi*net.frequency;conductance=.02;capacitance=5e-10
    source_peaks=np.array([.001,.002,-.0006j,0,0])[:,None]
    source=samples(source_peaks,9)[:,0]
    y=conductance+1j*omega*capacitance
    result=periodic_norton_response(net,source_currents={'p':source},termination_admittances={'p':y})
    voltage_peaks=source_peaks[:,0]/(.01+y)
    voltage=samples(voltage_peaks[:,None],9)
    derivative=samples((1j*omega*voltage_peaks)[:,None],9)
    np.testing.assert_allclose(result.response.voltage,voltage,atol=GATE,rtol=0)
    np.testing.assert_allclose(result.termination_currents,conductance*voltage+capacitance*derivative,atol=GATE,rtol=0)
    check_power(result)


def test_default_matched_shunt_and_constant_source():
    result=periodic_norton_response(resistor(),source_currents={'p':.003})
    np.testing.assert_allclose(result.response.voltage,.1,atol=GATE,rtol=0)
    np.testing.assert_allclose(result.termination_currents,.002,atol=GATE,rtol=0)
    np.testing.assert_allclose(result.frequency_solution.source_currents[:,0],[.003,0,0,0,0],atol=GATE,rtol=0)
    np.testing.assert_array_equal(result.frequency_solution.termination_admittances,.02)
    check_power(result)


def test_periodic_open_line_against_analytic_transmission_including_dc():
    f=np.arange(5)*1e8;net=rlgc_network(f,R=[[0.]],G=[[0.]],L=[[250e-9]],C=[[100e-12]],length=.1)
    t=np.arange(9)/9;drive=.0008+.0004*np.cos(2*np.pi*t)+.0001*np.sin(4*np.pi*t)
    result=periodic_norton_response(net,source_currents={'near:1':drive},
        termination_admittances={'near:1':.02,'far:1':0.})
    theta=2*np.pi*f*.1*5e-9;source=phasors(drive[:,None])[:,0]
    far=source/(.02*np.cos(theta)+1j*np.sin(theta)/50.)
    voltage=np.column_stack((np.cos(theta)*far,far))
    current=np.column_stack((1j*np.sin(theta)*far/50.,np.zeros(5)))
    np.testing.assert_allclose(result.response.voltage,samples(voltage,9),atol=GATE,rtol=0)
    np.testing.assert_allclose(result.response.current,samples(current,9),atol=GATE,rtol=0)
    np.testing.assert_array_equal(result.source_currents[:,1],0.)
    np.testing.assert_allclose(result.response.current[:,1],0.,atol=GATE,rtol=0)
    check_power(result)


@pytest.mark.parametrize('mixed',[False,True])
def test_actual_coupled_line_direct_harmonics_and_open_basis(mixed):
    net=rlgc_network(np.arange(5)*1e8,R=[[3.,.2],[.2,4.]],
        L=np.array([[300.,40.],[40.,260.]])*1e-9,G=[[.004,-.001],[-.001,.003]],
        C=np.array([[100.,-20.],[-20.,90.]])*1e-12,length=.07)
    if mixed:net=net.mixed_mode()
    rng=np.random.default_rng(67);source=.001*rng.normal(size=(9,4));source[:,-1]=0
    y=np.array([.02,.03,.01,.04])+2j*np.pi*net.frequency[:,None]*2e-12;y[:,-1]=0
    result=periodic_norton_response(net,source_currents=dict(zip(net.port_names,source.T)),
        termination_admittances=dict(zip(net.port_names,y.T)))
    direct=terminate_norton_network(net,source_currents=dict(zip(net.port_names,phasors(source).T)),
        termination_admittances=dict(zip(net.port_names,y.T)))
    for own,other in [('incident','a'),('reflected','b'),('voltage','voltage'),('current','current')]:
        np.testing.assert_allclose(getattr(result.response,own),samples(getattr(direct,other),9),atol=GATE,rtol=0)
    assert result.response.basis==net.basis
    np.testing.assert_array_equal(result.response.z_ref,net.z_ref)
    check_power(result)


@pytest.mark.parametrize('tool',['scipy','scikit-rf'])
def test_independent_pi_nodal_harmonics_and_direct_finite_synthesis(tool):
    ref=require_tool(tool);f=np.arange(5)*2e7;omega=2*np.pi*f
    bridge=1/(17+1j*omega*2e-9)
    y=np.zeros((5,2,2),complex)
    y[:,0,0]=1/83+1j*omega*1.2e-12+bridge
    y[:,1,1]=1/97+1j*omega*.8e-12+bridge;y[:,0,1]=y[:,1,0]=-bridge
    net=network_from_y(f,y,np.array([25.,90.]),('a','b'))
    rng=np.random.default_rng(119);drive=.001*rng.normal(size=(9,2));drive[:,1]=0
    loads=np.column_stack((.01+1j*omega*4e-12,np.zeros(5)))
    clock=Stopwatch()
    with clock('openphysics'):
        result=periodic_norton_response(net,source_currents=dict(zip(net.port_names,drive.T)),
            termination_admittances=dict(zip(net.port_names,loads.T)))
    with clock('reference'):
        if tool=='scipy':
            from scipy.linalg import solve
            yn=y
        else:
            solve=np.linalg.solve;yn=ref.network.s2y(net.s,z0=net.z_ref,s_def='power')
        currents=phasors(drive)
        voltage=np.array([solve(matrix+np.diag(load),source) for matrix,load,source in zip(yn,loads,currents)])
        current=np.einsum('fij,fj->fi',yn,voltage)
        v,i=samples(voltage,9),samples(current,9)
    errors=[float(np.max(abs(result.response.voltage-v))),float(np.max(abs(result.response.current-i)))]
    record=make_record(case='periodic-norton-pi-'+tool,physics='periodic Norton-driven RLC two-port with open terminal',
        api='sipi.periodic_norton_response',discretization='peak harmonic current feedback and inverse FFT',
        tool=tool,tool_discretization='explicit finite DFT/synthesis and '+('analytic RLC nodal solve' if tool=='scipy' else 's2y nodal solve'),
        matched=['same uniform real-DC network and odd real source samples',
                 'same complex parallel admittances, open terminal and unequal real references'],
        not_matched=['no new field extraction or measured accuracy','no causal startup or isolated pulse response'],
        observables=[observable(name,unit,'max absolute difference',value,GATE)
                     for name,unit,value in zip(('voltage','current'),('V','A'),errors)],
        analytical_acceptance='RC division, capacitive shunt derivative, open lossless line and time/harmonic average powers',stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    assert max(errors)<=GATE
    check_power(result)


def test_zero_drive_superposition_and_circular_shift():
    net=resistor();rng=np.random.default_rng(31);a,b=.001*rng.normal(size=(2,9))
    def solve(value):return periodic_norton_response(net,source_currents={'p':value},termination_admittances={'p':0.})
    ra,rb=solve(a),solve(b)
    np.testing.assert_allclose(solve(2*a-.3*b).response.voltage,2*ra.response.voltage-.3*rb.response.voltage,atol=GATE,rtol=0)
    np.testing.assert_allclose(solve(np.roll(a,2)).response.current,np.roll(ra.response.current,2,axis=0),atol=GATE,rtol=0)
    np.testing.assert_array_equal(solve(0.).response.voltage,0.)
    check_power(ra)


@pytest.mark.parametrize('sources',[{},[],{'bad':0.},{'p':True},{'p':1j},{'p':[0j]*9},
    {'p':[1,2]},{'p':[[0]*9]},{'p':float('nan')}])
def test_invalid_source_current_samples(sources):
    with pytest.raises(ValueError):periodic_norton_response(resistor(),source_currents=sources)


@pytest.mark.parametrize('loads',[[],{'bad':0.},{'p':True},{'p':-.01},{'p':'open'},
    {'p':float('inf')},{'p':[0,0]},{'p':.01+1e-20j}])
def test_invalid_shunts_or_nonreal_dc(loads):
    with pytest.raises(ValueError):periodic_norton_response(resistor(),source_currents={'p':0.},termination_admittances=loads)


@pytest.mark.parametrize('frequencies',[[0.],[1.,2.],[0.,1.,3.]])
def test_grid_must_be_uniform_and_include_dc(frequencies):
    net=LineNetwork(frequencies,np.zeros((len(frequencies),1,1)),50.,('p',))
    with pytest.raises(ValueError):periodic_norton_response(net,source_currents={'p':0.})


def test_complex_dc_network_floating_open_and_transform_overflow():
    net=LineNetwork([0.,1.],np.array([[[1e-20j]],[[0.]]]),50.,('p',))
    with pytest.raises(ValueError,match='DC S'):periodic_norton_response(net,source_currents={'p':0.})
    floating=LineNetwork([0.,1.],np.ones((2,1,1)),50.,('p',))
    with pytest.raises(ValueError,match='condition|singular'):
        periodic_norton_response(floating,source_currents={'p':0.},termination_admittances={'p':0.})
    with pytest.raises(ValueError):periodic_norton_response(resistor(),source_currents={'p':1e308})
