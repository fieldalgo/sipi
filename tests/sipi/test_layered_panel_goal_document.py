# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit coated panel goals: strict transport and actual search replay."""
import json
import numpy as np
import pytest
from sipi import CrossSection
from sipi.execution import execute_saved, normalize_saved, saved_schemas
from sipi.panel_pair_goal_document import PanelForwardPairDesignDocument
from sipi.pair_line_goal_document import ForwardPairDesignDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.panel_pair_goal import seek_panel_forward_pair_impedances
from sipi.study import ImpedanceStudyDocument
from test_pair_line_goal_document import source, Q
from test_panel_pair_goal import synthetic, quantities
from test_layered_panel_goal import factory, independent, snapshot

SCHEMA = 'sipi.panel-forward-pair-design/2'


def document(*, physical=False):
    return PanelForwardPairDesignDocument.from_study(source(physical=physical),
        conductor=factory(.6e-3,.4e-3).to_dict()['line']['conductor'],
        targets=dict(zip(Q,[110.,40.] if physical else quantities(1.35,.8))),
        tolerances=dict(zip(Q,[.25,.125] if physical else [1e-6,1e-6])),
        initial=[.7e-3,.35e-3] if physical else None,max_evaluations=64)


def test_normalization_is_field_free_and_does_not_convert_to_fem(monkeypatch):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('normalization meshed'))
    doc=document();text=doc.dumps()
    assert normalize_saved(text)==text==PanelForwardPairDesignDocument.loads(text).dumps()
    assert SCHEMA in saved_schemas()
    with pytest.raises(TypeError,match='version 1 accessor'):doc.design
    with pytest.raises(ValueError):ForwardPairDesignDocument.loads(text)
    raw=doc.goal_input;raw['conductor']['reference']['coatings'][0]['thickness_m']=0
    raw['study']['parameters']['left_width']=1
    assert doc.dumps()==text and 'schema' not in doc.goal_input
    assert doc.panel_options==dict(panels_per_edge=32,ground_modes=512,interpolation_degree=10)


def test_modal_root_and_complete_transport(monkeypatch):
    synthetic(monkeypatch);doc=document();goal=doc.solve()
    direct=seek_panel_forward_pair_impedances(factory,[[.15e-3,.6e-3],[.1e-3,.3e-3]],
        quantities(1.35,.8),tolerances=[1e-6]*2)
    assert goal.to_dict()==direct.to_dict()
    output=execute_saved(doc.dumps())
    assert output['status']=='complete' and output['input']==doc.to_dict()
    assert output['error'] is None and output['result']==goal.to_dict()
    np.testing.assert_allclose(goal.parameters,[1.35*.3e-3,.8*.2e-3],rtol=1e-6)
    json.dumps(output,allow_nan=False)


@pytest.mark.parametrize('where',['root','study','panel','conductor','coating'])
@pytest.mark.parametrize('mode',['missing','unknown'])
def test_all_nested_keys_are_strict(where,mode):
    raw=document().to_dict()
    target={'root':raw,'study':raw['study'],'panel':raw['panel'],'conductor':raw['conductor'],
            'coating':raw['conductor']['reference']['coatings'][0]}[where]
    if mode=='missing':target.pop(next(iter(target)))
    else:target['unexpected']=1
    with pytest.raises(ValueError):PanelForwardPairDesignDocument.from_dict(raw)


@pytest.mark.parametrize('change',['legacy-schema','fem-schema','nested-legacy','duplicate','nan','list-schema'])
def test_schema_and_json_ambiguities_refused(change):
    raw=document().to_dict();text=json.dumps(raw)
    if change=='legacy-schema':raw['schema']='sipi.panel-forward-pair-design/1'
    if change=='fem-schema':raw['schema']='sipi.forward-pair-design/2'
    if change=='nested-legacy':raw=dict(schema=SCHEMA,design=raw,panel=raw['panel'])
    if change=='list-schema':raw['schema']=[]
    if change=='duplicate':text=text.replace('"ground_modes": 512','"ground_modes": 512, "ground_modes": 512')
    elif change=='nan':text=text.replace('"ground_modes": 512','"ground_modes": NaN')
    else:text=json.dumps(raw)
    with pytest.raises(ValueError):PanelForwardPairDesignDocument.loads(text)


@pytest.mark.parametrize('value',[0,1,2,3,True,4.,10001])
def test_budget_bounds(value):
    raw=document().to_dict();raw['max_evaluations']=value
    with pytest.raises(ValueError):PanelForwardPairDesignDocument.from_dict(raw)


@pytest.mark.parametrize('key,value',[('panels_per_edge',129),('panels_per_edge',True),
                                     ('ground_modes',63),('interpolation_degree',11)])
def test_future_refinement_admission(key,value):
    raw=document().to_dict();raw['panel'][key]=value
    with pytest.raises(ValueError):PanelForwardPairDesignDocument.from_dict(raw)


@pytest.mark.parametrize('mode',['target','tolerance','initial','bounds','variables','frequency','core'])
def test_invalid_physics_and_controls_before_any_field(monkeypatch,mode):
    raw=document().to_dict()
    if mode=='target':raw['targets_ohm'][Q[0]]=0
    if mode=='tolerance':raw['tolerances_ohm'][Q[1]]=True
    if mode=='initial':raw['initial']=[1.,.2e-3]
    if mode=='bounds':raw['study']['sampling']['variables'][0]['lower']=0
    if mode=='variables':raw['study']['sampling']['variables'].pop()
    if mode=='frequency':raw['study']['material_evaluation']['frequency_hz']=0
    if mode=='core':raw['conductor']['ground_thickness']=10e-6
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('rejected input meshed'))
    with pytest.raises(ValueError):PanelForwardPairDesignDocument.from_dict(raw)


@pytest.mark.parametrize('attempt',[1,2,3,4])
def test_original_partial_failure_is_retained(monkeypatch,attempt):
    calls=synthetic(monkeypatch,fail_at=attempt);raw=document().to_dict()
    raw.update(initial=[1.35*.3e-3,.8*.2e-3],max_evaluations=4)
    output=execute_saved(PanelForwardPairDesignDocument.from_dict(raw).dumps(),max_evaluations=4)
    error=output['error']
    assert output['status']=='failed' and output['result'] is None
    assert error['attempts']==attempt and len(error['history'])==attempt-1
    assert error['input']==json.loads(calls[-1]) and error['cause_type']=='ArithmeticError'
    assert error['stage']==['search/extraction','volume-refinement/extraction',
                           'panel-refinement/extraction','joint-refinement/extraction'][attempt-1]
    assert error['unit']=='ohm' and error['quantities']==list(Q)
    json.dumps(output,allow_nan=False)


@pytest.mark.parametrize('options',[dict(max_evaluations=63),dict(diagnostics=['characteristic']),dict(max_input_bytes=16)])
def test_transport_admission_before_solver(monkeypatch,options):
    doc=document()
    monkeypatch.setattr(PanelForwardPairDesignDocument,'solve',lambda *a,**k:pytest.fail('rejected request solved'))
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('rejected request meshed'))
    with pytest.raises(ValueError):execute_saved(doc.dumps(),**options)


def test_reversed_variables_keep_physical_order(monkeypatch):
    synthetic(monkeypatch);raw=document().to_dict()
    raw['study']['sampling']['variables'].reverse();raw['initial']=[.2e-3,.375e-3]
    goal=PanelForwardPairDesignDocument.from_dict(raw).solve()
    np.testing.assert_allclose(goal.parameters,[.8*.2e-3,1.35*.3e-3],rtol=1e-6)


def test_fixed_pitch_and_material_leaf_preserve_coatings(monkeypatch):
    import sipi.panel_pair_goal_document as module
    from sipi.dielectric import ConstantDielectric,dielectric_to_dict
    raw=source().to_dict();raw.update(fixed_pitch_m=.95e-3,schema='sipi.impedance-study/4')
    raw['material_evaluation']['materials']={'substrate':dielectric_to_dict(ConstantDielectric(4.,.02))}
    raw['material_variables']={'dk':dict(region='substrate',path=['eps_r'])}
    raw['sampling']['variables']=[dict(name='left_width',lower=.4e-3,upper=.8e-3),dict(name='dk',lower=3.,upper=5.)]
    metal=document().goal_input['conductor']
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('preflight field'))
    monkeypatch.setattr(ImpedanceStudyDocument,'analyze',lambda *a,**k:pytest.fail('preliminary study'))
    doc=PanelForwardPairDesignDocument.from_study(raw,conductor=metal,
        targets=dict(zip(Q,[110.,40.])),tolerances=dict(zip(Q,[1.,1.])),initial=[.65e-3,3.7])
    def inspect(factory,bounds,targets,**options):
        for width,eps in ((.4e-3,3.),(.65e-3,3.7),(.8e-3,5.)):
            line=factory(width,eps).to_dict()['line'];traces=line['cross_section']['traces']
            assert traces[1]['x']-traces[0]['x']==pytest.approx(.95e-3,rel=1e-12)
            assert line['materials']['substrate']['parameters']['eps_r']==eps
            assert line['conductor']==metal and line['schema']=='sipi.transmission-line/7'
        return 'inspected'
    monkeypatch.setattr(module,'seek_panel_forward_pair_impedances',inspect)
    assert doc.solve()=='inspected'


@pytest.fixture(scope='module')
def physical():
    doc=document(physical=True);fields={};original=PanelTransmissionLineDocument.analyze
    with pytest.MonkeyPatch.context() as patch:
        def capture(self):
            result=original(self);fields[self.dumps()]=result;return result
        patch.setattr(PanelTransmissionLineDocument,'analyze',capture)
        goal=doc.solve()
    return doc,goal,fields


def test_actual_saved_search_retains_inputs_and_independent_fields(physical,record_property):
    doc,goal,fields=physical
    record_property('saved_coated_panel_search',json.dumps(goal.to_dict(),allow_nan=False))
    record_property('saved_coated_panel_fields',json.dumps([snapshot(r) for r in fields.values()],allow_nan=False))
    assert 4<len(goal.history)==len(fields)<=64
    assert np.any(abs(np.array(goal.history[0].impedances)-goal.targets)>goal.tolerances)
    assert goal.document.dumps()==factory(*goal.parameters).dumps()
    results=[goal.result]+[r.result for r in goal.refinements]
    for values in [goal.impedances]+[r.evaluation.impedances for r in goal.refinements]:
        assert np.all(abs(np.array(values)-goal.targets)<=goal.tolerances)
    record_property('saved_coated_panel_references',json.dumps([independent(r) for r in results]))


def test_direct_and_common_replay_use_exact_actual_search_inputs(physical,monkeypatch):
    doc,goal,fields=physical;calls=[]
    def replay(self):
        calls.append(self.dumps())
        assert self.dumps() in fields,'saved and direct field inputs differ'
        return fields[self.dumps()]
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',replay)
    direct=seek_panel_forward_pair_impedances(factory,[[.4e-3,.9e-3],[.2e-3,.6e-3]],
        [110.,40.],tolerances=[.25,.125],initial=[.7e-3,.35e-3],max_evaluations=64)
    assert direct.to_dict()==goal.to_dict() and len(calls)==len(goal.history)
    calls.clear();out=execute_saved(doc.dumps(),max_evaluations=64)
    assert out['status']=='complete' and out['result']==goal.to_dict()
    assert out['input']==doc.to_dict() and out['error'] is None
    assert len(calls)==len(goal.history)
