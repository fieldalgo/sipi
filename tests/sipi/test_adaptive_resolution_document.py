# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved adaptive requests retain budgets, acceptance and the selected domain."""
import json
import pytest

from sipi import CrossSection
from sipi.line_model import TransmissionLineDocument
from sipi.adaptive_line_resolution import refine_line_resolution
from sipi.line_resolution import ResolutionTolerance
from sipi.line_resolution_document import LineResolutionDocument,resolution_record
from sipi.execution import normalize_saved,execute_saved
from test_line_resolution import inputs,TOLERANCES


def document():
    base,outers=inputs()
    return LineResolutionDocument(base,outer_documents=outers,tolerances=TOLERANCES,
        schema='sipi.line-resolution/2',max_levels=4,max_solves=8)


def test_normalization_is_field_free_strict_and_isolated(monkeypatch):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('normalization meshed'))
    doc=document();text=doc.dumps()
    assert text==normalize_saved(text)==LineResolutionDocument.loads(text).dumps()
    raw=doc.to_dict();raw['max_levels']=2;raw['tolerances']['C_f_per_m']['absolute']=1.
    assert doc.dumps()==text
    assert set(doc.to_dict())=={'schema','line','outer_lines','refinement_factor','max_solves','max_levels','tolerances'}


@pytest.mark.parametrize('change',['missing','unknown','future','duplicate','nonfinite','too-few-levels',
    'too-many-levels','bool-levels','too-few-solves','too-many-solves','unit'])
def test_invalid_saved_controls_precede_all_field_work(monkeypatch,change):
    raw=document().to_dict()
    if change=='missing':raw.pop('max_levels')
    if change=='unknown':raw['stopping_rule']='first-pass'
    if change=='future':raw['schema']='sipi.line-resolution/3'
    if change=='too-few-levels':raw['max_levels']=1
    if change=='too-many-levels':raw['max_levels']=9
    if change=='bool-levels':raw['max_levels']=True
    if change=='too-few-solves':raw['max_solves']=4
    if change=='too-many-solves':raw['max_solves']=17
    if change=='unit':raw['tolerances']['C_pf_per_mm']=raw['tolerances'].pop('C_f_per_m')
    text=json.dumps(raw)
    if change=='duplicate':text=text.replace('"max_levels": 4','"max_levels": 4, "max_levels": 4')
    if change=='nonfinite':text=text.replace('"max_levels": 4','"max_levels": Infinity')
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('invalid request meshed'))
    with pytest.raises((ValueError,TypeError)):LineResolutionDocument.loads(text)


def test_legacy_request_cannot_silently_select_adaptive_controls():
    base,outers=inputs()
    with pytest.raises(ValueError,match='requires line-resolution/2'):
        LineResolutionDocument(base,outer_documents=outers,tolerances=TOLERANCES,max_levels=3)
    raw=document().to_dict();raw['schema']='sipi.line-resolution/1'
    with pytest.raises(ValueError):LineResolutionDocument.from_dict(raw)


@pytest.fixture(scope='module')
def observed():
    base,outers=inputs()
    return document(),refine_line_resolution(base,outer_documents=outers,tolerances=TOLERANCES)


def replay(monkeypatch,direct,failed=None):
    values={r.input_json:r.result for r in direct.evaluations};calls=[]
    def analyze(self):
        text=self.dumps();calls.append(text)
        if text==failed:raise ValueError('explicit saved adaptive field refusal')
        return values[text]
    monkeypatch.setattr(TransmissionLineDocument,'analyze',analyze)
    return calls


def test_actual_direct_saved_and_common_results_match_with_original_domain_selection(observed,monkeypatch):
    doc,direct=observed;calls=replay(monkeypatch,direct)
    saved=LineResolutionDocument.loads(doc.dumps()).analyze()
    output=execute_saved(doc.dumps(),max_evaluations=5)
    assert output['status']=='complete' and output['error'] is None
    assert output['result']==resolution_record(saved)==resolution_record(direct)
    record=output['result'];assert record['completed'] and record['accepted'] and record['outer_completed']
    assert record['stop_reason']=='accepted' and record['mesh_levels']==2
    assert record['selected_evaluation_index']==2
    assert record['evaluations'][2]['input']['cross_section']['box']['width']==.008
    assert record['evaluations'][-1]['input']['cross_section']['box']['width']==.016
    assert len(record['evaluations'])==5 and len(calls)==10
    assert 'expected_evaluations' not in record
    assert json.loads(json.dumps(output,allow_nan=False))==output


def test_level_stop_is_complete_but_not_accepted(observed,monkeypatch):
    doc,direct=observed;calls=replay(monkeypatch,direct)
    raw=doc.to_dict();raw['max_levels']=2
    raw['tolerances']={'C_f_per_m':dict(relative=0.,absolute=0.)}
    output=execute_saved(LineResolutionDocument.from_dict(raw).dumps())
    r=output['result'];assert output['status']=='complete' and output['error'] is None
    assert r['completed'] and not r['accepted'] and not r['outer_completed']
    assert r['stop_reason']=='mesh-unaccepted' and r['selected_evaluation_index'] is None
    assert len(calls)==len(r['evaluations'])==3


@pytest.mark.parametrize('external_budget',[False,True],ids=['stored','execution'])
def test_budget_exhaustion_is_failed_and_keeps_partial_results(observed,monkeypatch,external_budget):
    doc,direct=observed;calls=replay(monkeypatch,direct)
    raw=doc.to_dict();raw['tolerances']={'C_f_per_m':dict(relative=0.,absolute=0.)}
    if not external_budget:raw['max_solves']=5
    output=execute_saved(LineResolutionDocument.from_dict(raw).dumps(),
                          max_evaluations=5 if external_budget else 10000)
    r=output['result'];assert output['status']=='failed' and not r['completed'] and not r['accepted']
    assert r['stop_reason']=='budget-exhausted' and r['failure'] is None
    assert r['selected_evaluation_index'] is None and not r['outer_completed']
    assert output['error']['kind']=='ResolutionBudgetExceeded' and output['error']['stage']=='budget'
    assert output['error']['input']==output['input']
    assert len(calls)==len(r['evaluations'])==3


def test_execution_minimum_budget_refuses_before_field_work(monkeypatch):
    doc=document()
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('budget meshed'))
    with pytest.raises(ValueError,match='before any field solve'):
        execute_saved(doc.dumps(),max_evaluations=4)


@pytest.mark.parametrize('stage',['base','mesh:1','mesh:2','outer:0','outer:1'])
def test_field_failure_keeps_exact_stage_and_input(observed,monkeypatch,stage):
    doc,direct=observed;index=[r.stage for r in direct.evaluations].index(stage)
    text=direct.evaluations[index].input_json;calls=replay(monkeypatch,direct,text)
    output=execute_saved(doc.dumps());r=output['result']
    assert output['status']=='failed' and not r['completed'] and not r['accepted']
    assert r['stop_reason']=='field-failed' and r['selected_evaluation_index'] is None
    assert output['error']==r['failure']==dict(stage=stage,input=json.loads(text),
        kind='ValueError',message='explicit saved adaptive field refusal')
    assert len(calls)==index+1 and len(r['evaluations'])==index


def test_saved_user_interrupt_propagates(monkeypatch):
    def interrupt(self):raise KeyboardInterrupt()
    monkeypatch.setattr(TransmissionLineDocument,'analyze',interrupt)
    with pytest.raises(KeyboardInterrupt):execute_saved(document().dumps())
