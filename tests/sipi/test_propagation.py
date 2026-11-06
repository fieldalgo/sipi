# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Analytical propagation limits, power balance and independent circuit tool."""
import importlib.metadata as metadata
import numpy as np
import pytest
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import rlgc_propagation, rlgc_network

F = np.array([1e3,1e6,1e9])


def scalar(r=2,l=400e-9,g=.002,c=100e-12):
    return rlgc_propagation(F,R=[[r]],L=[[l]],G=[[g]],C=[[c]])


def test_lossless_line_analytic_phase_and_impedance():
    p = scalar(0,g=0)
    np.testing.assert_allclose(p.z_characteristic[:,0],np.sqrt(400e-9/100e-12),rtol=1e-12)
    np.testing.assert_allclose(p.beta[:,0],2*np.pi*F*np.sqrt(400e-9*100e-12),rtol=1e-12)
    np.testing.assert_allclose(p.phase_velocity,1/np.sqrt(400e-9*100e-12),rtol=1e-12)
    np.testing.assert_array_equal(p.alpha,0)
    np.testing.assert_array_equal(p.alpha_conductor,0)
    np.testing.assert_array_equal(p.alpha_dielectric,0)


def test_distortionless_exact_loss_partition_and_db():
    # R/L=G/C=k: Zc=sqrt(L/C), gamma=(k+jw)*sqrt(LC).
    l,c,k=400e-9,100e-12,3e8
    p = scalar(k*l,l,k*c,c)
    expected = (k+2j*np.pi*F)*np.sqrt(l*c)
    np.testing.assert_allclose(p.gamma[:,0],expected,rtol=1e-12)
    np.testing.assert_allclose(p.z_characteristic,np.sqrt(l/c),rtol=1e-12)
    np.testing.assert_allclose(p.alpha_conductor,p.alpha/2,rtol=1e-12)
    np.testing.assert_allclose(p.alpha_dielectric,p.alpha/2,rtol=1e-12)
    np.testing.assert_allclose(p.attenuation_db_per_m,20/np.log(10)*p.alpha,rtol=1e-12)
    np.testing.assert_allclose(p.conductor_db_per_m+p.dielectric_db_per_m,
                               p.attenuation_db_per_m,rtol=1e-12)
    # Matching Zref=Zc removes reflections, making finite S21 attenuation equal.
    net = rlgc_network(F,R=[[k*l]],L=[[l]],G=[[k*c]],C=[[c]],length=.2,z_ref=np.sqrt(l/c))
    np.testing.assert_allclose(-20*np.log10(abs(net.s[:,1,0])),
                               .2*p.attenuation_db_per_m[:,0],rtol=1e-10,atol=1e-12)


@pytest.mark.parametrize('r,g',[(0,.1),(100,0),(2,.002),(1e4,1e-6),(1e-3,10)])
def test_exact_power_balance_including_high_loss(r,g):
    p = scalar(r,g=g)
    np.testing.assert_allclose(p.alpha_conductor+p.alpha_dielectric,p.alpha,rtol=1e-10,atol=0)
    if r==0: np.testing.assert_array_equal(p.alpha_conductor,0)
    if g==0: np.testing.assert_array_equal(p.alpha_dielectric,0)


def test_symmetric_pair_normalizations_and_no_mode_tracking():
    l,c = np.array([[400,80],[80,400]])*1e-9,np.array([[100,-20],[-20,100]])*1e-12
    p = rlgc_propagation(F,R=np.zeros((2,2)),L=l,G=np.zeros((2,2)),C=c)
    assert p.modes == ('differential','common')
    expected = [2*np.sqrt(320e-9/120e-12),.5*np.sqrt(480e-9/80e-12)]
    np.testing.assert_allclose(p.z_characteristic,np.tile(expected,(3,1)),rtol=1e-12)
    np.testing.assert_allclose(p.gamma[:,0],p.gamma[:,1],rtol=1e-12)


def test_immutable_snapshot_and_shapes():
    f=F.copy()
    p=rlgc_propagation(f,R=[[2]],L=[[400e-9]],G=[[.002]],C=[[100e-12]])
    f[:] = 10
    np.testing.assert_array_equal(p.frequency,F)
    for name in ('gamma','z_characteristic','alpha','beta','alpha_conductor','alpha_dielectric',
                 'attenuation_db_per_m','conductor_db_per_m','dielectric_db_per_m','phase_velocity'):
        value = getattr(p,name)
        assert value.shape==(3,1) and not value.flags.writeable


@pytest.mark.parametrize('n',[1,2])
def test_independent_distributed_circuit(n):
    skrf=require_tool('scikit-rf')
    matrices = dict(R=np.array([[6,.4],[.4,6]]),L=np.array([[400,80],[80,400]])*1e-9,
                    G=np.array([[.004,-.001],[-.001,.004]]),C=np.array([[100,-20],[-20,100]])*1e-12)
    if n==1: matrices={k:v[:1,:1] for k,v in matrices.items()}
    clock=Stopwatch()
    with clock('openphysics'):
        p=rlgc_propagation(F,**matrices)
    gamma,zchar=[],[]
    with clock('reference'):
        for mode in range(n):
            if n==1: values={k:v[0,0] for k,v in matrices.items()}
            else:
                sign=-1 if mode==0 else 1
                values={k:(v[0,0]+sign*v[0,1])*(
                    (2 if mode==0 else .5) if k in ('R','L') else (.5 if mode==0 else 2))
                    for k,v in matrices.items()}
            media=skrf.media.DistributedCircuit(skrf.Frequency.from_f(F,unit='Hz'),**values)
            gamma.append(media.gamma)
            zchar.append(media.z0)
    errors=[float(np.max(abs((p.gamma-np.array(gamma).T)/np.array(gamma).T))),
            float(np.max(abs((p.z_characteristic-np.array(zchar).T)/np.array(zchar).T)))]
    record=make_record(case=f'propagation-{n}-conductor',physics='uniform-line traveling waves',
        api='sipi.rlgc_propagation',discretization='scalar modal RLGC and exact power balance',
        tool='scikit-rf',tool_discretization='DistributedCircuit gamma and z0',
        matched=['same frequency samples and modal RLGC with differential/common voltage-current normalization'],
        not_matched=[],observables=[observable(name,unit,'max relative difference',e,1e-10)
            for name,unit,e in zip(('gamma','Zc'),('1/m','ohm'),errors)],
        analytical_acceptance='lossless and distortionless exact limits; power-loss contributions sum to real gamma',
        stopwatch=clock)
    record['openphysics']['distribution']='sipi'
    record['openphysics']['version']=metadata.version('sipi')
    emit(record)
    assert max(errors)<=1e-10


@pytest.mark.parametrize('name',['R','L','G','C'])
def test_asymmetric_pair_is_not_silently_projected(name):
    values=dict(R=np.eye(2),L=np.eye(2)*400e-9,G=np.eye(2)*.002,C=np.eye(2)*100e-12)
    values[name][0,0]*=1.01
    with pytest.raises(ValueError,match='exchange-symmetric'):
        rlgc_propagation(F,**values)


@pytest.mark.parametrize('frequency',[[0,1e9],[-1],[],[True],[np.inf]])
def test_invalid_frequencies(frequency):
    with pytest.raises(ValueError):
        rlgc_propagation(frequency,R=[[2]],L=[[400e-9]],G=[[.002]],C=[[100e-12]])


def test_other_modes_and_nonpassive_input_are_rejected():
    with pytest.raises(ValueError,match='one conductor'):
        rlgc_propagation(F,R=np.eye(3),L=np.eye(3),G=np.eye(3),C=np.eye(3))
    with pytest.raises(ValueError,match='positive semidefinite'):
        scalar(-1)
    with pytest.raises(ValueError,match='finite'):
        scalar(np.inf)
