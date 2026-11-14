# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved adaptive plans retain all inputs, terminal states and partial evidence."""
import json
from types import SimpleNamespace
import numpy as np
import pytest
from sipi import CrossSection
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.adaptive_panel_resolution_document import AdaptivePanelResolutionDocument
from sipi.line_resolution_document import resolution_record
from sipi.execution import normalize_saved, execute_saved
from test_adaptive_panel_resolution import inputs,TOLERANCES,observed,replay,fake


def document(coated=True,levels=2):
    line,steps=inputs(coated,levels)
    return AdaptivePanelResolutionDocument(line,refinements=steps,tolerances=TOLERANCES)


def test_normalization_is_field_free_strict_and_isolated(monkeypatch):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('normalization meshed'))
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('normalization solved'))
    doc=document();text=doc.dumps()
    assert text==normalize_saved(text)==AdaptivePanelResolutionDocument.loads(text).dumps()
    raw=doc.to_dict();raw['refinements'][-1]['refined_panel']['panels_per_edge']=256
    raw['line']['line']['conductor']['conductors']['left']['coatings'][0]['thickness_m']=0.
    assert doc.dumps()==text


@pytest.mark.parametrize('where',['root','step','line','outer','panel','tolerance'])
@pytest.mark.parametrize('mutation',['missing','unknown'])
def test_exact_saved_keys(where,mutation):
    raw=document().to_dict()
    target={'root':raw,'step':raw['refinements'][0],'line':raw['line'],
        'outer':raw['refinements'][0]['outer_lines'][0],'panel':raw['refinements'][0]['refined_panel'],
        'tolerance':raw['tolerances']['C0_f_per_m']}[where]
    if mutation=='unknown':target['unexpected']=1
    else:target.pop(next(iter(target)))
    with pytest.raises((ValueError,TypeError)):AdaptivePanelResolutionDocument.from_dict(raw)


@pytest.mark.parametrize('change',['future','line-future','wrong-unit','duplicate','nan','short','long',
    'steps-tuple','outers-tuple','late-size','late-physics','late-mesh','late-panel','stored-budget'])
def test_invalid_whole_plan_precedes_fields(change,monkeypatch):
    raw=document().to_dict()
    if change=='future':raw['schema']='sipi.adaptive-panel-resolution/2'
    if change=='line-future':raw['line']['schema']='sipi.panel-transmission-line/3'
    if change=='wrong-unit':raw['tolerances']['C_pf_per_mm']=raw['tolerances'].pop('C0_f_per_m')
    if change=='short':raw['refinements']=raw['refinements'][:1]
    if change=='long':raw['refinements']*=3
    if change=='steps-tuple':raw['refinements']=tuple(raw['refinements'])
    if change=='outers-tuple':raw['refinements'][0]['outer_lines']=tuple(raw['refinements'][0]['outer_lines'])
    if change=='late-size':raw['refinements'][-1]['outer_lines'][0]['line']['cross_section']['box']['width']*=2
    if change=='late-physics':raw['refinements'][-1]['outer_lines'][0]['line']['conductor']['reference']['conductivity']*=.9
    if change=='late-mesh':raw['refinements'][-1]['outer_lines'][0]['line']['cross_section']['mesh']['grade']*=2
    if change=='late-panel':raw['refinements'][-1]['refined_panel']['panels_per_edge']=16
    if change=='stored-budget':raw['max_solves']=7
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('invalid input solved'))
    with pytest.raises((ValueError,TypeError)):
        if change in ('duplicate','nan'):
            text=json.dumps(raw)
            text=text.replace('"max_solves": 16','"max_solves": 16, "max_solves": 16') if change=='duplicate' else text.replace('"relative": 0.1','"relative": NaN')
            AdaptivePanelResolutionDocument.loads(text)
        else:AdaptivePanelResolutionDocument.from_dict(raw)


def test_actual_saved_and_common_results_match_direct(observed,monkeypatch,record_property):
    line,steps,direct=observed;calls=replay(monkeypatch,direct)
    doc=AdaptivePanelResolutionDocument(line,refinements=steps,tolerances=TOLERANCES)
    saved=AdaptivePanelResolutionDocument.loads(doc.dumps()).analyze(max_evaluations=8)
    output=execute_saved(doc.dumps(),max_evaluations=8)
    assert output['status']=='complete' and output['error'] is None
    assert output['result']==resolution_record(saved)==resolution_record(direct)
    assert output['result']['accepted'] and output['result']['outer_completed']
    assert output['result']['refinement_levels']==2 and output['result']['selected_evaluation_index']==6
    assert 'expected_evaluations' not in output['result'] and 'mesh_levels' not in output['result']
    assert len(calls)==16 and json.loads(json.dumps(output,allow_nan=False))==output
    record_property('saved_adaptive_panel_record',json.dumps(output,allow_nan=False))


def test_actual_unaccepted_small_terms_are_not_execution_success(observed,monkeypatch):
    line,steps,direct=observed;replay(monkeypatch,direct)
    raw=AdaptivePanelResolutionDocument(line,refinements=steps,tolerances=TOLERANCES).to_dict()
    raw['tolerances']={'R_ohm_per_m':dict(relative=.005,absolute=0.)}
    output=execute_saved(json.dumps(raw));r=output['result']
    assert output['status']=='complete' and output['error'] is None
    assert r['completed'] and not r['accepted'] and r['selected_evaluation_index'] is None
    assert any(not row['accepted'] for row in r['comparisons'])


def synthetic(monkeypatch,**kwargs):
    calls=fake(monkeypatch,**kwargs);operation=PanelTransmissionLineDocument.analyze
    def analyze(self):
        r=operation(self);r.R=r.C*1e10;r.G=r.C*1e5
        r.dielectric=SimpleNamespace(C0=r.C[0],L=np.eye(2)*1e-7);r.conductor=None
        return r
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',analyze)
    return calls


@pytest.mark.parametrize('index',range(1,9))
def test_each_failure_serializes_exact_attempt_and_partial_history(monkeypatch,index):
    doc=document();calls=synthetic(monkeypatch,fail=index)
    output=execute_saved(doc.dumps());r=output['result']
    assert output['status']=='failed' and not r['completed'] and not r['accepted']
    assert len(r['evaluations'])==index-1 and len(calls)==index
    assert output['error']==r['failure'] and r['failure']['input']==json.loads(calls[-1])
    assert r['failure']['kind']=='ValueError' and r['selected_evaluation_index'] is None
    assert json.loads(json.dumps(output,allow_nan=False))==output


@pytest.mark.parametrize('state',['accepted','level-limit','outer','budget'])
def test_terminal_status_and_caller_budget_preserve_partial_result(monkeypatch,state):
    levels=4 if state=='budget' else 2;raw=document(levels=levels).to_dict()
    raw['tolerances']={'C_f_per_m':dict(relative=.01,absolute=0.)}
    values={(1,1):2.,(2,2):3.} if state in ('level-limit','budget') else None
    calls=synthetic(monkeypatch,values=values,outer=2. if state=='outer' else 1.)
    output=execute_saved(json.dumps(raw),max_evaluations=8);r=output['result']
    expected={'accepted':'accepted','level-limit':'resolution-unaccepted','outer':'outer-unaccepted','budget':'budget-exhausted'}[state]
    assert r['stop_reason']==expected and r['accepted']==(state=='accepted')
    assert output['status']==('failed' if state=='budget' else 'complete')
    assert r['completed']==(state!='budget') and len(calls)==(7 if state in ('budget','level-limit') else 8)
    if state=='budget':assert output['error']['kind']=='ResolutionBudgetExceeded' and r['failure'] is None
    else:assert output['error'] is None
    if state!='accepted':assert r['selected_evaluation_index'] is None


def test_admission_budget_and_interrupt_propagate(monkeypatch):
    doc=document();calls=synthetic(monkeypatch,fail=1,interrupt=True)
    with pytest.raises(ValueError,match='before any field solve'):execute_saved(doc.dumps(),max_evaluations=7)
    assert not calls
    with pytest.raises(KeyboardInterrupt):execute_saved(doc.dumps(),max_evaluations=8)
    assert len(calls)==1
