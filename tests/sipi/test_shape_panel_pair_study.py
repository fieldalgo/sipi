# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Shape-current samples preserve statistics, invalid rows and every cause."""
import json
from dataclasses import FrozenInstanceError
import numpy as np
import pytest

from sipi import CrossSection
from sipi.execution import execute_saved,normalize_saved
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.panel_pair_study import PanelForwardPairStudyDocument
from sipi.shape_panel_pair_study import ShapePanelForwardPairStudyDocument
from sipi.shape_panel_line import ShapePanelTransmissionLineDocument
from test_panel_pair_study import document as legacy,expected_statistics,Q
from test_layered_panel_study import document as coated
from test_shape_panel_pair_goal_document import synthetic_transport
from test_panel_pair_goal import quantities
from test_execution_record import ARTIFACTS


def document(sampling=None,*,layered=False):
    old=coated() if layered else legacy(sampling)
    if layered and sampling is not None:
        raw=old.to_dict();raw['study']['sampling']=sampling
        old=PanelForwardPairStudyDocument.from_dict(raw)
    return ShapePanelForwardPairStudyDocument(old)


@pytest.mark.parametrize('layered',[False,True])
def test_one_extraction_per_pair_and_independent_statistics(monkeypatch,layered):
    calls=synthetic_transport(monkeypatch);doc=document(layered=layered)
    result=doc.analyze(max_evaluations=8)
    assert not result.failed and len(calls)==len(result.rows)==len(doc.samples())
    for row,values in zip(result.rows,doc.samples()):
        np.testing.assert_allclose(row.values,quantities(values[0]/.3e-3,values[1]/.2e-3),rtol=1e-12)
        assert row.input_json==calls[row.index] and row.result.input_json==row.input_json
        assert row.cause_details is None and row.to_dict()['current_solver']['diagnostics']=={'transport_stub':1.}
    for i,q in enumerate(Q):
        for key,value in expected_statistics([r.values[i] for r in result.rows]).items():
            assert result.summary[q][key]==pytest.approx(value,rel=1e-12)
    with pytest.raises(TypeError):result.summary[Q[0]]['mean']=0
    with pytest.raises(FrozenInstanceError):result.rows[0].index=999


def test_normalization_and_snapshots_are_field_free(monkeypatch):
    forbidden=lambda *a,**k:pytest.fail('normalization solved')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',forbidden)
    doc=document(layered=True);text=doc.dumps()
    assert normalize_saved(text)==text==ShapePanelForwardPairStudyDocument.loads(text).dumps()
    raw=doc.to_dict();raw['step_fraction']=.01;raw['study']['conductor']['reference']['coatings'].clear()
    assert doc.dumps()==text and doc.study.dumps()==coated().dumps()
    with pytest.raises(ValueError):PanelForwardPairStudyDocument.loads(text)


@pytest.mark.parametrize('where',['root','study','panel','sampling','conductor','coating'])
@pytest.mark.parametrize('kind',['missing','extra'])
def test_strict_nested_keys(where,kind):
    data=document(layered=True).to_dict();d=data['study']
    target={'root':data,'study':d,'panel':d['panel'],'sampling':d['study']['sampling'],
            'conductor':d['conductor'],'coating':d['conductor']['reference']['coatings'][0]}[where]
    if kind=='missing':target.pop(next(iter(target)))
    else:target['extra']=1
    with pytest.raises(ValueError):ShapePanelForwardPairStudyDocument.from_dict(data)


@pytest.mark.parametrize('kind',['schema','duplicate','nan','nested','step-bool','step-zero','step-large'])
def test_invalid_input_contracts(kind):
    data=document().to_dict();text=json.dumps(data)
    if kind=='schema':data['schema']='sipi.shape-panel-forward-pair-study/2'
    if kind=='duplicate':text=text.replace('"step_fraction": 0.001','"step_fraction": 0.001, "step_fraction": 0.001')
    if kind=='nan':text=text.replace('"step_fraction": 0.001','"step_fraction": NaN')
    if kind=='nested':data['study']=data['study']['study']
    if kind=='step-bool':data['step_fraction']=True
    if kind=='step-zero':data['step_fraction']=0
    if kind=='step-large':data['step_fraction']=.1
    if kind not in ('duplicate','nan'):text=json.dumps(data)
    with pytest.raises(ValueError):ShapePanelForwardPairStudyDocument.loads(text)


def test_duplicate_representable_samples_are_retained(monkeypatch):
    calls=synthetic_transport(monkeypatch);low=.3e-3
    doc=document(dict(kind='sweep',count=4,variables=[dict(name='left_width',lower=low,upper=float(np.nextafter(low,np.inf)))]))
    assert len(np.unique(doc.samples()[:,0]))<4
    result=doc.analyze(max_evaluations=4)
    assert len(calls)==len(result.rows)==4 and not result.failed
    np.testing.assert_array_equal([r.sample_values for r in result.rows],doc.samples())


def test_correlated_invalid_rows_remain_in_the_original_order(monkeypatch):
    calls=synthetic_transport(monkeypatch)
    doc=document(dict(kind='normal',count=8,seed=3,correlation=[[1.,.5],[.5,1.]],variables=[
        dict(name='left_width',mean=.2e-3,std=.3e-3),dict(name='gap',mean=.2e-3,std=.3e-3)]))
    result=doc.analyze(max_evaluations=8)
    assert 0<result.failed<8 and result.summary is None
    assert len(calls)==8-result.failed
    for i,(row,values) in enumerate(zip(result.rows,doc.samples())):
        assert row.index==i and row.sample_values==tuple(values)
        assert row.complete==(values[0]>0 and values[1]>0)
        if not row.complete:assert row.phase=='input' and row.values is None


def test_sampled_offset_collision_does_not_discard_later_rows(monkeypatch):
    calls=synthetic_transport(monkeypatch)
    doc=document(dict(kind='sweep',count=4,variables=[dict(name='gap',lower=1e-8,upper=.2e-3)]))
    result=doc.analyze(max_evaluations=4)
    assert result.failed==1 and len(calls)==3 and len(result.rows)==4 and result.summary is None
    assert result.rows[0].phase=='input' and 'touch or overlap' in result.rows[0].error
    assert all(r.complete for r in result.rows[1:])


@pytest.mark.parametrize('phase',['parameters','materials','input','extraction','diagnostic'])
def test_failure_preserves_original_phase_and_following_rows(monkeypatch,phase):
    import sipi.panel_pair_study as shared
    import sipi.shape_panel_pair_study as module
    doc=document();calls=synthetic_transport(monkeypatch,fail_at=2 if phase=='extraction' else None)
    if phase in ('parameters','materials','input'):
        owner=module if phase=='input' else shared
        name={'parameters':'_parameters','materials':'_sample_material','input':'_panel_study_line'}[phase]
        original=getattr(owner,name);seen=[]
        def fail_second(*a,**k):
            seen.append(1)
            if len(seen)==2:raise ArithmeticError('original sampled failure')
            return original(*a,**k)
        monkeypatch.setattr(owner,name,fail_second)
    if phase=='diagnostic':
        original=ShapePanelTransmissionLineDocument.analyze
        def bad_diagnostic(self):
            line=original(self)
            if len(calls)==2:
                def fail():raise ArithmeticError('original sampled failure')
                line.characteristic=fail
            return line
        monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',bad_diagnostic)
    result=doc.analyze(max_evaluations=4);row=result.rows[1]
    assert result.failed==1 and len(result.rows)==4 and result.summary is None and row.phase==phase
    assert row.values is None and all(result.rows[i].complete for i in (0,2,3))
    saved=row.to_dict()
    if phase=='extraction':
        assert row.cause_details['input']==json.loads(row.input_json)
        assert row.cause_details['partial_current']['samples']==[]
        changed=row.cause_details;changed['message']='mutated'
        assert row.cause_details['message']=='original current refusal'
    elif phase=='diagnostic':assert saved['current_solver']['diagnostics']=={'transport_stub':1.}


@pytest.mark.parametrize('fail_at',[None,2])
def test_common_complete_incomplete_receipts_restore_without_fields(monkeypatch,fail_at):
    synthetic_transport(monkeypatch,fail_at=fail_at);doc=document()
    request=SavedExecutionRequest(doc.dumps(),max_evaluations=4);receipt=request.run()
    out=receipt['execution'];assert out['status']==('complete' if fail_at is None else 'incomplete')
    assert out['error'] is None and out['result']['failed']==(0 if fail_at is None else 1)
    saved=SavedExecutionRecord(request,receipt,run_id='shape-study:synthetic',artifacts=ARTIFACTS)
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('restore solved'))
    restored=SavedExecutionRecord.loads(saved.dumps())
    assert restored.receipt==receipt and restored.prepare().to_dict()==request.to_dict()


def test_budget_precedes_every_field_and_interrupt_propagates(monkeypatch):
    calls=synthetic_transport(monkeypatch,fail_at=2,interrupt=True);doc=document()
    with pytest.raises(ValueError,match='before any solve'):doc.analyze(max_evaluations=3)
    with pytest.raises(ValueError,match='before any solve'):execute_saved(doc.dumps(),max_evaluations=3)
    assert not calls
    with pytest.raises(KeyboardInterrupt):doc.analyze(max_evaluations=4)
    assert len(calls)==2
