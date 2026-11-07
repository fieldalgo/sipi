# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Periodic mixed boundaries: finite synthesis, ideal terminals and time power."""
from importlib import metadata

import numpy as np
import pytest

from sipi import (LineNetwork, rlgc_network, periodic_mixed_response,
    periodic_terminated_response, periodic_norton_response, terminate_mixed_network)
from test_mixed_termination import thevenin, norton, coupled
from test_periodic_termination import phasors, samples
from test_norton_termination import network_from_y
from crosscheck import Stopwatch, emit, make_record, observable, require_tool

GATE=1e-12


def check_power(result):
    r=result.response;h=result.frequency_solution
    is_v=np.array([kind=='thevenin' for kind in h.kinds])
    np.testing.assert_allclose(result.source_voltages[:,is_v],
        r.voltage[:,is_v]+result.termination_voltages[:,is_v],atol=GATE,rtol=0)
    np.testing.assert_allclose(result.source_currents[:,~is_v],
        r.current[:,~is_v]+result.termination_currents[:,~is_v],atol=GATE,rtol=0)
    np.testing.assert_array_equal(result.source_voltages[:,~is_v],0.)
    np.testing.assert_array_equal(result.source_currents[:,is_v],0.)
    np.testing.assert_array_equal(result.termination_voltages[:,~is_v],0.)
    np.testing.assert_array_equal(result.termination_currents[:,is_v],0.)
    net=np.mean(np.sum(r.voltage*r.current,axis=1))
    load=np.mean(np.sum(result.termination_voltages*r.current+r.voltage*result.termination_currents,axis=1))
    source=np.mean(np.sum(result.source_voltages*r.current+r.voltage*result.source_currents,axis=1))
    np.testing.assert_allclose([net,load,source],
        [h.network_power.sum(),h.termination_power.sum(),h.source_power.sum()],atol=GATE,rtol=0)
    assert abs(source-net-load)<=GATE
    np.testing.assert_allclose(r.voltage*r.current,r.incident**2-r.reflected**2,atol=GATE,rtol=0)


def test_ideal_voltage_open_line_direct_analytic_harmonics_and_snapshot():
    f=np.arange(5)*1e8
    net=rlgc_network(f,R=[[0]],G=[[0]],L=[[250e-9]],C=[[100e-12]],length=.1)
    t=np.arange(9)/9;drive=.3+.2*np.cos(2*np.pi*t)+.1*np.sin(4*np.pi*t);original=drive.copy()
    result=periodic_mixed_response(net,{'near:1':thevenin(drive,0),'far:1':norton(0,0)})
    source=phasors(original[:,None])[:,0];theta=2*np.pi*f*.1*5e-9
    v=np.column_stack((source,source/np.cos(theta)))
    i=np.column_stack((1j*np.tan(theta)*source/50,np.zeros(5)))
    np.testing.assert_allclose(result.response.voltage,samples(v,9),atol=GATE,rtol=0)
    np.testing.assert_allclose(result.response.current,samples(i,9),atol=GATE,rtol=0)
    drive[:]=0
    np.testing.assert_array_equal(result.source_voltages[:,0],original)
    for array in (result.source_voltages,result.source_currents,result.termination_voltages,
                  result.termination_currents,result.response.voltage,result.frequency_solution.boundary_residual):
        assert not array.flags.writeable
    check_power(result)


@pytest.mark.parametrize('mixed',[False,True])
@pytest.mark.parametrize('kind',['thevenin','norton'])
def test_single_kind_equivalence_to_existing_periodic_apis(mixed,kind):
    net=coupled(mixed);p=net.port_names;rng=np.random.default_rng(32)
    drive=.01*rng.normal(size=(5,4));loads=np.ones((3,4))*(30 if kind=='thevenin' else .02)
    loads=loads+1j*np.arange(3)[:,None]*(2 if kind=='thevenin' else .002)
    boundary={name:(thevenin if kind=='thevenin' else norton)(s,z)
        for name,s,z in zip(p,drive.T,loads.T)}
    result=periodic_mixed_response(net,boundary)
    expected=(periodic_terminated_response(net,source_voltages=dict(zip(p,drive.T)),terminations=dict(zip(p,loads.T)))
        if kind=='thevenin' else periodic_norton_response(net,source_currents=dict(zip(p,drive.T)),termination_admittances=dict(zip(p,loads.T))))
    for key in ('voltage','current','incident','reflected'):
        np.testing.assert_allclose(getattr(result.response,key),getattr(expected.response,key),atol=GATE,rtol=0)
    for key in ('network_power','termination_power','source_power'):
        np.testing.assert_allclose(getattr(result.frequency_solution,key),getattr(expected.frequency_solution,key),atol=GATE,rtol=0)
    assert result.response.basis==net.basis
    check_power(result)


@pytest.mark.parametrize('kind',['thevenin','norton'])
def test_reactive_loads_follow_time_derivatives(kind):
    f=np.arange(5)*1e7;omega=2*np.pi*f
    net=LineNetwork(f,np.full((5,1,1),1/3),50.,('p',))
    peak=np.array([.001,.002,-.0006j,0,0]);drive=samples(peak[:,None],9)[:,0]
    if kind=='thevenin':
        resistance=20.;inductance=2e-7;load=resistance+1j*omega*inductance
        result=periodic_mixed_response(net,{'p':thevenin(drive,load)})
        current=peak/(100+load)
        expected=resistance*samples(current[:,None],9)+inductance*samples((1j*omega*current)[:,None],9)
        np.testing.assert_allclose(result.termination_voltages,expected,atol=GATE,rtol=0)
    else:
        conductance=.02;capacitance=5e-10;load=conductance+1j*omega*capacitance
        result=periodic_mixed_response(net,{'p':norton(drive,load)})
        voltage=peak/(.01+load)
        expected=conductance*samples(voltage[:,None],9)+capacitance*samples((1j*omega*voltage)[:,None],9)
        np.testing.assert_allclose(result.termination_currents,expected,atol=GATE,rtol=0)
    check_power(result)


@pytest.mark.parametrize('tool',['scipy','scikit-rf'])
def test_independent_pi_nodal_direct_dft_and_time_synthesis(tool):
    ref=require_tool(tool);f=np.arange(5)*2e7;omega=2*np.pi*f
    bridge=1/(17+1j*omega*2e-9);y=np.zeros((5,2,2),complex)
    y[:,0,0]=1/83+1j*omega*1.2e-12+bridge
    y[:,1,1]=1/97+1j*omega*.8e-12+bridge;y[:,0,1]=y[:,1,0]=-bridge
    net=network_from_y(f,y,np.array([25.,90.]),('a','b'))
    t=np.arange(9)/9;voltage=.3+.2*np.cos(2*np.pi*t);current=.001*np.sin(4*np.pi*t)
    load=.01+1j*omega*4e-12;clock=Stopwatch()
    with clock('openphysics'):
        result=periodic_mixed_response(net,{'a':thevenin(voltage,0),'b':norton(current,load)})
    with clock('reference'):
        if tool=='scipy':
            from scipy.linalg import solve
            yn=y
        else:
            solve=np.linalg.solve;yn=ref.network.s2y(net.s,z0=net.z_ref,s_def='power')
        v=np.empty((5,2),complex);v[:,0]=phasors(voltage[:,None])[:,0]
        inj=phasors(current[:,None])[:,0]
        for k in range(5):v[k,1]=solve([[yn[k,1,1]+load[k]]],[inj[k]-yn[k,1,0]*v[k,0]])[0]
        i=np.einsum('fij,fj->fi',yn,v)
        tv,ti=samples(v,9),samples(i,9)
    errors=[float(np.max(abs(result.response.voltage-tv))),float(np.max(abs(result.response.current-ti)))]
    rec=make_record(case='periodic-mixed-pi-'+tool,physics='periodic fixed-voltage/free-current RLC two-port',
        api='sipi.periodic_mixed_response',discretization='mixed harmonic wave feedback and inverse FFT',
        tool=tool,tool_discretization='explicit finite DFT/synthesis and '+('analytic RLC nodal solve' if tool=='scipy' else 's2y nodal solve'),
        matched=['same uniform real-DC network and odd real source samples','same ideal voltage and complex Norton shunt with unequal references'],
        not_matched=['no new field extraction or measured accuracy','no causal startup or isolated pulse response'],
        observables=[observable(name,unit,'max absolute difference',value,GATE)
            for name,unit,value in zip(('voltage','current'),('V','A'),errors)],
        analytical_acceptance='ideal-voltage/open line, reactive load derivatives, time KCL/KVL and harmonic average powers',stopwatch=clock)
    rec['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(rec)
    assert max(errors)<=GATE
    check_power(result)


@pytest.mark.parametrize('mixed',[False,True])
def test_actual_coupled_mixed_boundaries_direct_synthesis_shift_superposition(mixed):
    net=coupled(mixed);p=net.port_names;rng=np.random.default_rng(77)
    a,b=.01*rng.normal(size=(2,5));load=.02+1j*np.arange(3)*.002
    def solve(drive):
        return periodic_mixed_response(net,{p[0]:thevenin(drive,0),p[1]:norton(0,0),
            p[2]:thevenin(0,30),p[3]:norton(0,load)})
    result=solve(a)
    frequency=terminate_mixed_network(net,{p[0]:thevenin(phasors(a[:,None])[:,0],0),
        p[1]:norton(0,0),p[2]:thevenin(0,30),p[3]:norton(0,load)})
    np.testing.assert_allclose(result.response.voltage,samples(frequency.voltage,5),atol=GATE,rtol=0)
    np.testing.assert_allclose(solve(a+2*b).response.voltage,result.response.voltage+2*solve(b).response.voltage,atol=GATE,rtol=0)
    np.testing.assert_allclose(solve(np.roll(a,2)).response.current,np.roll(result.response.current,2,axis=0),atol=GATE,rtol=0)
    np.testing.assert_array_equal(solve(0.).response.voltage,0.)
    check_power(result)


@pytest.mark.parametrize('boundary',[
    {},[],{'bad':thevenin()}, {'p':'short'}, {'p':dict(kind='wrong')},
    {'p':dict(kind='thevenin',impedance=0)},
    {'p':dict(kind='norton',source_current=0,admittance=0,extra=1)},
    {'p':thevenin(True)}, {'p':norton(1j)}, {'p':thevenin([0j]*5)},
    {'p':thevenin([0,1])}, {'p':norton([[0]*5])}, {'p':thevenin(float('nan'))},
    {'p':thevenin(0,True)}, {'p':norton(0,-1)}, {'p':thevenin(0,float('inf'))},
    {'p':norton(0,.02+1e-20j)}, {'p':thevenin(0,50+1e-20j)},
    {'p':norton(0,[.02,.02])}])
def test_strict_real_time_sources_and_loads(boundary):
    net=LineNetwork([0,1,2],np.zeros((3,1,1)),50.,('p',))
    with pytest.raises(ValueError):periodic_mixed_response(net,boundary)


@pytest.mark.parametrize('grid',[[0],[1,2],[0,1,3]])
def test_periodic_grid_required(grid):
    net=LineNetwork(grid,np.zeros((len(grid),1,1)),50.,('p',))
    with pytest.raises(ValueError):periodic_mixed_response(net,{'p':thevenin(0,50)})


def test_nonreal_dc_floating_and_transform_overflow():
    net=LineNetwork([0,1],np.array([[[1e-20j]],[[0.]]]),50.,('p',))
    with pytest.raises(ValueError,match='DC S'):periodic_mixed_response(net,{'p':thevenin(0,50)})
    floating=LineNetwork([0,1],np.ones((2,1,1)),50.,('p',))
    with pytest.raises(ValueError,match='condition|singular'):periodic_mixed_response(floating,{'p':norton(0,0)})
    matched=LineNetwork([0,1],np.zeros((2,1,1)),50.,('p',))
    with pytest.raises(ValueError):periodic_mixed_response(matched,{'p':thevenin(1e308,0)})
