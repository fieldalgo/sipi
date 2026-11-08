# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Coupled finite-circuit storage, sample budgets and physical-state replay."""
from dataclasses import replace
from copy import copy
import json

import numpy as np
import pytest
from sipi import NortonReactiveRLGCLadderDocument, coupled_norton_reactive_ladder_response
from sipi.execution import execute_saved, normalize_saved, saved_schemas
import sipi.coupled_boundary_startup as api
import sipi.norton_startup_document as module


def arguments(**changes):
    args=dict(time=[0.,1e-9,2e-9],source_currents=[[0.,0.],[.02,0.],[.02,0.]],
        R=[[20.,3.],[3.,20.]],L=np.array([[500.,100.],[100.,500.]])*1e-9,
        G=[[.002,-.0003],[-.0003,.002]],C=np.array([[220.,-40.],[-40.,220.]])*1e-12,
        length=.1,cells=8,source_shunt_resistance=[None,37.],load_resistance=[91.,None],load_capacitance=np.array([[20.,-4.],[-4.,30.]])*1e-12,
        load_branch_resistance=np.array([[13.,1.],[1.,9.]]),load_branch_inductance=np.array([[12.,2.],[2.,8.]])*1e-9)
    args.update(changes);return args


def document(**changes):return NortonReactiveRLGCLadderDocument(**arguments(**changes))


def forbidden(*args,**kwargs):pytest.fail('validation or budget reached propagation')


def test_canonical_registry_and_nested_copies_without_propagation(monkeypatch):
    monkeypatch.setattr(api,'lsim',forbidden);monkeypatch.setattr(module,'coupled_norton_reactive_ladder_response',forbidden)
    args=arguments();d=NortonReactiveRLGCLadderDocument(**args);text=d.dumps()
    assert normalize_saved(text)==text and NortonReactiveRLGCLadderDocument.loads(text).dumps()==text
    assert 'sipi.norton-rlgc-startup/1' in saved_schemas() and d.samples==3
    args['load_branch_inductance'][:]=99;args['load_branch_resistance'][:]=99;args['load_capacitance'][:]=99;args['L'][:]=9;args['source_currents'][1][0]=99;args['source_shunt_resistance'][0]=99
    data=d.to_dict();data['R_ohm_per_m'][0][1]=999;data['time_s'].clear()
    assert d.dumps()==text


@pytest.mark.parametrize('mutate',[
    lambda d:d.update(schema='sipi.coupled-rlgc-startup/999'),lambda d:d.update(schema='sipi.rlgc-startup/1'),
    lambda d:d.update(extra=1),lambda d:d.pop('load_branch_resistance_ohm'),lambda d:d.pop('load_branch_inductance_h'),
    lambda d:d.update(load_branch_inductance_h=[[0,0],[0,0]]),
    lambda d:d.update(load_branch_inductance_h=[[1,0],[0,1e-14]]),
    lambda d:d.update(load_branch_inductance_h=[[1,1],[1,1]]),
    lambda d:d.update(load_branch_inductance_h=[[True,0],[0,1]]),
    lambda d:d.update(load_branch_resistance_ohm=[[1,0],[0,-1e-30]]),
    lambda d:d.update(load_branch_resistance_ohm=[[1,1e-15],[0,1]]),
    lambda d:d.update(load_branch_resistance_ohm=[[True,0],[0,1]]),
    lambda d:d.update(load_branch_resistance_ohm=0),lambda d:d.pop('load_capacitance_f'),
    lambda d:d.update(load_capacitance_f=[[1,0],[0,-1e-30]]),
    lambda d:d.update(load_capacitance_f=[[1,1e-15],[0,1]]),
    lambda d:d.update(load_capacitance_f=[[True,0],[0,1]]),
    lambda d:d.update(load_capacitance_f=[[1,0],[0,float('inf')]]),
    lambda d:d.update(load_capacitance_f=0),
    lambda d:d.update(load_capacitance_f=[[[1,0],[0,1]]]),lambda d:d.pop('load_resistance_ohm'),lambda d:d.pop('cells'),
    lambda d:d.update(time_s=[]),lambda d:d.update(time_s=[0.]),lambda d:d.update(time_s=[1.,2.,3.]),
    lambda d:d.update(time_s=[0.,0.,1.]),lambda d:d.update(time_s=[0.,1.,3.]),
    lambda d:d.update(time_s=[0.,True,2.]),lambda d:d.update(time_s=[[0.,1.,2.]]),
    lambda d:d.update(source_currents_a=[0.,1.,1.]),
    lambda d:d.update(source_currents_a=[[1.,0.],[1.,0.],[1.,0.]]),
    lambda d:d.update(source_currents_a=[[0.,0.],[True,0.],[1.,0.]]),
    lambda d:d.update(R_ohm_per_m=-1),lambda d:d.update(R_ohm_per_m=[[True,0],[0,1]]),
    lambda d:d.update(R_ohm_per_m=[[1,0],[0,-1e-30]]),lambda d:d.update(R_ohm_per_m=[[1,1e-15],[0,1]]),
    lambda d:d.update(L_h_per_m=[[1.,0.],[0.,1e-14]]),lambda d:d.update(C_f_per_m=[[0,0],[0,0]]),
    lambda d:d.update(G_s_per_m=[[[0,0],[0,0]]]),lambda d:d.update(length_m=0),
    lambda d:d.update(cells=0),lambda d:d.update(cells=129),lambda d:d.update(cells=True),lambda d:d.update(cells=8.),
    lambda d:d.update(source_shunt_resistance_ohm=25.),lambda d:d.update(source_shunt_resistance_ohm=[-1.,25.]),
    lambda d:d.update(load_resistance_ohm=None),lambda d:d.update(load_resistance_ohm=[100.,-1.]),
    lambda d:d.update(load_resistance_ohm=[True,100.]),
    lambda d:d.update(time_s=np.linspace(0.,1.,10001).tolist(),source_currents_a=[[0.,0.]]*10001),
])
def test_strict_matrix_and_waveform_inputs_reject_without_propagation(mutate,monkeypatch):
    data=document().to_dict();mutate(data);monkeypatch.setattr(api,'lsim',forbidden)
    with pytest.raises((ValueError,TypeError)):NortonReactiveRLGCLadderDocument.from_dict(data)
    with pytest.raises((ValueError,TypeError)):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('text',['{"schema":"x","schema":"y"}',
    '{"schema":"sipi.norton-rlgc-startup/1","time_s":[NaN]}',
    '{"schema":"sipi.norton-rlgc-startup/1","R_ohm_per_m":[[1e999,0],[0,1]]}',
    '[]','null'])
def test_duplicate_nonfinite_and_nonobject_reject(text):
    with pytest.raises(ValueError):NortonReactiveRLGCLadderDocument.loads(text)
    with pytest.raises(ValueError):normalize_saved(text)


def test_actual_sample_budget_is_independent_of_cells_and_conductor_count(monkeypatch):
    d=document(cells=128);original=module.coupled_norton_reactive_ladder_response;observed=[]
    def spy(**kw):observed.append((len(kw['time']),kw['cells'],np.shape(kw['source_currents'])));return original(**kw)
    monkeypatch.setattr(module,'coupled_norton_reactive_ladder_response',spy)
    out=execute_saved(d.dumps(),max_evaluations=3)
    assert observed==[(3,128,(3,2))] and out['input']['cells']==128
    assert out['status']=='complete' and not out['result']['states_included'] and 'node_voltage_v' not in out['result']
    monkeypatch.setattr(module,'coupled_norton_reactive_ladder_response',forbidden)
    for d in [d,document(cells=1)]:
        with pytest.raises(ValueError,match='max_evaluations'):d.analyze(max_evaluations=2)
        with pytest.raises(ValueError,match='max_evaluations'):execute_saved(d.dumps(),max_evaluations=2)


def test_byte_diagnostic_budget_controls_before_propagation(monkeypatch):
    d=document();monkeypatch.setattr(module,'coupled_norton_reactive_ladder_response',forbidden)
    with pytest.raises(ValueError,match='max_input_bytes'):execute_saved(d.dumps(),max_input_bytes=2)
    with pytest.raises(ValueError,match='diagnostics'):execute_saved(d.dumps(),diagnostics=['modes'])
    for budget in [True,1,10001,3.]:
        with pytest.raises((ValueError,TypeError)):d.analyze(max_evaluations=budget)


@pytest.mark.parametrize('kind',['exchange','asymmetric','decoupled'])
@pytest.mark.parametrize('pulse',[False,True])
def test_saved_direct_and_common_replay_full_physical_states(kind,pulse):
    t=np.linspace(0,12e-9,121)
    a=.02*np.interp(t,[0,2e-9,4e-9,6e-9],[0,1,1,0]) if pulse else .02*np.minimum(t/2e-9,1.)
    b=-.01*np.minimum(t/3e-9,1.);args=arguments(time=t,source_currents=np.column_stack((a,b)),cells=16)
    if kind=='asymmetric':
        args.update(R=[[25.,2.],[2.,17.]],L=np.array([[510.,70.],[70.,430.]])*1e-9,
            G=[[.003,-.0002],[-.0002,.0015]],C=np.array([[230.,-30.],[-30.,190.]])*1e-12,
            source_shunt_resistance=[23.,37.],load_resistance=[91.,113.])
    elif kind=='decoupled':
        for name in ['R','L','G','C']:args[name]=np.diag(np.diag(args[name]))
    expected=coupled_norton_reactive_ladder_response(**args);d=NortonReactiveRLGCLadderDocument(**args)
    loaded=NortonReactiveRLGCLadderDocument.loads(d.dumps());actual=loaded.analyze(max_evaluations=121)
    assert actual.to_dict(include_states=True)==expected.to_dict(include_states=True)
    out=execute_saved(loaded.dumps(),max_evaluations=121)
    assert out['status']=='complete' and out['error'] is None and out['result']==expected.to_dict()
    assert out['input']==d.to_dict();json.dumps(out,allow_nan=False)


@pytest.mark.parametrize('change',['inputs','time','drive','node_shape','segment_shape','voltage_shape','current_shape','cap_current','cap_energy','cap_power','branch_current','branch_energy','branch_rate','branch_loss','type'])
def test_solver_result_must_retain_saved_identity(change,monkeypatch):
    d=document();r=d.analyze()
    if change=='inputs':
        data=r.inputs;data['R_ohm_per_m'][0][0]+=1;bad=replace(r,input_json=json.dumps(data))
    elif change=='time':bad=replace(r,time=np.array([0.,1.,2.]))
    elif change=='drive':bad=replace(r,source_currents=np.ones((3,2)))
    elif change=='node_shape':bad=replace(r,node_voltage=np.zeros((3,8,2)))
    elif change=='segment_shape':bad=replace(r,segment_current=np.zeros((3,9,2)))
    elif change=='voltage_shape':bad=replace(r,voltage=np.zeros((3,2)))
    elif change=='current_shape':bad=replace(r,current=np.zeros((3,2)))
    elif change=='cap_current':bad=replace(r,load_capacitor_current=np.zeros((3,1)))
    elif change=='cap_energy':
        # A malformed solver result must reach the document guard; normal
        # response construction already rejects incompatible energy shapes.
        bad=copy(r);object.__setattr__(bad,'load_capacitor_energy',np.zeros(2))
    elif change in ['cap_power','branch_current','branch_energy','branch_rate','branch_loss']:
        field={'cap_power':'load_capacitor_power','branch_current':'load_branch_current',
               'branch_energy':'load_branch_energy','branch_rate':'load_branch_energy_rate',
               'branch_loss':'load_branch_resistor_loss'}[change]
        bad=copy(r);object.__setattr__(bad,field,np.zeros((3,1)) if change=='branch_current' else np.zeros(2))
    else:bad=None
    monkeypatch.setattr(module,'coupled_norton_reactive_ladder_response',lambda **kw:bad)
    with pytest.raises(ValueError,match='changed saved'):d.analyze()


def test_runtime_unrepresentable_cell_failure_is_not_partial_success():
    d=document(L=np.eye(2)*1e-300,C=np.eye(2)*1e-300,length=1e-300)
    assert normalize_saved(d.dumps())==d.dumps()
    with pytest.raises(ValueError,match='finite scales'):d.analyze()
    with pytest.raises(ValueError,match='finite scales'):execute_saved(d.dumps())


@pytest.mark.parametrize('source,load',[
    ([None,None],[None,None]),([0.,0.],[0.,0.]),([None,37.],[None,0.]),
    ([23.,0.],[0.,None]),([23.,37.],[None,100.]),([23.,37.],[91.,113.]),
])
def test_saved_per_conductor_boundaries_keep_null_and_zero_distinct(source,load):
    args=arguments(source_shunt_resistance=source,load_resistance=load)
    expected=coupled_norton_reactive_ladder_response(**args).to_dict()
    d=NortonReactiveRLGCLadderDocument(**args);out=execute_saved(d.dumps(),max_evaluations=3)
    assert out['input']['schema']=='sipi.norton-rlgc-startup/1'
    assert out['input']['source_shunt_resistance_ohm']==source and out['input']['load_resistance_ohm']==load
    assert out['result']==expected and out['status']=='complete'


def test_current_and_voltage_saved_inputs_do_not_substitute_units_or_versions():
    from sipi import ReactiveRLGCLadderDocument, StartupPortWavesDocument
    args=arguments();currents=args.pop('source_currents');shunt=args.pop('source_shunt_resistance')
    old=ReactiveRLGCLadderDocument(source_voltages=currents,source_resistance=[25.,37.],**args)
    assert normalize_saved(old.dumps())==old.dumps()
    assert execute_saved(old.dumps(),max_evaluations=3)['result']['scope']=='finite-passive-two-signal-reactive-load-rlgc-startup'
    with pytest.raises(ValueError):NortonReactiveRLGCLadderDocument.loads(old.dumps())
    with pytest.raises(ValueError):ReactiveRLGCLadderDocument.loads(document().dumps())
    for key,value in [('source_currents_a',currents),('source_shunt_resistance_ohm',shunt)]:
        data=old.to_dict();data[key]=value
        with pytest.raises(ValueError):ReactiveRLGCLadderDocument.from_dict(data)
        with pytest.raises(ValueError):normalize_saved(json.dumps(data))
    for key,value in [('source_voltages_v',currents),('source_resistance_ohm',[25.,37.])]:
        data=document().to_dict();data[key]=value
        with pytest.raises(ValueError):NortonReactiveRLGCLadderDocument.from_dict(data)
        with pytest.raises(ValueError):normalize_saved(json.dumps(data))
    wrapped=dict(schema='sipi.startup-port-waves/1',startup=document().to_dict(),z_ref_ohm=[35.,45.,55.,65.])
    with pytest.raises(ValueError,match='nested startup'):StartupPortWavesDocument.from_dict(wrapped)
    with pytest.raises(ValueError):normalize_saved(json.dumps(wrapped))


@pytest.mark.parametrize('cap,resistance',[(np.zeros((2,2)),np.zeros((2,2))),
    (np.array([[1.,-1.],[-1.,1.]])*20e-12,np.array([[1.,-1.],[-1.,1.]]))])
def test_zero_and_rank_one_load_terms_replay_without_repair(cap,resistance):
    args=arguments(load_capacitance=cap,load_branch_resistance=resistance)
    d=NortonReactiveRLGCLadderDocument(**args);out=execute_saved(d.dumps())
    assert out['input']['load_capacitance_f']==cap.tolist()
    assert out['input']['load_branch_resistance_ohm']==resistance.tolist()
    assert out['result']==coupled_norton_reactive_ladder_response(**args).to_dict()
    r=d.analyze()
    assert not hasattr(r,'source_voltages') and not hasattr(r,'source_resistor_loss')
    for name in ['source_currents','source_shunt_resistor_loss','load_branch_current','load_branch_energy']:
        assert not getattr(r,name).flags.writeable
