# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Separate discretization axes, unchanged physical domains and retained failures."""
from types import SimpleNamespace
import json
import numpy as np
import pytest
from sipi import CrossSection,CrossSectionDocument,Layer,Trace
from sipi.line_resolution import ResolutionTolerance
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument as Line,TwoGroundFacePanelLineError
from sipi.two_ground_face_resolution import assess_two_ground_face_line_resolution as assess,_two_ground_face_resolution_inputs
from test_two_ground_panel_line import metal
from test_two_ground_face_panel_line import faces

KEYS=('R','L_internal','L_external','C','G','C0')


def inputs():
    section=CrossSection([Layer('lower',.001,3.,tan_delta=.002),Layer('upper',.001,5.,tan_delta=.004)],
        [Trace('signal',0.,.0007,.0006,.00005)],.008,top='ground')
    base=Line(CrossSectionDocument(section,mesh=dict(edge_size=5e-6,far_size=.0001,grade=.05)),[2e9,5e9],
        materials={},conductors=dict(signal=faces()),
        reference=dict(kind='surfaces',bottom=metal(58e6),top=metal(21e6),sides=None,conductors={}),
        ground_thickness=35e-6,length=.02,panels_per_edge=64,ground_modes=128,interpolation_degree=16)
    finer=dict(panels_per_edge=128,ground_modes=256,interpolation_degree=16);outer=[]
    for width,modes in ((.016,512),(.032,1024)):
        raw=base.to_dict();raw['cross_section']['box']['width']=width;raw['panel']=dict(finer,ground_modes=modes)
        for key in ('edge_size','far_size','grade'):raw['cross_section']['mesh'][key]*=.5
        outer.append(Line.from_dict(raw))
    return base,dict(refined_panel_options=finer,outer_documents=outer,tolerances={key:ResolutionTolerance(.01,0.) for key in KEYS},max_solves=6)


def synthetic(monkeypatch,fail_at=None,interrupt=False,mismatch=False,disagree=False):
    calls=[]
    def analyze(doc):
        calls.append(doc.dumps());n=len(calls)
        if n==fail_at:
            if interrupt:raise KeyboardInterrupt()
            cause=ArithmeticError('retained current refusal')
            raise TwoGroundFacePanelLineError(cause,stage='current',input_json=doc.dumps(),factors=None,settings=doc.current_options,mesh_observation=None) from cause
        scalar=2. if disagree and n==4 else 1.
        matrix=np.full((2,1,1),scalar);vacuum=np.full((1,1),scalar)
        return SimpleNamespace(names=('wrong',) if mismatch and n==4 else ('signal',),frequency=np.array([2e9,5e9]),
            R=matrix,C=matrix,G=matrix,conductor=SimpleNamespace(L_internal=matrix),dielectric=SimpleNamespace(C0=vacuum,L=vacuum),
            current_record=lambda:dict(kind='test-only-synthetic',index=n),mesh_record=lambda:dict(kind='test-only-synthetic',index=n))
    monkeypatch.setattr(Line,'analyze',analyze);return calls


def test_fieldfree_plan_preserves_each_axis_and_every_outer(monkeypatch):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('preflight meshed'))
    base,kw=inputs();before=base.dumps();models,stages=_two_ground_face_resolution_inputs(base,**kw,refinement_factor=.5)
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
    'outer-panel','outer-degree','outer-modes','width','height','metal','material','frequency','length','mesh','tolerances'])
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
    else:
        if case=='outer-panel':raw['panel']['panels_per_edge']=256
        if case=='outer-degree':raw['panel']['interpolation_degree']=14
        if case=='outer-modes':raw['panel']['ground_modes']=128
        if case=='width':raw['cross_section']['box']['width']=.008
        if case=='height':raw['cross_section']['layers'][-1]['thickness']*=2
        if case=='metal':raw['reference']['top']['conductivity']=22e6
        if case=='material':raw['cross_section']['layers'][0]['eps_r']=4.
        if case=='frequency':raw['frequency_hz'][0]=3e9
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
    for i,row in enumerate(out['evaluations']):assert row['current_solver']['index']==row['dielectric_mesh']['index']==i+1
    out.clear();assert result.to_dict()['failure']['details']


def test_completed_disagreement_is_unaccepted_and_comparisons_independent(monkeypatch):
    calls=synthetic(monkeypatch,disagree=True);base,kw=inputs();result=assess(base,**kw)
    assert result.completed and not result.accepted and len(calls)==6 and len(result.comparisons)==6
    for row in result.comparisons:
        a=1. if row.reference_index!=3 else 2.;b=2. if row.evaluation_index==3 else 1.
        for key in KEYS:
            np.testing.assert_array_equal(row.differences[key],np.full((2,1,1),abs(b-a)))
            np.testing.assert_array_equal(row.allowances[key],np.full((2,1,1),.01*max(abs(a),abs(b))))


def test_comparison_failure_retains_completed_line(monkeypatch):
    calls=synthetic(monkeypatch,mismatch=True);base,kw=inputs();result=assess(base,**kw)
    assert not result.completed and len(calls)==len(result.evaluations)==4
    assert result.failure.stage=='joint' and result.failure.kind=='ValueError' and result.failure.details is None
    assert result.to_dict()['evaluations'][-1]['current_solver']['index']==4


def test_interrupt_not_converted(monkeypatch):
    calls=synthetic(monkeypatch,fail_at=3,interrupt=True);base,kw=inputs()
    with pytest.raises(KeyboardInterrupt):assess(base,**kw)
    assert len(calls)==3


def test_actual_layered_separate_axes_and_finite_wider_domains(record_property):
    base,kw=inputs();result=assess(base,**kw);record=result.to_dict()
    record_property('two_ground_face_finite_resolution',json.dumps(record,sort_keys=True))
    assert result.completed and result.accepted
    assert len(result.evaluations)==len(result.comparisons)==6
    for evaluation in result.evaluations:
        line=evaluation.result;omega=2*np.pi*line.frequency
        z=line.R[:,0,0]+1j*omega*line.L[:,0,0];y=line.G[:,0,0]+1j*omega*line.C[:,0,0]
        np.testing.assert_allclose(line.characteristic().z_characteristic[:,0,0],np.sqrt(z/y),rtol=1e-10,atol=0)
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


def test_whole_boundary_input_is_not_silently_adapted(monkeypatch):
    from test_two_ground_resolution import inputs as whole_inputs
    base,kw=whole_inputs()
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('wrong type solved'))
    with pytest.raises(TypeError):assess(base,**kw)


@pytest.mark.parametrize('changed',['face','coating','roughness','reference'])
def test_outer_face_laws_cannot_change(monkeypatch,changed):
    base,kw=inputs();raw=kw['outer_documents'][0].to_dict()
    if changed=='face':raw['conductors']['signal']['top']['conductivity']*=.9
    elif changed=='coating':
        raw['conductors']['signal']['top']=dict(kind='layered',conductivity=35e6,relative_permeability=1.,
            coatings=[dict(thickness_m=2e-7,conductivity=14e6,relative_permeability=3.)])
    elif changed=='roughness':raw['conductors']['signal']['top']['roughness']=dict(kind='hammerstad',rms_m=1e-7)
    else:raw['reference']['bottom']['conductivity']*=.9
    kw['outer_documents'][0]=Line.from_dict(raw)
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('changed law solved'))
    with pytest.raises(ValueError):assess(base,**kw)


def test_actual_pair_three_frequencies_separate_axes_and_outer_boxes(record_property):
    from scipy.linalg import sqrtm
    from sipi.constants import epsilon_0,mu_0
    from test_two_ground_face_sampled_pair_goal import document
    raw=document(.00043,.00028,[2e9,3.5e9,5e9]).to_dict()
    raw['panel']['panels_per_edge']=64
    base=Line.from_dict(raw);finer=dict(base.current_options,panels_per_edge=128,ground_modes=256)
    outer=[]
    for width,modes in ((.016,512),(.032,1024)):
        data=base.to_dict();data['cross_section']['box']['width']=width
        data['panel']=dict(finer,ground_modes=modes)
        for key in ('edge_size','far_size','grade'):data['cross_section']['mesh'][key]*=.5
        outer.append(Line.from_dict(data))
    result=assess(base,refined_panel_options=finer,outer_documents=outer,
        tolerances={key:ResolutionTolerance(.01,0.) for key in KEYS},max_solves=6)
    record_property('two_ground_face_pair_finite_resolution',json.dumps(result.to_dict(),sort_keys=True))
    assert result.completed and result.accepted
    transform=np.array([[1.,-1.],[.5,.5]])
    for evaluation in result.evaluations:
        line=evaluation.result;c0=line.current_factors.C0
        np.testing.assert_allclose(line.C,4*np.broadcast_to(c0,line.C.shape),rtol=1e-12,atol=0)
        np.testing.assert_allclose(line.G,2*np.pi*line.frequency[:,None,None]*.003*line.C,rtol=1e-12,atol=0)
        np.testing.assert_allclose(line.dielectric.L@c0,mu_0*epsilon_0*np.eye(2),rtol=1e-12,atol=1e-28)
        for i,f in enumerate(line.frequency):
            z=line.R[i]+2j*np.pi*f*line.L[i];y=line.G[i]+2j*np.pi*f*line.C[i]
            independent=np.diag(transform@np.linalg.solve(np.asarray(sqrtm(z@y),dtype=complex),z)@transform.T)
            np.testing.assert_allclose(np.diag(line.characteristic().mixed_mode().z_characteristic[i]),independent,rtol=1e-10,atol=0)
    for comparison in result.comparisons:
        a=result.evaluations[comparison.reference_index].result;b=result.evaluations[comparison.evaluation_index].result
        def metric(line,key):
            if key=='L_internal':return line.conductor.L_internal
            if key=='L_external':return np.broadcast_to(line.dielectric.L,line.R.shape)
            if key=='C0':return np.broadcast_to(line.current_factors.C0,line.R.shape)
            return getattr(line,key)
        for key in KEYS:
            expected=abs(metric(b,key)-metric(a,key));allowance=.01*np.maximum(abs(metric(a,key)),abs(metric(b,key)))
            np.testing.assert_array_equal(comparison.differences[key],expected)
            np.testing.assert_array_equal(comparison.allowances[key],allowance)
            assert np.all(expected<=allowance)
