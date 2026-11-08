# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit six/eight-port waves: independent modes, Z-to-S and line power."""
from dataclasses import fields, replace
import importlib.metadata as metadata
import json
import numpy as np
import pytest
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import psd_multiconductor_debye_norton_reactive_ladder_response, coupled_norton_reactive_ladder_response, startup_port_waves, psd_multiconductor_debye_reactive_ladder_response as voltage_response
from sipi.rlgc_startup import RLGCLadderResponse
from test_multiconductor_debye_norton_startup import modal_data
from test_multiconductor_debye_norton_startup_document import arguments as saved_arguments


def arguments(signals=3,kind='coupled',pulse=False):
    a=saved_arguments(signals,kind,pulse)
    if kind=='coupled':
        j=np.arange(signals);off=np.eye(signals,k=1)+np.eye(signals,k=-1)
        a.update(R=np.diag(20.+3*j)+2*off,L=(np.diag(450.+20*j)+60*off)*1e-9,
            G=np.diag(.002+.0002*j)-.0002*off,C_inf=(np.diag(210.+10*j)-20*off)*1e-12,
            source_shunt_conductance=np.array([0.,.02,0.,.01])[:signals],load_resistance=91.+11*j)
    return a


def checks(r,z=None):
    signals=r.inputs['signals'];z=np.linspace(35.,85.,2*signals) if z is None else z
    w=startup_port_waves(r,z_ref=z)
    assert w.source_kind=='NortonMulticonductorDebyeReactiveLadderResponse' and w.port_names==r.port_names
    for name in ['time','voltage','current']:np.testing.assert_array_equal(getattr(w,name),getattr(r,name))
    root=np.sqrt(w.z_ref);power=w.incident**2-w.reflected**2
    np.testing.assert_allclose(root*(w.incident+w.reflected),r.voltage,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose((w.incident-w.reflected)/root,r.current,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(power,r.voltage*r.current,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(power[:,:signals].sum(axis=1),r.source_power-r.source_shunt_resistor_loss,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(power[:,signals:].sum(axis=1),-r.load_resistor_loss-r.load_capacitor_power-r.load_branch_energy_rate-r.load_branch_resistor_loss,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(power.sum(axis=1),r.line_energy_rate+r.series_loss+r.shunt_loss+r.relaxation_loss,rtol=1e-10,atol=1e-12)
    assert max(w.voltage_reconstruction_relative_error,w.current_reconstruction_relative_error,w.power_balance_relative_error)<=1e-10
    return w


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('kind',['coupled','diagonal','lossless'])
@pytest.mark.parametrize('pulse',[False,True])
def test_twelve_terminal_power_and_reference_invariance_cases(signals,kind,pulse):
    r=psd_multiconductor_debye_norton_reactive_ladder_response(**arguments(signals,kind,pulse));w=checks(r)
    changed=checks(r,2*w.z_ref);np.testing.assert_array_equal(changed.port_power,w.port_power)
    if pulse:assert np.any(r.load_capacitor_power<0)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('pulse',[False,True])
@pytest.mark.parametrize('zero_cap',[False,True])
@pytest.mark.parametrize('gs',[0.,.02])
def test_zero_strength_padded_constant_norton_modal_waves(signals,pulse,zero_cap,gs):
    a=saved_arguments(signals,'coupled',pulse);q,diags,delta,cl,rb,lb,mats=modal_data(signals)
    a['delta_C']=np.zeros_like(a['delta_C']);a['source_shunt_conductance']=[gs]*signals
    if zero_cap:cl=np.zeros(signals);a['load_capacitance']=np.zeros((signals,signals))
    w=checks(psd_multiconductor_debye_norton_reactive_ladder_response(**a),[35.]*signals+[75.]*signals);parts=[]
    for mode in range(signals):
        # Zero-strength limit uses the existing constant two-signal Norton
        # circuit, with one active modal channel and one unexcited dummy.
        drive=np.c_[(a['source_currents']@q)[:,mode],np.zeros(len(a['time']))]
        matrices={key:np.diag([value[mode],dummy]) for key,value,dummy in
            [(key,value,dict(R=0.,L=1e-9,G=0.,C_inf=1e-12)[key]) for key,value in diags.items()]}
        matrices['C']=matrices.pop('C_inf')
        r=coupled_norton_reactive_ladder_response(a['time'],drive,**matrices,
            length=a['length'],cells=a['cells'],
            source_shunt_resistance=[None if gs==0 else 1/gs,1.],load_resistance=[100.,100.],
            load_capacitance=np.diag([cl[mode],0.]),load_branch_resistance=np.diag([rb[mode],1.]),
            load_branch_inductance=np.diag([lb[mode],1e-9]))
        parts.append(startup_port_waves(r,z_ref=[35.,35.,75.,75.]))
    for name in ['incident','reflected']:
        modal=np.stack([getattr(x,name)[:,[0,2]] for x in parts],axis=2)@q.T
        expected=np.concatenate((modal[:,0],modal[:,1]),axis=1)
        np.testing.assert_allclose(getattr(w,name),expected,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(w.port_power.sum(axis=1),sum(x.port_power.sum(axis=1) for x in parts),rtol=1e-10,atol=1e-12)


@pytest.mark.parametrize('signals',[3,4])
def test_independent_skrf_six_eight_port_real_reference_phasors(signals):
    require_tool('scikit-rf');from skrf.network import z2s
    ports=2*signals;clock=Stopwatch();t=np.linspace(0,8e-9,801);freq=500e6;reference=np.linspace(35.,85.,ports)
    impedance=np.diag(np.linspace(50.,90.,ports))+5.*np.ones((ports,ports))
    impedance=impedance+1j*(np.diag(np.linspace(20.,40.,ports))+3.*np.ones((ports,ports)))
    incident=np.linspace(.2,.5,ports)+1j*np.linspace(-.3,.1,ports)
    with clock('reference'):
        scattering=z2s(impedance[None,:,:],z0=reference,s_def='power')[0]
        outgoing=scattering@incident
        current=np.linalg.solve(impedance+np.diag(reference),2*np.sqrt(reference)*incident)
        voltage=impedance@current;phase=np.exp(2j*np.pi*freq*t)[:,None]
        v=np.real(phase*voltage);i=np.real(phase*current)
        expected_a=np.real(phase*incident);expected_b=np.real(phase*outgoing)
    # Explicit terminal-sample fixture; not a propagated line or startup solution.
    original=psd_multiconductor_debye_norton_reactive_ladder_response(**arguments(signals))
    source=replace(original,time=t,voltage=v,current=i)
    with clock('openphysics'):actual=startup_port_waves(source,z_ref=reference)
    error=float(max(np.max(abs(actual.incident-expected_a)),np.max(abs(actual.reflected-expected_b))))
    record=make_record(case=f'sipi-multiconductor-debye-norton-startup-waves-{ports}-port',physics='real-reference port power-wave conversion',
        api='sipi.startup_port_waves',discretization='explicit real V/I terminal samples;constant real diagonal reference',
        tool='scikit-rf',tool_discretization='power-wave Z-to-S and independent V=ZI current solve',
        matched=['500MHz phasors,positive real references,same into-port current convention'],
        not_matched=['synthetic impedance fixture is not a propagated line or startup solution'],
        observables=[observable('incident/reflected wave','sqrt(W)','maximum absolute error',error,1e-10)],
        analytical_acceptance='zero-strength padded constant Norton modal reconstruction and terminal power identities',stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    assert error<=1e-10


@pytest.mark.parametrize('signals',[3,4])
def test_conductor_permutation_preserves_paired_ports_and_references(signals):
    a=arguments(signals);w=checks(psd_multiconductor_debye_norton_reactive_ladder_response(**a));p=np.arange(signals)[::-1]
    for key in ['R','L','G','C_inf','load_capacitance','load_branch_resistance','load_branch_inductance']:a[key]=a[key][np.ix_(p,p)]
    a['delta_C']=a['delta_C'][:,p][:,:,p]
    a['source_currents']=a['source_currents'][:,p]
    a['source_shunt_conductance']=np.asarray(a['source_shunt_conductance'])[p];a['load_resistance']=np.asarray(a['load_resistance'])[p]
    order=np.r_[p,signals+p];other=checks(psd_multiconductor_debye_norton_reactive_ladder_response(**a),w.z_ref[order])
    for name in ['incident','reflected','port_power']:np.testing.assert_allclose(getattr(other,name),getattr(w,name)[:,order],rtol=1e-10,atol=1e-12)


@pytest.mark.parametrize('signals',[3,4])
def test_zero_detached_readonly_finite_json(signals):
    a=arguments(signals);a['source_currents'][:]=0;w=checks(psd_multiconductor_debye_norton_reactive_ladder_response(**a))
    assert not np.any(w.incident) and not np.any(w.reflected)
    r=psd_multiconductor_debye_norton_reactive_ladder_response(**arguments(signals));z=np.linspace(35.,85.,2*signals);w=checks(r,z)
    before=json.dumps(w.to_dict(),sort_keys=True,allow_nan=False);z[:]=9
    for name in ['time','voltage','current','z_ref','incident','reflected','port_power']:
        assert not getattr(w,name).flags.writeable
        assert not np.shares_memory(getattr(w,name),getattr(r,name,np.empty(0)))
    out=w.to_dict();out['port_power_w'][0][0]=9;assert json.dumps(w.to_dict(),sort_keys=True,allow_nan=False)==before


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('kind',['scalar','two','four','wrongcount','zero','negative','boolean','inf','complex','matrix'])
def test_only_explicit_positive_real_six_eight_references(signals,kind):
    z=[50.]*(2*signals)
    if kind=='scalar':z=50.
    elif kind=='two':z=[50.]*2
    elif kind=='four':z=[50.]*4
    elif kind=='wrongcount':z=z[:-1]
    elif kind=='matrix':z=np.diag(z)
    else:z[0]={'zero':0.,'negative':-1.,'boolean':True,'inf':np.inf,'complex':50.+0j}[kind]
    with pytest.raises(ValueError):startup_port_waves(psd_multiconductor_debye_norton_reactive_ladder_response(**arguments(signals)),z_ref=z)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('replacement',['source','node','segment','two-terminal'])
def test_internal_arrays_do_not_replace_terminal_current(signals,replacement):
    r=psd_multiconductor_debye_norton_reactive_ladder_response(**arguments(signals))
    value={'source':r.source_currents,'node':r.node_voltage,'segment':r.segment_current,'two-terminal':r.current[:,:2]}[replacement]
    with pytest.raises(ValueError,match='shapes'):startup_port_waves(replace(r,current=value),z_ref=[50.]*(2*signals))


@pytest.mark.parametrize('signals',[3,4])
def test_old_response_types_do_not_silently_admit_six_eight_ports(signals):
    a=arguments(signals);drive=a.pop('source_currents');a.pop('source_shunt_conductance')
    original=voltage_response(**a,source_voltages=drive/.02,source_resistance=[50.]*signals);names=original.port_names
    class ExtendedOldResponse(RLGCLadderResponse):
        @property
        def port_names(self):return names
    spoof=ExtendedOldResponse(**{field.name:getattr(original,field.name) for field in fields(RLGCLadderResponse)})
    with pytest.raises(ValueError,match='shapes'):startup_port_waves(spoof,z_ref=[50.]*(2*signals))


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('bad_signals',[1,2,5])
def test_multiconductor_does_not_admit_other_port_counts(signals,bad_signals):
    r=psd_multiconductor_debye_norton_reactive_ladder_response(**arguments(signals));data=r.inputs;data['signals']=bad_signals
    r=replace(r,input_json=json.dumps(data),voltage=np.zeros((121,2*bad_signals)),current=np.zeros((121,2*bad_signals)))
    with pytest.raises(ValueError,match='shapes'):startup_port_waves(r,z_ref=[50.]*(2*bad_signals))


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('reference',[1e-320,1e300])
def test_nonrepresentable_wave_scales_are_rejected(signals,reference):
    r=psd_multiconductor_debye_norton_reactive_ladder_response(**arguments(signals))
    with pytest.raises(ValueError,match='finite scales|reconstruction'):startup_port_waves(r,z_ref=[reference]*(2*signals))


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('pole_case',['one','first-zero','all-zero','reordered'])
def test_declared_poles_terminal_power_and_no_repropagation(signals,pole_case,monkeypatch):
    a=arguments(signals);delta=a['delta_C'].copy();poles=a['relaxation_hz'].copy()
    if pole_case=='one':delta=delta[:1];poles=poles[:1]
    elif pole_case=='first-zero':delta[0]=0
    elif pole_case=='all-zero':delta[:]=0
    else:delta=delta[::-1];poles=poles[::-1]
    a.update(delta_C=delta,relaxation_hz=poles);response=psd_multiconductor_debye_norton_reactive_ladder_response(**a)
    import sipi.multiconductor_debye_norton_startup as api
    def forbidden(*a,**kw):pytest.fail('wave conversion propagated the circuit again')
    monkeypatch.setattr(api,'lsim',forbidden);checks(response)


@pytest.mark.parametrize('signals',[3,4])
def test_pole_order_preserves_waves_exact_terminal_reference_contract(signals):
    a=arguments(signals);w=checks(psd_multiconductor_debye_norton_reactive_ladder_response(**a))
    a['delta_C']=a['delta_C'][::-1];a['relaxation_hz']=a['relaxation_hz'][::-1]
    other=checks(psd_multiconductor_debye_norton_reactive_ladder_response(**a),w.z_ref)
    for name in ['incident','reflected','port_power']:
        np.testing.assert_allclose(getattr(w,name),getattr(other,name),rtol=1e-10,atol=1e-12)


@pytest.mark.parametrize('signals',[3,4])
def test_null_only_polarization_preserves_external_branch_wave_power(signals):
    a=arguments(signals);a['source_currents'][:,:-1]=0
    a.update(R=np.eye(signals)*20,L=np.eye(signals)*450e-9,G=np.eye(signals)*.002,
        C_inf=np.eye(signals)*210e-12,delta_C=np.array([np.diag([150e-12]+[0.]*(signals-1))]),relaxation_hz=[8e7],
        load_capacitance=np.eye(signals)*30e-12,load_branch_resistance=np.eye(signals)*30.,load_branch_inductance=np.eye(signals)*180e-9)
    r=psd_multiconductor_debye_norton_reactive_ladder_response(**a);checks(r)
    assert np.any(r.polarization_voltage[:,:,:,-1])
    assert not np.any(r.polarization_charge) and not np.any(r.relaxation_loss) and not np.any(r.polarization_energy)
    assert np.any(r.load_branch_energy) and np.any(r.load_capacitor_energy)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('tiny',[0.,1e-13,1e-20])
def test_nearzero_declared_strengths_preserve_wave_power(signals,tiny):
    a=arguments(signals);a.update(delta_C=np.array([np.diag([150e-12]+[150e-12*tiny]*(signals-1))]),relaxation_hz=[8e7])
    r=psd_multiconductor_debye_norton_reactive_ladder_response(**a);checks(r)
    assert r.inputs['delta_C_f_per_m']==a['delta_C'].tolist()


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('kind',['rankone','near13','near20'])
def test_rankone_and_nearzero_external_capacitance_wave_power(signals,kind):
    a=arguments(signals,pulse=True);cap=np.zeros((signals,signals))
    if kind=='rankone':cap[:2,:2]=np.array([[30.,-30.],[-30.,30.]])*1e-12
    else:cap=np.diag([30e-12]+[30e-12*10**(-int(kind[4:]))]*(signals-1))
    a['load_capacitance']=cap;r=psd_multiconductor_debye_norton_reactive_ladder_response(**a);checks(r)
    assert r.inputs['load_capacitance_f']==cap.tolist() and np.any(r.load_capacitor_power<0)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('kind',['zero','rankone','near13','near20'])
def test_zero_rankone_nearzero_branch_resistance_wave_power(signals,kind):
    a=arguments(signals,pulse=True);rb=np.zeros((signals,signals))
    if kind=='rankone':rb[:2,:2]=[[30.,-30.],[-30.,30.]]
    elif kind.startswith('near'):rb=np.diag([30.]+[30.*10**(-int(kind[4:]))]*(signals-1))
    a['load_branch_resistance']=rb;r=psd_multiconductor_debye_norton_reactive_ladder_response(**a);checks(r)
    assert r.inputs['load_branch_resistance_ohm']==rb.tolist()
    if kind=='zero':assert not np.any(r.load_branch_resistor_loss)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('kind',['ideal','mixed','positive','near13','near20'])
@pytest.mark.parametrize('pulse',[False,True])
def test_source_shunt_loss_excluded_from_terminal_wave_power(signals,kind,pulse):
    a=arguments(signals,pulse=pulse);gs=np.zeros(signals)
    if kind=='mixed':gs[1]=.02
    elif kind=='positive':gs[:]=.02
    elif kind.startswith('near'):gs[:]=.02*10**(-int(kind[4:]));gs[0]=.02
    a['source_shunt_conductance']=gs;r=psd_multiconductor_debye_norton_reactive_ladder_response(**a);w=checks(r)
    np.testing.assert_allclose(w.current[:,:signals],r.source_currents-r.voltage[:,:signals]*gs,rtol=1e-13,atol=1e-15)
    np.testing.assert_allclose(w.port_power[:,:signals].sum(axis=1),r.source_power-r.source_shunt_resistor_loss,rtol=1e-10,atol=1e-12)
    if kind=='ideal':np.testing.assert_array_equal(w.current[:,:signals],r.source_currents)
    else:assert np.any(w.current[:,:signals]!=r.source_currents)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('pulse',[False,True])
def test_positive_conductance_debye_thevenin_terminal_waves(signals,pulse):
    a=arguments(signals,pulse=pulse);gs=np.array([.04,.02,.01,.03])[:signals];a['source_shunt_conductance']=gs
    r=psd_multiconductor_debye_norton_reactive_ladder_response(**a);w=checks(r)
    old=dict(a);drive=old.pop('source_currents');old.pop('source_shunt_conductance')
    ref=voltage_response(**old,source_voltages=drive/gs,source_resistance=1/gs)
    expected=startup_port_waves(ref,z_ref=w.z_ref)
    for name in ['incident','reflected','port_power']:
        np.testing.assert_allclose(getattr(w,name),getattr(expected,name),rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(r.source_power-r.source_shunt_resistor_loss,ref.source_power-ref.source_resistor_loss,rtol=1e-10,atol=1e-12)
