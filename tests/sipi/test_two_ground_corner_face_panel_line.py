# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved corner-current contracts, independent network and replay evidence."""
import json
import numpy as np
import pytest
from sipi import CrossSection, CrossSectionDocument, Layer, Trace
from sipi.constants import epsilon_0, mu_0
from sipi.two_ground_corner_face_panel_line import (
    TwoGroundCornerFacePanelTransmissionLineDocument as Document,
    TwoGroundCornerFacePanelLineError)
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument as OldDocument
from sipi.execution import normalize_saved, saved_schemas
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject
from sipi.shape_face_panel_line import _metals
import sipi.two_ground_corner_face_panel_line as module
import sipi.two_ground_corner_conductor as current
from test_two_ground_corner_conductor import section, F
from test_two_ground_face_panel_line import metal, faces
from test_two_ground_panel_line import independent_network

SCHEMA = 'sipi.two-ground-corner-face-panel-transmission-line/1'


def document(index=0, heterogeneous=False):
    base=section(index)
    layers=([Layer('lower',.001,3.),Layer('upper',.001,7.,tan_delta=.01)] if heterogeneous
            else [Layer('uniform',.002,4.,tan_delta=.003)])
    sec=CrossSection(layers,base.traces,base.width,top='ground')
    conductors={t.name:faces() for t in sec.traces}
    conductors[sec.traces[0].name]['top']=dict(kind='layered',conductivity=58e6,
        relative_permeability=1.,coatings=[dict(thickness_m=2e-7,conductivity=14e6,relative_permeability=3.)])
    return Document(CrossSectionDocument(sec,mesh=dict(edge_size=5e-6,far_size=.0001,grade=.05)),
        F,materials={},conductors=conductors,
        reference=dict(kind='surfaces',bottom=metal(45e6),top=metal(21e6),sides=None,conductors={}),
        ground_thickness=35e-6,length=.02)


def forbidden(*args,**kwargs):pytest.fail('field solve reached during input admission')


def test_field_free_separate_schema_detached_roundtrip_and_request(monkeypatch):
    monkeypatch.setattr(current,'_solver',forbidden)
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    for i in (0,1):
        doc=document(i);text=doc.dumps()
        assert Document.loads(text).dumps()==text
        assert normalize_saved(text)==text
        assert SCHEMA in saved_schemas()
        assert doc.current_options==dict(panels_per_edge=128,ground_modes=256,interpolation_degree=24)
        raw=doc.to_dict();raw['panel']['ground_modes']=64;doc.current_options.clear()
        assert doc.dumps()==text
        request=SavedExecutionRequest(text,diagnostics=('modes','characteristic'))
        assert request.input_json==text
        with pytest.raises(ValueError,match='unsupported'):OldDocument.from_dict(doc.to_dict())
        old=document(i).to_dict();old['schema']='sipi.two-ground-face-panel-transmission-line/1'
        old['panel']=dict(panels_per_edge=32,ground_modes=128,interpolation_degree=12)
        old_doc=OldDocument.from_dict(old)
        assert OldDocument.loads(old_doc.dumps()).dumps()==old_doc.dumps()
        with pytest.raises(ValueError,match='unsupported'):Document.from_dict(old)


@pytest.mark.parametrize('where',['root','panel','section','signal','face','reference','top','coating'])
@pytest.mark.parametrize('change',['extra','missing'])
def test_strict_nested_admission(where,change,monkeypatch):
    monkeypatch.setattr(current,'_solver',forbidden);monkeypatch.setattr(CrossSection,'mesh',forbidden)
    raw=document().to_dict();name=next(iter(raw['conductors']))
    target={'root':raw,'panel':raw['panel'],'section':raw['cross_section'],
        'signal':raw['conductors'][name],'face':raw['conductors'][name]['bottom'],
        'reference':raw['reference'],'top':raw['reference']['top'],
        'coating':raw['conductors'][name]['top']['coatings'][0]}[where]
    if change=='extra':target['unexpected']=1
    else:target.pop(next(iter(target)))
    with pytest.raises((ValueError,TypeError)):Document.from_dict(raw)


@pytest.mark.parametrize('case',['schema','duplicate','nonfinite','panels','degree','modes',
    'missing-top','side-metal','signal-name','dc','length','zref','skin','core','material-name','wall','guard','three'])
def test_invalid_inputs_before_fields(monkeypatch,case):
    monkeypatch.setattr(current,'_solver',forbidden);monkeypatch.setattr(CrossSection,'mesh',forbidden)
    raw=document().to_dict();name=next(iter(raw['conductors']))
    if case=='schema':raw['schema']+='/unknown'
    elif case=='panels':raw['panel']['panels_per_edge']=False
    elif case=='degree':raw['panel']['interpolation_degree']=20
    elif case=='modes':raw['panel']['ground_modes']=63
    elif case=='missing-top':raw['reference']['top']=None
    elif case=='side-metal':raw['reference']['sides']=metal()
    elif case=='signal-name':raw['conductors']['extra']=faces()
    elif case=='dc':raw['frequency_hz'][0]=0
    elif case=='length':raw['length_m']=-1
    elif case=='zref':raw['reference_ohms']=0
    elif case=='skin':raw['ground_thickness_m']=1e-8
    elif case=='core':raw['conductors'][name]['top']['coatings'][0]['thickness_m']=.001
    elif case=='material-name':raw['materials']={'missing':dict(kind='constant',epsilon_r=4.,tan_delta=0.)}
    elif case=='wall':raw['cross_section']['box']['top']='open'
    elif case in ('guard','three'):
        cross=document().cross_section;sec=cross.section
        extra=[Trace('guard',x=-.001,y=.001,width=.0002,thickness=.00004,ground=case=='guard')]
        if case=='three':extra.append(Trace('third',x=.001,y=.001,width=.0002,thickness=.00004))
        raw['cross_section']=CrossSectionDocument(CrossSection(sec.layers,[*sec.traces,*extra],sec.width,top='ground'),mesh=cross.mesh_options).to_dict()
        for t in extra:
            if t.ground:raw['reference']['conductors'][t.name]=dict(kind='faces',**faces())
            else:raw['conductors'][t.name]=faces()
    text=json.dumps(raw)
    if case=='duplicate':text=text.replace('"length_m": 0.02','"length_m": 0.02, "length_m": 0.02')
    if case=='nonfinite':text=text.replace('"length_m": 0.02','"length_m": NaN')
    with pytest.raises((ValueError,TypeError)):Document.loads(text)


@pytest.fixture(scope='module')
def observations():
    return [(document(i),document(i).analyze()) for i in (0,1)]


def test_homogeneous_invariants_independent_network_and_distinct_face_laws(observations,record_property):
    records=[]
    for doc,result in observations:
        data=doc.to_dict();f=result.frequency;n=len(result.names);factor=result.current_factors
        assert result.current_record()['kind']=='two-ground-corner-power-faces-all-active'
        assert result.current_record()['whole_current']['kind']=='two-ground-corner-power-all-active'
        np.testing.assert_allclose(result.C,4*np.broadcast_to(factor.C0,result.C.shape),rtol=1e-12,atol=0)
        np.testing.assert_allclose(result.G,2*np.pi*f[:,None,None]*.003*result.C,rtol=1e-12,atol=0)
        np.testing.assert_allclose(result.dielectric.L@factor.C0,mu_0*epsilon_0*np.eye(n),rtol=1e-10,atol=1e-28)
        conductors,reference,_,_=_metals(data)
        direct=current.two_ground_corner_conductor_loss_by_face(doc.cross_section.section,f,
            conductors=conductors,reference=reference,ground_thickness=data['ground_thickness_m'],**doc.current_options)
        np.testing.assert_array_equal(result.R,direct.R)
        np.testing.assert_array_equal(result.conductor.L_internal,direct.L_internal)
        for i,x in enumerate(f):
            expected=independent_network(x,result.R[i],result.L[i],result.G[i],result.C[i],.02,50.)
            np.testing.assert_allclose(result.network.s[i],expected,rtol=1e-10,atol=1e-12)
        assert np.max(np.linalg.svd(result.network.s,compute_uv=False))<=1+1e-10
        assert result.input_json==doc.dumps() and result.mesh_record()['nodes']>0
        result.current_record().clear();result.mesh_record().clear()
        assert result.current_record() and result.mesh_record()
        with pytest.raises(TypeError):result.panel_settings['panels_per_edge']=4
        records.append(dict(input=data,R=result.R.tolist(),L=result.L.tolist(),C=result.C.tolist(),G=result.G.tolist(),
            current=result.current_record(),mesh=result.mesh_record(),s_real=result.network.s.real.tolist(),s_imag=result.network.s.imag.tolist()))
    record_property('corner_face_lines',json.dumps(records,sort_keys=True))


@pytest.mark.parametrize('stage',['current','mesh','dielectric','network'])
def test_failed_stages_retain_actual_partial_work(monkeypatch,stage):
    def broken(*a,**k):raise ArithmeticError('deliberate '+stage)
    name={'current':'two_ground_corner_conductor_loss_by_face','mesh':'_reuse_mesh',
          'dielectric':'_dispersive_from_mesh','network':'rlgc_network'}[stage]
    monkeypatch.setattr(module,name,broken);doc=document()
    with pytest.raises(TwoGroundCornerFacePanelLineError) as caught:doc.analyze()
    error=caught.value;record=error.to_dict()
    assert error.stage==stage and record['cause_type']=='ArithmeticError' and record['input']==doc.to_dict()
    assert (record['current_solver'] is not None)==(stage!='current')
    assert (record['dielectric_mesh'] is not None)==(stage in ('dielectric','network'))
    if record['current_solver']:assert record['current_solver']['kind']=='two-ground-corner-power-faces-all-active'
    record.clear();assert error.to_dict()['stage']==stage
    request=SavedExecutionRequest(doc.dumps());receipt=request.run()
    assert receipt['execution']['status']=='failed'
    saved=SavedExecutionRecord(request,receipt,run_id='corner-failed-'+stage,
        artifacts=[dict(component='sipi',version='0.1.0',kind='wheel',sha256='0'*64)])
    assert SavedExecutionRecord.loads(saved.dumps()).dumps()==saved.dumps()
    assert saved.prepare().request_id==request.request_id


def test_nonuniform_same_geometry_dielectric_fields_and_vacuum_inverse(record_property):
    doc=document(0,True);raw=doc.to_dict();raw['schema']='sipi.two-ground-face-panel-transmission-line/1'
    raw['panel']=dict(panels_per_edge=64,ground_modes=128,interpolation_degree=16)
    corner,old=doc.analyze(),OldDocument.from_dict(raw).analyze()
    np.testing.assert_array_equal(corner.C,old.C);np.testing.assert_array_equal(corner.G,old.G)
    assert corner.mesh_record()==old.mesh_record() and np.max(abs(corner.G))>0
    np.testing.assert_allclose(corner.dielectric.L@corner.current_factors.C0,
        mu_0*epsilon_0*np.eye(len(corner.names)),rtol=1e-10,atol=1e-28)
    record_property('nonuniform',json.dumps(dict(C=corner.C.tolist(),G=corner.G.tolist(),
        L=corner.dielectric.L.tolist(),C0=corner.current_factors.C0.tolist(),mesh=corner.mesh_record()),sort_keys=True))


def test_saved_request_execution_record_and_actual_replay(record_property):
    doc=document();request=SavedExecutionRequest(doc.dumps(),diagnostics=('characteristic','modes'))
    receipt=request.run();assert receipt['execution']['status']=='complete'
    saved=SavedExecutionRecord(request,receipt,run_id='corner-complete',
        artifacts=[dict(component='sipi',version='0.1.0',kind='wheel',sha256='0'*64)])
    restored=SavedExecutionRecord.loads(saved.dumps())
    assert restored.prepare().run()==receipt
    assert restored.dumps()==saved.dumps()
    project=SavedProject(request,project_id='corner',design_id='a',title='Corner line',label='Nominal').attach_record('a',saved,select=True)
    reopened=SavedProject.loads(project.dumps())
    assert reopened.current_record('a').dumps()==saved.dumps()
    assert reopened.prepare('a').request_id==request.request_id
    record_property('corner_receipt',json.dumps(receipt,sort_keys=True))


def test_old_resolution_refuses_new_schema_before_fields(monkeypatch):
    from sipi.two_ground_face_resolution import assess_two_ground_face_line_resolution
    from sipi.line_resolution import ResolutionTolerance
    monkeypatch.setattr(current,'_solver',forbidden);monkeypatch.setattr(CrossSection,'mesh',forbidden)
    doc=document()
    with pytest.raises(ValueError,match='unsupported'):
        assess_two_ground_face_line_resolution(doc,refined_panel_options=dict(panels_per_edge=256,
            ground_modes=512,interpolation_degree=24),outer_documents=[doc],
            tolerances={'R':ResolutionTolerance(relative=.01,absolute=0.)})


def test_saved_frequency_budget_precedes_fields(monkeypatch):
    monkeypatch.setattr(current,'_solver',forbidden);monkeypatch.setattr(CrossSection,'mesh',forbidden)
    request=SavedExecutionRequest(document().dumps(),max_evaluations=2)
    with pytest.raises(ValueError,match='frequency count exceeds'):request.run()


def test_cli_actual_file_run_matches_request(tmp_path):
    from sipi import cli
    doc=document();input_path=tmp_path/'input.json';output_path=tmp_path/'output.json'
    input_path.write_text(doc.dumps(),encoding='utf-8')
    assert cli.main(['run',str(input_path),'--output',str(output_path)])==0
    output=json.loads(output_path.read_text(encoding='utf-8'))
    assert output==SavedExecutionRequest(doc.dumps()).run()
    assert output['execution']['result']['current_solver']['kind']=='two-ground-corner-power-faces-all-active'
