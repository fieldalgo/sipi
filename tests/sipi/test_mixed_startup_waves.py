# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Mixed-source terminal waves retain source units and external power partitions."""
from copy import copy
import json
import numpy as np
import pytest
from sipi import (coupled_mixed_source_ladder_response, coupled_reactive_ladder_response,
    coupled_norton_reactive_ladder_response, startup_port_waves)


def arguments(kinds=('voltage','current'),resistance=(0.,None),load=(91.,None),pulse=False):
    t=np.linspace(0,12e-9,121);ramp=np.interp(t,[0,2e-9,4e-9,6e-9],[0,1,1,0]) if pulse else np.minimum(t/2e-9,1.)
    drive=np.column_stack((ramp,-.4*np.minimum(t/3e-9,1.)))
    src=[]
    for j,k in enumerate(kinds):
        src.append(dict(kind=k,**{('voltage_v' if k=='voltage' else 'current_a'):drive[:,j]*(1. if k=='voltage' else .02),
            ('series_resistance_ohm' if k=='voltage' else 'shunt_resistance_ohm'):resistance[j]}))
    return dict(time=t,sources=src,R=[[25.,2.],[2.,17.]],L=np.array([[510.,70.],[70.,430.]])*1e-9,
        G=[[.003,-.0002],[-.0002,.0015]],C=np.array([[230.,-30.],[-30.,190.]])*1e-12,
        length=.1,cells=8,load_resistance=load,load_capacitance=np.array([[20.,-4.],[-4.,30.]])*1e-12,
        load_branch_resistance=[[13.,1.],[1.,9.]],load_branch_inductance=np.array([[12.,2.],[2.,8.]])*1e-9)


def checks(source,z=(35.,45.,55.,65.)):
    w=startup_port_waves(source,z_ref=z)
    assert w.source_kind=='MixedSourceRLGCLadderResponse' and w.port_names==source.port_names
    for name in ['time','voltage','current']:np.testing.assert_array_equal(getattr(w,name),getattr(source,name))
    assert max(w.voltage_reconstruction_relative_error,w.current_reconstruction_relative_error,w.power_balance_relative_error)<=1e-10
    root=np.sqrt(w.z_ref)
    np.testing.assert_allclose(root*(w.incident+w.reflected),source.voltage,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose((w.incident-w.reflected)/root,source.current,rtol=1e-10,atol=1e-12)
    power=w.incident**2-w.reflected**2
    np.testing.assert_allclose(power,source.voltage*source.current,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(power[:,:2].sum(axis=1),source.source_power-source.source_series_resistor_loss-source.source_shunt_resistor_loss,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(power[:,2:].sum(axis=1),-source.load_resistor_loss-source.load_capacitor_power-source.load_branch_energy_rate-source.load_branch_resistor_loss,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(power.sum(axis=1),source.line_power,rtol=1e-10,atol=1e-12)
    return w


@pytest.mark.parametrize('kinds,resistance,load',[
    (['voltage','current'],[0.,None],[91.,None]),(['current','voltage'],[None,0.],[None,0.]),
    (['voltage','current'],[25.,37.],[91.,113.]),(['current','voltage'],[37.,25.],[91.,113.]),
    (['voltage','current'],[0.,0.],[0.,None]),(['current','voltage'],[0.,0.],[None,0.]),
])
def test_actual_mixed_boundaries_preserve_terminal_waves_and_source_power_split(kinds,resistance,load):
    r=coupled_mixed_source_ladder_response(**arguments(kinds,resistance,load));w=checks(r)
    other=checks(r,[70.,90.,110.,130.]);np.testing.assert_array_equal(other.port_power,w.port_power)
    for j,k in enumerate(kinds):
        if k=='current' and resistance[j]==0:np.testing.assert_array_equal(w.incident[:,j],-w.reflected[:,j])
        if k=='current' and resistance[j] is None:np.testing.assert_allclose((w.incident[:,j]-w.reflected[:,j])/np.sqrt(w.z_ref[j]),r.source_values[:,j],rtol=1e-10,atol=1e-12)
        if k=='voltage' and resistance[j]==0:np.testing.assert_allclose((w.incident[:,j]+w.reflected[:,j])*np.sqrt(w.z_ref[j]),r.source_values[:,j],rtol=1e-10,atol=1e-12)
    for j,res in enumerate(load):
        if res==0:np.testing.assert_array_equal(w.incident[:,j+2],-w.reflected[:,j+2])


@pytest.mark.parametrize('pulse',[False,True])
def test_mixed_finite_source_equivalent_thevenin_waves_preserve_only_net_delivered_power(pulse):
    a=arguments(resistance=[25.,37.],pulse=pulse);r=coupled_mixed_source_ladder_response(**a);w=checks(r)
    src=a.pop('sources');v=np.column_stack((src[0]['voltage_v'],src[1]['current_a']*37.))
    other=coupled_reactive_ladder_response(source_voltages=v,source_resistance=[25.,37.],**a)
    old=startup_port_waves(other,z_ref=w.z_ref)
    for name in ['incident','reflected']:np.testing.assert_allclose(getattr(w,name),getattr(old,name),rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(r.source_power-r.source_series_resistor_loss-r.source_shunt_resistor_loss,other.source_power-other.source_resistor_loss,rtol=1e-10,atol=1e-12)
    assert np.max(abs(r.source_power-other.source_power))>1e-6
    assert np.max(abs(r.source_series_resistor_loss+r.source_shunt_resistor_loss-other.source_resistor_loss))>1e-6


@pytest.mark.parametrize('kind',['voltage','current'])
def test_homogeneous_limits_keep_original_source_wave_values(kind):
    resistance=[0.,37.] if kind=='voltage' else [None,37.];a=arguments([kind,kind],resistance);r=coupled_mixed_source_ladder_response(**a);w=checks(r)
    src=a.pop('sources');drive=np.column_stack([s['voltage_v' if kind=='voltage' else 'current_a'] for s in src])
    other=(coupled_reactive_ladder_response(source_voltages=drive,source_resistance=resistance,**a) if kind=='voltage'
        else coupled_norton_reactive_ladder_response(source_currents=drive,source_shunt_resistance=resistance,**a))
    old=startup_port_waves(other,z_ref=w.z_ref)
    np.testing.assert_allclose(w.incident,old.incident,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(w.reflected,old.reflected,rtol=1e-10,atol=1e-12)
    assert w.source_kind!=old.source_kind


@pytest.mark.parametrize('rankone',[False,True])
def test_zero_rankone_external_terms_keep_wave_power(rankone):
    a=arguments();mat=np.array([[1.,-1.],[-1.,1.]]) if rankone else np.zeros((2,2))
    a.update(load_capacitance=mat*20e-12,load_branch_resistance=mat);checks(coupled_mixed_source_ladder_response(**a))


def test_zero_drive_detached_readonly_and_finite_json():
    a=arguments();a['sources'][0]['voltage_v'][:]=0;a['sources'][1]['current_a'][:]=0
    w=checks(coupled_mixed_source_ladder_response(**a));assert not np.any(w.incident) and not np.any(w.reflected)
    r=coupled_mixed_source_ladder_response(**arguments());z=np.array([35.,45.,55.,65.]);w=checks(r,z);text=json.dumps(w.to_dict(),sort_keys=True,allow_nan=False);z[:]=99
    for name in ['time','voltage','current','z_ref','incident','reflected','port_power']:
        assert not getattr(w,name).flags.writeable and not np.shares_memory(getattr(w,name),getattr(r,name,np.empty(0)))
    data=w.to_dict();data['current_into_line_a'][0][0]=99;assert json.dumps(w.to_dict(),sort_keys=True,allow_nan=False)==text


def test_mixed_drive_values_cannot_substitute_four_terminal_currents():
    r=copy(coupled_mixed_source_ladder_response(**arguments()));object.__setattr__(r,'current',r.source_values)
    with pytest.raises(ValueError,match='shapes'):startup_port_waves(r,z_ref=[35.,45.,55.,65.])
