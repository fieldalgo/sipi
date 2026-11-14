# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Coated pair goals at fixed frequencies, with independent refinement axes."""
import json
import numpy as np
import pytest
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.sampled_panel_pair_goal import seek_sampled_panel_forward_pair_impedances
from test_layered_panel_goal import factory as single_factory, independent, snapshot

FREQUENCIES = [1e9, 2e9, 4e9]


def factory(width, gap, **kwargs):
    raw = single_factory(width, gap, **kwargs).to_dict()
    raw['line']['frequency_hz'] = FREQUENCIES
    return PanelTransmissionLineDocument.from_dict(raw)


@pytest.fixture(scope='module')
def searched():
    return seek_sampled_panel_forward_pair_impedances(factory,
        [[.4e-3,.9e-3],[.2e-3,.6e-3]], FREQUENCIES,
        [[110.,40.]]*3, tolerances=[[.25,.125]]*3,
        initial=[.7e-3,.35e-3], max_evaluations=64)


def test_actual_joint_frequency_search_and_independent_refinement(searched, record_property):
    goal = searched
    record_property('coated_sampled_goal', json.dumps(goal.to_dict(),allow_nan=False))
    assert goal.frequencies == tuple(FREQUENCIES)
    assert 4<len(goal.history)<=64
    assert np.any(abs(np.array(goal.history[0].impedances)-goal.targets)>goal.tolerances)
    assert [r.evaluation.stage for r in goal.refinements] == [
        'volume-refinement','panel-refinement','joint-refinement']
    results = [goal.result]+[r.result for r in goal.refinements]
    record_property('coated_sampled_fields',json.dumps([snapshot(r) for r in results],allow_nan=False))
    values = np.array([np.diagonal(r.characteristic().mixed_mode().z_characteristic,
                                  axis1=1,axis2=2).real for r in results])
    assert np.all(abs(values-goal.targets)<=goal.tolerances)
    assert np.all(abs(values[1:]-values[0])/abs(values[0])<=.005)
    for index in (1,2):assert np.all(abs(values[3]-values[index])/abs(values[index])<=.005)
    expected = factory(*goal.parameters).to_dict()['line']['conductor']
    for row in goal.history:
        data = json.loads(row.input_json)
        assert data['schema']=='sipi.panel-transmission-line/2'
        assert data['line']['schema']=='sipi.transmission-line/7'
        assert data['line']['frequency_hz']==FREQUENCIES
        assert data['line']['conductor']==expected
    record_property('coated_sampled_independent',json.dumps([independent(r) for r in results]))


def test_frozen_selected_geometry_finite_outer_gates(searched, record_property):
    results = []
    for box,air,modes in ((.024,.010,512),(.036,.015,768),(.048,.020,1024)):
        raw = factory(*searched.parameters,box=box,air=air).to_dict()
        raw['line']['cross_section']['mesh'] = searched.refinements[-1].document.line.cross_section.mesh_options
        raw['panel'] = dict(searched.refinements[-1].document.panel_options,ground_modes=modes)
        results.append(PanelTransmissionLineDocument.from_dict(raw).analyze())
    values = np.array([np.diagonal(r.characteristic().mixed_mode().z_characteristic,
                                  axis1=1,axis2=2).real for r in results])
    changes = abs(np.diff(values,axis=0))
    record_property('coated_sampled_outer',json.dumps(dict(values=values.tolist(),changes=changes.tolist(),
        fields=[snapshot(r) for r in results]),allow_nan=False))
    assert np.all(changes[:,:,0]<=1e-4*values[0,:,0])
    assert np.all(changes[1,:,1]<changes[0,:,1])
    record_property('coated_sampled_outer_independent',json.dumps([independent(r) for r in results]))
