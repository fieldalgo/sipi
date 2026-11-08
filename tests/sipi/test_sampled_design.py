# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Finite-frequency goals, actual batch budgets and independent thin-line checks."""
from dataclasses import FrozenInstanceError
import json
from types import SimpleNamespace

import numpy as np
import pytest

from sipi import (CrossSection, CrossSectionDocument, SampledImpedanceGoalError,
                  seek_sampled_impedance)
from sipi.templates import coupled_stripline, stripline
from sipi.dielectric import DebyeDielectric, ConstantDielectric, PrincipalAxisDielectric
from sipi.impedance_material import _analyze_material
import sipi.sampled_design as module

BOUNDS=((.3e-3,.7e-3),(2.,6.))
F=[1e8,1e10]
MESH=dict(edge_size=1e-6,far_size=.125e-3,grade=.1)


def factory(width,strength):
    return coupled_stripline(width=width,gap=.1e-3,plane_spacing=1e-3,eps_r=1.,box_width=8e-3)


def models(width,strength):return {'dielectric':DebyeDielectric(2.,[strength],[1e9])}


def run(**changes):
    args=dict(factory=factory,bounds=BOUNDS,frequencies=F,targets=[109.,47.5],
        tolerances=[1e-4,1e-4],quantity='z_diff',mesh=MESH,material_factory=models)
    args.update(changes);return seek_sampled_impedance(**args)


def affine_values(u):return np.array([100.,40.])+np.array([[20.,-10.],[5.,15.]])@u


@pytest.fixture
def affine(monkeypatch):
    calls=[]
    def analyze(doc,value,quantity):
        width=doc.section.traces[0].width
        strength=value['materials']['dielectric']['parameters']['strengths'][0]
        calls.append((doc.dumps(),json.dumps(value,sort_keys=True)))
        return ('positive','negative'),affine_values(np.array([(width-.3e-3)/.4e-3,(strength-2)/4]))
    monkeypatch.setattr(module,'_analyze_sweep',analyze)
    return calls


@pytest.mark.parametrize('scale',[(1.,1.),(1000.,.001)])
def test_coupled_sample_goals_units_cache_and_per_batch_models(affine,scale):
    d=run(bounds=np.array(BOUNDS)/np.array(scale)[:,None],
        factory=lambda a,b:factory(a*scale[0],b*scale[1]),
        material_factory=lambda a,b:models(a*scale[0],b*scale[1]))
    np.testing.assert_allclose(np.array(d.parameters)*scale,[.54e-3,3.2],rtol=1e-6)
    assert len(d.history)==len(affine)<=64
    assert len({r.parameters for r in d.history[:-1]})==len(d.history)-1
    for row in d.history:
        data=json.loads(row.material_sweep_json)
        assert data['frequencies_hz']==F
        assert data['materials']['dielectric']['parameters']['strengths']==[row.parameters[1]*scale[1]]
        assert row.to_dict()['material_sweep']==data
        assert row.quantity==row.to_dict()['quantity']=='z_diff'
    assert d.material_sweep_json==d.history[-1].material_sweep_json
    assert d.quantity=='z_diff' and d.frequencies==tuple(F)
    assert np.max(np.abs(d.refined_residuals))<=1e-4
    json.dumps(d.to_dict(),allow_nan=False)
    with pytest.raises(FrozenInstanceError):d.parameters=(1.,2.)
    x=d.to_dict();x['input']['traces'][0]['width']=1
    assert d.document.section.traces[0].width<1e-3


@pytest.mark.parametrize('quantity',['z0','z_diff','z_common'])
def test_standalone_row_identifies_its_quantity(quantity):
    row=module.SampledImpedanceEvaluation((1.,2.),(100.,40.),'search','{}',
        json.dumps(dict(frequencies_hz=F,materials={})),quantity)
    assert row.to_dict()['quantity']==quantity
    assert row.to_dict()['material_sweep']['frequencies_hz']==F


@pytest.mark.parametrize('feasible',[True,False])
def test_overdetermined_search_requires_every_sample(monkeypatch,feasible):
    matrix=np.array([[20.,-10.],[5.,15.],[4.,8.]])
    offset=np.array([100.,40.,70.]);target=offset+matrix@np.array([.6,.3])
    if not feasible:target[2]+=10
    def analyze(doc,value,quantity):
        w=doc.section.traces[0].width
        s=value['materials']['dielectric']['parameters']['strengths'][0]
        return ('positive','negative'),offset+matrix@np.array([(w-.3e-3)/.4e-3,(s-2)/4])
    monkeypatch.setattr(module,'_analyze_sweep',analyze)
    if feasible:
        d=run(frequencies=[1e8,1e9,1e10],targets=target,tolerances=[1e-4]*3)
        np.testing.assert_allclose(d.parameters,[.54e-3,3.2],rtol=1e-6)
        assert np.max(np.abs(d.refined_residuals))<=1e-4
    else:
        with pytest.raises(SampledImpedanceGoalError) as caught:
            run(frequencies=[1e8,1e9,1e10],targets=target,tolerances=[1e-4]*3)
        assert caught.value.stage=='convergence' and caught.value.input_json


def test_maximum_frequency_count_still_counts_two_batches(monkeypatch):
    frequencies=list(range(64));targets=np.arange(64.)+100
    monkeypatch.setattr(module,'_analyze_sweep',lambda doc,value,quantity:(('positive','negative'),targets))
    d=run(frequencies=frequencies,targets=targets,tolerances=[1.]*64,max_evaluations=2,
          material_factory=None)
    assert len(d.history)==2 and d.frequencies==tuple(frequencies)
    assert json.loads(d.material_sweep_json)['materials']=={}


@pytest.mark.parametrize('change',[
    dict(frequencies=[]),dict(frequencies=[1e9]),dict(frequencies=list(range(65))),
    dict(frequencies=[1e9,1e9]),dict(frequencies=[2e9,1e9]),dict(frequencies=[-1,1]),
    dict(frequencies=[0,True]),dict(frequencies=[0,np.inf]),dict(frequencies=[[1,2]]),
    dict(targets=[100]),dict(targets=[0,40]),dict(targets=[100,np.nan]),
    dict(tolerances=[1]),dict(tolerances=[1,False]),dict(quantity='gamma'),dict(quantity=[]),
    dict(bounds=[[0,1],[1,2]]),dict(bounds=[[2,1],[1,2]]),dict(bounds=[1,2]),
    dict(initial=[.2e-3,4]),dict(initial=[.5e-3]),dict(max_evaluations=1),
    dict(max_evaluations=True),dict(mesh={'unknown':1}),dict(materials={}),
    dict(material_factory=False),dict(material_factory={}),
])
def test_controls_precede_both_callbacks(change):
    def forbidden(*args):pytest.fail('invalid controls reached factory')
    changes=dict(factory=forbidden,material_factory=forbidden);changes.update(change)
    with pytest.raises((ValueError,TypeError)):run(**changes)


def test_frozen_refinement_no_factory_recall_and_caller_isolation(monkeypatch):
    frequencies=np.array(F);targets=np.array([100.,40.]);mapping=models(.5e-3,4.);counts=[0,0];seen=[]
    def geometry(a,b):
        counts[0]+=1;assert counts[0]==1
        frequencies[:]=-1;targets[:]=1
        return factory(a,b)
    def material(a,b):counts[1]+=1;assert counts[1]==1;return mapping
    def analyze(doc,value,quantity):
        seen.append(json.dumps(value,sort_keys=True));mapping.clear()
        return ('positive','negative'),[100.,40.]
    monkeypatch.setattr(module,'_analyze_sweep',analyze)
    d=run(factory=geometry,frequencies=frequencies,targets=targets,material_factory=material,max_evaluations=2)
    assert counts==[1,1] and len(d.history)==2
    assert d.frequencies==tuple(F) and d.targets==(100.,40.)
    assert seen[0]==seen[1]==d.material_sweep_json
    assert d.refined_document.mesh_options['edge_size']==MESH['edge_size']/2
    assert d.document.to_dict()['traces']==d.refined_document.to_dict()['traces']


@pytest.mark.parametrize('budget',[2,3,5])
def test_budget_counts_batches_including_jacobian_and_reserves_refinement(affine,budget):
    with pytest.raises(SampledImpedanceGoalError) as caught:run(max_evaluations=budget)
    exc=caught.value
    assert exc.stage=='budget' and exc.attempts==budget-1==len(exc.history)==len(affine)
    assert exc.quantity=='z_diff' and exc.frequencies==tuple(F)


@pytest.mark.parametrize('kind',['shape','negative','nonfinite','names'])
def test_invalid_extraction_is_failure(monkeypatch,kind):
    def analyze(*args):return ('bad','negative') if kind=='names' else ('positive','negative'),{
        'shape':[100.], 'negative':[-1,40], 'nonfinite':[np.nan,40], 'names':[100,40]}[kind]
    monkeypatch.setattr(module,'_analyze_sweep',analyze)
    with pytest.raises(SampledImpedanceGoalError) as caught:run()
    exc=caught.value
    assert exc.stage=='search/diagnostic' and exc.attempts==1 and not exc.history
    assert exc.input_json and exc.material_sweep_json and exc.__cause__


def test_geometry_quantity_and_tilted_models_rejected_before_mesh(monkeypatch):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('invalid input meshed'))
    with pytest.raises(SampledImpedanceGoalError) as caught:run(quantity='z0')
    assert caught.value.stage=='search/validation'
    for quantity in ['z_diff','z_common']:
        with pytest.raises(SampledImpedanceGoalError) as caught:
            run(quantity=quantity,material_factory=lambda a,b:{'dielectric':PrincipalAxisDielectric(
                ConstantDielectric(2),ConstantDielectric(4),.3)})
        assert caught.value.stage=='search/extraction' and caught.value.material_sweep_json


def test_failed_model_creation_has_no_previous_mapping(affine):
    calls=0
    def material(a,b):
        nonlocal calls
        calls+=1
        if calls==2:raise LookupError('model unavailable')
        return models(a,b)
    with pytest.raises(SampledImpedanceGoalError) as caught:run(material_factory=material)
    exc=caught.value
    assert exc.attempts==2 and exc.stage=='search/material' and len(exc.history)==1
    assert exc.material_sweep_json is None and exc.history[0].material_sweep_json
    assert exc.input_json and isinstance(exc.__cause__,LookupError)


def test_current_failed_model_differs_from_previous_completed_model(monkeypatch):
    calls=[]
    def material(a,b):return {'dielectric':ConstantDielectric(2+1000*a)}
    def analyze(doc,value,quantity):
        calls.append(json.dumps(value,sort_keys=True))
        if len(calls)==2:raise ArithmeticError('failed batch')
        return ('positive','negative'),[100.,40.]
    monkeypatch.setattr(module,'_analyze_sweep',analyze)
    with pytest.raises(SampledImpedanceGoalError) as caught:run(material_factory=material)
    exc=caught.value
    assert exc.stage=='search/extraction' and exc.attempts==2
    assert exc.material_sweep_json==calls[1]!=exc.history[0].material_sweep_json==calls[0]


@pytest.mark.parametrize('kind',['unsuccessful','stationary','refined-miss'])
def test_optimizer_and_refinement_failures_retain_candidate(affine,monkeypatch,kind):
    if kind!='refined-miss':
        monkeypatch.setattr(module,'least_squares',lambda fun,u,**kw:SimpleNamespace(
            success=kind=='stationary',x=u,message='stopped'))
    else:
        calls=0
        def analyze(doc,value,quantity):
            nonlocal calls
            calls+=1
            return ('positive','negative'),[109.,47.5] if calls==1 else [110.,47.5]
        monkeypatch.setattr(module,'_analyze_sweep',analyze)
    with pytest.raises(SampledImpedanceGoalError) as caught:run()
    exc=caught.value
    assert exc.stage==('refinement/target' if kind=='refined-miss' else 'convergence')
    assert exc.input_json and exc.material_sweep_json and exc.failed_parameters
    if kind=='refined-miss':assert len(exc.history)==exc.attempts==2


@pytest.mark.parametrize('quantity',['z0','z_common'])
def test_real_batch_single_mesh_scaling_and_individual_frequency_parity(monkeypatch,quantity):
    from test_sipi_references import stripline_z0,coupled_stripline_z
    frequencies=[0.,1e9,1e10];model=DebyeDielectric(2.,[4.],[1e9])
    def geometry(w,s):
        return stripline(width=w,plane_spacing=1e-3,eps_r=1.,box_width=8e-3) if quantity=='z0' else factory(w,s)
    expected=np.array([stripline_z0(.5e-3,1e-3,model.permittivity(f).real) if quantity=='z0'
        else coupled_stripline_z(.5e-3,.1e-3,1e-3,model.permittivity(f).real)[0]/2 for f in frequencies])
    original=CrossSection.mesh;calls=[]
    def mesh(self,**kwargs):calls.append(kwargs);return original(self,**kwargs)
    monkeypatch.setattr(CrossSection,'mesh',mesh)
    d=run(factory=geometry,quantity=quantity,frequencies=frequencies,targets=expected,
        tolerances=[.5]*3,material_factory=None,materials={'dielectric':model},max_evaluations=2)
    assert len(calls)==2
    for doc,values in [(d.document,d.impedances),(d.refined_document,d.refined_impedances)]:
        vacuum=doc.analyze();z=vacuum.z0 if quantity=='z0' else vacuum.even_odd()[quantity]
        np.testing.assert_allclose(values,z/np.sqrt(model.permittivity(frequencies).real),rtol=1e-10,atol=0)
        for f,value in zip(frequencies,values):
            single=_analyze_material(doc,dict(frequency_hz=f,materials=json.loads(d.material_sweep_json)['materials']),
                                     'z0' if quantity=='z0' else 'z_diff')
            assert value==pytest.approx(single.z0 if quantity=='z0' else single.even_odd()[quantity],rel=1e-10)


def test_real_two_frequency_inverse_refinement_outer_and_cohn():
    from test_sipi_references import coupled_stripline_z
    def reference(w,s):return np.array([2*coupled_stripline_z(w,.1e-3,1e-3,2+s/(1+(f/1e9)**2))[1] for f in F])
    target=reference(.5e-3,4.)
    d=run(targets=target,tolerances=[.5,.5],initial=[.35e-3,5.5])
    assert np.max(abs(np.array(d.parameters)/[.5e-3,4.]-1))<.02
    for values in [d.impedances,d.refined_impedances,reference(*d.parameters)]:
        assert np.all(abs(np.array(values)-target)<=.5)
    selected=next(r for r in d.history[:-1] if r.parameters==d.parameters)
    for row in [d.history[0],selected]:
        _,actual=module._analyze_sweep(CrossSectionDocument.loads(row.input_json),
                                     json.loads(row.material_sweep_json),'z_diff')
        np.testing.assert_allclose(actual,row.impedances,rtol=1e-10,atol=0)
    doc=d.document.to_dict();doc['box']['width']=16e-3
    _,outer=module._analyze_sweep(CrossSectionDocument.from_dict(doc),json.loads(d.material_sweep_json),'z_diff')
    assert np.all(abs(outer-target)<=.5)
    assert selected.material_sweep_json==d.material_sweep_json==d.history[-1].material_sweep_json
    print('sampled inverse parameters/attempts',d.parameters,len(d.history),
        'requested/refined/outer/cohn',d.residuals,d.refined_residuals,outer-target,reference(*d.parameters)-target)
