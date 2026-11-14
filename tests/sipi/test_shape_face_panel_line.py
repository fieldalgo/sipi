# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict saved face laws and field-free material/offset admission."""
import json
import pytest
from sipi import CrossSection,CrossSectionDocument,Layer
from sipi.shape_face_panel_line import ShapeFacePanelTransmissionLineDocument as Document
from sipi.execution import normalize_saved,execute_saved
import sipi.panel_shape_conductor as whole
import sipi.panel_shape_face_conductor as face
from test_shape_face_conductor import geometry,F,OPTIONS
from test_shape_reference_panel_line import metal
from test_layered_panel_goal import material

FACES=('bottom','top','left','right')


def document(panels=32,ground_faces=True):
    s=geometry();s=CrossSection([Layer('u',s.height,4.)],s.traces,s.width)
    signals={'a':dict(zip(FACES,[metal(58e6),material(),metal(35e6),metal(20e6)])),
             'b':{f:metal(45e6) for f in FACES}}
    ground=dict(kind='faces',**dict(zip(FACES,[metal(s) for s in (30e6,40e6,50e6,60e6)]))) if ground_faces else metal(30e6)
    return Document(CrossSectionDocument(s,mesh=dict(edge_size=10e-6,far_size=.0005,grade=.1)),F,materials={},conductors=signals,
        reference=dict(kind='surfaces',bottom=metal(48e6),top=None,sides=None,conductors={'guard':ground}),
        ground_thickness=35e-6,length=.02,panels_per_edge=panels,**OPTIONS)


@pytest.mark.parametrize('ground_faces',[False,True])
def test_detached_field_free_canonical_input(monkeypatch,ground_faces):
    def forbidden(*a,**k):pytest.fail('normalization reached fields')
    monkeypatch.setattr(CrossSection,'mesh',forbidden);monkeypatch.setattr(whole,'_panel_solver',forbidden);monkeypatch.setattr(face,'_panel_solver',forbidden)
    doc=document(ground_faces=ground_faces);text=doc.dumps();assert text==normalize_saved(text)==Document.loads(text).dumps()
    copy=doc.to_dict();copy['conductors']['a']['top']['conductivity']=1.
    doc.current_options['step_fraction']=.01
    assert doc.dumps()==text and doc.cross_section.to_dict()==doc.to_dict()['cross_section']


@pytest.mark.parametrize('where',['root','panel','section','signal','signal-metal','reference','ground','ground-metal','coating'])
@pytest.mark.parametrize('change',['missing','extra'])
def test_exact_nested_keys(where,change):
    raw=document().to_dict();ref=raw['reference'];signal=raw['conductors']['a']
    v={'root':raw,'panel':raw['panel'],'section':raw['cross_section'],'signal':signal,'signal-metal':signal['bottom'],
       'reference':ref,'ground':ref['conductors']['guard'],'ground-metal':ref['conductors']['guard']['bottom'],
       'coating':signal['top']['coatings'][0]}[where]
    if change=='extra':v['unexpected']=1
    else:v.pop(next(iter(v)))
    with pytest.raises(ValueError):Document.from_dict(raw)


@pytest.mark.parametrize('kind',['missing-signal','extra-signal','signal-whole','missing-ground','extra-ground','no-bottom','top','sides',
    'plane-skin','ground-face-skin','signal-face-skin','ground-face-core','plane-core','signal-face-core','common-reference','perfect',
    'dc','negative-length','reference-zero','bad-step','bad-panel','bad-material','wall','zero','duplicate','nonfinite','unknown-schema'])
def test_invalid_input_is_rejected_before_fields(monkeypatch,kind):
    def forbidden(*a,**k):pytest.fail('invalid input reached fields')
    monkeypatch.setattr(CrossSection,'mesh',forbidden);monkeypatch.setattr(whole,'_panel_solver',forbidden);monkeypatch.setattr(face,'_panel_solver',forbidden)
    raw=document().to_dict();ref=raw['reference'];signals=raw['conductors'];ground=ref['conductors']
    if kind=='missing-signal':signals.pop('a')
    if kind=='extra-signal':signals['extra']=signals['a']
    if kind=='signal-whole':signals['a']=metal(58e6)
    if kind=='missing-ground':ground.clear()
    if kind=='extra-ground':ground['extra']=metal(58e6)
    if kind=='no-bottom':ref['bottom']=None
    if kind in ('top','sides'):ref[kind]=metal(58e6)
    if kind=='plane-skin':raw['ground_thickness_m']=1e-7
    if kind=='ground-face-skin':ground['guard']['left']=metal(1.)
    if kind=='signal-face-skin':signals['a']['right']=metal(1.)
    if kind.endswith('-core'):
        m=material();m['coatings'][0]['thickness_m']=.001
        if kind=='ground-face-core':ground['guard']['bottom']=m
        elif kind=='plane-core':ref['bottom']=m
        else:signals['a']['top']=m
    if kind=='common-reference':raw['reference']=metal(58e6)
    if kind=='perfect':raw['conductors']={'kind':'perfect'}
    if kind=='dc':raw['frequency_hz'][0]=0.
    if kind=='negative-length':raw['length_m']=-1.
    if kind=='reference-zero':raw['reference_ohms']=0.
    if kind=='bad-step':raw['step_fraction']=True
    if kind=='bad-panel':raw['panel']['panels_per_edge']=2.
    if kind=='bad-material':raw['materials']={'missing':{'kind':'constant','epsilon_r':4.,'tan_delta':0.}}
    if kind=='wall':raw['cross_section']['box']['top']='ground'
    if kind=='zero':raw['cross_section']['traces'][0]['thickness']=0.
    text=json.dumps(raw)
    if kind=='duplicate':text=text.replace('"step_fraction": 0.001','"step_fraction": 0.001, "step_fraction": 0.001')
    if kind=='nonfinite':text=text.replace('"step_fraction": 0.001','"step_fraction": NaN')
    if kind=='unknown-schema':text=text.replace('sipi.shape-face-panel-transmission-line/1','sipi.shape-face-panel-transmission-line/2')
    with pytest.raises((ValueError,TypeError)):Document.loads(text)


def test_frequency_budget_precedes_fields(monkeypatch):
    doc=document();monkeypatch.setattr(Document,'analyze',lambda s:pytest.fail('budget reached fields'))
    with pytest.raises(ValueError,match='before any field solve'):execute_saved(doc.dumps(),max_evaluations=2)


def test_overlapping_face_offsets_reject_without_fields(monkeypatch):
    doc=document();raw=doc.to_dict();s=raw['cross_section']['traces'];s[0]['x']=-.0002500001;s[0]['top_width']=s[0]['width'];s[1]['top_width']=s[1]['width']
    # The unperturbed bottom edges have a tiny positive gap; outward offsets overlap.
    monkeypatch.setattr(whole,'_panel_solver',lambda:pytest.fail('preflight reached fields'))
    with pytest.raises(ValueError):Document.from_dict(raw)
