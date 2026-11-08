# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Physical Z/Y wave equations, independent RF conversion and strict gates."""
import numpy as np
import pytest
from crosscheck import Stopwatch,emit,make_record,observable,require_tool
from sipi import impedance_network,admittance_network
from sipi.termination import terminate_network
import sipi.parameter_network as module

APIS={'z':impedance_network,'y':admittance_network}


def samples(n,kind,parameter):
    refs=np.arange(n)*13.+31.;r=np.sqrt(refs);i=np.arange(1,n+1,dtype=float)
    grid=np.outer(i,i)/(n*n)
    if kind=='nonreciprocal':
        a=np.diag(1.2+.1*i)+.09*grid+.03j*(grid+np.arange(n)[:,None])
        a+=.07*(np.arange(n)[:,None]-np.arange(n)[None,:])
    elif kind=='reciprocal':a=np.diag(1.+.2*i)+(.08+.05j)*grid
    elif kind=='diagonal':a=np.diag(.4+.2*i+.1j*i)
    else:a=(.2+.07j)*grid  # Rank one; no inverse of these physical matrices exists.
    values=a*r[:,None]*r[None,:] if parameter=='z' else a/r[:,None]/r[None,:]
    return np.array([0.,1e6,1e9]),np.stack([values,values*(1+.2j),values*(.7-.1j)]),refs


@pytest.mark.parametrize('parameter',['z','y'])
@pytest.mark.parametrize('n',[1,2,3,4])
@pytest.mark.parametrize('kind',['nonreciprocal','reciprocal','diagonal','rank-one'])
def test_independent_rf_conversion_and_physical_wave_equations(parameter,n,kind):
    rf=require_tool('scikit-rf');f,values,refs=samples(n,kind,parameter);clock=Stopwatch()
    with clock('openphysics'):network=APIS[parameter](f,values,z_ref=refs)
    with clock('reference'):expected=getattr(rf.network,parameter+'2s')(values,z0=refs,s_def='power')
    error=float(np.max(abs(network.s-expected)));assert error<=1e-12
    eye=np.eye(n);root=np.sqrt(refs)
    voltage=root[None,:,None]*(eye+network.s)
    current=(eye-network.s)/root[None,:,None]
    lhs,rhs=(voltage,values@current) if parameter=='z' else (current,values@voltage)
    physical=float(np.max(abs(lhs-rhs))/max(np.max(abs(lhs)),np.max(abs(rhs))))
    assert physical<=1e-10
    emit(make_record(case=f'physical-{parameter}-waves-{n}-{kind}',physics='explicit finite port matrices to power waves',
        api=APIS[parameter].__name__,discretization='three explicit frequency matrices; scaled right solve',
        tool='scikit-rf',tool_discretization=f'network.{parameter}2s power-wave conversion',
        matched=['physical matrices','frequency','port order','positive real references','power-wave convention'],
        not_matched=['implementation and conditioning guards'],
        observables=[observable('S','1','max_absolute',error,1e-12),observable('VI equation','1','relative',physical,1e-10)],
        analytical_acceptance='Scalar R/L/C, exact open/short and independent loaded KCL are separate gates; no mesh or physical extraction.',stopwatch=clock))


@pytest.mark.parametrize('parameter',['z','y'])
def test_one_port_resistor_inductor_capacitor_and_active_input(parameter):
    f=np.array([0.,1e6,1e8]);w=2*np.pi*f;ref=73.
    matrices=[np.full(3,120.+0j),1j*w*7e-9,np.full(3,-20.+0j)] if parameter=='z' else [np.full(3,1/120+0j),1j*w*9e-12,np.full(3,-1/200+0j)]
    for value in matrices:
        network=APIS[parameter](f,value[:,None,None],z_ref=ref)
        expected=(value-ref)/(value+ref) if parameter=='z' else (1-ref*value)/(1+ref*value)
        np.testing.assert_allclose(network.s[:,0,0],expected,atol=1e-12,rtol=0)
    assert abs(network.s[0,0,0])>1  # Conversion does not fabricate passivity.


@pytest.mark.parametrize('n',[1,2,3,4])
@pytest.mark.parametrize('parameter',['z','y'])
def test_exact_short_or_open_does_not_invert_physical_matrix(n,parameter):
    r=APIS[parameter]([0.,1e9],np.zeros((2,n,n)),z_ref=np.arange(n)+35.)
    expected=(-1 if parameter=='z' else 1)*np.eye(n)
    np.testing.assert_array_equal(r.s,np.broadcast_to(expected,r.s.shape))


def test_rank_one_series_resistor_has_exact_two_port_analytic_limit():
    resistance=37.;reference=50.;y=np.array([[1.,-1.],[-1.,1.]])/resistance
    net=admittance_network([0.],y[None],z_ref=reference)
    expected=np.array([[resistance,2*reference],[2*reference,resistance]])/(resistance+2*reference)
    np.testing.assert_allclose(net.s[0],expected,atol=1e-12,rtol=0)
    np.testing.assert_allclose(net.s[0].T,net.s[0],atol=1e-14,rtol=0)


@pytest.mark.parametrize('n',[1,2,3,4])
def test_loaded_admittance_matches_independent_kcl(n):
    f=np.array([0.,2e8]);index=np.arange(1,n+1,dtype=float);g=.003*np.eye(n)+.0001*np.outer(index,index)
    c=(5*np.eye(n)+.3*np.outer(index,index))*1e-12
    y=g+2j*np.pi*f[:,None,None]*c
    names=tuple(f'p{i}' for i in range(n));refs=31.+13*np.arange(n)
    network=admittance_network(f,y,z_ref=refs,names=names)
    source=(1+.2j)*index;resistance=23.+11*np.arange(n)
    driven=terminate_network(network,source_voltages=dict(zip(names,source)),terminations=dict(zip(names,resistance)))
    expected=np.linalg.solve(y+np.diag(1/resistance),np.broadcast_to(source/resistance,(2,n))[...,None])[...,0]
    np.testing.assert_allclose(driven.voltage,expected,atol=1e-12,rtol=1e-12)
    np.testing.assert_allclose(driven.current,(y@expected[...,None])[...,0],atol=1e-12,rtol=1e-12)
    assert np.max(np.linalg.svd(network.s,compute_uv=False))<=1+1e-12


@pytest.mark.parametrize('parameter',['z','y'])
def test_port_permutation_reference_change_and_consistent_unit_scaling(parameter):
    f,values,refs=samples(4,'nonreciprocal',parameter);api=APIS[parameter];r=api(f,values,z_ref=refs)
    order=[2,0,3,1];permuted=api(f,values[:,order][:,:,order],z_ref=refs[order])
    np.testing.assert_allclose(permuted.s,r.s[:,order][:,:,order],atol=1e-12,rtol=0)
    newrefs=refs[::-1]*1.5
    np.testing.assert_allclose(api(f,values,z_ref=newrefs).s,r.renormalized(newrefs).s,atol=1e-12,rtol=0)
    factor=1e7;scaled=values*factor if parameter=='z' else values/factor
    np.testing.assert_allclose(api(f,scaled,z_ref=refs*factor).s,r.s,atol=1e-12,rtol=0)


@pytest.mark.parametrize('parameter',['z','y'])
def test_detached_readonly_arrays_and_explicit_labels(parameter):
    f,values,refs=samples(2,'reciprocal',parameter);names=['a','b'];r=APIS[parameter](f,values,z_ref=refs,names=names)
    before=r.s.copy();f[:]=9;values[:]=9;refs[:]=9;names[0]='other'
    assert r.port_names==('a','b') and r.basis=='single-ended'
    assert r.frequency[0]==0 and r.z_ref[0]==31
    np.testing.assert_array_equal(r.s,before)
    for a in [r.frequency,r.z_ref,r.s]:
        assert not a.flags.writeable
        with pytest.raises(ValueError):a.flat[0]=0


@pytest.mark.parametrize('parameter',['z','y'])
@pytest.mark.parametrize('value',[True,[[[True,1],[1,2]]],[[['1']]],[[[float('nan')]]],[[[complex(0,float('inf'))]]],None,{},[],[1],[[1]],np.zeros((1,0,0)),np.zeros((1,2,3)),np.zeros((2,1,1))])
def test_bad_parameters_rejected(parameter,value):
    with pytest.raises((ValueError,TypeError)):APIS[parameter]([0.],value,z_ref=50.)


@pytest.mark.parametrize('parameter',['z','y'])
@pytest.mark.parametrize('frequency',[[],[True],[float('nan')],[-1.],[1.,1.],[2.,1.],[[0.]]])
def test_bad_frequency_rejected(parameter,frequency):
    with pytest.raises((ValueError,TypeError)):APIS[parameter](frequency,np.ones((1,1,1)),z_ref=50.)


@pytest.mark.parametrize('parameter',['z','y'])
@pytest.mark.parametrize('reference',[0.,-1.,True,complex(50),float('inf'),[50,True],[[50,50]],[50],[50,50,50]])
def test_bad_references_rejected(parameter,reference):
    with pytest.raises((ValueError,TypeError)):APIS[parameter]([0.],np.eye(2)[None],z_ref=reference)


@pytest.mark.parametrize('parameter',['z','y'])
@pytest.mark.parametrize('names',['ab',[],['a'],['a','a'],['a',''],['a','b\nc'],['a',2]])
def test_bad_labels_rejected(parameter,names):
    with pytest.raises((ValueError,TypeError)):APIS[parameter]([0.],np.eye(2)[None],z_ref=50,names=names)


@pytest.mark.parametrize('parameter',['z','y'])
@pytest.mark.parametrize('case',['singular','scalar-cancellation','matrix-conditioning','nonfinite-normalization'])
def test_singular_and_unrepresentable_cases_reject_without_repair(parameter,case):
    a=np.array([[[-1.+0j]]]);ref=1.
    if case=='scalar-cancellation':a[0,0,0]+=5e-14
    elif case=='matrix-conditioning':a=np.diag([1.,1e14])[None]
    elif case=='nonfinite-normalization':a=np.array([[[1e308+0j]]]);ref=1e300 if parameter=='y' else 1e-300
    with pytest.raises(ValueError):APIS[parameter]([0.],a,z_ref=ref)


@pytest.mark.parametrize('parameter',['z','y'])
def test_large_finite_normalized_matrix_is_scaled_before_addition(parameter):
    values=np.array([[[1.4e308+1.4e308j]]])
    r=APIS[parameter]([0.],values,z_ref=1.)
    np.testing.assert_allclose(r.s,[[[(1 if parameter=='z' else -1)+0j]]],atol=1e-14,rtol=0)


@pytest.mark.parametrize('parameter',['z','y'])
@pytest.mark.parametrize('failure',['residual','nonfinite','singular'])
def test_solve_failures_or_corruption_reject(parameter,failure,monkeypatch):
    def broken(a,b):
        if failure=='singular':raise np.linalg.LinAlgError('deliberate')
        return np.full_like(b,np.nan if failure=='nonfinite' else 7.)
    monkeypatch.setattr(module.np.linalg,'solve',broken)
    with pytest.raises(ValueError):APIS[parameter]([0.],np.array([[[2.]]]),z_ref=1.)
