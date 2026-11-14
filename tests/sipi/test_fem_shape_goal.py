# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit FEM goal control, frozen input and complete failure accounting."""
import json
from types import SimpleNamespace
import numpy as np
import pytest
from sipi.fem_shape_line import FEMShapeTransmissionLineDocument as Document
from sipi.fem_shape_goal import seek_fem_shape_line_quantity as seek,FEMShapeLineQuantityGoalError as Error
from sipi.fem_shape_study import _line
from test_fem_shape_study import document as study, MESH


def factory(width,quantity='impedance_real'):
    data=study(quantity).to_dict();source=data['study'];parameters=dict(source['parameters'],width=width)
    return _line(source,parameters,source['material_evaluation'],data)


def fake(monkeypatch,*,offset=0.,metric=None,broken=None):
    calls=[]
    def analyze(doc):
        raw=doc.to_dict();calls.append(raw)
        if broken=='extraction':raise ArithmeticError('field failure')
        names=tuple(t.name for t in doc.cross_section.section.traces if not t.ground);f=np.array(raw['frequency_hz'])
        x=doc.cross_section.section.traces[0].width/.0004
        value=(1/x if metric is None else metric(x))+(offset if doc.cross_section.mesh_options['grade']==MESH['grade']/2 else 0.)
        def propagation():
            if broken=='diagnostic':raise ArithmeticError('diagnostic failure')
            return SimpleNamespace(modes=('single',),frequency=f,z_characteristic=np.array([[value+1j]]),gamma=np.array([[value+2j]]))
        return SimpleNamespace(names=names,frequency=f,input_json=doc.dumps(),current_record=lambda:dict(fake=True),propagation=propagation,
            characteristic=lambda:SimpleNamespace(basis='single-ended',names=names,frequency=f,
                mixed_mode=lambda:SimpleNamespace(z_characteristic=np.array([[[value+1j,2j],[2j,value+1j]]]))))
    monkeypatch.setattr(Document,'analyze',analyze);return calls


@pytest.mark.parametrize('quantity',['impedance_real','attenuation','differential_forward_impedance_real','common_forward_impedance_real'])
def test_all_quantities_use_frozen_chosen_input_and_one_reserved_attempt(monkeypatch,quantity):
    fields=fake(monkeypatch);calls=[]
    def make(x):calls.append(x);return factory(x*.0004,quantity)
    result=seek(make,[1.,2.],.7,quantity=quantity,tolerance=1e-6)
    assert result.parameter==pytest.approx(10/7,abs=3e-6)
    assert len(fields)==len(result.history)==len(calls)+1
    raw=result.document.to_dict();settings=result.document.cross_section.section.mesh_settings(**result.document.cross_section.mesh_options)
    for key in ('edge_size','far_size','grade'):settings[key]/=2
    raw['cross_section']['mesh']=settings;assert raw==result.refined_document.to_dict()
    saved=result.to_dict();assert saved['current_solver']==saved['refined_current_solver']=={'fake':True}
    assert json.loads(json.dumps(saved,allow_nan=False))==saved


@pytest.mark.parametrize('quantity,target',[('impedance_real',1.),('attenuation',0.)])
def test_endpoint_and_zero_attenuation_use_minimum_budget(monkeypatch,quantity,target):
    fake(monkeypatch,metric=lambda x:target/x)
    result=seek(lambda x:factory(x*.0004),[1.,2.],target,quantity=quantity,tolerance=1e-10,max_evaluations=3)
    assert result.parameter==1. and len(result.history)==3


@pytest.mark.parametrize('kind',['bracket','budget','target-refinement','mesh-change'])
def test_failed_acceptance_retains_all_attempts_and_refined_current(monkeypatch,kind):
    fake(monkeypatch,offset=.02 if kind=='mesh-change' else 1. if kind=='target-refinement' else 0.)
    target=2. if kind=='bracket' else .7 if kind=='budget' else 1.
    with pytest.raises(Error) as caught:
        seek(lambda x:factory(x*.0004),[1.,2.],target,quantity='impedance_real',
            tolerance=.1 if kind=='mesh-change' else 1e-10,max_evaluations=3 if kind=='budget' else 40)
    error=caught.value;assert error.attempts==len(error.history)==(2 if kind in ('bracket','budget') else 3)
    assert error.stage==dict(bracket='bracket',budget='budget',**{'target-refinement':'refinement/acceptance','mesh-change':'refinement/mesh-change'})[kind]
    assert error.current_solver==(None if kind in ('bracket','budget') else {'fake':True})
    assert json.loads(json.dumps(error.to_dict(),allow_nan=False))==error.to_dict()


@pytest.mark.parametrize('broken',['factory','type','extraction','diagnostic'])
def test_attempt_failures_keep_original_cause_and_complete_diagnostic_current(monkeypatch,broken):
    fake(monkeypatch,broken=broken)
    def make(x):
        if broken=='factory':raise ArithmeticError('factory failure')
        return None if broken=='type' else factory(x*.0004)
    with pytest.raises(Error) as caught:seek(make,[1.,2.],.7,quantity='impedance_real',tolerance=.01)
    error=caught.value;assert error.attempts==1 and not error.history and error.__cause__ is not None
    assert error.current_solver==({'fake':True} if broken=='diagnostic' else None)
    assert (error.input_json is not None)==(broken in ('extraction','diagnostic'))


@pytest.mark.parametrize('change',['frequency','names','length','grid','wrong-count'])
def test_invalid_or_changed_identity_never_runs_its_fields(monkeypatch,change):
    calls=fake(monkeypatch)
    def make(x):
        raw=factory(x*.0004,'differential_forward_impedance_real' if change=='wrong-count' else 'impedance_real').to_dict()
        if x==2 or change not in ('frequency','names'):
            if change=='frequency':raw['frequency_hz']=[3e9]
            if change=='names':
                raw['cross_section']['traces'][0]['name']='other';raw['conductors']['other']=raw['conductors'].pop('signal')
            if change=='length':raw['length_m']=.01
            if change=='grid':raw['frequency_hz']=[2e9,3e9]
        return Document.from_dict(raw)
    with pytest.raises(Error) as caught:seek(make,[1.,2.],.7,quantity='impedance_real',tolerance=.01)
    assert len(calls)==(1 if change in ('frequency','names') else 0)
    assert caught.value.stage=='search/validation'


@pytest.mark.parametrize('changes',[dict(bounds=[1.,1.]),dict(bounds=[0.,2.]),dict(target=-1.),dict(tolerance=0.),dict(quantity='invalid'),dict(max_evaluations=2)])
def test_invalid_controls_do_not_invoke_factory(changes):
    options=dict(bounds=[1.,2.],target=1.,quantity='impedance_real',tolerance=.01);options.update(changes)
    with pytest.raises(ValueError):seek(lambda x:pytest.fail('invalid controls reached factory'),**options)


def test_optional_mesh_settings_are_resolved_before_halving_without_meshing(monkeypatch):
    from sipi.fem_shape_goal import _refine
    from sipi import CrossSection
    raw=factory(.0004).to_dict();raw['cross_section']['mesh']={'grade':.1}
    doc=Document.from_dict(raw);resolved=doc.cross_section.section.mesh_settings(**doc.cross_section.mesh_options)
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('refinement input meshed'))
    refined=_refine(raw);actual=refined['cross_section']['mesh']
    assert actual['min_angle']==resolved['min_angle']
    for key in ('edge_size','far_size','grade'):assert actual[key]==resolved[key]/2


def test_cancellation_propagates(monkeypatch):
    def stop(doc):raise KeyboardInterrupt('cancelled')
    monkeypatch.setattr(Document,'analyze',stop)
    with pytest.raises(KeyboardInterrupt):seek(lambda x:factory(x*.0004),[1.,2.],1.,quantity='impedance_real',tolerance=.01)
