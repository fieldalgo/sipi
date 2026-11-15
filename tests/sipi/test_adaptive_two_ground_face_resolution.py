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
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument,TwoGroundFacePanelLineError
from sipi.adaptive_two_ground_face_resolution import (TwoGroundFaceResolutionRefinement,
    refine_two_ground_face_line_resolution)
from test_two_ground_face_panel_line import document

TOLERANCES={'C0':ResolutionTolerance(.1,0.)}  # Control example, not an accuracy gate.


def inputs(coated=False,levels=2):
    raw=document('pair').to_dict();raw['panel']['panels_per_edge']=16
    doc=TwoGroundFacePanelTransmissionLineDocument.from_dict(raw);steps=[]
    for level in range(1,levels+1):
        raw=doc.to_dict();options=dict(doc.current_options,panels_per_edge=16*2**level,ground_modes=128*2**level)
        raw['panel']=dict(options,ground_modes=4096)
        cross=raw['cross_section'];cross['box']['width']*=2
        for key in ('edge_size','far_size','grade'):cross['mesh'][key]*=.5**level
        steps.append(TwoGroundFaceResolutionRefinement(options,[TwoGroundFacePanelTransmissionLineDocument.from_dict(raw)]))
    return doc,steps


def fake(monkeypatch,values=None,*,outer=1.,fail=None,interrupt=False,mutual=False,shape_error=False):
    calls=[]
    def analyze(self):
        raw=self.to_dict();calls.append(self.dumps())
        if len(calls)==fail:
            if interrupt:raise KeyboardInterrupt()
            if shape_error:
                cause=ArithmeticError('original adaptive current refusal')
                raise TwoGroundFacePanelLineError(cause,stage='current',input_json=self.dumps(),factors=None,
                    settings=self.current_options,mesh_observation=None) from cause
            raise ValueError('retained adaptive panel refusal')
        v=round(np.log2(.05/raw['cross_section']['mesh']['grade']))
        p=round(np.log2(raw['panel']['panels_per_edge']/16))
        value=(values or {}).get((v,p),1.)
        if raw['cross_section']['box']['width']>.008:value=outer
        C=np.full((3,2,2),1e-12);C[:,0,0]=C[:,1,1]=1e-10
        if mutual:C[-1,0,1]=C[-1,1,0]=value*1e-12
        else:C*=value
        # Synthetic transport values are not physical extraction evidence.
        return SimpleNamespace(names=('left','right'),frequency=np.array([1e9,3e9,10e9]),C=C,
            R=C,G=C,dielectric=SimpleNamespace(L=C,C0=C[0]),conductor=SimpleNamespace(L_internal=C),
            current_record=lambda:dict(kind='test-only-synthetic',diagnostics={'transport_stub':1.}),
            mesh_record=lambda attempt=len(calls):dict(kind='test-only-synthetic',attempt=attempt))
    monkeypatch.setattr(TwoGroundFacePanelTransmissionLineDocument,'analyze',analyze)
    return calls


def test_two_consecutive_four_way_passes_reset_after_mixed_failure(monkeypatch):
    doc,steps=inputs(levels=4)
    # At step 2 both base comparisons pass; joint/panel fails by 1.8%.
    values={(2,1):1.009,(1,2):.991,(2,2):1.009,(3,2):1.009,(2,3):1.009,
            (3,3):1.009,(4,3):1.009,(3,4):1.009,(4,4):1.009}
    calls=fake(monkeypatch,values,outer=1.009)
    r=refine_two_ground_face_line_resolution(doc,refinements=steps,tolerances={'C':ResolutionTolerance(.01,0.)},max_solves=14)
    assert r.accepted and r.refinement_levels==4 and len(calls)==14
    assert [x.accepted for x in r.comparisons[4:8]]==[True,True,True,False]
    assert r.comparisons[-1].reference_index==12 and r.selected_evaluation is r.evaluations[12]


@pytest.mark.parametrize('position',[(1,0),(0,1),(1,1),(2,1),(1,2),(2,2)])
def test_every_axis_and_last_frequency_mutual_are_required(monkeypatch,position):
    doc,steps=inputs();fake(monkeypatch,{position:1.2},mutual=True)
    r=refine_two_ground_face_line_resolution(doc,refinements=steps,tolerances={'C':ResolutionTolerance(.01,0.)})
    assert r.completed and not r.accepted and not r.outer_completed
    assert r.stop_reason=='resolution-unaccepted' and len(r.evaluations)==7
    assert any(np.any(x.differences['C'][-1,0,1]>x.allowances['C'][-1,0,1]) for x in r.comparisons)


def test_budget_reserves_whole_step_and_outer_checks(monkeypatch):
    doc,steps=inputs(levels=4);calls=fake(monkeypatch,{(1,1):2.,(2,2):3.})
    r=refine_two_ground_face_line_resolution(doc,refinements=steps,tolerances={'C':ResolutionTolerance(.01,0.)},max_solves=8)
    assert r.stop_reason=='budget-exhausted' and not r.completed and not r.accepted
    assert r.refinement_levels==2 and len(calls)==7 and r.selected_evaluation is None


def test_outer_failure_does_not_trigger_further_refinement(monkeypatch):
    doc,steps=inputs(levels=4);calls=fake(monkeypatch,outer=2.)
    r=refine_two_ground_face_line_resolution(doc,refinements=steps,tolerances={'C':ResolutionTolerance(.01,0.)})
    assert r.stop_reason=='outer-unaccepted' and r.completed and r.outer_completed
    assert r.refinement_levels==2 and len(calls)==8 and r.selected_evaluation is None


@pytest.mark.parametrize('index',range(1,9))
def test_every_failed_stage_retains_exact_input_and_history(monkeypatch,index):
    doc,steps=inputs();calls=fake(monkeypatch,fail=index)
    r=refine_two_ground_face_line_resolution(doc,refinements=steps,tolerances={'C':ResolutionTolerance(.01,0.)})
    assert r.stop_reason=='field-failed' and not r.completed and not r.accepted
    assert len(calls)==index and len(r.evaluations)==index-1
    assert r.failure.input_json==calls[-1] and r.failure.kind=='ValueError'
    assert r.failure.message=='retained adaptive panel refusal' and r.selected_evaluation is None


@pytest.mark.parametrize('index',[1,4,7,8])
def test_interrupt_propagates_from_each_phase(monkeypatch,index):
    doc,steps=inputs();calls=fake(monkeypatch,fail=index,interrupt=True)
    with pytest.raises(KeyboardInterrupt):
        refine_two_ground_face_line_resolution(doc,refinements=steps,tolerances={'C':ResolutionTolerance(.01,0.)})
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
        raw['cross_section']['box']['width']*=2
    if change=='late-outer-geometry':raw['cross_section']['traces'][0]['width']*=.9
    if change=='late-outer-mesh':raw['cross_section']['mesh']['grade']*=2
    if change=='late-outer-frequency':raw['frequency_hz']=[1e9]
    if change=='late-outer-metal':raw['reference']['top']['conductivity']*=.9
    if change=='late-outer-modes':raw['panel']['ground_modes']=256
    if change.startswith('late-') or change in ('options-missing','same-panel','decrease-panel'):
        steps[-1]=TwoGroundFaceResolutionRefinement(options,[TwoGroundFacePanelTransmissionLineDocument.from_dict(raw)])
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('admission meshed'))
    monkeypatch.setattr(TwoGroundFacePanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('admission solved'))
    with pytest.raises((ValueError,TypeError)):
        if change=='no-outer':TwoGroundFaceResolutionRefinement(options,[])
        else:refine_two_ground_face_line_resolution(doc,refinements=steps,
            tolerances={} if change=='tolerance' else TOLERANCES,**kwargs)


def test_plan_snapshots_cannot_be_edited_through_input_containers():
    doc,steps=inputs();options=dict(steps[0].panel_options);outers=list(steps[0].outer_documents)
    step=TwoGroundFaceResolutionRefinement(options,outers);options['panels_per_edge']=99;outers.clear()
    assert step.panel_options['panels_per_edge']==32 and len(step.outer_documents)==1
    with pytest.raises(TypeError):step.panel_options['panels_per_edge']=99
    with pytest.raises(FrozenInstanceError):step.outer_documents=()


@pytest.mark.parametrize('index',range(1,9))
def test_original_partial_current_error_survives_every_stage(monkeypatch,index):
    doc,steps=inputs();calls=fake(monkeypatch,fail=index,shape_error=True)
    result=refine_two_ground_face_line_resolution(doc,refinements=steps,tolerances={'C':ResolutionTolerance(.01,0.)})
    assert result.stop_reason=='field-failed' and len(calls)==index
    details=result.failure.details
    assert details['input']==json.loads(calls[-1]) and details['current_solver'] is None and details['dielectric_mesh'] is None
    assert details['stage']=='current' and details['message']=='original adaptive current refusal'
    report=result.to_dict();assert report['failure']['details']==details
    for row in report['evaluations']:assert row['current_solver']['diagnostics']=={'transport_stub':1.}
    report['failure']['details']['stage']='edited';assert result.failure.details['stage']=='current'


@pytest.mark.parametrize('level',[0,1])
@pytest.mark.parametrize('change',['plane','face'])
def test_physical_planes_and_face_laws_cannot_change_at_later_steps(monkeypatch,level,change):
    doc,steps=inputs();raw=steps[level].outer_documents[0].to_dict()
    if change=='plane':raw['cross_section']['layers'][-1]['thickness']*=1.01
    else:raw['conductors']['right']['top']['conductivity']*=.9
    steps[level]=TwoGroundFaceResolutionRefinement(steps[level].panel_options,[TwoGroundFacePanelTransmissionLineDocument.from_dict(raw)])
    calls=fake(monkeypatch)
    with pytest.raises(ValueError):refine_two_ground_face_line_resolution(doc,refinements=steps,tolerances=TOLERANCES)
    assert not calls


def physical_inputs(kind):
    if kind=='scalar':
        from test_two_ground_face_resolution import inputs as scalar
        base=scalar()[0]
    else:
        from test_two_ground_face_sampled_pair_study import physical_document
        from sipi.two_ground_face_input import _line_from_values
        raw=physical_document().to_dict();raw['study']['sampling'].update(kind='uniform',count=2,seed=19)
        from sipi.two_ground_face_sampled_pair_study import TwoGroundFaceSampledForwardPairStudyDocument
        study=TwoGroundFaceSampledForwardPairStudyDocument.from_dict(raw)
        line=_line_from_values(raw,study.samples()[0]).to_dict();line['frequency_hz']=raw['frequency_hz']
        base=TwoGroundFacePanelTransmissionLineDocument.from_dict(line)
    steps=[]
    for level in (1,2):
        options=dict(panels_per_edge=64*2**level,ground_modes=128*2**level,interpolation_degree=16)
        outer=[]
        for width,modes in ((.016,256*2**level),(.032,512*2**level)):
            raw=base.to_dict();raw['panel']=dict(options,ground_modes=modes)
            raw['cross_section']['box']['width']=width
            for _ in range(level):
                for key in ('edge_size','far_size','grade'):raw['cross_section']['mesh'][key]*=.75
            outer.append(TwoGroundFacePanelTransmissionLineDocument.from_dict(raw))
        steps.append(TwoGroundFaceResolutionRefinement(options,outer))
    return base,steps


@pytest.mark.parametrize('kind',['scalar','pair'])
def test_registered_two_levels_all_axes_and_outer_with_independent_fields(kind,record_property):
    from scipy.linalg import sqrtm
    from sipi.constants import mu_0,epsilon_0
    base,steps=physical_inputs(kind)
    keys=('R','L_internal','L_external','C','G','C0')
    result=refine_two_ground_face_line_resolution(base,refinements=steps,
        tolerances={key:ResolutionTolerance(.01,0.) for key in keys},refinement_factor=.75,max_solves=9)
    record=result.to_dict();record_property('two_ground_face_adaptive_'+kind,json.dumps(record,sort_keys=True))
    assert result.completed and result.accepted and result.outer_completed
    assert result.refinement_levels==2 and len(result.evaluations)==9 and len(result.comparisons)==10
    assert result.selected_evaluation is result.evaluations[6]
    for row in result.evaluations:
        line=row.result
        for i,f in enumerate(line.frequency):
            z=line.R[i]+2j*np.pi*f*line.L[i];y=line.G[i]+2j*np.pi*f*line.C[i]
            independent=np.linalg.solve(np.asarray(sqrtm(z@y),dtype=complex),z)
            np.testing.assert_allclose(line.characteristic().z_characteristic[i],independent,rtol=1e-10,atol=0)
            if kind=='pair':
                eps=3.+.7/(1+1j*f/1e9);c0=line.current_factors.C0
                np.testing.assert_allclose(line.C[i],eps.real*c0,rtol=.005,atol=0)
                np.testing.assert_allclose(line.G[i],2*np.pi*f*(-eps.imag)*c0,rtol=.005,atol=0)
                np.testing.assert_allclose(line.dielectric.L@c0,mu_0*epsilon_0*np.eye(2),rtol=1e-12,atol=1e-28)
    # Independently compare every serialized entry, not only the accepted flag.
    units=('R_ohm_per_m','L_internal_h_per_m','L_external_h_per_m','C_f_per_m','G_s_per_m','C0_f_per_m')
    for comparison in record['comparisons']:
        a=record['evaluations'][comparison['reference_index']]['quantities']
        b=record['evaluations'][comparison['evaluation_index']]['quantities']
        for unit in units:
            x,y=np.array(a[unit]),np.array(b[unit]);delta=abs(x-y);allowance=.01*np.maximum(abs(x),abs(y))
            np.testing.assert_array_equal(comparison['differences'][unit],delta)
            np.testing.assert_array_equal(comparison['allowances'][unit],allowance)
            assert np.all(delta<=allowance)
