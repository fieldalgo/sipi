# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Whole-plan budgets, strict snapshots and retained resolution disagreements."""
import json
import numpy as np
import pytest
from sipi import CrossSection
from sipi.two_ground_face_sampled_pair_study import TwoGroundFaceSampledForwardPairStudyDocument
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument as PanelTransmissionLineDocument
from sipi.two_ground_face_sampled_resolution_yield import assess_two_ground_face_sampled_pair_resolution_yield
from sipi.two_ground_face_sampled_resolution_yield_document import TwoGroundFaceSampledResolutionYieldDocument
from sipi.execution import execute_saved, normalize_saved
from test_two_ground_face_sampled_pair_yield import random_document, limits
LIMITS=limits()
from test_two_ground_face_sampled_pair_study import synthetic


def document(*,physical=False):
    if physical:
        from test_two_ground_face_sampled_pair_study import physical_document, Q
        raw=physical_document().to_dict()
        raw['study']['sampling'].update(kind='uniform',count=2,seed=19)
        bounds={q:dict(minimum=[lo]*3,maximum=[hi]*3) for q,lo,hi in zip(Q,[100.,50.],[103.,52.])}
    else:raw=random_document(2).to_dict();bounds=LIMITS
    studies=[]
    for stage in ('base','joint'):
        data=json.loads(json.dumps(raw))
        if stage=='joint':
            for key in ('edge_size','far_size','grade'):data['study']['mesh'][key]*=.5
            data['panel'].update(panels_per_edge=128,ground_modes=256)
        studies.append(TwoGroundFaceSampledForwardPairStudyDocument.from_dict(data))
    return TwoGroundFaceSampledResolutionYieldDocument(studies,acceptance=bounds,minimum_yield=.8 if physical else .9)


def test_field_free_canonical_snapshots_and_required_budget(monkeypatch):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('normalization meshed'))
    monkeypatch.setattr(TwoGroundFaceSampledForwardPairStudyDocument,'analyze',lambda *a,**k:pytest.fail('normalization analyzed'))
    doc=document();text=doc.dumps()
    assert doc.required_evaluations==4
    assert normalize_saved(text)==text==TwoGroundFaceSampledResolutionYieldDocument.loads(text).dumps()
    raw=doc.to_dict();raw['studies'][0]['panel']['panels_per_edge']=256
    nested=doc.studies[0];nested._data['panel']['panels_per_edge']=256
    assert doc.dumps()==text and doc.studies[0].to_dict()['panel']['panels_per_edge']==64


def test_direct_and_common_execution_match_exactly(monkeypatch):
    calls=synthetic(monkeypatch);doc=document();direct=doc.analyze(max_evaluations=4)
    assert len(calls)==4
    expected=assess_two_ground_face_sampled_pair_resolution_yield([d.analyze(max_evaluations=2) for d in doc.studies],
        acceptance=LIMITS,minimum_yield=.9)
    assert expected.to_dict()==direct.to_dict()
    calls.clear();out=execute_saved(doc.dumps(),max_evaluations=4)
    assert out['status']==('incomplete' if direct.unresolved else 'complete')
    assert out['input']==doc.to_dict() and out['result']==direct.to_dict() and out['error'] is None
    assert len(calls)==4 and out['result']['count']==2
    json.dumps(out,allow_nan=False)


@pytest.mark.parametrize('attempt',[1,2,3,4])
def test_original_failed_rows_are_incomplete_but_every_planned_row_is_attempted(monkeypatch,attempt):
    calls=synthetic(monkeypatch,fail_at=attempt);doc=document()
    out=execute_saved(doc.dumps(),max_evaluations=4)
    assert out['status']=='incomplete' and out['error'] is None and len(calls)==4
    result=out['result'];assert result['count']==2 and result['unresolved']==1
    source=result['resolutions'][(attempt-1)//2]['assessment']['rows'][(attempt-1)%2]
    assert source['phase']=='extraction' and source['error_type']=='TwoGroundFacePanelLineError'
    assert source['input']==json.loads(calls[attempt-1]) and source['values_ohm'] is None
    assert result['rows'][(attempt-1)%2]['classification']=='unresolved'


@pytest.mark.parametrize('budget',[0,1,2,3,True,4.,10001])
def test_whole_plan_budget_rejected_before_any_analysis(monkeypatch,budget):
    doc=document()
    monkeypatch.setattr(TwoGroundFaceSampledForwardPairStudyDocument,'analyze',lambda *a,**k:pytest.fail('rejected plan analyzed'))
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('rejected plan meshed'))
    with pytest.raises(ValueError):doc.analyze(max_evaluations=budget)
    with pytest.raises(ValueError):execute_saved(doc.dumps(),max_evaluations=budget)


@pytest.mark.parametrize('options',[dict(diagnostics=['characteristic']),dict(max_input_bytes=16)])
def test_common_transport_limits_before_fields(monkeypatch,options):
    doc=document()
    monkeypatch.setattr(TwoGroundFaceSampledResolutionYieldDocument,'analyze',lambda *a,**k:pytest.fail('rejected request analyzed'))
    with pytest.raises(ValueError):execute_saved(doc.dumps(),**options)


@pytest.mark.parametrize('where',['root','source','panel','acceptance'])
@pytest.mark.parametrize('mode',['missing','extra'])
def test_strict_nested_keys(where,mode):
    raw=document().to_dict()
    target={'root':raw,'source':raw['studies'][0],'panel':raw['studies'][0]['panel'],
            'acceptance':raw['acceptance']}[where]
    if mode=='missing':target.pop(next(iter(target)))
    else:target['unexpected']=1
    with pytest.raises(ValueError):TwoGroundFaceSampledResolutionYieldDocument.from_dict(raw)


@pytest.mark.parametrize('mode',['schema','duplicate','nonfinite','nonobject','nested-schema'])
def test_ambiguous_json_and_versions_refused(mode):
    raw=document().to_dict();text=json.dumps(raw)
    if mode=='schema':raw['schema']='sipi.two-ground-face-sampled-resolution-yield/unsupported'
    if mode=='nested-schema':raw['studies'][0]['schema']='unknown'
    if mode=='duplicate':text=text.replace('"ground_modes": 128','"ground_modes": 128, "ground_modes": 128')
    elif mode=='nonfinite':text=text.replace('"confidence": 0.95','"confidence": NaN')
    elif mode=='nonobject':text='[]'
    else:text=json.dumps(raw)
    with pytest.raises(ValueError):TwoGroundFaceSampledResolutionYieldDocument.loads(text)


@pytest.mark.parametrize('mode',['duplicate','geometry','seed','mixed-schema','too-many','one','not-list','corners','total-budget'])
def test_plan_preflight_rejects_without_solving(monkeypatch,mode):
    raw=document().to_dict()
    if mode=='duplicate':raw['studies'][1]=raw['studies'][0]
    if mode=='geometry':raw['studies'][1]['study']['parameters']['width']*=1.01
    if mode=='seed':raw['studies'][1]['study']['sampling']['seed']+=1
    if mode=='mixed-schema':raw['studies'][1]['schema']='sipi.sampled-panel-forward-pair-study/2'
    if mode=='too-many':raw['studies']*=5
    if mode=='one':raw['studies']=raw['studies'][:1]
    if mode=='not-list':raw['studies']={}
    if mode=='corners':
        for item in raw['studies']:
            sampling=item['study']['sampling'];sampling['kind']='corners'
            sampling.pop('seed',None);sampling.pop('count',None)
    if mode=='total-budget':
        for item in raw['studies']:item['study']['sampling']['count']=5001
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('preflight meshed'))
    with pytest.raises(ValueError):TwoGroundFaceSampledResolutionYieldDocument.from_dict(raw)


def test_generation_failure_precedes_all_fields_and_interrupts_propagate(monkeypatch):
    doc=document();calls=[]
    original=TwoGroundFaceSampledForwardPairStudyDocument.samples
    def failed(self):raise OverflowError('retained sample failure')
    monkeypatch.setattr(TwoGroundFaceSampledForwardPairStudyDocument,'samples',failed)
    monkeypatch.setattr(TwoGroundFaceSampledForwardPairStudyDocument,'analyze',lambda *a,**k:calls.append(1))
    with pytest.raises(OverflowError,match='retained sample failure'):doc.analyze(max_evaluations=4)
    assert not calls
    monkeypatch.setattr(TwoGroundFaceSampledForwardPairStudyDocument,'samples',original)
    def interrupt(*a,**k):calls.append(1);raise KeyboardInterrupt
    monkeypatch.setattr(TwoGroundFaceSampledForwardPairStudyDocument,'analyze',interrupt)
    with pytest.raises(KeyboardInterrupt):doc.analyze(max_evaluations=4)
    assert calls==[1]


@pytest.mark.parametrize('value',[None,{},[None]])
def test_constructor_requires_source_documents(value):
    with pytest.raises(TypeError):TwoGroundFaceSampledResolutionYieldDocument(value,acceptance=LIMITS)


def test_actual_saved_face_grid_and_common_replay(monkeypatch,record_property):
    from scipy.linalg import sqrtm
    doc=document(physical=True);fields={};original=PanelTransmissionLineDocument.analyze
    def capture(self):
        line=original(self);fields[self.dumps()]=line;return line
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',capture)
    result=doc.analyze(max_evaluations=4)
    record_property('face_saved_resolution_direct',json.dumps(result.to_dict(),sort_keys=True))
    assert len(fields)==4 and result.to_dict()['count']==2
    transform=np.array([[1.,-1.],[.5,.5]])
    for resolution in result.assessments:
        for row in resolution.study.rows:
            line=row.result
            for i,f in enumerate(line.frequency):
                z=line.R[i]+2j*np.pi*f*line.L[i];y=line.G[i]+2j*np.pi*f*line.C[i]
                gamma=np.asarray(sqrtm(z@y),dtype=complex)
                np.testing.assert_allclose(row.values[i],np.diag(transform@np.linalg.solve(gamma,z)@transform.T).real,rtol=1e-10,atol=0)
    calls=[]
    def replay(self):
        calls.append(self.dumps());assert self.dumps() in fields
        return fields[self.dumps()]
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',replay)
    out=execute_saved(doc.dumps(),max_evaluations=4)
    record_property('face_saved_resolution_execution',json.dumps(out,sort_keys=True))
    assert out['status']==('incomplete' if result.unresolved else 'complete') and out['error'] is None
    assert out['result']==result.to_dict() and out['input']==doc.to_dict()
    assert len(calls)==doc.required_evaluations==4 and out['result']['resolution_count']==2


def test_resolution_label_disagreement_is_incomplete_without_a_fabricated_error(monkeypatch):
    from sipi.two_ground_face_sampled_pair_study import TwoGroundFaceSampledForwardPairStudy,TwoGroundFaceSampledForwardPairStudyRow
    from test_two_ground_face_sampled_pair_yield import GOOD,BAD
    calls=[]
    def statistical(self,*,max_evaluations):
        # Synthetic statistics only: a mismatch at one frequency changes the joint event.
        raw=self.to_dict();calls.append(raw);rows=[]
        for i,sample in enumerate(self.samples()):
            values=BAD if i==0 and raw['panel']['panels_per_edge']==128 else GOOD
            rows.append(TwoGroundFaceSampledForwardPairStudyRow(i,tuple(sample),None,None,None,values,'complete',None,None))
        return TwoGroundFaceSampledForwardPairStudy(self.dumps(),tuple(raw['frequency_hz']),
            tuple(v['name'] for v in raw['study']['sampling']['variables']),tuple(rows),None)
    monkeypatch.setattr(TwoGroundFaceSampledForwardPairStudyDocument,'analyze',statistical)
    out=execute_saved(document().dumps(),max_evaluations=4)
    assert len(calls)==2 and out['status']=='incomplete' and out['error'] is None
    assert out['result']['count']==2 and out['result']['unresolved']==1
    assert out['result']['rows'][0]['labels_by_resolution']==['pass','fail']
    assert out['result']['sample_fraction_bounds']==[.5,1.]


@pytest.mark.parametrize('change',['grid','bounds-length','bounds-boolean','metal'])
def test_full_grid_and_fixed_metal_identity_before_fields(monkeypatch,change):
    raw=document(physical=True).to_dict()
    if change=='grid':raw['studies'][1]['frequency_hz'][-1]*=1.01
    if change=='bounds-length':raw['acceptance'][next(iter(raw['acceptance']))]['minimum'].pop()
    if change=='bounds-boolean':raw['acceptance'][next(iter(raw['acceptance']))]['minimum'][1]=True
    if change=='metal':raw['studies'][1]['conductors']['positive']['top']['conductivity']*=1.01
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('invalid full grid meshed'))
    with pytest.raises(ValueError):TwoGroundFaceSampledResolutionYieldDocument.from_dict(raw)


def test_old_current_documents_cannot_be_retyped():
    from test_sampled_panel_resolution_yield_document import document as old_document
    raw=old_document().to_dict();raw['schema']='sipi.two-ground-face-sampled-resolution-yield/1'
    with pytest.raises(ValueError):TwoGroundFaceSampledResolutionYieldDocument.from_dict(raw)
