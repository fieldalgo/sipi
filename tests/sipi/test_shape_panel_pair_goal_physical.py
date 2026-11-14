# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Actual two-parameter searches, independent eigenspaces and finite domains."""
import json
import numpy as np
import pytest
from scipy.linalg import expm

from sipi.panel_line import PanelTransmissionLineDocument
from sipi.shape_panel_line import ShapePanelTransmissionLineDocument, shape_current_record
from sipi.shape_panel_pair_goal import seek_shape_panel_forward_pair_impedances
from sipi.network import rlgc_network
from test_panel_pair_goal import document as legacy_line
from test_layered_panel_goal import factory as coated_panel, independent as coated_independent


def factory(width,gap,*,coated=False,box=.024,air=.010):
    panel=(coated_panel(width,gap,box=box,air=air) if coated else
           PanelTransmissionLineDocument(legacy_line(width,gap,box=box,air=air)))
    return ShapePanelTransmissionLineDocument(panel)


def snapshot(line):
    return dict(input=json.loads(line.input_json),
        quantities={k:getattr(line,k).tolist() for k in ('R','L','C','G')},
        current_solver=shape_current_record(line.current_factors,line.panel_settings))


def independent(line):
    errors=[]
    network=rlgc_network(line.frequency,R=line.R,L=line.L,C=line.C,G=line.G,
                         length=.02,z_ref=50.,names=line.names)
    for i,f in enumerate(line.frequency):
        omega=2*np.pi*f;z=line.R[i]+1j*omega*line.L[i];y=line.G[i]+1j*omega*line.C[i]
        generator=np.block([[np.zeros((2,2)),z],[y,np.zeros((2,2))]])
        roots,vectors=np.linalg.eig(expm(generator*.003));v=vectors[:,abs(roots)>1]
        assert v.shape==(4,2)
        expected=np.linalg.solve(v[2:].T,v[:2].T).T
        error=float(abs(line.characteristic().z_characteristic[i]-expected).max()/abs(expected).max())
        t=expm(generator*.02);a,b,c,d=t[:2,:2],t[:2,2:],t[2:,:2],t[2:,2:];eye=np.eye(2)
        expected_s=np.linalg.solve(np.block([[eye,-a-b/50],[-eye,-50*c-d]]),
                                  np.block([[-eye,a-b/50],[-eye,50*c-d]]))
        scattering=float(abs(network.s[i]-expected_s).max())
        assert error<1e-10 and scattering<1e-10
        errors.append(dict(characteristic=error,scattering=scattering))
    np.testing.assert_allclose(network.s,network.s.swapaxes(1,2),rtol=0,atol=1e-10)
    assert np.linalg.svd(network.s,compute_uv=False).max()<=1+1e-10
    return errors


@pytest.fixture(scope='module',params=[False,True],ids=['legacy','coated'])
def searched(request):
    coated=request.param
    goal=seek_shape_panel_forward_pair_impedances(lambda w,g:factory(w,g,coated=coated),
        [[.4e-3,.9e-3],[.2e-3,.6e-3]],[110.,40.],tolerances=[.25,.125],
        initial=[.7e-3,.35e-3],max_evaluations=64)
    return coated,goal


def test_actual_search_and_separate_refinements(searched,record_property):
    coated,goal=searched
    record_property('shape_pair_search',json.dumps(goal.to_dict(),allow_nan=False))
    results=[goal.result]+[r.result for r in goal.refinements]
    record_property('shape_pair_fields',json.dumps([snapshot(r) for r in results],allow_nan=False))
    assert np.any(abs(np.array(goal.history[0].impedances)-goal.targets)>goal.tolerances)
    assert 4<len(goal.history)<=64
    assert [r.evaluation.stage for r in goal.refinements]==['volume-refinement','panel-refinement','joint-refinement']
    values=np.array([np.diag(r.characteristic().mixed_mode().z_characteristic[0]).real for r in results])
    assert np.all(abs(values-goal.targets)<=goal.tolerances)
    assert np.all(abs(values[1:]/values[0]-1)<=.005)
    for i in (1,2):assert np.all(abs(values[3]/values[i]-1)<=.005)
    for row in goal.history:
        raw=json.loads(row.input_json)
        assert raw['schema']=='sipi.shape-panel-transmission-line/1' and raw['step_fraction']==.001
        assert raw['line']['line']['conductor']==goal.document.to_dict()['line']['line']['conductor']
    saved=goal.to_dict()
    for row,line in zip([saved]+saved['refinements'],results):
        assert row['current_solver']==shape_current_record(line.current_factors,line.panel_settings)
    errors=[independent(r) for r in results]
    if coated:
        for r in results:coated_independent(r)
    record_property('shape_pair_independent',json.dumps(errors))


def test_selected_finite_outer_gates_at_three_frequencies(searched,record_property):
    coated,goal=searched;results=[]
    for box,air,modes in ((.024,.010,512),(.036,.015,768),(.048,.020,1024)):
        raw=factory(*goal.parameters,coated=coated,box=box,air=air).to_dict()
        raw['line']['line']['cross_section']['mesh']=goal.refinements[-1].document.line.line.cross_section.mesh_options
        raw['line']['panel']=dict(goal.refinements[-1].document.line.panel_options,ground_modes=modes)
        raw['line']['line']['frequency_hz']=[1e9,2e9,4e9]
        results.append(ShapePanelTransmissionLineDocument.from_dict(raw).analyze())
    values=np.array([np.diagonal(r.characteristic().mixed_mode().z_characteristic,axis1=1,axis2=2).real for r in results])
    changes=abs(np.diff(values,axis=0))
    record_property('shape_pair_outer',json.dumps(dict(values=values.tolist(),changes=changes.tolist(),
        fields=[snapshot(r) for r in results]),allow_nan=False))
    assert np.all(changes[:,:,0]<=1e-4*values[0,:,0])
    assert np.all(changes[1,:,1]<changes[0,:,1])
    record_property('shape_pair_outer_independent',json.dumps([independent(r) for r in results]))
    if coated:
        for r in results:coated_independent(r)
