# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Bounded paired goals: control failures and independent field targets."""
from dataclasses import FrozenInstanceError, replace
import json
from types import SimpleNamespace

import numpy as np
import pytest

from sipi import (CrossSection, CrossSectionDocument, PairImpedanceGoalError, seek_pair_impedances,
                  coupled_grounded_coplanar)
from sipi.dielectric import ConstantDielectric, PrincipalAxisDielectric
import sipi.pair_design as module

BOUNDS=((.3e-3,.7e-3),(.1e-3,.5e-3))
MESH=dict(edge_size=2e-6,far_size=.125e-3,grade=.15)


def factory(width,gap,**changes):
    return coupled_grounded_coplanar(width=width,gap=gap,ground_gap=.2e-3,
        ground_width=1e-3,substrate_height=.5e-3,eps_r=1.,thickness=0.,
        **dict(dict(box_width=12e-3,air_height=6e-3),**changes))


def coordinates(doc):
    a,b=doc.section.traces[:2]
    return np.array([(a.width-.3e-3)/.4e-3,(b.x0-a.x1-.1e-3)/.4e-3])


def affine(u):
    return np.array([100.,40.])+np.array([[20.,-10.],[5.,15.]])@u


@pytest.fixture
def analytic(monkeypatch):
    calls=[]
    def analyze(doc):
        calls.append(doc.dumps());values=affine(coordinates(doc))
        return SimpleNamespace(names=('positive','negative'),
            even_odd=lambda:dict(z_diff=values[0],z_common=values[1]))
    monkeypatch.setattr(CrossSectionDocument,'analyze',analyze)
    return calls


@pytest.mark.parametrize('scale',[(1.,1.),(1000.,.001)])
def test_coupled_affine_targets_and_parameter_unit_scaling(analytic,scale):
    bounds=np.array(BOUNDS)/np.array(scale)[:,None]
    result=seek_pair_impedances(lambda a,b:factory(a*scale[0],b*scale[1]),bounds,
        affine([.6,.3]),tolerances=[1e-4,1e-4],mesh=MESH)
    np.testing.assert_allclose(np.array(result.parameters)*scale,[.54e-3,.22e-3],rtol=1e-6)
    assert max(abs(np.array(result.residuals)))<=1e-4
    assert max(abs(np.array(result.refined_residuals)))<=1e-4
    assert len(result.history)==len(analytic)<=64
    assert result.history[-1].stage=='refinement'
    assert len({row.parameters for row in result.history[:-1]})==len(result.history)-1
    assert result.refined_document.mesh_options['edge_size']==MESH['edge_size']/2
    json.dumps(result.to_dict(),allow_nan=False)
    with pytest.raises(FrozenInstanceError):result.parameters=(1.,2.)
    copy=result.to_dict();copy['input']['traces'][0]['width']=1
    assert result.document.section.traces[0].width<.001


@pytest.mark.parametrize('point',[(.3e-3,.1e-3),(.5e-3,.3e-3),(.7e-3,.5e-3)])
def test_initial_and_endpoint_targets_reserve_frozen_refinement(analytic,point):
    calls=[]
    def once(a,b):
        calls.append((a,b));assert len(calls)==1
        return factory(a,b)
    target=affine((np.array(point)-np.array(BOUNDS)[:,0])/.4e-3)
    out=seek_pair_impedances(once,BOUNDS,target,tolerances=[1e-6,1e-6],initial=point,
        mesh=dict(MESH,min_angle=25.),max_evaluations=2)
    assert len(out.history)==len(analytic)==2 and len(calls)==1
    assert out.refined_document.mesh_options['min_angle']==25.
    assert out.refined_document.to_dict()['traces']==out.document.to_dict()['traces']
    assert out.refined_document.to_dict()['layers']==out.document.to_dict()['layers']


@pytest.mark.parametrize('change',[
    dict(bounds=[[0,1],[1,2]]),dict(bounds=[[2,1],[1,2]]),dict(bounds=[1,2]),
    dict(bounds=[[True,2],[1,2]]),dict(targets=[0,1]),dict(targets=[100,np.inf]),
    dict(targets=[100,True]),dict(targets=[100]),dict(tolerances=[1,0]),
    dict(tolerances=[1,np.nan]),dict(initial=[.1e-3,.3e-3]),dict(initial=[.5e-3]),
    dict(initial=[False,.3e-3]),dict(max_evaluations=True),dict(max_evaluations=1),
    dict(max_evaluations=10001),dict(mesh={'unknown':1}),dict(mesh={'edge_size':0}),
    dict(frequency=1e9),dict(materials={'substrate':ConstantDielectric(4.)}),
])
def test_control_errors_before_factory(change):
    def forbidden(*args):pytest.fail('invalid controls reached factory')
    args=dict(bounds=BOUNDS,targets=[100,40],tolerances=[1,1]);args.update(change)
    with pytest.raises((ValueError,TypeError)):seek_pair_impedances(forbidden,**args)


@pytest.mark.parametrize('budget',[2,3,5])
def test_actual_attempt_budget_includes_jacobian_probes(analytic,budget):
    with pytest.raises(PairImpedanceGoalError) as caught:
        seek_pair_impedances(factory,BOUNDS,affine([.6,.3]),tolerances=[1e-6,1e-6],
            mesh=MESH,max_evaluations=budget)
    exc=caught.value
    assert exc.stage=='budget' and exc.attempts==budget-1
    assert len(exc.history)==len(analytic)==budget-1
    assert all(row.stage=='search' for row in exc.history)


def test_factory_failure_keeps_completed_history_and_cause(analytic):
    count=0
    def broken(a,b):
        nonlocal count
        count+=1
        if count==2:raise LookupError('invalid local candidate')
        return factory(a,b)
    with pytest.raises(PairImpedanceGoalError) as caught:
        seek_pair_impedances(broken,BOUNDS,[109,47.5],tolerances=[1e-4,1e-4],mesh=MESH)
    exc=caught.value
    assert exc.attempts==2 and len(exc.history)==1 and exc.stage=='search/factory'
    assert exc.cause_type=='LookupError' and isinstance(exc.__cause__,LookupError)
    assert exc.failed_parameters is not None


@pytest.mark.parametrize('kind',['nan','negative','names','asymmetry','exception'])
def test_diagnostic_and_extraction_errors_are_not_success(monkeypatch,kind):
    def analyze(doc):
        if kind=='exception':raise ArithmeticError('field failed')
        def modes():
            if kind=='asymmetry':raise ValueError('pair is not symmetric')
            return dict(z_diff=np.nan if kind=='nan' else -1 if kind=='negative' else 100.,z_common=40.)
        return SimpleNamespace(names=('other','negative') if kind=='names' else ('positive','negative'),even_odd=modes)
    monkeypatch.setattr(CrossSectionDocument,'analyze',analyze)
    with pytest.raises(PairImpedanceGoalError) as caught:
        seek_pair_impedances(factory,BOUNDS,[100,40],tolerances=[1,1],mesh=MESH)
    assert caught.value.attempts==1 and not caught.value.history
    assert caught.value.input_json and caught.value.__cause__ is not None


def test_signal_identity_changes_fail_before_extraction(analytic):
    count=0
    def changing(a,b):
        nonlocal count
        count+=1;s=factory(a,b)
        return s if count==1 else CrossSection(s.layers,
            [replace(t,name='changed') if i==0 else t for i,t in enumerate(s.traces)],
            s.width,bottom=s.bottom,top=s.top,sides=s.sides)
    with pytest.raises(PairImpedanceGoalError) as caught:
        seek_pair_impedances(changing,BOUNDS,[109,47.5],tolerances=[1e-4,1e-4],mesh=MESH)
    assert caught.value.stage=='search/validation' and caught.value.attempts==2
    assert len(analytic)==1 and len(caught.value.history)==1


def test_refinement_miss_preserves_both_rows(monkeypatch):
    def analyze(doc):
        z=105. if doc.mesh_options['edge_size']==MESH['edge_size'] else 109.
        return SimpleNamespace(names=('positive','negative'),even_odd=lambda:dict(z_diff=z,z_common=50.))
    monkeypatch.setattr(CrossSectionDocument,'analyze',analyze)
    with pytest.raises(PairImpedanceGoalError) as caught:
        seek_pair_impedances(factory,BOUNDS,[105,50],tolerances=[.1,.1],mesh=MESH,max_evaluations=2)
    exc=caught.value
    assert exc.stage=='refinement/target' and exc.attempts==2
    assert [r.stage for r in exc.history]==['search','refinement']
    assert exc.history[-1].impedances==(109.,50.)


def test_impossible_stationary_objective_fails(monkeypatch):
    monkeypatch.setattr(CrossSectionDocument,'analyze',lambda doc:SimpleNamespace(
        names=('positive','negative'),even_odd=lambda:dict(z_diff=100.,z_common=40.)))
    with pytest.raises(PairImpedanceGoalError) as caught:
        seek_pair_impedances(factory,BOUNDS,[110,45],tolerances=[.1,.1],mesh=MESH)
    assert caught.value.stage=='convergence' and caught.value.history
    assert all(r.stage=='search' for r in caught.value.history)


def test_rank_deficient_feasible_objective_does_not_claim_unique_parameters(monkeypatch):
    def analyze(doc):
        total=sum(coordinates(doc));return SimpleNamespace(names=('positive','negative'),
            even_odd=lambda:dict(z_diff=100+total,z_common=40+2*total))
    monkeypatch.setattr(CrossSectionDocument,'analyze',analyze)
    out=seek_pair_impedances(factory,BOUNDS,[101.3,42.6],tolerances=[1e-4,1e-4],mesh=MESH)
    assert max(abs(np.array(out.refined_residuals)))<=1e-4


def test_material_snapshot_and_same_fixed_frequency_on_both_meshes(monkeypatch):
    supplied={'substrate':ConstantDielectric(4.,.02)};observed=[]
    def material(doc,value,quantity):
        observed.append(json.dumps(value,sort_keys=True));assert quantity=='z_diff'
        supplied.clear()
        return SimpleNamespace(names=('positive','negative'),even_odd=lambda:dict(z_diff=100.,z_common=40.))
    monkeypatch.setattr(module,'_analyze_material',material)
    out=seek_pair_impedances(factory,BOUNDS,[100,40],tolerances=[.1,.1],mesh=MESH,
        frequency=1e9,materials=supplied,max_evaluations=2)
    assert len(observed)==2 and observed[0]==observed[1]==out.material_evaluation_json
    assert json.loads(out.material_evaluation_json)['frequency_hz']==1e9


def test_tilted_tensor_rejected_before_field_extraction(monkeypatch):
    def forbidden(*args,**kwargs):pytest.fail('tilted material reached field extraction')
    monkeypatch.setattr('sipi.impedance_material.dispersive_line',forbidden)
    model=PrincipalAxisDielectric(ConstantDielectric(2),ConstantDielectric(4),30.)
    with pytest.raises(PairImpedanceGoalError,match='diagonal'):
        seek_pair_impedances(factory,BOUNDS,[100,40],tolerances=[1,1],mesh=MESH,
            frequency=1e9,materials={'substrate':model})


def test_failure_retains_material_snapshot_after_caller_mutation(monkeypatch):
    supplied={'substrate':ConstantDielectric(4.,.02)};calls=0
    def material(doc,value,quantity):
        nonlocal calls
        calls+=1;supplied.clear()
        if calls==2:raise ArithmeticError('refinement failed')
        return SimpleNamespace(names=('positive','negative'),even_odd=lambda:dict(z_diff=100.,z_common=40.))
    monkeypatch.setattr(module,'_analyze_material',material)
    with pytest.raises(PairImpedanceGoalError) as caught:
        seek_pair_impedances(factory,BOUNDS,[100,40],tolerances=[.1,.1],mesh=MESH,
            frequency=1e9,materials=supplied,max_evaluations=2)
    exc=caught.value;model=json.loads(exc.material_evaluation_json)
    assert exc.stage=='refinement/extraction' and len(exc.history)==1 and exc.attempts==2
    assert model['frequency_hz']==1e9 and model['materials']['substrate']['parameters']['eps_r']==4.


def test_fixed_material_pair_obeys_homogeneous_capacitance_scaling():
    from sipi.templates import coupled_stripline
    def section(width,gap):
        return coupled_stripline(width=width,gap=gap,plane_spacing=1e-3,
            eps_r=1.,box_width=8e-3)
    modes=section(.5e-3,.3e-3).analyze(**MESH).even_odd()
    targets=np.array([modes['z_diff'],modes['z_common']])/2
    result=seek_pair_impedances(section,BOUNDS,targets,tolerances=[1.,1.],mesh=MESH,
        frequency=1e9,materials={'dielectric':ConstantDielectric(4.,.02)},max_evaluations=2)
    # Compare the exact frozen geometry: the normalized midpoint can differ
    # from decimal literals by an ulp, changing an adaptive mesh's topology.
    requested=result.document.analyze().even_odd()
    np.testing.assert_allclose(result.impedances,
        np.array([requested['z_diff'],requested['z_common']])/2,rtol=1e-10,atol=0)
    refined=result.refined_document.analyze().even_odd()
    np.testing.assert_allclose(result.refined_impedances,
        np.array([refined['z_diff'],refined['z_common']])/2,rtol=1e-10,atol=0)
    assert json.loads(result.material_evaluation_json)['materials']['dielectric']['parameters']['eps_r']==4.
    print('material scaling literal/selected parameters',(.5e-3,.3e-3),result.parameters,
        'literal/requested vacuum targets',targets,np.array([requested['z_diff'],requested['z_common']])/2)


def test_wrong_factory_type_and_refinement_exception_keep_context(monkeypatch):
    with pytest.raises(PairImpedanceGoalError) as caught:
        seek_pair_impedances(lambda a,b:None,BOUNDS,[100,40],tolerances=[1,1])
    assert caught.value.stage=='search/validation' and caught.value.attempts==1
    calls=0
    def analyze(doc):
        nonlocal calls
        calls+=1
        if calls==2:raise ArithmeticError('refinement field failed')
        return SimpleNamespace(names=('positive','negative'),even_odd=lambda:dict(z_diff=100.,z_common=40.))
    monkeypatch.setattr(CrossSectionDocument,'analyze',analyze)
    with pytest.raises(PairImpedanceGoalError) as caught:
        seek_pair_impedances(factory,BOUNDS,[100,40],tolerances=[1,1],mesh=MESH,max_evaluations=2)
    assert caught.value.stage=='refinement/extraction' and caught.value.attempts==2
    assert len(caught.value.history)==1 and caught.value.input_json


def test_independent_panel_target_refinement_outer_domain_and_geometry():
    from scipy.constants import c
    from test_coupled_coplanar import panel_reference
    def reference(width,gap):
        intervals=[(-gap/2-width,-gap/2),(gap/2,gap/2+width),
            (-gap/2-width-.2e-3-1e-3,-gap/2-width-.2e-3),
            (gap/2+width+.2e-3,gap/2+width+.2e-3+1e-3)]
        cap=panel_reference(intervals,.5e-3,160)[:2,:2]
        return np.array([2/(c*(cap[0,0]-cap[0,1])),.5/(c*(cap[0,0]+cap[0,1]))])
    target=reference(.5e-3,.3e-3);tolerance=np.array([1.5,.5])
    result=seek_pair_impedances(factory,BOUNDS,target,tolerances=tolerance,initial=[.35e-3,.45e-3],mesh=MESH)
    assert np.all(abs(np.array(result.residuals))<=tolerance)
    assert np.all(abs(np.array(result.refined_residuals))<=tolerance)
    assert np.max(abs(np.array(result.parameters)/[.5e-3,.3e-3]-1))<.02
    outer=factory(*result.parameters,box_width=24e-3,air_height=12e-3).analyze(**MESH).even_odd()
    outer_error=np.array([outer['z_diff'],outer['z_common']])-target
    independent_error=reference(*result.parameters)-target
    assert np.all(abs(outer_error)<=tolerance)
    assert np.all(abs(independent_error)<=tolerance)
    assert len(result.history)<=64 and result.history[-1].stage=='refinement'
    print('pair design independent target',target,'parameters',result.parameters,'attempts',len(result.history),
        'requested/refined/outer/panel',result.residuals,result.refined_residuals,outer_error,independent_error)
