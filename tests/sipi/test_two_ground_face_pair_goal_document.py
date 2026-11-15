# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved two-ground goals retain exact sources, failures and physical refinements."""
import json
import itertools
import numpy as np
import pytest
from scipy.linalg import sqrtm

from sipi import CrossSection
from sipi.study import ImpedanceStudyDocument
from sipi.two_ground_face_pair_goal_document import TwoGroundFaceForwardPairDesignDocument as Document, _QUANTITIES
from sipi.two_ground_face_input import _line_from_values
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument as Line
from sipi.execution import execute_saved, normalize_saved
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject
from test_execution_record import ARTIFACTS
from test_two_ground_face_pair_goal import physical_document, synthetic
from test_panel_pair_goal import quantities, ROOT, STAGES


def document(physical=False):
    raw=physical_document(.00038,.00028).to_dict()
    bounds=[[.00035,.0005],[.0002,.0004]] if physical else [[.00015,.0006],[.0001,.0003]]
    study=ImpedanceStudyDocument('coupled_stripline',dict(width=.00038,gap=.00028,
        plane_spacing=.002,eps_r=4.,thickness=.00005,tan_delta=.003,box_width=.008,trace_height=.000975),
        sampling=dict(kind='corners',variables=[dict(name=name,lower=pair[0],upper=pair[1])
                      for name,pair in zip(('width','gap'),bounds)]),quantity='z_diff_forward',
        mesh=raw['cross_section']['mesh'],frequency=2e9 if physical else 1e9,materials={})
    return Document(study,conductors=raw['conductors'],reference=raw['reference'],
        ground_thickness=raw['ground_thickness_m'],targets=dict(zip(_QUANTITIES,[90.,44.5] if physical else quantities(*ROOT))),
        tolerances=dict(zip(_QUANTITIES,[.1,.1] if physical else [1e-6,1e-6])),
        initial=[.00038,.00028] if physical else None,**raw['panel'])


def test_field_free_snapshot_and_shared_normalization(monkeypatch):
    def forbidden(*a,**k):pytest.fail('preparation performed fields')
    monkeypatch.setattr(CrossSection,'mesh',forbidden);monkeypatch.setattr(Line,'analyze',forbidden)
    doc=document();text=doc.dumps()
    assert Document.loads(text).dumps()==normalize_saved(text)==text
    raw=doc.to_dict();raw['reference']['top']['conductivity']=1
    doc.goal_input['study']['parameters']['gap']=0
    assert doc.dumps()==text
    request=SavedExecutionRequest(text)
    project=SavedProject(request,project_id='two-ground-goal',design_id='a',title='Goal',label='Nominal')
    assert SavedProject.loads(project.dumps()).prepare('a').request_id==request.request_id


@pytest.mark.parametrize('where',['root','study','sampling','targets','panel','signal','top','coating'])
@pytest.mark.parametrize('change',['extra','missing'])
def test_strict_nested_contract(where,change):
    raw=document().to_dict()
    raw['conductors']['positive']['top']=dict(kind='layered',conductivity=58e6,relative_permeability=1.,coatings=[dict(thickness_m=2e-7,conductivity=14e6,relative_permeability=3.)])
    target={'root':raw,'study':raw['study'],'sampling':raw['study']['sampling'],
        'targets':raw['targets_ohm'],'panel':raw['panel'],'signal':raw['conductors']['positive'],
        'top':raw['reference']['top'],'coating':raw['conductors']['positive']['top']['coatings'][0]}[where]
    if change=='extra':target['unexpected']=1
    else:target.pop(next(iter(target)))
    with pytest.raises((ValueError,TypeError)):Document.from_dict(raw)


@pytest.mark.parametrize('case',['schema','duplicate','nan','budget','upper-budget','bool-budget',
    'target','tolerance','initial-size','initial-bool','initial-outside','one-variable',
    'sampling','zero-bound','refinement','frequency','open-top'])
def test_invalid_controls_before_field_work(monkeypatch,case):
    raw=document().to_dict();text=None
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('invalid input solved'))
    if case=='schema':raw['schema']+='unknown'
    if case=='duplicate':text=json.dumps(raw).replace('"max_evaluations": 64','"max_evaluations": 64, "max_evaluations": 64')
    if case=='nan':text=json.dumps(raw).replace('"max_evaluations": 64','"max_evaluations": NaN')
    if case=='budget':raw['max_evaluations']=3
    if case=='upper-budget':raw['max_evaluations']=10001
    if case=='bool-budget':raw['max_evaluations']=True
    if case=='target':raw['targets_ohm'][_QUANTITIES[0]]=0
    if case=='tolerance':raw['tolerances_ohm'][_QUANTITIES[1]]=-1
    if case=='initial-size':raw['initial']=[.0003]
    if case=='initial-bool':raw['initial']=[True,.0002]
    if case=='initial-outside':raw['initial']=[.001,.0002]
    if case=='one-variable':raw['study']['sampling']['variables'].pop()
    if case=='sampling':raw['study']['sampling'].update(kind='uniform',count=4,seed=12)
    if case=='zero-bound':raw['study']['sampling']['variables'][0]['lower']=0
    if case=='refinement':raw['panel']['panels_per_edge']=129
    if case=='frequency':raw['study']['material_evaluation']['frequency_hz']=0
    if case=='open-top':
        raw['study']['template']='coupled_microstrip'
        params=raw['study']['parameters'];params['substrate_height']=params.pop('plane_spacing')
    with pytest.raises((ValueError,TypeError)):Document.loads(text or json.dumps(raw))


def test_source_factory_matches_independent_geometry_at_bounds_and_initial(monkeypatch):
    import sipi.two_ground_face_pair_goal_document as module
    doc=document(True);data=doc.to_dict();sentinel=object()
    def inspect(make,bounds,targets,**controls):
        for w,g in [controls['initial'],*itertools.product(*bounds)]:
            actual=make(w,g).to_dict();expected=physical_document(w,g).to_dict()
            expected['cross_section']['layers'][0]['name']='dielectric'
            original=physical_document(w,g).cross_section
            expected['cross_section']['mesh']=original.section.mesh_settings(**original.mesh_options)
            assert actual==expected
        assert targets==[90.,44.5] and controls['tolerances']==[.1,.1]
        assert controls['max_evaluations']==64
        return sentinel
    monkeypatch.setattr(module,'seek_two_ground_face_forward_pair_impedances',inspect)
    assert doc.solve() is sentinel


def test_synthetic_modal_root_and_saved_receipt(monkeypatch):
    calls=synthetic(monkeypatch);doc=document();result=doc.solve()
    np.testing.assert_allclose(result.parameters,np.array(ROOT)*[.0003,.0002],rtol=1e-6)
    receipt=SavedExecutionRequest(doc.dumps()).run()
    assert receipt['execution']['result']==result.to_dict()
    assert receipt['execution']['status']=='complete'
    request=SavedExecutionRequest(doc.dumps());record=SavedExecutionRecord(request,receipt,
        run_id='two-ground-goal:complete',artifacts=ARTIFACTS)
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('restore solved'))
    assert SavedExecutionRecord.loads(record.dumps()).receipt==receipt
    assert len(calls)>4 and [r.evaluation.stage for r in result.refinements]==STAGES


@pytest.mark.parametrize('mode',['budget','diagnostics','bytes'])
def test_caller_limits_before_solve(monkeypatch,mode):
    monkeypatch.setattr(Document,'solve',lambda *a,**k:pytest.fail('rejected goal solved'))
    kwargs={'max_evaluations':63} if mode=='budget' else {'diagnostics':['characteristic']} if mode=='diagnostics' else {'max_input_bytes':16}
    with pytest.raises(ValueError):execute_saved(document().dumps(),**kwargs)


@pytest.mark.parametrize('attempt',[1,2,3,4])
def test_failed_and_interrupted_attempts_retain_original_cause(monkeypatch,attempt):
    calls=synthetic(monkeypatch,fail_at=attempt)
    raw=document().to_dict();raw.update(initial=(np.array(ROOT)*[.0003,.0002]).tolist(),max_evaluations=4)
    doc=Document.from_dict(raw);request=SavedExecutionRequest(doc.dumps(),max_evaluations=4)
    receipt=request.run();error=receipt['execution']['error']
    assert receipt['execution']['status']=='failed' and receipt['execution']['result'] is None
    assert error['attempts']==len(calls)==attempt and len(error['history'])==attempt-1
    assert error['stage']==(['search']+STAGES)[attempt-1]+'/extraction'
    assert error['cause_type']=='TwoGroundFacePanelLineError'
    assert error['cause_details']['stage']=='current' and error['cause_details']['cause_type']=='ArithmeticError'
    assert error['cause_details']['input']==error['input']==json.loads(calls[-1])
    record=SavedExecutionRecord(request,receipt,run_id='two-ground-goal:failed',artifacts=ARTIFACTS)
    assert SavedExecutionRecord.loads(record.dumps()).receipt==receipt
    synthetic(monkeypatch,fail_at=attempt,interrupt=True)
    with pytest.raises(KeyboardInterrupt):request.run()


def test_registered_actual_saved_goal_and_independent_characteristic(record_property):
    doc=document(True);receipt=SavedExecutionRequest(doc.dumps()).run();output=receipt['execution']
    assert output['status']=='complete',output['error']
    saved=output['result'];assert 4<saved['evaluations']<=64
    assert [r['stage'] for r in saved['refinements']]==STAGES
    # Independently reconstruct the full complex characteristic matrix from
    # fresh selected/refined line results, not an uncoupled modal approximation.
    inputs=[saved['input']]+[r['input'] for r in saved['refinements']]
    transform=np.array([[1.,-1.],[.5,.5]])
    for raw in inputs:
        result=Line.from_dict(raw).analyze();omega=2*np.pi*result.frequency[0]
        z=result.R[0]+1j*omega*result.L[0];y=result.G[0]+1j*omega*result.C[0]
        gamma=np.asarray(sqrtm(z@y),dtype=complex)
        independent=np.diag(transform@np.linalg.solve(gamma,z)@transform.T).real
        np.testing.assert_allclose(independent,[90.,44.5],rtol=0,atol=.1)
    record_property('two_ground_face_saved_goal',json.dumps(output,sort_keys=True))


def test_fixed_pitch_and_material_leaf_use_the_same_source_without_solves(monkeypatch):
    from sipi.dielectric import ConstantDielectric, dielectric_to_dict
    raw=document().to_dict();study=raw['study']
    study.update(schema='sipi.impedance-study/4',fixed_pitch_m=.0008,
        material_variables={'dk':dict(region='dielectric',path=['eps_r'])})
    study['parameters']['gap']=.0008-study['parameters']['width']
    study['material_evaluation']['materials']={'dielectric':dielectric_to_dict(ConstantDielectric(4.,.003))}
    study['sampling']['variables']=[dict(name='width',lower=.0003,upper=.0005),dict(name='dk',lower=3.,upper=5.)]
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('source preparation solved'))
    doc=Document.from_dict(raw)
    for w,er in itertools.product([.0003,.0005],[3.,5.]):
        line=_line_from_values(doc.to_dict(),[w,er]);traces=line.cross_section.section.traces
        assert traces[1].x0-traces[0].x1==pytest.approx(.0008-w,rel=1e-14,abs=0)
        assert line.to_dict()['materials']['dielectric']['parameters']['eps_r']==er
        assert line.to_dict()['conductors']==raw['conductors']


def test_invalid_unsolved_corner_refuses_before_search(monkeypatch):
    raw=document().to_dict();raw['study']['sampling']['variables'][1]['upper']=.02
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('corner check solved'))
    with pytest.raises(ValueError):Document.from_dict(raw)
