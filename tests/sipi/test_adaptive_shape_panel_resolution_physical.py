# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Real finite-plan observations; independent metal/network identities and rejection."""
import json
import numpy as np
import pytest
from sipi.constants import epsilon_0,mu_0
from sipi.line_resolution import ResolutionTolerance
from sipi.shape_panel_line import ShapePanelTransmissionLineDocument
from sipi.adaptive_shape_panel_resolution import refine_shape_panel_line_resolution
from test_adaptive_shape_panel_resolution import inputs,TOLERANCES
from test_shape_panel_pair_goal_physical import independent,snapshot
from test_layered_metal import transfer


@pytest.fixture(scope='module',params=[False,True],ids=['bulk','coated'])
def observed(request):
    doc,steps=inputs(request.param)
    result=refine_shape_panel_line_resolution(doc,refinements=steps,tolerances=TOLERANCES,max_solves=8)
    return request.param,doc,steps,result


def test_actual_two_levels_and_independent_fields(observed,record_property):
    coated,doc,steps,result=observed
    record_property('adaptive_shape_observation',json.dumps(result.to_dict(),allow_nan=False))
    assert result.accepted and result.completed and result.outer_completed and result.failure is None
    assert result.refinement_levels==2 and result.selected_evaluation is result.evaluations[6]
    assert [r.stage for r in result.evaluations]==['base','level:1:volume','level:1:panel',
        'level:1:joint','level:2:volume','level:2:panel','level:2:joint','outer:0']
    assert [(r.reference_index,r.evaluation_index) for r in result.comparisons]==[
        (0,1),(0,2),(1,3),(2,3),(3,4),(3,5),(4,6),(5,6),(6,7)]
    assert len({r.input_json for r in result.evaluations})==8
    assert result.evaluations[-1].input_json==steps[-1].outer_documents[0].dumps()
    references=[]
    for row in result.evaluations:
        line=row.result;f=line.frequency;factors=line.current_factors
        np.testing.assert_allclose(line.C,4.2*np.broadcast_to(factors.C0,line.C.shape),atol=0,rtol=1e-12)
        np.testing.assert_allclose(line.G,2*np.pi*f[:,None,None]*.02*line.C,atol=0,rtol=1e-12)
        np.testing.assert_allclose(line.dielectric.L@factors.C0,epsilon_0*mu_0*np.eye(2),atol=1e-28,rtol=1e-10)
        expected=np.zeros_like(line.R,dtype=complex)
        for b,sigma in enumerate((58e6,35e6,45e6)):
            z=np.array([transfer(x) for x in f]) if coated else np.sqrt(2j*np.pi*f*mu_0/sigma)
            expected+=z[:,None,None]*factors.parts[b]
        np.testing.assert_allclose(line.R+2j*np.pi*f[:,None,None]*line.conductor.L_internal,expected,rtol=1e-10,atol=0)
        references.append(independent(line))
        assert json.loads(row.input_json)['step_fraction']==doc.to_dict()['step_fraction']
        assert len(factors.samples)==13
    for a,b in ((0,1),(2,3),(3,4),(5,6)):
        np.testing.assert_array_equal(result.evaluations[a].result.R,result.evaluations[b].result.R)
        np.testing.assert_array_equal(result.evaluations[a].result.current_factors.parts,result.evaluations[b].result.current_factors.parts)
    record_property('adaptive_shape_fields',json.dumps([snapshot(r.result) for r in result.evaluations],allow_nan=False))
    record_property('adaptive_shape_independent',json.dumps(references))


def test_same_fields_preserve_small_mutual_outer_rejection(observed,monkeypatch,record_property):
    _,doc,steps,observed_result=observed
    fields={r.input_json:r.result for r in observed_result.evaluations};calls=[]
    def replay(self):calls.append(self.dumps());return fields[self.dumps()]
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',replay)
    result=refine_shape_panel_line_resolution(doc,refinements=steps,
        tolerances={'R':ResolutionTolerance(.005,0.)},max_solves=8)
    record_property('adaptive_shape_rejection',json.dumps(result.to_dict(),allow_nan=False))
    assert result.completed and not result.accepted and result.selected_evaluation is None
    assert result.stop_reason in ('resolution-unaccepted','outer-unaccepted') and len(calls) in (7,8)
    assert any(not row.accepted for row in result.comparisons)
    for row in result.comparisons:
        a=result.evaluations[row.reference_index].result.R;b=result.evaluations[row.evaluation_index].result.R
        np.testing.assert_array_equal(row.differences['R'],abs(a-b))
        np.testing.assert_array_equal(row.allowances['R'],.005*np.maximum(abs(a),abs(b)))
