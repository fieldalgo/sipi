# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Separate solver axes retain actual per-entry acceptance and failure history."""
import json
import numpy as np
import pytest

from sipi import CrossSection
from sipi.constants import mu_0,epsilon_0
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.line_model import TransmissionLineDocument
from sipi.panel_resolution import assess_panel_line_resolution
from sipi.line_resolution import ResolutionTolerance
from sipi.line_resolution_document import resolution_record
from test_panel_line import base
from test_layered_study import material

FINE=dict(panels_per_edge=32,ground_modes=1024,interpolation_degree=12)
# A deliberately loose requested C0 allowance tests positive execution, not
# numerical accuracy. Existing independent panel and line gates stay required.
TOLERANCES={'C0':ResolutionTolerance(.1,0.)}


def inputs(coated=False):
    line=base();schema='sipi.panel-transmission-line/1'
    if coated:
        data=line.to_dict();data['schema']='sipi.transmission-line/7'
        data['conductor']['conductors']['left']=material()
        line=TransmissionLineDocument.from_dict(data);schema='sipi.panel-transmission-line/2'
    doc=PanelTransmissionLineDocument(line,panels_per_edge=16,schema=schema)
    raw=doc.to_dict();raw['panel']=dict(FINE,ground_modes=2048)
    cross=raw['line']['cross_section'];cross['box']['width']*=2
    cross['layers'][-1]['thickness']*=2
    for key in ('edge_size','far_size','grade'):cross['mesh'][key]*=.5
    return doc,[PanelTransmissionLineDocument.from_dict(raw)]


@pytest.fixture(scope='module',params=[False,True],ids=['legacy','coated'])
def observed(request):
    doc,outers=inputs(request.param)
    result=assess_panel_line_resolution(doc,refined_panel_options=FINE,
        outer_documents=outers,tolerances=TOLERANCES)
    return doc,outers,result


def test_real_axes_keep_physics_inputs_and_independent_uniform_identities(observed,record_property):
    doc,outers,result=observed
    assert result.completed and result.accepted and result.failure is None
    assert [r.stage for r in result.evaluations]==['base','volume','panel','joint','outer:0']
    assert [(r.reference_index,r.evaluation_index) for r in result.comparisons]==[(0,1),(0,2),(1,3),(2,3),(3,4)]
    assert result.evaluations[0].input_json==doc.dumps()
    assert result.evaluations[-1].input_json==outers[0].dumps()
    for row in result.evaluations:
        r=row.result
        np.testing.assert_allclose(r.C,4.2*np.broadcast_to(r.current_factors.C0,r.C.shape),rtol=1e-12,atol=0.)
        np.testing.assert_allclose(r.G,2*np.pi*r.frequency[:,None,None]*.02*r.C,rtol=1e-12,atol=0.)
        np.testing.assert_allclose(r.dielectric.L@r.current_factors.C0,
                                   mu_0*epsilon_0*np.eye(2),rtol=1e-10,atol=1e-28)
    for a,b in ((0,1),(2,3)):
        np.testing.assert_array_equal(result.evaluations[a].result.R,result.evaluations[b].result.R)
        np.testing.assert_array_equal(result.evaluations[a].result.current_factors.parts,
                                      result.evaluations[b].result.current_factors.parts)
    for row in result.comparisons:
        a=result.evaluations[row.reference_index].result.current_factors.C0
        b=result.evaluations[row.evaluation_index].result.current_factors.C0
        for f in range(2):
            np.testing.assert_array_equal(row.differences['C0'][f],abs(b-a))
            np.testing.assert_array_equal(row.allowances['C0'][f],.1*np.maximum(abs(a),abs(b)))
    record=resolution_record(result)
    assert json.loads(json.dumps(record,allow_nan=False))==record
    record_property('panel_resolution',json.dumps(record))


def replay(monkeypatch,result,failed=None):
    values={r.input_json:r.result for r in result.evaluations};calls=[]
    def analyze(self):
        text=self.dumps();calls.append(text)
        if text==failed:raise ValueError('explicit panel assessment refusal')
        return values[text]
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',analyze)
    return calls


def test_no_matrix_norm_floor_hides_actual_mutual_changes(observed,monkeypatch):
    doc,outers,previous=observed;calls=replay(monkeypatch,previous)
    tol=ResolutionTolerance(.005,0.)
    result=assess_panel_line_resolution(doc,refined_panel_options=FINE,
        outer_documents=outers,tolerances={'R':tol})
    assert result.completed and not result.accepted and len(calls)==5
    for row in result.comparisons:
        a=result.evaluations[row.reference_index].result.R
        b=result.evaluations[row.evaluation_index].result.R
        np.testing.assert_array_equal(row.allowances['R'],.005*np.maximum(abs(a),abs(b)))
    outer=result.comparisons[-1]
    assert np.any(outer.differences['R'][:,0,1]>outer.allowances['R'][:,0,1])


def test_exact_agreement_request_retains_unaccepted_steps(observed,monkeypatch):
    doc,outers,previous=observed;replay(monkeypatch,previous)
    result=assess_panel_line_resolution(doc,refined_panel_options=FINE,
        outer_documents=outers,tolerances={'C0':ResolutionTolerance(0.,0.)})
    assert result.completed and not result.accepted
    assert result.comparisons[0].accepted and not result.comparisons[1].accepted


@pytest.mark.parametrize('stage',['base','volume','panel','joint','outer:0'])
def test_stage_failure_keeps_exact_input_and_prior_history(observed,monkeypatch,stage):
    doc,outers,previous=observed
    index=[r.stage for r in previous.evaluations].index(stage)
    text=previous.evaluations[index].input_json;calls=replay(monkeypatch,previous,text)
    result=assess_panel_line_resolution(doc,refined_panel_options=FINE,
        outer_documents=outers,tolerances=TOLERANCES)
    assert not result.completed and not result.accepted and len(calls)==index+1
    assert len(result.evaluations)==index and result.failure.input_json==text
    assert result.failure.stage==stage and result.failure.kind=='ValueError'


@pytest.mark.parametrize('change',['budget','missing-control','decreased-panel','same-panel',
    'outer-panel','outer-degree','outer-modes','outer-mesh','outer-geometry','outer-metal',
    'outer-schema','factor','no-outer'])
def test_controls_and_outer_physics_precede_field_work(monkeypatch,change):
    doc,outers=inputs();fine=dict(FINE);raw=outers[0].to_dict();options={}
    if change=='budget':options['max_solves']=4
    if change=='missing-control':fine.pop('ground_modes')
    if change=='decreased-panel':fine['panels_per_edge']=8
    if change=='same-panel':fine=doc.panel_options
    if change=='outer-panel':raw['panel']['panels_per_edge']=16
    if change=='outer-degree':raw['panel']['interpolation_degree']=10
    if change=='outer-modes':raw['panel']['ground_modes']=512
    if change=='outer-mesh':raw['line']['cross_section']['mesh']['grade']*=2
    if change=='outer-geometry':raw['line']['cross_section']['traces'][0]['width']*=.9
    if change=='outer-metal':raw['line']['conductor']['reference']['conductivity']*=.9
    if change=='outer-schema':
        raw['schema']='sipi.panel-transmission-line/2';raw['line']['schema']='sipi.transmission-line/7'
    if change=='factor':options['refinement_factor']=1.
    outers=[] if change=='no-outer' else [PanelTransmissionLineDocument.from_dict(raw)]
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('preflight meshed'))
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('preflight solved'))
    with pytest.raises((ValueError,TypeError)):
        assess_panel_line_resolution(doc,refined_panel_options=fine,outer_documents=outers,
                                     tolerances=TOLERANCES,**options)


def test_user_interrupt_propagates(monkeypatch):
    doc,outers=inputs()
    def interrupt(self):raise KeyboardInterrupt()
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',interrupt)
    with pytest.raises(KeyboardInterrupt):
        assess_panel_line_resolution(doc,refined_panel_options=FINE,outer_documents=outers,
                                     tolerances=TOLERANCES)
