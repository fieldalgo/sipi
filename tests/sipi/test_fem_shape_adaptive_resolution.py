# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Controlled histories isolate budget, continuation and failure semantics."""
from types import SimpleNamespace
import numpy as np
import pytest
from sipi import CrossSection,refine_fem_shape_line_resolution
from sipi.line_resolution import ResolutionTolerance
from test_fem_shape_resolution import inputs,Document

TOLERANCES={'C':ResolutionTolerance(.01,0.)}


def controlled(monkeypatch,*,values=(1.,.995,.99,.985),fail=None,outer_mismatch=False):
    calls=[]
    def analyze(self):
        raw=self.to_dict();level=round(np.log2(.1/raw['cross_section']['mesh']['grade']))
        outer=raw['cross_section']['box']['width']>.008
        stage=('outer:'+str(0 if raw['cross_section']['box']['width']==.016 else 1)) if outer else ('base' if level==0 else 'mesh:'+str(level))
        calls.append((stage,self.dumps()))
        if stage==fail:raise ValueError('controlled field refusal')
        value=values[level]*(1.1 if outer and outer_mismatch else 1.)
        matrix=np.broadcast_to(np.eye(2)*value,(2,2,2)).copy()
        return SimpleNamespace(names=('positive','negative'),frequency=np.array([2e9,3e9]),C=matrix,
            R=np.zeros_like(matrix),G=np.zeros_like(matrix),conductor=None,
            dielectric=SimpleNamespace(C0=np.eye(2),L=np.eye(2)),current_record=lambda:{'controlled':True})
    monkeypatch.setattr(Document,'analyze',analyze);return calls


def run(**options):
    base,outer=inputs();return refine_fem_shape_line_resolution(base,outer_documents=outer,
        tolerances=TOLERANCES,**options)


def test_two_consecutive_passes_then_all_outer_inputs(monkeypatch):
    calls=controlled(monkeypatch);report=run(max_levels=2,max_solves=5)
    assert report.completed and report.accepted and report.outer_completed
    assert [s for s,_ in calls]==['base','mesh:1','mesh:2','outer:0','outer:1']
    assert report.selected_evaluation is report.evaluations[2]
    assert [c.reference_index for c in report.comparisons]==[0,1,2,2]
    assert report.evaluations[2].result is report.selected_evaluation.result
    assert all(row.result.C.shape==(2,2,2) for row in report.evaluations)
    for row in report.evaluations[2:]:
        import json
        assert json.loads(row.input_json)['cross_section']['mesh']['grade']==.025
    saved=report.to_dict();assert saved['selected_evaluation_index']==2
    assert all(row['current_solver']=={'controlled':True} for row in saved['evaluations'])


def test_one_pass_does_not_select_a_result_or_run_outer(monkeypatch):
    calls=controlled(monkeypatch,values=(1.,.995,.98))
    report=run(max_levels=2,max_solves=5)
    assert report.completed and not report.accepted and not report.outer_completed
    assert report.stop_reason=='mesh-unaccepted' and report.selected_evaluation is None
    assert len(calls)==3 and report.comparisons[0].accepted and not report.comparisons[1].accepted


def test_two_passes_must_be_consecutive(monkeypatch):
    calls=controlled(monkeypatch,values=(1.,.995,.98,.979))
    report=run(max_levels=3,max_solves=6)
    assert report.stop_reason=='mesh-unaccepted' and report.selected_evaluation is None
    assert [row.accepted for row in report.comparisons]==[True,False,True] and len(calls)==4


def test_reserve_outer_budget_before_next_mesh(monkeypatch):
    calls=controlled(monkeypatch,values=(1.,.98,.96))
    report=run(max_levels=4,max_solves=5)
    assert not report.completed and not report.accepted and report.stop_reason=='budget-exhausted'
    assert len(calls)==3 and report.mesh_levels==2 and report.selected_evaluation is None


def test_outer_disagreement_stops_without_changing_physical_domain(monkeypatch):
    calls=controlled(monkeypatch,outer_mismatch=True);report=run(max_levels=4,max_solves=8)
    assert report.completed and not report.accepted and report.outer_completed
    assert report.stop_reason=='outer-unaccepted' and report.selected_evaluation is None and len(calls)==5


@pytest.mark.parametrize('stage',['base','mesh:1','mesh:2','outer:0','outer:1'])
def test_field_failures_keep_exact_attempt_and_prior_work(monkeypatch,stage):
    calls=controlled(monkeypatch,fail=stage);report=run(max_levels=2,max_solves=5)
    assert report.stop_reason=='field-failed' and not report.completed and report.selected_evaluation is None
    assert report.failure.stage==stage and report.failure.input_json==calls[-1][1]
    assert report.failure.kind=='ValueError' and report.failure.details is None
    assert len(report.evaluations)==len(calls)-1 and report.to_dict()['failure']['details'] is None


@pytest.mark.parametrize('options',[dict(max_levels=1),dict(max_levels=True),dict(max_solves=4),dict(max_solves=True),dict(refinement_factor=1.)])
def test_admission_before_field_work(monkeypatch,options):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**kw:pytest.fail('preflight reached mesh'))
    with pytest.raises((TypeError,ValueError)):run(**options)


def test_later_setup_failure_keeps_unprepared_input(monkeypatch):
    calls=controlled(monkeypatch);original=Document.from_dict
    def from_dict(cls,raw):
        if raw['cross_section']['mesh'].get('grade',1.)<.05:raise ValueError('controlled setup refusal')
        return original(raw)
    monkeypatch.setattr(Document,'from_dict',classmethod(from_dict))
    report=run(max_levels=2,max_solves=5)
    assert report.stop_reason=='field-failed' and report.failure.stage=='mesh:2'
    assert len(calls)==2 and len(report.evaluations)==2
    assert '0.025' in report.failure.input_json


def test_interrupt_propagates(monkeypatch):
    def stop(self):raise KeyboardInterrupt('cancelled')
    monkeypatch.setattr(Document,'analyze',stop)
    with pytest.raises(KeyboardInterrupt):run()
