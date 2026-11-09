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

def factory(x,y):return document(x*.3e-3,y*.2e-3)

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
        traces=self.cross_section.section.traces
        x=traces[0].width/.3e-3;y=(traces[1].x0-traces[0].x1)/.2e-3
        matrices,_=modal(x,y,lossless)
        return SimpleNamespace(input_json=self.dumps(),frequency=np.array([1e9]),names=('positive','negative'),
            characteristic=lambda:rlgc_characteristic([1e9],**matrices,names=('positive','negative')),
            **{k:v[None] for k,v in matrices.items()})
    monkeypatch.setattr(TransmissionLineDocument,'analyze',analyze)
    return calls


import json
from dataclasses import FrozenInstanceError
import numpy as np
import pytest
from sipi.pair_line_goal import seek_forward_pair_impedances,ForwardPairGoalError
import sipi.pair_line_goal as goal_module

BOUNDS=np.array([[.5,2.],[.5,1.5]])

@pytest.mark.parametrize('scale',[(1.,1.),(1000.,.001)])
@pytest.mark.parametrize('lossless',[False,True])
def test_known_modal_root_and_parameter_units(monkeypatch,scale,lossless):
    calls=synthetic(monkeypatch,lossless=lossless)
    expected=np.array([1.35,.8]);scale=np.array(scale)
    result=seek_forward_pair_impedances(lambda x,y:factory(x*scale[0],y*scale[1]),
        BOUNDS/scale[:,None],quantities(*expected,lossless),tolerances=[1e-6,1e-6])
    np.testing.assert_allclose(np.array(result.parameters)*scale,expected,rtol=1e-6)
    assert max(abs(np.array(result.residuals)))<=1e-6
    assert max(abs(np.array(result.refined_residuals)))<=1e-6
    assert len(calls)==len(result.history)<=64
    assert len(set(row.parameters for row in result.history[:-1]))==len(result.history)-1
    assert result.history[-1].stage=='refinement'
    assert result.refined_document.to_dict()['cross_section']['mesh']['edge_size']==MESH['edge_size']/2
    json.dumps(result.to_dict(),allow_nan=False)
    with pytest.raises(FrozenInstanceError):result.parameters=(1.,1.)

def test_initial_match_still_refines_without_factory_reentry(monkeypatch):
    calls=synthetic(monkeypatch);factories=[]
    def once(x,y):
        factories.append((x,y));assert len(factories)==1;return factory(x,y)
    result=seek_forward_pair_impedances(once,BOUNDS,quantities(1.35,.8),tolerances=[1e-8,1e-8],
        initial=[1.35,.8],max_evaluations=2)
    assert len(calls)==len(result.history)==2 and len(factories)==1
    raw=result.document.to_dict();fine=result.refined_document.to_dict()
    for key in ['traces','layers','box']:assert raw['cross_section'][key]==fine['cross_section'][key]
    assert raw['conductor']==fine['conductor'] and raw['materials']==fine['materials']

def test_budget_counts_uncached_probe_attempts_and_keeps_history(monkeypatch):
    calls=synthetic(monkeypatch)
    with pytest.raises(ForwardPairGoalError) as caught:
        seek_forward_pair_impedances(factory,BOUNDS,quantities(1.35,.8),tolerances=[1e-8,1e-8],max_evaluations=2)
    err=caught.value
    assert err.stage=='budget' and err.attempts==len(calls)==len(err.history)==1

def test_failed_extraction_preserves_cause_and_inputs(monkeypatch):
    calls=synthetic(monkeypatch,fail_at=2)
    with pytest.raises(ForwardPairGoalError) as caught:
        seek_forward_pair_impedances(factory,BOUNDS,quantities(1.35,.8),tolerances=[1e-8,1e-8])
    err=caught.value
    assert err.stage=='search/extraction' and err.attempts==len(calls)==2 and len(err.history)==1
    assert err.cause_type=='ArithmeticError' and isinstance(err.__cause__,ArithmeticError)
    assert err.input_json==calls[-1] and err.failed_parameters is not None

@pytest.mark.parametrize('change',[
    dict(bounds=[[0,1],[1,2]]),dict(bounds=[[2,1],[1,2]]),dict(bounds=[1,2]),
    dict(bounds=[[True,2],[1,2]]),dict(targets=[0,1]),dict(targets=[100,np.inf]),
    dict(targets=[100,True]),dict(targets=[100]),dict(tolerances=[1,0]),
    dict(tolerances=[1,np.nan]),dict(initial=[.1,.3]),dict(initial=[.5]),
    dict(initial=[False,.3]),dict(max_evaluations=True),dict(max_evaluations=1)])
def test_control_errors_before_factory(change):
    def forbidden(*args):pytest.fail('invalid controls reached factory')
    kwargs=dict(bounds=BOUNDS,targets=[100.,40.],tolerances=[.25,.125]);kwargs.update(change)
    with pytest.raises(ValueError):seek_forward_pair_impedances(forbidden,**kwargs)


def reference_record(case, tool, description, errors, clock):
    from importlib import metadata
    from crosscheck import emit, make_record, observable
    record=make_record(case=case,physics='two-parameter lossy forward-current launches',
        api='sipi.pair_line_goal.seek_forward_pair_impedances',
        discretization='full complex RLGC characteristic matrix and bounded local search',
        tool=tool,tool_discretization=description,
        matched=['same frequency, ordered conductors and full RLGC',
                 'power-dual differential/common coordinates with separate Ic=0 and Id=0 launches'],
        not_matched=['independent geometry extraction, measured manufacturing and finite terminal response',
                     'no uniqueness, global optimization or infinite-domain guarantee'],
        observables=[observable(k,'ohm','maximum relative matrix/quantity difference',v,1e-10)
                     for k,v in errors.items()],
        analytical_acceptance='known two-scale modal roots and frozen mesh/finite-domain checks',stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'))
    emit(record);assert max(errors.values())<1e-10


def test_known_root_against_independent_modal_circuits(monkeypatch):
    from crosscheck import require_tool,Stopwatch
    skrf=require_tool('scikit-rf');clock=Stopwatch();synthetic(monkeypatch)
    a=np.array([[1.,-1.],[.5,.5]])
    def reference(x,y):
        scale=np.array([x,y])
        diagonal=dict(R=np.array([300.,2.])*scale,L=np.array([200e-9,400e-9])*scale,
                      G=np.array([.005,.003])/scale,C=np.array([100e-12,80e-12])/scale)
        media=[skrf.media.DistributedCircuit(skrf.Frequency.from_f([1e9],unit='hz'),
            **{k:v[i] for k,v in diagonal.items()}) for i in range(2)]
        return T@np.diag([m.z0[0] for m in media])@T.T
    with clock('reference'):target=np.diag(a@reference(1.35,.8)@a.T).real
    with clock('openphysics'):
        result=seek_forward_pair_impedances(factory,BOUNDS,target,tolerances=[1e-6,1e-6])
        actual=result.result.characteristic().z_characteristic[0]
    with clock('reference'):expected=reference(*result.parameters);mixed=a@expected@a.T
    np.testing.assert_allclose(result.parameters,[1.35,.8],rtol=1e-6)
    assert abs(mixed[0,1])>1e-3 and max(abs(np.diag(mixed).imag))>.01
    assert max(abs(abs(np.diag(mixed))-np.diag(mixed).real))>1e-4
    reference_record('two-variable-forward-pair-modal-root','scikit-rf',
        'two DistributedCircuit media under a known nonorthogonal power-dual transform',
        dict(Zc=float(abs(actual-expected).max()/abs(expected).max()),
             impedances=float(np.max(abs(np.array(result.impedances)/np.diag(mixed).real-1)))),clock)


def test_symmetric_limit_preserves_both_current_launch_definitions(monkeypatch):
    import sys
    monkeypatch.setattr(sys.modules[__name__],'T',np.array([[1.,1.],[1.,-1.]])/np.sqrt(2))
    synthetic(monkeypatch)
    result=seek_forward_pair_impedances(factory,BOUNDS,quantities(1.35,.8),tolerances=[1e-6,1e-6])
    x,y=result.parameters;omega=2*np.pi*1e9
    even=x*np.sqrt((300+1j*omega*200e-9)/(.005+1j*omega*100e-12))
    odd=y*np.sqrt((2+1j*omega*400e-9)/(.003+1j*omega*80e-12))
    np.testing.assert_allclose(result.impedances,[2*odd.real,.5*even.real],rtol=1e-10)
    assert abs(result.result.characteristic().mixed_mode().z_characteristic[0,0,1])<1e-10


def test_cache_hits_return_copies_and_preserve_real_attempt_budget(monkeypatch):
    calls=synthetic(monkeypatch)
    root=np.array([1.35,.8]);u=(root-BOUNDS[:,0])/np.diff(BOUNDS,axis=1)[:,0]
    def optimizer(fun,initial,**kwargs):
        first=fun(initial);reference=first.copy();first[:]=999.
        for _ in range(5):np.testing.assert_array_equal(fun(initial),reference)
        for _ in range(5):fun(u)
        return SimpleNamespace(success=True,x=u)
    monkeypatch.setattr(goal_module,'least_squares',optimizer)
    result=seek_forward_pair_impedances(factory,BOUNDS,quantities(*root),tolerances=[1e-6,1e-6],max_evaluations=3)
    assert len(result.history)==len(calls)==3
    assert [row.stage for row in result.history]==['search','search','refinement']


@pytest.mark.parametrize('kind',['raise','unsuccessful'])
def test_optimizer_failure_retains_completed_history(monkeypatch,kind):
    calls=synthetic(monkeypatch)
    def optimizer(fun,initial,**kwargs):
        if kind=='raise':raise LookupError('retained optimizer failure')
        return SimpleNamespace(success=False,x=initial,message='stated nonconvergence')
    monkeypatch.setattr(goal_module,'least_squares',optimizer)
    with pytest.raises(ForwardPairGoalError) as caught:
        seek_forward_pair_impedances(factory,BOUNDS,quantities(1.35,.8),tolerances=[1e-8,1e-8])
    err=caught.value;assert err.attempts==len(calls)==len(err.history)==1
    assert err.stage==('optimizer' if kind=='raise' else 'convergence')
    if kind=='raise':assert err.cause_type=='LookupError' and isinstance(err.__cause__,LookupError)
    else:assert err.input_json==calls[0]


def test_factory_failure_and_wrong_factory_type_are_retained(monkeypatch):
    calls=synthetic(monkeypatch);made=[]
    def failing(x,y):
        made.append((x,y))
        if len(made)==2:raise LookupError('original factory failure')
        return factory(x,y)
    with pytest.raises(ForwardPairGoalError) as caught:
        seek_forward_pair_impedances(failing,BOUNDS,quantities(1.35,.8),tolerances=[1e-8,1e-8])
    err=caught.value
    assert err.attempts==2 and len(err.history)==len(calls)==1 and err.stage=='search/factory'
    assert err.cause_type=='LookupError' and isinstance(err.__cause__,LookupError)
    with pytest.raises(ForwardPairGoalError) as wrong:
        seek_forward_pair_impedances(lambda *args:object(),BOUNDS,[100.,40.],tolerances=[1.,1.])
    assert wrong.value.attempts==1 and wrong.value.cause_type=='TypeError'


@pytest.mark.parametrize('kind',['frequency','order'])
def test_identity_change_rejects_before_second_extraction(monkeypatch,kind):
    calls=synthetic(monkeypatch);made=[]
    def changing(x,y):
        raw=factory(x,y).to_dict();made.append((x,y))
        if len(made)>1:
            if kind=='frequency':raw['frequency_hz']=[2e9]
            else:raw['cross_section']['traces'].reverse()
        return TransmissionLineDocument.from_dict(raw)
    with pytest.raises(ForwardPairGoalError) as caught:
        seek_forward_pair_impedances(changing,BOUNDS,quantities(1.35,.8),tolerances=[1e-8,1e-8])
    err=caught.value
    assert err.stage=='search/validation' and err.attempts==2 and len(calls)==len(err.history)==1
    assert err.input_json and err.cause_type=='ValueError'


@pytest.mark.parametrize('kind',['scalar','zero_frequency','frequency_grid','length'])
def test_line_contract_rejects_before_fields(monkeypatch,kind):
    raw=factory(1.,1.).to_dict()
    if kind=='scalar':
        raw['cross_section']['traces']=raw['cross_section']['traces'][:1];raw['conductor']=dict(kind='perfect')
    elif kind=='zero_frequency':raw['frequency_hz']=[0.];raw['conductor']=dict(kind='perfect')
    elif kind=='frequency_grid':raw['frequency_hz']=[1e9,2e9]
    else:raw['length_m']=.1
    def forbidden(*args,**kwargs):pytest.fail('invalid goal line reached fields')
    monkeypatch.setattr(TransmissionLineDocument,'analyze',forbidden)
    with pytest.raises(ForwardPairGoalError) as caught:
        seek_forward_pair_impedances(lambda *args:TransmissionLineDocument.from_dict(raw),BOUNDS,[100.,40.],tolerances=[1.,1.])
    assert caught.value.stage=='search/validation' and caught.value.attempts==1


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
    monkeypatch.setattr(TransmissionLineDocument,'analyze',analyze)


@pytest.mark.parametrize('kind',['exception','basis','names','frequency','mixed_names','mixed_frequency',
                                'nan','negative','shape','line_names','line_frequency'])
def test_changed_or_invalid_diagnostics_never_become_success(monkeypatch,kind):
    diagnostic_fixture(monkeypatch,kind)
    with pytest.raises(ForwardPairGoalError) as caught:
        seek_forward_pair_impedances(factory,BOUNDS,[100.,40.],tolerances=[1.,1.])
    err=caught.value
    assert err.attempts==1 and not err.history and err.input_json
    assert err.stage==('search/extraction' if kind.startswith('line_') else 'search/diagnostic')
    assert err.cause_type==('ArithmeticError' if kind=='exception' else 'ValueError')


def test_stationary_missed_target_is_failure(monkeypatch):
    matrices,_=modal(1.,1.)
    monkeypatch.setattr(TransmissionLineDocument,'analyze',lambda self:SimpleNamespace(
        names=('positive','negative'),frequency=[1e9],
        characteristic=lambda:rlgc_characteristic([1e9],**matrices,names=('positive','negative'))))
    with pytest.raises(ForwardPairGoalError) as caught:
        seek_forward_pair_impedances(factory,BOUNDS,quantities(1.35,.8),tolerances=[1e-6,1e-6])
    assert caught.value.stage=='convergence' and all(r.stage=='search' for r in caught.value.history)


def test_rank_deficient_feasible_goal_does_not_claim_unique_parameters(monkeypatch):
    def analyze(self):
        x=self.cross_section.section.traces[0].width/.3e-3;matrices,_=modal(x,x)
        return SimpleNamespace(names=('positive','negative'),frequency=[1e9],
            characteristic=lambda:rlgc_characteristic([1e9],**matrices,names=('positive','negative')))
    monkeypatch.setattr(TransmissionLineDocument,'analyze',analyze)
    result=seek_forward_pair_impedances(factory,BOUNDS,quantities(1.2,1.2),tolerances=[1e-6,1e-6])
    assert result.parameters[0]==pytest.approx(1.2,rel=1e-6)
    assert max(abs(np.array(result.refined_residuals)))<=1e-6


def test_refinement_miss_keeps_both_original_rows(monkeypatch):
    def analyze(self):
        fine=self.to_dict()['cross_section']['mesh']['edge_size']<MESH['edge_size']
        matrices,_=modal(2. if fine else 1.25,1.)
        return SimpleNamespace(names=('positive','negative'),frequency=[1e9],
            characteristic=lambda:rlgc_characteristic([1e9],**matrices,names=('positive','negative')))
    monkeypatch.setattr(TransmissionLineDocument,'analyze',analyze)
    with pytest.raises(ForwardPairGoalError) as caught:
        seek_forward_pair_impedances(factory,BOUNDS,quantities(1.25,1.),tolerances=[1e-6,1e-6],max_evaluations=2)
    err=caught.value
    assert err.stage=='refinement/target' and err.attempts==2
    assert [row.stage for row in err.history]==['search','refinement']
    assert err.input_json==err.history[-1].input_json


@pytest.fixture(scope='module')
def physical_goal():
    return seek_forward_pair_impedances(document,[[.4e-3,.9e-3],[.2e-3,.6e-3]],
        [110.,40.],tolerances=[.25,.125],initial=[.7e-3,.35e-3],max_evaluations=64)


def test_real_asymmetric_two_target_goal_replay_and_refinement(physical_goal):
    result=physical_goal
    assert np.all(abs(np.array(result.residuals))<=np.array([.25,.125]))
    assert np.all(abs(np.array(result.refined_residuals))<=np.array([.25,.125]))
    assert np.all(abs(np.array(result.refined_impedances)/result.impedances-1)<=.005)
    assert result.history[-1].stage=='refinement' and len(result.history)<=64
    raw=result.document.to_dict();fine=result.refined_document.to_dict()
    for key in ['edge_size','far_size','grade']:raw['cross_section']['mesh'][key]/=2
    assert raw==fine
    mixed=result.result.characteristic().mixed_mode().z_characteristic[0]
    assert abs(mixed[0,1])>1e-3 and max(abs(np.diag(mixed).imag))>.01
    for doc,line in [(result.document,result.result),(result.refined_document,result.refined_result)]:
        replay=doc.analyze()
        for key in ['R','L','G','C']:np.testing.assert_allclose(getattr(replay,key),getattr(line,key),rtol=1e-10)
    json.dumps(result.to_dict(),allow_nan=False)


def test_both_real_goals_have_separate_finite_outer_gates(physical_goal):
    result=physical_goal;base=np.array(result.refined_impedances);previous=base.copy();changes=[]
    for box,air in [(36e-3,15e-3),(48e-3,20e-3)]:
        raw=document(*result.parameters,box=box,air=air).to_dict()
        raw['cross_section']['mesh']=result.refined_document.to_dict()['cross_section']['mesh']
        line=TransmissionLineDocument.from_dict(raw).analyze()
        values=np.diag(line.characteristic().mixed_mode().z_characteristic[0]).real
        assert np.all(abs(values-result.targets)<=result.tolerances)
        assert np.all(abs(values/base-1)<=.005)
        changes.append(abs(values-previous));previous=values
    assert np.all(changes[1]<changes[0])


def test_physical_selected_and_refined_matrices_against_independent_2n(physical_goal):
    from crosscheck import require_tool,Stopwatch
    scipy=require_tool('scipy');clock=Stopwatch();errors=dict(Zc=0.,Zdd=0.,Zcc=0.)
    a=np.array([[1.,-1.],[.5,.5]])
    for line in [physical_goal.result,physical_goal.refined_result]:
        with clock('openphysics'):actual=line.characteristic().z_characteristic[0]
        with clock('reference'):
            omega=2*np.pi*line.frequency[0];z=line.R[0]+1j*omega*line.L[0];y=line.G[0]+1j*omega*line.C[0]
            scale=np.sqrt(abs(z).max()/abs(y).max())
            roots,vectors=scipy.linalg.eig(np.block([[np.zeros_like(z),z/scale],[scale*y,np.zeros_like(y)]]))
            selected=roots.imag>0;assert np.count_nonzero(selected)==2 and np.all(roots[selected].real>=0)
            v=vectors[:,selected];expected=scale*v[:2]@np.linalg.inv(v[2:]);mixed=a@expected@a.T
        errors['Zc']=max(errors['Zc'],float(abs(actual-expected).max()/abs(expected).max()))
        for i,key in enumerate(['Zdd','Zcc']):errors[key]=max(errors[key],float(abs((a@actual@a.T)[i,i]/mixed[i,i]-1)))
    reference_record('two-variable-forward-pair-physical-2n','scipy',
        'balanced 2N voltage/current eigenspaces with positive-phase roots',errors,clock)


def test_noncallable_and_excessive_budget_reject_before_factory():
    with pytest.raises(TypeError):seek_forward_pair_impedances(None,BOUNDS,[100.,40.],tolerances=[1.,1.])
    def forbidden(*args):pytest.fail('invalid budget reached factory')
    with pytest.raises(ValueError):
        seek_forward_pair_impedances(forbidden,BOUNDS,[100.,40.],tolerances=[1.,1.],max_evaluations=10001)


def test_nonrepresentable_normalized_residual_retains_failed_attempt(monkeypatch):
    calls=synthetic(monkeypatch)
    with pytest.raises(ForwardPairGoalError) as caught:
        seek_forward_pair_impedances(factory,BOUNDS,[1e308,1e308],tolerances=[1e-308,1e-308])
    err=caught.value
    assert err.stage=='search/diagnostic' and err.attempts==len(calls)==1 and not err.history
    assert err.cause_type=='FloatingPointError' and err.input_json
