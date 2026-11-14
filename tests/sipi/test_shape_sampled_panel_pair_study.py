# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit full-frequency rows retain original samples and atomic failures."""
from types import SimpleNamespace
from dataclasses import FrozenInstanceError
import json
import numpy as np
import pytest
from sipi import CrossSection
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.panel_shape_conductor import PanelShapeCurrentError
from sipi.shape_panel_line import ShapePanelTransmissionLineDocument,ShapePanelLineError
from sipi.shape_sampled_panel_pair_study import ShapeSampledPanelForwardPairStudyDocument as Document
from sipi.sampled_panel_pair_study import SampledPanelForwardPairStudyDocument
from sipi.execution import normalize_saved,execute_saved
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from test_execution_record import ARTIFACTS
from test_sampled_panel_pair_study import document as old_document
from test_layered_sampled_panel_study import document as coated_document
from test_sampled_panel_pair_goal import synthetic as old_synthetic,targets,F
from test_panel_pair_study import expected_statistics,Q


def document(sampling=None,frequencies=F,*,coated=False):
    nested=coated_document(4) if coated else old_document(sampling,frequencies)
    if coated:
        raw=nested.to_dict();raw['frequency_hz']=list(frequencies)
        raw['study']['material_evaluation']['frequency_hz']=float(frequencies[0])
        if sampling is not None:raw['study']['sampling']=sampling
        nested=SampledPanelForwardPairStudyDocument.from_dict(raw)
    return Document(nested)


def synthetic(monkeypatch,*,lossless=False,fail_at=None,interrupt=False):
    old_synthetic(monkeypatch,lossless=lossless);previous=PanelTransmissionLineDocument.analyze;calls=[]
    def analyze(self):
        calls.append(self.dumps())
        if len(calls)==fail_at:
            if interrupt:raise KeyboardInterrupt()
            cause=PanelShapeCurrentError('original failed current batch',samples=())
            raise ShapePanelLineError(cause,stage='current',input_json=self.dumps(),factors=None,settings=self.current_options) from cause
        result=previous(self.line);result.input_json=self.dumps()
        # Deliberately synthetic metadata, used only to test method transport.
        parts=np.array([np.eye(2),2*np.eye(2),3*np.eye(2)])
        result.current_factors=SimpleNamespace(ground_trace_names=(),C0=np.eye(2)*1e-11,
            parts=parts,current_integrals=np.array([[1.,0.],[0.,1.],[-1.,-1.]]),
            diagnostics={'transport_stub':1.},step_m=1e-8,
            step_parts=np.array([parts,parts]),boundary_step_parts=np.array([parts,parts]),samples=())
        result.panel_settings=self.current_options;return result
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',analyze)
    return calls


@pytest.mark.parametrize('coated',[False,True])
@pytest.mark.parametrize('lossless',[False,True])
def test_one_batch_per_manufactured_row_and_independent_statistics(monkeypatch,coated,lossless):
    calls=synthetic(monkeypatch,lossless=lossless);doc=document(coated=coated);result=doc.analyze(max_evaluations=4)
    assert not result.failed and len(calls)==len(result.rows)==4 and result.frequencies==tuple(F)
    for row,values in zip(result.rows,doc.samples()):
        np.testing.assert_allclose(row.values,targets(values[0]/.3e-3,values[1]/.2e-3,lossless=lossless),rtol=1e-12,atol=0)
        assert row.input_json==calls[row.index] and row.result.input_json==row.input_json
        assert json.loads(row.input_json)['line']['line']['frequency_hz']==list(F)
        assert row.to_dict()['current_solver']['diagnostics']=={'transport_stub':1.}
    for j in range(len(F)):
        for i,q in enumerate(Q):
            for key,value in expected_statistics([r.values[j][i] for r in result.rows]).items():
                assert result.summary[q][j][key]==pytest.approx(value,rel=1e-12)
    with pytest.raises(FrozenInstanceError):result.rows[0].index=1
    with pytest.raises(TypeError):result.summary[Q[0]][0]['mean']=0


def test_maximum_grid_preserves_whole_row_budget(monkeypatch):
    calls=synthetic(monkeypatch);result=document(frequencies=np.geomspace(F[0],F[-1],64)).analyze(max_evaluations=4)
    assert len(calls)==4 and not result.failed and len(result.summary[Q[0]])==64


def test_field_free_roundtrip_and_copy_isolation(monkeypatch):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('normalize meshed'))
    doc=document(coated=True);text=doc.dumps();assert normalize_saved(text)==text==Document.loads(text).dumps()
    raw=doc.to_dict();raw['study']['frequency_hz'].reverse();assert doc.dumps()==text
    with pytest.raises(ValueError):SampledPanelForwardPairStudyDocument.loads(text)


@pytest.mark.parametrize('where',['root','study','panel','sampling'])
@pytest.mark.parametrize('kind',['missing','extra'])
def test_exact_nested_keys(where,kind):
    data=document().to_dict();d=data['study'];target={'root':data,'study':d,'panel':d['panel'],'sampling':d['study']['sampling']}[where]
    if kind=='missing':target.pop(next(iter(target)))
    else:target['extra']=1
    with pytest.raises(ValueError):Document.from_dict(data)


@pytest.mark.parametrize('kind',['schema','duplicate','nan','step','frequency','anchor','old-source'])
def test_invalid_contract(kind):
    data=document().to_dict();text=json.dumps(data)
    if kind=='schema':data['schema']='sipi.shape-sampled-panel-forward-pair-study/2'
    if kind=='duplicate':text=text.replace('"step_fraction": 0.001','"step_fraction": 0.001, "step_fraction": 0.001')
    if kind=='nan':text=text.replace('"step_fraction": 0.001','"step_fraction": NaN')
    if kind=='step':data['step_fraction']=True
    if kind=='frequency':data['study']['frequency_hz']=[float(F[0])]
    if kind=='anchor':data['study']['frequency_hz']=[float(F[1]),float(F[2])]
    if kind=='old-source':data['study']=data['study']['study']
    if kind not in ('duplicate','nan'):text=json.dumps(data)
    with pytest.raises(ValueError):Document.loads(text)


@pytest.mark.parametrize('phase',['parameters','materials','input','extraction','diagnostic'])
def test_atomic_failure_preserves_partial_current_and_later_rows(monkeypatch,phase):
    import sipi.sampled_panel_pair_study as shared
    import sipi.shape_sampled_panel_pair_study as module
    calls=synthetic(monkeypatch,fail_at=2 if phase=='extraction' else None)
    if phase in ('parameters','materials','input'):
        owner=module if phase=='input' else shared
        name={'parameters':'_parameters','materials':'_sample_material','input':'_sampled_study_line'}[phase]
        previous=getattr(owner,name);seen=[]
        def fail(*a,**k):
            seen.append(1)
            if len(seen)==2:raise ArithmeticError('original failed sample')
            return previous(*a,**k)
        monkeypatch.setattr(owner,name,fail)
    if phase=='diagnostic':
        previous=ShapePanelTransmissionLineDocument.analyze
        def fail(self):
            result=previous(self)
            if len(calls)==2:
                def bad():raise ArithmeticError('original failed sample')
                result.characteristic=bad
            return result
        monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',fail)
    result=document().analyze(max_evaluations=4);row=result.rows[1]
    assert result.failed==1 and result.summary is None and len(result.rows)==4
    assert row.phase==phase and row.values is None and all(result.rows[i].complete for i in (0,2,3))
    if phase=='extraction':
        assert row.cause_details['partial_current']['samples']==[]
        assert row.cause_details['input']==json.loads(row.input_json)
        copy=row.cause_details;copy['message']='changed';assert row.cause_details['message']=='original failed current batch'
    if phase=='diagnostic':assert row.to_dict()['current_solver']['diagnostics']=={'transport_stub':1.}


@pytest.mark.parametrize('index',[0,1,2])
def test_bad_single_frequency_invalidates_entire_row(monkeypatch,index):
    synthetic(monkeypatch);previous=ShapePanelTransmissionLineDocument.analyze
    def broken(self):
        result=previous(self);c=result.characteristic();m=c.mixed_mode();matrix=m.z_characteristic.copy();matrix[index,0,0]=np.nan
        result.characteristic=lambda:SimpleNamespace(basis=c.basis,names=c.names,frequency=c.frequency,
            mixed_mode=lambda:SimpleNamespace(basis=m.basis,names=m.names,frequency=m.frequency,z_characteristic=matrix))
        return result
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',broken)
    result=document().analyze(max_evaluations=4)
    assert result.failed==4 and result.summary is None
    assert all(r.phase=='diagnostic' and r.values is None and r.result is not None for r in result.rows)


def test_correlated_invalid_and_duplicate_sample_vectors_are_retained(monkeypatch):
    for sampling in (dict(kind='normal',count=8,seed=3,correlation=[[1.,.5],[.5,1.]],variables=[
            dict(name='left_width',mean=.2e-3,std=.3e-3),dict(name='gap',mean=.2e-3,std=.3e-3)]),
            dict(kind='sweep',count=4,variables=[dict(name='left_width',lower=.3e-3,upper=float(np.nextafter(.3e-3,np.inf)))])):
        calls=synthetic(monkeypatch);doc=document(sampling);result=doc.analyze(max_evaluations=8)
        np.testing.assert_array_equal([r.sample_values for r in result.rows],doc.samples())
        assert len(calls)==len(result.rows)-result.failed
        if sampling['kind']=='normal':assert 0<result.failed<8
        else:assert len(np.unique(doc.samples()))<4 and len(calls)==4


def test_sampled_offset_collision_is_one_failed_row(monkeypatch):
    calls=synthetic(monkeypatch)
    result=document(dict(kind='sweep',count=4,variables=[dict(name='gap',lower=1e-8,upper=.2e-3)])).analyze(max_evaluations=4)
    assert result.failed==1 and len(calls)==3 and result.rows[0].phase=='input' and result.summary is None
    assert 'touch or overlap' in result.rows[0].error and all(r.complete for r in result.rows[1:])


def test_fixed_pitch_and_material_leaf_preserved_across_grid(monkeypatch):
    from sipi.dielectric import DebyeDielectric,dielectric_to_dict
    synthetic(monkeypatch);raw=old_document().to_dict();study=raw['study']
    study['schema']='sipi.impedance-study/4';study['fixed_pitch_m']=.95e-3
    study['material_evaluation']['materials']={'substrate':dielectric_to_dict(DebyeDielectric(3.,(.7,),(1e9,)))}
    study['material_variables']={'strength':dict(region='substrate',path=['strengths',0])}
    study['sampling']['variables']=[dict(name='left_width',lower=.4e-3,upper=.8e-3),dict(name='strength',lower=.5,upper=.9)]
    doc=Document(SampledPanelForwardPairStudyDocument.from_dict(raw));result=doc.analyze(max_evaluations=4)
    assert not result.failed
    for row,(width,strength) in zip(result.rows,doc.samples()):
        line=json.loads(row.input_json)['line']['line'];traces=line['cross_section']['traces']
        assert traces[1]['x']-traces[0]['x']==pytest.approx(.95e-3,rel=1e-12)
        assert line['frequency_hz']==list(F) and line['materials']['substrate']['parameters']['strengths']==[strength]


@pytest.mark.parametrize('failure',[None,2])
def test_complete_incomplete_receipts_and_budget(monkeypatch,failure):
    calls=synthetic(monkeypatch,fail_at=failure);request=SavedExecutionRequest(document().dumps(),max_evaluations=4)
    with pytest.raises(ValueError,match='before any solve'):execute_saved(document().dumps(),max_evaluations=3)
    assert not calls
    receipt=request.run();out=receipt['execution']
    assert out['status']==('complete' if failure is None else 'incomplete')
    assert out['result']['frequencies_hz']==list(F) and out['result']['count']==4
    saved=SavedExecutionRecord(request,receipt,run_id='shape-grid:study',artifacts=ARTIFACTS)
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('restore solved'))
    assert SavedExecutionRecord.loads(saved.dumps()).receipt==receipt


def test_interrupt_propagates(monkeypatch):
    calls=synthetic(monkeypatch,fail_at=2,interrupt=True)
    with pytest.raises(KeyboardInterrupt):document().analyze(max_evaluations=4)
    assert len(calls)==2
