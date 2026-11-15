# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit corner goals preserve search controls, refinement and field evidence."""
import json
from dataclasses import replace
import numpy as np
import pytest
from sipi.corner_fem_line import CornerFEMShapeTransmissionLineDocument as Document
from sipi.corner_fem_goal import seek_corner_fem_shape_line_quantity as seek
from sipi.fem_shape_goal import FEMShapeLineQuantityGoalError as Error
from sipi.fem_shape_line import FEMShapeTransmissionLineDocument, FEMShapeLineError, FEMShapeCurrentError
from test_fem_shape_goal import factory as original_factory, fake as old_fake, MESH
from test_fem_shape_study_physical import independent


def factory(width,quantity='impedance_real',corner=2.5e-6):
    return Document(original_factory(width,quantity),corner)


def fake(monkeypatch,**options):
    old_fake(monkeypatch,**options);method=FEMShapeTransmissionLineDocument.analyze;calls=[]
    def analyze(doc):
        calls.append(doc.to_dict());result=method(doc.line);result.input_json=doc.dumps();return result
    monkeypatch.setattr(Document,'analyze',analyze)
    return calls


@pytest.mark.parametrize('quantity',['impedance_real','attenuation','differential_forward_impedance_real','common_forward_impedance_real'])
def test_four_quantities_freeze_input_and_reserve_refinement(monkeypatch,quantity):
    fields=fake(monkeypatch);calls=[]
    def make(x):calls.append(x);return factory(x*.0004,quantity)
    result=seek(make,[1.,2.],.7,quantity=quantity,tolerance=1e-6)
    assert result.parameter==pytest.approx(10/7,abs=3e-6)
    assert len(fields)==len(result.history)==len(calls)+1
    selected=result.document.to_dict();settings=result.document.cross_section.section.mesh_settings(**result.document.cross_section.mesh_options)
    corner=settings.pop('corner_size')/2
    for key in ('edge_size','far_size','grade'):settings[key]/=2
    selected['line']['cross_section']['mesh']=settings;selected['corner_size']=corner
    assert selected==result.refined_document.to_dict()
    assert result.to_dict()['current_solver']==result.to_dict()['refined_current_solver']=={'fake':True}


@pytest.mark.parametrize('kind',['bracket','budget','target-refinement','mesh-change'])
def test_failed_acceptance_retains_original_stages_and_current(monkeypatch,kind):
    fake(monkeypatch,offset=.02 if kind=='mesh-change' else 1. if kind=='target-refinement' else 0.)
    target=2. if kind=='bracket' else .7 if kind=='budget' else 1.
    with pytest.raises(Error) as caught:
        seek(lambda x:factory(x*.0004),[1.,2.],target,quantity='impedance_real',
            tolerance=.1 if kind=='mesh-change' else 1e-10,max_evaluations=3 if kind=='budget' else 40)
    error=caught.value;assert error.attempts==len(error.history)==(2 if kind in ('bracket','budget') else 3)
    assert error.stage==dict(bracket='bracket',budget='budget',**{'target-refinement':'refinement/acceptance','mesh-change':'refinement/mesh-change'})[kind]
    if kind not in ('bracket','budget'):
        assert error.current_solver=={'fake':True} and Document.loads(error.input_json).corner_size==1.25e-6


@pytest.mark.parametrize('broken',['factory','type','extraction','diagnostic'])
def test_attempt_failures_keep_cause_and_corner_input(monkeypatch,broken):
    fake(monkeypatch,broken=broken)
    def make(x):
        if broken=='factory':raise ArithmeticError('factory failure')
        return original_factory(x*.0004) if broken=='type' else factory(x*.0004)
    with pytest.raises(Error) as caught:seek(make,[1.,2.],.7,quantity='impedance_real',tolerance=.01)
    error=caught.value;assert error.attempts==1 and not error.history and error.__cause__ is not None
    assert error.current_solver==({'fake':True} if broken=='diagnostic' else None)
    if broken in ('extraction','diagnostic'):assert Document.loads(error.input_json).corner_size==2.5e-6


@pytest.mark.parametrize('change',['frequency','names','length','grid','wrong-count'])
def test_nested_identity_is_checked_before_changed_fields(monkeypatch,change):
    calls=fake(monkeypatch)
    def make(x):
        raw=factory(x*.0004,'differential_forward_impedance_real' if change=='wrong-count' else 'impedance_real').to_dict();line=raw['line']
        if x==2 or change not in ('frequency','names'):
            if change=='frequency':line['frequency_hz']=[3e9]
            if change=='names':
                line['cross_section']['traces'][0]['name']='other';line['conductors']['other']=line['conductors'].pop('signal')
            if change=='length':line['length_m']=.01
            if change=='grid':line['frequency_hz']=[2e9,3e9]
        return Document.from_dict(raw)
    with pytest.raises(Error) as caught:seek(make,[1.,2.],.7,quantity='impedance_real',tolerance=.01)
    assert len(calls)==(1 if change in ('frequency','names') else 0)
    assert caught.value.stage=='search/validation'


@pytest.mark.parametrize('changes',[dict(bounds=[1.,1.]),dict(bounds=[0.,2.]),dict(target=-1.),dict(tolerance=0.),dict(quantity='invalid'),dict(max_evaluations=2)])
def test_bad_controls_precede_factory(changes):
    options=dict(bounds=[1.,2.],target=1.,quantity='impedance_real',tolerance=.01);options.update(changes)
    with pytest.raises(ValueError):seek(lambda x:pytest.fail('invalid controls reached factory'),**options)


def test_optional_controls_resolve_and_corner_halves_without_mesh(monkeypatch):
    from sipi import CrossSection
    from sipi.corner_fem_goal import _refine_corner
    raw=factory(.0004).to_dict();raw['line']['cross_section']['mesh']={'grade':.1}
    doc=Document.from_dict(raw);settings=doc.cross_section.section.mesh_settings(**doc.cross_section.mesh_options)
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('refinement input meshed'))
    refined=Document.from_dict(_refine_corner(raw));actual=refined.cross_section.mesh_options
    assert actual['min_angle']==settings['min_angle']
    for key in ('edge_size','far_size','grade','corner_size'):assert actual[key]==settings[key]/2


@pytest.fixture(scope='module',params=[('impedance_real',70.35,5e-6),('differential_forward_impedance_real',92.8,5e-6),
    ('impedance_real',70.35,2.5e-6),('differential_forward_impedance_real',92.8,2.5e-6)],ids=['scalar-default','pair-default','scalar-corner','pair-corner'])
def actual(request):
    quantity,target,corner=request.param
    result=seek(lambda w:factory(w,quantity,corner),[.00039,.00041],target,quantity=quantity,tolerance=.2,max_evaluations=12)
    return quantity,corner,result


def test_actual_goals_and_independent_characteristics(actual,record_property):
    quantity,corner,result=actual
    assert abs(result.residual)<=.2 and abs(result.refined_residual)<=.2
    assert abs(result.mesh_change)/result.refined_value<=.005
    assert result.document.corner_size==corner and result.refined_document.corner_size==corner/2
    assert result.history[-1].stage=='refinement' and result.history[-1].parameter==result.parameter
    for line,value in ((result.result,result.value),(result.refined_result,result.refined_value)):
        assert value==pytest.approx(independent(line,quantity),rel=1e-10,abs=0)
        assert len(line.current_factors.samples)==8*(len(line.names)+1)
    record_property('corner_fem_goal',json.dumps(dict(quantity=quantity,corner=corner,design=result.to_dict(),
        selected={k:getattr(result.result,k).tolist() for k in ('R','L','G','C')},
        refined={k:getattr(result.refined_result,k).tolist() for k in ('R','L','G','C')}),allow_nan=False))


def test_later_typed_failure_retains_full_corner_input(actual,monkeypatch):
    quantity,corner,result=actual;current=result.result.current_factors;calls=[]
    def analyze(doc):
        calls.append(doc.dumps())
        if len(calls)==1:return replace(result.result,input_json=doc.dumps())
        cause=FEMShapeCurrentError('retained partial',stage='capacitance-differences',base=current.base,
            extension_parts=current.extension_parts,samples=current.samples[:1],request=(0,0,0,1,current.step_m))
        raise FEMShapeLineError(cause,stage='current',input_json=doc.dumps(),factors=None,mesh_observation=result.result.mesh_observation)
    monkeypatch.setattr(Document,'analyze',analyze)
    with pytest.raises(Error) as caught:
        seek(lambda w:factory(w,quantity,corner),[.00039,.00041],result.target,quantity=quantity,tolerance=.2)
    error=caught.value;assert error.attempts==2 and len(error.history)==1
    assert error.input_json==calls[-1] and error.cause_details['input']==json.loads(calls[-1])
    assert len(error.cause_details['partial_current']['samples'])==1 and error.current_solver is None
    assert json.loads(json.dumps(error.to_dict(),allow_nan=False))==error.to_dict()


def test_interrupt_propagates(monkeypatch):
    def stop(doc):raise KeyboardInterrupt('cancelled')
    monkeypatch.setattr(Document,'analyze',stop)
    with pytest.raises(KeyboardInterrupt):seek(lambda x:factory(x*.0004),[1.,2.],1.,quantity='impedance_real',tolerance=.01)
