# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Actual four-input FEM extraction and independent uniform-line identities."""
import json
import numpy as np
import pytest
from sipi import assess_fem_shape_line_resolution
from sipi.line_resolution import ResolutionTolerance
from sipi.fem_shape_line import FEMShapeLineError
from test_fem_shape_resolution import inputs,TOLERANCES,Document
from test_fem_shape_line_physical import independent
from test_fem_shape_loss_physical import snapshot


@pytest.fixture(scope='module')
def observed():
    base,outer=inputs()
    return base,outer,assess_fem_shape_line_resolution(base,outer_documents=outer,tolerances=TOLERANCES)


def test_actual_mesh_disagreement_outer_agreement_and_independent_identities(observed,record_property):
    base,outer,report=observed
    record_property('fem_resolution',json.dumps(report.to_dict(),allow_nan=False))
    assert report.completed and not report.accepted and report.failure is None
    assert not report.comparisons[0].accepted
    assert all(row.accepted for row in report.comparisons[1:])
    for key in ('R','L_internal'):
        assert np.any(report.comparisons[0].differences[key]>report.comparisons[0].allowances[key])
    for key in ('C','G','C0','L_external'):
        assert np.all(report.comparisons[0].differences[key]<=report.comparisons[0].allowances[key])
    assert len(report.evaluations)==4 and len(report.comparisons)==3
    assert [r.reference_index for r in report.comparisons]==[0,1,1]
    rows=[]
    for row in report.evaluations:
        result=row.result
        rows.append(dict(input=json.loads(row.input_json),loss=snapshot(result.conductor),current=result.current_record(),network_errors=independent(result)))
    record_property('fem_resolution_lines',json.dumps(rows,allow_nan=False))
    assert report.evaluations[0].input_json==base.dumps()
    assert [r.input_json for r in report.evaluations[2:]]==[d.dumps() for d in outer]
    assert all(np.all(r.differences['G']==0) and np.all(r.allowances['G']==0) for r in report.comparisons)
    assert all(r.differences[k].shape==(2,2,2) for r in report.comparisons for k in TOLERANCES)
    copied=report.to_dict();copied['evaluations'][0]['current_solver'].clear()
    assert report.to_dict()['evaluations'][0]['current_solver']
    with pytest.raises(ValueError):report.comparisons[0].differences['R'][0,0,0]=0
    with pytest.raises(TypeError):report.tolerances['R']=ResolutionTolerance(0,0)


def replay(monkeypatch,report):
    values={r.input_json:r.result for r in report.evaluations}
    monkeypatch.setattr(Document,'analyze',lambda self:values[self.dumps()])


def test_completed_exact_disagreement_is_retained(observed,monkeypatch):
    base,outer,original=observed;replay(monkeypatch,original)
    report=assess_fem_shape_line_resolution(base,outer_documents=outer,tolerances={'R':ResolutionTolerance(0,0)})
    assert report.completed and not report.accepted and report.failure is None
    assert report.comparisons[0].differences['R'].max()>0
    assert all(np.all(r.allowances['R']==0) for r in report.comparisons)


@pytest.mark.parametrize('stage',['base','mesh','outer:0','outer:1'])
@pytest.mark.parametrize('typed',[False,True])
def test_failure_keeps_exact_stage_input_and_partial_current(observed,monkeypatch,stage,typed):
    base,outer,original=observed;calls=[];values={r.input_json:r.result for r in original.evaluations}
    failing=next(r for r in original.evaluations if r.stage==stage)
    error=FEMShapeLineError(ValueError('retained refusal'),stage='dielectric',input_json=failing.input_json,factors=failing.result.current_factors,mesh_observation=failing.result.mesh_observation) if typed else ValueError('retained refusal')
    def analyze(self):
        calls.append(self.dumps())
        if self.dumps()==failing.input_json:raise error
        return values[self.dumps()]
    monkeypatch.setattr(Document,'analyze',analyze)
    report=assess_fem_shape_line_resolution(base,outer_documents=outer,tolerances=TOLERANCES)
    index=[r.stage for r in original.evaluations].index(stage)
    assert len(calls)==index+1 and len(report.evaluations)==index
    assert not report.completed and not report.accepted
    assert report.failure.stage==stage and report.failure.input_json==failing.input_json
    assert report.failure.details==(error.to_dict() if typed else None)
    saved=report.to_dict();assert saved['failure']['details']==report.failure.details
    if typed:
        report.failure.details.clear();assert report.failure.details==error.to_dict()
