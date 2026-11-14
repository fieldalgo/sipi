# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Actual finite-domain frequency goals with independent selected/refined checks."""
from pathlib import Path
import json
import numpy as np
import pytest
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.shape_panel_line import ShapePanelTransmissionLineDocument
from sipi.shape_sampled_panel_pair_goal import seek_shape_sampled_panel_forward_pair_impedances as seek
from sipi.sampled_panel_pair_goal import SampledPanelForwardPairGoalError
from sipi.sampled_panel_pair_study import _full_line
from sipi.line_input import _line_from_values
from test_shape_sampled_panel_pair_study_physical import document,identities,F
from test_shape_panel_pair_goal_physical import snapshot

CASES=json.loads((Path(__file__).parent/'fixtures/shape-sampled-pair-goal.json').read_text())['cases']
BOUNDS=[[.4e-3,.7e-3],[.2e-3,.5e-3]]
TOLERANCES=[[.05,.025]]*3
INITIAL=[.48e-3,.28e-3]


def factory(width,gap,coated=False):
    raw=document(coated).to_dict()['study'];raw['study']['parameters'].update(left_width=width,gap=gap)
    options=dict(line_schema='sipi.transmission-line/7') if coated else {}
    panel=_full_line(_line_from_values(raw['study'],raw['conductor'],**options),
        F,raw['panel'],layered=coated)
    return ShapePanelTransmissionLineDocument(panel)


@pytest.mark.parametrize('name',['bulk','coated'])
def test_actual_nonmatching_start_grid_search_and_independent_refinements(name,monkeypatch,record_property):
    coated=name=='coated';case=CASES[name]
    assert factory(*case['parameters_m'],coated).to_dict()==case['input']
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('changed current method'))
    try:
        goal=seek(lambda w,g:factory(w,g,coated),BOUNDS,F,case['targets_ohm'],
            tolerances=TOLERANCES,initial=INITIAL,max_evaluations=64)
    except SampledPanelForwardPairGoalError as error:
        cause=error.__cause__
        record_property('shape_grid_goal_failure',json.dumps(dict(stage=error.stage,attempts=error.attempts,
            history=[r.to_dict() for r in error.history],input=None if error.input_json is None else json.loads(error.input_json),
            cause=cause.to_dict() if hasattr(cause,'to_dict') else str(cause)),allow_nan=False))
        raise
    record_property('shape_grid_goal_search',json.dumps(goal.to_dict(),allow_nan=False))
    results=[goal.result]+[r.result for r in goal.refinements]
    record_property('shape_grid_goal_fields',json.dumps([snapshot(r) for r in results],allow_nan=False))
    assert np.any(abs(np.array(goal.history[0].impedances)-case['targets_ohm'])>TOLERANCES)
    assert 4<len(goal.history)<=64 and len(goal.refinements)==3
    assert np.all(np.array(goal.parameters)>=np.array(BOUNDS)[:,0]) and np.all(np.array(goal.parameters)<=np.array(BOUNDS)[:,1])
    assert np.all(abs(np.array(goal.impedances)-case['targets_ohm'])<=TOLERANCES)
    record_property('shape_grid_goal_independent',json.dumps([identities(line,coated) for line in results]))
    for row in goal.refinements:
        assert row.document.to_dict()['step_fraction']==goal.document.to_dict()['step_fraction']
        assert np.all(abs(np.array(row.evaluation.impedances)-case['targets_ohm'])<=TOLERANCES)
        assert np.max(abs(np.array(row.evaluation.impedances)/goal.impedances-1))<=.005
