# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Full forward-wave matrices: independent modal media and telegrapher power."""
import importlib.metadata as metadata

import numpy as np
import pytest
from scipy.linalg import expm
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import (LineCharacteristic, rlgc_characteristic, rlgc_propagation,
                  CrossSection, CrossSectionDocument, coupled_microstrip)
from sipi.dielectric import PrincipalAxisDielectric, DebyeDielectric, ConstantDielectric
from sipi.line_model import TransmissionLineDocument
from sipi.volume_line import VolumeLineDocument

F=np.array([1e3,1e6,1e9])
T=np.array([[1,.3,-.1],[.2,.9,.15],[0,-.2,1.1]])
D=dict(R=np.array([2.,3.,4.]),L=np.array([200,300,400])*1e-9,
       G=np.array([.001,.002,.003]),C=np.array([100,150,80])*1e-12)


def transformed(diagonal=D,t=T):
    ti=np.linalg.inv(t)
    return {name:(t@np.diag(value)@t.T if name in ('R','L') else ti.T@np.diag(value)@ti)
            for name,value in diagonal.items()}


def relative(actual,expected):
    return float(abs(actual-expected).max()/abs(expected).max())


@pytest.mark.parametrize('lossless',[False,True])
def test_asymmetric_three_conductor_matrices_against_independent_modal_circuits(lossless):
    tool=require_tool('scikit-rf'); clock=Stopwatch()
    diagonal=dict(D,R=np.zeros(3),G=np.zeros(3)) if lossless else D
    matrices=transformed(diagonal)
    with clock('openphysics'): result=rlgc_characteristic(F,**matrices,names=('one','two','three'))
    expected_gamma=[];expected_zc=[];expected_transfer=[];ti=np.linalg.inv(T)
    with clock('reference'):
        media=[tool.media.DistributedCircuit(tool.Frequency.from_f(F,unit='Hz'),
                    **{name:value[i] for name,value in diagonal.items()}) for i in range(3)]
        for k in range(len(F)):
            gamma=np.array([m.gamma[k] for m in media]);zc=np.array([m.z0[k] for m in media])
            expected_gamma.append(T@np.diag(gamma)@ti)
            expected_zc.append(T@np.diag(zc)@T.T)
            expected_transfer.append(T@np.diag(np.exp(-gamma*.02))@ti)
    errors=[relative(result.gamma_voltage,np.array(expected_gamma)),
            relative(result.z_characteristic,np.array(expected_zc)),
            relative(result.voltage_transfer(.02),np.array(expected_transfer))]
    record=make_record(case='characteristic-three-lines-'+('lossless' if lossless else 'lossy'),
        physics='asymmetric reciprocal uniform-line forward waves',api='sipi.rlgc_characteristic',
        discretization='scaled physical-branch Schur matrix square root',tool='scikit-rf',
        tool_discretization='DistributedCircuit scalar modes transformed by known nonorthogonal coordinates',
        matched=['same real power-dual coordinate transform, modal RLGC, frequencies and length'],
        not_matched=['no inferred mode ordering, physical geometry or full-wave validation'],
        observables=[observable(name,unit,'max normwise relative difference',error,1e-10)
            for name,unit,error in zip(('Gamma voltage','Z characteristic','forward voltage transfer'),('1/m','ohm','1'),errors)],
        analytical_acceptance='lossless/degenerate exact limits; general telegrapher subspace and power identity',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    assert max(errors)<1e-10
    if lossless: np.testing.assert_array_equal(result.gamma_voltage.real,0)


@pytest.mark.parametrize('resistance,conductance',[(0,0),(2,.002),(1e4,1e-6),(1e-3,10)])
def test_single_line_reduces_to_existing_exact_scalar_propagation(resistance,conductance):
    values=dict(R=[[resistance]],L=[[400e-9]],G=[[conductance]],C=[[100e-12]])
    old=rlgc_propagation(F,**values);new=rlgc_characteristic(F,**values)
    np.testing.assert_allclose(new.gamma_voltage[:,0,0],old.gamma[:,0],rtol=1e-12,atol=0)
    np.testing.assert_allclose(new.z_characteristic[:,0,0],old.z_characteristic[:,0],rtol=1e-12,atol=0)


def test_symmetric_pair_preserves_differential_common_normalizations():
    values=dict(R=np.array([[6,.4],[.4,6]]),L=np.array([[400,80],[80,400]])*1e-9,
                G=np.array([[.004,-.001],[-.001,.004]]),C=np.array([[100,-20],[-20,100]])*1e-12)
    old=rlgc_propagation(F,**values);new=rlgc_characteristic(F,**values)
    q=np.array([[1,1],[-1,1]])/np.sqrt(2)
    for k in range(len(F)):
        np.testing.assert_allclose(q.T@new.gamma_voltage[k]@q,np.diag(old.gamma[k]),rtol=1e-12,atol=1e-12)
        np.testing.assert_allclose(q.T@new.z_characteristic[k]@q,
            np.diag(old.z_characteristic[k]*[.5,2]),rtol=1e-12,atol=1e-12)


@pytest.mark.parametrize('loss',[0.,1e7])
def test_repeated_and_nearly_repeated_roots_do_not_require_eigenvector_tracking(loss):
    l=np.array([200,300,400])*1e-9;c=4e-17/l
    matrices=transformed(dict(R=loss*l,L=l,G=loss*c,C=c))
    result=rlgc_characteristic(F,**matrices)
    expected=(loss+2j*np.pi*F)*np.sqrt(4e-17)
    for actual,value in zip(result.gamma_voltage,expected):
        assert relative(actual,np.eye(3)*value)<1e-12
    near=c.copy();near[1]*=1+1e-12
    perturbed=rlgc_characteristic(F,**transformed(dict(R=loss*l,L=l,G=loss*near,C=near)))
    assert relative(perturbed.gamma_voltage,result.gamma_voltage)<1e-10
    assert relative(perturbed.z_characteristic,result.z_characteristic)<1e-10


def arbitrary_matrices():
    rng=np.random.default_rng(83)
    def spd(scale):
        a=rng.normal(size=(3,3));return scale*(a@a.T+np.eye(3))
    return dict(R=spd(2),L=spd(1e-7),G=spd(.001),C=spd(1e-11))


@pytest.mark.parametrize('lossless',[False,True])
def test_general_telegrapher_subspace_power_balance_and_transfer_composition(lossless):
    values=arbitrary_matrices()
    if lossless:values.update(R=np.zeros((3,3)),G=np.zeros((3,3)))
    result=rlgc_characteristic(F,**values)
    a,b,ab=(result.voltage_transfer(length) for length in (.01,.02,.03))
    np.testing.assert_allclose(a@b,ab,rtol=1e-10,atol=1e-12)
    np.testing.assert_array_equal(result.voltage_transfer(0),np.tile(np.eye(3),(len(F),1,1)))
    for k,f in enumerate(F):
        z=values['R']+2j*np.pi*f*values['L'];y=values['G']+2j*np.pi*f*values['C']
        gamma,zc,yc=result.gamma_voltage[k],result.z_characteristic[k],result.y_characteristic[k]
        assert relative(gamma@gamma,z@y)<1e-10
        assert relative(gamma@zc,z)<1e-10
        assert relative(zc@y@zc,z)<1e-10
        block=np.block([[np.zeros_like(z),-z],[-y,np.zeros_like(z)]])
        fields=expm(block*.02)@np.vstack([np.eye(3),yc])
        assert relative(fields,np.vstack([b[k],yc@b[k]]))<1e-10
        h=.5*(yc+yc.conj().T)
        loss=yc.conj().T@values['R']@yc+values['G']
        residual=gamma.conj().T@h+h@gamma-loss
        assert abs(residual).max()/(abs(gamma).max()*abs(h).max()+abs(loss).max())<1e-10
        change=b[k].conj().T@h@b[k]-h
        if lossless: assert abs(change).max()/abs(h).max()<1e-10
        else: assert np.linalg.eigvalsh(change).max()<=1e-12*abs(h).max()


@pytest.mark.parametrize('scale',[1e-200,1e-100,1e100,1e200])
def test_separate_coefficient_scaling_avoids_product_overflow_and_underflow(scale):
    values=arbitrary_matrices();original=rlgc_characteristic(F,**values)
    scaled=rlgc_characteristic(F,**{name:value*scale for name,value in values.items()})
    assert relative(scaled.gamma_voltage/scale,original.gamma_voltage)<1e-10
    assert relative(scaled.z_characteristic,original.z_characteristic)<1e-10
    assert relative(scaled.voltage_transfer(.02/scale),original.voltage_transfer(.02))<1e-10


@pytest.mark.parametrize('transform',[T,np.array([[0,1,0],[0,0,1],[1,0,0]])])
def test_power_dual_coordinate_covariance_and_permutation(transform):
    values=arbitrary_matrices();original=rlgc_characteristic(F,**values)
    inverse=np.linalg.inv(transform)
    changed={name:(transform@value@transform.T if name in ('R','L') else inverse.T@value@inverse)
             for name,value in values.items()}
    result=rlgc_characteristic(F,**changed)
    assert relative(result.gamma_voltage,transform@original.gamma_voltage@inverse)<1e-10
    assert relative(result.z_characteristic,transform@original.z_characteristic@transform.T)<1e-10
    assert relative(result.y_characteristic,inverse.T@original.y_characteristic@inverse)<1e-10


def test_frequency_dependent_coefficients_and_immutable_snapshots():
    values=arbitrary_matrices()
    stack={name:np.array([value*(1+.2*k) for k in range(len(F))]) for name,value in values.items()}
    frequency=F.copy();result=rlgc_characteristic(frequency,**stack,names=('a','b','c'))
    for k,f in enumerate(F):
        single=rlgc_characteristic([f],**{name:value[k] for name,value in stack.items()})
        np.testing.assert_array_equal(result.gamma_voltage[k],single.gamma_voltage[0])
    frequency[:]=7;stack['R'][:]=99
    np.testing.assert_array_equal(result.frequency,F)
    assert result.names==('a','b','c')
    for name in ('frequency','gamma_voltage','z_characteristic','y_characteristic'):
        assert not getattr(result,name).flags.writeable
    assert not result.voltage_transfer(.02).flags.writeable


@pytest.mark.parametrize('frequency',[[0],[-1],[],[True],[np.inf],[1e6,1e3]])
def test_invalid_frequencies_are_rejected(frequency):
    with pytest.raises(ValueError):rlgc_characteristic(frequency,**arbitrary_matrices())


@pytest.mark.parametrize('name',['R','L','G','C'])
def test_nonpassive_or_nonsymmetric_inputs_are_rejected(name):
    values=arbitrary_matrices();values[name]=-values[name]
    with pytest.raises(ValueError):rlgc_characteristic(F,**values)
    values=arbitrary_matrices();values[name][0,1]*=1.1
    with pytest.raises(ValueError,match='symmetric'):rlgc_characteristic(F,**values)


@pytest.mark.parametrize('length',[True,-1,np.nan,np.inf,[1]])
def test_invalid_lengths_are_rejected(length):
    result=rlgc_characteristic(F,**arbitrary_matrices())
    with pytest.raises(ValueError):result.voltage_transfer(length)


def test_unresolved_condition_and_unrepresentable_transfers_are_rejected():
    values=dict(R=np.zeros((2,2)),G=np.zeros((2,2)),L=np.diag([1e-30,1.]),C=np.eye(2))
    with pytest.raises(ValueError,match='condition'):rlgc_characteristic([1],**values)
    result=rlgc_characteristic(F,**arbitrary_matrices())
    with pytest.raises(ValueError,match='representable'):result.voltage_transfer(1e308)


@pytest.mark.parametrize('names',[[],['a'],['a','a','b'],['a','','b'],['a','b','c\nd']])
def test_invalid_conductor_names(names):
    with pytest.raises(ValueError):rlgc_characteristic(F,**arbitrary_matrices(),names=names)


def test_invalid_result_matrix_shapes_inverse_and_forward_branch():
    result=rlgc_characteristic(F,**arbitrary_matrices())
    args=dict(frequency=result.frequency,names=result.names,gamma_voltage=result.gamma_voltage,
              z_characteristic=result.z_characteristic,y_characteristic=result.y_characteristic)
    for changes in (dict(gamma_voltage=result.gamma_voltage[:1]),
                    dict(gamma_voltage=-result.gamma_voltage),
                    dict(y_characteristic=result.y_characteristic*2),
                    dict(z_characteristic=-result.z_characteristic)):
        with pytest.raises(ValueError):LineCharacteristic(**dict(args,**changes))


@pytest.mark.parametrize('kind',['shared','volume'])
def test_asymmetric_tensor_line_results_expose_matrices_without_new_field_solve(kind,monkeypatch):
    section=coupled_microstrip(width=.4e-3,gap=.2e-3,substrate_height=.5e-3,
        thickness=.1e-3,eps_r=4,air_height=.5e-3,box_width=2e-3)
    model=PrincipalAxisDielectric(DebyeDielectric(2,[2],[1e4]),ConstantDielectric(5,.02),.4)
    if kind=='shared':
        doc=TransmissionLineDocument(CrossSectionDocument(section,mesh=dict(edge_size=10e-6,far_size=.25e-3,grade=.2)),
            [1e3,1e5],materials={'substrate':model},conductor={'kind':'perfect'},length=.01)
    else:
        doc=VolumeLineDocument(CrossSectionDocument(section),[1e3,1e5],materials={'substrate':model},
            conductivity=58e6,length=.01,mesh=dict(ground_thickness=.1e-3,padding=2e-3,
                metal_size=50e-6,far_size=.5e-3,grade=.2,min_angle=28))
    line=doc.analyze()
    def forbidden(*args,**kwargs):pytest.fail('characteristic diagnostics started a field solve')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    monkeypatch.setattr('sipi.volume_line.mesh_conductor_section',forbidden)
    result=line.characteristic()
    assert result.names==line.names
    direct=rlgc_characteristic(line.frequency,R=line.R,L=line.L,G=line.G,C=line.C,names=line.names)
    np.testing.assert_array_equal(result.gamma_voltage,direct.gamma_voltage)
    with pytest.raises(ValueError,match='exchange-symmetric'):line.propagation()
