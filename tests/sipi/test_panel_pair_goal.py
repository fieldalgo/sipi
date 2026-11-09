# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Two-variable full-loss forward goals: independent references and failure accounting."""
import numpy as np
from types import SimpleNamespace
from sipi import asymmetric_coupled_microstrip, CrossSectionDocument, rlgc_characteristic
from sipi.line_model import TransmissionLineDocument

MESH=dict(edge_size=2.5e-6, far_size=.25e-3, grade=.075)
T=np.array([[1.,.3],[.2,1.1]])

def document(width, gap, *, box=24e-3, air=10e-3, loss=.02, metal=True):
    section=asymmetric_coupled_microstrip(left_width=width,right_width=.5e-3,gap=gap,
        substrate_height=.5e-3,eps_r=4.,tan_delta=loss,left_thickness=35e-6,
        right_thickness=50e-6,air_height=air,box_width=box)
    def surface(sigma,rms):
        return dict(conductivity=sigma,relative_permeability=1.,roughness=dict(kind='hammerstad',rms_m=rms))
    conductor=(dict(kind='surface-boundaries',conductors={'positive':surface(58e6,.5e-6),
        'negative':surface(35e6,1e-6)},reference=surface(58e6,0.),ground_thickness=35e-6)
        if metal else dict(kind='perfect'))
    return TransmissionLineDocument(CrossSectionDocument(section,mesh=MESH),[1e9],materials={},
        length=0.,conductor=conductor,schema='sipi.transmission-line/6')

def factory(x,y):return PanelTransmissionLineDocument(document(x*.3e-3,y*.2e-3))

def modal(x,y,lossless=False):
    scale=np.array([x,y]);omega=2*np.pi*1e9
    diagonal=dict(R=np.array([300.,2.])*scale,L=np.array([200e-9,400e-9])*scale,
        G=np.array([.005,.003])/scale,C=np.array([100e-12,80e-12])/scale)
    if lossless:diagonal['R']*=0;diagonal['G']*=0
    inverse=np.linalg.inv(T)
    matrices={k:(T@np.diag(v)@T.T if k in ('R','L') else inverse.T@np.diag(v)@inverse)
              for k,v in diagonal.items()}
    z=np.sqrt((diagonal['R']+1j*omega*diagonal['L'])/(diagonal['G']+1j*omega*diagonal['C']))
    expected=T@np.diag(z)@T.T
    return matrices,expected

def quantities(x,y,lossless=False):
    _,z=modal(x,y,lossless)
    a=np.array([[1.,-1.],[.5,.5]])
    return np.diag(a@z@a.T).real

def synthetic(monkeypatch, *, lossless=False, fail_at=None):
    calls=[]
    def analyze(self):
        calls.append(self.dumps())
        if len(calls)==fail_at:raise ArithmeticError('retained physical failure')
        traces=self.line.cross_section.section.traces
        x=traces[0].width/.3e-3;y=(traces[1].x0-traces[0].x1)/.2e-3
        matrices,_=modal(x,y,lossless)
        return SimpleNamespace(input_json=self.dumps(),frequency=np.array([1e9]),names=('positive','negative'),
            characteristic=lambda:rlgc_characteristic([1e9],**matrices,names=('positive','negative')),
            **{k:v[None] for k,v in matrices.items()})
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',analyze)
    return calls

from sipi.panel_line import PanelTransmissionLineDocument

import json
from types import SimpleNamespace
import numpy as np
import pytest
import sipi.panel_pair_goal as module
from sipi.panel_pair_goal import seek_panel_forward_pair_impedances as seek, ForwardPairGoalError
from sipi import rlgc_characteristic

BOUNDS=np.array([[.5,2.],[.5,1.5]])
ROOT=np.array([1.35,.8])
STAGES=['volume-refinement','panel-refinement','joint-refinement']

@pytest.mark.parametrize('scale',[(1.,1.),(1000.,.001)])
@pytest.mark.parametrize('lossless',[False,True])
def test_known_modal_root(monkeypatch,scale,lossless):
    calls=synthetic(monkeypatch,lossless=lossless);scale=np.array(scale)
    result=seek(lambda x,y:factory(x*scale[0],y*scale[1]),BOUNDS/scale[:,None],quantities(*ROOT,lossless),tolerances=[1e-6,1e-6])
    np.testing.assert_allclose(np.array(result.parameters)*scale,ROOT,rtol=1e-6)
    assert len(calls)==len(result.history)<=64
    assert [r.evaluation.stage for r in result.refinements]==STAGES
    for r in result.refinements:np.testing.assert_allclose(r.evaluation.impedances,result.targets,rtol=0,atol=1e-6)
    assert len({r.parameters for r in result.history[:-3]})==len(result.history)-3
    json.dumps(result.to_dict(),allow_nan=False)


def test_initial_match_four_evaluations_and_frozen_inputs(monkeypatch):
    calls=synthetic(monkeypatch);made=[]
    def once(x,y):
        made.append((x,y));assert len(made)==1;return factory(x,y)
    result=seek(once,BOUNDS,quantities(*ROOT),tolerances=[1e-8]*2,initial=ROOT,max_evaluations=4)
    assert len(calls)==len(result.history)==4
    raw=result.document.to_dict()
    for i,r in enumerate(result.refinements):
        expected=json.loads(result.input_json)
        if i!=1:
            for k in MESH:expected['line']['cross_section']['mesh'][k]/=2
        if i!=0:expected['panel']['panels_per_edge']*=2
        assert r.document.to_dict()==expected
    assert result.document.to_dict()==raw

@pytest.mark.parametrize('attempt',[1,2,3,4])
def test_extraction_failures_preserve_cause_and_attempts(monkeypatch,attempt):
    calls=synthetic(monkeypatch,fail_at=attempt)
    with pytest.raises(ForwardPairGoalError) as caught:
        seek(factory,BOUNDS,quantities(*ROOT),tolerances=[1e-8]*2,initial=ROOT,max_evaluations=4)
    e=caught.value
    assert e.attempts==attempt and len(e.history)==attempt-1 and len(calls)==attempt
    assert e.stage==(['search']+STAGES)[attempt-1]+'/extraction'
    assert e.input_json==calls[-1] and isinstance(e.__cause__,ArithmeticError)

@pytest.mark.parametrize('change',[
    dict(bounds=[[0,1],[1,2]]),dict(bounds=[[2,1],[1,2]]),dict(bounds=[1,2]),
    dict(targets=[0,1]),dict(targets=[100,np.inf]),dict(targets=[100,True]),
    dict(tolerances=[1,0]),dict(tolerances=[1,np.nan]),dict(initial=[.1,.3]),
    dict(initial=[False,.3]),dict(max_evaluations=True),dict(max_evaluations=3),dict(max_evaluations=10001)])
def test_invalid_controls_before_factory(change):
    def forbidden(*a):pytest.fail('factory reached')
    kwargs=dict(bounds=BOUNDS,targets=[100.,40.],tolerances=[.25,.125]);kwargs.update(change)
    with pytest.raises(ValueError):seek(forbidden,**kwargs)


def test_budget_reserves_three_real_attempts(monkeypatch):
    calls=synthetic(monkeypatch)
    with pytest.raises(ForwardPairGoalError) as caught:seek(factory,BOUNDS,quantities(*ROOT),tolerances=[1e-8]*2,max_evaluations=4)
    e=caught.value
    assert e.stage=='budget' and e.attempts==len(calls)==len(e.history)==1

@pytest.mark.parametrize('panels',[129,256])
def test_refinement_limit_admitted_before_any_fields(monkeypatch,panels):
    calls=synthetic(monkeypatch)
    def oversized(x,y):
        raw=factory(x,y).to_dict();raw['panel']['panels_per_edge']=panels
        return PanelTransmissionLineDocument.from_dict(raw)
    with pytest.raises(ForwardPairGoalError) as caught:seek(oversized,BOUNDS,quantities(*ROOT),tolerances=[1e-8]*2)
    assert caught.value.stage=='search/validation' and not calls
    assert caught.value.input_json

@pytest.mark.parametrize('key,value',[('ground_modes',1024),('panels_per_edge',64),('interpolation_degree',12)])
def test_search_panel_controls_frozen(monkeypatch,key,value):
    calls=synthetic(monkeypatch);made=[]
    def changing(x,y):
        raw=factory(x,y).to_dict();made.append(1)
        if len(made)>1:raw['panel'][key]=value
        return PanelTransmissionLineDocument.from_dict(raw)
    with pytest.raises(ForwardPairGoalError) as caught:seek(changing,BOUNDS,quantities(*ROOT),tolerances=[1e-8]*2)
    assert caught.value.stage=='search/validation' and caught.value.attempts==2 and len(calls)==1


def test_cache_copies(monkeypatch):
    calls=synthetic(monkeypatch);u=(ROOT-BOUNDS[:,0])/np.diff(BOUNDS,axis=1)[:,0]
    def optimizer(fun,initial,**kwargs):
        first=fun(initial);saved=first.copy();first[:]=999
        for _ in range(5):np.testing.assert_array_equal(fun(initial),saved);fun(u)
        return SimpleNamespace(success=True,x=u)
    monkeypatch.setattr(module,'least_squares',optimizer)
    result=seek(factory,BOUNDS,quantities(*ROOT),tolerances=[1e-6]*2,max_evaluations=5)
    assert len(calls)==len(result.history)==5

@pytest.mark.parametrize('stage',STAGES)
@pytest.mark.parametrize('failure',['target','convergence'])
def test_each_refinement_can_refuse(monkeypatch,stage,failure):
    original=synthetic(monkeypatch);analyze=PanelTransmissionLineDocument.analyze
    def altered(self):
        result=analyze(self)
        if len(original)==STAGES.index(stage)+2:
            matrices,_=modal(ROOT[0]*1.02,ROOT[1]*1.02)
            result.characteristic=lambda:rlgc_characteristic([1e9],**matrices,names=('positive','negative'))
        return result
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',altered)
    with pytest.raises(ForwardPairGoalError) as caught:
        seek(factory,BOUNDS,quantities(*ROOT),tolerances=([1e-8]*2 if failure=='target' else [100]*2),initial=ROOT,max_evaluations=4)
    e=caught.value
    assert e.stage==stage+'/'+failure and len(e.history)==STAGES.index(stage)+2
    assert e.input_json==e.history[-1].input_json


def test_joint_compared_with_each_single_axis(monkeypatch):
    calls=synthetic(monkeypatch);analyze=PanelTransmissionLineDocument.analyze
    def changed(self):
        result=analyze(self);factor=[1.,.996,1.,1.004][len(calls)-1]
        matrices,_=modal(ROOT[0]*factor,ROOT[1]*factor)
        result.characteristic=lambda:rlgc_characteristic([1e9],**matrices,names=('positive','negative'))
        return result
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',changed)
    with pytest.raises(ForwardPairGoalError) as caught:
        seek(factory,BOUNDS,quantities(*ROOT),tolerances=[100]*2,initial=ROOT,max_evaluations=4)
    assert caught.value.stage=='joint-refinement/convergence' and caught.value.attempts==4

@pytest.mark.parametrize('kind',['factory','wrong_type','optimizer','unsuccessful'])
def test_search_failures_retained(monkeypatch,kind):
    calls=synthetic(monkeypatch)
    def fail(*args,**kwargs):raise LookupError('original failure')
    chosen=factory
    if kind=='factory':chosen=fail
    if kind=='wrong_type':chosen=lambda *a:object()
    if kind=='optimizer':monkeypatch.setattr(module,'least_squares',fail)
    if kind=='unsuccessful':monkeypatch.setattr(module,'least_squares',lambda f,x,**k:SimpleNamespace(success=False,x=x,message='not converged'))
    with pytest.raises(ForwardPairGoalError) as caught:seek(chosen,BOUNDS,quantities(*ROOT),tolerances=[1e-8]*2)
    e=caught.value
    assert e.attempts==1
    assert e.stage==dict(factory='search/factory',wrong_type='search/factory',optimizer='optimizer',unsuccessful='convergence')[kind]
    if kind in ('factory','optimizer'):assert isinstance(e.__cause__,LookupError)
    assert len(e.history)==(1 if kind in ('optimizer','unsuccessful') else 0)

@pytest.mark.parametrize('kind',['frequency','order','length','grid','scalar'])
def test_line_admission_before_fields(monkeypatch,kind):
    calls=synthetic(monkeypatch);made=[]
    def bad(x,y):
        data=factory(x,y).to_dict();made.append(1);line=data['line']
        if kind=='frequency' and len(made)>1:line['frequency_hz']=[2e9]
        elif kind=='order' and len(made)>1:line['cross_section']['traces'].reverse()
        elif kind=='length':line['length_m']=.01
        elif kind=='grid':line['frequency_hz']=[1e9,2e9]
        elif kind=='scalar':line['cross_section']['traces']=line['cross_section']['traces'][:1];line['conductor']={'kind':'perfect'}
        return PanelTransmissionLineDocument.from_dict(data)
    with pytest.raises(ForwardPairGoalError) as caught:seek(bad,BOUNDS,quantities(*ROOT),tolerances=[1e-8]*2)
    e=caught.value
    assert e.stage=='search/validation'
    assert len(calls)==(1 if kind in ('frequency','order') else 0)
    assert e.attempts==len(calls)+1


def test_stationary_miss_never_success(monkeypatch):
    synthetic(monkeypatch);matrices,_=modal(1.,1.)
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',lambda self:SimpleNamespace(names=('positive','negative'),frequency=[1e9],characteristic=lambda:rlgc_characteristic([1e9],**matrices,names=('positive','negative'))))
    with pytest.raises(ForwardPairGoalError) as caught:seek(factory,BOUNDS,quantities(*ROOT),tolerances=[1e-8]*2)
    assert caught.value.stage=='convergence'
    assert all(r.stage=='search' for r in caught.value.history)


def test_independent_distributed_circuit_root(monkeypatch):
    import skrf
    synthetic(monkeypatch)
    diagonal=dict(R=np.array([300.,2.])*ROOT,L=np.array([200e-9,400e-9])*ROOT,G=np.array([.005,.003])/ROOT,C=np.array([100e-12,80e-12])/ROOT)
    media=[skrf.media.DistributedCircuit(skrf.Frequency.from_f([1e9],unit='hz'),**{k:v[i] for k,v in diagonal.items()}) for i in range(2)]
    expected=T@np.diag([m.z0[0] for m in media])@T.T;a=np.array([[1.,-1.],[.5,.5]])
    target=np.diag(a@expected@a.T).real
    result=seek(factory,BOUNDS,target,tolerances=[1e-6]*2)
    np.testing.assert_allclose(result.parameters,ROOT,rtol=1e-6)
    np.testing.assert_allclose(result.result.characteristic().z_characteristic[0],expected,rtol=1e-8,atol=1e-8)
    assert abs((a@expected@a.T)[0,1])>.001


def diagnostic_fixture(monkeypatch,kind):
    matrices,_=modal(1.,1.)
    def analyze(self):
        real=rlgc_characteristic([1e9],**matrices,names=('positive','negative'))
        def characteristic():
            if kind=='exception':raise ArithmeticError('original characteristic failure')
            if kind=='basis':return real.mixed_mode()
            mixed=real.mixed_mode();matrix=mixed.z_characteristic.copy()
            if kind=='nan':matrix[0,0,1]=np.nan
            if kind=='negative':matrix[0,1,1]=-1.
            if kind=='shape':matrix=matrix[:,:,:1]
            transformed=SimpleNamespace(basis='mixed-mode',names=('bad','common') if kind=='mixed_names' else mixed.names,
                frequency=[2e9] if kind=='mixed_frequency' else mixed.frequency,z_characteristic=matrix)
            return SimpleNamespace(basis='single-ended',names=('bad','negative') if kind=='names' else real.names,
                frequency=[2e9] if kind=='frequency' else real.frequency,mixed_mode=lambda:transformed)
        return SimpleNamespace(names=('bad','negative') if kind=='line_names' else ('positive','negative'),
            frequency=[2e9] if kind=='line_frequency' else [1e9],characteristic=characteristic)
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',analyze)


@pytest.mark.parametrize('kind',['exception','basis','names','frequency','mixed_names','mixed_frequency',
                                'nan','negative','shape','line_names','line_frequency'])
def test_changed_or_invalid_diagnostics_never_become_success(monkeypatch,kind):
    diagnostic_fixture(monkeypatch,kind)
    with pytest.raises(ForwardPairGoalError) as caught:
        seek(factory,BOUNDS,[100.,40.],tolerances=[1.,1.])
    err=caught.value
    assert err.attempts==1 and not err.history and err.input_json
    assert err.stage==('search/extraction' if kind.startswith('line_') else 'search/diagnostic')
    assert err.cause_type==('ArithmeticError' if kind=='exception' else 'ValueError')
