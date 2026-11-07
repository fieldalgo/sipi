# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved scalar material goals with analytical and refined-mesh acceptance."""
import json
import numpy as np
import pytest
from sipi import CrossSection, CrossSectionDocument, GoalSeekError, seek_impedance
from sipi.design_document import ImpedanceDesignDocument
from sipi.dielectric import ConstantDielectric, DebyeDielectric, dielectric_from_dict, dispersive_line
from sipi.templates import stripline
from sipi.execution import execute_saved, normalize_saved
from test_sipi_references import stripline_z0

P = dict(width=.5e-3,plane_spacing=1e-3,eps_r=1)
MESH = dict(edge_size=2e-6,far_size=.125e-3,grade=.15)
F = 1e8


def goal(**kwargs):
    args=dict(variable='dk',bounds=[2,8],target=50.,tolerance=.25,mesh=MESH,
        frequency=F,materials={'dielectric':ConstantDielectric(4)},
        material_variables={'dk':dict(region='dielectric',path=['eps_r'])})
    args.update(kwargs)
    return ImpedanceDesignDocument('stripline',P,**args)


def replay(result):
    saved=json.loads(result.material_evaluation_json)
    models={name:dielectric_from_dict(value) for name,value in saved['materials'].items()}
    field=dispersive_line(result.document.section,[saved['frequency_hz']],materials=models,
                          **result.document.mesh_options)
    assert np.sqrt(field.L[0,0]/field.C[0,0,0]) == pytest.approx(result.impedance,rel=1e-10)
    return saved


def test_saved_permittivity_goal_matches_independent_cohn_and_refinement():
    doc=goal();restored=ImpedanceDesignDocument.loads(doc.dumps())
    assert restored.dumps()==doc.dumps()==normalize_saved(doc.dumps())
    assert doc.to_dict()['schema']=='sipi.impedance-design/3'
    result=restored.solve()
    expected=(stripline_z0(P['width'],P['plane_spacing'],1)/50)**2
    assert result.parameter==pytest.approx(expected,rel=.01)
    assert abs(result.residual)<=.25 and abs(result.refined_residual)<=.25
    assert result.history[-1].stage=='refinement'
    saved=replay(result)
    assert saved['materials']['dielectric']['parameters']['eps_r']==result.parameter
    assert doc.to_dict()['material_evaluation']['materials']['dielectric']['parameters']['eps_r']==4
    print('Cohn permittivity goal',result.parameter,expected,result.residual,result.refined_residual)


def test_debye_relaxation_goal_against_independent_formula_and_execution():
    target=stripline_z0(P['width'],P['plane_spacing'],3.5)
    doc=goal(variable='pole',bounds=[F/2,2*F],target=target,tolerance=.1,
        mesh=dict(edge_size=1e-6,far_size=.125e-3,grade=.1),
        materials={'dielectric':DebyeDielectric(2,[3],[F])},
        material_variables={'pole':dict(region='dielectric',path=['relaxation_hz',0])})
    result=doc.solve()
    # Re(eps)=2+3/(1+(f/pole)^2); eps=3.5 gives pole=f.
    assert result.parameter==pytest.approx(F,rel=.015)
    assert abs(result.residual)<=.1 and abs(result.refined_residual)<=.1
    saved=replay(result)
    assert saved['materials']['dielectric']['parameters']['relaxation_hz']==[result.parameter]
    output=execute_saved(doc.dumps())
    assert output['status']=='complete'
    assert output['result']['material_evaluation']==saved
    assert output['result']['parameter']==result.parameter
    print('Debye pole goal',result.parameter,F,result.residual,result.refined_residual)


@pytest.mark.parametrize('chosen',[2.,6.])
def test_factory_called_only_for_search_and_selected_snapshot_is_refined(chosen):
    coarse=dict(edge_size=4e-6,far_size=.25e-3,grade=.2)
    base=stripline(**P);samples=dispersive_line(base,[F],materials={'dielectric':ConstantDielectric(chosen)},**coarse)
    target=np.sqrt(samples.L[0,0]/samples.C[0,0,0]);calls=[]
    def models(value):
        calls.append(value)
        return {'dielectric':ConstantDielectric(value)}
    result=seek_impedance(lambda value:base,[2,6],target,tolerance=1,mesh=coarse,
                          frequency=F,material_factory=models)
    assert result.parameter==chosen
    assert calls==[2.,6.]  # A refinement callback would make a third call.
    assert [r.stage for r in result.history]==['search','search','refinement']
    assert json.loads(result.material_evaluation_json)['materials']['dielectric']['parameters']['eps_r']==chosen
    replay(result)


@pytest.mark.parametrize('kwargs',[
    dict(material_factory=4,frequency=F),
    dict(material_factory=lambda value:{},frequency=None),
    dict(material_factory=lambda value:{},frequency=F,materials={}),
    dict(material_factory=lambda value:{},frequency=True),
    dict(material_factory=lambda value:None,frequency=F),
])
def test_bad_material_factory_inputs_reject_before_field_solving(kwargs,monkeypatch):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('invalid input meshed'))
    with pytest.raises(ValueError):seek_impedance(lambda value:stripline(**P),[2,8],50,**kwargs)


@pytest.mark.parametrize('change',[
    lambda d:d.update(schema='sipi.impedance-design/2'),
    lambda d:d.pop('material_variables'),
    lambda d:d.update(material_variables=None),
    lambda d:d.update(material_variables={}),
    lambda d:d.update(variable='width'),
    lambda d:d['material_variables'].update(other=dict(region='dielectric',path=['tan_delta'])),
    lambda d:d['material_variables']['dk'].update(path=['missing']),
    lambda d:d.update(bounds=[0,8]),
    lambda d:d.update(bounds=[-1,8]),
    lambda d:d.update(bounds=[True,8]),
    lambda d:d.update(bounds=[2,2]),
    lambda d:d.update(material_evaluation=None),
    lambda d:d.update(max_evaluations=2),
])
def test_strict_saved_material_goal_validation_before_meshing(change,monkeypatch):
    data=goal().to_dict();change(data)
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('normalization meshed'))
    with pytest.raises(ValueError):ImpedanceDesignDocument.from_dict(data)


def test_unbracketed_material_goal_preserves_history_in_shared_execution():
    doc=goal(target=1000,mesh=dict(edge_size=20e-6,far_size=.25e-3,grade=.2))
    with pytest.raises(GoalSeekError,match='not bracketed') as exc:doc.solve()
    assert [r.parameter for r in exc.value.history]==[2,8]
    out=execute_saved(doc.dumps())
    assert out['status']=='failed' and out['error']['type']=='GoalSeekError'
    assert len(out['error']['history'])==2


def test_material_goal_budget_and_snapshot():
    doc=goal(max_evaluations=3,mesh=dict(edge_size=20e-6,far_size=.25e-3,grade=.2))
    copy=doc.to_dict();copy['material_variables']['dk']['path'][0]='bad'
    assert doc.to_dict()['material_variables']['dk']['path']==['eps_r']
    with pytest.raises(GoalSeekError,match='evaluation limit') as exc:doc.solve()
    assert len(exc.value.history)==2


def test_material_endpoint_still_rejects_a_failed_refined_target():
    base=stripline(**P);coarse=dict(edge_size=20e-6,far_size=.25e-3,grade=.3)
    field=dispersive_line(base,[F],materials={'dielectric':ConstantDielectric(4)},**coarse)
    target=np.sqrt(field.L[0,0]/field.C[0,0,0])
    with pytest.raises(GoalSeekError,match='refined mesh misses') as exc:
        seek_impedance(lambda value:base,[4,8],target,tolerance=1e-5,mesh=coarse,frequency=F,
                       material_factory=lambda value:{'dielectric':ConstantDielectric(value)})
    assert exc.value.history[-1].parameter==4
    assert exc.value.history[-1].stage=='refinement'
    assert abs(exc.value.history[-1].impedance-target)>1e-5
