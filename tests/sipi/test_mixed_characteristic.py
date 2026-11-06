# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Physical differential/common normalization for full pair matrices."""
import importlib.metadata as metadata
import numpy as np
import pytest
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import (LineCharacteristic, rlgc_characteristic, rlgc_propagation,
                  CrossSection, CrossSectionDocument, coupled_microstrip)
from sipi.dielectric import PrincipalAxisDielectric, DebyeDielectric, ConstantDielectric
from sipi.line_model import TransmissionLineDocument
from sipi.volume_line import VolumeLineDocument

F = np.array([1e3, 1e6, 1e9, 1e10])


def values(symmetric=False, lossless=False):
    return dict(R=np.zeros((2,2)) if lossless else np.array([[6,.4],[.4,6 if symmetric else 11]]),
        L=np.array([[400,80],[80,400 if symmetric else 310]])*1e-9,
        G=np.zeros((2,2)) if lossless else np.array([[.004,-.001],[-.001,.004 if symmetric else .006]]),
        C=np.array([[100,-20],[-20,100 if symmetric else 130]])*1e-12)


def voltage_coordinates(v):
    return np.stack([v[...,0]-v[...,1], (v[...,0]+v[...,1])/2], axis=-1)


def current_coordinates(i):
    return np.stack([(i[...,0]-i[...,1])/2, i[...,0]+i[...,1]], axis=-1)


@pytest.mark.parametrize('lossless', [False, True])
def test_independent_generalized_mixed_wave_coordinates(lossless):
    skrf = require_tool('scikit-rf'); clock = Stopwatch()
    original = rlgc_characteristic(F, **values(lossless=lossless), names=('plus','minus'))
    with clock('openphysics'): actual = original.mixed_mode()
    with clock('reference'):
        reference = skrf.Network(frequency=skrf.Frequency.from_f(F,unit='Hz'),
                                z=original.z_characteristic, z0=50)
        reference.se2gmm(p=1)
    errors = [float(abs(a-b).max()/abs(b).max()) for a,b in
              [(actual.z_characteristic, reference.z), (actual.y_characteristic, reference.y)]]
    record = make_record(case='mixed-characteristic-'+('lossless' if lossless else 'lossy'),
        physics='power-dual pair coordinates', api='sipi.LineCharacteristic.mixed_mode',
        discretization='full differential/common voltage, current and forward matrices',
        tool='scikit-rf', tool_discretization='generalized mixed-mode waves and impedance/admittance conversion',
        matched=['same coupled impedance matrices and differential/common physical normalization'],
        not_matched=['coordinate comparison, not an independent field extraction or eigenmode identification'],
        observables=[observable(name, unit, 'max normwise relative difference', error, 1e-10)
                     for name,unit,error in zip(('Zc','Yc'),('ohm','S'),errors)],
        analytical_acceptance='symmetric modal limit, complex-power invariance and telegrapher covariance',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi')); emit(record)
    assert max(errors) < 1e-10
    assert actual.names == ('differential','common') and actual.basis == 'mixed-mode'
    assert original.basis == 'single-ended' and original.names == ('plus','minus')
    assert abs(actual.z_characteristic[:,0,1]).max() > 1
    assert abs(actual.gamma_voltage[:,0,1]).max() > 1e-3


@pytest.mark.parametrize('lossless', [False, True])
def test_symmetric_pair_reduces_to_existing_differential_common_modes(lossless):
    args = values(symmetric=True,lossless=lossless)
    modes = rlgc_propagation(F,**args)
    actual = rlgc_characteristic(F,**args).mixed_mode()
    for k in range(len(F)):
        np.testing.assert_allclose(actual.z_characteristic[k],np.diag(modes.z_characteristic[k]),
                                   rtol=1e-12,atol=1e-12)
        np.testing.assert_allclose(actual.gamma_voltage[k],np.diag(modes.gamma[k]),rtol=1e-12,atol=1e-12)


@pytest.mark.parametrize('lossless', [False, True])
def test_complex_power_constitutive_derivative_and_forward_transfer(lossless):
    args = values(lossless=lossless)
    single = rlgc_characteristic(F,**args); mixed = single.mixed_mode()
    drive = np.array([1+.2j,-.3+.7j])
    for length in (0., .01, .1):
        v = single.voltage_transfer(length)@drive
        i = np.einsum('fij,fj->fi',single.y_characteristic,v)
        vm,im = voltage_coordinates(v),current_coordinates(i)
        np.testing.assert_allclose(mixed.voltage_transfer(length)@voltage_coordinates(drive),vm,
                                   atol=1e-12,rtol=1e-12)
        np.testing.assert_allclose(np.einsum('fij,fj->fi',mixed.y_characteristic,vm),im,
                                   atol=1e-12,rtol=1e-12)
        np.testing.assert_allclose(np.einsum('fij,fj->fi',mixed.z_characteristic,im),vm,
                                   atol=1e-12,rtol=1e-12)
        np.testing.assert_allclose(np.sum(vm*np.conj(im),axis=1),np.sum(v*np.conj(i),axis=1),
                                   atol=1e-12,rtol=1e-12)
        derivative = -np.einsum('fij,fj->fi',single.gamma_voltage,v)
        mixed_derivative = -np.einsum('fij,fj->fi',mixed.gamma_voltage,vm)
        np.testing.assert_allclose(mixed_derivative,voltage_coordinates(derivative),atol=1e-12,rtol=1e-12)
    # Convert RLGC by their voltage/current laws, then recompute the physical root.
    a=np.array([[1.,-1.],[.5,.5]]); b=np.array([[.5,-.5],[1.,1.]])
    transformed={name:(a@x@a.T if name in ('R','L') else b@x@b.T) for name,x in args.items()}
    reference=rlgc_characteristic(F,**transformed)
    for name in ('gamma_voltage','z_characteristic','y_characteristic'):
        x,y=getattr(mixed,name),getattr(reference,name)
        assert abs(x-y).max()/abs(y).max()<1e-10


def test_pair_polarity_reversal_changes_only_cross_coordinate_signs():
    args=values(); original=rlgc_characteristic(F,**args).mixed_mode()
    flipped=rlgc_characteristic(F,**{name:x[::-1,::-1] for name,x in args.items()}).mixed_mode()
    sign=np.diag([-1.,1.])
    for name in ('gamma_voltage','z_characteristic','y_characteristic'):
        np.testing.assert_allclose(getattr(flipped,name),sign@getattr(original,name)@sign,rtol=1e-12,atol=1e-12)


def test_identical_uncoupled_lines_and_forward_current_launch_definition():
    single=rlgc_characteristic(F,R=np.zeros((2,2)),L=np.eye(2)*250e-9,
                               G=np.zeros((2,2)),C=np.eye(2)*100e-12)
    mixed=single.mixed_mode()
    np.testing.assert_allclose(mixed.z_characteristic,np.broadcast_to(np.diag([100.,25.]),(4,2,2)),
                               rtol=1e-12,atol=1e-12)
    coupled=rlgc_characteristic(F,**values()).mixed_mode()
    currents=np.array([1.,0.])
    voltages=coupled.z_characteristic@currents
    np.testing.assert_array_equal(voltages[:,0],coupled.z_characteristic[:,0,0])
    np.testing.assert_array_equal(voltages[:,1],coupled.z_characteristic[:,1,0])
    assert abs(voltages[:,1]).max()>1  # Not an uncoupled differential eigenmode.


def test_old_constructor_immutable_arrays_and_repeat_rejection():
    source=rlgc_characteristic(F,**values())
    old=LineCharacteristic(source.frequency,source.names,source.gamma_voltage,
                           source.z_characteristic,source.y_characteristic)
    assert old.basis=='single-ended'
    mixed=old.mixed_mode()
    for name in ('frequency','gamma_voltage','z_characteristic','y_characteristic'):
        array=getattr(mixed,name);assert not array.flags.writeable
        array.setflags(write=True);array[:]=123
        assert not np.any(getattr(old,name)==123)
    with pytest.raises(ValueError,match='two single-ended'):old.mixed_mode().mixed_mode()


@pytest.mark.parametrize('count',[1,3])
def test_other_conductor_counts_rejected(count):
    eye=np.eye(count)
    source=rlgc_characteristic(F,R=eye,L=eye*250e-9,G=eye*.001,C=eye*100e-12)
    with pytest.raises(ValueError,match='two single-ended'):source.mixed_mode()
    with pytest.raises(ValueError,match='basis'):
        LineCharacteristic(source.frequency,source.names,source.gamma_voltage,
                           source.z_characteristic,source.y_characteristic,basis='mixed-mode')


def test_unrepresentable_mixed_impedance_is_rejected_without_rescaling_output():
    source=LineCharacteristic([1],('a','b'),[1j*np.eye(2)],[1e308*np.eye(2)],[1e-308*np.eye(2)])
    with pytest.raises(ValueError,match='finite'):source.mixed_mode()


@pytest.mark.parametrize('basis',[None,True,'modes',[],{}])
def test_invalid_basis(basis):
    source=rlgc_characteristic(F,**values())
    with pytest.raises(ValueError,match='basis'):
        LineCharacteristic(source.frequency,source.names,source.gamma_voltage,
                           source.z_characteristic,source.y_characteristic,basis=basis)


@pytest.mark.parametrize('kind',['shared','volume'])
def test_asymmetric_tensor_line_view_does_not_start_another_field_solve(kind,monkeypatch):
    section=coupled_microstrip(width=.4e-3,gap=.2e-3,substrate_height=.5e-3,
        thickness=.1e-3,eps_r=4,air_height=.5e-3,box_width=2e-3)
    material=PrincipalAxisDielectric(DebyeDielectric(2,[2],[1e4]),ConstantDielectric(5,.02),.4)
    if kind=='shared':
        doc=TransmissionLineDocument(CrossSectionDocument(section,mesh=dict(edge_size=10e-6,far_size=.25e-3,grade=.2)),
            [1e3,1e5],materials={'substrate':material},conductor={'kind':'perfect'},length=.01)
    else:
        doc=VolumeLineDocument(CrossSectionDocument(section),[1e3,1e5],materials={'substrate':material},
            conductivity=58e6,length=.01,mesh=dict(ground_thickness=.1e-3,padding=2e-3,
                metal_size=50e-6,far_size=.5e-3,grade=.2,min_angle=28))
    line=doc.analyze()
    def forbidden(*args,**kwargs):pytest.fail('coordinate view started another field solve')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    monkeypatch.setattr('sipi.volume_line.mesh_conductor_section',forbidden)
    mixed=line.characteristic().mixed_mode()
    assert mixed.basis=='mixed-mode' and abs(mixed.z_characteristic[:,0,1]).max()>1e-6
    with pytest.raises(ValueError,match='exchange-symmetric'):line.propagation()
