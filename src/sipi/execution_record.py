# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Immutable saved results with request binding and host-declared artifacts."""
from dataclasses import dataclass,field
import hashlib
import json
import re
from ._validation import _json_copy, _keys, _unique_object, _integer, _reject_number, _float
from .execution_request import SavedExecutionRequest

__all__ = ['SavedExecutionRecord']

_RUN=re.compile(r'[A-Za-z0-9._:-]{1,128}')
_COMPONENT=re.compile(r'[a-z0-9][a-z0-9._-]{0,63}')
_VERSION=re.compile(r'[A-Za-z0-9+._-]{1,128}')
_DIGEST=re.compile(r'[0-9a-f]{64}')
_KINDS=('wheel','source-archive','wasm','executable','runtime')
_DEFAULT_LIMIT=8*1024*1024
_PARTIAL_RESOLUTION_SCHEMAS=('sipi.line-resolution/1','sipi.line-resolution/2',
    'sipi.panel-resolution/1','sipi.adaptive-panel-resolution/1','sipi.fem-shape-resolution/1','sipi.fem-shape-adaptive-resolution/1','sipi.corner-fem-shape-resolution/1')


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


def _partial_resolution_failure(output,source):
    """Version-2 structural variant; preserve existing partial execution bytes."""
    schema=source['schema']
    if schema=='sipi.two-ground-resolution/1':
        return _two_ground_partial_resolution_failure(output,source)
    if schema=='sipi.two-ground-face-resolution/1':
        return _two_ground_face_partial_resolution_failure(output,source)
    if schema=='sipi.two-ground-corner-face-resolution/1':
        return _two_ground_corner_face_partial_resolution_failure(output,source)
    if schema=='sipi.two-ground-linear-corner-face-resolution/1':
        return _two_ground_linear_corner_face_partial_resolution_failure(output,source)
    result,error=output['result'],output['error']
    if schema not in _PARTIAL_RESOLUTION_SCHEMAS or not isinstance(result,dict):
        raise ValueError('partial failed result requires a supported resolution input')
    adaptive=schema in ('sipi.line-resolution/2','sipi.adaptive-panel-resolution/1','sipi.fem-shape-adaptive-resolution/1')
    keys=('completed','accepted','tolerances','evaluations','comparisons','failure')
    level='refinement_levels' if schema=='sipi.adaptive-panel-resolution/1' else 'mesh_levels'
    keys+=('stop_reason',level,'expected_outer_evaluations','outer_completed','selected_evaluation_index') if adaptive else ('expected_evaluations',)
    _keys(result,keys,where='partial resolution result')
    fem = schema in ('sipi.fem-shape-resolution/1','sipi.fem-shape-adaptive-resolution/1','sipi.corner-fem-shape-resolution/1')
    _keys(error,('stage','input','kind','message')+(('details',) if fem else ()),where='partial resolution error')
    if fem:
        details = error['details']
        if error['kind']=='FEMShapeLineError':
            _keys(details,('type','message','stage','cause_type','input','mesh','current_solver','partial_current'),where='FEM resolution cause')
            if (details['type']!=error['kind'] or details['message']!=error['message']
                    or _canonical(details['input'])!=_canonical(error['input'])):
                raise ValueError('FEM resolution cause must match the failed input and error')
        elif details is not None:
            raise ValueError('untyped FEM resolution failure cannot contain typed cause details')
    if (result['completed'] is not False or result['accepted'] is not False
            or _canonical(result['tolerances'])!=_canonical(source['tolerances'])
            or any(not isinstance(error[k],str) or not error[k] for k in ('stage','kind'))
            or not isinstance(error['message'],str) or not isinstance(error['input'],dict)):
        raise ValueError('partial resolution failure flags, tolerances or error are inconsistent')
    for key in ('evaluations','comparisons'):
        if not isinstance(result[key],list) or any(not isinstance(row,dict) for row in result[key]):
            raise ValueError('partial resolution history must retain object rows')
    if adaptive:
        _integer(level,result[level],0,10000)
        _integer('expected_outer_evaluations',result['expected_outer_evaluations'],1,10000)
        if result['outer_completed'] is not False or result['selected_evaluation_index'] is not None:
            raise ValueError('failed adaptive resolution cannot select a qualified evaluation')
    else:
        expected=_integer('expected_evaluations',result['expected_evaluations'],1,10000)
        if len(result['evaluations'])>expected:
            raise ValueError('partial resolution exceeds its planned evaluations')
    if result['failure'] is not None:
        if (_canonical(result['failure'])!=_canonical(error)
                or (adaptive and result['stop_reason']!='field-failed')):
            raise ValueError('partial resolution failure must match its original error')
    elif (not adaptive or result['stop_reason']!='budget-exhausted'
            or error['kind']!='ResolutionBudgetExceeded' or error['stage']!='budget'
            or _canonical(error['input'])!=_canonical(source)):
        raise ValueError('partial resolution without field failure must retain budget exhaustion')



def _two_ground_partial_resolution_failure(output,source):
    """Bind the explicit two-ground failure to its field-free planned prefix."""
    from .two_ground_panel_line import TwoGroundPanelTransmissionLineDocument as Line
    from .two_ground_resolution import _two_ground_resolution_inputs
    from .line_resolution import ResolutionTolerance
    from .line_resolution_document import _API
    result,error=output['result'],output['error']
    _keys(result,('completed','accepted','tolerances','evaluations','comparisons','failure',
                 'expected_evaluations','scope'),where='partial two-ground resolution result')
    _keys(error,('stage','input','kind','message','details'),where='partial two-ground resolution error')
    if (result['completed'] is not False or result['accepted'] is not False or
        result['scope']!='two-ground-finite-resolution-not-absolute-accuracy' or
        _canonical(result['tolerances'])!=_canonical(source['tolerances']) or
        _canonical(result['failure'])!=_canonical(error) or
        any(not isinstance(error[k],str) or not error[k] for k in ('stage','kind')) or
        not isinstance(error['message'],str)):
        raise ValueError('partial two-ground flags, limits or failure are inconsistent')
    details=error['details']
    if error['kind']=='TwoGroundPanelLineError':
        _keys(details,('type','message','stage','cause_type','input','current_solver','dielectric_mesh'),where='two-ground resolution cause')
        if (details['type']!=error['kind'] or details['message']!=error['message'] or
            _canonical(details['input'])!=_canonical(error['input']) or
            any(not isinstance(details[k],str) or not details[k] for k in ('stage','cause_type'))):
            raise ValueError('two-ground typed cause must match the original input and failure')
    elif details is not None:
        raise ValueError('untyped two-ground failure cannot carry typed details')
    _,stages=_two_ground_resolution_inputs(Line.from_dict(source['line']),source['refined_panel'],
        [Line.from_dict(v) for v in source['outer_lines']],
        {_API[k]:ResolutionTolerance(**v) for k,v in source['tolerances'].items()},
        source['refinement_factor'],source['max_solves'])
    names=[stage for stage,_,_ in stages]
    if error['stage'] not in names:raise ValueError('failure stage must belong to the planned two-ground evaluations')
    index=names.index(error['stage'])
    if _canonical(error['input'])!=_canonical(stages[index][1].to_dict()):
        raise ValueError('failure input must match its planned two-ground stage')
    if _integer('expected_evaluations',result['expected_evaluations'],1,16)!=len(stages):
        raise ValueError('partial two-ground result must retain its planned count')
    for key in ('evaluations','comparisons'):
        if not isinstance(result[key],list) or any(not isinstance(row,dict) for row in result[key]):
            raise ValueError('partial two-ground history must retain object rows')
    if len(result['evaluations']) not in (index,index+1):
        raise ValueError('partial two-ground history must end at its failed stage')
    for i,row in enumerate(result['evaluations']):
        if row.get('stage')!=names[i] or _canonical(row.get('input'))!=_canonical(stages[i][1].to_dict()):
            raise ValueError('partial two-ground history must retain the exact planned prefix')
        if not isinstance(row.get('current_solver'),dict) or not isinstance(row.get('dielectric_mesh'),dict):
            raise ValueError('completed two-ground history requires current and mesh evidence')


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
        if data['schema']=='sipi.execution-record/2' and output['result'] is not None:
            if request['input']['schema']=='sipi.adaptive-two-ground-face-resolution/1':
                _two_ground_face_adaptive_partial_failure(output,request['input'],controls['max_evaluations'])
            else:
                _partial_resolution_failure(output,request['input'])
        elif (output['result'] is not None or not isinstance(error,dict)
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
    if data['schema'] not in ('sipi.execution-record/1','sipi.execution-record/2') or not _matches(_RUN,data['run_id']):
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

    Version 1 remains the default. Explicit version 2 additionally preserves
    the existing non-null partial-result failure variant of supported resolution
    requests, including adaptive budget exhaustion, without changing execution.
    """
    _data_json: str=field(repr=False)

    def __init__(self,request,receipt,*,run_id,artifacts,max_record_bytes=_DEFAULT_LIMIT,
                 schema='sipi.execution-record/1'):
        if not isinstance(request,SavedExecutionRequest):
            raise ValueError('request must be a SavedExecutionRequest')
        data=dict(schema=schema,run_id=run_id,source_text=request.source_text,
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


def _two_ground_face_partial_resolution_failure(output,source):
    """Bind the explicit two-ground-face failure to its field-free planned prefix."""
    from .two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument as Line
    from .two_ground_face_resolution import _two_ground_face_resolution_inputs
    from .line_resolution import ResolutionTolerance
    from .line_resolution_document import _API
    result,error=output['result'],output['error']
    _keys(result,('completed','accepted','tolerances','evaluations','comparisons','failure',
                 'expected_evaluations','scope'),where='partial two-ground-face resolution result')
    _keys(error,('stage','input','kind','message','details'),where='partial two-ground-face resolution error')
    if (result['completed'] is not False or result['accepted'] is not False or
        result['scope']!='two-ground-face-finite-resolution-not-absolute-accuracy' or
        _canonical(result['tolerances'])!=_canonical(source['tolerances']) or
        _canonical(result['failure'])!=_canonical(error) or
        any(not isinstance(error[k],str) or not error[k] for k in ('stage','kind')) or
        not isinstance(error['message'],str)):
        raise ValueError('partial two-ground-face flags, limits or failure are inconsistent')
    details=error['details']
    if error['kind']=='TwoGroundFacePanelLineError':
        _keys(details,('type','message','stage','cause_type','input','current_solver','dielectric_mesh'),where='two-ground-face resolution cause')
        if (details['type']!=error['kind'] or details['message']!=error['message'] or
            _canonical(details['input'])!=_canonical(error['input']) or
            any(not isinstance(details[k],str) or not details[k] for k in ('stage','cause_type'))):
            raise ValueError('two-ground-face typed cause must match the original input and failure')
    elif details is not None:
        raise ValueError('untyped two-ground-face failure cannot carry typed details')
    _,stages=_two_ground_face_resolution_inputs(Line.from_dict(source['line']),source['refined_panel'],
        [Line.from_dict(v) for v in source['outer_lines']],
        {_API[k]:ResolutionTolerance(**v) for k,v in source['tolerances'].items()},
        source['refinement_factor'],source['max_solves'])
    names=[stage for stage,_,_ in stages]
    if error['stage'] not in names:raise ValueError('failure stage must belong to the planned two-ground-face evaluations')
    index=names.index(error['stage'])
    if _canonical(error['input'])!=_canonical(stages[index][1].to_dict()):
        raise ValueError('failure input must match its planned two-ground-face stage')
    if _integer('expected_evaluations',result['expected_evaluations'],1,16)!=len(stages):
        raise ValueError('partial two-ground-face result must retain its planned count')
    for key in ('evaluations','comparisons'):
        if not isinstance(result[key],list) or any(not isinstance(row,dict) for row in result[key]):
            raise ValueError('partial two-ground-face history must retain object rows')
    if len(result['evaluations']) not in (index,index+1):
        raise ValueError('partial two-ground-face history must end at its failed stage')
    for i,row in enumerate(result['evaluations']):
        if row.get('stage')!=names[i] or _canonical(row.get('input'))!=_canonical(stages[i][1].to_dict()):
            raise ValueError('partial two-ground-face history must retain the exact planned prefix')
        if not isinstance(row.get('current_solver'),dict) or not isinstance(row.get('dielectric_mesh'),dict):
            raise ValueError('completed two-ground-face history requires current and mesh evidence')

def _two_ground_face_adaptive_partial_failure(output,source,max_evaluations):
    """Bind partial adaptive evidence to the exact planned prefix and caller budget.

    This validates structure and control flow, not the truth of recorded fields.
    """
    from .adaptive_two_ground_face_resolution import (TwoGroundFaceResolutionRefinement,
        _adaptive_two_ground_face_inputs)
    from .two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument as Line
    from .line_resolution import ResolutionTolerance
    from .line_resolution_document import _API
    result,error=output['result'],output['error']
    _keys(result,('completed','accepted','tolerances','evaluations','comparisons','failure',
        'stop_reason','refinement_levels','expected_outer_evaluations','outer_completed',
        'selected_evaluation_index','scope'),where='partial adaptive face resolution')
    _keys(error,('stage','input','kind','message','details'),where='partial adaptive face error')
    if (result['completed'] is not False or result['accepted'] is not False or
        result['outer_completed'] is not False or result['selected_evaluation_index'] is not None or
        result['scope']!='two-ground-face-adaptive-finite-resolution-not-absolute-accuracy' or
        _canonical(result['tolerances'])!=_canonical(source['tolerances']) or
        any(not isinstance(error[k],str) or not error[k] for k in ('stage','kind')) or
        not isinstance(error['message'],str)):
        raise ValueError('partial adaptive face flags, tolerances or selection are inconsistent')
    steps=[TwoGroundFaceResolutionRefinement(step['refined_panel'],
        [Line.from_dict(v) for v in step['outer_lines']]) for step in source['refinements']]
    limit,_,plans=_adaptive_two_ground_face_inputs(Line.from_dict(source['line']),steps,
        {_API[k]:ResolutionTolerance(**v) for k,v in source['tolerances'].items()},
        source['refinement_factor'],min(source['max_solves'],max_evaluations))
    level=_integer('refinement_levels',result['refinement_levels'],0,len(plans))
    count_outer=len(plans[0])-4
    if _integer('expected_outer_evaluations',result['expected_outer_evaluations'],1,12)!=count_outer:
        raise ValueError('partial adaptive face outer count differs from the plan')
    stages=[('base',plans[0][0][1],())]
    for n,plan in enumerate(plans[:level],1):
        indices=[3*(n-1)]
        for name,doc,refs in plan[1:4]:
            stages.append((f'level:{n}:{name}',doc,tuple((indices[i],f'level:{n}:{label}') for i,label in refs)))
            indices.append(len(stages)-1)
    if level>=2:
        stages.extend((name,doc,((3*level,name),)) for name,doc,_ in plans[level-1][4:])
    for key in ('evaluations','comparisons'):
        if not isinstance(result[key],list) or any(not isinstance(row,dict) for row in result[key]):
            raise ValueError('partial adaptive face history must retain object rows')
    evaluations,comparisons=result['evaluations'],result['comparisons']
    if len(evaluations)>limit:
        raise ValueError('partial adaptive face history exceeds the caller budget')
    if result['failure'] is None:
        if (result['stop_reason']!='budget-exhausted' or error['kind']!='ResolutionBudgetExceeded' or
            error['stage']!='budget' or error['details'] is not None or
            _canonical(error['input'])!=_canonical(source) or not 2<=level<len(plans) or
            len(evaluations)!=1+3*level or len(comparisons)!=4*level or
            len(evaluations)+count_outer>limit or len(evaluations)+3+count_outer<=limit):
            raise ValueError('adaptive face budget exhaustion must retain its exact reserved prefix')
        stages=stages[:1+3*level]
    else:
        if result['stop_reason']!='field-failed' or _canonical(result['failure'])!=_canonical(error):
            raise ValueError('partial adaptive face failure must match the original error')
        if level and 1+3*level+count_outer>limit:
            raise ValueError('failed adaptive face level must have reserved its whole step and outer checks')
        stage=error['stage'];names=[s for s,_,_ in stages]
        if (stage not in names or (stage=='base' and level!=0) or
            (stage.startswith('level:') and not stage.startswith(f'level:{level}:')) or
            (stage.startswith('outer:') and level<2)):
            raise ValueError('failure must occur at the declared adaptive face level')
        index=names.index(stage)
        if _canonical(error['input'])!=_canonical(stages[index][1].to_dict()):
            raise ValueError('failure input must match its planned adaptive face stage')
        prior=sum(len(refs) for _,_,refs in stages[:index])
        if len(evaluations)==index:
            valid=len(comparisons)==prior
        elif len(evaluations)==index+1:
            valid=prior<=len(comparisons)<prior+len(stages[index][2])
        else:valid=False
        if not valid:
            raise ValueError('partial adaptive face history must end at its original failed operation')
        details=error['details']
        if error['kind']=='TwoGroundFacePanelLineError':
            _keys(details,('type','message','stage','cause_type','input','current_solver','dielectric_mesh'),
                  where='adaptive face typed cause')
            if (details['type']!=error['kind'] or details['message']!=error['message'] or
                _canonical(details['input'])!=_canonical(error['input']) or
                any(not isinstance(details[k],str) or not details[k] for k in ('stage','cause_type'))):
                raise ValueError('adaptive face typed cause must retain the original failure and input')
        elif details is not None:
            raise ValueError('untyped adaptive face failure cannot carry typed details')
    for row,(stage,doc,_) in zip(evaluations,stages):
        if row.get('stage')!=stage or _canonical(row.get('input'))!=_canonical(doc.to_dict()):
            raise ValueError('partial adaptive face evaluations must retain the exact planned prefix')
        if not isinstance(row.get('current_solver'),dict) or not isinstance(row.get('dielectric_mesh'),dict):
            raise ValueError('completed adaptive face evaluations need current and mesh evidence')
    expected=[(label,reference,i) for i,(_,_,refs) in enumerate(stages[:len(evaluations)])
              for reference,label in refs]
    if len(comparisons)>len(expected):raise ValueError('extra adaptive face comparisons')
    for row,(label,reference,index) in zip(comparisons,expected):
        _keys(row,('stage','reference_index','evaluation_index','accepted','differences','allowances'),
              where='partial adaptive face comparison')
        if (row['stage']!=label or _integer('reference_index',row['reference_index'],0,31)!=reference or
            _integer('evaluation_index',row['evaluation_index'],0,31)!=index or
            not isinstance(row['accepted'],bool) or
            not isinstance(row['differences'],dict) or not isinstance(row['allowances'],dict) or
            set(row['differences'])!=set(source['tolerances']) or set(row['allowances'])!=set(source['tolerances'])):
            raise ValueError('adaptive face comparisons must retain their planned references and quantities')
    consecutive=0
    for n in range(1,level+1):
        batch=comparisons[4*(n-1):4*n]
        if len(batch)<4:break
        consecutive=consecutive+1 if all(row['accepted'] for row in batch) else 0
        if consecutive>=2 and (n<level or result['failure'] is None):
            raise ValueError('adaptive face history cannot advance past two accepted levels')
    if error['stage'].startswith('outer:') and consecutive<2:
        raise ValueError('adaptive face outer work needs two accepted levels')


def _two_ground_corner_face_partial_resolution_failure(output,source):
    """Bind the explicit two-ground-corner-face failure to its field-free planned prefix."""
    from .two_ground_corner_face_panel_line import TwoGroundCornerFacePanelTransmissionLineDocument as Line
    from .two_ground_corner_face_resolution import _two_ground_corner_face_resolution_inputs
    from .line_resolution import ResolutionTolerance
    from .line_resolution_document import _API
    result,error=output['result'],output['error']
    _keys(result,('completed','accepted','tolerances','evaluations','comparisons','failure',
                 'expected_evaluations','scope'),where='partial two-ground-corner-face resolution result')
    _keys(error,('stage','input','kind','message','details'),where='partial two-ground-corner-face resolution error')
    if (result['completed'] is not False or result['accepted'] is not False or
        result['scope']!='two-ground-corner-face-finite-resolution-not-absolute-accuracy' or
        _canonical(result['tolerances'])!=_canonical(source['tolerances']) or
        _canonical(result['failure'])!=_canonical(error) or
        any(not isinstance(error[k],str) or not error[k] for k in ('stage','kind')) or
        not isinstance(error['message'],str)):
        raise ValueError('partial two-ground-corner-face flags, limits or failure are inconsistent')
    details=error['details']
    if error['kind']=='TwoGroundCornerFacePanelLineError':
        _keys(details,('type','message','stage','cause_type','input','current_solver','dielectric_mesh'),where='two-ground-corner-face resolution cause')
        if (details['type']!=error['kind'] or details['message']!=error['message'] or
            _canonical(details['input'])!=_canonical(error['input']) or
            any(not isinstance(details[k],str) or not details[k] for k in ('stage','cause_type'))):
            raise ValueError('two-ground-corner-face typed cause must match the original input and failure')
    elif details is not None:
        raise ValueError('untyped two-ground-corner-face failure cannot carry typed details')
    _,stages=_two_ground_corner_face_resolution_inputs(Line.from_dict(source['line']),source['refined_panel'],
        [Line.from_dict(v) for v in source['outer_lines']],
        {_API[k]:ResolutionTolerance(**v) for k,v in source['tolerances'].items()},
        source['refinement_factor'],source['max_solves'])
    names=[stage for stage,_,_ in stages]
    if error['stage'] not in names:raise ValueError('failure stage must belong to the planned two-ground-corner-face evaluations')
    index=names.index(error['stage'])
    if _canonical(error['input'])!=_canonical(stages[index][1].to_dict()):
        raise ValueError('failure input must match its planned two-ground-corner-face stage')
    if _integer('expected_evaluations',result['expected_evaluations'],1,16)!=len(stages):
        raise ValueError('partial two-ground-corner-face result must retain its planned count')
    for key in ('evaluations','comparisons'):
        if not isinstance(result[key],list) or any(not isinstance(row,dict) for row in result[key]):
            raise ValueError('partial two-ground-corner-face history must retain object rows')
    if len(result['evaluations']) not in (index,index+1):
        raise ValueError('partial two-ground-corner-face history must end at its failed stage')
    for i,row in enumerate(result['evaluations']):
        if row.get('stage')!=names[i] or _canonical(row.get('input'))!=_canonical(stages[i][1].to_dict()):
            raise ValueError('partial two-ground-corner-face history must retain the exact planned prefix')
        if not isinstance(row.get('current_solver'),dict) or not isinstance(row.get('dielectric_mesh'),dict):
            raise ValueError('completed two-ground-corner-face history requires current and mesh evidence')


def _two_ground_linear_corner_face_partial_resolution_failure(output,source):
    """Bind the explicit two-ground-linear-corner-face failure to its field-free planned prefix."""
    from .two_ground_linear_corner_face_panel_line import TwoGroundLinearCornerFacePanelTransmissionLineDocument as Line
    from .two_ground_linear_corner_face_resolution import _two_ground_linear_corner_face_resolution_inputs
    from .line_resolution import ResolutionTolerance
    from .line_resolution_document import _API
    result,error=output['result'],output['error']
    _keys(result,('completed','accepted','tolerances','evaluations','comparisons','failure',
                 'expected_evaluations','scope'),where='partial two-ground-linear-corner-face resolution result')
    _keys(error,('stage','input','kind','message','details'),where='partial two-ground-linear-corner-face resolution error')
    if (result['completed'] is not False or result['accepted'] is not False or
        result['scope']!='two-ground-linear-corner-face-finite-resolution-not-absolute-accuracy' or
        _canonical(result['tolerances'])!=_canonical(source['tolerances']) or
        _canonical(result['failure'])!=_canonical(error) or
        any(not isinstance(error[k],str) or not error[k] for k in ('stage','kind')) or
        not isinstance(error['message'],str)):
        raise ValueError('partial two-ground-linear-corner-face flags, limits or failure are inconsistent')
    details=error['details']
    if error['kind']=='TwoGroundLinearCornerFacePanelLineError':
        _keys(details,('type','message','stage','cause_type','input','current_solver','dielectric_mesh'),where='two-ground-linear-corner-face resolution cause')
        if (details['type']!=error['kind'] or details['message']!=error['message'] or
            _canonical(details['input'])!=_canonical(error['input']) or
            any(not isinstance(details[k],str) or not details[k] for k in ('stage','cause_type'))):
            raise ValueError('two-ground-linear-corner-face typed cause must match the original input and failure')
    elif details is not None:
        raise ValueError('untyped two-ground-linear-corner-face failure cannot carry typed details')
    _,stages=_two_ground_linear_corner_face_resolution_inputs(Line.from_dict(source['line']),source['refined_panel'],
        [Line.from_dict(v) for v in source['outer_lines']],
        {_API[k]:ResolutionTolerance(**v) for k,v in source['tolerances'].items()},
        source['refinement_factor'],source['max_solves'])
    names=[stage for stage,_,_ in stages]
    if error['stage'] not in names:raise ValueError('failure stage must belong to the planned two-ground-linear-corner-face evaluations')
    index=names.index(error['stage'])
    if _canonical(error['input'])!=_canonical(stages[index][1].to_dict()):
        raise ValueError('failure input must match its planned two-ground-linear-corner-face stage')
    if _integer('expected_evaluations',result['expected_evaluations'],1,16)!=len(stages):
        raise ValueError('partial two-ground-linear-corner-face result must retain its planned count')
    for key in ('evaluations','comparisons'):
        if not isinstance(result[key],list) or any(not isinstance(row,dict) for row in result[key]):
            raise ValueError('partial two-ground-linear-corner-face history must retain object rows')
    if len(result['evaluations']) not in (index,index+1):
        raise ValueError('partial two-ground-linear-corner-face history must end at its failed stage')
    for i,row in enumerate(result['evaluations']):
        if row.get('stage')!=names[i] or _canonical(row.get('input'))!=_canonical(stages[i][1].to_dict()):
            raise ValueError('partial two-ground-linear-corner-face history must retain the exact planned prefix')
        if not isinstance(row.get('current_solver'),dict) or not isinstance(row.get('dielectric_mesh'),dict):
            raise ValueError('completed two-ground-linear-corner-face history requires current and mesh evidence')
