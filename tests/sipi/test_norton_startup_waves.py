# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Current-source terminal waves, equivalent circuits and source power partition."""
import json
from copy import copy

import numpy as np
import pytest
from sipi import (coupled_norton_reactive_ladder_response,
                  coupled_reactive_ladder_response, startup_port_waves)


def arguments(**changes):
    t=np.linspace(0.,12e-9,121)
    args=dict(time=t,source_currents=np.column_stack((.02*np.minimum(t/2e-9,1.),-.01*np.minimum(t/3e-9,1.))),
        R=[[25.,2.],[2.,17.]],L=np.array([[510.,70.],[70.,430.]])*1e-9,
        G=[[.003,-.0002],[-.0002,.0015]],C=np.array([[230.,-30.],[-30.,190.]])*1e-12,
        length=.1,cells=8,source_shunt_resistance=[None,37.],load_resistance=[91.,None],
        load_capacitance=np.array([[20.,-4.],[-4.,30.]])*1e-12,
        load_branch_resistance=[[13.,1.],[1.,9.]],load_branch_inductance=np.array([[12.,2.],[2.,8.]])*1e-9)
    args.update(changes);return args


def checks(source,z):
    w=startup_port_waves(source,z_ref=z)
    for field in ['time','voltage','current']:np.testing.assert_array_equal(getattr(w,field),getattr(source,field))
    assert w.port_names==source.port_names and w.source_kind=='NortonReactiveRLGCLadderResponse'
    assert max(w.voltage_reconstruction_relative_error,w.current_reconstruction_relative_error,w.power_balance_relative_error)<=1e-10
    root=np.sqrt(w.z_ref)
    np.testing.assert_allclose(root*(w.incident+w.reflected),source.voltage,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose((w.incident-w.reflected)/root,source.current,rtol=1e-10,atol=1e-12)
    power=w.incident**2-w.reflected**2
    np.testing.assert_allclose(power,source.voltage*source.current,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(power[:,:2].sum(axis=1),source.source_power-source.source_shunt_resistor_loss,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(power[:,2:].sum(axis=1),-source.load_resistor_loss-source.load_capacitor_power-source.load_branch_energy_rate-source.load_branch_resistor_loss,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(power.sum(axis=1),source.line_power,rtol=1e-10,atol=1e-12)
    return w


@pytest.mark.parametrize('shunt,load',[
    ([None,None],[None,None]),([0.,0.],[0.,0.]),([None,37.],[None,0.]),
    ([23.,0.],[0.,None]),([23.,37.],[None,100.]),([23.,37.],[91.,113.]),
])
def test_actual_mixed_boundaries_use_terminal_currents_and_separate_external_powers(shunt,load):
    source=coupled_norton_reactive_ladder_response(**arguments(source_shunt_resistance=shunt,load_resistance=load))
    w=checks(source,[35.,45.,55.,65.])
    changed=checks(source,[70.,90.,110.,130.]);np.testing.assert_array_equal(changed.port_power,w.port_power)
    for j,r in enumerate(shunt):
        if r is None:np.testing.assert_allclose((w.incident[:,j]-w.reflected[:,j])/np.sqrt(w.z_ref[j]),source.source_currents[:,j],rtol=1e-10,atol=1e-12)
        elif r==0:np.testing.assert_array_equal(w.incident[:,j],-w.reflected[:,j])
        else:
            assert np.max(abs(source.current[:,j]-source.source_currents[:,j]))>1e-8
            assert np.max(source.source_shunt_resistor_loss)>0
    for j,r in enumerate(load):
        if r==0:np.testing.assert_array_equal(w.incident[:,j+2],-w.reflected[:,j+2])


@pytest.mark.parametrize('pulse',[False,True])
def test_finite_norton_thevenin_equivalence_includes_waves_but_not_source_loss(pulse):
    args=arguments(source_shunt_resistance=[25.,37.])
    if pulse:args['source_currents'][:,0]=.02*np.interp(args['time'],[0.,2e-9,4e-9,6e-9],[0.,1.,1.,0.])
    source=coupled_norton_reactive_ladder_response(**args);w=checks(source,[35.,45.,55.,65.])
    current=args.pop('source_currents');shunt=np.array(args.pop('source_shunt_resistance'))
    other=coupled_reactive_ladder_response(source_voltages=current*shunt,source_resistance=shunt,**args)
    v=startup_port_waves(other,z_ref=w.z_ref)
    np.testing.assert_allclose(w.incident,v.incident,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(w.reflected,v.reflected,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(source.source_power-source.source_shunt_resistor_loss,other.source_power-other.source_resistor_loss,rtol=1e-10,atol=1e-12)
    assert np.max(abs(source.source_power-other.source_power))>1e-6
    assert np.max(abs(source.source_shunt_resistor_loss-other.source_resistor_loss))>1e-6


@pytest.mark.parametrize('rankone',[False,True])
def test_zero_and_rankone_external_terms_preserve_terminal_wave_contract(rankone):
    matrix=np.array([[1.,-1.],[-1.,1.]]) if rankone else np.zeros((2,2))
    source=coupled_norton_reactive_ladder_response(**arguments(load_capacitance=matrix*20e-12,load_branch_resistance=matrix))
    checks(source,[35.,45.,55.,65.])


def test_zero_input_and_detached_readonly_json():
    source=coupled_norton_reactive_ladder_response(**arguments(source_currents=np.zeros((121,2))))
    w=checks(source,[35.,45.,55.,65.]);assert not np.any(w.incident) and not np.any(w.reflected)
    source=coupled_norton_reactive_ladder_response(**arguments());z=np.array([35.,45.,55.,65.]);w=checks(source,z)
    text=json.dumps(w.to_dict(),sort_keys=True,allow_nan=False);z[:]=99
    for name in ['time','voltage','current','z_ref','incident','reflected','port_power']:
        assert not getattr(w,name).flags.writeable
        assert not np.shares_memory(getattr(w,name),getattr(source,name,np.empty(0)))
    out=w.to_dict();out['voltage_v'][0][0]=99;out['z_ref_ohm'][0]=99
    assert json.dumps(w.to_dict(),sort_keys=True,allow_nan=False)==text


@pytest.mark.parametrize('z',[50.,[50.,50.],[0.,50.,50.,50.],[True,50.,50.,50.],
    [complex(50)]*4,[np.inf]*4,[np.nan]*4])
def test_norton_reference_contract_rejects_ambiguous_or_nonpositive_values(z):
    with pytest.raises(ValueError):startup_port_waves(coupled_norton_reactive_ladder_response(**arguments()),z_ref=z)


def test_malformed_norton_terminal_shape_rejects_instead_of_using_injected_current():
    r=copy(coupled_norton_reactive_ladder_response(**arguments()))
    object.__setattr__(r,'current',r.source_currents)
    with pytest.raises(ValueError,match='shapes'):startup_port_waves(r,z_ref=[35.,45.,55.,65.])
