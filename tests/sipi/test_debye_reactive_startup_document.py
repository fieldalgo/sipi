# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Coupled finite-circuit storage, sample budgets and physical-state replay."""
from dataclasses import replace
import json

import numpy as np
import pytest
from sipi import DebyeReactiveLadderDocument, psd_coupled_debye_reactive_ladder_response
from sipi.execution import execute_saved, normalize_saved, saved_schemas
import sipi.debye_reactive_startup as api
import sipi.debye_reactive_startup_document as module


def arguments(**changes):
    args=dict(time=[0.,1e-9,2e-9],source_voltages=[[0.,0.],[1.,0.],[1.,0.]],
        R=[[20.,3.],[3.,20.]],L=np.array([[500.,100.],[100.,500.]])*1e-9,
        G=[[.002,-.0003],[-.0003,.002]],C_inf=np.array([[220.,-40.],[-40.,220.]])*1e-12,
        delta_C=np.array([[[150.,-150.],[-150.,150.]],[[50.,50.],[50.,50.]]])*1e-12,relaxation_hz=[1e9,1e8],
        length=.1,cells=8,source_resistance=[25.,25.],load_resistance=[100.,100.],
        load_capacitance=np.array([[30.,-5.],[-5.,30.]])*1e-12,
        load_branch_resistance=np.array([[150.,20.],[20.,150.]]),
        load_branch_inductance=np.array([[200.,30.],[30.,200.]])*1e-9)
    args.update(changes);return args


def document(**changes):return DebyeReactiveLadderDocument(**arguments(**changes))


def forbidden(*args,**kwargs):pytest.fail('validation or budget reached propagation')


def test_canonical_registry_and_nested_copies_without_propagation(monkeypatch):
    monkeypatch.setattr(api,'lsim',forbidden);monkeypatch.setattr(module,'psd_coupled_debye_reactive_ladder_response',forbidden)
    args=arguments();d=DebyeReactiveLadderDocument(**args);text=d.dumps()
    assert normalize_saved(text)==text and DebyeReactiveLadderDocument.loads(text).dumps()==text
    assert 'sipi.debye-reactive-startup/1' in saved_schemas() and d.samples==3
    args['L'][:]=9;args['source_voltages'][1][0]=99;args['source_resistance'][0]=99
    data=d.to_dict();data['R_ohm_per_m'][0][1]=999;data['time_s'].clear()
    assert d.dumps()==text


@pytest.mark.parametrize('mutate',[
    lambda d:d.update(schema='sipi.debye-reactive-startup/999'),lambda d:d.update(schema='sipi.rlgc-startup/1'),
    lambda d:d.update(extra=1),lambda d:d.pop('load_resistance_ohm'),lambda d:d.pop('cells'),
    lambda d:d.update(time_s=[]),lambda d:d.update(time_s=[0.]),lambda d:d.update(time_s=[1.,2.,3.]),
    lambda d:d.update(time_s=[0.,0.,1.]),lambda d:d.update(time_s=[0.,1.,3.]),
    lambda d:d.update(time_s=[0.,True,2.]),lambda d:d.update(time_s=[[0.,1.,2.]]),
    lambda d:d.update(source_voltages_v=[0.,1.,1.]),
    lambda d:d.update(source_voltages_v=[[1.,0.],[1.,0.],[1.,0.]]),
    lambda d:d.update(source_voltages_v=[[0.,0.],[True,0.],[1.,0.]]),
    lambda d:d.update(R_ohm_per_m=-1),lambda d:d.update(R_ohm_per_m=[[True,0],[0,1]]),
    lambda d:d.update(R_ohm_per_m=[[1,0],[0,-1e-30]]),lambda d:d.update(R_ohm_per_m=[[1,1e-15],[0,1]]),
    lambda d:d.update(L_h_per_m=[[1.,0.],[0.,1e-14]]),lambda d:d.update(C_inf_f_per_m=[[0,0],[0,0]]),
    lambda d:d.update(G_s_per_m=[[[0,0],[0,0]]]),lambda d:d.update(length_m=0),
    lambda d:d.update(cells=0),lambda d:d.update(cells=129),lambda d:d.update(cells=True),lambda d:d.update(cells=8.),
    lambda d:d.update(source_resistance_ohm=25.),lambda d:d.update(source_resistance_ohm=[0.,25.]),
    lambda d:d.update(load_resistance_ohm=None),lambda d:d.update(load_resistance_ohm=[100.,0.]),
    lambda d:d.update(load_resistance_ohm=[True,100.]),
    lambda d:d.update(time_s=np.linspace(0.,1.,10001).tolist(),source_voltages_v=[[0.,0.]]*10001),
])
def test_strict_matrix_and_waveform_inputs_reject_without_propagation(mutate,monkeypatch):
    data=document().to_dict();mutate(data);monkeypatch.setattr(api,'lsim',forbidden)
    with pytest.raises((ValueError,TypeError)):DebyeReactiveLadderDocument.from_dict(data)
    with pytest.raises((ValueError,TypeError)):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('text',['{"schema":"x","schema":"y"}',
    '{"schema":"sipi.debye-reactive-startup/1","time_s":[NaN]}',
    '{"schema":"sipi.debye-reactive-startup/1","R_ohm_per_m":[[1e999,0],[0,1]]}',
    '[]','null'])
def test_duplicate_nonfinite_and_nonobject_reject(text):
    with pytest.raises(ValueError):DebyeReactiveLadderDocument.loads(text)
    with pytest.raises(ValueError):normalize_saved(text)


def test_actual_sample_budget_is_independent_of_cells_and_conductor_count(monkeypatch):
    d=document(cells=128);original=module.psd_coupled_debye_reactive_ladder_response;observed=[]
    def spy(**kw):observed.append((len(kw['time']),kw['cells'],np.shape(kw['source_voltages'])));return original(**kw)
    monkeypatch.setattr(module,'psd_coupled_debye_reactive_ladder_response',spy)
    out=execute_saved(d.dumps(),max_evaluations=3)
    assert observed==[(3,128,(3,2))] and out['input']['cells']==128
    assert out['status']=='complete' and not out['result']['states_included'] and 'node_voltage_v' not in out['result']
    monkeypatch.setattr(module,'psd_coupled_debye_reactive_ladder_response',forbidden)
    for d in [d,document(cells=1)]:
        with pytest.raises(ValueError,match='max_evaluations'):d.analyze(max_evaluations=2)
        with pytest.raises(ValueError,match='max_evaluations'):execute_saved(d.dumps(),max_evaluations=2)


def test_byte_diagnostic_budget_controls_before_propagation(monkeypatch):
    d=document();monkeypatch.setattr(module,'psd_coupled_debye_reactive_ladder_response',forbidden)
    with pytest.raises(ValueError,match='max_input_bytes'):execute_saved(d.dumps(),max_input_bytes=2)
    with pytest.raises(ValueError,match='diagnostics'):execute_saved(d.dumps(),diagnostics=['modes'])
    for budget in [True,1,10001,3.]:
        with pytest.raises((ValueError,TypeError)):d.analyze(max_evaluations=budget)


@pytest.mark.parametrize('kind',['exchange','asymmetric','decoupled'])
@pytest.mark.parametrize('pulse',[False,True])
def test_saved_direct_and_common_replay_full_physical_states(kind,pulse):
    t=np.linspace(0,12e-9,121)
    a=np.interp(t,[0,2e-9,4e-9,6e-9],[0,1,1,0]) if pulse else np.minimum(t/2e-9,1.)
    b=-.4*np.minimum(t/3e-9,1.);args=arguments(time=t,source_voltages=np.column_stack((a,b)),cells=16)
    if kind=='asymmetric':
        args.update(R=[[25.,2.],[2.,17.]],L=np.array([[510.,70.],[70.,430.]])*1e-9,
            G=[[.003,-.0002],[-.0002,.0015]],C_inf=np.array([[230.,-30.],[-30.,190.]])*1e-12,
            delta_C=np.array([[[80.,-40.],[-40.,20.]],[[32.,32.],[32.,32.]]])*1e-12,
            source_resistance=[23.,37.],load_resistance=[91.,113.],load_capacitance=np.array([[20.,-4.],[-4.,30.]])*1e-12,
            load_branch_resistance=np.array([[140.,17.],[17.,180.]]),load_branch_inductance=np.array([[210.,25.],[25.,170.]])*1e-9)
    elif kind=='decoupled':
        for name in ['R','L','G','C_inf','load_capacitance','load_branch_resistance','load_branch_inductance']:args[name]=np.diag(np.diag(args[name]))
        args['delta_C']=np.array([np.diag([150e-12,0.]),np.diag([0.,50e-12])])
    expected=psd_coupled_debye_reactive_ladder_response(**args);d=DebyeReactiveLadderDocument(**args)
    loaded=DebyeReactiveLadderDocument.loads(d.dumps());actual=loaded.analyze(max_evaluations=121)
    assert actual.to_dict(include_states=True)==expected.to_dict(include_states=True)
    out=execute_saved(loaded.dumps(),max_evaluations=121)
    assert out['status']=='complete' and out['error'] is None and out['result']==expected.to_dict()
    assert out['input']==d.to_dict();json.dumps(out,allow_nan=False)


@pytest.mark.parametrize('change',['inputs','time','drive','node_shape','segment_shape','voltage_shape','current_shape','type'])
def test_solver_result_must_retain_saved_identity(change,monkeypatch):
    d=document();r=d.analyze()
    if change=='inputs':
        data=r.inputs;data['R_ohm_per_m'][0][0]+=1;bad=replace(r,input_json=json.dumps(data))
    elif change=='time':bad=replace(r,time=np.array([0.,1.,2.]))
    elif change=='drive':bad=replace(r,source_voltages=np.ones((3,2)))
    elif change=='node_shape':bad=replace(r,node_voltage=np.zeros((3,8,2)))
    elif change=='segment_shape':bad=replace(r,segment_current=np.zeros((3,9,2)))
    elif change=='voltage_shape':bad=replace(r,voltage=np.zeros((3,2)))
    elif change=='current_shape':bad=replace(r,current=np.zeros((3,2)))
    else:bad=None
    monkeypatch.setattr(module,'psd_coupled_debye_reactive_ladder_response',lambda **kw:bad)
    with pytest.raises(ValueError,match='changed saved'):d.analyze()


def test_runtime_unrepresentable_cell_failure_is_not_partial_success():
    d=document(L=np.eye(2)*1e-300,C_inf=np.eye(2)*1e-300,length=1e-300)
    assert normalize_saved(d.dumps())==d.dumps()
    with pytest.raises(ValueError,match='finite scales'):d.analyze()
    with pytest.raises(ValueError,match='finite scales'):execute_saved(d.dumps())


@pytest.mark.parametrize('key',['schema',*module._NAMES])
def test_all_sixteen_keys_required(key,monkeypatch):
    data=document().to_dict();data.pop(key);monkeypatch.setattr(api,'lsim',forbidden)
    with pytest.raises(ValueError):DebyeReactiveLadderDocument.from_dict(data)


@pytest.mark.parametrize('mutate',[
    lambda d:d.update(schema='sipi.debye-rlgc-startup/1'),
    lambda d:d.update(delta_C_f_per_m=[1e-12,2e-12]),
    lambda d:d.update(delta_C_f_per_m=[]),lambda d:d.update(delta_C_f_per_m=[[[1.,0.],[0.,1.]]]*3,relaxation_hz=[1e9]*3),
    lambda d:d.update(delta_C_f_per_m=[[[True,False],[False,True]]],relaxation_hz=[1e9]),
    lambda d:d.update(delta_C_f_per_m=[[[1.,2.],[2.,1.]]],relaxation_hz=[1e9]),
    lambda d:d.update(delta_C_f_per_m=[[[1.,0.],[0.,-1e-13]]],relaxation_hz=[1e9]),
    lambda d:d.update(delta_C_f_per_m=[[[1.,1.],[0.,1.]]],relaxation_hz=[1e9]),
    lambda d:d.update(delta_C_f_per_m=[[[1.,0.],[0.,-1e-20]]],relaxation_hz=[1e9]),
    lambda d:d.update(relaxation_hz=[0.,1e8]),lambda d:d.update(relaxation_hz=[True,1e8]),
    lambda d:d.update(relaxation_hz=[1e9]),lambda d:d.update(relaxation_hz=[[1e9,1e8]]),
    lambda d:d.update(delta_C=[1.,2.]),lambda d:d.update(C_f_per_m=d['C_inf_f_per_m']),
])
def test_explicit_matrix_poles_units_and_limits(mutate,monkeypatch):
    data=document().to_dict();mutate(data);monkeypatch.setattr(api,'lsim',forbidden)
    with pytest.raises((ValueError,TypeError)):DebyeReactiveLadderDocument.from_dict(data)
    with pytest.raises((ValueError,TypeError)):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('kind',['one','zero','one-zero','repeat','reversed'])
def test_declared_poles_zero_and_order_replay(kind):
    a=arguments();delta=a['delta_C'];poles=np.array(a['relaxation_hz'])
    if kind=='one':delta=delta[:1];poles=poles[:1]
    elif kind=='zero':delta=np.zeros_like(delta)
    elif kind=='one-zero':delta=delta.copy();delta[0]=0
    elif kind=='repeat':poles[:]=1e9
    else:delta=delta[::-1];poles=poles[::-1]
    a.update(delta_C=delta,relaxation_hz=poles);expected=psd_coupled_debye_reactive_ladder_response(**a);d=DebyeReactiveLadderDocument(**a)
    actual=DebyeReactiveLadderDocument.loads(d.dumps()).analyze(max_evaluations=3)
    assert actual.to_dict(include_states=True)==expected.to_dict(include_states=True)
    assert actual.inputs['delta_C_f_per_m']==delta.tolist() and actual.inputs['relaxation_hz']==poles.tolist()
    assert execute_saved(d.dumps(),max_evaluations=3)['result']==expected.to_dict()
    for p,m in enumerate(delta):
        if not np.any(m):assert not np.any(actual.polarization_charge[:,:,p])


@pytest.mark.parametrize('field',['polarization_voltage','polarization_charge','polarization_current','energy','energy_rate',
    'polarization_energy','polarization_energy_rate','relaxation_loss','series_loss','shunt_loss','line_power',
    'source_power','source_resistor_loss','load_resistor_loss'])
def test_all_polarization_and_diagnostic_shapes_guarded(field,monkeypatch):
    d=document();r=d.analyze();bad=replace(r,**{field:np.zeros((3,1))})
    monkeypatch.setattr(module,'psd_coupled_debye_reactive_ladder_response',lambda **kwargs:bad)
    with pytest.raises(ValueError,match='changed saved'):d.analyze()


@pytest.mark.parametrize('version',[1,2,3,4,5,6,7])
def test_existing_saved_waves_reject_coupled_debye(version):
    from sipi import StartupPortWavesDocument
    d=document()
    with pytest.raises(ValueError):StartupPortWavesDocument(d,z_ref=[35.,45.,55.,65.],version=version)
    data=dict(schema=f'sipi.startup-port-waves/{version}',startup=d.to_dict(),z_ref_ohm=[35.,45.,55.,65.])
    with pytest.raises(ValueError):normalize_saved(json.dumps(data))


def test_original_scalar_document_rejects_matrix_kind():
    from sipi import DebyeRLGCLadderDocument
    with pytest.raises(ValueError):DebyeRLGCLadderDocument.from_dict(document().to_dict())


def test_strength_and_frequency_inputs_are_detached(monkeypatch):
    a=arguments();a['relaxation_hz']=np.array(a['relaxation_hz']);d=DebyeReactiveLadderDocument(**a);text=d.dumps()
    a['delta_C'][:]=0;a['relaxation_hz'][:]=1;out=d.to_dict();out['delta_C_f_per_m'][0][0][0]=9
    assert d.dumps()==text;monkeypatch.setattr(api,'lsim',forbidden);assert normalize_saved(text)==text


def test_original_runtime_exception_retained(monkeypatch):
    d=document()
    def fail(**kwargs):raise RuntimeError('coupled Debye integration failed')
    monkeypatch.setattr(module,'psd_coupled_debye_reactive_ladder_response',fail)
    with pytest.raises(RuntimeError,match='coupled Debye'):d.analyze()
    with pytest.raises(RuntimeError,match='coupled Debye'):execute_saved(d.dumps())


@pytest.mark.parametrize('tiny',[0.,1e-13,1e-20])
def test_near_singular_strength_preserved_without_rank_threshold(tiny):
    delta=np.array([np.diag([150e-12,150e-12*tiny])]);a=arguments(delta_C=delta,relaxation_hz=[1e9]);d=DebyeReactiveLadderDocument(**a)
    expected=psd_coupled_debye_reactive_ladder_response(**a);r=DebyeReactiveLadderDocument.loads(d.dumps()).analyze(max_evaluations=3)
    assert r.inputs['delta_C_f_per_m']==delta.tolist() and r.to_dict(include_states=True)==expected.to_dict(include_states=True)


def test_original_psd_and_spd_documents_reject_external_load_kind():
    from sipi import CoupledDebyeRLGCLadderDocument,PSDCoupledDebyeRLGCLadderDocument
    for cls in [CoupledDebyeRLGCLadderDocument,PSDCoupledDebyeRLGCLadderDocument]:
        with pytest.raises(ValueError):cls.from_dict(document().to_dict())


@pytest.mark.parametrize('mutate',[
    lambda d:d.update(load_capacitance_f=None),lambda d:d.update(load_capacitance_f=1e-12),
    lambda d:d.update(load_capacitance_f=np.eye(3).tolist()),
    lambda d:d.update(load_capacitance_f=[[True,0.],[0.,1.]]),
    lambda d:d.update(load_capacitance_f=[[1.,1.],[0.,1.]]),
    lambda d:d.update(load_capacitance_f=[[1.,2.],[2.,1.]]),
    lambda d:d.update(load_capacitance_f=[[1.,0.],[0.,-1e-20]]),
    lambda d:d.update(load_capacitance_f_per_m=d.pop('load_capacitance_f')),
    lambda d:d.update(load_capacitance=d.pop('load_capacitance_f')),
])
def test_external_farad_units_matrix_and_psd_before_propagation(mutate,monkeypatch):
    data=document().to_dict();mutate(data);monkeypatch.setattr(api,'lsim',forbidden)
    with pytest.raises(ValueError):DebyeReactiveLadderDocument.from_dict(data)
    with pytest.raises(ValueError):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('cap',[np.zeros((2,2)),np.array([[30.,-30.],[-30.,30.]])*1e-12,np.array([[20.,-4.],[-4.,30.]])*1e-12])
@pytest.mark.parametrize('pulse',[False,True])
def test_external_capacitance_and_full_diagnostics_replay(cap,pulse):
    t=np.linspace(0,12e-9,121);d=np.minimum(t/2e-9,1.)
    if pulse:d-=np.minimum(np.maximum(t-5e-9,0)/2e-9,1.)
    a=arguments(time=t,source_voltages=d[:,None]*[1.,-.4],load_capacitance=cap)
    expected=psd_coupled_debye_reactive_ladder_response(**a);doc=DebyeReactiveLadderDocument(**a)
    actual=DebyeReactiveLadderDocument.loads(doc.dumps()).analyze(max_evaluations=121)
    assert actual.to_dict(include_states=True)==expected.to_dict(include_states=True)
    assert execute_saved(doc.dumps(),max_evaluations=121)['result']==expected.to_dict()
    assert actual.inputs['load_capacitance_f']==cap.tolist()


@pytest.mark.parametrize('field',['load_capacitor_current','load_capacitor_energy','load_capacitor_power'])
def test_external_capacitor_shapes_guarded(field,monkeypatch):
    doc=document();response=doc.analyze();bad=replace(response,**{field:np.zeros((3,1))})
    monkeypatch.setattr(module,'psd_coupled_debye_reactive_ladder_response',lambda **kw:bad)
    with pytest.raises(ValueError,match='changed saved'):doc.analyze()


def test_external_capacitance_copied_without_propagation(monkeypatch):
    a=arguments();doc=DebyeReactiveLadderDocument(**a);text=doc.dumps();a['load_capacitance'][:]=9
    out=doc.to_dict();out['load_capacitance_f'][0][0]=9;assert doc.dumps()==text
    monkeypatch.setattr(api,'lsim',forbidden);assert normalize_saved(text)==text


@pytest.mark.parametrize('key,value',[
    ('load_branch_resistance_ohm',None),('load_branch_resistance_ohm',1.),
    ('load_branch_resistance_ohm',[[True,0.],[0.,1.]]),('load_branch_resistance_ohm',[[1.,2.],[2.,1.]]),
    ('load_branch_resistance_ohm',[[1.,0.],[0.,-1e-20]]),('load_branch_resistance_ohm',[[1.,1.],[0.,1.]]),
    ('load_branch_inductance_h',None),('load_branch_inductance_h',1e-9),
    ('load_branch_inductance_h',[[0.,0.],[0.,0.]]),('load_branch_inductance_h',[[1.,1.],[1.,1.]]),
    ('load_branch_inductance_h',np.diag([1.,1e-13]).tolist()),('load_branch_inductance_h',[[1.,1.],[0.,1.]]),
    ('load_branch_inductance_h',[[True,0.],[0.,1.]])])
def test_external_branch_units_and_psd_spd_before_propagation(key,value,monkeypatch):
    data=document().to_dict();data[key]=value;monkeypatch.setattr(api,'lsim',forbidden)
    with pytest.raises(ValueError):DebyeReactiveLadderDocument.from_dict(data)
    with pytest.raises(ValueError):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('key',['load_branch_resistance_ohm','load_branch_inductance_h'])
def test_external_branch_does_not_use_per_length_units(key,monkeypatch):
    data=document().to_dict();data[key+'_per_m']=data.pop(key);monkeypatch.setattr(api,'lsim',forbidden)
    with pytest.raises(ValueError):DebyeReactiveLadderDocument.from_dict(data)


@pytest.mark.parametrize('field',['load_branch_current','load_branch_energy','load_branch_energy_rate','load_branch_resistor_loss'])
def test_branch_state_and_diagnostic_shapes_guarded(field,monkeypatch):
    d=document();r=d.analyze();bad=replace(r,**{field:np.zeros((3,1))})
    monkeypatch.setattr(module,'psd_coupled_debye_reactive_ladder_response',lambda **kwargs:bad)
    with pytest.raises(ValueError,match='changed saved'):d.analyze()


@pytest.mark.parametrize('rb',[np.zeros((2,2)),np.array([[150.,-150.],[-150.,150.]]),np.array([[150.,20.],[20.,150.]])])
@pytest.mark.parametrize('pulse',[False,True])
def test_branch_zero_rankone_full_resistance_and_energy_replay(rb,pulse):
    t=np.linspace(0,12e-9,121);d=np.minimum(t/2e-9,1.)
    if pulse:d-=np.minimum(np.maximum(t-5e-9,0)/2e-9,1.)
    a=arguments(time=t,source_voltages=d[:,None]*[1.,-.4],load_branch_resistance=rb)
    expected=psd_coupled_debye_reactive_ladder_response(**a);doc=DebyeReactiveLadderDocument(**a)
    actual=DebyeReactiveLadderDocument.loads(doc.dumps()).analyze(max_evaluations=121)
    assert actual.to_dict(include_states=True)==expected.to_dict(include_states=True)
    assert execute_saved(doc.dumps(),max_evaluations=121)['result']==expected.to_dict()
    assert actual.inputs['load_branch_resistance_ohm']==rb.tolist()


def test_branch_inputs_detached_and_capacitive_document_rejects_kind(monkeypatch):
    from sipi import DebyeCapacitiveLadderDocument
    a=arguments();doc=DebyeReactiveLadderDocument(**a);text=doc.dumps()
    a['load_branch_resistance'][:]=0;a['load_branch_inductance'][:]=9
    assert doc.dumps()==text;monkeypatch.setattr(api,'lsim',forbidden)
    assert normalize_saved(text)==text
    with pytest.raises(ValueError):DebyeCapacitiveLadderDocument.from_dict(doc.to_dict())
