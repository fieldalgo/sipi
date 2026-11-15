# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit two-ground grids retain bounded search and independent launch checks."""
from dataclasses import FrozenInstanceError
from types import SimpleNamespace
import json
import numpy as np
import pytest
from scipy.linalg import sqrtm

from sipi import rlgc_characteristic
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument as Line, TwoGroundFacePanelLineError
from sipi.two_ground_face_sampled_pair_goal import seek_two_ground_face_sampled_forward_pair_impedances as seek
from sipi.sampled_panel_pair_goal import SampledPanelForwardPairGoalError
from sipi.two_ground_face_pair_goal import seek_two_ground_face_forward_pair_impedances
from test_two_ground_face_pair_goal import physical_document
from test_sampled_panel_pair_goal import modal, targets, BOUNDS, T, A

F = [1e9, 2e9, 5e9]
STAGES = ['volume-refinement','panel-refinement','joint-refinement']


def document(width, gap, frequencies=F):
    raw = physical_document(width,gap).to_dict()
    raw['frequency_hz'] = list(frequencies)
    return Line.from_dict(raw)


def factory(x,y,frequencies=F):
    return document(x*.3e-3,y*.2e-3,frequencies)


def synthetic(monkeypatch, *, lossless=False, fail_at=None, interrupt=False):
    calls = []
    def analyze(self):
        calls.append(self.dumps())
        if len(calls) == fail_at:
            if interrupt: raise KeyboardInterrupt()
            cause = ArithmeticError('original current batch refusal')
            raise TwoGroundFacePanelLineError(cause,stage='current',input_json=self.dumps(),
                factors=None,settings=self.current_options,mesh_observation=None) from cause
        traces = self.cross_section.section.traces
        x = traces[0].width/.3e-3; y = (traces[1].x0-traces[0].x1)/.2e-3
        f = np.array(self.to_dict()['frequency_hz']); matrices,_ = modal(x,y,f,lossless)
        return SimpleNamespace(input_json=self.dumps(),frequency=f,names=('positive','negative'),
            characteristic=lambda:rlgc_characteristic(f,**matrices,names=('positive','negative')),
            current_record=lambda:dict(kind='test-only-synthetic'),mesh_record=lambda:dict(kind='test-only-synthetic'))
    monkeypatch.setattr(Line,'analyze',analyze)
    return calls


@pytest.mark.parametrize('lossless',[False,True])
@pytest.mark.parametrize('scale',[(1.,1.),(1000.,.001)])
def test_independent_modal_frequency_root_and_parameter_scaling(monkeypatch,lossless,scale):
    calls = synthetic(monkeypatch,lossless=lossless); scale=np.array(scale)
    result = seek(lambda x,y:factory(x*scale[0],y*scale[1]),BOUNDS/scale[:,None],F,
        targets(frequencies=F,lossless=lossless),tolerances=np.full((3,2),1e-6))
    np.testing.assert_allclose(np.array(result.parameters)*scale,[1.35,.8],rtol=1e-6)
    assert len(calls) == len(result.history) <= 64
    assert [r.evaluation.stage for r in result.refinements] == STAGES
    for row in result.history:
        np.testing.assert_allclose(row.impedances,targets(*(np.array(row.parameters)*scale),
            frequencies=F,lossless=lossless),rtol=1e-12,atol=0)
    saved = result.to_dict()
    assert saved['current_solver'] == saved['dielectric_mesh'] == dict(kind='test-only-synthetic')
    assert all(r['current_solver'] == r['dielectric_mesh'] == dict(kind='test-only-synthetic') for r in saved['refinements'])
    json.dumps(saved,allow_nan=False)
    with pytest.raises(FrozenInstanceError): result.parameters = (1.,1.)


def test_independent_skrf_modal_frequency_reference(monkeypatch):
    import skrf
    synthetic(monkeypatch)
    scales=np.array([1.35,.8]);d=dict(R=np.array([300.,2.])*scales,L=np.array([200e-9,400e-9])*scales,
        G=np.array([.005,.003])/scales,C=np.array([100e-12,80e-12])/scales)
    media=[skrf.media.DistributedCircuit(skrf.Frequency.from_f(F,unit='hz'),**{k:v[i] for k,v in d.items()}) for i in range(2)]
    matrix=np.array([T@np.diag([m.z0[j] for m in media])@T.T for j in range(len(F))])
    requested=np.diagonal(A@matrix@A.T,axis1=1,axis2=2).real
    result=seek(factory,BOUNDS,F,requested,tolerances=np.full((3,2),1e-6))
    scales=np.array(result.parameters)
    selected=dict(R=np.array([300.,2.])*scales,L=np.array([200e-9,400e-9])*scales,
        G=np.array([.005,.003])/scales,C=np.array([100e-12,80e-12])/scales)
    media=[skrf.media.DistributedCircuit(skrf.Frequency.from_f(F,unit='hz'),**{k:v[i] for k,v in selected.items()}) for i in range(2)]
    reference=np.array([T@np.diag([m.z0[j] for m in media])@T.T for j in range(len(F))])
    np.testing.assert_allclose(result.result.characteristic().z_characteristic,reference,rtol=1e-10,atol=0)
    np.testing.assert_allclose(result.impedances,requested,rtol=0,atol=1e-6)


def test_one_factory_call_and_frozen_refinements_match_single_frequency_goals(monkeypatch):
    calls=synthetic(monkeypatch);made=[]
    def once(x,y):
        made.append((x,y));assert len(made)==1;return factory(x,y)
    result=seek(once,BOUNDS,F,targets(frequencies=F),tolerances=np.full((3,2),1e-8),
        initial=[1.35,.8],max_evaluations=4)
    assert len(calls)==len(result.history)==4
    base=result.document.to_dict()
    for index,row in enumerate(result.refinements):
        raw=json.loads(json.dumps(base))
        if index!=1:
            for key in ('edge_size','far_size','grade'):raw['cross_section']['mesh'][key]/=2
        if index!=0:raw['panel']['panels_per_edge']*=2
        assert row.document.to_dict()==raw and row.result.input_json==row.evaluation.input_json
    for i,f in enumerate(F):
        single=seek_two_ground_face_forward_pair_impedances(lambda x,y:factory(x,y,[f]),BOUNDS,
            targets(frequencies=[f])[0],tolerances=[1e-8]*2,initial=[1.35,.8],max_evaluations=4)
        np.testing.assert_allclose(single.impedances,result.impedances[i],rtol=1e-12,atol=0)


def test_maximum_grid_retains_four_batch_budget(monkeypatch):
    calls=synthetic(monkeypatch);f=np.geomspace(F[0],F[-1],64)
    result=seek(lambda x,y:factory(x,y,f),BOUNDS,f,targets(frequencies=f),
        tolerances=np.full((64,2),1e-8),initial=[1.35,.8],max_evaluations=4)
    assert len(calls)==4 and len(result.impedances)==64


@pytest.mark.parametrize('attempt',[1,2,3,4])
def test_failed_batch_preserves_input_typed_cause_and_attempts(monkeypatch,attempt):
    calls=synthetic(monkeypatch,fail_at=attempt)
    with pytest.raises(SampledPanelForwardPairGoalError) as caught:
        seek(factory,BOUNDS,F,targets(frequencies=F),tolerances=np.full((3,2),1e-8),initial=[1.35,.8],max_evaluations=4)
    error=caught.value
    assert error.attempts==len(calls)==attempt and len(error.history)==attempt-1
    assert error.stage==(['search']+STAGES)[attempt-1]+'/extraction'
    assert error.input_json==calls[-1] and error.cause_type=='TwoGroundFacePanelLineError'
    assert isinstance(error.__cause__,TwoGroundFacePanelLineError)
    assert error.__cause__.to_dict()['input']==json.loads(error.input_json)
    assert error.__cause__.cause_type=='ArithmeticError'
    assert error.frequencies==tuple(F)


@pytest.mark.parametrize('frequency',[0,1,2])
def test_one_refined_frequency_miss_is_not_averaged_away(monkeypatch,frequency):
    calls=synthetic(monkeypatch);previous=Line.analyze
    def broken(self):
        line=previous(self)
        if len(calls)==2:
            c=line.characteristic();m=c.mixed_mode();matrix=m.z_characteristic.copy();matrix[frequency,0,0]*=1.01
            line.characteristic=lambda:SimpleNamespace(names=c.names,basis=c.basis,frequency=c.frequency,
                mixed_mode=lambda:SimpleNamespace(names=m.names,basis=m.basis,frequency=m.frequency,z_characteristic=matrix))
        return line
    monkeypatch.setattr(Line,'analyze',broken)
    with pytest.raises(SampledPanelForwardPairGoalError) as caught:
        seek(factory,BOUNDS,F,targets(frequencies=F),tolerances=np.full((3,2),1e-8),initial=[1.35,.8],max_evaluations=4)
    assert caught.value.stage=='volume-refinement/target' and len(calls)==2


@pytest.mark.parametrize('which',['frequency','signal','panel'])
def test_factory_cannot_change_grid_signal_order_or_current_controls(monkeypatch,which):
    calls=synthetic(monkeypatch);seen=[]
    def unstable(x,y):
        seen.append(1);raw=factory(x,y).to_dict()
        if len(seen)>1:
            if which=='frequency':raw['frequency_hz'][1]*=1.001
            if which=='signal':raw['cross_section']['traces'].reverse()
            if which=='panel':raw['panel']['interpolation_degree']-=2
        return Line.from_dict(raw)
    with pytest.raises(SampledPanelForwardPairGoalError) as caught:
        seek(unstable,BOUNDS,F,targets(frequencies=F),tolerances=np.full((3,2),1e-8))
    assert caught.value.stage=='search/validation' and len(calls)==1


@pytest.mark.parametrize('change',[
    dict(frequencies=[]),dict(frequencies=[1e9]),dict(frequencies=[2e9,1e9]),
    dict(frequencies=[0,1e9]),dict(frequencies=[1e9,1e9]),dict(frequencies=[1e9,float('inf')]),
    dict(frequencies=list(np.geomspace(1e9,5e9,65))),dict(bounds=[[0,1],[1,2]]),
    dict(bounds=[[2,1],[1,2]]),dict(bounds=[1,2]),dict(targets=[[1,2]]),
    dict(targets=[[0,1]]*3),dict(targets=[[True,1]]*3),dict(tolerances=[[1,0]]*3),
    dict(initial=[False,1.]),dict(initial=[100.,1.]),dict(max_evaluations=True),
    dict(max_evaluations=3),dict(max_evaluations=10001)])
def test_invalid_controls_precede_factory(change):
    def forbidden(*a):pytest.fail('invalid control reached factory')
    kwargs=dict(bounds=BOUNDS,frequencies=F,targets=targets(frequencies=F),tolerances=np.full((3,2),1e-8))
    kwargs.update(change)
    with pytest.raises(ValueError):seek(forbidden,**kwargs)


def test_refinement_resource_rejection_precedes_fields(monkeypatch):
    calls=synthetic(monkeypatch)
    def oversized(x,y):
        raw=factory(x,y).to_dict();raw['panel']['panels_per_edge']=129
        return Line.from_dict(raw)
    with pytest.raises(SampledPanelForwardPairGoalError) as caught:
        seek(oversized,BOUNDS,F,targets(frequencies=F),tolerances=np.full((3,2),1e-8))
    assert caught.value.stage=='search/validation' and not calls


def test_three_refinement_attempts_are_reserved(monkeypatch):
    calls=synthetic(monkeypatch)
    with pytest.raises(SampledPanelForwardPairGoalError) as caught:
        seek(factory,BOUNDS,F,targets(frequencies=F),tolerances=np.full((3,2),1e-8),max_evaluations=4)
    assert caught.value.stage=='budget' and caught.value.attempts==len(calls)==1


def test_interrupt_propagates(monkeypatch):
    calls=synthetic(monkeypatch,fail_at=2,interrupt=True)
    with pytest.raises(KeyboardInterrupt):
        seek(factory,BOUNDS,F,targets(frequencies=F),tolerances=np.full((3,2),1e-8),initial=[1.35,.8])
    assert len(calls)==2


def test_real_finite_grid_goal_refinements_and_outer_observations(record_property):
    from sipi.constants import mu_0,epsilon_0
    f=[2e9,3.5e9,5e9];requested=[[90.,44.5]]*3
    try:
        result=seek(lambda w,g:document(w,g,f),[[.00035,.0005],[.0002,.0004]],f,requested,
            tolerances=[[.1,.1]]*3,initial=[.00038,.00028],max_evaluations=64)
    except SampledPanelForwardPairGoalError as error:
        record_property('two_ground_face_sampled_goal_failure',json.dumps(dict(message=str(error),stage=error.stage,
            attempts=error.attempts,history=[r.to_dict() for r in error.history],input=error.input_json,
            cause=None if not isinstance(error.__cause__,TwoGroundFacePanelLineError) else error.__cause__.to_dict()),sort_keys=True))
        raise
    record_property('two_ground_face_sampled_goal',json.dumps(result.to_dict(),sort_keys=True))
    assert 4<len(result.history)<=64 and [r.evaluation.stage for r in result.refinements]==STAGES
    lines=[result.result]+[r.result for r in result.refinements]; observations=[]
    for line in lines:
        c0=line.current_factors.C0;values=[]
        for i,frequency in enumerate(f):
            omega=2*np.pi*frequency;z=line.R[i]+1j*omega*line.L[i];y=line.G[i]+1j*omega*line.C[i]
            independent=np.diag(A@np.linalg.solve(np.asarray(sqrtm(z@y),dtype=complex),z)@A.T).real
            actual=np.diag(line.characteristic().mixed_mode().z_characteristic[i]).real
            np.testing.assert_allclose(actual,independent,rtol=1e-10,atol=0)
            np.testing.assert_allclose(actual,requested[i],rtol=0,atol=.1);values.append(actual.tolist())
        np.testing.assert_allclose(line.C,4*np.broadcast_to(c0,line.C.shape),rtol=1e-12,atol=0)
        np.testing.assert_allclose(line.G,2*np.pi*np.array(f)[:,None,None]*.003*line.C,rtol=1e-12,atol=0)
        np.testing.assert_allclose(line.dielectric.L@c0,mu_0*epsilon_0*np.eye(2),rtol=1e-12,atol=1e-28)
        observations.append(dict(input=json.loads(line.input_json),values=values,R=line.R.tolist(),L=line.L.tolist(),G=line.G.tolist(),C=line.C.tolist()))
    record_property('two_ground_face_sampled_goal_independent',json.dumps(observations,sort_keys=True))
    joint=result.refinements[-1].result
    def quantities(line):
        return dict(R=line.R,L_internal=line.conductor.L_internal,L_external=line.dielectric.L,
                    C=line.C,G=line.G,C0=line.current_factors.C0)
    baseline=quantities(joint)
    for width,modes in ((.016,512),(.032,1024)):
        raw=result.refinements[-1].document.to_dict();raw['cross_section']['box']['width']=width;raw['panel']['ground_modes']=modes
        line=Line.from_dict(raw).analyze();actual=quantities(line)
        differences={key:abs(actual[key]-value) for key,value in baseline.items()}
        allowances={key:.01*np.maximum(abs(actual[key]),abs(value)) for key,value in baseline.items()}
        record_property('two_ground_face_sampled_goal_outer_'+str(width),json.dumps(dict(input=raw,
            values={key:value.tolist() for key,value in actual.items()},current=line.current_record(),mesh=line.mesh_record(),
            differences={key:value.tolist() for key,value in differences.items()},allowances={key:value.tolist() for key,value in allowances.items()}),sort_keys=True))
        for key in baseline: assert np.all(differences[key]<=allowances[key]),key
