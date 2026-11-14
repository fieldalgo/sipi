# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Actual three-mesh history retains the unresolved mutual-loss differences."""
import json
import pytest
from sipi import refine_fem_shape_line_resolution
from sipi.fem_shape_line import FEMShapeLineError
from sipi.fem_shape_conductor import FEMShapeCurrentError
from test_fem_shape_resolution import inputs,TOLERANCES,Document
from test_fem_shape_line_physical import independent


@pytest.fixture(scope='module')
def observed():
    base,outer=inputs()
    return base,outer,refine_fem_shape_line_resolution(base,outer_documents=outer,
        tolerances=TOLERANCES,max_levels=2,max_solves=5)


def test_actual_three_meshes_remain_unaccepted_with_independent_line_identities(observed,record_property):
    base,outer,result=observed
    record_property('fem_adaptive_resolution',json.dumps(result.to_dict(),allow_nan=False))
    assert result.completed and not result.accepted and result.stop_reason=='mesh-unaccepted'
    assert result.selected_evaluation is None and not result.outer_completed and result.failure is None
    assert [r.stage for r in result.evaluations]==['base','mesh:1','mesh:2']
    assert [r.reference_index for r in result.comparisons]==[0,1]
    assert all(not row.accepted for row in result.comparisons)
    errors=[independent(row.result) for row in result.evaluations]
    record_property('fem_adaptive_network_errors',json.dumps(errors,allow_nan=False))
    assert result.to_dict()['selected_evaluation_index'] is None


@pytest.mark.parametrize('partial',[False,True])
def test_replayed_typed_failure_preserves_original_current_evidence(observed,monkeypatch,partial):
    base,outer,result=observed;values={row.input_json:row.result for row in result.evaluations}
    failed=result.evaluations[2];cur=failed.result.current_factors
    cause=FEMShapeCurrentError('original partial',stage='capacitance-differences',base=cur.base,
        extension_parts=cur.extension_parts,samples=cur.samples[:1],request=(0,0,0,1,cur.step_m)) if partial else ValueError('original later failure')
    error=FEMShapeLineError(cause,stage='current' if partial else 'dielectric',input_json=failed.input_json,
        factors=None if partial else cur,mesh_observation=failed.result.mesh_observation)
    calls=[]
    def analyze(self):
        calls.append(self.dumps())
        if self.dumps()==failed.input_json:raise error
        return values[self.dumps()]
    monkeypatch.setattr(Document,'analyze',analyze)
    actual=refine_fem_shape_line_resolution(base,outer_documents=outer,tolerances=TOLERANCES,max_levels=2,max_solves=5)
    assert actual.stop_reason=='field-failed' and len(calls)==3 and len(actual.evaluations)==2
    assert actual.selected_evaluation is None and actual.failure.stage=='mesh:2'
    assert actual.failure.details==error.to_dict()==actual.to_dict()['failure']['details']
    if partial:assert len(actual.failure.details['partial_current']['samples'])==1
    else:assert actual.failure.details['current_solver']==failed.result.current_record()
