# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent state-machine cases for explicit shape-current refinement."""
from dataclasses import FrozenInstanceError
from types import SimpleNamespace
import json
import numpy as np
import pytest
from sipi import CrossSection
from sipi.line_resolution import ResolutionTolerance
from sipi.shape_panel_line import ShapePanelTransmissionLineDocument,ShapePanelLineError
from sipi.panel_shape_conductor import PanelShapeCurrentError
from sipi.adaptive_shape_panel_resolution import (ShapePanelResolutionRefinement,
    refine_shape_panel_line_resolution)
from test_shape_panel_line import document

TOLERANCES={'C0':ResolutionTolerance(.1,0.)}  # Control example, not an accuracy gate.


def inputs(coated=False,levels=2):
    doc=document(coated);steps=[]
    for level in range(1,levels+1):
        raw=doc.to_dict();options=dict(doc.line.panel_options,panels_per_edge=16*2**level)
        raw['line']['panel']=dict(options,ground_modes=2048)
        cross=raw['line']['line']['cross_section'];cross['box']['width']*=2;cross['layers'][-1]['thickness']*=2
        for key in ('edge_size','far_size','grade'):cross['mesh'][key]*=.5**level
        steps.append(ShapePanelResolutionRefinement(options,[ShapePanelTransmissionLineDocument.from_dict(raw)]))
    return doc,steps


def fake(monkeypatch,values=None,*,outer=1.,fail=None,interrupt=False,mutual=False,shape_error=False):
    calls=[]
    def analyze(self):
        raw=self.to_dict();calls.append(self.dumps())
        if len(calls)==fail:
            if interrupt:raise KeyboardInterrupt()
            if shape_error:
                cause=PanelShapeCurrentError('original adaptive current refusal',samples=())
                raise ShapePanelLineError(cause,stage='current',input_json=self.dumps(),factors=None,settings=self.current_options) from cause
            raise ValueError('retained adaptive panel refusal')
        v=round(np.log2(.1/raw['line']['line']['cross_section']['mesh']['grade']))
        p=round(np.log2(raw['line']['panel']['panels_per_edge']/16))
        value=(values or {}).get((v,p),1.)
        if raw['line']['line']['cross_section']['box']['width']>.004:value=outer
        C=np.full((2,2,2),1e-12);C[:,0,0]=C[:,1,1]=1e-10
        if mutual:C[-1,0,1]=C[-1,1,0]=value*1e-12
        else:C*=value
        # Deliberately synthetic fields/current metadata for control transport.
        parts=np.array([np.eye(2),2*np.eye(2),3*np.eye(2)])
        factors=SimpleNamespace(ground_trace_names=(),C0=C[0],parts=parts,
            current_integrals=np.array([[1.,0.],[0.,1.],[-1.,-1.]]),
            diagnostics={'transport_stub':1.},step_m=1e-8,step_parts=np.array([parts,parts]),
            boundary_step_parts=np.array([parts,parts]),samples=())
        return SimpleNamespace(names=('left','right'),frequency=np.array([1e9,2e9]),C=C,
            R=C,G=C,dielectric=SimpleNamespace(L=C,C0=C[0]),conductor=SimpleNamespace(L_internal=C),
            current_factors=factors,panel_settings=self.current_options)
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',analyze)
    return calls


def test_two_consecutive_four_way_passes_reset_after_mixed_failure(monkeypatch):
    doc,steps=inputs(levels=4)
    # At step 2 both base comparisons pass; joint/panel fails by 1.8%.
    values={(2,1):1.009,(1,2):.991,(2,2):1.009,(3,2):1.009,(2,3):1.009,
            (3,3):1.009,(4,3):1.009,(3,4):1.009,(4,4):1.009}
    calls=fake(monkeypatch,values,outer=1.009)
    r=refine_shape_panel_line_resolution(doc,refinements=steps,tolerances={'C':ResolutionTolerance(.01,0.)},max_solves=14)
    assert r.accepted and r.refinement_levels==4 and len(calls)==14
    assert [x.accepted for x in r.comparisons[4:8]]==[True,True,True,False]
    assert r.comparisons[-1].reference_index==12 and r.selected_evaluation is r.evaluations[12]


@pytest.mark.parametrize('position',[(1,0),(0,1),(1,1),(2,1),(1,2),(2,2)])
def test_every_axis_and_last_frequency_mutual_are_required(monkeypatch,position):
    doc,steps=inputs();fake(monkeypatch,{position:1.2},mutual=True)
    r=refine_shape_panel_line_resolution(doc,refinements=steps,tolerances={'C':ResolutionTolerance(.01,0.)})
    assert r.completed and not r.accepted and not r.outer_completed
    assert r.stop_reason=='resolution-unaccepted' and len(r.evaluations)==7
    assert any(np.any(x.differences['C'][-1,0,1]>x.allowances['C'][-1,0,1]) for x in r.comparisons)


def test_budget_reserves_whole_step_and_outer_checks(monkeypatch):
    doc,steps=inputs(levels=4);calls=fake(monkeypatch,{(1,1):2.,(2,2):3.})
    r=refine_shape_panel_line_resolution(doc,refinements=steps,tolerances={'C':ResolutionTolerance(.01,0.)},max_solves=8)
    assert r.stop_reason=='budget-exhausted' and not r.completed and not r.accepted
    assert r.refinement_levels==2 and len(calls)==7 and r.selected_evaluation is None


def test_outer_failure_does_not_trigger_further_refinement(monkeypatch):
    doc,steps=inputs(levels=4);calls=fake(monkeypatch,outer=2.)
    r=refine_shape_panel_line_resolution(doc,refinements=steps,tolerances={'C':ResolutionTolerance(.01,0.)})
    assert r.stop_reason=='outer-unaccepted' and r.completed and r.outer_completed
    assert r.refinement_levels==2 and len(calls)==8 and r.selected_evaluation is None


@pytest.mark.parametrize('index',range(1,9))
def test_every_failed_stage_retains_exact_input_and_history(monkeypatch,index):
    doc,steps=inputs();calls=fake(monkeypatch,fail=index)
    r=refine_shape_panel_line_resolution(doc,refinements=steps,tolerances={'C':ResolutionTolerance(.01,0.)})
    assert r.stop_reason=='field-failed' and not r.completed and not r.accepted
    assert len(calls)==index and len(r.evaluations)==index-1
    assert r.failure.input_json==calls[-1] and r.failure.kind=='ValueError'
    assert r.failure.message=='retained adaptive panel refusal' and r.selected_evaluation is None


@pytest.mark.parametrize('index',[1,4,7,8])
def test_interrupt_propagates_from_each_phase(monkeypatch,index):
    doc,steps=inputs();calls=fake(monkeypatch,fail=index,interrupt=True)
    with pytest.raises(KeyboardInterrupt):
        refine_shape_panel_line_resolution(doc,refinements=steps,tolerances={'C':ResolutionTolerance(.01,0.)})
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
    if change=='late-outer-size':
        raw['line']['line']['cross_section']['box']['width']*=2
        raw['line']['line']['cross_section']['layers'][-1]['thickness']*=2
    if change=='late-outer-geometry':raw['line']['line']['cross_section']['traces'][0]['width']*=.9
    if change=='late-outer-mesh':raw['line']['line']['cross_section']['mesh']['grade']*=2
    if change=='late-outer-frequency':raw['line']['line']['frequency_hz']=[1e9]
    if change=='late-outer-metal':raw['line']['line']['conductor']['reference']['conductivity']*=.9
    if change=='late-outer-modes':raw['line']['panel']['ground_modes']=256
    if change.startswith('late-') or change in ('options-missing','same-panel','decrease-panel'):
        steps[-1]=ShapePanelResolutionRefinement(options,[ShapePanelTransmissionLineDocument.from_dict(raw)])
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('admission meshed'))
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('admission solved'))
    with pytest.raises((ValueError,TypeError)):
        if change=='no-outer':ShapePanelResolutionRefinement(options,[])
        else:refine_shape_panel_line_resolution(doc,refinements=steps,
            tolerances={} if change=='tolerance' else TOLERANCES,**kwargs)


def test_plan_snapshots_cannot_be_edited_through_input_containers():
    doc,steps=inputs();options=dict(steps[0].panel_options);outers=list(steps[0].outer_documents)
    step=ShapePanelResolutionRefinement(options,outers);options['panels_per_edge']=99;outers.clear()
    assert step.panel_options['panels_per_edge']==32 and len(step.outer_documents)==1
    with pytest.raises(TypeError):step.panel_options['panels_per_edge']=99
    with pytest.raises(FrozenInstanceError):step.outer_documents=()


@pytest.mark.parametrize('index',range(1,9))
def test_original_partial_current_error_survives_every_stage(monkeypatch,index):
    doc,steps=inputs();calls=fake(monkeypatch,fail=index,shape_error=True)
    result=refine_shape_panel_line_resolution(doc,refinements=steps,tolerances={'C':ResolutionTolerance(.01,0.)})
    assert result.stop_reason=='field-failed' and len(calls)==index
    details=result.failure.details
    assert details['input']==json.loads(calls[-1]) and details['partial_current']['samples']==[]
    assert details['stage']=='current' and details['message']=='original adaptive current refusal'
    report=result.to_dict();assert report['failure']['details']==details
    for row in report['evaluations']:assert row['current_solver']['diagnostics']=={'transport_stub':1.}
    report['failure']['details']['stage']='edited';assert result.failure.details['stage']=='current'


@pytest.mark.parametrize('level',[0,1])
def test_changed_shape_step_is_rejected_before_any_fields(monkeypatch,level):
    doc,steps=inputs();raw=steps[level].outer_documents[0].to_dict();raw['step_fraction']=.002
    steps[level]=ShapePanelResolutionRefinement(steps[level].panel_options,[ShapePanelTransmissionLineDocument.from_dict(raw)])
    calls=fake(monkeypatch)
    with pytest.raises(ValueError,match='step_fraction'):
        refine_shape_panel_line_resolution(doc,refinements=steps,tolerances=TOLERANCES)
    assert not calls
