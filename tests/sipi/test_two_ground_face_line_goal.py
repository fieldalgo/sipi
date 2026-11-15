# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Bounded scalar/paired quantities and three independently required refinements."""
import json
from dataclasses import replace
import numpy as np
import pytest
from sipi.two_ground_face_line_goal import seek_two_ground_face_line_quantity as seek,TwoGroundFaceLineQuantityGoalError as GoalError
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument as Line
from sipi.two_ground_face_input import _line_from_inputs
from test_two_ground_face_line_study import document,synthetic,QUANTITIES


def factory(quantity='impedance_real',physical=False):
    data=document(quantity,physical=physical).to_dict()
    if physical:data['panel']['panels_per_edge']=128
    def build(width):
        parameters=dict(data['study']['parameters'],width=width)
        return _line_from_inputs(data,parameters,data['study']['material_evaluation'])
    return build


def target(quantity):return .4 if quantity=='attenuation' else 10. if quantity=='common_forward_impedance_real' else 40.


@pytest.mark.parametrize('quantity',QUANTITIES)
def test_independent_linear_quantity_root_and_three_frozen_axes(monkeypatch,quantity):
    calls=synthetic(monkeypatch);made=[];original=factory(quantity)
    def build(width):made.append(width);return original(width)
    goal=seek(build,[.0003,.0005],target(quantity),quantity=quantity,tolerance=1e-8,max_evaluations=6)
    assert goal.parameter==pytest.approx(.0004,rel=0,abs=1e-18)
    assert len(made)==3 and len(calls)==len(goal.history)==6
    assert [row.evaluation.stage for row in goal.refinements]==['joint-refinement','volume-refinement','panel-refinement']
    assert [row.stage for row in goal.history[-3:]]==['joint-refinement','volume-refinement','panel-refinement']
    for item in goal.refinements:
        expected=goal.document.to_dict();stage=item.evaluation.stage
        if stage!='panel-refinement':
            for name in ('edge_size','far_size','grade'):expected['cross_section']['mesh'][name]/=2
        if stage!='volume-refinement':expected['panel']['panels_per_edge']*=2
        assert item.document.to_dict()==expected
        assert item.evaluation.value==pytest.approx(goal.target,abs=1e-8)
    saved=goal.to_dict();assert saved['current_solver'] and saved['dielectric_mesh'] and len(saved['refinements'])==3


@pytest.mark.parametrize('at',range(1,7))
def test_every_failed_attempt_preserves_history_and_typed_cause(monkeypatch,at):
    calls=synthetic(monkeypatch,fail_at=at)
    with pytest.raises(GoalError) as caught:seek(factory(),[.0003,.0005],40.,quantity='impedance_real',tolerance=1e-8,max_evaluations=6)
    e=caught.value;assert e.attempts==len(calls)==at and len(e.history)==at-1
    assert e.to_dict()['cause_details']['cause_type']=='ArithmeticError'
    assert e.to_dict()['cause_details']['input']==json.loads(calls[-1])


@pytest.mark.parametrize('at',[1,4,5,6])
def test_interrupt_propagates_in_search_and_all_refinements(monkeypatch,at):
    calls=synthetic(monkeypatch,fail_at=at,interrupt=True)
    with pytest.raises(KeyboardInterrupt):seek(factory(),[.0003,.0005],40.,quantity='impedance_real',tolerance=1e-8,max_evaluations=6)
    assert len(calls)==at


def test_reserved_budget_cannot_be_used_by_search(monkeypatch):
    calls=synthetic(monkeypatch)
    with pytest.raises(GoalError,match='budget') as e:seek(factory(),[.0003,.0005],40.,quantity='impedance_real',tolerance=1e-8,max_evaluations=5)
    assert e.value.attempts==len(calls)==2
    calls.clear();goal=seek(factory(),[.0003,.0005],30.,quantity='impedance_real',tolerance=1e-8,max_evaluations=5)
    assert len(calls)==len(goal.history)==5


@pytest.mark.parametrize('change',[dict(max_evaluations=4),dict(max_evaluations=True),dict(max_evaluations=10001),dict(quantity='z_diff'),dict(target=float('nan')),dict(tolerance=0),dict(bounds=[.0005,.0003])])
def test_control_errors_precede_factory(monkeypatch,change):
    args=dict(bounds=[.0003,.0005],target=40.,quantity='impedance_real',tolerance=.1);args.update(change)
    with pytest.raises((ValueError,TypeError)):seek(lambda *a:pytest.fail('invalid control reached factory'),**args)
    with pytest.raises(TypeError):seek(None,[.0003,.0005],40.,quantity='impedance_real',tolerance=.1)


def test_unrefinable_panel_count_refused_before_fields(monkeypatch):
    calls=synthetic(monkeypatch);original=factory()
    def invalid(w):
        raw=original(w).to_dict();raw['panel']['panels_per_edge']=256;return Line.from_dict(raw)
    with pytest.raises(GoalError) as e:seek(invalid,[.0003,.0005],40.,quantity='impedance_real',tolerance=.1)
    assert e.value.attempts==1 and not calls


def test_panel_controls_cannot_drift(monkeypatch):
    calls=synthetic(monkeypatch);original=factory();seen=[]
    def drift(w):
        seen.append(w);raw=original(w).to_dict()
        if len(seen)>1:raw['panel']['ground_modes']*=2
        return Line.from_dict(raw)
    with pytest.raises(GoalError,match='remain fixed') as e:seek(drift,[.0003,.0005],40.,quantity='impedance_real',tolerance=.1)
    assert e.value.attempts==2 and len(calls)==1


@pytest.mark.parametrize('at,delta,expected',[(4,1.,'refinement/acceptance'),(5,1.,'volume-refinement/target'),(6,1.,'panel-refinement/target'),(4,.3,'joint-refinement/convergence'),(5,.3,'volume-refinement/convergence'),(6,.3,'panel-refinement/convergence')])
def test_each_refinement_has_original_target_and_relative_gate(monkeypatch,at,delta,expected):
    calls=synthetic(monkeypatch);original=Line.analyze
    def shifted(self):
        line=original(self)
        if len(calls)==at:
            p=line.propagation();p.z_characteristic+=delta;line.propagation=lambda:p
        return line
    monkeypatch.setattr(Line,'analyze',shifted)
    tol=.1 if delta==1 else .5
    with pytest.raises(GoalError) as e:seek(factory(),[.0003,.0005],40.,quantity='impedance_real',tolerance=tol,max_evaluations=6)
    assert e.value.stage==expected and e.value.to_dict()['current_solver'] and e.value.to_dict()['dielectric_mesh']


def test_joint_must_agree_with_each_single_axis_not_only_nominal(monkeypatch):
    calls=synthetic(monkeypatch);original=Line.analyze
    def shifted(self):
        line=original(self);change={4:.16,5:-.16}.get(len(calls),0.)
        p=line.propagation();p.z_characteristic+=change;line.propagation=lambda:p;return line
    monkeypatch.setattr(Line,'analyze',shifted)
    with pytest.raises(GoalError) as e:seek(factory(),[.0003,.0005],40.,quantity='impedance_real',tolerance=.2,max_evaluations=6)
    assert e.value.stage=='volume-refinement/joint-check/convergence'


def test_lossless_zero_attenuation_refinement_is_well_defined(monkeypatch):
    calls=synthetic(monkeypatch);original=Line.analyze
    def lossless(self):
        line=original(self);p=line.propagation();p.gamma[:]=2j;line.propagation=lambda:p;return line
    monkeypatch.setattr(Line,'analyze',lossless)
    result=seek(factory('attenuation'),[.0003,.0005],0.,quantity='attenuation',tolerance=1e-8,max_evaluations=5)
    assert result.value==result.refined_value==0 and len(calls)==5


def test_actual_registered_scalar_target_and_independent_complex_fields(record_property):
    result=seek(factory(physical=True),[.00055,.00065],58.,quantity='impedance_real',tolerance=.05,max_evaluations=40)
    record_property('two_ground_face_scalar_goal',json.dumps(result.to_dict(),sort_keys=True))
    assert abs(result.value-58.)<=.05 and len(result.history)<=40
    for line in [result.result,*[x.result for x in result.refinements]]:
        omega=2*np.pi*line.frequency[0];z=line.R[0,0,0]+1j*omega*line.L[0,0,0];y=line.G[0,0,0]+1j*omega*line.C[0,0,0]
        np.testing.assert_allclose(line.propagation().z_characteristic[0,0],np.sqrt(z/y),rtol=1e-12,atol=0)
        np.testing.assert_allclose(line.propagation().gamma[0,0],np.sqrt(z*y),rtol=1e-12,atol=0)
    assert all(abs(row.evaluation.value-58.)<=.05 for row in result.refinements)
