# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Separate corner-current and volume resolution axes with retained evidence."""
from types import SimpleNamespace
import json
import numpy as np
import pytest
from sipi import CrossSection
from sipi.line_resolution import ResolutionTolerance
from sipi.two_ground_harmonic_guard_corner_face_panel_line import (
    TwoGroundHarmonicGuardCornerFacePanelTransmissionLineDocument as Line,
    TwoGroundHarmonicGuardCornerFacePanelLineError)
from sipi.two_ground_harmonic_guard_corner_face_resolution import (
    assess_two_ground_harmonic_guard_corner_face_line_resolution as assess,
    _two_ground_harmonic_guard_corner_face_resolution_inputs)
from test_two_ground_harmonic_guard_corner_face_panel_line import document

KEYS=('R','L_internal','L_external','C','G','C0')


def inputs(index=0):
    base=document(index,heterogeneous=True)
    finer=dict(panels_per_edge=48,ground_modes=512,interpolation_degree=24);outer=[]
    for width,modes in ((.016,1024),(.032,2048)):
        raw=base.to_dict();raw['cross_section']['box']['width']=width;raw['panel']=dict(finer,ground_modes=modes)
        for key in ('edge_size','far_size','grade'):raw['cross_section']['mesh'][key]*=.5
        outer.append(Line.from_dict(raw))
    return base,dict(refined_panel_options=finer,outer_documents=outer,
        tolerances={key:ResolutionTolerance(.01,0.) for key in KEYS},max_solves=6)


def synthetic(monkeypatch,fail_at=None,interrupt=False,mismatch=False,disagree=False):
    calls=[]
    def analyze(doc):
        calls.append(doc.dumps());n=len(calls)
        if n==fail_at:
            if interrupt:raise KeyboardInterrupt()
            cause=ArithmeticError('retained current refusal')
            raise TwoGroundHarmonicGuardCornerFacePanelLineError(cause,stage='current',input_json=doc.dumps(),
                factors=None,settings=doc.current_options,mesh_observation=None) from cause
        scalar=2. if disagree and n==4 else 1.
        matrix=np.full((3,2,2),scalar);vacuum=np.full((2,2),scalar)
        return SimpleNamespace(names=('wrong',) if mismatch and n==4 else ('left','right'),frequency=np.array([1e9,3e9,10e9]),
            R=matrix,C=matrix,G=matrix,conductor=SimpleNamespace(L_internal=matrix),dielectric=SimpleNamespace(C0=vacuum,L=vacuum),
            current_record=lambda:dict(kind='test-only-synthetic',index=n),mesh_record=lambda:dict(kind='test-only-synthetic',index=n))
    monkeypatch.setattr(Line,'analyze',analyze);return calls


def test_fieldfree_plan_preserves_axes_materials_and_every_outer(monkeypatch):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('preflight meshed'))
    base,kw=inputs();before=base.dumps();models,stages=_two_ground_harmonic_guard_corner_face_resolution_inputs(base,**kw,refinement_factor=.5)
    assert [s for s,_,_ in stages]==['base','volume','panel','joint','outer:0','outer:1']
    assert [refs for _,_,refs in stages]==[(),((0,'volume'),),((0,'panel'),),((1,'joint:panel'),(2,'joint:volume')),((3,'outer:0'),),((3,'outer:1'),)]
    original=base.to_dict()
    for i in (1,2,3):
        raw=stages[i][1].to_dict()
        if i in (1,3):
            for key in ('edge_size','far_size','grade'):
                assert raw['cross_section']['mesh'][key]==original['cross_section']['mesh'][key]*.5
                raw['cross_section']['mesh'][key]*=2
        if i in (2,3):assert raw['panel']==kw['refined_panel_options'];raw['panel']=original['panel']
        assert raw==original
    assert stages[4][1].to_dict()==kw['outer_documents'][0].to_dict()
    assert base.dumps()==before


@pytest.mark.parametrize('case',['budget','factor','empty-outer','wrong-line','same-panel','lower-panel','missing-panel',
    'outer-panel','outer-modes','width','height','metal','material','frequency','length','mesh','tolerances','old-schema'])
def test_bad_plan_rejected_before_fields(monkeypatch,case):
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('bad plan solved'))
    base,kw=inputs();raw=kw['outer_documents'][0].to_dict()
    if case=='budget':kw['max_solves']=5
    elif case=='factor':kw['refinement_factor']=1.
    elif case=='empty-outer':kw['outer_documents']=[]
    elif case=='wrong-line':base=object()
    elif case=='same-panel':kw['refined_panel_options']=base.current_options
    elif case=='lower-panel':kw['refined_panel_options']['ground_modes']=64
    elif case=='missing-panel':kw['refined_panel_options'].pop('ground_modes')
    elif case=='tolerances':kw['tolerances']={}
    elif case=='old-schema':
        from test_two_ground_face_panel_line import document as old_document
        base=old_document()
    else:
        if case=='outer-panel':raw['panel']['panels_per_edge']=46
        if case=='outer-modes':raw['panel']['ground_modes']=256
        if case=='width':raw['cross_section']['box']['width']=.008
        if case=='height':raw['cross_section']['layers'][-1]['thickness']*=2
        if case=='metal':raw['reference']['top']['conductivity']=22e6
        if case=='material':raw['cross_section']['layers'][0]['eps_r']=4.
        if case=='frequency':raw['frequency_hz'][0]=2e9
        if case=='length':raw['length_m']=.03
        if case=='mesh':raw['cross_section']['mesh']['grade']*=2
        kw['outer_documents'][0]=Line.from_dict(raw)
    with pytest.raises((ValueError,TypeError)):assess(base,**kw)


@pytest.mark.parametrize('fail_at',range(1,7))
def test_typed_failures_keep_previous_work_and_stop(monkeypatch,fail_at):
    calls=synthetic(monkeypatch,fail_at=fail_at);base,kw=inputs();result=assess(base,**kw)
    assert not result.accepted and not result.completed and len(calls)==fail_at
    assert len(result.evaluations)==fail_at-1 and result.failure.input_json==calls[-1]
    out=result.to_dict();assert out['failure']['details']['cause_type']=='ArithmeticError'
    assert out['scope']=='two-ground-harmonic-guard-corner-face-finite-resolution-not-absolute-accuracy'
    for i,row in enumerate(out['evaluations']):assert row['current_solver']['index']==row['dielectric_mesh']['index']==i+1
    out.clear();assert result.to_dict()['failure']['details']


def test_completed_disagreement_remains_unaccepted_without_floor(monkeypatch):
    calls=synthetic(monkeypatch,disagree=True);base,kw=inputs();result=assess(base,**kw)
    assert result.completed and not result.accepted and len(calls)==6 and len(result.comparisons)==6
    for row in result.comparisons:
        a=1. if row.reference_index!=3 else 2.;b=2. if row.evaluation_index==3 else 1.
        for key in KEYS:
            np.testing.assert_array_equal(row.differences[key],np.full((3,2,2),abs(b-a)))
            np.testing.assert_array_equal(row.allowances[key],np.full((3,2,2),.01*max(abs(a),abs(b))))


def test_comparison_failure_retains_completed_line(monkeypatch):
    calls=synthetic(monkeypatch,mismatch=True);base,kw=inputs();result=assess(base,**kw)
    assert not result.completed and len(calls)==len(result.evaluations)==4
    assert result.failure.stage=='joint' and result.failure.kind=='ValueError' and result.failure.details is None
    assert result.to_dict()['evaluations'][-1]['current_solver']['index']==4


def test_interrupt_not_converted(monkeypatch):
    calls=synthetic(monkeypatch,fail_at=3,interrupt=True);base,kw=inputs()
    with pytest.raises(KeyboardInterrupt):assess(base,**kw)
    assert len(calls)==3


@pytest.mark.parametrize('index',[0])
def test_actual_layered_two_signals_and_guard_finite_comparisons(index,record_property,monkeypatch):
    import sipi.two_ground_harmonic_guard_corner_conductor as current
    original=current._solver();calls=[]
    def solve(*args,**kwargs):calls.append(kwargs);return original(*args,**kwargs)
    monkeypatch.setattr(current,"_solver",lambda:solve)
    base,kw=inputs(index);result=assess(base,**kw);record=result.to_dict()
    record_property('corner_face_finite_resolution',json.dumps(record,sort_keys=True))
    assert len(calls)==4  # Six complete lines; exact base/volume and panel/joint current reuse.
    assert result.completed and result.accepted
    assert len(result.evaluations)==len(result.comparisons)==6
    for evaluation in result.evaluations:
        assert evaluation.result.current_record()['kind']=='two-ground-harmonic-corner-faces-fixed-guard'
    for row in result.comparisons:
        a=result.evaluations[row.reference_index].result;b=result.evaluations[row.evaluation_index].result
        def metric(line,key):
            if key=='L_internal':return line.conductor.L_internal
            if key=='L_external':return np.broadcast_to(line.dielectric.L,line.R.shape)
            if key=='C0':return np.broadcast_to(line.current_factors.C0,line.R.shape)
            return getattr(line,key)
        for key in KEYS:
            expected=abs(metric(b,key)-metric(a,key));allowance=.01*np.maximum(abs(metric(a,key)),abs(metric(b,key)))
            np.testing.assert_array_equal(row.differences[key],expected)
            np.testing.assert_array_equal(row.allowances[key],allowance)
            assert np.all(expected<=allowance)


@pytest.mark.parametrize('kind',['ground-assignment','guard-face-metal'])
def test_guard_physics_must_remain_fixed_between_domains(monkeypatch,kind):
    import dataclasses
    from sipi import CrossSectionDocument
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('changed guard physics solved'))
    base,kw=inputs();outer=kw['outer_documents'][0];raw=outer.to_dict()
    if kind=='guard-face-metal':raw['reference']['conductors']['center']['right']['conductivity']=18e6
    else:
        cross=outer.cross_section;s=cross.section
        traces=[dataclasses.replace(t,ground=(i==1)) for i,t in enumerate(s.traces)]
        raw['cross_section']=CrossSectionDocument(CrossSection(s.layers,traces,s.width,top='ground'),mesh=cross.mesh_options).to_dict()
        old=raw['reference']['conductors'].pop('center');old.pop('kind')
        raw['reference']['conductors']['right']=dict(kind='faces',**raw['conductors'].pop('right'))
        raw['conductors']['center']=old
    kw['outer_documents'][0]=Line.from_dict(raw)
    with pytest.raises(ValueError):assess(base,**kw)
