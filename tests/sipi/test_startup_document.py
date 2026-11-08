# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict startup storage, no-waveform parsing, budgets and actual replay."""
from dataclasses import replace
import json

import numpy as np
import pytest
from sipi import LosslessStartupDocument, lossless_line_response
from sipi.execution import execute_saved, normalize_saved, saved_schemas
import sipi.startup as api
import sipi.startup_document as module


def document(**changes):
    args=dict(time=[0.,1e-9,2e-9,3e-9],source_times=[0.],source_voltages=[1.],
        z0_ohm=50.,delay_s=1e-9,source_resistance=50.,load_resistance=None,max_terms=10000)
    args.update(changes);return LosslessStartupDocument(**args)


def forbidden(*args,**kwargs):pytest.fail('validation or caller budget evaluated waveforms')


def test_canonical_detached_input_and_registry_without_waveforms(monkeypatch):
    monkeypatch.setattr(api,'_drive',forbidden)
    monkeypatch.setattr(module,'lossless_line_response',forbidden)
    t=np.array([0.,1e-9,2e-9]);knots=np.array([0.]);v=np.array([1.])
    d=document(time=t,source_times=knots,source_voltages=v)
    text=d.dumps();assert normalize_saved(text)==text
    assert LosslessStartupDocument.loads(text).dumps()==text
    assert 'sipi.lossless-startup/1' in saved_schemas() and d.required_terms==1
    t[:]=9;knots[:]=9;v[:]=9
    out=d.to_dict();out['time_s'].clear();out['source_voltages_v'][0]=999
    assert d.dumps()==text


@pytest.mark.parametrize('mutate',[
    lambda d:d.update(schema='sipi.lossless-startup/999'),lambda d:d.update(extra=1),
    lambda d:d.pop('load_resistance_ohm'),lambda d:d.pop('max_terms'),
    lambda d:d.update(time_s=[]),lambda d:d.update(time_s=[1.,0.]),lambda d:d.update(time_s=[0.,0.]),
    lambda d:d.update(time_s=[True]),lambda d:d.update(time_s=[-1]),lambda d:d.update(time_s=[[0.]]),
    lambda d:d.update(source_times_s=[]),lambda d:d.update(source_times_s=[1.,0.]),
    lambda d:d.update(source_voltages_v=[1.,2.]),lambda d:d.update(source_voltages_v=[True]),
    lambda d:d.update(source_voltages_v=1.),lambda d:d.update(z0_ohm=0),lambda d:d.update(z0_ohm=True),
    lambda d:d.update(delay_s=-1),lambda d:d.update(source_resistance_ohm=-1),
    lambda d:d.update(load_resistance_ohm='open'),lambda d:d.update(load_resistance_ohm=True),
    lambda d:d.update(max_terms=0),lambda d:d.update(max_terms=10001),lambda d:d.update(max_terms=True),
    lambda d:d.update(max_terms=1.,source_resistance_ohm=0.),
    lambda d:d.update(max_terms=1,source_resistance_ohm=0.),
])
def test_strict_saved_inputs_reject_without_waveforms(mutate,monkeypatch):
    data=document().to_dict();mutate(data)
    monkeypatch.setattr(api,'_drive',forbidden)
    with pytest.raises((ValueError,TypeError)):LosslessStartupDocument.from_dict(data)
    with pytest.raises((ValueError,TypeError)):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('text',['{"schema":"x","schema":"y"}',
    '{"schema":"sipi.lossless-startup/1","time_s":[NaN]}',
    '{"schema":"sipi.lossless-startup/1","load_resistance_ohm":1e999}',
    '[]','null'])
def test_duplicate_nonfinite_and_nonobject_json_reject(text):
    with pytest.raises(ValueError):LosslessStartupDocument.loads(text)
    with pytest.raises(ValueError):normalize_saved(text)


def test_caller_budget_counts_required_terms_not_saved_ceiling_or_samples(monkeypatch):
    d=document(time=np.linspace(0.,20e-9,1000));assert d.required_terms==1
    original=module.lossless_line_response;observed=[]
    def spy(**kwargs):observed.append(kwargs['max_terms']);return original(**kwargs)
    monkeypatch.setattr(module,'lossless_line_response',spy)
    out=execute_saved(d.dumps(),max_evaluations=2)
    assert out['status']=='complete' and out['result']['terms']==1 and observed==[10000]
    assert out['input']['max_terms']==10000 and len(out['result']['time_s'])==1000
    several=document(time=[0.,4e-9],source_resistance=0.)
    assert several.required_terms==3
    monkeypatch.setattr(module,'lossless_line_response',forbidden)
    with pytest.raises(ValueError,match='max_evaluations'):several.analyze(max_evaluations=2)
    with pytest.raises(ValueError,match='max_evaluations'):execute_saved(several.dumps(),max_evaluations=2)


def test_zero_term_and_diagnostics_byte_limits_before_waveforms(monkeypatch):
    d=document(time=[0.],source_times=[1.]);assert d.required_terms==0
    out=execute_saved(d.dumps(),max_evaluations=2)
    assert out['result']['terms']==0 and out['result']['voltage_v']==[[0.,0.]]
    monkeypatch.setattr(module,'lossless_line_response',forbidden)
    with pytest.raises(ValueError,match='diagnostics'):execute_saved(d.dumps(),diagnostics=['modes'])
    with pytest.raises(ValueError,match='max_input_bytes'):execute_saved(d.dumps(),max_input_bytes=2)
    with pytest.raises(ValueError):d.analyze(max_evaluations=True)


@pytest.mark.parametrize('load',[None,0.,50.,100.,1e200])
@pytest.mark.parametrize('pulse',[False,True])
def test_saved_and_common_execution_equal_direct_actual_startup(load,pulse):
    t=np.linspace(0.,12e-9,121)
    args=dict(time=t,source_times=[0.,.7e-9,2e-9,5e-9] if pulse else [0.],
        source_voltages=[0.,2.,-1.,0.] if pulse else [1.],z0_ohm=50.,delay_s=1e-9,
        source_resistance=25.,load_resistance=load,max_terms=64)
    expected=lossless_line_response(**args).to_dict()
    d=LosslessStartupDocument(**args);loaded=LosslessStartupDocument.loads(d.dumps())
    assert loaded.analyze(max_evaluations=64).to_dict()==expected
    out=execute_saved(loaded.dumps(),max_evaluations=64)
    assert out['status']=='complete' and out['error'] is None and out['result']==expected
    json.dumps(out,allow_nan=False)


@pytest.mark.parametrize('change',[dict(z0_ohm=60.),dict(time=np.array([0.])),dict(terms=99)])
def test_solve_cannot_change_saved_input_or_count(change,monkeypatch):
    d=document();valid=d.analyze()
    monkeypatch.setattr(module,'lossless_line_response',lambda **kwargs:replace(valid,**change))
    with pytest.raises(ValueError,match='changed saved'):d.analyze()


def test_runtime_resolution_failure_is_preserved_without_partial_success():
    d=document(time=[1e20],delay_s=1e20,source_times=[0.,1.],source_voltages=[0.,1.],load_resistance=50.)
    assert normalize_saved(d.dumps())==d.dumps()
    with pytest.raises(ValueError,match='resolution'):d.analyze()
    with pytest.raises(ValueError,match='resolution'):execute_saved(d.dumps())
