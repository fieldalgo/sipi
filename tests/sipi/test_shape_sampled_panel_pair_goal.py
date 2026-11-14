# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit shape-current grid goals retain bounded search and frozen controls."""
import json
from dataclasses import FrozenInstanceError
from types import SimpleNamespace
import numpy as np
import pytest
from sipi.shape_panel_line import ShapePanelTransmissionLineDocument,ShapePanelLineError
from sipi.shape_sampled_panel_pair_goal import seek_shape_sampled_panel_forward_pair_impedances as seek
from sipi.sampled_panel_pair_goal import SampledPanelForwardPairGoalError
from test_sampled_panel_pair_goal import factory as legacy_factory,targets,F,BOUNDS
from test_shape_sampled_panel_pair_study import synthetic


def factory(x,y):
    return ShapePanelTransmissionLineDocument(legacy_factory(x,y))


@pytest.mark.parametrize('scales',[(1.,1.),(1000.,.001)])
@pytest.mark.parametrize('lossless',[False,True])
def test_independent_modal_grid_search_and_unit_scaling(monkeypatch,scales,lossless):
    calls=synthetic(monkeypatch,lossless=lossless);scales=np.array(scales)
    result=seek(lambda x,y:factory(x*scales[0],y*scales[1]),BOUNDS/scales[:,None],F,
        targets(lossless=lossless),tolerances=np.full((3,2),1e-6))
    np.testing.assert_allclose(np.array(result.parameters)*scales,[1.35,.8],rtol=1e-6)
    assert len(calls)==len(result.history)<=64 and len(result.refinements)==3
    for row in result.history:
        np.testing.assert_allclose(row.impedances,targets(*(np.array(row.parameters)*scales),lossless=lossless),rtol=1e-12,atol=0)
        assert row.input_json in calls
    report=result.to_dict();assert report['current_solver']['diagnostics']=={'transport_stub':1.}
    assert all(r['current_solver']['diagnostics']=={'transport_stub':1.} for r in report['refinements'])
    assert result.document.dumps()==result.input_json and result.document.current_options['step_fraction']==.001
    with pytest.raises(FrozenInstanceError):result.frequencies=()


def test_matching_start_uses_one_factory_and_three_frozen_refinements(monkeypatch):
    calls=synthetic(monkeypatch);made=[]
    def once(x,y):
        made.append((x,y));assert len(made)==1;return factory(x,y)
    result=seek(once,BOUNDS,F,targets(),tolerances=np.full((3,2),1e-8),initial=[1.35,.8],max_evaluations=4)
    assert len(calls)==4 and len(made)==1
    base=result.document.to_dict()
    for row,stage in zip(result.refinements,('volume-refinement','panel-refinement','joint-refinement')):
        assert row.evaluation.stage==stage and row.document.dumps()==row.evaluation.input_json
        data=row.document.to_dict();assert data['step_fraction']==base['step_fraction']
        assert data['line']['line']['frequency_hz']==list(F)
        assert data['line']['panel']['panels_per_edge']==base['line']['panel']['panels_per_edge']*(1 if stage=='volume-refinement' else 2)
        for key in ('edge_size','far_size','grade'):
            assert data['line']['line']['cross_section']['mesh'][key]==base['line']['line']['cross_section']['mesh'][key]/(1 if stage=='panel-refinement' else 2)


@pytest.mark.parametrize('attempt',[1,2,3,4])
def test_current_failure_preserves_frequency_history_attempt_and_partial_cause(monkeypatch,attempt):
    calls=synthetic(monkeypatch,fail_at=attempt)
    with pytest.raises(SampledPanelForwardPairGoalError) as caught:
        seek(factory,BOUNDS,F,targets(),tolerances=np.full((3,2),1e-8),initial=[1.35,.8],max_evaluations=4)
    error=caught.value
    assert error.attempts==len(calls)==attempt and len(error.history)==attempt-1 and error.frequencies==tuple(F)
    assert error.input_json==calls[-1] and isinstance(error.__cause__,ShapePanelLineError)
    cause=error.__cause__.to_dict();assert cause['message']=='original failed current batch'
    assert cause['input']==json.loads(calls[-1]) and cause['partial_current']['samples']==[]


@pytest.mark.parametrize('kind',['step','panels','names','frequency','length'])
def test_changed_factory_contract_fails_before_second_field(monkeypatch,kind):
    calls=synthetic(monkeypatch);made=[]
    def changed(x,y):
        raw=factory(x,y).to_dict();made.append(1)
        if len(made)>1:
            if kind=='step':raw['step_fraction']=.002
            if kind=='panels':raw['line']['panel']['panels_per_edge']=48
            if kind=='names':
                trace=raw['line']['line']['cross_section']['traces'][0]
                old_name=trace['name'];trace['name']='changed'
                metals=raw['line']['line']['conductor']['conductors'];metals['changed']=metals.pop(old_name)
            if kind=='frequency':raw['line']['line']['frequency_hz'][-1]=4e9
            if kind=='length':raw['line']['line']['length_m']=.01
        return ShapePanelTransmissionLineDocument.from_dict(raw)
    with pytest.raises(SampledPanelForwardPairGoalError) as caught:
        seek(changed,BOUNDS,F,targets(),tolerances=np.full((3,2),1e-8))
    assert caught.value.attempts==2 and len(calls)==1 and caught.value.stage=='search/validation'


@pytest.mark.parametrize('key,value',[('frequencies',[1e9]),('frequencies',[1e9,1e9]),
    ('targets',[100.,40.]),('targets',np.ones((3,2),complex)),('tolerances',1e-3),
    ('tolerances',np.zeros((3,2))),('max_evaluations',3),('max_evaluations',True),
    ('bounds',[[0.,1.],[.5,1.5]]),('initial',[100.,1.])])
def test_invalid_controls_precede_factory(key,value):
    def forbidden(*a):pytest.fail('invalid input invoked factory')
    kwargs=dict(bounds=BOUNDS,frequencies=F,targets=targets(),tolerances=np.full((3,2),1e-6))
    kwargs[key]=value
    with pytest.raises((ValueError,TypeError)):seek(forbidden,**kwargs)


def test_future_shape_offset_refinement_admitted_before_field(monkeypatch):
    calls=synthetic(monkeypatch)
    def oversized(x,y):
        raw=factory(x,y).to_dict();raw['line']['panel']['panels_per_edge']=129
        return ShapePanelTransmissionLineDocument.from_dict(raw)
    with pytest.raises(SampledPanelForwardPairGoalError) as caught:
        seek(oversized,BOUNDS,F,targets(),tolerances=np.full((3,2),1e-8),initial=[1.35,.8])
    assert caught.value.attempts==1 and not calls and caught.value.stage=='search/validation'


@pytest.mark.parametrize('index',[0,1,2])
def test_bad_frequency_diagnostic_rejects_whole_batch(monkeypatch,index):
    calls=synthetic(monkeypatch);previous=ShapePanelTransmissionLineDocument.analyze
    def broken(self):
        result=previous(self);c=result.characteristic();m=c.mixed_mode();matrix=m.z_characteristic.copy();matrix[index,0,0]=np.nan
        result.characteristic=lambda:SimpleNamespace(basis=c.basis,names=c.names,frequency=c.frequency,
            mixed_mode=lambda:SimpleNamespace(basis=m.basis,names=m.names,frequency=m.frequency,z_characteristic=matrix))
        return result
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',broken)
    with pytest.raises(SampledPanelForwardPairGoalError) as caught:
        seek(factory,BOUNDS,F,targets(),tolerances=np.full((3,2),1e-8))
    assert len(calls)==1 and not caught.value.history and caught.value.stage=='search/diagnostic'


def test_unreachable_frequency_targets_are_not_returned_as_a_design(monkeypatch):
    synthetic(monkeypatch);target=targets().copy();target[1,0]*=1.2
    with pytest.raises(SampledPanelForwardPairGoalError) as caught:
        seek(factory,BOUNDS,F,target,tolerances=np.full((3,2),1e-6),initial=[1.35,.8])
    assert caught.value.stage in ('convergence','budget') and caught.value.history


def test_budget_and_interrupt_count_whole_attempts(monkeypatch):
    calls=synthetic(monkeypatch)
    with pytest.raises(SampledPanelForwardPairGoalError) as caught:
        seek(factory,BOUNDS,F,targets(),tolerances=np.full((3,2),1e-8),max_evaluations=4)
    assert caught.value.stage=='budget' and caught.value.attempts==len(calls)==1
    calls=synthetic(monkeypatch,fail_at=2,interrupt=True)
    with pytest.raises(KeyboardInterrupt):
        seek(factory,BOUNDS,F,targets(),tolerances=np.full((3,2),1e-8),initial=[1.35,.8],max_evaluations=4)
    assert len(calls)==2
