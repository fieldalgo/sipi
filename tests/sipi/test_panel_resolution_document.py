# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved separate-axis checks preserve partial and unaccepted panel results."""
import json
import pytest

from sipi import CrossSection
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.panel_resolution_document import PanelResolutionDocument
from sipi.line_resolution_document import resolution_record
from sipi.execution import normalize_saved,execute_saved
from test_panel_resolution import inputs,FINE,TOLERANCES,observed,replay


def document(coated=True):
    base,outers=inputs(coated)
    return PanelResolutionDocument(base,refined_panel_options=FINE,
        outer_documents=outers,tolerances=TOLERANCES)


def test_normalization_keeps_explicit_method_and_copies_controls(monkeypatch):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('normalization meshed'))
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('normalization solved'))
    doc=document();text=doc.dumps()
    assert text==normalize_saved(text)==PanelResolutionDocument.loads(text).dumps()
    raw=doc.to_dict();raw['refined_panel']['panels_per_edge']=256
    raw['line']['line']['conductor']['conductors']['left']['coatings'][0]['thickness_m']=0.
    assert doc.dumps()==text
    assert doc.to_dict()['line']['schema']=='sipi.panel-transmission-line/2'
    with pytest.raises(ValueError):PanelTransmissionLineDocument.loads(text)


@pytest.mark.parametrize('where',['root','line','outer','panel','tolerance'])
@pytest.mark.parametrize('mutation',['unknown','missing'])
def test_strict_keys_at_each_saved_level(where,mutation):
    data=document().to_dict()
    target={'root':data,'line':data['line'],'outer':data['outer_lines'][0],
        'panel':data['refined_panel'],'tolerance':data['tolerances']['C0_f_per_m']}[where]
    if mutation=='unknown':target['unexpected']=1
    else:target.pop(next(iter(target)))
    with pytest.raises((ValueError,TypeError)):PanelResolutionDocument.from_dict(data)


@pytest.mark.parametrize('change',['future','nested-future','wrong-unit','duplicate','nonfinite',
    'decreasing-panel','changed-physics','outer-resolution','stored-budget'])
def test_invalid_contracts_precede_field_work(change,monkeypatch):
    data=document().to_dict()
    if change=='future':data['schema']='sipi.panel-resolution/2'
    if change=='nested-future':data['line']['schema']='sipi.panel-transmission-line/3'
    if change=='wrong-unit':data['tolerances']['C_pf_per_mm']=data['tolerances'].pop('C0_f_per_m')
    if change=='decreasing-panel':data['refined_panel']['panels_per_edge']=8
    if change=='changed-physics':data['outer_lines'][0]['line']['cross_section']['traces'][0]['width']*=.9
    if change=='outer-resolution':data['outer_lines'][0]['panel']['ground_modes']=512
    if change=='stored-budget':data['max_solves']=4
    text=json.dumps(data)
    if change=='duplicate':text=text.replace('"max_solves": 6','"max_solves": 6, "max_solves": 6')
    if change=='nonfinite':text=text.replace('"relative": 0.1','"relative": NaN')
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('invalid input solved'))
    with pytest.raises((ValueError,TypeError)):PanelResolutionDocument.loads(text)


def test_actual_direct_saved_and_common_records_match_for_each_method(observed,monkeypatch):
    base,outers,direct=observed;calls=replay(monkeypatch,direct)
    doc=PanelResolutionDocument(base,refined_panel_options=FINE,outer_documents=outers,tolerances=TOLERANCES)
    saved=PanelResolutionDocument.loads(doc.dumps()).analyze(max_evaluations=5)
    output=execute_saved(doc.dumps(),max_evaluations=5)
    assert output['status']=='complete' and output['error'] is None
    assert output['result']==resolution_record(saved)==resolution_record(direct)
    assert output['result']['completed'] and output['result']['accepted']
    assert len(calls)==10 and output['result']['expected_evaluations']==5
    assert [(r['reference_index'],r['evaluation_index']) for r in output['result']['comparisons']]==[(0,1),(0,2),(1,3),(2,3),(3,4)]
    assert output['input']==doc.to_dict()
    assert json.loads(json.dumps(output,allow_nan=False))==output


def test_unaccepted_mutual_terms_remain_visible_without_execution_error(observed,monkeypatch):
    base,outers,direct=observed;replay(monkeypatch,direct)
    data=PanelResolutionDocument(base,refined_panel_options=FINE,
        outer_documents=outers,tolerances=TOLERANCES).to_dict()
    data['tolerances']={'R_ohm_per_m':dict(relative=.005,absolute=0.)}
    output=execute_saved(PanelResolutionDocument.from_dict(data).dumps())
    r=output['result'];assert output['status']=='complete' and output['error'] is None
    assert r['completed'] and not r['accepted']
    assert not r['comparisons'][-1]['accepted']
    delta=r['comparisons'][-1]['differences']['R_ohm_per_m'][0][0][1]
    allowance=r['comparisons'][-1]['allowances']['R_ohm_per_m'][0][0][1]
    assert delta>allowance


@pytest.mark.parametrize('stage',['base','volume','panel','joint','outer:0'])
def test_each_failed_stage_keeps_partial_result_and_exact_input(observed,monkeypatch,stage):
    base,outers,direct=observed;index=[r.stage for r in direct.evaluations].index(stage)
    text=direct.evaluations[index].input_json;calls=replay(monkeypatch,direct,text)
    doc=PanelResolutionDocument(base,refined_panel_options=FINE,outer_documents=outers,tolerances=TOLERANCES)
    output=execute_saved(doc.dumps());r=output['result']
    assert output['status']=='failed' and not r['completed'] and not r['accepted']
    assert output['error']==r['failure']==dict(stage=stage,input=json.loads(text),
        kind='ValueError',message='explicit panel assessment refusal')
    assert len(calls)==index+1 and len(r['evaluations'])==index


def test_common_budget_and_interrupt_remain_explicit(monkeypatch):
    doc=document()
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('budget solved'))
    with pytest.raises(ValueError,match='before any field solve'):execute_saved(doc.dumps(),max_evaluations=4)
    def interrupt(self):raise KeyboardInterrupt()
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',interrupt)
    with pytest.raises(KeyboardInterrupt):execute_saved(doc.dumps())
