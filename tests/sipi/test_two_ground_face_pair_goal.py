# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Face-law goals retain bounded search, modal references and frozen refinements."""
import json
from types import SimpleNamespace
import numpy as np
import pytest
from scipy.linalg import sqrtm
from sipi import CrossSection, CrossSectionDocument, Layer, Trace, rlgc_characteristic
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument as Document,TwoGroundFacePanelLineError
from sipi.two_ground_face_pair_goal import seek_two_ground_face_forward_pair_impedances as seek
from sipi.pair_line_goal import ForwardPairGoalError
from test_panel_pair_goal import factory as old_factory,modal,quantities,BOUNDS,ROOT,STAGES
from test_two_ground_panel_line import document as original_document


def physical_document(width,gap,frequency=2e9):
    original=original_document("box-8",panels=128)
    section=CrossSection([Layer("uniform",.002,4.,tan_delta=.003)],
        [Trace("positive",x=-(width+gap)/2,width=width,y=.000975,thickness=.00005),
         Trace("negative",x=(width+gap)/2,width=width,y=.000975,thickness=.00005)],.008,top="ground")
    raw=original.to_dict();raw["cross_section"]=CrossSectionDocument(section,mesh=original.cross_section.mesh_options).to_dict()
    raw["frequency_hz"]=[frequency];raw["length_m"]=0.
    raw['schema']='sipi.two-ground-face-panel-transmission-line/1'
    from test_two_ground_face_panel_line import faces
    raw['conductors']={'positive':faces()}
    # Preserve named physical faces; reverse metal assignments on the second signal.
    raw['conductors']['negative']=dict(zip(faces(),reversed(list(faces().values()))))
    raw['panel']['interpolation_degree']=16
    return Document.from_dict(raw)


def factory(x,y):return physical_document(x*.3e-3,y*.2e-3,frequency=1e9)


def synthetic(monkeypatch,*,lossless=False,fail_at=None,interrupt=False):
    calls=[]
    def analyze(self):
        calls.append(self.dumps())
        if len(calls)==fail_at:
            if interrupt:raise KeyboardInterrupt()
            cause=ArithmeticError("original current refusal")
            raise TwoGroundFacePanelLineError(cause,stage="current",input_json=self.dumps(),
                factors=None,settings=self.current_options,mesh_observation=None) from cause
        traces=self.cross_section.section.traces
        x=traces[0].width/.3e-3;y=(traces[1].x0-traces[0].x1)/.2e-3
        matrices,_=modal(x,y,lossless)
        return SimpleNamespace(input_json=self.dumps(),frequency=np.array([1e9]),names=("positive","negative"),
            characteristic=lambda:rlgc_characteristic([1e9],**matrices,names=("positive","negative")),
            current_record=lambda:dict(kind="test-only-synthetic"),mesh_record=lambda:dict(kind="test-only-synthetic"))
    monkeypatch.setattr(Document,"analyze",analyze)
    return calls


@pytest.mark.parametrize('scale',[(1.,1.),(1000.,.001)])
@pytest.mark.parametrize('lossless',[False,True])
def test_independent_modal_root_with_scaled_parameters(monkeypatch,scale,lossless):
    calls=synthetic(monkeypatch,lossless=lossless);scale=np.array(scale)
    goal=seek(lambda x,y:factory(x*scale[0],y*scale[1]),BOUNDS/scale[:,None],
              quantities(*ROOT,lossless),tolerances=[1e-6]*2)
    np.testing.assert_allclose(np.array(goal.parameters)*scale,ROOT,rtol=1e-6)
    assert len(calls)==len(goal.history)<=64
    assert [r.evaluation.stage for r in goal.refinements]==STAGES
    assert len({r.parameters for r in goal.history[:-3]})==len(goal.history)-3
    for row in goal.history:
        np.testing.assert_allclose(row.impedances,quantities(*(np.array(row.parameters)*scale),lossless),rtol=1e-13)
    for row in goal.refinements:
        assert row.document.dumps()==row.evaluation.input_json
        np.testing.assert_allclose(row.evaluation.impedances,goal.targets,rtol=0,atol=1e-6)


def test_frozen_selected_input_and_exact_four_attempts(monkeypatch):
    calls=synthetic(monkeypatch);made=[]
    def once(x,y):
        made.append((x,y));assert len(made)==1;return factory(x,y)
    goal=seek(once,BOUNDS,quantities(*ROOT),tolerances=[1e-8]*2,initial=ROOT,max_evaluations=4)
    assert len(calls)==len(goal.history)==4
    for index,row in enumerate(goal.refinements):
        expected=goal.document.to_dict()
        if index!=1:
            for key in ('edge_size','far_size','grade'):
                expected['cross_section']['mesh'][key]/=2
        if index!=0:expected['panel']['panels_per_edge']*=2
        assert row.document.to_dict()==expected


@pytest.mark.parametrize('attempt',[1,2,3,4])
def test_failed_current_preserves_cause_history_and_original_input(monkeypatch,attempt):
    calls=synthetic(monkeypatch,fail_at=attempt)
    with pytest.raises(ForwardPairGoalError) as caught:
        seek(factory,BOUNDS,quantities(*ROOT),tolerances=[1e-8]*2,initial=ROOT,max_evaluations=4)
    e=caught.value
    assert e.attempts==len(calls)==attempt and len(e.history)==attempt-1
    assert e.stage==(['search']+STAGES)[attempt-1]+'/extraction'
    assert e.input_json==calls[-1] and e.cause_type=='TwoGroundFacePanelLineError'
    assert isinstance(e.__cause__,TwoGroundFacePanelLineError)
    details=e.__cause__.to_dict()
    assert details['message']=='original current refusal'
    assert details['current_solver'] is None and details['dielectric_mesh'] is None
    assert details['cause_type']=='ArithmeticError'
    assert isinstance(e.__cause__.__cause__,ArithmeticError)


@pytest.mark.parametrize('attempt',[1,2,3,4])
def test_interrupts_never_become_failed_goals(monkeypatch,attempt):
    calls=synthetic(monkeypatch,fail_at=attempt,interrupt=True)
    with pytest.raises(KeyboardInterrupt):
        seek(factory,BOUNDS,quantities(*ROOT),tolerances=[1e-8]*2,initial=ROOT,max_evaluations=4)
    assert len(calls)==attempt


@pytest.mark.parametrize('key,value',[('panels_per_edge',64),
                                     ('ground_modes',1024),('interpolation_degree',14)])
def test_method_controls_cannot_drift_during_search(monkeypatch,key,value):
    calls=synthetic(monkeypatch);made=[]
    def changing(x,y):
        data=factory(x,y).to_dict();made.append(1)
        if len(made)>1:
            data['panel'][key]=value
        return Document.from_dict(data)
    with pytest.raises(ForwardPairGoalError) as caught:
        seek(changing,BOUNDS,quantities(*ROOT),tolerances=[1e-8]*2)
    assert caught.value.stage=='search/validation' and caught.value.attempts==2 and len(calls)==1


def test_old_panel_factory_is_not_silently_converted(monkeypatch):
    calls=synthetic(monkeypatch)
    with pytest.raises(ForwardPairGoalError) as caught:
        seek(old_factory,BOUNDS,quantities(*ROOT),tolerances=[1e-8]*2)
    assert caught.value.stage=='search/factory' and caught.value.cause_type=='TypeError' and not calls


@pytest.mark.parametrize('panels',[129,256])
def test_all_refinements_admitted_before_fields(monkeypatch,panels):
    calls=synthetic(monkeypatch)
    def oversized(x,y):
        data=factory(x,y).to_dict();data['panel']['panels_per_edge']=panels
        return Document.from_dict(data)
    with pytest.raises(ForwardPairGoalError) as caught:
        seek(oversized,BOUNDS,quantities(*ROOT),tolerances=[1e-8]*2)
    assert caught.value.stage=='search/validation' and not calls


def test_three_actual_refinement_attempts_are_reserved(monkeypatch):
    calls=synthetic(monkeypatch)
    with pytest.raises(ForwardPairGoalError) as caught:
        seek(factory,BOUNDS,quantities(*ROOT),tolerances=[1e-8]*2,max_evaluations=4)
    assert caught.value.stage=='budget' and caught.value.attempts==len(calls)==1


@pytest.mark.parametrize('change',[
    dict(bounds=[[0,1],[1,2]]),dict(bounds=[[2,1],[1,2]]),dict(bounds=[1,2]),
    dict(targets=[0,1]),dict(targets=[100,np.inf]),dict(targets=[100,True]),
    dict(tolerances=[1,0]),dict(tolerances=[1,np.nan]),dict(initial=[.1,.3]),
    dict(initial=[False,.3]),dict(max_evaluations=True),dict(max_evaluations=3),dict(max_evaluations=10001)])
def test_invalid_controls_precede_factory(change):
    def forbidden(*a):pytest.fail('factory reached')
    kwargs=dict(bounds=BOUNDS,targets=[100.,40.],tolerances=[.25,.125]);kwargs.update(change)
    with pytest.raises(ValueError):seek(forbidden,**kwargs)


def test_registered_actual_two_ground_face_pair_goal_and_independent_forward_matrix(record_property):
    goal=seek(physical_document,[[.00035,.0005],[.0002,.0004]],[90.,44.5],
        tolerances=[.1,.1],initial=[.00038,.00028],max_evaluations=64)
    assert 4<len(goal.history)<=64
    assert [r.evaluation.stage for r in goal.refinements]==STAGES
    a=np.array([[1.,-1.],[.5,.5]])
    rows=[(goal.result,goal.impedances)]+[(r.result,r.evaluation.impedances) for r in goal.refinements]
    for result,values in rows:
        omega=2*np.pi*result.frequency[0];z=result.R[0]+1j*omega*result.L[0];y=result.G[0]+1j*omega*result.C[0]
        gamma=np.asarray(sqrtm(z@y),dtype=complex)
        independent=np.linalg.solve(gamma,z)
        target_values=np.diag(a@independent@a.T).real
        np.testing.assert_allclose(values,target_values,rtol=1e-10,atol=0)
        np.testing.assert_allclose(values,[90.,44.5],rtol=0,atol=.1)
    selected=goal.document.to_dict()
    for i,row in enumerate(goal.refinements):
        expected=json.loads(json.dumps(selected))
        if i!=1:
            for key in ("edge_size","far_size","grade"):expected["cross_section"]["mesh"][key]/=2
        if i!=0:expected["panel"]["panels_per_edge"]*=2
        assert row.document.to_dict()==expected
        assert row.result.current_record()["settings"]==expected["panel"]
    observation=goal.to_dict()
    assert observation["scope"]=="bounded-two-parameter-two-ground-face-forward-pair-impedance-goal"
    assert len(observation["refinements"])==3
    assert all(row["current_solver"] and row["dielectric_mesh"] for row in observation["refinements"])
    record_property("two_ground_face_pair_goal",json.dumps(observation,sort_keys=True))


def test_registered_factory_preserves_width_gap_and_height():
    doc=physical_document(.00038,.00028);traces=doc.cross_section.section.traces
    assert tuple(t.width for t in traces)==(.00038,.00038)
    assert tuple(t.y for t in traces)==(.000975,.000975)
    assert tuple(t.thickness for t in traces)==(.00005,.00005)
    assert traces[1].x0-traces[0].x1==pytest.approx(.00028,rel=1e-14,abs=0)
    assert doc.to_dict()['frequency_hz']==[2e9] and doc.to_dict()['length_m']==0
