# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Immutable saved results with request binding and host-declared artifacts."""
from dataclasses import dataclass,field
import hashlib
import json
import re
from .circuit_document import _json_copy
from .document import _keys,_unique_object
from .execution import _integer,_reject_number,_float
from .execution_request import SavedExecutionRequest

__all__ = ['SavedExecutionRecord']

_RUN=re.compile(r'[A-Za-z0-9._:-]{1,128}')
_COMPONENT=re.compile(r'[a-z0-9][a-z0-9._-]{0,63}')
_VERSION=re.compile(r'[A-Za-z0-9+._-]{1,128}')
_DIGEST=re.compile(r'[0-9a-f]{64}')
_KINDS=('wheel','source-archive','wasm','executable','runtime')
_DEFAULT_LIMIT=8*1024*1024


def _canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)


def _matches(pattern,value):
    return isinstance(value,str) and pattern.fullmatch(value) is not None


def _limit(value):
    return _integer('max_record_bytes',value,1,64*1024*1024)


def _digest(data):
    body={k:v for k,v in data.items() if k!='content_sha256'}
    return hashlib.sha256(_canonical(body).encode('utf-8')).hexdigest()


def _artifact_declaration(items):
    if not isinstance(items,list) or not 1<=len(items)<=64:
        raise ValueError('artifacts must contain 1..64 declared items')
    seen=set();rows=[]
    for item in items:
        _keys(item,('component','version','kind','sha256'),where='artifact item')
        if (not _matches(_COMPONENT,item['component']) or not _matches(_VERSION,item['version'])
                or item['kind'] not in _KINDS or not _matches(_DIGEST,item['sha256'])):
            raise ValueError('invalid declared artifact component, version, kind or digest')
        key=(item['component'],item['kind'])
        if key in seen:raise ValueError('artifact component/kind pairs must be unique')
        seen.add(key);rows.append(dict(item))
    if not any(row['component']=='sipi' for row in rows):
        raise ValueError('artifact declarations must include the sipi component')
    return dict(schema='sipi.artifact-declaration/1',verification='host-declared',
                items=sorted(rows,key=lambda row:(row['component'],row['kind'])))


def _prepared(data):
    receipt=data['receipt']
    _keys(receipt,('schema','request','execution'),where='execution receipt')
    if receipt['schema']!='sipi.execution-receipt/1':
        raise ValueError('unsupported execution receipt schema')
    request=receipt['request']
    _keys(request,('schema','request_id','input_sha256','input','controls'),where='receipt request')
    controls=request['controls']
    _keys(controls,('max_input_bytes','max_evaluations','diagnostics'),where='receipt controls')
    if not isinstance(data['source_text'],str):raise ValueError('source_text must be original JSON text')
    prepared=SavedExecutionRequest(data['source_text'],**controls)
    if _canonical(prepared.to_dict())!=_canonical(request):
        raise ValueError('receipt request differs from original source and controls')
    output=receipt['execution']
    _keys(output,('schema','input','status','result','error'),where='execution output')
    if output['schema']!='sipi.execution/1' or _canonical(output['input'])!=_canonical(request['input']):
        raise ValueError('execution output does not match the canonical request input')
    if output['status'] in ('complete','incomplete'):
        if not isinstance(output['result'],dict) or output['error'] is not None:
            raise ValueError('completed/incomplete execution needs a result object and null error')
    elif output['status']=='failed':
        error=output['error']
        if (output['result'] is not None or not isinstance(error,dict)
                or not isinstance(error.get('type'),str) or not error['type']
                or not isinstance(error.get('message'),str)):
            raise ValueError('failed execution needs null result and a typed error message')
    else:raise ValueError('unsupported execution status')
    return prepared


def _validated(data,max_record_bytes):
    limit=_limit(max_record_bytes);data=_json_copy(data)
    text=_canonical(data)
    if len(text.encode('utf-8'))>limit:raise ValueError('saved result exceeds max_record_bytes')
    _keys(data,('schema','run_id','source_text','receipt','artifacts','content_sha256'),where='execution record')
    if data['schema']!='sipi.execution-record/1' or not _matches(_RUN,data['run_id']):
        raise ValueError('unsupported execution record schema or invalid run_id')
    if not _matches(_DIGEST,data['content_sha256']) or data['content_sha256']!=_digest(data):
        raise ValueError('execution record content digest mismatch')
    artifacts=data['artifacts']
    _keys(artifacts,('schema','verification','items'),where='artifact declaration')
    expected=_artifact_declaration(artifacts['items'])
    if _canonical(artifacts)!=_canonical(expected):
        raise ValueError('artifact declaration must use canonical order and host-declared verification')
    _prepared(data)
    return text


@dataclass(frozen=True,init=False)
class SavedExecutionRecord:
    """Bind a receipt to original input and explicit host provenance declarations.

    Loading/preparing never calculates. The content digest detects changes; it
    is not a signature, authenticity check or proof of executed artifact bytes.
    Hosts own run-ID uniqueness, stale-response handling, actual artifact checks,
    cancellation, filesystem persistence and project state. Numerical result
    plausibility is not certified by this structural envelope.
    """
    _data_json: str=field(repr=False)

    def __init__(self,request,receipt,*,run_id,artifacts,max_record_bytes=_DEFAULT_LIMIT):
        if not isinstance(request,SavedExecutionRequest):
            raise ValueError('request must be a SavedExecutionRequest')
        data=dict(schema='sipi.execution-record/1',run_id=run_id,source_text=request.source_text,
                  receipt=_json_copy(receipt),artifacts=_artifact_declaration(_json_copy(artifacts)))
        _keys(data['receipt'],('schema','request','execution'),where='execution receipt')
        if _canonical(data['receipt'].get('request'))!=_canonical(request.to_dict()):
            raise ValueError('receipt does not belong to the supplied request')
        data['content_sha256']=_digest(data)
        object.__setattr__(self,'_data_json',_validated(data,max_record_bytes))

    @classmethod
    def from_dict(cls,data,*,max_record_bytes=_DEFAULT_LIMIT):
        result=cls.__new__(cls)
        object.__setattr__(result,'_data_json',_validated(data,max_record_bytes))
        return result

    @classmethod
    def loads(cls,text,*,max_record_bytes=_DEFAULT_LIMIT):
        limit=_limit(max_record_bytes)
        if not isinstance(text,str):raise ValueError('saved record must be JSON text')
        if len(text.encode('utf-8'))>limit:raise ValueError('saved result exceeds max_record_bytes')
        data=json.loads(text,object_pairs_hook=_unique_object,parse_constant=_reject_number,parse_float=_float)
        return cls.from_dict(data,max_record_bytes=limit)

    def dumps(self):
        """Canonical compact UTF-8-compatible JSON; no filesystem action."""
        return self._data_json

    def to_dict(self):
        return json.loads(self._data_json)

    def prepare(self):
        """Reconstruct the original request and controls without executing it."""
        return _prepared(self.to_dict())

    @property
    def run_id(self):return self.to_dict()['run_id']

    @property
    def receipt(self):return self.to_dict()['receipt']

    @property
    def artifacts(self):return self.to_dict()['artifacts']
