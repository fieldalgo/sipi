# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Finite refinement control preserves separate axes and unresolved mutual terms."""
from dataclasses import FrozenInstanceError
from types import SimpleNamespace
import json
import numpy as np
import pytest
from sipi import CrossSection
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.line_model import TransmissionLineDocument
from sipi.line_resolution import ResolutionTolerance
from sipi.adaptive_panel_resolution import PanelResolutionRefinement, refine_panel_line_resolution
from sipi.constants import epsilon_0, mu_0
from test_panel_line import base, test_independent_two_n_characteristic_and_network_invariants as check_network
from test_layered_panel_goal import material, independent, snapshot


def inputs(coated=False, levels=2):
    raw=base().to_dict()
    if coated:
        raw['schema']='sipi.transmission-line/7'
        raw['conductor']['conductors']={k:material() for k in raw['conductor']['conductors']}
        raw['conductor']['reference']=material()
    line=TransmissionLineDocument.from_dict(raw)
    doc=PanelTransmissionLineDocument(line,panels_per_edge=8,
        schema=f'sipi.panel-transmission-line/{2 if coated else 1}')
    steps=[]
    for level in range(1,levels+1):
        raw=doc.to_dict();options=dict(doc.panel_options,panels_per_edge=8*2**level)
        raw['panel']=dict(options,ground_modes=1024)
        cross=raw['line']['cross_section'];cross['box']['width']*=2;cross['layers'][-1]['thickness']*=2
        for key in ('edge_size','far_size','grade'):cross['mesh'][key]*=.5**level
        steps.append(PanelResolutionRefinement(options,[PanelTransmissionLineDocument.from_dict(raw)]))
    return doc,steps


TOLERANCES={'C0':ResolutionTolerance(.1,0.)}  # Explicit control example, not an accuracy gate.


@pytest.fixture(scope='module',params=[False,True],ids=['legacy','coated'])
def observed(request):
    doc,steps=inputs(request.param)
    result=refine_panel_line_resolution(doc,refinements=steps,tolerances=TOLERANCES,max_solves=8)
    return doc,steps,result


def test_real_separate_axes_and_independent_fields(observed,record_property):
    doc,steps,result=observed
    assert result.accepted and result.completed and result.outer_completed
    assert result.failure is None and result.refinement_levels==2
    assert result.selected_evaluation is result.evaluations[6]
    assert [r.stage for r in result.evaluations]==['base','level:1:volume','level:1:panel',
        'level:1:joint','level:2:volume','level:2:panel','level:2:joint','outer:0']
    assert [(r.reference_index,r.evaluation_index) for r in result.comparisons]==[
        (0,1),(0,2),(1,3),(2,3),(3,4),(3,5),(4,6),(5,6),(6,7)]
    assert result.evaluations[-1].input_json==steps[-1].outer_documents[0].dumps()
    assert len({row.input_json for row in result.evaluations})==8
    fields=[];references=[]
    for row in result.evaluations:
        r=row.result;fields.append(snapshot(r))
        assert json.loads(row.input_json)['line']['conductor']==doc.to_dict()['line']['conductor']
        np.testing.assert_allclose(r.C,4.2*np.broadcast_to(r.current_factors.C0,r.C.shape),rtol=1e-12)
        np.testing.assert_allclose(r.G,2*np.pi*r.frequency[:,None,None]*.02*r.C,rtol=1e-12)
        np.testing.assert_allclose(r.dielectric.L@r.current_factors.C0,mu_0*epsilon_0*np.eye(2),rtol=1e-10,atol=1e-28)
        if doc.to_dict()['schema'].endswith('/2'):references.append(independent(r))
        else:check_network((doc,r))
    for a,b in ((0,1),(2,3),(3,4),(5,6)):
        np.testing.assert_array_equal(result.evaluations[a].result.R,result.evaluations[b].result.R)
    record_property('adaptive_panel_fields',json.dumps(fields,allow_nan=False))
    record_property('adaptive_panel_independent',json.dumps(references,allow_nan=False))
    with pytest.raises(TypeError):result.tolerances['C0']=ResolutionTolerance(1,0)
    with pytest.raises(FrozenInstanceError):result.stop_reason='accepted'


def replay(monkeypatch,result):
    saved={r.input_json:r.result for r in result.evaluations};calls=[]
    def analyze(self):calls.append(self.dumps());return saved[self.dumps()]
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',analyze)
    return calls


def test_actual_small_mutual_remains_unaccepted(observed,monkeypatch,record_property):
    doc,steps,previous=observed;calls=replay(monkeypatch,previous)
    result=refine_panel_line_resolution(doc,refinements=steps,
        tolerances={'R':ResolutionTolerance(.005,0.)},max_solves=8)
    assert result.completed and not result.accepted and result.selected_evaluation is None
    assert result.stop_reason in ('resolution-unaccepted','outer-unaccepted')
    failed=[]
    for row in result.comparisons:
        a=result.evaluations[row.reference_index].result.R;b=result.evaluations[row.evaluation_index].result.R
        np.testing.assert_array_equal(row.allowances['R'],.005*np.maximum(abs(a),abs(b)))
        if not row.accepted:failed.append(row.stage)
    assert failed and len(calls) in (7,8)
    record_property('unaccepted_R_stages',json.dumps(failed))


def fake(monkeypatch,values=None,*,outer=1.,fail=None,interrupt=False,mutual=False):
    calls=[]
    def analyze(self):
        raw=self.to_dict();calls.append(self.dumps())
        if len(calls)==fail:
            if interrupt:raise KeyboardInterrupt()
            raise ValueError('retained adaptive panel refusal')
        v=round(np.log2(.1/raw['line']['cross_section']['mesh']['grade']))
        p=round(np.log2(raw['panel']['panels_per_edge']/8))
        value=(values or {}).get((v,p),1.)
        if raw['line']['cross_section']['box']['width']>.004:value=outer
        C=np.full((2,2,2),1e-12);C[:,0,0]=C[:,1,1]=1e-10
        if mutual:C[-1,0,1]=C[-1,1,0]=value*1e-12
        else:C*=value
        return SimpleNamespace(names=('left','right'),frequency=np.array([1e9,2e9]),C=C)
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',analyze)
    return calls


def test_two_consecutive_four_way_passes_reset_after_mixed_failure(monkeypatch):
    doc,steps=inputs(levels=4)
    # At step 2 both base comparisons pass; joint/panel fails by 1.8%.
    values={(2,1):1.009,(1,2):.991,(2,2):1.009,(3,2):1.009,(2,3):1.009,
            (3,3):1.009,(4,3):1.009,(3,4):1.009,(4,4):1.009}
    calls=fake(monkeypatch,values,outer=1.009)
    r=refine_panel_line_resolution(doc,refinements=steps,tolerances={'C':ResolutionTolerance(.01,0.)},max_solves=14)
    assert r.accepted and r.refinement_levels==4 and len(calls)==14
    assert [x.accepted for x in r.comparisons[4:8]]==[True,True,True,False]
    assert r.comparisons[-1].reference_index==12 and r.selected_evaluation is r.evaluations[12]


@pytest.mark.parametrize('position',[(1,0),(0,1),(1,1),(2,1),(1,2),(2,2)])
def test_every_axis_and_last_frequency_mutual_are_required(monkeypatch,position):
    doc,steps=inputs();fake(monkeypatch,{position:1.2},mutual=True)
    r=refine_panel_line_resolution(doc,refinements=steps,tolerances={'C':ResolutionTolerance(.01,0.)})
    assert r.completed and not r.accepted and not r.outer_completed
    assert r.stop_reason=='resolution-unaccepted' and len(r.evaluations)==7
    assert any(np.any(x.differences['C'][-1,0,1]>x.allowances['C'][-1,0,1]) for x in r.comparisons)


def test_budget_reserves_whole_step_and_outer_checks(monkeypatch):
    doc,steps=inputs(levels=4);calls=fake(monkeypatch,{(1,1):2.,(2,2):3.})
    r=refine_panel_line_resolution(doc,refinements=steps,tolerances={'C':ResolutionTolerance(.01,0.)},max_solves=8)
    assert r.stop_reason=='budget-exhausted' and not r.completed and not r.accepted
    assert r.refinement_levels==2 and len(calls)==7 and r.selected_evaluation is None


def test_outer_failure_does_not_trigger_further_refinement(monkeypatch):
    doc,steps=inputs(levels=4);calls=fake(monkeypatch,outer=2.)
    r=refine_panel_line_resolution(doc,refinements=steps,tolerances={'C':ResolutionTolerance(.01,0.)})
    assert r.stop_reason=='outer-unaccepted' and r.completed and r.outer_completed
    assert r.refinement_levels==2 and len(calls)==8 and r.selected_evaluation is None


@pytest.mark.parametrize('index',range(1,9))
def test_every_failed_stage_retains_exact_input_and_history(monkeypatch,index):
    doc,steps=inputs();calls=fake(monkeypatch,fail=index)
    r=refine_panel_line_resolution(doc,refinements=steps,tolerances={'C':ResolutionTolerance(.01,0.)})
    assert r.stop_reason=='field-failed' and not r.completed and not r.accepted
    assert len(calls)==index and len(r.evaluations)==index-1
    assert r.failure.input_json==calls[-1] and r.failure.kind=='ValueError'
    assert r.failure.message=='retained adaptive panel refusal' and r.selected_evaluation is None


@pytest.mark.parametrize('index',[1,4,7,8])
def test_interrupt_propagates_from_each_phase(monkeypatch,index):
    doc,steps=inputs();calls=fake(monkeypatch,fail=index,interrupt=True)
    with pytest.raises(KeyboardInterrupt):
        refine_panel_line_resolution(doc,refinements=steps,tolerances={'C':ResolutionTolerance(.01,0.)})
    assert len(calls)==index


@pytest.mark.parametrize('change',['short','long','invalid-step','limit-small','limit-large','limit-bool',
    'factor','options-missing','same-panel','decrease-panel','late-outer-size','late-outer-geometry',
    'late-outer-mesh','late-outer-frequency','late-outer-metal','late-outer-modes','no-outer','tolerance'])
def test_entire_plan_admission_precedes_field_work(monkeypatch,change):
    doc,steps=inputs();kwargs={};options=dict(steps[-1].panel_options);raw=steps[-1].outer_documents[0].to_dict()
    if change=='short':steps=steps[:1]
    if change=='long':steps=steps*3
    if change=='invalid-step':steps[-1]=None
    if change=='limit-small':kwargs['max_solves']=7
    if change=='limit-large':kwargs['max_solves']=33
    if change=='limit-bool':kwargs['max_solves']=True
    if change=='factor':kwargs['refinement_factor']=1.
    if change=='options-missing':options.pop('ground_modes')
    if change=='same-panel':options=dict(steps[0].panel_options)
    if change=='decrease-panel':options['panels_per_edge']=8
    if change=='late-outer-size':raw['line']['cross_section']['box']['width']*=2
    if change=='late-outer-geometry':raw['line']['cross_section']['traces'][0]['width']*=.9
    if change=='late-outer-mesh':raw['line']['cross_section']['mesh']['grade']*=2
    if change=='late-outer-frequency':raw['line']['frequency_hz']=[1e9]
    if change=='late-outer-metal':raw['line']['conductor']['reference']['conductivity']*=.9
    if change=='late-outer-modes':raw['panel']['ground_modes']=256
    if change.startswith('late-') or change in ('options-missing','same-panel','decrease-panel'):
        steps[-1]=PanelResolutionRefinement(options,[PanelTransmissionLineDocument.from_dict(raw)])
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('admission meshed'))
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('admission solved'))
    with pytest.raises((ValueError,TypeError)):
        if change=='no-outer':PanelResolutionRefinement(options,[])
        else:refine_panel_line_resolution(doc,refinements=steps,
            tolerances={} if change=='tolerance' else TOLERANCES,**kwargs)


def test_plan_snapshots_cannot_be_edited_through_input_containers():
    doc,steps=inputs();options=dict(steps[0].panel_options);outers=list(steps[0].outer_documents)
    step=PanelResolutionRefinement(options,outers);options['panels_per_edge']=99;outers.clear()
    assert step.panel_options['panels_per_edge']==16 and len(step.outer_documents)==1
    with pytest.raises(TypeError):step.panel_options['panels_per_edge']=99
    with pytest.raises(FrozenInstanceError):step.outer_documents=()
