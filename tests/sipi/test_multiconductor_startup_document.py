# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit signal count, SI storage, full-state replay and pre-solve budgets."""
from dataclasses import fields, replace
import json

import numpy as np
import pytest
from sipi import (MulticonductorRLGCLadderDocument, multiconductor_rlgc_ladder_response,
                  CoupledRLGCLadderDocument, RLGCLadderDocument, StartupPortWavesDocument)
from sipi.execution import execute_saved, normalize_saved, saved_schemas
from test_multiconductor_startup import modal_data
import sipi.multiconductor_startup as api
import sipi.multiconductor_startup_document as module


def arguments(signals=3,kind='coupled',pulse=False,**changes):
    _,_,matrices=modal_data(signals)
    if kind=='diagonal':matrices={k:np.diag(np.diag(v)) for k,v in matrices.items()}
    if kind=='lossless':matrices['R']=np.zeros((signals,signals));matrices['G']=np.zeros((signals,signals))
    t=np.linspace(0,12e-9,121);drive=np.minimum(t/2e-9,1.)[:,None]*np.array([1.,-.4,.2,-.1])[:signals]
    if pulse:drive*=np.clip((6e-9-t)/2e-9,0,1)[:,None]
    args=dict(time=t,source_voltages=drive,signals=signals,**matrices,length=.1,cells=8,
        source_resistance=[25.]*signals,load_resistance=[100.]*signals)
    args.update(changes);return args


def document(signals=3,**kw):return MulticonductorRLGCLadderDocument(**arguments(signals,**kw))


def forbidden(*args,**kwargs):pytest.fail('validation or budget reached propagation')


@pytest.mark.parametrize('signals',[3,4])
def test_canonical_twelve_keys_and_copies_without_propagation(monkeypatch,signals):
    monkeypatch.setattr(api,'lsim',forbidden);monkeypatch.setattr(module,'multiconductor_rlgc_ladder_response',forbidden)
    args=arguments(signals);d=MulticonductorRLGCLadderDocument(**args);text=d.dumps()
    assert normalize_saved(text)==text and MulticonductorRLGCLadderDocument.loads(text).dumps()==text
    assert 'sipi.multiconductor-rlgc-startup/1' in saved_schemas() and d.samples==121
    assert set(d.to_dict())=={'schema','signals','time_s','source_voltages_v','R_ohm_per_m','L_h_per_m','G_s_per_m','C_f_per_m','length_m','cells','source_resistance_ohm','load_resistance_ohm'}
    args['L'][:]=9;args['source_voltages'][:]=99;args['source_resistance'][0]=99
    data=d.to_dict();data['R_ohm_per_m'][0][0]=999;data['time_s'].clear();data['signals']=99
    assert d.dumps()==text


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('key',['schema','signals','time_s','source_voltages_v','R_ohm_per_m','L_h_per_m','G_s_per_m','C_f_per_m','length_m','cells','source_resistance_ohm','load_resistance_ohm'])
def test_every_key_required(signals,key,monkeypatch):
    data=document(signals).to_dict();data.pop(key);monkeypatch.setattr(api,'lsim',forbidden)
    with pytest.raises(ValueError):MulticonductorRLGCLadderDocument.from_dict(data)
    with pytest.raises(ValueError):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('key,value',[
    ('schema','sipi.multiconductor-rlgc-startup/2'),('schema','sipi.coupled-rlgc-startup/1'),
    ('extra',1),('R_ohm',[[1.]]),('C_f',[[1.]]),('signals',None),('signals',True),('signals',3.),('signals',2),('signals',5),
    ('time_s',[]),('time_s',[0.]),('time_s',[1.,2.,3.]),('time_s',[0.,0.,1.]),('time_s',[0.,1.,3.]),
    ('time_s',[0.,True,2.]),('time_s',[[0.,1.,2.]]),('source_voltages_v',[0.,1.,1.]),
    ('R_ohm_per_m',-1),('G_s_per_m',[[[0.]]]),('L_h_per_m',[[1.,0.],[0.,1e-14]]),('C_f_per_m',[[0.]]),
    ('length_m',0),('length_m',float('inf')),('cells',0),('cells',129),('cells',True),('cells',8.),
    ('source_resistance_ohm',25.),('source_resistance_ohm',[0.,25.,25.]),('source_resistance_ohm',[25.,25.]),
    ('load_resistance_ohm',None),('load_resistance_ohm',[100.,0.,100.]),('load_resistance_ohm',[True]*4)])
def test_strict_saved_inputs_reject_without_propagation(signals,key,value,monkeypatch):
    data=document(signals).to_dict();data[key]=value;monkeypatch.setattr(api,'lsim',forbidden)
    with pytest.raises((ValueError,TypeError)):MulticonductorRLGCLadderDocument.from_dict(data)
    with pytest.raises((ValueError,TypeError)):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('key',['R_ohm_per_m','L_h_per_m','G_s_per_m','C_f_per_m'])
def test_nonzero_singular_and_asymmetric_matrices_rejected(signals,key):
    data=document(signals).to_dict();data[key]=np.diag([1.]*(signals-1)+[0.]).tolist()
    with pytest.raises(ValueError):normalize_saved(json.dumps(data))
    data=document(signals).to_dict();data[key][0][1]=np.nextafter(data[key][1][0],np.inf)
    with pytest.raises(ValueError):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('text',['{"schema":"x","schema":"y"}',
    '{"schema":"sipi.multiconductor-rlgc-startup/1","signals":3,"signals":4}',
    '{"schema":"sipi.multiconductor-rlgc-startup/1","time_s":[NaN]}',
    '{"schema":"sipi.multiconductor-rlgc-startup/1","R_ohm_per_m":[[1e999]]}',
    '[]','null'])
def test_duplicate_nonfinite_and_nonobject_reject(text):
    with pytest.raises(ValueError):MulticonductorRLGCLadderDocument.loads(text)
    with pytest.raises(ValueError):normalize_saved(text)


@pytest.mark.parametrize('signals',[3,4])
def test_actual_time_budget_independent_of_cells_and_signal_count(signals,monkeypatch):
    t=[0.,1e-9,2e-9];drive=np.zeros((3,signals));drive[1:,0]=1.
    d=document(signals,time=t,source_voltages=drive,cells=128);original=module.multiconductor_rlgc_ladder_response;observed=[]
    def spy(**kw):observed.append((len(kw['time']),kw['cells'],kw['signals'],np.shape(kw['source_voltages'])));return original(**kw)
    monkeypatch.setattr(module,'multiconductor_rlgc_ladder_response',spy)
    out=execute_saved(d.dumps(),max_evaluations=3)
    assert observed==[(3,128,signals,(3,signals))] and out['input']['cells']==128
    assert out['status']=='complete' and not out['result']['states_included'] and 'node_voltage_v' not in out['result']
    monkeypatch.setattr(module,'multiconductor_rlgc_ladder_response',forbidden)
    for d in [d,document(signals,time=t,source_voltages=drive,cells=1)]:
        with pytest.raises(ValueError,match='max_evaluations'):d.analyze(max_evaluations=2)
        with pytest.raises(ValueError,match='max_evaluations'):execute_saved(d.dumps(),max_evaluations=2)


def test_row_limit_and_source_initial_validation_without_propagation(monkeypatch):
    monkeypatch.setattr(api,'lsim',forbidden)
    for rows in [1,10001]:
        with pytest.raises(ValueError):document(time=np.linspace(0,1,rows),source_voltages=np.zeros((rows,3)))
    data=document().to_dict();data['source_voltages_v'][0][0]=1e-15
    with pytest.raises(ValueError):normalize_saved(json.dumps(data))
    data=document().to_dict();data['source_voltages_v'][1][0]=True
    with pytest.raises(ValueError):normalize_saved(json.dumps(data))


def test_byte_diagnostic_and_integer_budget_control_before_propagation(monkeypatch):
    d=document();monkeypatch.setattr(module,'multiconductor_rlgc_ladder_response',forbidden)
    with pytest.raises(ValueError,match='max_input_bytes'):execute_saved(d.dumps(),max_input_bytes=2)
    with pytest.raises(ValueError,match='diagnostics'):execute_saved(d.dumps(),diagnostics=['modes'])
    for budget in [True,1,10001,3.]:
        with pytest.raises((ValueError,TypeError)):d.analyze(max_evaluations=budget)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('kind',['coupled','diagonal','lossless'])
@pytest.mark.parametrize('pulse',[False,True])
def test_twelve_saved_direct_common_replays_preserve_full_states(signals,kind,pulse):
    args=arguments(signals,kind,pulse);expected=multiconductor_rlgc_ladder_response(**args)
    d=MulticonductorRLGCLadderDocument(**args);loaded=MulticonductorRLGCLadderDocument.loads(d.dumps())
    actual=loaded.analyze(max_evaluations=121)
    assert actual.to_dict(include_states=True)==expected.to_dict(include_states=True)
    out=execute_saved(loaded.dumps(),max_evaluations=121)
    assert out['status']=='complete' and out['error'] is None and out['result']==expected.to_dict()
    assert out['input']==d.to_dict();json.dumps(out,allow_nan=False)


@pytest.mark.parametrize('signals',[3,4])
@pytest.mark.parametrize('change',['inputs','time','drive','type','node_voltage','segment_current','voltage','current','energy','energy_rate','series_loss','shunt_loss','line_power','source_power','source_resistor_loss','load_resistor_loss'])
def test_solver_result_retains_identity_and_every_array_shape(signals,change,monkeypatch):
    d=document(signals);r=d.analyze(max_evaluations=121)
    if change=='inputs':
        data=r.inputs;data['signals']=3 if signals==4 else 4;bad=replace(r,input_json=json.dumps(data))
    elif change=='time':bad=replace(r,time=r.time*2)
    elif change=='drive':bad=replace(r,source_voltages=np.ones((121,signals)))
    elif change=='type':bad=None
    else:bad=replace(r,**{change:np.zeros((121,1))})
    monkeypatch.setattr(module,'multiconductor_rlgc_ladder_response',lambda **kw:bad)
    with pytest.raises(ValueError,match='changed saved'):d.analyze(max_evaluations=121)


@pytest.mark.parametrize('signals',[3,4])
def test_old_saved_inputs_and_all_prior_wave_versions_reject_new_kind(signals):
    d=document(signals)
    for cls in [CoupledRLGCLadderDocument,RLGCLadderDocument]:
        with pytest.raises(ValueError):cls.loads(d.dumps())
    for version in range(1,9):
        with pytest.raises(ValueError):StartupPortWavesDocument(d,z_ref=[50.]*(2*signals),version=version)
        data=dict(schema=f'sipi.startup-port-waves/{version}',startup=d.to_dict(),z_ref_ohm=[50.]*(2*signals))
        with pytest.raises(ValueError):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('signals',[3,4])
def test_runtime_unrepresentable_cell_failure_is_retained(signals):
    d=document(signals,L=np.eye(signals)*1e-300,C=np.eye(signals)*1e-300,length=1e-300)
    assert normalize_saved(d.dumps())==d.dumps()
    with pytest.raises(ValueError,match='finite scales'):d.analyze(max_evaluations=121)
    with pytest.raises(ValueError,match='finite scales'):execute_saved(d.dumps(),max_evaluations=121)


def test_original_propagation_error_retained(monkeypatch):
    d=document()
    def fail(**kw):raise RuntimeError('deliberate saved propagation failure')
    monkeypatch.setattr(module,'multiconductor_rlgc_ladder_response',fail)
    with pytest.raises(RuntimeError,match='deliberate'):execute_saved(d.dumps(),max_evaluations=121)
