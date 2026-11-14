# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit current-method goals retain physical launches and bounded failures."""
import json
from types import SimpleNamespace
import numpy as np
import pytest

from sipi import rlgc_characteristic
from sipi.shape_panel_line import ShapePanelTransmissionLineDocument, ShapePanelLineError
from sipi.panel_shape_conductor import PanelShapeCurrentError
from sipi.shape_panel_pair_goal import seek_shape_panel_forward_pair_impedances as seek
from sipi.pair_line_goal import ForwardPairGoalError
from test_panel_pair_goal import (factory as old_factory, modal, quantities,
                                  BOUNDS, ROOT, STAGES)


def factory(x,y):
    return ShapePanelTransmissionLineDocument(old_factory(x,y))


def synthetic(monkeypatch, *, lossless=False, fail_at=None, interrupt=False):
    calls=[]
    def analyze(self):
        calls.append(self.dumps())
        if len(calls)==fail_at:
            if interrupt:raise KeyboardInterrupt()
            cause=PanelShapeCurrentError('original current refusal',samples=())
            raise ShapePanelLineError(cause,stage='current',input_json=self.dumps(),
                                     factors=None,settings=self.current_options) from cause
        traces=self.line.line.cross_section.section.traces
        x=traces[0].width/.3e-3;y=(traces[1].x0-traces[0].x1)/.2e-3
        matrices,_=modal(x,y,lossless)
        return SimpleNamespace(input_json=self.dumps(),frequency=np.array([1e9]),
            names=('positive','negative'), characteristic=lambda:rlgc_characteristic(
                [1e9],**matrices,names=('positive','negative')))
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',analyze)
    return calls


@pytest.mark.parametrize('scale',[(1.,1.),(1000.,.001)])
@pytest.mark.parametrize('lossless',[False,True])
def test_independent_modal_root_with_scaled_parameters(monkeypatch,scale,lossless):
    calls=synthetic(monkeypatch,lossless=lossless);scale=np.array(scale)
    goal=seek(lambda x,y:factory(x*scale[0],y*scale[1]),BOUNDS/scale[:,None],
              quantities(*ROOT,lossless),tolerances=[1e-6]*2)
    np.testing.assert_allclose(np.array(goal.parameters)*scale,ROOT,rtol=1e-6)
    assert len(calls)==len(goal.history)<=64
    assert [r.evaluation.stage for r in goal.refinements]==STAGES
    assert len({r.parameters for r in goal.history[:-3]})==len(goal.history)-3
    for row in goal.history:
        np.testing.assert_allclose(row.impedances,quantities(*(np.array(row.parameters)*scale),lossless),rtol=1e-13)
    for row in goal.refinements:
        assert row.document.dumps()==row.evaluation.input_json
        np.testing.assert_allclose(row.evaluation.impedances,goal.targets,rtol=0,atol=1e-6)


def test_frozen_selected_input_and_exact_four_attempts(monkeypatch):
    calls=synthetic(monkeypatch);made=[]
    def once(x,y):
        made.append((x,y));assert len(made)==1;return factory(x,y)
    goal=seek(once,BOUNDS,quantities(*ROOT),tolerances=[1e-8]*2,initial=ROOT,max_evaluations=4)
    assert len(calls)==len(goal.history)==4
    for index,row in enumerate(goal.refinements):
        expected=goal.document.to_dict()
        if index!=1:
            for key in ('edge_size','far_size','grade'):
                expected['line']['line']['cross_section']['mesh'][key]/=2
        if index!=0:expected['line']['panel']['panels_per_edge']*=2
        assert row.document.to_dict()==expected


@pytest.mark.parametrize('attempt',[1,2,3,4])
def test_failed_current_preserves_cause_history_and_original_input(monkeypatch,attempt):
    calls=synthetic(monkeypatch,fail_at=attempt)
    with pytest.raises(ForwardPairGoalError) as caught:
        seek(factory,BOUNDS,quantities(*ROOT),tolerances=[1e-8]*2,initial=ROOT,max_evaluations=4)
    e=caught.value
    assert e.attempts==len(calls)==attempt and len(e.history)==attempt-1
    assert e.stage==(['search']+STAGES)[attempt-1]+'/extraction'
    assert e.input_json==calls[-1] and e.cause_type=='ShapePanelLineError'
    assert isinstance(e.__cause__,ShapePanelLineError)
    details=e.__cause__.to_dict()
    assert details['message']=='original current refusal'
    assert details['partial_current']['samples']==[]
    assert details['partial_current']['cause_type']=='PanelShapeCurrentError'
    assert isinstance(e.__cause__.__cause__,PanelShapeCurrentError)


@pytest.mark.parametrize('attempt',[1,2,3,4])
def test_interrupts_never_become_failed_goals(monkeypatch,attempt):
    calls=synthetic(monkeypatch,fail_at=attempt,interrupt=True)
    with pytest.raises(KeyboardInterrupt):
        seek(factory,BOUNDS,quantities(*ROOT),tolerances=[1e-8]*2,initial=ROOT,max_evaluations=4)
    assert len(calls)==attempt


@pytest.mark.parametrize('key,value',[('step_fraction',.002),('panels_per_edge',64),
                                     ('ground_modes',1024),('interpolation_degree',12)])
def test_method_controls_cannot_drift_during_search(monkeypatch,key,value):
    calls=synthetic(monkeypatch);made=[]
    def changing(x,y):
        data=factory(x,y).to_dict();made.append(1)
        if len(made)>1:
            if key=='step_fraction':data[key]=value
            else:data['line']['panel'][key]=value
        return ShapePanelTransmissionLineDocument.from_dict(data)
    with pytest.raises(ForwardPairGoalError) as caught:
        seek(changing,BOUNDS,quantities(*ROOT),tolerances=[1e-8]*2)
    assert caught.value.stage=='search/validation' and caught.value.attempts==2 and len(calls)==1


def test_old_panel_factory_is_not_silently_converted(monkeypatch):
    calls=synthetic(monkeypatch)
    with pytest.raises(ForwardPairGoalError) as caught:
        seek(old_factory,BOUNDS,quantities(*ROOT),tolerances=[1e-8]*2)
    assert caught.value.stage=='search/factory' and caught.value.cause_type=='TypeError' and not calls


@pytest.mark.parametrize('panels',[129,256])
def test_all_refinements_admitted_before_fields(monkeypatch,panels):
    calls=synthetic(monkeypatch)
    def oversized(x,y):
        data=factory(x,y).to_dict();data['line']['panel']['panels_per_edge']=panels
        return ShapePanelTransmissionLineDocument.from_dict(data)
    with pytest.raises(ForwardPairGoalError) as caught:
        seek(oversized,BOUNDS,quantities(*ROOT),tolerances=[1e-8]*2)
    assert caught.value.stage=='search/validation' and not calls


def test_three_actual_refinement_attempts_are_reserved(monkeypatch):
    calls=synthetic(monkeypatch)
    with pytest.raises(ForwardPairGoalError) as caught:
        seek(factory,BOUNDS,quantities(*ROOT),tolerances=[1e-8]*2,max_evaluations=4)
    assert caught.value.stage=='budget' and caught.value.attempts==len(calls)==1


@pytest.mark.parametrize('change',[
    dict(bounds=[[0,1],[1,2]]),dict(bounds=[[2,1],[1,2]]),dict(bounds=[1,2]),
    dict(targets=[0,1]),dict(targets=[100,np.inf]),dict(targets=[100,True]),
    dict(tolerances=[1,0]),dict(tolerances=[1,np.nan]),dict(initial=[.1,.3]),
    dict(initial=[False,.3]),dict(max_evaluations=True),dict(max_evaluations=3),dict(max_evaluations=10001)])
def test_invalid_controls_precede_factory(change):
    def forbidden(*a):pytest.fail('factory reached')
    kwargs=dict(bounds=BOUNDS,targets=[100.,40.],tolerances=[.25,.125]);kwargs.update(change)
    with pytest.raises(ValueError):seek(forbidden,**kwargs)
