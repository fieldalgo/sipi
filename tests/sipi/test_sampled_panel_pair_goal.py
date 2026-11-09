# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Finite-frequency goals: independent references, strict controls and retained failures."""
import json
from dataclasses import FrozenInstanceError
from types import SimpleNamespace
import numpy as np
import pytest
import sipi.sampled_panel_pair_goal as implementation
from sipi.sampled_panel_pair_goal import seek_sampled_panel_forward_pair_impedances as seek, SampledPanelForwardPairGoalError
from sipi import rlgc_characteristic
from sipi.line_model import TransmissionLineDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.panel_pair_goal import seek_panel_forward_pair_impedances
from test_pair_line_goal import document as single_document,T

F=np.array([.2e9,1e9,3e9]);BOUNDS=np.array([[.5,2.],[.5,1.5]]);A=np.array([[1.,-1.],[.5,.5]])


def document(width,gap,frequencies=F,**kwargs):
    raw=single_document(width,gap,**kwargs).to_dict();raw['frequency_hz']=list(frequencies)
    return PanelTransmissionLineDocument(TransmissionLineDocument.from_dict(raw))


def factory(x,y,frequencies=F):return document(x*.3e-3,y*.2e-3,frequencies)


def modal(x,y,frequencies=F,lossless=False):
    scales=np.array([x,y]);inverse=np.linalg.inv(T)
    d=dict(R=np.array([300.,2.])*scales,L=np.array([200e-9,400e-9])*scales,
           G=np.array([.005,.003])/scales,C=np.array([100e-12,80e-12])/scales)
    if lossless:d['R']*=0;d['G']*=0
    matrices={k:(T@np.diag(v)@T.T if k in ('R','L') else inverse.T@np.diag(v)@inverse) for k,v in d.items()}
    z=np.sqrt((d['R'][None]+2j*np.pi*np.array(frequencies)[:,None]*d['L'])/
              (d['G'][None]+2j*np.pi*np.array(frequencies)[:,None]*d['C']))
    return matrices,np.array([T@np.diag(row)@T.T for row in z])


def targets(x=1.35,y=.8,frequencies=F,lossless=False):
    _,zc=modal(x,y,frequencies,lossless)
    return np.diagonal(A@zc@A.T,axis1=1,axis2=2).real


def synthetic(monkeypatch,*,lossless=False,fail_at=None):
    calls=[]
    def analyze(self):
        calls.append(self.dumps())
        if len(calls)==fail_at:raise ArithmeticError('original failed frequency batch')
        traces=self.line.cross_section.section.traces
        x=traces[0].width/.3e-3;y=(traces[1].x0-traces[0].x1)/.2e-3
        frequency=np.array(self.to_dict()['line']['frequency_hz'])
        matrices,_=modal(x,y,frequency,lossless)
        return SimpleNamespace(names=('positive','negative'),frequency=frequency,input_json=self.dumps(),
            characteristic=lambda:rlgc_characteristic(frequency,**matrices,names=('positive','negative')),
            **{k:np.broadcast_to(v,(len(frequency),2,2)).copy() for k,v in matrices.items()})
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',analyze);return calls


@pytest.mark.parametrize('scale',[(1.,1.),(1000.,.001)])
@pytest.mark.parametrize('lossless',[False,True])
def test_frequency_dependent_modal_search_and_units(monkeypatch,scale,lossless):
    calls=synthetic(monkeypatch,lossless=lossless);scale=np.array(scale)
    result=seek(lambda x,y:factory(x*scale[0],y*scale[1]),BOUNDS/scale[:,None],F,
        targets(lossless=lossless),tolerances=np.full((3,2),1e-6))
    np.testing.assert_allclose(np.array(result.parameters)*scale,[1.35,.8],rtol=1e-6)
    assert np.max(abs(np.asarray(result.residuals)))<=1e-6
    assert result.frequencies==tuple(F) and len(result.history)==len(calls)<=64
    assert len(result.refinements)==3 and len(set(row.parameters for row in result.history[:-3]))==len(result.history)-3
    for refined in result.refinements:
        assert np.max(abs(np.asarray(refined.evaluation.impedances)-result.targets))<=1e-6
    assert result.to_dict()['frequencies_hz']==list(F)
    assert result.to_dict()['targets_ohm']==targets(lossless=lossless).tolist()
    json.dumps(result.to_dict(),allow_nan=False)
    with pytest.raises(FrozenInstanceError):result.parameters=(1.,1.)


def test_independent_skrf_modal_frequency_grid(monkeypatch):
    import skrf
    synthetic(monkeypatch)
    def reference(x,y):
        scales=np.array([x,y]);d=dict(R=np.array([300.,2.])*scales,L=np.array([200e-9,400e-9])*scales,
            G=np.array([.005,.003])/scales,C=np.array([100e-12,80e-12])/scales)
        media=[skrf.media.DistributedCircuit(skrf.Frequency.from_f(F,unit='hz'),**{k:v[i] for k,v in d.items()}) for i in range(2)]
        return np.array([T@np.diag([m.z0[j] for m in media])@T.T for j in range(len(F))])
    expected=reference(1.35,.8);requested=np.diagonal(A@expected@A.T,axis1=1,axis2=2).real
    result=seek(factory,BOUNDS,F,requested,tolerances=np.full((3,2),1e-6))
    actual=result.result.characteristic().z_characteristic;ref=reference(*result.parameters)
    assert abs(actual-ref).max()/abs(ref).max()<=1e-10


def test_matching_start_four_frozen_batches_match_single_frequency_api(monkeypatch):
    calls=synthetic(monkeypatch);made=[]
    def once(x,y):made.append((x,y));assert len(made)==1;return factory(x,y)
    result=seek(once,BOUNDS,F,targets(),tolerances=np.full((3,2),1e-8),initial=[1.35,.8],max_evaluations=4)
    assert len(calls)==len(result.history)==4 and len(made)==1
    base=result.document.to_dict()
    for item,stage in zip(result.refinements,['volume-refinement','panel-refinement','joint-refinement']):
        raw=item.document.to_dict();assert item.evaluation.stage==stage
        for key in ['edge_size','far_size','grade']:
            assert raw['line']['cross_section']['mesh'][key]==base['line']['cross_section']['mesh'][key]/(1 if stage=='panel-refinement' else 2)
        assert raw['panel']['panels_per_edge']==base['panel']['panels_per_edge']*(1 if stage=='volume-refinement' else 2)
        assert raw['panel']['ground_modes']==base['panel']['ground_modes']
        assert raw['panel']['interpolation_degree']==base['panel']['interpolation_degree']
    for i,f in enumerate(F):
        single=seek_panel_forward_pair_impedances(lambda x,y:factory(x,y,[f]),BOUNDS,
            targets(frequencies=[f])[0],tolerances=[1e-8]*2,initial=[1.35,.8],max_evaluations=4)
        np.testing.assert_allclose(single.impedances,result.impedances[i],rtol=1e-12,atol=0)


@pytest.mark.parametrize('attempt',[1,2,3,4])
def test_failed_batch_preserves_frequency_vector_history_cause_and_attempts(monkeypatch,attempt):
    calls=synthetic(monkeypatch,fail_at=attempt)
    with pytest.raises(SampledPanelForwardPairGoalError) as caught:
        seek(factory,BOUNDS,F,targets(),tolerances=np.full((3,2),1e-8),initial=[1.35,.8],max_evaluations=4)
    error=caught.value
    assert error.attempts==len(calls)==attempt and len(error.history)==attempt-1
    assert error.frequencies==tuple(F) and error.cause_type=='ArithmeticError'
    assert error.stage==['search','volume-refinement','panel-refinement','joint-refinement'][attempt-1]+'/extraction'
    assert error.input_json==calls[-1] and isinstance(error.__cause__,ArithmeticError)


@pytest.mark.parametrize('frequencies',[[],[1e9],[1e9,1e9],[2e9,1e9],[0.,1e9],[-1.,1e9],[[1e9,2e9]],[1e9,float('inf')],list(range(1,66))])
def test_invalid_frequency_controls_before_factory(frequencies):
    def forbidden(*a,**k):pytest.fail('invalid frequency reached factory')
    with pytest.raises(ValueError):seek(forbidden,BOUNDS,frequencies,[[100.,40.]]*2,tolerances=[[1.,1.]]*2)


@pytest.mark.parametrize('key,value',[('targets',[110.,40.]),('targets',[[110.,40.]]),('targets',[[110.],[40.],[110.]]),
    ('targets',[[110.,40.],[110.,0.],[110.,40.]]),('tolerances',1.),('tolerances',[[1.,1.],[1.,float('nan')],[1.,1.]]),
    ('bounds',[[0.,2.],[.5,1.5]]),('initial',[.1,1.]),('max_evaluations',3),('max_evaluations',True),('max_evaluations',10001)])
def test_invalid_shapes_and_controls_before_factory(key,value):
    args=dict(bounds=BOUNDS,frequencies=F,targets=targets(),tolerances=np.ones((3,2)));args[key]=value
    def forbidden(*a,**k):pytest.fail('invalid controls reached factory')
    with pytest.raises(ValueError):seek(forbidden,**args)


@pytest.mark.parametrize('kind',['frequency','length','names','panel'])
def test_changed_factory_identity_rejects_without_reinterpreting_targets(monkeypatch,kind):
    calls=synthetic(monkeypatch);made=[]
    def drift(x,y):
        made.append(1);doc=factory(x,y);raw=doc.to_dict()
        if len(made)==2:
            if kind=='frequency':raw['line']['frequency_hz']=[.3e9,1e9,3e9]
            elif kind=='length':raw['line']['length_m']=.01
            elif kind=='panel':raw['panel']['ground_modes']=1024
            else:
                for trace in raw['line']['cross_section']['traces']:
                    if trace['name']=='positive':trace['name']='other'
                raw['line']['conductor']={'kind':'perfect'}
        return PanelTransmissionLineDocument.from_dict(raw)
    with pytest.raises(SampledPanelForwardPairGoalError) as caught:
        seek(drift,BOUNDS,F,targets(),tolerances=np.full((3,2),1e-8))
    assert caught.value.stage=='search/validation' and caught.value.attempts==2 and len(calls)==1


def test_future_refinements_admitted_before_fields(monkeypatch):
    calls=synthetic(monkeypatch)
    def excessive(x,y):
        raw=factory(x,y).to_dict();raw['panel']['panels_per_edge']=256
        return PanelTransmissionLineDocument.from_dict(raw)
    with pytest.raises(SampledPanelForwardPairGoalError) as caught:
        seek(excessive,BOUNDS,F,targets(),tolerances=np.full((3,2),1e-8),initial=[1.35,.8],max_evaluations=4)
    assert caught.value.stage=='search/validation' and caught.value.attempts==1 and len(calls)==0


def test_budget_reserves_three_batches_and_counts_uncached_probes(monkeypatch):
    calls=synthetic(monkeypatch)
    with pytest.raises(SampledPanelForwardPairGoalError) as caught:
        seek(factory,BOUNDS,F,targets(),tolerances=np.full((3,2),1e-8),max_evaluations=5)
    assert caught.value.stage=='budget' and caught.value.attempts==len(calls)==2
    assert all(row.stage=='search' for row in caught.value.history)


def test_frequency_first_flat_residual_and_jacobian_cache_copies(monkeypatch):
    calls=synthetic(monkeypatch);requested=targets();tolerance=np.array([[1.,2.],[3.,4.],[5.,6.]])*1e-6
    def optimizer(fun,x0,**kwargs):
        expected=((targets(*((BOUNDS[:,0]+BOUNDS[:,1])/2))-requested)/tolerance).ravel()
        first=fun(x0);np.testing.assert_allclose(first,expected,rtol=1e-12,atol=1e-8)
        first[:]=1e99;np.testing.assert_allclose(fun(x0),expected,rtol=1e-12,atol=1e-8)
        jac=kwargs['jac'](x0);assert jac.shape==(6,2)
        return SimpleNamespace(success=True,x=(np.array([1.35,.8])-BOUNDS[:,0])/(BOUNDS[:,1]-BOUNDS[:,0]),message='fixed solution')
    monkeypatch.setattr(implementation,'least_squares',optimizer)
    result=seek(factory,BOUNDS,F,requested,tolerances=tolerance)
    assert len(calls)==len(result.history)==9


@pytest.mark.parametrize('attempt,mode',[(2,'target'),(3,'target'),(4,'target'),(2,'relative'),(3,'relative'),(4,'relative')])
def test_every_refinement_checks_middle_frequency_targets_and_relative_change(monkeypatch,attempt,mode):
    calls=synthetic(monkeypatch);original=PanelTransmissionLineDocument.analyze
    def changed(self):
        line=original(self)
        if len(calls)==attempt:
            characteristic=line.characteristic();mixed=characteristic.mixed_mode();matrix=mixed.z_characteristic.copy()
            matrix[1,0,0]*=1.006 if mode=='relative' else 1.1
            line.characteristic=lambda:SimpleNamespace(basis='single-ended',names=line.names,frequency=line.frequency,
                mixed_mode=lambda:SimpleNamespace(basis='mixed-mode',names=('differential','common'),frequency=line.frequency,z_characteristic=matrix))
        return line
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',changed)
    with pytest.raises(SampledPanelForwardPairGoalError) as caught:
        seek(factory,BOUNDS,F,targets(),tolerances=np.full((3,2),1000. if mode=='relative' else 1e-8),initial=[1.35,.8],max_evaluations=4)
    error=caught.value
    assert error.stage==['volume-refinement','panel-refinement','joint-refinement'][attempt-2]+('/convergence' if mode=='relative' else '/target')
    assert error.attempts==len(error.history)==len(calls)==attempt
    assert error.frequencies==tuple(F) and error.input_json==calls[-1]


def test_joint_refinement_checks_both_single_axis_results(monkeypatch):
    calls=synthetic(monkeypatch);original=PanelTransmissionLineDocument.analyze
    def changed(self):
        line=original(self);factor=[1.,.996,1.004,1.004][len(calls)-1]
        characteristic=line.characteristic();mixed=characteristic.mixed_mode();matrix=mixed.z_characteristic.copy()*factor
        line.characteristic=lambda:SimpleNamespace(basis='single-ended',names=line.names,frequency=line.frequency,
            mixed_mode=lambda:SimpleNamespace(basis='mixed-mode',names=('differential','common'),frequency=line.frequency,z_characteristic=matrix))
        return line
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',changed)
    with pytest.raises(SampledPanelForwardPairGoalError) as caught:
        seek(factory,BOUNDS,F,targets(),tolerances=np.full((3,2),1000.),initial=[1.35,.8],max_evaluations=4)
    assert caught.value.stage=='joint-refinement/convergence' and caught.value.attempts==4


def test_optimizer_success_does_not_certify_stationary_misses(monkeypatch):
    calls=synthetic(monkeypatch)
    monkeypatch.setattr(implementation,'least_squares',lambda fun,x0,**kwargs:SimpleNamespace(success=True,x=x0,message='stationary'))
    with pytest.raises(SampledPanelForwardPairGoalError) as caught:
        seek(factory,BOUNDS,F,targets(),tolerances=np.full((3,2),1e-8))
    assert caught.value.stage=='convergence' and caught.value.attempts==len(calls)==1


@pytest.mark.parametrize('kind',['line_frequency','line_names','basis','frequency','names','mixed_basis','mixed_frequency','mixed_names','shape','nonfinite','negative'])
def test_invalid_whole_batch_diagnostics_are_never_partial_success(monkeypatch,kind):
    calls=synthetic(monkeypatch);original=PanelTransmissionLineDocument.analyze
    def broken(self):
        line=original(self)
        if kind=='line_frequency':line.frequency=line.frequency[::-1];return line
        if kind=='line_names':line.names=('wrong','names');return line
        characteristic=line.characteristic();mixed=characteristic.mixed_mode();matrix=mixed.z_characteristic.copy()
        basis='single-ended';names=line.names;frequency=line.frequency;mbasis='mixed-mode';mnames=('differential','common');mf=frequency
        if kind=='basis':basis='wrong'
        elif kind=='names':names=('negative','positive')
        elif kind=='frequency':frequency=frequency[::-1]
        elif kind=='mixed_basis':mbasis='wrong'
        elif kind=='mixed_names':mnames=('common','differential')
        elif kind=='mixed_frequency':mf=mf[::-1]
        elif kind=='shape':matrix=matrix[:1]
        elif kind=='nonfinite':matrix[1,1,1]=np.nan
        elif kind=='negative':matrix[1,1,1]=-1.
        line.characteristic=lambda:SimpleNamespace(basis=basis,names=names,frequency=frequency,
            mixed_mode=lambda:SimpleNamespace(basis=mbasis,names=mnames,frequency=mf,z_characteristic=matrix))
        return line
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',broken)
    with pytest.raises(SampledPanelForwardPairGoalError) as caught:
        seek(factory,BOUNDS,F,targets(),tolerances=np.full((3,2),1e-8),initial=[1.35,.8],max_evaluations=4)
    error=caught.value
    assert error.stage==('search/extraction' if kind.startswith('line_') else 'search/diagnostic')
    assert error.attempts==len(calls)==1 and not error.history and error.frequencies==tuple(F)
    assert error.input_json==calls[0] and error.cause_type=='ValueError'


@pytest.mark.parametrize('kind',['exception','unsuccessful'])
def test_optimizer_failures_preserve_completed_batches(monkeypatch,kind):
    calls=synthetic(monkeypatch)
    def optimizer(fun,x0,**kwargs):
        if kind=='exception':raise ArithmeticError('optimizer cause')
        return SimpleNamespace(success=False,x=x0,message='iteration limit')
    monkeypatch.setattr(implementation,'least_squares',optimizer)
    with pytest.raises(SampledPanelForwardPairGoalError) as caught:
        seek(factory,BOUNDS,F,targets(),tolerances=np.full((3,2),1e-8))
    error=caught.value
    assert error.attempts==len(error.history)==len(calls)==1
    assert error.stage==('optimizer' if kind=='exception' else 'convergence')
    if kind=='exception':assert isinstance(error.__cause__,ArithmeticError) and error.cause_type=='ArithmeticError'
    else:assert error.input_json==calls[0] and 'iteration limit' in str(error)


@pytest.mark.parametrize('kind',['exception','wrong-type'])
def test_factory_failures_count_attempts_without_fields(monkeypatch,kind):
    calls=synthetic(monkeypatch)
    def broken(*args):
        if kind=='exception':raise ArithmeticError('factory cause')
        return object()
    with pytest.raises(SampledPanelForwardPairGoalError) as caught:
        seek(broken,BOUNDS,F,targets(),tolerances=np.ones((3,2)))
    error=caught.value
    assert error.attempts==1 and not error.history and not calls and error.input_json is None
    assert error.stage=='search/factory' and error.cause_type==('ArithmeticError' if kind=='exception' else 'TypeError')


@pytest.mark.parametrize('initial',[[.5,.5],[2.,1.5]])
def test_matching_boundary_parameters_are_exact_and_frozen(monkeypatch,initial):
    calls=synthetic(monkeypatch);made=[]
    def once(*args):made.append(args);return factory(*args)
    result=seek(once,BOUNDS,F,targets(*initial),tolerances=np.full((3,2),1e-8),initial=initial,max_evaluations=4)
    assert made==[tuple(initial)] and result.parameters==tuple(initial) and len(calls)==4


def test_overflowing_normalized_residual_is_failed_whole_batch(monkeypatch):
    calls=synthetic(monkeypatch)
    with pytest.raises(SampledPanelForwardPairGoalError) as caught:
        seek(factory,BOUNDS,F,targets(),tolerances=np.full((3,2),np.nextafter(0.,1.)))
    error=caught.value
    assert error.stage=='search/diagnostic' and error.cause_type=='FloatingPointError'
    assert error.attempts==len(calls)==1 and not error.history
