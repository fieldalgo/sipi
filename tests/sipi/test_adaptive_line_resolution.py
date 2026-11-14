# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Bounded refinement keeps every rejected level and checks domains separately."""
from types import SimpleNamespace
import json
import numpy as np
import pytest

from sipi import CrossSection
from sipi.line_model import TransmissionLineDocument
from sipi.line_resolution import ResolutionTolerance
from sipi.adaptive_line_resolution import refine_line_resolution
from sipi.constants import epsilon_0, mu_0
from test_line_resolution import inputs, TOLERANCES


@pytest.fixture(scope='module')
def observed():
    base,outers=inputs()
    result=refine_line_resolution(base,outer_documents=outers,tolerances=TOLERANCES)
    return base,outers,result


def test_real_fields_need_two_mesh_passes_and_separate_outer_checks(observed,record_property):
    base,outers,result=observed
    assert result.completed and result.accepted and result.outer_completed
    assert result.stop_reason=='accepted' and result.failure is None and result.mesh_levels==2
    assert result.selected_evaluation is result.evaluations[2]
    assert json.loads(result.selected_evaluation.input_json)['cross_section']['box']['width']==.008
    assert [r.stage for r in result.evaluations]==['base','mesh:1','mesh:2','outer:0','outer:1']
    assert [r.reference_index for r in result.comparisons]==[0,1,2,2]
    assert result.evaluations[0].input_json==base.dumps()
    for row in result.evaluations:
        actual=row.result
        np.testing.assert_allclose(actual.C,4*np.broadcast_to(actual.dielectric.C0,actual.C.shape),rtol=1e-12)
        np.testing.assert_allclose(actual.L@actual.C,4*mu_0*epsilon_0*np.ones_like(actual.C),rtol=1e-10)
    for index,outer in enumerate(outers):
        expected=outer.to_dict()
        expected['cross_section']['mesh']=json.loads(result.evaluations[2].input_json)['cross_section']['mesh']
        assert json.loads(result.evaluations[index+3].input_json)==expected
    rows=[dict(stage=r.stage,maximum_fraction=max(float(r.differences[k].max()/r.allowances[k].max())
                for k in r.differences)) for r in result.comparisons]
    record_property('adaptive_resolution_allowance_fractions',json.dumps(rows))
    with pytest.raises(TypeError): result.tolerances['C']=ResolutionTolerance(1.,0.)


def cached(monkeypatch,result):
    values={row.input_json:row.result for row in result.evaluations};calls=[]
    def analyze(self):calls.append(self.dumps());return values[self.dumps()]
    monkeypatch.setattr(TransmissionLineDocument,'analyze',analyze)
    return calls


def test_level_limit_keeps_unaccepted_meshes_without_outer_solves(observed,monkeypatch):
    base,outers,previous=observed;calls=cached(monkeypatch,previous)
    result=refine_line_resolution(base,outer_documents=outers,max_levels=2,
        tolerances={'C':ResolutionTolerance(0.,0.)})
    assert result.completed and not result.accepted and not result.outer_completed
    assert result.stop_reason=='mesh-unaccepted' and result.mesh_levels==2
    assert result.selected_evaluation is None
    assert len(calls)==len(result.evaluations)==3 and len(result.comparisons)==2
    assert all(not row.accepted for row in result.comparisons)


def test_reserve_outer_budget_before_attempting_another_mesh(observed,monkeypatch):
    base,outers,previous=observed;calls=cached(monkeypatch,previous)
    result=refine_line_resolution(base,outer_documents=outers,max_levels=4,max_solves=5,
        tolerances={'C':ResolutionTolerance(0.,0.)})
    assert not result.completed and not result.accepted and not result.outer_completed
    assert result.stop_reason=='budget-exhausted' and result.failure is None
    assert result.selected_evaluation is None
    assert result.mesh_levels==2 and len(calls)==3


def synthetic(monkeypatch,values,*,outer_value=None):
    # Controlled positive capacitances exercise the state machine, not field accuracy.
    calls=[]
    grades=[.1*.5**n for n in range(len(values))]
    def analyze(self):
        data=self.to_dict();calls.append(data)
        level=grades.index(data['cross_section']['mesh']['grade'])
        value=values[level]
        if data['cross_section']['box']['width']>.008 and outer_value is not None:value=outer_value
        return SimpleNamespace(names=('signal',),frequency=np.array([1e9,2e9]),C=np.full((2,1,1),value*1e-10))
    monkeypatch.setattr(TransmissionLineDocument,'analyze',analyze)
    return calls


def test_failed_middle_level_resets_consecutive_agreement(monkeypatch):
    base,outers=inputs();calls=synthetic(monkeypatch,[1.,1.001,1.101,1.102,1.103])
    result=refine_line_resolution(base,outer_documents=outers,max_levels=4,max_solves=8,
        tolerances={'C':ResolutionTolerance(.01,0.)})
    assert result.accepted and result.mesh_levels==4 and len(calls)==7
    assert [r.accepted for r in result.comparisons[:4]]==[True,False,True,True]
    assert [r.reference_index for r in result.comparisons[-2:]]==[4,4]


def test_outer_mismatch_stops_without_blind_further_refinement(monkeypatch):
    base,outers=inputs();calls=synthetic(monkeypatch,[1.,1.001,1.002],outer_value=2.)
    result=refine_line_resolution(base,outer_documents=outers,max_levels=8,max_solves=12,
        tolerances={'C':ResolutionTolerance(.01,0.)})
    assert result.completed and result.outer_completed and not result.accepted
    assert result.stop_reason=='outer-unaccepted' and result.mesh_levels==2 and len(calls)==5
    assert result.selected_evaluation is None


@pytest.mark.parametrize('stage',['base','mesh:1','mesh:2','outer:0','outer:1'])
def test_each_failure_keeps_completed_history_and_stops(observed,monkeypatch,stage):
    base,outers,previous=observed;values={r.input_json:r.result for r in previous.evaluations};calls=[]
    text=next(r.input_json for r in previous.evaluations if r.stage==stage)
    def analyze(self):
        calls.append(self.dumps())
        if self.dumps()==text:raise ValueError('retained adaptive field refusal')
        return values[self.dumps()]
    monkeypatch.setattr(TransmissionLineDocument,'analyze',analyze)
    result=refine_line_resolution(base,outer_documents=outers,tolerances=TOLERANCES)
    index=[r.stage for r in previous.evaluations].index(stage)
    assert not result.completed and not result.accepted and result.stop_reason=='field-failed'
    assert len(result.evaluations)==index and len(calls)==index+1
    assert result.failure.stage==stage and result.failure.input_json==text
    assert result.failure.kind=='ValueError' and result.failure.message=='retained adaptive field refusal'


@pytest.mark.parametrize('options',[dict(max_levels=1),dict(max_levels=9),dict(max_levels=True),
    dict(max_solves=4),dict(max_solves=17),dict(max_solves=True),dict(refinement_factor=1.),dict(refinement_factor=0.)])
def test_controls_precede_all_field_work(options,monkeypatch):
    base,outers=inputs()
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('invalid controls meshed'))
    with pytest.raises((ValueError,TypeError)):
        refine_line_resolution(base,outer_documents=outers,tolerances=TOLERANCES,**options)


def test_user_interrupt_is_not_converted_to_a_result(monkeypatch):
    base,outers=inputs()
    def interrupt(self):raise KeyboardInterrupt()
    monkeypatch.setattr(TransmissionLineDocument,'analyze',interrupt)
    with pytest.raises(KeyboardInterrupt):
        refine_line_resolution(base,outer_documents=outers,tolerances=TOLERANCES)
