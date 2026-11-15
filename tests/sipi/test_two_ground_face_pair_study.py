# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Ordered manufacture samples, unknown rows, paired values and field refinement."""
from dataclasses import FrozenInstanceError
import itertools
import json
import numpy as np
import pytest
from scipy.linalg import sqrtm

from sipi import CrossSection
from sipi.study import ImpedanceStudyDocument
from sipi.two_ground_face_pair_study import TwoGroundFaceForwardPairStudyDocument as Document
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument as Line
from sipi.execution import execute_saved, normalize_saved
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject
from test_execution_record import ARTIFACTS
from test_two_ground_face_pair_goal_document import document as goal_document
from test_two_ground_face_pair_goal import synthetic
from test_panel_pair_goal import quantities
from test_panel_pair_study import expected_statistics

Q=('differential_forward_impedance_real','common_forward_impedance_real')


def document(sampling=None,physical=False):
    raw=goal_document(physical).to_dict();study=raw['study']
    if physical:
        study['sampling']['variables']=[dict(name='width',lower=.00043,upper=.00044),dict(name='gap',lower=.00028,upper=.00030)]
    if sampling is not None:study['sampling']=sampling
    return Document(study,conductors=raw['conductors'],reference=raw['reference'],
        ground_thickness=raw['ground_thickness_m'],panels_per_edge=64,
        ground_modes=raw['panel']['ground_modes'],interpolation_degree=raw['panel']['interpolation_degree'])


def test_pair_values_order_and_independent_statistics(monkeypatch):
    calls=synthetic(monkeypatch);doc=document();result=doc.analyze(max_evaluations=4)
    assert result.failed==0 and len(calls)==len(result.rows)==4
    assert result.variable_names==('width','gap')
    for i,(row,values) in enumerate(zip(result.rows,doc.samples())):
        assert row.index==i and row.sample_values==tuple(values) and row.phase=='complete'
        np.testing.assert_allclose(row.values,quantities(values[0]/.0003,values[1]/.0002),rtol=1e-12)
        assert row.input_json==calls[i]
        assert row.to_dict()['current_solver']['kind']=='test-only-synthetic'
    for i,q in enumerate(Q):
        for k,v in expected_statistics([row.values[i] for row in result.rows]).items():
            assert result.summary[q][k]==pytest.approx(v,rel=1e-12)
    with pytest.raises(TypeError):result.summary[Q[0]]['mean']=0
    with pytest.raises(FrozenInstanceError):result.rows[0].index=999


def test_snapshot_normalization_and_project_restore_without_fields(monkeypatch):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('preparation meshed'))
    doc=document();text=doc.dumps();raw=doc.to_dict();raw['panel']['panels_per_edge']=16
    assert Document.loads(text).dumps()==normalize_saved(text)==text==doc.dumps()
    request=SavedExecutionRequest(text);project=SavedProject(request,project_id='two-ground-study',design_id='a',title='Study',label='Source')
    assert SavedProject.loads(project.dumps()).prepare('a').request_id==request.request_id


@pytest.mark.parametrize('where',['root','panel','study','conductors','reference'])
@pytest.mark.parametrize('change',['extra','missing'])
def test_strict_saved_fields(where,change):
    raw=document().to_dict();target=raw if where=='root' else raw[where]
    if change=='extra':target['unexpected']=1
    else:target.pop(next(iter(target)))
    with pytest.raises((ValueError,TypeError)):Document.from_dict(raw)


@pytest.mark.parametrize('kind',['schema','duplicate','nan','wrong-source'])
def test_saved_contract_rejects_invalid_json(kind):
    raw=document().to_dict();text=None
    if kind=='schema':raw['schema']+='/unknown'
    if kind=='duplicate':text=json.dumps(raw).replace('"ground_modes": 128','"ground_modes": 128, "ground_modes": 128')
    if kind=='nan':text=json.dumps(raw).replace('"ground_modes": 128','"ground_modes": NaN')
    if kind=='wrong-source':raw['study']['schema']='sipi.impedance-study/1'
    with pytest.raises((ValueError,TypeError)):Document.loads(text or json.dumps(raw))


def test_correlated_normal_retains_invalid_samples_without_resampling(monkeypatch):
    calls=synthetic(monkeypatch)
    sampling=dict(kind='normal',count=8,seed=3,correlation=[[1.,.5],[.5,1.]],variables=[
        dict(name='width',mean=.0002,std=.0003),dict(name='gap',mean=.0002,std=.0003)])
    doc=document(sampling);expected=doc.samples();result=doc.analyze(max_evaluations=8)
    np.testing.assert_array_equal([row.sample_values for row in result.rows],expected)
    assert 0<result.failed<8 and result.summary is None
    assert len(calls)==8-result.failed
    for row in result.rows:
        if not row.complete:
            assert row.phase=='input' and row.values is None and row.input_json is None
            assert row.parameters_json is not None and row.material_evaluation_json is not None


def test_duplicate_sample_values_are_individually_attempted(monkeypatch):
    calls=synthetic(monkeypatch);lo=.0003
    doc=document(dict(kind='sweep',count=4,variables=[dict(name='width',lower=lo,upper=np.nextafter(lo,np.inf))]))
    result=doc.analyze(max_evaluations=4)
    assert len(calls)==len(result.rows)==4 and len(set(calls))<4
    assert [r.index for r in result.rows]==list(range(4))


@pytest.mark.parametrize('phase',['parameters','materials','input','extraction','diagnostic'])
def test_failed_row_retains_phase_and_later_rows_continue(monkeypatch,phase):
    import sipi.panel_pair_study as loop
    import sipi.two_ground_face_pair_study as module
    doc=document();calls=synthetic(monkeypatch,fail_at=2 if phase=='extraction' else None)
    if phase in ('parameters','materials','input'):
        target=module if phase=='input' else loop
        name={'parameters':'_parameters','materials':'_sample_material','input':'_line_from_inputs'}[phase]
        original=getattr(target,name);seen=[]
        def fail_second(*args,**kwargs):
            seen.append(1)
            if len(seen)==2:raise ArithmeticError('retained original row cause')
            return original(*args,**kwargs)
        monkeypatch.setattr(target,name,fail_second)
    elif phase=='diagnostic':
        original=Line.analyze
        def analyze(self):
            line=original(self)
            if len(calls)==2:
                def fail():raise ArithmeticError('retained original row cause')
                line.characteristic=fail
            return line
        monkeypatch.setattr(Line,'analyze',analyze)
    output=execute_saved(doc.dumps(),max_evaluations=4)
    assert output['status']=='incomplete' and output['error'] is None
    result=output['result'];assert result['failed']==1 and result['summary'] is None and result['count']==4
    row=result['rows'][1];assert row['phase']==phase and row['values_ohm'] is None
    assert all(r['phase']=='complete' for i,r in enumerate(result['rows']) if i!=1)
    if phase=='extraction':
        assert row['cause_details']['cause_type']=='ArithmeticError'
        assert row['cause_details']['stage']=='current' and row['cause_details']['input']==row['input']
    if phase=='diagnostic':
        assert row['current_solver'] and row['dielectric_mesh']
    request=SavedExecutionRequest(doc.dumps(),max_evaluations=4)
    # Bind the existing output without rerunning the intentionally failing loop.
    monkeypatch.setattr(Document,'analyze',lambda *a,**k: type('Saved',(),{'to_dict':lambda self:result,'failed':1})())
    receipt=request.run();record=SavedExecutionRecord(request,receipt,run_id='two-ground-study:partial',artifacts=ARTIFACTS)
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('restore solved'))
    assert SavedExecutionRecord.loads(record.dumps()).receipt==receipt


@pytest.mark.parametrize('budget',[0,1,True,4.,10001,3])
def test_budget_and_sample_count_precede_fields(monkeypatch,budget):
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('budget reached fields'))
    with pytest.raises(ValueError):document().analyze(max_evaluations=budget)


def test_interrupt_propagates_without_partial_success(monkeypatch):
    calls=synthetic(monkeypatch,fail_at=2,interrupt=True)
    with pytest.raises(KeyboardInterrupt):SavedExecutionRequest(document().dumps()).run()
    assert len(calls)==2


def test_material_samples_reach_each_preserved_input(monkeypatch):
    from sipi.dielectric import ConstantDielectric,dielectric_to_dict
    raw=document().to_dict();study=raw['study']
    study.update(schema='sipi.impedance-study/4',material_variables={'dk':dict(region='dielectric',path=['eps_r'])})
    study['material_evaluation']['materials']={'dielectric':dielectric_to_dict(ConstantDielectric(4.,.003))}
    study['sampling']=dict(kind='uniform',seed=123,count=4,variables=[dict(name='width',lower=.0003,upper=.0005),dict(name='dk',lower=3.,upper=5.)])
    calls=synthetic(monkeypatch);doc=Document.from_dict(raw);result=doc.analyze(max_evaluations=4)
    assert result.failed==0
    for row,text in zip(result.rows,calls):
        assert json.loads(text)['materials']['dielectric']['parameters']['eps_r']==row.sample_values[1]
        assert json.loads(row.material_evaluation_json)['materials']['dielectric']['parameters']['eps_r']==row.sample_values[1]


def test_actual_four_corners_panel_refinement_and_independent_launches(record_property):
    doc=document(physical=True);result=doc.analyze(max_evaluations=4)
    assert not result.failed and len(result.rows)==4
    transform=np.array([[1.,-1.],[.5,.5]]);observations=[]
    for row in result.rows:
        levels=[row.result]
        for count in (128,256):
            raw=json.loads(row.input_json);raw['panel']['panels_per_edge']=count
            levels.append(Line.from_dict(raw).analyze())
        for attribute in ('R','L','C0'):
            values=[x.current_factors.C0 if attribute=='C0' else getattr(x,attribute) for x in levels]
            for a,b in zip(values,values[1:]):np.testing.assert_allclose(a,b,rtol=.01,atol=0)
        for line in levels:
            omega=2*np.pi*line.frequency[0];z=line.R[0]+1j*omega*line.L[0];y=line.G[0]+1j*omega*line.C[0]
            gamma=np.asarray(sqrtm(z@y),dtype=complex)
            independent=np.diag(transform@np.linalg.solve(gamma,z)@transform.T).real
            actual=np.diag(line.characteristic().mixed_mode().z_characteristic[0]).real
            np.testing.assert_allclose(actual,independent,rtol=1e-10,atol=0)
        np.testing.assert_allclose(row.values,np.diag(levels[0].characteristic().mixed_mode().z_characteristic[0]).real,rtol=0,atol=0)
        observations.append(dict(input=json.loads(row.input_json),values=list(row.values),levels=[dict(panel=dict(x.panel_settings),R=x.R.tolist(),L=x.L.tolist(),C0=x.current_factors.C0.tolist(),current=x.current_record(),mesh=x.mesh_record()) for x in levels]))
    record_property('two_ground_face_study_refinement',json.dumps(observations,sort_keys=True))
