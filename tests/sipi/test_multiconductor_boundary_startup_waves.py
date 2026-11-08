# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit six/eight-port waves: independent modes, Z-to-S and line power."""
from dataclasses import fields, replace
import importlib.metadata as metadata
import json
import numpy as np
import pytest
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import multiconductor_boundary_ladder_response, rlgc_ladder_response, startup_port_waves
from sipi.rlgc_startup import RLGCLadderResponse
from test_multiconductor_startup import modal_data
from test_multiconductor_startup_document import arguments as positive_arguments
from test_multiconductor_boundary_startup_document import arguments as saved_arguments


def arguments(signals=3,kind='coupled',pulse=False):
    return saved_arguments(signals,kind,pulse)


def checks(r,z=None):
    signals=r.inputs['signals'];z=np.linspace(35.,85.,2*signals) if z is None else z
    w=startup_port_waves(r,z_ref=z)
    assert w.source_kind=='MixedBoundaryMulticonductorRLGCLadderResponse' and w.port_names==r.port_names
    for name in ['time','voltage','current']:np.testing.assert_array_equal(getattr(w,name),getattr(r,name))
    root=np.sqrt(w.z_ref);power=w.incident**2-w.reflected**2
    np.testing.assert_allclose(root*(w.incident+w.reflected),r.voltage,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose((w.incident-w.reflected)/root,r.current,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(power,r.voltage*r.current,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(power[:,:signals].sum(axis=1),r.source_power-r.source_resistor_loss,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(power[:,signals:].sum(axis=1),-r.load_resistor_loss,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(power.sum(axis=1),r.energy_rate+r.series_loss+r.shunt_loss,rtol=1e-10,atol=1e-12)
    assert max(w.voltage_reconstruction_relative_error,w.current_reconstruction_relative_error,w.power_balance_relative_error)<=1e-10
    return w


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('kind',['coupled','diagonal','lossless'])
@pytest.mark.parametrize('pulse',[False,True])
def test_twelve_terminal_power_and_reference_invariance_cases(signals,kind,pulse):
    r=multiconductor_boundary_ladder_response(**arguments(signals,kind,pulse));w=checks(r)
    changed=checks(r,2*w.z_ref);np.testing.assert_array_equal(changed.port_power,w.port_power)
    assert np.all(w.port_power[:,signals:]<=0)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('pulse',[False,True])
@pytest.mark.parametrize('rs,rl',[(0.,0.),(0.,None),(0.,100.),(25.,0.),(25.,None),(25.,100.)])
def test_independent_scalar_modal_waves_reconstruct_every_terminal(signals,pulse,rs,rl):
    a=positive_arguments(signals,'coupled',pulse);a.update(source_resistance=[rs]*signals,load_resistance=[rl]*signals);q,diags,_=modal_data(signals)
    w=checks(multiconductor_boundary_ladder_response(**a),[35.]*signals+[75.]*signals);parts=[]
    for mode in range(signals):
        r=rlgc_ladder_response(a['time'],(a['source_voltages']@q)[:,mode],
            **{key:value[mode] for key,value in diags.items()},length=a['length'],cells=a['cells'],
            source_resistance=rs,load_resistance=rl)
        parts.append(startup_port_waves(r,z_ref=[35.,75.]))
    for name in ['incident','reflected']:
        modal=np.stack([getattr(x,name) for x in parts],axis=2)@q.T
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
    original=multiconductor_boundary_ladder_response(**arguments(signals))
    source=replace(original,time=t,voltage=v,current=i)
    with clock('openphysics'):actual=startup_port_waves(source,z_ref=reference)
    error=float(max(np.max(abs(actual.incident-expected_a)),np.max(abs(actual.reflected-expected_b))))
    record=make_record(case=f'sipi-multiconductor-boundary-startup-waves-{ports}-port',physics='real-reference port power-wave conversion',
        api='sipi.startup_port_waves',discretization='explicit real V/I terminal samples;constant real diagonal reference',
        tool='scikit-rf',tool_discretization='power-wave Z-to-S and independent V=ZI current solve',
        matched=['500MHz phasors,positive real references,same into-port current convention'],
        not_matched=['synthetic impedance fixture is not a propagated line or startup solution'],
        observables=[observable('incident/reflected wave','sqrt(W)','maximum absolute error',error,1e-10)],
        analytical_acceptance='independent scalar modal reconstruction and terminal power identities',stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    assert error<=1e-10


@pytest.mark.parametrize('signals',[3,4])
def test_conductor_permutation_preserves_paired_ports_and_references(signals):
    a=arguments(signals);w=checks(multiconductor_boundary_ladder_response(**a));p=np.arange(signals)[::-1]
    for key in ['R','L','G','C']:a[key]=a[key][np.ix_(p,p)]
    a['source_voltages']=a['source_voltages'][:,p]
    a['source_resistance']=np.asarray(a['source_resistance'])[p];a['load_resistance']=np.asarray(a['load_resistance'])[p]
    order=np.r_[p,signals+p];other=checks(multiconductor_boundary_ladder_response(**a),w.z_ref[order])
    for name in ['incident','reflected','port_power']:np.testing.assert_allclose(getattr(other,name),getattr(w,name)[:,order],rtol=1e-10,atol=1e-12)


@pytest.mark.parametrize('signals',[3,4])
def test_zero_detached_readonly_finite_json(signals):
    a=arguments(signals);a['source_voltages'][:]=0;w=checks(multiconductor_boundary_ladder_response(**a))
    assert not np.any(w.incident) and not np.any(w.reflected)
    r=multiconductor_boundary_ladder_response(**arguments(signals));z=np.linspace(35.,85.,2*signals);w=checks(r,z)
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
    with pytest.raises(ValueError):startup_port_waves(multiconductor_boundary_ladder_response(**arguments(signals)),z_ref=z)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('replacement',['source','node','segment','two-terminal'])
def test_internal_arrays_do_not_replace_terminal_current(signals,replacement):
    r=multiconductor_boundary_ladder_response(**arguments(signals))
    value={'source':r.source_voltages,'node':r.node_voltage,'segment':r.segment_current,'two-terminal':r.current[:,:2]}[replacement]
    with pytest.raises(ValueError,match='shapes'):startup_port_waves(replace(r,current=value),z_ref=[50.]*(2*signals))


@pytest.mark.parametrize('signals',[3,4])
def test_old_response_types_do_not_silently_admit_six_eight_ports(signals):
    original=multiconductor_boundary_ladder_response(**arguments(signals));names=original.port_names
    class ExtendedOldResponse(RLGCLadderResponse):
        @property
        def port_names(self):return names
    spoof=ExtendedOldResponse(**{field.name:getattr(original,field.name) for field in fields(RLGCLadderResponse)})
    with pytest.raises(ValueError,match='shapes'):startup_port_waves(spoof,z_ref=[50.]*(2*signals))


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('bad_signals',[1,2,5])
def test_multiconductor_does_not_admit_other_port_counts(signals,bad_signals):
    r=multiconductor_boundary_ladder_response(**arguments(signals));data=r.inputs;data['signals']=bad_signals
    r=replace(r,input_json=json.dumps(data),voltage=np.zeros((121,2*bad_signals)),current=np.zeros((121,2*bad_signals)))
    with pytest.raises(ValueError,match='shapes'):startup_port_waves(r,z_ref=[50.]*(2*bad_signals))


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('reference',[1e-320,1e300])
def test_nonrepresentable_wave_scales_are_rejected(signals,reference):
    r=multiconductor_boundary_ladder_response(**arguments(signals))
    with pytest.raises(ValueError,match='finite scales|reconstruction'):startup_port_waves(r,z_ref=[reference]*(2*signals))


@pytest.mark.parametrize('signals',[3,4])
def test_all_boundary_masks_power_and_open_short_wave_relations(signals):
    from itertools import product
    a=arguments(signals);a.update(cells=1,time=np.linspace(0,12e-9,13))
    a['source_voltages']=np.minimum(a['time'][:,None]/2e-9,1.)*np.array([1.,-.4,.2,-.1])[:signals]
    count=0
    for near in product([0.,25.],repeat=signals):
        for far in product([None,0.,100.],repeat=signals):
            r=multiconductor_boundary_ladder_response(**dict(a,source_resistance=near,load_resistance=far));w=checks(r)
            for j,load in enumerate(far):
                if load is None:
                    np.testing.assert_array_equal(w.incident[:,signals+j],w.reflected[:,signals+j])
                    assert not np.any(w.current[:,signals+j]) and not np.any(w.port_power[:,signals+j])
                elif load==0:
                    np.testing.assert_array_equal(w.incident[:,signals+j],-w.reflected[:,signals+j])
                    assert not np.any(w.voltage[:,signals+j]) and not np.any(w.port_power[:,signals+j])
            count+=1
    assert count==6**signals


@pytest.mark.parametrize('signals',[3,4])
def test_prescribed_ramp_includes_mutual_endpoint_displacement_current(signals):
    a=arguments(signals);a.update(cells=1,R=np.zeros((signals,signals)),G=np.zeros((signals,signals)),source_resistance=[0.]*signals,load_resistance=[0.]*signals)
    r=multiconductor_boundary_ladder_response(**a);w=checks(r);t=a['time'];Tr=2e-9;amp=np.array([1.,-.4,.2,-.1])[:signals]
    integ=np.where(t<=Tr,t*t/(2*Tr),t-Tr/2)
    line_i=integ[:,None]*np.linalg.solve(a['L']*a['length'],amp)
    slope=np.where(t<Tr,1/Tr,0.)[:,None]*amp
    near_i=line_i+slope@a['C'].T*a['length']*.5
    np.testing.assert_allclose(w.current[:,:signals],near_i,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(w.current[:,signals:],-line_i,rtol=1e-10,atol=1e-12)
    assert np.any(w.current[0,:signals]) and not np.any(r.segment_current[0])
    root=np.sqrt(w.z_ref[:signals]);expected_a=(a['source_voltages']/root+near_i*root)/2
    expected_b=(a['source_voltages']/root-near_i*root)/2
    np.testing.assert_allclose(w.incident[:,:signals],expected_a,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(w.reflected[:,:signals],expected_b,rtol=1e-10,atol=1e-12)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('tiny',[0.,1e-13,1e-20])
def test_psd_loss_nulls_and_near_values_preserved_in_terminal_waves(signals,tiny):
    a=arguments(signals);a.update(R=np.diag([20.]+[20*tiny]*(signals-1)),G=np.diag([.002]+[.002*tiny]*(signals-1)))
    r=multiconductor_boundary_ladder_response(**a);checks(r)
    assert r.inputs['R_ohm_per_m']==a['R'].tolist() and r.inputs['G_s_per_m']==a['G'].tolist()


@pytest.mark.parametrize('signals',[3,4])
def test_wave_conversion_does_not_repropagate_fixed_boundary_states(signals,monkeypatch):
    import sipi.multiconductor_boundary_startup as api
    r=multiconductor_boundary_ladder_response(**arguments(signals))
    def forbidden(*a,**kw):pytest.fail('wave conversion propagated the circuit again')
    monkeypatch.setattr(api,'lsim',forbidden);checks(r)
