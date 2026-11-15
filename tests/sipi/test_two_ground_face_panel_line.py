# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
import copy
import json
import numpy as np
import pytest
from sipi import CrossSection,CrossSectionDocument,Layer,Trace
from sipi.constants import epsilon_0,mu_0
from sipi.two_ground_face_panel_line import (TwoGroundFacePanelTransmissionLineDocument as Document,
    TwoGroundFacePanelLineError)
from sipi.two_ground_panel_line import TwoGroundPanelTransmissionLineDocument
from sipi.two_ground_face_conductor import two_ground_conductor_loss_by_face
from sipi.shape_face_panel_line import _metals
import sipi.two_ground_face_panel_line as module
import sipi.two_ground_face_conductor as current
from test_two_ground_panel_line import independent_network

F=[1e9,3e9,10e9]


def metal(sigma=58e6):
    return dict(conductivity=sigma,relative_permeability=1.,roughness=dict(kind='smooth'))


def faces():
    return dict(zip(('bottom','top','left','right'),[metal(x) for x in (58e6,35e6,21e6,45e6)]))


def document(kind='scalar'):
    if kind=='scalar':traces=[Trace('signal',x=.0002,width=.0006,y=.0007,thickness=.00005,top_width=.00055)]
    else:
        traces=[Trace('left',x=-.0004,width=.0003,y=.0007,thickness=.00005,top_width=.00028),
                Trace('right',x=.0004,width=.0003,y=.0009,thickness=.00006,top_width=.00032)]
        if kind=='guard':traces.insert(1,Trace('guard',x=0.,width=.0002,y=.001,thickness=.00005,ground=True))
    sec=CrossSection([Layer('uniform',.002,4.,tan_delta=.003)],traces,.008,top='ground')
    ref=dict(kind='surfaces',bottom=metal(45e6),top=metal(21e6),sides=None,
             conductors={'guard':dict(kind='faces',**faces())} if kind=='guard' else {})
    conductors={t.name:faces() for t in traces if not t.ground}
    conductors[next(iter(conductors))]['top']=dict(kind='layered',conductivity=58e6,relative_permeability=1.,
        coatings=[dict(thickness_m=2e-7,conductivity=14e6,relative_permeability=3.)])
    return Document(CrossSectionDocument(sec,mesh=dict(edge_size=5e-6,far_size=.0001,grade=.05)),
        F,materials={},conductors=conductors,reference=ref,ground_thickness=35e-6,
        length=.02,panels_per_edge=64,interpolation_degree=16)


def forbidden(*args,**kwargs):pytest.fail('field solve reached')


def test_detached_field_free_roundtrip_and_separate_schema(monkeypatch):
    monkeypatch.setattr(current,'_solver',forbidden);monkeypatch.setattr(CrossSection,'mesh',forbidden)
    for kind in ('scalar','pair','guard'):
        doc=document(kind);text=doc.dumps();assert Document.loads(text).dumps()==text
        raw=doc.to_dict();raw['reference']['top']['conductivity']=1
        doc.current_options['ground_modes']=64
        assert doc.dumps()==text
        with pytest.raises(ValueError,match='unsupported'):TwoGroundPanelTransmissionLineDocument.from_dict(doc.to_dict())


@pytest.mark.parametrize('where',['root','panel','section','signal','face','reference','top','ground','coating'])
@pytest.mark.parametrize('change',['extra','missing'])
def test_strict_nested_keys(where,change,monkeypatch):
    monkeypatch.setattr(current,'_solver',forbidden);monkeypatch.setattr(CrossSection,'mesh',forbidden)
    raw=document('guard').to_dict();target={'root':raw,'panel':raw['panel'],'section':raw['cross_section'],
        'signal':raw['conductors']['left'],'face':raw['conductors']['right']['bottom'],
        'reference':raw['reference'],'top':raw['reference']['top'],
        'ground':raw['reference']['conductors']['guard'],
        'coating':raw['conductors']['left']['top']['coatings'][0]}[where]
    if change=='extra':target['unexpected']=1
    else:target.pop(next(iter(target)))
    with pytest.raises((ValueError,TypeError)):Document.from_dict(raw)


@pytest.mark.parametrize('case',['schema','duplicate','nonfinite','bad-panel','bad-degree','bad-modes',
    'missing-top','side-metal','signal-name','dc','length','zref','skin','core','material-name','wall','polygon'])
def test_invalid_input_stops_before_fields(monkeypatch,case):
    monkeypatch.setattr(current,'_solver',forbidden);monkeypatch.setattr(CrossSection,'mesh',forbidden)
    raw=document().to_dict()
    if case=='schema':raw['schema']='sipi.two-ground-panel-transmission-line/1'
    elif case=='bad-panel':raw['panel']['panels_per_edge']=False
    elif case=='bad-degree':raw['panel']['interpolation_degree']=11
    elif case=='bad-modes':raw['panel']['ground_modes']=63
    elif case=='missing-top':raw['reference']['top']=None
    elif case=='side-metal':raw['reference']['sides']=metal()
    elif case=='signal-name':raw['conductors']['extra']=faces()
    elif case=='dc':raw['frequency_hz'][0]=0
    elif case=='length':raw['length_m']=-1
    elif case=='zref':raw['reference_ohms']=0
    elif case=='skin':raw['ground_thickness_m']=1e-8
    elif case=='core':raw['conductors']['signal']['top']['coatings'][0]['thickness_m']=.001
    elif case=='material-name':raw['materials']={'missing':dict(kind='constant',epsilon_r=4.,tan_delta=0.)}
    elif case=='wall':raw['cross_section']['box']['top']='open'
    elif case=='polygon':
        from sipi import PolygonTrace
        sec=document().cross_section.section;t=sec.traces[0]
        cross=CrossSectionDocument(CrossSection(sec.layers,[PolygonTrace(t.name,t.corners())],sec.width,top='ground'),mesh=document().cross_section.mesh_options)
        raw['cross_section']=cross.to_dict()
    text=json.dumps(raw)
    if case=='duplicate':text=text.replace('"length_m": 0.02','"length_m": 0.02, "length_m": 0.02')
    if case=='nonfinite':text=text.replace('"length_m": 0.02','"length_m": NaN')
    with pytest.raises((ValueError,TypeError)):Document.loads(text)


@pytest.fixture(scope='module')
def observations():
    return [(document(kind),document(kind).analyze()) for kind in ('scalar','pair','guard')]


def test_actual_three_lines_same_geometry_materials_and_independent_network(observations,record_property):
    records=[]
    for doc,result in observations:
        data=doc.to_dict();f=result.frequency;n=len(result.names);factor=result.current_factors
        assert result.current_record()['kind']=='two-ground-rectangle-face-panels'
        assert result.current_record()['whole_current']['kind']=='two-ground-rectangle-panels'
        np.testing.assert_allclose(result.C,4*np.broadcast_to(factor.C0,result.C.shape),rtol=1e-12,atol=0)
        np.testing.assert_allclose(result.G,2*np.pi*f[:,None,None]*.003*result.C,rtol=1e-12,atol=0)
        np.testing.assert_allclose(result.dielectric.L@factor.C0,mu_0*epsilon_0*np.eye(n),rtol=1e-10,atol=1e-28)
        conductors,reference,_,_=_metals(data)
        direct=two_ground_conductor_loss_by_face(doc.cross_section.section,f,conductors=conductors,reference=reference,
            ground_thickness=data['ground_thickness_m'],**doc.current_options)
        np.testing.assert_array_equal(result.R,direct.R)
        np.testing.assert_array_equal(result.conductor.L_internal,direct.L_internal)
        for i,x in enumerate(f):
            network=independent_network(x,result.R[i],result.L[i],result.G[i],result.C[i],.02,50.)
            np.testing.assert_allclose(result.network.s[i],network,rtol=1e-10,atol=1e-12)
        assert np.max(np.linalg.svd(result.network.s,compute_uv=False))<=1+1e-10
        assert result.input_json==doc.dumps() and result.mesh_record()['nodes']>0
        for item in (result.current_record(),result.mesh_record()):item.clear()
        assert result.current_record() and result.mesh_record()
        with pytest.raises(TypeError):result.panel_settings['panels_per_edge']=4
        records.append(dict(input=data,R=result.R.tolist(),L=result.L.tolist(),C=result.C.tolist(),G=result.G.tolist(),
            current=result.current_record(),mesh=result.mesh_record(),s_real=result.network.s.real.tolist(),s_imag=result.network.s.imag.tolist()))
    record_property('face_lines',json.dumps(records,sort_keys=True))


@pytest.mark.parametrize('stage',['current','mesh','dielectric','network'])
def test_failed_stages_retain_completed_face_and_mesh_work(monkeypatch,stage):
    def broken(*a,**k):raise ArithmeticError('deliberate '+stage)
    name={'current':'two_ground_conductor_loss_by_face','mesh':'_reuse_mesh','dielectric':'_dispersive_from_mesh','network':'rlgc_network'}[stage]
    monkeypatch.setattr(module,name,broken)
    doc=document()
    with pytest.raises(TwoGroundFacePanelLineError) as caught:doc.analyze()
    error=caught.value;record=error.to_dict()
    assert error.stage==stage and record['cause_type']=='ArithmeticError' and record['input']==doc.to_dict()
    assert (record['current_solver'] is not None)==(stage!='current')
    assert (record['dielectric_mesh'] is not None)==(stage in ('dielectric','network'))
    if record['current_solver']:
        assert record['current_solver']['labels'] and record['current_solver']['whole_current']['boundary_labels']
    record.clear();assert error.to_dict()['stage']==stage


def test_nonuniform_dielectric_fields_match_same_geometry_whole_line():
    face=document();raw=face.to_dict();cross=face.cross_section
    layered=CrossSection([Layer('lower',.001,3.),Layer('upper',.001,7.,tan_delta=.01)],
                         cross.section.traces,cross.section.width,top='ground')
    raw['cross_section']=CrossSectionDocument(layered,mesh=cross.mesh_options).to_dict()
    face=Document.from_dict(raw)
    whole_raw=copy.deepcopy(raw);whole_raw['schema']='sipi.two-ground-panel-transmission-line/1'
    whole_raw['conductors']={name:parts['bottom'] for name,parts in raw['conductors'].items()}
    whole=TwoGroundPanelTransmissionLineDocument.from_dict(whole_raw)
    a,b=face.analyze(),whole.analyze()
    for key in ('C','G'):np.testing.assert_array_equal(getattr(a,key),getattr(b,key))
    np.testing.assert_array_equal(a.dielectric.L,b.dielectric.L)
    np.testing.assert_array_equal(a.current_factors.C0,b.current_factors.C0)
    assert a.mesh_record()==b.mesh_record()
    assert np.max(abs(a.G))>0
