# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict resolution requests distinguish finite acceptance from completion."""
import json
import numpy as np
import pytest

from sipi import CrossSection
from sipi.line_model import TransmissionLineDocument
from sipi.line_resolution import ResolutionTolerance, assess_line_resolution
from sipi.line_resolution_document import LineResolutionDocument, resolution_record
from sipi.execution import normalize_saved, execute_saved
from test_line_resolution import inputs, TOLERANCES


def document():
    base,outers=inputs()
    return LineResolutionDocument(base,outer_documents=outers,tolerances=TOLERANCES)


def test_canonical_si_keys_and_field_free_copy(monkeypatch):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('normalization meshed'))
    doc=document();text=doc.dumps()
    assert normalize_saved(text)==text==LineResolutionDocument.loads(text).dumps()
    raw=doc.to_dict();assert set(raw['tolerances'])=={'C_f_per_m','C0_f_per_m','G_s_per_m','L_external_h_per_m'}
    raw['tolerances']['C_f_per_m']['relative']=1.
    raw['outer_lines'][0]['cross_section']['box']['width']=.001
    assert doc.dumps()==text


@pytest.mark.parametrize('where',['root','line','outer','tolerance'])
@pytest.mark.parametrize('mutation',['unknown','missing'])
def test_strict_nested_keys(where,mutation):
    data=document().to_dict();target={'root':data,'line':data['line'],
        'outer':data['outer_lines'][0],'tolerance':data['tolerances']['C_f_per_m']}[where]
    if mutation=='unknown':target['unexpected']=1
    else:target.pop(next(iter(target)))
    with pytest.raises(ValueError):LineResolutionDocument.from_dict(data)


@pytest.mark.parametrize('change',['future','nested-future','wrong-unit','duplicate','nonfinite','scalar-tolerance'])
def test_unsupported_inputs_refuse_without_implicit_units(change):
    data=document().to_dict();text=json.dumps(data)
    if change=='future':text=text.replace('sipi.line-resolution/1','sipi.line-resolution/2')
    if change=='nested-future':text=text.replace('sipi.transmission-line/1','sipi.transmission-line/8')
    if change=='wrong-unit':text=text.replace('C_f_per_m','C_pf_per_mm')
    if change=='duplicate':text=text.replace('"max_solves": 4','"max_solves": 4, "max_solves": 4')
    if change=='nonfinite':text=text.replace('"relative": 0.005','"relative": NaN')
    if change=='scalar-tolerance':data['tolerances']['C_f_per_m']=.005;text=json.dumps(data)
    with pytest.raises(ValueError):LineResolutionDocument.loads(text)


def test_both_budgets_are_checked_before_field_work(monkeypatch):
    doc=document();data=doc.to_dict()
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('budget meshed'))
    data['max_solves']=3
    with pytest.raises(ValueError,match='before any field solve'):LineResolutionDocument.from_dict(data)
    with pytest.raises(ValueError,match='before any field solve'):execute_saved(doc.dumps(),max_evaluations=3)
    for bad in (True,2,17):
        data=doc.to_dict();data['max_solves']=bad
        with pytest.raises(ValueError):LineResolutionDocument.from_dict(data)


@pytest.fixture(scope='module')
def observed():
    base,outers=inputs();direct=assess_line_resolution(base,outer_documents=outers,tolerances=TOLERANCES)
    return document(),direct


def replay(monkeypatch,direct):
    results={row.input_json:row.result for row in direct.evaluations}
    monkeypatch.setattr(TransmissionLineDocument,'analyze',lambda self:results[self.dumps()])


def test_direct_saved_and_common_results_keep_every_matrix_and_input(observed,monkeypatch):
    doc,direct=observed;replay(monkeypatch,direct)
    saved=LineResolutionDocument.loads(doc.dumps()).analyze(max_evaluations=4)
    output=execute_saved(doc.dumps(),max_evaluations=4)
    assert output['status']=='complete' and output['error'] is None
    assert output['result']==resolution_record(saved)==resolution_record(direct)
    record=output['result'];assert record['completed'] and record['accepted']
    assert record['expected_evaluations']==len(record['evaluations'])==4
    for row,original in zip(record['evaluations'],direct.evaluations):
        assert row['input']==json.loads(original.input_json)
        assert set(row['quantities'])=={'R_ohm_per_m','L_internal_h_per_m','L_external_h_per_m',
                                      'C_f_per_m','C0_f_per_m','G_s_per_m'}
        for key,field in [('R_ohm_per_m','R'),('C_f_per_m','C'),('G_s_per_m','G')]:
            np.testing.assert_array_equal(row['quantities'][key],getattr(original.result,field))
    assert json.loads(json.dumps(output,allow_nan=False))==output


def test_completed_but_unaccepted_is_not_a_solver_failure(observed,monkeypatch):
    doc,direct=observed;replay(monkeypatch,direct)
    raw=doc.to_dict();raw['tolerances']={'C_f_per_m':dict(relative=0.,absolute=0.)}
    output=execute_saved(LineResolutionDocument.from_dict(raw).dumps(),max_evaluations=4)
    assert output['status']=='complete' and output['error'] is None
    assert output['result']['completed'] and not output['result']['accepted']
    assert not output['result']['comparisons'][0]['accepted']
    assert all(set(row['differences'])=={'C_f_per_m'} for row in output['result']['comparisons'])


@pytest.mark.parametrize('stage',['base','mesh','outer:0','outer:1'])
def test_failed_stage_preserves_completed_records_and_exact_input(observed,monkeypatch,stage):
    doc,direct=observed;values={row.input_json:row.result for row in direct.evaluations};calls=[]
    failed=next(row.input_json for row in direct.evaluations if row.stage==stage)
    def analyze(self):
        text=self.dumps();calls.append(text)
        if text==failed:raise ValueError('explicit field refusal')
        return values[text]
    monkeypatch.setattr(TransmissionLineDocument,'analyze',analyze)
    output=execute_saved(doc.dumps(),max_evaluations=4);result=output['result']
    index=[row.stage for row in direct.evaluations].index(stage)
    assert output['status']=='failed' and not result['completed'] and not result['accepted']
    assert len(result['evaluations'])==index and len(calls)==index+1
    assert output['error']==result['failure']==dict(stage=stage,input=json.loads(failed),
                                                    kind='ValueError',message='explicit field refusal')


def test_outer_physics_change_is_rejected_by_shared_preflight(monkeypatch):
    data=document().to_dict();data['outer_lines'][0]['cross_section']['traces'][0]['width']*=1.1
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('preflight meshed'))
    with pytest.raises(ValueError,match='physical geometry'):LineResolutionDocument.from_dict(data)
