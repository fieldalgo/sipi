# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Corner FEM samples retain strict inputs, original statistics and failures."""
from dataclasses import FrozenInstanceError
import json
import numpy as np
import pytest
from sipi import CrossSection, CornerFEMShapeLineQuantityStudyDocument as Document
from sipi.corner_fem_line import CornerFEMShapeTransmissionLineDocument as Line
from sipi.fem_shape_line import FEMShapeTransmissionLineDocument, FEMShapeLineError, FEMShapeCurrentError
from sipi.fem_shape_study import FEMShapeLineQuantityStudyDocument
from sipi.execution import normalize_saved, execute_saved
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject
from test_fem_shape_study import document as original, fake as old_fake
from test_fem_shape_study_physical import independent, serialized
from test_execution_record import ARTIFACTS
from test_project import project


def document(quantity='impedance_real',corner=2.5e-6,material=False,sampling=None):
    return Document(original(quantity,material=material,sampling=sampling),corner)


def fake(monkeypatch,fail_index=None):
    original_calls=old_fake(monkeypatch,fail_index);method=FEMShapeTransmissionLineDocument.analyze;calls=[]
    def analyze(doc):calls.append(doc.to_dict());return method(doc.line)
    monkeypatch.setattr(Line,'analyze',analyze)
    return calls,original_calls


@pytest.mark.parametrize('corner',[None,True,0.,-1.,float('nan'),float('inf'),'1e-6',1e-5])
def test_bad_corner_precedes_fields(corner,monkeypatch):
    raw=document().to_dict();raw['corner_size']=corner
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('unexpected mesh'))
    with pytest.raises(ValueError):Document.from_dict(raw)


@pytest.mark.parametrize('quantity',['impedance_real','attenuation','differential_forward_impedance_real','common_forward_impedance_real'])
def test_canonical_source_vectors_and_all_quantities(quantity,monkeypatch):
    doc=document(quantity);text=doc.dumps()
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('unexpected mesh'))
    assert normalize_saved(text)==Document.loads(text).dumps()==text
    np.testing.assert_array_equal(doc.samples(),doc.study.samples())
    calls,original_calls=fake(monkeypatch);result=doc.analyze()
    assert len(calls)==2 and not result.failed and result.summary is not None
    for row,raw,nested in zip(result.rows,calls,original_calls):
        assert raw['line']==nested and raw['corner_size']==doc.corner_size
        assert row.to_dict()['input']==raw and row.to_dict()['current_solver']=={'fake':True}
    assert result.input_json==text and result.quantity==quantity


@pytest.mark.parametrize('change',['extra','missing','schema','nested','quantity','frequency'])
def test_strict_wrapper_and_nested_admission(change,monkeypatch):
    raw=document().to_dict()
    if change=='extra':raw['result']={}
    elif change=='missing':del raw['study']
    elif change=='schema':raw['schema']='unsupported'
    elif change=='nested':raw['study']['study']['mesh']['corner_size']=1e-6
    elif change=='quantity':raw['study']['quantity']='z_diff'
    else:raw['study']['study']['material_evaluation']['frequency_hz']=0.
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('unexpected mesh'))
    with pytest.raises(ValueError):Document.from_dict(raw)


def test_snapshot_duplicate_and_original_rejection():
    doc=document();text=doc.dumps();raw=doc.to_dict();raw['corner_size']=999
    inner=doc.study;inner._data['quantity']='bad';assert doc.dumps()==text
    with pytest.raises(FrozenInstanceError):doc._data_json='{}'
    with pytest.raises(ValueError,match='duplicate'):
        Document.loads(text.replace('"corner_size":','"corner_size": 1e-6, "corner_size":',1))
    with pytest.raises(ValueError):FEMShapeLineQuantityStudyDocument.from_dict(doc.to_dict())
    with pytest.raises(TypeError):Document({},1e-6)


def test_budget_precedes_all_fields(monkeypatch):
    raw=document().to_dict();raw['study']['study']['sampling']['count']=3;doc=Document.from_dict(raw)
    calls,_=fake(monkeypatch)
    for run in (lambda:doc.analyze(max_evaluations=2),lambda:execute_saved(doc.dumps(),max_evaluations=2)):
        with pytest.raises(ValueError,match='max_evaluations'):run()
    assert calls==[]


def test_duplicate_failure_does_not_stop_later_rows(monkeypatch):
    doc=document();monkeypatch.setattr(Document,'samples',lambda self:np.full((3,1),.0004))
    calls,_=fake(monkeypatch,1);result=doc.analyze()
    assert len(calls)==3 and calls[0]==calls[1]==calls[2]
    assert result.failed==1 and result.summary is None and result.rows[-1].complete
    assert result.rows[1].phase=='extraction' and result.rows[1].error=='retained field failure'


def test_correlated_invalid_rows_keep_original_draws(monkeypatch):
    sampling=dict(kind='normal',count=8,seed=3,correlation=[[1.,.5],[.5,1.]],variables=[
        dict(name='width',mean=.0002,std=.0003),dict(name='loss',mean=.02,std=.06)])
    doc=document(material=True,sampling=sampling);calls,_=fake(monkeypatch);result=doc.analyze()
    assert 0<result.failed<8 and result.summary is None and len(calls)==8-result.failed
    np.testing.assert_array_equal([row.sample_values for row in result.rows],doc.samples())
    assert [row.index for row in result.rows]==list(range(8))


@pytest.fixture(scope='module',params=[('impedance_real',5e-6),('differential_forward_impedance_real',5e-6),
    ('impedance_real',2.5e-6),('differential_forward_impedance_real',2.5e-6)],ids=['scalar-default','pair-default','scalar-corner','pair-corner'])
def actual(request):
    quantity,corner=request.param;doc=document(quantity,corner)
    return doc,doc.analyze()


def test_actual_geometry_samples_keep_corner_and_independent_values(actual,record_property):
    doc,result=actual;assert not result.failed and len(result.rows)==2
    quantity=doc.study.to_dict()['quantity']
    for row in result.rows:
        assert row.value==pytest.approx(independent(row.result,quantity),rel=1e-10,abs=0)
        assert Line.loads(row.input_json).corner_size==doc.corner_size
        assert row.result.input_json==row.input_json and len(row.result.current_factors.samples)==8*(len(row.result.names)+1)
    record_property('corner_fem_study',json.dumps(dict(quantity=quantity,corner=doc.corner_size,observed=serialized(result)),allow_nan=False))


def test_actual_common_execution_project_and_edited_control(actual,monkeypatch):
    doc,result=actual
    def replay(self,**options):
        assert self.dumps()==doc.dumps()
        return result
    monkeypatch.setattr(Document,'analyze',replay)
    request=SavedExecutionRequest(doc.dumps());receipt=request.run()
    assert receipt['execution']['status']=='complete' and receipt['execution']['result']==result.to_dict()
    record=SavedExecutionRecord(request,receipt,run_id='corner:samples',artifacts=ARTIFACTS)
    attached=project(request).attach_record('a',record,select=True)
    monkeypatch.setattr(Document,'analyze',lambda *a,**k:pytest.fail('reopening solved'))
    reopened=SavedProject.loads(attached.dumps());assert reopened.current_record('a').receipt==receipt
    changed=reopened.update_design('a',SavedExecutionRequest(Document(doc.study,doc.corner_size/2).dumps()))
    assert changed.current_record('a') is None and changed.design('a')['records']==[record.to_dict()]


def test_actual_material_attenuation_keeps_each_sample(record_property):
    doc=document('attenuation',material=True);result=doc.analyze();assert not result.failed
    for row,loss in zip(result.rows,(.01,.03)):
        assert row.value==pytest.approx(independent(row.result,'attenuation'),rel=1e-10,abs=0)
        assert row.to_dict()['material_evaluation']['materials']['dielectric']['parameters']['tan_delta']==loss
        np.testing.assert_allclose(row.result.G,2*np.pi*2e9*loss*row.result.C,rtol=1e-12,atol=0)
    record_property('corner_fem_material',json.dumps(serialized(result),allow_nan=False))


def test_partial_failure_keeps_corner_input_and_later_attempts(actual,monkeypatch):
    doc,observed=actual;first,last=observed.rows;current=first.result.current_factors
    samples=np.array([doc.samples()[0],doc.samples()[0],doc.samples()[1]])
    monkeypatch.setattr(Document,'samples',lambda self:samples.copy());calls=[]
    by_input={row.input_json:row.result for row in observed.rows}
    def analyze(value):
        index=len(calls);calls.append(value.dumps())
        if index==1:
            cause=FEMShapeCurrentError('sample failed',stage='capacitance-differences',base=current.base,
                extension_parts=current.extension_parts,samples=current.samples[:1],request=(0,0,0,1,current.step_m))
            raise FEMShapeLineError(cause,stage='current',input_json=value.dumps(),factors=None,mesh_observation=first.result.mesh_observation)
        return by_input[value.dumps()]
    monkeypatch.setattr(Line,'analyze',analyze)
    request=SavedExecutionRequest(doc.dumps());receipt=request.run();out=receipt['execution'];rows=out['result']['rows']
    assert out['status']=='incomplete' and out['result']['summary'] is None and rows[2]['phase']=='complete'
    assert calls==[first.input_json,first.input_json,last.input_json]
    details=rows[1]['cause_details'];assert details['input']==json.loads(first.input_json)
    assert len(details['partial_current']['samples'])==1 and details['current_solver'] is None
    record=SavedExecutionRecord(request,receipt,run_id='corner:partial-samples',artifacts=ARTIFACTS)
    assert SavedExecutionRecord.loads(record.dumps()).receipt==receipt


def test_fixed_pitch_and_corner_are_both_preserved(monkeypatch):
    from sipi.study import ImpedanceStudyDocument
    from test_fem_shape_study import source, MESH
    raw=original('differential_forward_impedance_real').to_dict()
    nested=ImpedanceStudyDocument('coupled_stripline',source(True).to_dict()['parameters'],
        quantity='z_diff_forward',frequency=2e9,materials={},mesh=MESH,fixed_pitch_m=.0007,
        sampling=source(True).to_dict()['sampling'])
    raw['study']=nested.to_dict();doc=Document(FEMShapeLineQuantityStudyDocument.from_dict(raw),2.5e-6)
    calls,_=fake(monkeypatch);result=doc.analyze();assert not result.failed
    for value in calls:
        section=Line.from_dict(value).cross_section.section
        traces=[t for t in section.traces if not t.ground]
        assert traces[1].x-traces[0].x==pytest.approx(.0007,rel=1e-14,abs=0)
        assert value['corner_size']==2.5e-6
