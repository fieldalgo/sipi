# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Geometry/material pair targets with frozen model history and Cohn references."""
import json
from types import SimpleNamespace

import numpy as np
import pytest

from sipi import CrossSection, CrossSectionDocument, PairImpedanceGoalError, seek_pair_impedances
from sipi.templates import coupled_stripline
from sipi.dielectric import (ConstantDielectric, DebyeDielectric, PrincipalAxisDielectric,
                            dielectric_from_dict, dispersive_line)
from sipi.quasistatic import LineParameters
import sipi.pair_design as module

F=1e9
BOUNDS=((.3e-3,.7e-3),(2.,6.))
MESH=dict(edge_size=1e-6,far_size=.125e-3,grade=.1)


def factory(width,strength):
    return coupled_stripline(width=width,gap=.1e-3,plane_spacing=1e-3,eps_r=1.,box_width=8e-3)


def models(width,strength):
    return {'dielectric':DebyeDielectric(2.,[strength],[F])}


def fake(values):
    return SimpleNamespace(names=('positive','negative'),
        even_odd=lambda:dict(z_diff=values[0],z_common=values[1]))


@pytest.fixture
def affine(monkeypatch):
    calls=[]
    def analyze(doc,material,quantity, *, mesh_reuse=None):
        width=doc.section.traces[0].width
        strength=material['materials']['dielectric']['parameters']['strengths'][0]
        assert material['frequency_hz']==F and quantity=='z_diff'
        calls.append((doc.dumps(),json.dumps(material,sort_keys=True)))
        u=np.array([(width-.3e-3)/.4e-3,(strength-2)/4])
        return fake(np.array([100.,40.])+np.array([[20.,-10.],[5.,15.]])@u)
    monkeypatch.setattr(module,'_analyze_material',analyze)
    return calls


def test_each_row_retains_parameter_dependent_models_and_order(affine):
    seen=[]
    def material(a,b):seen.append((a,b));return models(a,b)
    result=seek_pair_impedances(factory,BOUNDS,[109,47.5],tolerances=[1e-4,1e-4],
        frequency=F,material_factory=material,mesh=MESH)
    np.testing.assert_allclose(result.parameters,[.54e-3,3.2],rtol=1e-6)
    assert len(seen)==len(result.history)-1==len(affine)-1
    assert len(set(seen))==len(seen)
    for row in result.history:
        data=json.loads(row.material_evaluation_json)
        assert data['frequency_hz']==F
        assert data['materials']['dielectric']['parameters']['strengths']==[row.parameters[1]]
        assert row.to_dict()['material_evaluation']==data
    assert result.history[-1].material_evaluation_json==result.material_evaluation_json
    selected=[r for r in result.history[:-1] if r.parameters==result.parameters]
    assert len(selected)==1 and selected[0].material_evaluation_json==result.material_evaluation_json
    json.dumps(result.to_dict(),allow_nan=False)


@pytest.mark.parametrize('changes',[dict(frequency=None),dict(frequency=True),dict(frequency=-1),
    dict(frequency=float('inf')),dict(frequency=[F]),dict(material_factory=False),
    dict(material_factory={}),dict(materials={})])
def test_invalid_material_controls_precede_both_factories(changes):
    def forbidden(*args):pytest.fail('invalid controls reached a factory')
    kwargs=dict(frequency=F,material_factory=forbidden);kwargs.update(changes)
    with pytest.raises((ValueError,TypeError)):
        seek_pair_impedances(forbidden,BOUNDS,[100,40],tolerances=[1,1],**kwargs)


def test_refinement_freezes_models_without_recalling_either_factory(monkeypatch):
    counts={'geometry':0,'material':0};mapping=models(.5e-3,4.);observed=[]
    def geometry(a,b):counts['geometry']+=1;assert counts['geometry']==1;return factory(a,b)
    def material(a,b):counts['material']+=1;assert counts['material']==1;return mapping
    def analyze(doc,value,quantity, *, mesh_reuse=None):
        observed.append(json.dumps(value,sort_keys=True));mapping.clear();return fake([100.,40.])
    monkeypatch.setattr(module,'_analyze_material',analyze)
    result=seek_pair_impedances(geometry,BOUNDS,[100,40],tolerances=[1,1],frequency=F,
        material_factory=material,mesh=MESH,max_evaluations=2)
    assert counts=={'geometry':1,'material':1}
    assert len(observed)==2 and observed[0]==observed[1]==result.material_evaluation_json
    assert result.history[0].input_json!=result.history[1].input_json
    assert result.document.to_dict()['traces']==result.refined_document.to_dict()['traces']


@pytest.mark.parametrize('value',[None,[],{'dielectric':'bad-model'}])
def test_malformed_mapping_keeps_geometry_without_inventing_material(value):
    with pytest.raises(PairImpedanceGoalError) as caught:
        seek_pair_impedances(factory,BOUNDS,[100,40],tolerances=[1,1],frequency=F,
            material_factory=lambda a,b:value,mesh=MESH)
    exc=caught.value
    assert exc.stage=='search/material' and exc.attempts==1 and not exc.history
    assert exc.input_json is not None and exc.material_evaluation_json is None
    assert exc.__cause__ is not None


def test_material_factory_failure_preserves_completed_rows(affine):
    calls=0
    def material(a,b):
        nonlocal calls
        calls+=1
        if calls==2:raise LookupError('model unavailable')
        return models(a,b)
    with pytest.raises(PairImpedanceGoalError) as caught:
        seek_pair_impedances(factory,BOUNDS,[109,47.5],tolerances=[1e-4,1e-4],frequency=F,
            material_factory=material,mesh=MESH)
    exc=caught.value
    assert exc.stage=='search/material' and exc.attempts==2 and len(exc.history)==1
    assert exc.cause_type=='LookupError' and isinstance(exc.__cause__,LookupError)
    assert exc.material_evaluation_json is None and exc.history[0].material_evaluation_json is not None


@pytest.mark.parametrize('kind',['unknown','tilted'])
def test_encoded_invalid_material_retained_before_meshing(monkeypatch,kind):
    def forbidden(*args,**kwargs):pytest.fail('invalid material reached field mesh')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    model={'unknown':ConstantDielectric(4.)} if kind=='unknown' else {
        'dielectric':PrincipalAxisDielectric(ConstantDielectric(2),ConstantDielectric(4),30.)}
    with pytest.raises(PairImpedanceGoalError) as caught:
        seek_pair_impedances(factory,BOUNDS,[100,40],tolerances=[1,1],frequency=F,
            material_factory=lambda a,b:model,mesh=MESH)
    exc=caught.value
    assert exc.stage=='search/extraction' and exc.attempts==1 and not exc.history
    assert json.loads(exc.material_evaluation_json)['frequency_hz']==F


def test_field_failure_keeps_current_model_not_previous_model(monkeypatch):
    calls=[]
    def material(a,b):return {'dielectric':ConstantDielectric(2+1000*a)}
    def analyze(doc,value,quantity, *, mesh_reuse=None):
        calls.append(json.dumps(value,sort_keys=True))
        if len(calls)==2:raise ArithmeticError('field failed')
        return fake([100.,40.])
    monkeypatch.setattr(module,'_analyze_material',analyze)
    with pytest.raises(PairImpedanceGoalError) as caught:
        seek_pair_impedances(factory,BOUNDS,[110,45],tolerances=[.1,.1],frequency=F,
            material_factory=material,mesh=MESH)
    exc=caught.value
    assert exc.stage=='search/extraction' and exc.attempts==2 and len(exc.history)==1
    assert exc.material_evaluation_json==calls[1]!=exc.history[0].material_evaluation_json
    assert exc.history[0].material_evaluation_json==calls[0]


def test_unsuccessful_optimizer_keeps_cached_candidate_geometry_and_model(affine,monkeypatch):
    monkeypatch.setattr(module,'least_squares',lambda fun,u,**kwargs:SimpleNamespace(
        success=False,x=u,message='stopped by test'))
    with pytest.raises(PairImpedanceGoalError) as caught:
        seek_pair_impedances(factory,BOUNDS,[109,47.5],tolerances=[1e-4,1e-4],frequency=F,
            material_factory=models,mesh=MESH)
    exc=caught.value
    assert exc.stage=='convergence' and exc.attempts==1 and len(exc.history)==1
    assert exc.input_json==exc.history[0].input_json
    assert exc.material_evaluation_json==exc.history[0].material_evaluation_json


def test_budget_counts_parameter_attempts_not_two_factory_calls(affine):
    calls=[]
    def material(a,b):calls.append((a,b));return models(a,b)
    with pytest.raises(PairImpedanceGoalError) as caught:
        seek_pair_impedances(factory,BOUNDS,[109,47.5],tolerances=[1e-4,1e-4],frequency=F,
            material_factory=material,mesh=MESH,max_evaluations=5)
    exc=caught.value
    assert exc.stage=='budget' and exc.attempts==4
    assert len(calls)==len(affine)==len(exc.history)==4
    assert all(r.material_evaluation_json for r in exc.history)


def test_zero_frequency_uses_existing_nonnegative_contract(monkeypatch):
    observed=[]
    def analyze(doc,value,quantity, *, mesh_reuse=None):
        observed.append(value['frequency_hz']);return fake([100.,40.])
    monkeypatch.setattr(module,'_analyze_material',analyze)
    result=seek_pair_impedances(factory,BOUNDS,[100,40],tolerances=[1,1],frequency=0.,
        material_factory=models,mesh=MESH,max_evaluations=2)
    assert observed==[0.,0.]
    assert json.loads(result.material_evaluation_json)['frequency_hz']==0.


def test_geometry_only_row_retains_four_argument_constructor_and_dict_shape():
    row=module.PairImpedanceEvaluation((1.,2.),(100.,40.),'search','{}')
    assert row.material_evaluation_json is None
    assert row.to_dict()==dict(parameters=[1.,2.],impedances_ohm=[100.,40.],stage='search',input={})


def test_real_width_strength_goal_against_cohn_refinement_and_outer_domain():
    from test_sipi_references import coupled_stripline_z
    even,odd=coupled_stripline_z(.5e-3,.1e-3,1e-3,4.)
    targets=np.array([2*odd,even/2]);tolerances=np.array([.5,.2])
    result=seek_pair_impedances(factory,BOUNDS,targets,tolerances=tolerances,frequency=F,
        material_factory=models,initial=[.35e-3,5.5],mesh=MESH,max_evaluations=64)
    assert np.max(abs(np.array(result.parameters)/[.5e-3,4.]-1))<.02
    assert np.all(np.abs(result.residuals)<=tolerances) and np.all(np.abs(result.refined_residuals)<=tolerances)
    for row in result.history:
        data=json.loads(row.material_evaluation_json)
        assert data['frequency_hz']==F
        model=dielectric_from_dict(data['materials']['dielectric'])
        assert model.strengths==(row.parameters[1],)
        assert model.permittivity(F)==pytest.approx(2+row.parameters[1]/(1+1j),rel=1e-12)
    def replay(row,outer=False):
        doc=CrossSectionDocument.loads(row.input_json);data=doc.to_dict()
        if outer:data['box']['width']=16e-3
        doc=CrossSectionDocument.from_dict(data)
        material=json.loads(row.material_evaluation_json)
        sweep=dispersive_line(doc.section,[F],materials={k:dielectric_from_dict(v)
            for k,v in material['materials'].items()},**doc.mesh_options)
        modes=LineParameters(sweep.names,sweep.C[0],sweep.C0,sweep.L,-sweep.C_complex[0].imag).even_odd()
        return np.array([modes['z_diff'],modes['z_common']])
    selected=next(row for row in result.history[:-1] if row.parameters==result.parameters)
    for row in (result.history[0],selected):
        np.testing.assert_allclose(replay(row),row.impedances,rtol=1e-10,atol=0)
    outer=replay(selected,outer=True)
    width,strength=result.parameters
    even,odd=coupled_stripline_z(width,.1e-3,1e-3,2+strength/2)
    independent=np.array([2*odd,even/2])
    assert np.all(abs(outer-targets)<=tolerances)
    assert np.all(abs(independent-targets)<=tolerances)
    assert result.material_evaluation_json==selected.material_evaluation_json==result.history[-1].material_evaluation_json
    print('material pair target/parameters/attempts',targets,result.parameters,len(result.history),
        'requested/refined/outer/cohn',result.residuals,result.refined_residuals,outer-targets,independent-targets)
