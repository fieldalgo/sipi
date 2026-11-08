# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Two-signal Debye waves: scalar-mode limits and terminal energy partitions."""
from copy import copy
import json
import numpy as np
import pytest
from sipi import psd_coupled_debye_reactive_ladder_response, coupled_reactive_ladder_response, debye_rlgc_ladder_response, startup_port_waves


def arguments(kind='exchange',pulse=False):
    t=np.linspace(0.,12e-9,121);d=np.minimum(t/2e-9,1.)
    if pulse:d-=np.minimum(np.maximum(t-5e-9,0)/2e-9,1.)
    a=dict(time=t,source_voltages=d[:,None]*[1.,-.4],R=np.array([[20.,3.],[3.,20.]]),
        L=np.array([[500.,100.],[100.,500.]])*1e-9,G=np.array([[.002,-.0003],[-.0003,.002]]),
        C_inf=np.array([[220.,-40.],[-40.,220.]])*1e-12,
        delta_C=np.array([[[150.,-150.],[-150.,150.]],[[50.,50.],[50.,50.]]])*1e-12,
        relaxation_hz=np.array([1e9,1e8]),length=.1,cells=16,
        source_resistance=[25.,25.],load_resistance=[100.,100.],load_capacitance=np.array([[30.,-5.],[-5.,30.]])*1e-12,
        load_branch_resistance=np.array([[150.,20.],[20.,150.]]),load_branch_inductance=np.array([[200.,30.],[30.,200.]])*1e-9)
    if kind=='diagonal':
        for key in ['R','L','G','C_inf','load_capacitance','load_branch_resistance','load_branch_inductance']:a[key]=np.diag(np.diag(a[key]))
        a['delta_C']=np.array([np.diag([150e-12,0.]),np.diag([0.,50e-12])])
    if kind=='noncommuting':
        a.update(R=np.array([[25.,2.],[2.,17.]]),L=np.array([[510.,70.],[70.,430.]])*1e-9,
            G=np.array([[.003,-.0002],[-.0002,.0015]]),C_inf=np.array([[230.,-30.],[-30.,190.]])*1e-12,
            delta_C=np.array([[[80.,-40.],[-40.,20.]],[[32.,32.],[32.,32.]]])*1e-12,
            source_resistance=[23.,37.],load_resistance=[91.,113.],load_capacitance=np.array([[20.,-4.],[-4.,30.]])*1e-12,
            load_branch_resistance=np.array([[140.,17.],[17.,180.]]),load_branch_inductance=np.array([[210.,25.],[25.,170.]])*1e-9)
    return a


def checks(r,z=(35.,45.,55.,65.)):
    w=startup_port_waves(r,z_ref=z);assert w.source_kind=='DebyeReactiveLadderResponse'
    assert w.port_names==('near_0','near_1','far_0','far_1')
    for name in ['time','voltage','current']:np.testing.assert_array_equal(getattr(w,name),getattr(r,name))
    root=np.sqrt(w.z_ref);power=w.incident**2-w.reflected**2
    np.testing.assert_allclose(root*(w.incident+w.reflected),r.voltage,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose((w.incident-w.reflected)/root,r.current,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(power,r.voltage*r.current,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(power[:,:2].sum(axis=1),r.source_power-r.source_resistor_loss,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(power[:,2:].sum(axis=1),-r.load_resistor_loss-r.load_capacitor_power-r.load_branch_energy_rate-r.load_branch_resistor_loss,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(power.sum(axis=1),r.line_energy_rate+r.series_loss+r.shunt_loss+r.relaxation_loss,rtol=1e-10,atol=1e-12)
    assert max(w.voltage_reconstruction_relative_error,w.current_reconstruction_relative_error,w.power_balance_relative_error)<=1e-10
    return w


@pytest.mark.parametrize('kind',['diagonal','exchange','noncommuting'])
@pytest.mark.parametrize('pulse',[False,True])
def test_terminal_power_includes_relaxation_and_reference_invariance(kind,pulse):
    r=psd_coupled_debye_reactive_ladder_response(**arguments(kind,pulse));w=checks(r);other=checks(r,[70.,90.,110.,130.])
    np.testing.assert_array_equal(other.port_power,w.port_power)
    assert np.max(r.relaxation_loss)>0 and np.max(r.polarization_energy)>0


@pytest.mark.parametrize('kind',['diagonal','exchange'])
@pytest.mark.parametrize('pulse',[False,True])
def test_independent_scalar_modes_reconstruct_four_terminal_waves(kind,pulse):
    a=arguments(kind,pulse);a['load_capacitance'][:]=0;a['load_branch_inductance']=np.eye(2)*1e6;basis=np.eye(2) if kind=='diagonal' else np.array([[1.,1.],[1.,-1.]])/np.sqrt(2)
    w=checks(psd_coupled_debye_reactive_ladder_response(**a),[35.,35.,75.,75.]);parts=[]
    for mode in range(2):
        pick=lambda m:float((basis.T@m@basis)[mode,mode])
        r=debye_rlgc_ladder_response(a['time'],(a['source_voltages']@basis)[:,mode],
            **{key:pick(a[key]) for key in ['R','L','G','C_inf']},
            delta_C=[pick(x) for x in a['delta_C']],relaxation_hz=a['relaxation_hz'],
            length=a['length'],cells=a['cells'],source_resistance=25.,load_resistance=100.)
        parts.append(startup_port_waves(r,z_ref=[35.,75.]))
    for name in ['incident','reflected']:
        modal=np.stack([getattr(x,name) for x in parts],axis=2)@basis.T
        expected=np.concatenate((modal[:,0],modal[:,1]),axis=1)
        np.testing.assert_allclose(getattr(w,name),expected,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(w.port_power.sum(axis=1),sum(x.port_power.sum(axis=1) for x in parts),rtol=1e-10,atol=1e-12)


@pytest.mark.parametrize('pulse',[False,True])
def test_zero_strength_original_coupled_limit(pulse):
    a=arguments('noncommuting',pulse);a['delta_C'][:]=0;w=checks(psd_coupled_debye_reactive_ladder_response(**a))
    a['C']=a.pop('C_inf');a.pop('delta_C');a.pop('relaxation_hz');other=startup_port_waves(coupled_reactive_ladder_response(**a),z_ref=w.z_ref)
    for name in ['incident','reflected','port_power']:np.testing.assert_allclose(getattr(w,name),getattr(other,name),rtol=1e-10,atol=1e-12)


def test_noncommuting_pole_and_conductor_permutations():
    a=arguments('noncommuting');w=checks(psd_coupled_debye_reactive_ladder_response(**a))
    a['delta_C']=a['delta_C'][::-1];a['relaxation_hz']=a['relaxation_hz'][::-1];other=checks(psd_coupled_debye_reactive_ladder_response(**a))
    for name in ['incident','reflected','port_power']:np.testing.assert_allclose(getattr(w,name),getattr(other,name),rtol=1e-10,atol=1e-12)
    for key in ['R','L','G','C_inf','load_capacitance','load_branch_resistance','load_branch_inductance']:a[key]=a[key][::-1,::-1]
    a['delta_C']=a['delta_C'][:,::-1,::-1];a['source_voltages']=a['source_voltages'][:,::-1]
    a['source_resistance']=a['source_resistance'][::-1];a['load_resistance']=a['load_resistance'][::-1]
    order=[1,0,3,2];other=checks(psd_coupled_debye_reactive_ladder_response(**a),w.z_ref[order])
    for name in ['incident','reflected','port_power']:np.testing.assert_allclose(getattr(other,name),getattr(w,name)[:,order],rtol=1e-10,atol=1e-12)


def test_zero_readonly_detached_finite_json():
    a=arguments();a['source_voltages'][:]=0;w=checks(psd_coupled_debye_reactive_ladder_response(**a));assert not np.any(w.incident) and not np.any(w.reflected)
    r=psd_coupled_debye_reactive_ladder_response(**arguments());z=np.array([35.,45.,55.,65.]);w=checks(r,z);before=json.dumps(w.to_dict(),sort_keys=True,allow_nan=False);z[:]=9
    for name in ['time','voltage','current','z_ref','incident','reflected','port_power']:
        assert not getattr(w,name).flags.writeable and not np.shares_memory(getattr(w,name),getattr(r,name,np.empty(0)))
    out=w.to_dict();out['port_power_w'][0][0]=9;assert json.dumps(w.to_dict(),sort_keys=True,allow_nan=False)==before


@pytest.mark.parametrize('z',[50.,[50.,50.],[50.]*3,[50.]*5,[0.,50.,50.,50.],[-1.,50.,50.,50.],[True,50.,50.,50.],[np.inf,50.,50.,50.],[50+0j,50.,50.,50.]])
def test_explicit_positive_real_four_references(z):
    with pytest.raises(ValueError):startup_port_waves(psd_coupled_debye_reactive_ladder_response(**arguments()),z_ref=z)


@pytest.mark.parametrize('replacement',['drive','polarization-current','load-capacitor-current','load-branch-current'])
def test_internal_arrays_cannot_replace_four_terminal_current(replacement):
    r=copy(psd_coupled_debye_reactive_ladder_response(**arguments()));value={'drive':r.source_voltages,'polarization-current':r.polarization_current,'load-capacitor-current':r.load_capacitor_current,'load-branch-current':r.load_branch_current}[replacement]
    object.__setattr__(r,'current',value)
    with pytest.raises(ValueError,match='shapes'):startup_port_waves(r,z_ref=[35.,45.,55.,65.])


@pytest.mark.parametrize('pulse',[False,True])
def test_large_branch_inductance_original_capacitive_wave_limit(pulse):
    from sipi import psd_coupled_debye_capacitive_ladder_response as original
    a=arguments(pulse=pulse);a['load_branch_inductance']=np.eye(2)*1e6
    w=checks(psd_coupled_debye_reactive_ladder_response(**a));a.pop('load_branch_resistance');a.pop('load_branch_inductance')
    other=startup_port_waves(original(**a),z_ref=w.z_ref)
    for name in ['incident','reflected','port_power']:np.testing.assert_allclose(getattr(w,name),getattr(other,name),rtol=1e-10,atol=1e-12)


def test_null_mode_no_polarization_power_matches_constant_line_waves():
    a=arguments('diagonal');a['delta_C']=np.array([np.diag([150e-12,0.])]);a['relaxation_hz']=[1e9];a['source_voltages'][:,0]=0
    r=psd_coupled_debye_reactive_ladder_response(**a);w=checks(r)
    assert np.any(r.polarization_voltage[:,:,:,1])
    assert not np.any(r.polarization_energy) and not np.any(r.relaxation_loss)
    a['C']=a.pop('C_inf');a.pop('delta_C');a.pop('relaxation_hz');other=startup_port_waves(coupled_reactive_ladder_response(**a),z_ref=w.z_ref)
    for name in ['incident','reflected','port_power']:np.testing.assert_allclose(getattr(w,name),getattr(other,name),rtol=1e-10,atol=1e-12)
    assert not np.any(w.incident[:,[0,2]]) and not np.any(w.reflected[:,[0,2]])


@pytest.mark.parametrize('tiny',[1e-13,1e-20])
def test_near_singular_strength_waves_remain_finite_without_rank_clipping(tiny):
    a=arguments('diagonal');a['delta_C']=np.array([np.diag([150e-12,150e-12*tiny])]);a['relaxation_hz']=[1e9]
    r=psd_coupled_debye_reactive_ladder_response(**a);w=checks(r)
    assert r.inputs['delta_C_f_per_m'][0][1][1]==150e-12*tiny and np.any(r.polarization_charge[:,:,:,1])
    assert np.all(np.isfinite(w.incident)) and np.all(np.isfinite(w.reflected))


@pytest.mark.parametrize('cap',[np.zeros((2,2)),np.array([[30.,-30.],[-30.,30.]])*1e-12,np.array([[20.,-4.],[-4.,30.]])*1e-12])
@pytest.mark.parametrize('pulse',[False,True])
def test_external_capacitance_and_energy_partitions(cap,pulse):
    a=arguments('noncommuting',pulse);a['load_capacitance']=cap
    r=psd_coupled_debye_reactive_ladder_response(**a);w=checks(r)
    np.testing.assert_allclose(r.total_energy_rate,r.line_energy_rate+r.load_capacitor_power+r.load_branch_energy_rate,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(r.source_power,r.total_energy_rate+r.series_loss+r.shunt_loss+r.relaxation_loss+r.source_resistor_loss+r.load_resistor_loss+r.load_branch_resistor_loss,rtol=1e-10,atol=1e-12)
    far=r.voltage[:,2:]
    np.testing.assert_allclose(w.port_power[:,2:].sum(axis=1),-np.sum(far**2/np.array(a['load_resistance']),axis=1)-np.sum(far*(r.load_capacitor_current+r.load_branch_current),axis=1),rtol=1e-10,atol=1e-12)


def test_external_capacitor_charge_and_discharge_are_not_line_loss():
    r=psd_coupled_debye_reactive_ladder_response(**arguments('noncommuting',True));w=checks(r)
    assert np.max(r.load_capacitor_power)>1e-6 and np.min(r.load_capacitor_power)<-1e-6
    assert np.max(abs(r.total_energy_rate-r.line_energy_rate))>1e-6
    assert np.max(abs(w.port_power[:,2:].sum(axis=1)+r.load_resistor_loss))>1e-6
    assert np.all(r.load_capacitor_energy>=0) and np.all(r.load_resistor_loss>=0)


@pytest.mark.parametrize('rb',[np.zeros((2,2)),np.array([[150.,-150.],[-150.,150.]]),np.array([[140.,17.],[17.,180.]])])
@pytest.mark.parametrize('pulse',[False,True])
def test_external_branch_power_is_separate_from_line_storage_and_parallel_loss(rb,pulse):
    a=arguments('noncommuting',pulse);a['load_branch_resistance']=rb
    r=psd_coupled_debye_reactive_ladder_response(**a);w=checks(r);far=r.voltage[:,2:]
    np.testing.assert_allclose(np.sum(far*r.load_branch_current,axis=1),r.load_branch_energy_rate+r.load_branch_resistor_loss,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(w.port_power[:,2:].sum(axis=1),-r.load_resistor_loss-r.load_capacitor_power-np.sum(far*r.load_branch_current,axis=1),rtol=1e-10,atol=1e-12)
    assert np.all(r.load_branch_energy>=0) and np.all(r.load_branch_resistor_loss>=0)
    if not np.any(rb):assert not np.any(r.load_branch_resistor_loss)
    if pulse:assert np.any(r.load_branch_energy_rate<0)
