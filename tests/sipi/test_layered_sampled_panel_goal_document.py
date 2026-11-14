# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit coated frequency-grid goals: strict inputs and retained execution."""
import json
import numpy as np
import pytest
from sipi import CrossSection
from sipi.execution import execute_saved, normalize_saved, saved_schemas
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.pair_line_goal_document import ForwardPairDesignDocument
from sipi.sampled_panel_pair_goal import seek_sampled_panel_forward_pair_impedances
from sipi.sampled_panel_pair_goal_document import SampledPanelForwardPairDesignDocument as Document
from sipi.dielectric import DebyeDielectric, TabulatedDielectric, dielectric_to_dict
from test_pair_line_goal_document import source, Q
from test_sampled_panel_pair_goal import F, targets, synthetic
from test_layered_panel_goal import factory as single_factory, independent, snapshot
from test_layered_sampled_panel_goal import factory, FREQUENCIES

SCHEMA='sipi.sampled-panel-forward-pair-design/2'
SELECTED=[.0006050501120606677,.0004089487094424394]


def document(*,physical=False):
    study=source(physical=physical).to_dict()
    frequencies=FREQUENCIES if physical else F.tolist()
    study['material_evaluation']['frequency_hz']=frequencies[0]
    values=np.array([[110.,40.]]*3) if physical else targets()
    tolerances=np.array([[.25,.125]]*3) if physical else np.full((3,2),1e-6)
    return Document(study,conductor=single_factory(.6e-3,.4e-3).to_dict()['line']['conductor'],
        frequencies=frequencies,targets={q:values[:,i].tolist() for i,q in enumerate(Q)},
        tolerances={q:tolerances[:,i].tolist() for i,q in enumerate(Q)},
        initial=SELECTED if physical else None,max_evaluations=4 if physical else 64,schema=SCHEMA)


def test_field_free_canonical_snapshot_without_coated_fem_conversion(monkeypatch):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('normalization meshed'))
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('normalization solved'))
    doc=document();text=doc.dumps()
    assert normalize_saved(text)==text==Document.loads(text).dumps() and SCHEMA in saved_schemas()
    raw=doc.to_dict();raw['conductor']['reference']['coatings'][0]['thickness_m']=0
    raw['frequency_hz'][0]=1.
    assert doc.dumps()==text
    with pytest.raises(ValueError):ForwardPairDesignDocument.loads(text)


def test_synthetic_search_matches_direct_and_common_execution(monkeypatch):
    synthetic(monkeypatch);doc=document();goal=doc.solve()
    def direct_factory(w,g):
        raw=single_factory(w,g).to_dict();raw['line']['frequency_hz']=F.tolist()
        return PanelTransmissionLineDocument.from_dict(raw)
    direct=seek_sampled_panel_forward_pair_impedances(direct_factory,
        [[.15e-3,.6e-3],[.1e-3,.3e-3]],F,targets(),tolerances=np.full((3,2),1e-6))
    assert goal.to_dict()==direct.to_dict()
    out=execute_saved(doc.dumps())
    assert out['status']=='complete' and out['error'] is None
    assert out['input']==doc.to_dict() and out['result']==goal.to_dict()
    np.testing.assert_allclose(goal.parameters,[1.35*.3e-3,.8*.2e-3],rtol=1e-6)


@pytest.mark.parametrize('where',['root','study','conductor','coating','panel','targets_ohm','tolerances_ohm'])
@pytest.mark.parametrize('change',['missing','unknown'])
def test_strict_nested_keys(where,change):
    raw=document().to_dict()
    target=raw if where=='root' else (raw['conductor']['reference']['coatings'][0] if where=='coating' else raw[where])
    if change=='missing':target.pop(next(iter(target)))
    else:target['unexpected']=1
    with pytest.raises(ValueError):Document.from_dict(raw)


@pytest.mark.parametrize('mode',['legacy','fem','unknown','list','duplicate','nan','nested'])
def test_versions_and_ambiguous_json(mode):
    raw=document().to_dict();text=json.dumps(raw)
    if mode=='legacy':raw['schema']='sipi.sampled-panel-forward-pair-design/1'
    if mode=='fem':raw['schema']='sipi.forward-pair-design/2'
    if mode=='unknown':raw['schema']='sipi.sampled-panel-forward-pair-design/unsupported'
    if mode=='list':raw['schema']=[]
    if mode=='nested':raw=dict(schema=SCHEMA,design=raw,panel=raw['panel'])
    if mode=='duplicate':text=text.replace('"ground_modes": 512','"ground_modes": 512, "ground_modes": 512')
    elif mode=='nan':text=text.replace('"ground_modes": 512','"ground_modes": NaN')
    else:text=json.dumps(raw)
    with pytest.raises(ValueError):Document.loads(text)


@pytest.mark.parametrize('mode',['anchor','target','tolerance','budget','initial','panel','band','core','corner-core'])
def test_full_grid_and_future_inputs_reject_before_fields(monkeypatch,mode):
    raw=document().to_dict()
    if mode=='anchor':raw['study']['material_evaluation']['frequency_hz']=1e9
    if mode=='target':raw['targets_ohm'][Q[0]][-1]=0
    if mode=='tolerance':raw['tolerances_ohm'][Q[1]][-1]=True
    if mode=='budget':raw['max_evaluations']=3
    if mode=='initial':raw['initial']=[1.,.2e-3]
    if mode=='panel':raw['panel']['panels_per_edge']=256
    if mode=='band':raw['study']['material_evaluation']['materials']['substrate']=dielectric_to_dict(
        TabulatedDielectric((F[0],1e9),(4.,4.),(.02,.02)))
    if mode=='core':raw['conductor']['ground_thickness']=10e-6
    if mode=='corner-core':
        raw['study']['sampling']['variables'][0]=dict(name='left_thickness',lower=2e-6,upper=35e-6)
        raw['initial']=[35e-6,.2e-3]
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('invalid input meshed'))
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('invalid input solved'))
    with pytest.raises(ValueError):Document.from_dict(raw)


@pytest.mark.parametrize('attempt',[1,2,3,4])
def test_each_failed_batch_preserves_all_frequency_and_input_context(monkeypatch,attempt):
    calls=synthetic(monkeypatch,fail_at=attempt);raw=document().to_dict()
    raw.update(initial=[1.35*.3e-3,.8*.2e-3],max_evaluations=4)
    out=execute_saved(Document.from_dict(raw).dumps(),max_evaluations=4);error=out['error']
    assert out['status']=='failed' and out['result'] is None
    assert error['frequencies_hz']==F.tolist() and error['attempts']==len(calls)==attempt
    assert len(error['history'])==attempt-1 and error['cause_type']=='ArithmeticError'
    assert error['input']==json.loads(calls[-1]) and error['input']['schema']=='sipi.panel-transmission-line/2'
    assert error['stage']==['search','volume-refinement','panel-refinement','joint-refinement'][attempt-1]+'/extraction'


@pytest.mark.parametrize('options',[dict(max_evaluations=63),dict(diagnostics=['characteristic']),dict(max_input_bytes=16)])
def test_common_limits_before_solver(monkeypatch,options):
    doc=document()
    monkeypatch.setattr(Document,'solve',lambda *a,**k:pytest.fail('rejected request solved'))
    with pytest.raises(ValueError):execute_saved(doc.dumps(),**options)


def test_fixed_pitch_material_leaf_and_ordered_coatings(monkeypatch):
    import sipi.sampled_panel_pair_goal_document as module
    raw=document().to_dict();study=raw['study'];study['schema']='sipi.impedance-study/4'
    study['fixed_pitch_m']=.95e-3
    study['material_evaluation']['materials']['substrate']=dielectric_to_dict(DebyeDielectric(3.,(.7,),(1e9,)))
    study['material_variables']={'strength':dict(region='substrate',path=['strengths',0])}
    study['sampling']['variables']=[dict(name='left_width',lower=.4e-3,upper=.8e-3),dict(name='strength',lower=.5,upper=.9)]
    raw['initial']=[.65e-3,.7]
    def inspect(factory,bounds,frequencies,requested,**options):
        assert bounds==[[.4e-3,.8e-3],[.5,.9]] and frequencies==F.tolist()
        for width,strength in ((.4e-3,.5),(.65e-3,.7),(.8e-3,.9)):
            d=factory(width,strength).to_dict();t=d['line']['cross_section']['traces']
            assert d['schema']=='sipi.panel-transmission-line/2' and d['line']['schema']=='sipi.transmission-line/7'
            assert d['line']['conductor']==raw['conductor'] and d['line']['frequency_hz']==frequencies
            assert d['line']['materials']['substrate']['parameters']['strengths']==[strength]
            assert abs(t[1]['x']-t[0]['x']-.95e-3)<1e-15
        return 'inspected'
    monkeypatch.setattr(module,'seek_sampled_panel_forward_pair_impedances',inspect)
    assert Document.from_dict(raw).solve()=='inspected'


def test_actual_four_batches_and_exact_direct_common_replay(monkeypatch,record_property):
    doc=document(physical=True);fields={};original=PanelTransmissionLineDocument.analyze
    def capture(self):
        result=original(self);fields[self.dumps()]=result;return result
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',capture)
    goal=doc.solve()
    record_property('saved_coated_sampled_fields',json.dumps([snapshot(r) for r in fields.values()],allow_nan=False))
    record_property('saved_coated_sampled_references',json.dumps([independent(r) for r in fields.values()]))
    assert len(fields)==len(goal.history)==4 and np.all(abs(np.array(goal.residuals))<=goal.tolerances)
    calls=[]
    def replay(self):calls.append(self.dumps());return fields[self.dumps()]
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',replay)
    direct=seek_sampled_panel_forward_pair_impedances(factory,[[.4e-3,.9e-3],[.2e-3,.6e-3]],
        FREQUENCIES,[[110.,40.]]*3,tolerances=[[.25,.125]]*3,initial=SELECTED,max_evaluations=4)
    assert direct.to_dict()==goal.to_dict() and len(calls)==4
    out=execute_saved(doc.dumps(),max_evaluations=4)
    assert out['status']=='complete' and out['error'] is None and len(calls)==8
    assert out['result']==goal.to_dict() and out['input']==doc.to_dict()
    record_property('saved_coated_sampled_execution',json.dumps(out,allow_nan=False))
