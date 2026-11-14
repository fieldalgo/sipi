# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict saved reference metals; normalization never solves a field."""
import json
import pytest
from sipi import CrossSection,CrossSectionDocument
from sipi.shape_reference_panel_line import ShapeReferencePanelTransmissionLineDocument as Document
from sipi.execution import normalize_saved,execute_saved
import sipi.panel_shape_conductor as current
from test_panel_shape_conductor import guard
from test_layered_panel_goal import material


def metal(sigma):return dict(conductivity=sigma,relative_permeability=1.,roughness={'kind':'smooth'})


def document(coated=False,panels=16):
    return Document(CrossSectionDocument(guard(permittivity=4.),mesh=dict(edge_size=10e-6,far_size=.0005,grade=.1)),
        [1e9,4e9,16e9],materials={},conductors={'a':metal(58e6),'b':metal(35e6)},
        reference=dict(kind='surfaces',bottom=metal(45e6),top=None,sides=None,
            conductors={'guard':material() if coated else metal(20e6)}),
        ground_thickness=35e-6,length=.02,panels_per_edge=panels,ground_modes=1024)


@pytest.mark.parametrize('coated',[False,True])
def test_detached_field_free_canonical_input(monkeypatch,coated):
    def forbidden(*a,**k):pytest.fail('normalization reached fields')
    monkeypatch.setattr(CrossSection,'mesh',forbidden);monkeypatch.setattr(current,'_panel_solver',forbidden)
    doc=document(coated);text=doc.dumps();assert text==normalize_saved(text)==Document.loads(text).dumps()
    copy=doc.to_dict();copy['reference']['conductors']['guard']['conductivity']=1.
    doc.current_options['step_fraction']=.01
    assert doc.dumps()==text
    assert doc.cross_section.to_dict()==doc.to_dict()['cross_section']


@pytest.mark.parametrize('where',['root','panel','section','signal','reference','ground','coating'])
@pytest.mark.parametrize('change',['extra','missing'])
def test_exact_nested_keys(where,change):
    raw=document(True).to_dict();ref=raw['reference']
    value={'root':raw,'panel':raw['panel'],'section':raw['cross_section'],'signal':raw['conductors']['a'],
        'reference':ref,'ground':ref['conductors']['guard'],'coating':ref['conductors']['guard']['coatings'][0]}[where]
    if change=='extra':value['unexpected']=1
    else:value.pop(next(iter(value)))
    with pytest.raises(ValueError):Document.from_dict(raw)


@pytest.mark.parametrize('kind',['missing-signal','extra-signal','missing-ground','extra-ground','face-ground',
    'no-bottom','top','sides','plane-skin','ground-skin','signal-skin','ground-core','plane-core','signal-core',
    'common-reference','perfect','dc','negative-length','reference-zero','bad-step','bad-panel','bad-material',
    'wall','nonconvex','duplicate','nonfinite','unknown-schema'])
def test_invalid_input_refused_before_fields(monkeypatch,kind):
    def forbidden(*a,**k):pytest.fail('invalid input reached fields')
    monkeypatch.setattr(CrossSection,'mesh',forbidden);monkeypatch.setattr(current,'_panel_solver',forbidden)
    raw=document().to_dict();ref=raw['reference'];signals=raw['conductors'];ground=ref['conductors']
    if kind=='missing-signal':signals.pop('a')
    if kind=='extra-signal':signals['extra']=metal(58e6)
    if kind=='missing-ground':ground.clear()
    if kind=='extra-ground':ground['extra']=metal(58e6)
    if kind=='face-ground':ground['guard']=dict(kind='faces',**{n:metal(58e6) for n in ('bottom','top','left','right')})
    if kind=='no-bottom':ref['bottom']=None
    if kind in ('top','sides'):ref[kind]=metal(58e6)
    if kind=='plane-skin':raw['ground_thickness_m']=1e-7
    if kind=='ground-skin':ground['guard']=metal(1.)
    if kind=='signal-skin':signals['a']=metal(1.)
    if kind.endswith('-core'):
        m=material();m['coatings'][0]['thickness_m']=.001
        if kind=='ground-core':ground['guard']=m
        elif kind=='plane-core':ref['bottom']=m
        else:signals['a']=m
    if kind=='common-reference':raw['reference']=metal(58e6)
    if kind=='perfect':raw['conductors']={'kind':'perfect'}
    if kind=='dc':raw['frequency_hz'][0]=0.
    if kind=='negative-length':raw['length_m']=-1.
    if kind=='reference-zero':raw['reference_ohms']=0.
    if kind=='bad-step':raw['step_fraction']=True
    if kind=='bad-panel':raw['panel']['panels_per_edge']=2.
    if kind=='bad-material':raw['materials']={'missing':{'kind':'constant','epsilon_r':4.,'tan_delta':0.}}
    if kind=='wall':raw['cross_section']['box']['top']='ground'
    if kind=='nonconvex':raw['cross_section']['traces'][0]['thickness']=0.
    text=json.dumps(raw)
    if kind=='duplicate':text=text.replace('"step_fraction": 0.001','"step_fraction": 0.001, "step_fraction": 0.001')
    if kind=='nonfinite':text=text.replace('"step_fraction": 0.001','"step_fraction": NaN')
    if kind=='unknown-schema':text=text.replace('sipi.shape-reference-panel-transmission-line/1','sipi.shape-reference-panel-transmission-line/2')
    with pytest.raises((ValueError,TypeError)):Document.loads(text)


def test_frequency_budget_precedes_solve(monkeypatch):
    doc=document();monkeypatch.setattr(Document,'analyze',lambda s:pytest.fail('budget reached fields'))
    with pytest.raises(ValueError,match='before any field solve'):execute_saved(doc.dumps(),max_evaluations=2)


def test_each_reference_uses_its_own_thickness_for_skin_admission():
    raw=document().to_dict();raw['ground_thickness_m']=15e-6
    raw['reference']['conductors']['guard']=metal(3e6)
    # At 1 GHz this ground trace has depth 9.19 um: below its 10 um
    # bound, above the plane's 3 um bound. No shared minimum is substituted.
    accepted=Document.from_dict(raw)
    assert accepted.to_dict()['reference']['conductors']['guard']['conductivity']==3e6
    raw['reference']['bottom']=metal(3e6)
    with pytest.raises(ValueError,match='reference:bottom'):Document.from_dict(raw)
