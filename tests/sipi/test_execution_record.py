# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Bound saved results, no implicit replay, and explicit declaration limits."""
from dataclasses import FrozenInstanceError
import copy
import hashlib
import json
import numpy as np
import pytest
from sipi import CrossSection,LumpedNetworkDocument
from sipi.execution import execute_saved,normalize_saved,saved_schemas
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord as Record
from sipi.tensor_dielectric_fit_document import TensorDebyeFitDocument
from sipi.dielectric import TensorDebyeDielectric

# Deliberately synthetic declarations, never a claim about installed bytes.
ARTIFACTS=[dict(component='sipi',version='example-only',kind='wheel',sha256='1'*64),
           dict(component='galerkin',version='example-only',kind='wheel',sha256='2'*64)]


def rehash(data):
    body={k:v for k,v in data.items() if k!='content_sha256'}
    data['content_sha256']=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')).hexdigest()
    return data


def lumped():
    return SavedExecutionRequest(LumpedNetworkDocument([0,1e9],resistance=10,port_names=('입력','출력')).dumps())


def record(request=None,**options):
    request=lumped() if request is None else request
    return Record(request,request.run(),run_id=options.pop('run_id','host:run-1'),artifacts=options.pop('artifacts',ARTIFACTS),**options)


@pytest.mark.parametrize('mismatch',[False,True])
def test_real_tensor_fit_roundtrip_retains_completed_sample_decision(mismatch):
    f=np.geomspace(1e6,1e12,17);model=TensorDebyeDielectric([2,3],[[4,.5],[.25,3]],[1e8,1e10],[0,.7],.31)
    eps=model.permittivity(f)
    doc=TensorDebyeFitDocument(f,eps_real=eps.real,eps_loss=-eps.imag+(.01*np.eye(2) if mismatch else 0),
        relaxation_hz=model.relaxation_hz,angles_rad=model.angles_rad,eps_inf_angle_rad=.31,max_error=1e-8)
    request=SavedExecutionRequest(doc.dumps(),max_evaluations=len(f));receipt=request.run()
    saved=Record(request,receipt,run_id='host:fit-1',artifacts=ARTIFACTS)
    restored=Record.loads(saved.dumps())
    assert restored.dumps()==saved.dumps() and restored.receipt==receipt
    assert restored.receipt['execution']['status']=='complete'
    assert restored.receipt['execution']['result']['accepted'] is (not mismatch)
    assert restored.prepare().to_dict()==request.to_dict()
    assert restored.prepare().run()==receipt


def test_real_incomplete_study_preserves_original_failed_rows_without_fields(monkeypatch):
    from sipi.study import ImpedanceStudyDocument
    doc=ImpedanceStudyDocument('stripline',dict(width=.5e-3,plane_spacing=1e-3,eps_r=4),quantity='z0',
        sampling=dict(kind='normal',count=2,seed=71,correlation=[[1.]],variables=[dict(name='width',mean=-1e-3,std=1e-12)]))
    def forbidden(*a,**k):pytest.fail('invalid sampled geometry reached fields')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    request=SavedExecutionRequest(doc.dumps(),max_evaluations=2);receipt=request.run()
    assert receipt['execution']['status']=='incomplete'
    assert receipt['execution']['result']['failed']==2 and receipt['execution']['result']['summary'] is None
    restored=Record.loads(Record(request,receipt,run_id='host:study-1',artifacts=ARTIFACTS).dumps())
    assert restored.receipt==receipt
    assert all(row['parameters']['width']<0 for row in restored.receipt['execution']['result']['rows'])


def test_real_failed_goal_preserves_error_and_search_history():
    from sipi.design_document import ImpedanceDesignDocument
    doc=ImpedanceDesignDocument('stripline',dict(width=.15e-3,plane_spacing=1e-3,eps_r=4),
        variable='width',bounds=[.1e-3,.2e-3],target=1,tolerance=.001,max_evaluations=8,
        mesh=dict(edge_size=40e-6,far_size=.25e-3,grade=.3))
    request=SavedExecutionRequest(doc.dumps(),max_evaluations=8);receipt=request.run()
    assert receipt['execution']['status']=='failed' and receipt['execution']['result'] is None
    original=copy.deepcopy(receipt['execution']['error'])
    assert 'history' in original
    restored=Record.loads(Record(request,receipt,run_id='host:goal-1',artifacts=ARTIFACTS).dumps())
    assert restored.receipt['execution']['error']==original


def test_exact_source_text_preserves_utf8_cap_before_canonical_expansion():
    doc=LumpedNetworkDocument([0,1e9],resistance=10,port_names=('입력','출력'))
    source=json.dumps(doc.to_dict(),separators=(',',':'),ensure_ascii=False);size=len(source.encode('utf-8'))
    assert size>len(source)
    request=SavedExecutionRequest(source,max_input_bytes=size)
    assert len(request.input_json.encode('utf-8'))>size
    receipt=request.run();saved=Record(request,receipt,run_id='host:compact-1',artifacts=ARTIFACTS)
    restored=Record.loads(saved.dumps())
    assert restored.to_dict()['source_text']==source
    assert restored.prepare().source_text==source and restored.prepare().max_input_bytes==size
    assert restored.prepare().run()==receipt


def test_load_prepare_never_execute_optimize_or_mesh(monkeypatch):
    import sipi.tensor_dielectric_fit as fit_module
    request=lumped();saved=record(request);text=saved.dumps()
    def forbidden(*a,**k):pytest.fail('record loading/preparation performed computation')
    monkeypatch.setattr(SavedExecutionRequest,'run',forbidden)
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    monkeypatch.setattr(fit_module,'nnls',forbidden)
    restored=Record.loads(text);prepared=restored.prepare()
    assert prepared.to_dict()==request.to_dict() and restored.dumps()==text


def test_all_registered_inputs_prepare_from_structural_records_without_fields(monkeypatch):
    from test_execution import documents
    docs=documents();assert len(docs)==len(saved_schemas())==115
    assert {doc.to_dict()['schema'] for doc in docs} == set(saved_schemas())
    def forbidden(*a,**k):pytest.fail('structural record preparation reached fields')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    monkeypatch.setattr(SavedExecutionRequest,'run',forbidden)
    for i,doc in enumerate(docs):
        request=SavedExecutionRequest(doc.dumps())
        # A structural failure fixture, not an assertion that these calculations ran.
        receipt=dict(schema='sipi.execution-receipt/1',request=request.to_dict(),execution=dict(
            schema='sipi.execution/1',input=doc.to_dict(),status='failed',result=None,
            error=dict(type='NotExecutedFixture',message='structural replay fixture only')))
        saved=Record(request,receipt,run_id=f'fixture:{i}',artifacts=ARTIFACTS)
        assert Record.loads(saved.dumps()).prepare().to_dict()==request.to_dict()


def test_snapshot_detachment_immutability_and_explicit_host_run_identity():
    request=lumped();receipt=request.run();items=copy.deepcopy(ARTIFACTS)
    first=Record(request,receipt,run_id='host:1',artifacts=items)
    second=Record(request,receipt,run_id='host:2',artifacts=items)
    assert first.receipt==second.receipt and first.run_id!=second.run_id
    assert first.to_dict()['content_sha256']!=second.to_dict()['content_sha256']
    receipt['execution']['result'].clear();items[0]['version']='changed'
    raw=first.to_dict();raw['source_text']='{}';raw['receipt']['execution']['result'].clear()
    artifacts=first.artifacts;artifacts['items'][0]['sha256']='9'*64
    assert first.prepare().to_dict()==request.to_dict()
    assert first.receipt['execution']['result'] and first.artifacts!=artifacts
    with pytest.raises(FrozenInstanceError):first._data_json='{}'
    assert first.artifacts['verification']=='host-declared'
    assert [x['component'] for x in first.artifacts['items']]==['galerkin','sipi']


def test_checksums_are_not_artifact_verification_or_authentication():
    saved=record();raw=saved.to_dict();raw['artifacts']['items'][-1]['sha256']='a'*64
    with pytest.raises(ValueError,match='digest'):Record.from_dict(raw)
    # Anyone can recompute the hash: declarations remain explicitly unverified.
    altered=Record.from_dict(rehash(raw))
    assert altered.artifacts['verification']=='host-declared'
    assert altered.artifacts['items'][-1]['sha256']=='a'*64


def test_record_utf8_byte_boundary_canonical_limits_and_not_an_engine_input():
    saved=record();text=saved.dumps();size=len(text.encode('utf-8'));assert size>len(text)
    assert Record.loads(text,max_record_bytes=size).dumps()==text
    assert Record.from_dict(saved.to_dict(),max_record_bytes=size).dumps()==text
    with pytest.raises(ValueError,match='max_record_bytes'):Record.loads(text,max_record_bytes=size-1)
    with pytest.raises(ValueError,match='max_record_bytes'):Record.from_dict(saved.to_dict(),max_record_bytes=size-1)
    with pytest.raises(ValueError,match='max_record_bytes'):Record.loads(' '+text,max_record_bytes=size)
    with pytest.raises(ValueError,match='unsupported saved schema'):normalize_saved(text)
    with pytest.raises(ValueError,match='unsupported saved schema'):execute_saved(text)


@pytest.mark.parametrize('limit',[True,0,-1,1.5,64*1024*1024+1])
def test_invalid_record_limits(limit):
    saved=record()
    with pytest.raises(ValueError):Record.loads(saved.dumps(),max_record_bytes=limit)
    with pytest.raises(ValueError):Record.from_dict(saved.to_dict(),max_record_bytes=limit)


@pytest.mark.parametrize('run_id',['','a'*129,'with space','path/name','한글',True,None])
def test_invalid_host_run_ids(run_id):
    with pytest.raises(ValueError):record(run_id=run_id)


@pytest.mark.parametrize('kind',['empty','many','missing_sipi','duplicate','component','version','kind','digest','extra','missing','nonobject'])
def test_invalid_artifact_declarations(kind):
    items=copy.deepcopy(ARTIFACTS)
    if kind=='empty':items=[]
    if kind=='many':items=items*33
    if kind=='missing_sipi':items=items[1:]
    if kind=='duplicate':items.append(dict(items[0]))
    if kind=='component':items[0]['component']='../sipi'
    if kind=='version':items[0]['version']='with space'
    if kind=='kind':items[0]['kind']='verified'
    if kind=='digest':items[0]['sha256']='A'*64
    if kind=='extra':items[0]['path']='local'
    if kind=='missing':items[0].pop('sha256')
    if kind=='nonobject':items[0]=[]
    with pytest.raises(ValueError):record(artifacts=items)


@pytest.mark.parametrize('field',['schema','run_id','source_text','receipt','artifacts','content_sha256'])
def test_missing_record_keys(field):
    raw=record().to_dict();raw.pop(field)
    with pytest.raises(ValueError):Record.from_dict(raw)


@pytest.mark.parametrize('kind',['schema','run','source','receipt_schema','request_id','input_hash','request_input',
 'controls','controls_bool','output_schema','output_input','output_input_bool','status','complete_null_result','complete_error',
 'incomplete_null_result','failed_result','failed_null_error','failed_no_type','failed_no_message','artifact_schema','artifact_verified','artifact_order','extra'])
def test_rehashed_structural_mismatches_still_reject(kind):
    raw=record().to_dict();receipt=raw['receipt'];output=receipt['execution'];request=receipt['request']
    if kind=='schema':raw['schema']='sipi.execution-record/2'
    if kind=='run':raw['run_id']='bad id'
    if kind=='source':raw['source_text']='{}'
    if kind=='receipt_schema':receipt['schema']='sipi.execution-receipt/2'
    if kind=='request_id':request['request_id']='0'*64
    if kind=='input_hash':request['input_sha256']='0'*64
    if kind=='request_input':request['input']['frequency_hz'][0]=3
    if kind=='controls':request['controls']['max_evaluations']+=1
    if kind=='controls_bool':request['controls']['max_evaluations']=True
    if kind=='output_schema':output['schema']='sipi.execution/2'
    if kind=='output_input':output['input']['frequency_hz'][0]=3
    if kind=='output_input_bool':output['input']['frequency_hz'][0]=False
    if kind=='status':output['status']='cancelled'
    if kind=='complete_null_result':output['result']=None
    if kind=='complete_error':output['error']={'type':'X','message':'x'}
    if kind=='incomplete_null_result':output.update(status='incomplete',result=None)
    if kind=='failed_result':output.update(status='failed',error={'type':'X','message':'x'})
    if kind=='failed_null_error':output.update(status='failed',result=None)
    if kind=='failed_no_type':output.update(status='failed',result=None,error={'message':'x'})
    if kind=='failed_no_message':output.update(status='failed',result=None,error={'type':'X'})
    if kind=='artifact_schema':raw['artifacts']['schema']='sipi.artifact-declaration/2'
    if kind=='artifact_verified':raw['artifacts']['verification']='verified'
    if kind=='artifact_order':raw['artifacts']['items'].reverse()
    if kind=='extra':raw['extra']=1
    with pytest.raises(ValueError):Record.from_dict(rehash(raw))


@pytest.mark.parametrize('receipt',[None,[],{},dict(request={})])
def test_constructor_rejects_malformed_receipt(receipt):
    with pytest.raises(ValueError):Record(lumped(),receipt,run_id='host:1',artifacts=ARTIFACTS)


def test_receipt_from_another_request_is_rejected():
    first=lumped();other=SavedExecutionRequest(LumpedNetworkDocument([0,1e9],resistance=20).dumps())
    with pytest.raises(ValueError,match='supplied request'):Record(first,other.run(),run_id='host:1',artifacts=ARTIFACTS)
    with pytest.raises(ValueError):Record({},first.run(),run_id='host:1',artifacts=ARTIFACTS)


@pytest.mark.parametrize('token',['NaN','Infinity','-Infinity','1e999'])
def test_nonfinite_record_json_rejects(token):
    text=record().dumps().replace('"run_id":"host:run-1"','"run_id":'+token)
    assert token in text
    with pytest.raises(ValueError):Record.loads(text)


def test_duplicate_keys_and_non_json_objects_reject():
    text=record().dumps().replace('"run_id":','"run_id":"duplicate","run_id":',1)
    with pytest.raises(ValueError):Record.loads(text)
    for value in (None,[],{},b'{}'):
        with pytest.raises(ValueError):Record.from_dict(value)
    with pytest.raises(ValueError):Record.loads(b'{}')
    raw=record().to_dict();raw['receipt']['execution']['result']['bad']=float('nan')
    with pytest.raises(ValueError):Record.from_dict(raw)
