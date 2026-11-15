# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved factories retain direct goals, preflight, failure evidence and input identity."""
import json
import numpy as np
import pytest
from sipi import CrossSection
from sipi.two_ground_face_line_goal_document import TwoGroundFaceLineQuantityDesignDocument as Document
from sipi.two_ground_face_line_study import TwoGroundFaceLineQuantityStudyDocument as Source
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument as Line
from sipi.execution import normalize_saved,execute_saved
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject
from test_two_ground_face_line_study import document as study_document,synthetic,QUANTITIES
from test_two_ground_face_line_goal import target
from test_execution_record import ARTIFACTS


def document(quantity='impedance_real',physical=False):
    raw=study_document(quantity,physical=physical).to_dict();raw['study']['sampling']['count']=2
    if physical:raw['panel']['panels_per_edge']=128
    return Document(Source.from_dict(raw),target=58. if physical else target(quantity),
                    tolerance=.05 if physical else 1e-8,max_evaluations=40)


@pytest.mark.parametrize('quantity',QUANTITIES)
def test_fieldfree_roundtrip_request_project_and_detached_source(monkeypatch,quantity):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('preparation solved'))
    doc=document(quantity);text=doc.dumps();assert normalize_saved(text)==Document.loads(text).dumps()==text
    source=doc.study.to_dict();source['reference']['top']['conductivity']=1;assert doc.dumps()==text
    request=SavedExecutionRequest(text,max_evaluations=40)
    project=SavedProject(request,project_id='scalar-goal',design_id='a',title='Goal',label='Source')
    assert SavedProject.loads(project.dumps()).prepare('a').request_id==request.request_id


@pytest.mark.parametrize('quantity',QUANTITIES)
def test_saved_factory_targets_and_refinement_evidence(monkeypatch,quantity):
    calls=synthetic(monkeypatch);result=document(quantity).solve()
    assert result.parameter==pytest.approx(.0004,abs=1e-18) and result.value==pytest.approx(target(quantity),abs=1e-8)
    assert len(calls)==len(result.history)==6 and len(result.refinements)==3
    request=SavedExecutionRequest(document(quantity).dumps(),max_evaluations=40)
    receipt=request.run();assert receipt['execution']['status']=='complete'
    record=SavedExecutionRecord(request,receipt,run_id='scalar-goal:synthetic',artifacts=ARTIFACTS)
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('restore solved'))
    assert SavedExecutionRecord.loads(record.dumps()).receipt==receipt


@pytest.mark.parametrize('where',['root','study','panel','reference'])
@pytest.mark.parametrize('change',['missing','extra'])
def test_strict_nested_keys(where,change):
    raw=document().to_dict();targets=dict(root=raw,study=raw['study'],panel=raw['study']['panel'],reference=raw['study']['reference']);value=targets[where]
    if change=='missing':value.pop(next(iter(value)))
    else:value['extra']=0
    with pytest.raises((ValueError,TypeError)):Document.from_dict(raw)


@pytest.mark.parametrize('kind',['schema','duplicate','nan','count','two-variables','normal','degenerate','nonpositive','budget','target','tolerance','unrefinable'])
def test_invalid_preflight_never_solves(monkeypatch,kind):
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('invalid input solved'))
    raw=document().to_dict();sampling=raw['study']['study']['sampling'];text=None
    if kind=='schema':raw['schema']+='/unknown'
    if kind=='duplicate':text=json.dumps(raw).replace('"max_evaluations": 40','"max_evaluations": 40, "max_evaluations": 40')
    if kind=='nan':text=json.dumps(raw).replace('"target": 40.0','"target": NaN')
    if kind=='count':sampling['count']=3
    if kind=='two-variables':sampling['variables'].append(dict(name='eps_r',lower=3.,upper=5.))
    if kind=='normal':sampling.update(kind='normal',seed=3,correlation=[[1.]],variables=[dict(name='width',mean=.0004,std=1e-5)])
    if kind=='degenerate':sampling['variables'][0]['upper']=sampling['variables'][0]['lower']
    if kind=='nonpositive':sampling['variables'][0]['lower']=0.
    if kind=='budget':raw['max_evaluations']=4
    if kind=='target':raw['target']=-1.
    if kind=='tolerance':raw['tolerance']=0.
    if kind=='unrefinable':raw['study']['panel']['panels_per_edge']=256
    with pytest.raises((ValueError,TypeError)):Document.loads(text or json.dumps(raw))


def test_preflight_visits_nominal_endpoints_midpoint_and_every_refinement(monkeypatch):
    import sipi.two_ground_face_line_goal_document as module
    doc=document();raw=doc.to_dict();original=module._refinements;seen=[]
    def observe(text):
        result=original(text);assert set(result)=={'volume-refinement','panel-refinement','joint-refinement'}
        seen.append(json.loads(text)['cross_section']['traces'][0]['width']);return result
    monkeypatch.setattr(module,'_refinements',observe)
    Document.from_dict(raw);v=raw['study']['study']['sampling']['variables'][0]
    assert seen==[raw['study']['study']['parameters']['width'],v['lower'],v['lower']+(v['upper']-v['lower'])/2,v['upper']]


@pytest.mark.parametrize('at',[1,4,5,6])
def test_failed_and_interrupted_attempts_keep_typed_evidence(monkeypatch,at):
    calls=synthetic(monkeypatch,fail_at=at);output=execute_saved(document().dumps(),max_evaluations=40)
    assert output['status']=='failed' and output['result'] is None and output['error']['attempts']==at
    assert output['error']['cause_details']['cause_type']=='ArithmeticError'
    assert output['error']['cause_details']['input']==json.loads(calls[-1])
    calls=synthetic(monkeypatch,fail_at=at,interrupt=True)
    with pytest.raises(KeyboardInterrupt):execute_saved(document().dumps(),max_evaluations=40)
    assert len(calls)==at


def test_host_budget_rejected_before_fields(monkeypatch):
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('budget solved'))
    with pytest.raises(ValueError,match='before any solve'):execute_saved(document().dumps(),max_evaluations=39)


def test_material_leaf_and_fixed_pitch_remain_source_transformations(monkeypatch):
    material=study_document('attenuation',material=True).to_dict();material['study']['sampling']['count']=2
    doc=Document(Source.from_dict(material),target=.4,tolerance=1e-8)
    calls=synthetic(monkeypatch);doc.solve()
    assert json.loads(calls[0])['materials']['dielectric']['parameters']['tan_delta']==.01
    assert json.loads(calls[1])['materials']['dielectric']['parameters']['tan_delta']==.03
    raw=document('differential_forward_impedance_real').to_dict();source=raw['study']['study'];source['fixed_pitch_m']=.0007
    assert source['parameters']['width']+source['parameters']['gap']==pytest.approx(.0007)
    doc=Document.from_dict(raw);calls.clear();doc.solve()
    for text in calls:
        traces=json.loads(text)['cross_section']['traces'];width=traces[0]['width'];gap=(traces[1]['x']-traces[1]['width']/2)-(traces[0]['x']+width/2)
        assert width+gap==pytest.approx(.0007,abs=1e-18)


def test_actual_saved_goal_retains_selected_and_three_refinements(record_property, monkeypatch):
    fields=[];original=Line.analyze
    def checked(self):
        line=original(self);omega=2*np.pi*line.frequency[0]
        z=line.R[0,0,0]+1j*omega*line.L[0,0,0];y=line.G[0,0,0]+1j*omega*line.C[0,0,0]
        np.testing.assert_allclose(line.propagation().z_characteristic[0,0],np.sqrt(z/y),rtol=1e-12,atol=0)
        np.testing.assert_allclose(line.propagation().gamma[0,0],np.sqrt(z*y),rtol=1e-12,atol=0)
        fields.append(dict(input=self.to_dict(),R=line.R.tolist(),L=line.L.tolist(),G=line.G.tolist(),C=line.C.tolist()))
        return line
    monkeypatch.setattr(Line,'analyze',checked)
    doc=document(physical=True);request=SavedExecutionRequest(doc.dumps(),max_evaluations=40);receipt=request.run()
    record_property('two_ground_face_saved_scalar_goal',json.dumps(receipt,sort_keys=True))
    assert receipt['execution']['status']=='complete'
    assert len(fields)==receipt['execution']['result']['evaluations']
    record_property('face_saved_scalar_fields',json.dumps(fields,sort_keys=True))
    result=receipt['execution']['result'];assert abs(result['value']-58.)<=.05 and result['evaluations']<=40
    assert result['current_solver'] and result['dielectric_mesh'] and len(result['refinements'])==3
    assert all(abs(item['evaluation']['value']-58.)<=.05 for item in result['refinements'])
    record=SavedExecutionRecord(request,receipt,run_id='scalar-goal:actual',artifacts=ARTIFACTS)
    assert SavedExecutionRecord.loads(record.dumps()).receipt==receipt


def test_whole_boundary_study_refused_without_field_conversion(monkeypatch):
    from test_two_ground_line_goal_document import document as whole_document
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('wrong study solved'))
    with pytest.raises(TypeError):Document(whole_document().study,target=40.,tolerance=.1)


@pytest.mark.parametrize('quantity',QUANTITIES)
def test_face_laws_frozen_in_saved_goal_refinements(monkeypatch,quantity):
    synthetic(monkeypatch);raw=document(quantity).to_dict();name=next(iter(raw['study']['conductors']))
    raw['study']['conductors'][name]['top']=dict(kind='layered',conductivity=58e6,relative_permeability=1.,
        coatings=[dict(thickness_m=2e-7,conductivity=14e6,relative_permeability=3.)])
    raw['study']['conductors'][name]['left']['roughness']=dict(kind='hammerstad',rms_m=1e-6)
    result=Document.from_dict(raw).solve()
    for line in [result.document,*[row.document for row in result.refinements]]:
        for key in ('conductors','reference','materials','ground_thickness_m'):
            expected=raw['study']['study']['material_evaluation']['materials'] if key=='materials' else raw['study'][key]
            assert line.to_dict()[key]==expected
