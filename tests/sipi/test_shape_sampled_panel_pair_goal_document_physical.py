# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Actual searches and exact field replay through saved finite-grid requests."""
import json
import numpy as np
import pytest
from sipi.sampled_panel_pair_goal_document import SampledPanelForwardPairDesignDocument
from sipi.shape_sampled_panel_pair_goal_document import ShapeSampledPanelForwardPairDesignDocument as Document
from sipi.shape_sampled_panel_pair_goal import seek_shape_sampled_panel_forward_pair_impedances as seek
from sipi.shape_panel_line import ShapePanelTransmissionLineDocument
from sipi.execution import execute_saved
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from test_execution_record import ARTIFACTS
from test_pair_line_goal_document import Q
from test_shape_sampled_panel_pair_study_physical import document as study,identities,F
from test_shape_sampled_panel_pair_goal_physical import factory,CASES,BOUNDS,TOLERANCES,INITIAL
from test_shape_panel_pair_goal_physical import snapshot


def document(coated=False):
    raw=study(coated).to_dict()['study'];source=raw['study']
    for v,bounds in zip(source['sampling']['variables'],BOUNDS):
        v.update(lower=bounds[0],upper=bounds[1])
    values=np.array(CASES['coated' if coated else 'bulk']['targets_ohm'])
    nested=SampledPanelForwardPairDesignDocument(source,conductor=raw['conductor'],frequencies=F,
        targets={q:values[:,i].tolist() for i,q in enumerate(Q)},
        tolerances={q:np.array(TOLERANCES)[:,i].tolist() for i,q in enumerate(Q)},
        initial=INITIAL,max_evaluations=64,**raw['panel'],
        schema='sipi.sampled-panel-forward-pair-design/2' if coated else 'sipi.sampled-panel-forward-pair-design/1')
    return Document(nested)


@pytest.mark.parametrize('coated',[False,True],ids=['bulk','coated'])
def test_actual_saved_grid_search_and_replay_receipt(monkeypatch,record_property,coated):
    doc=document(coated);fields={};previous=ShapePanelTransmissionLineDocument.analyze
    def capture(self):
        result=previous(self);fields[self.dumps()]=result;return result
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',capture)
    goal=doc.solve()
    record_property('shape_saved_grid_goal_search',json.dumps(goal.to_dict(),allow_nan=False))
    results=[goal.result]+[r.result for r in goal.refinements]
    record_property('shape_saved_grid_goal_fields',json.dumps([snapshot(r) for r in results],allow_nan=False))
    record_property('shape_saved_grid_goal_independent',json.dumps([identities(r,coated) for r in results]))
    assert len(fields)==len(goal.history)>4
    calls=[]
    def replay(self):
        calls.append(self.dumps());return fields[self.dumps()]
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',replay)
    direct=seek(lambda w,g:factory(w,g,coated),BOUNDS,F,CASES['coated' if coated else 'bulk']['targets_ohm'],
        tolerances=TOLERANCES,initial=INITIAL,max_evaluations=64)
    assert direct.to_dict()==goal.to_dict() and len(calls)==len(fields)
    out=execute_saved(doc.dumps(),max_evaluations=64)
    assert out['result']==goal.to_dict() and out['status']=='complete' and out['error'] is None
    request=SavedExecutionRequest(doc.dumps(),max_evaluations=64);receipt=request.run()
    saved=SavedExecutionRecord(request,receipt,run_id='shape-grid-goal:actual',artifacts=ARTIFACTS)
    assert len(calls)==3*len(fields)
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('restore solved'))
    assert SavedExecutionRecord.loads(saved.dumps()).receipt==receipt
    record_property('shape_saved_grid_goal_execution',json.dumps(out,allow_nan=False))
