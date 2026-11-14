# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict field-free FEM shape-line documents and common admission."""
import json
import numpy as np
import pytest
from sipi import CrossSection, CrossSectionDocument
from sipi.fem_shape_line import FEMShapeTransmissionLineDocument as Document
import sipi.fem_shape_line as api
from sipi.execution import normalize_saved, execute_saved
from sipi.execution_request import SavedExecutionRequest
from test_fem_shape_loss import geometry, F, OPTIONS
from test_layered_metal import LAYERS


def metal(sigma): return dict(conductivity=sigma,relative_permeability=1.,roughness={'kind':'smooth'})


def document(factor=1.,coated=True):
    positive=metal(58e6)
    if coated:positive=dict(kind='layered',conductivity=58e6,relative_permeability=1.,coatings=[dict(thickness_m=l.thickness_m,conductivity=l.conductivity,relative_permeability=l.relative_permeability) for l in LAYERS])
    return Document(CrossSectionDocument(geometry(),mesh={k:v*factor for k,v in OPTIONS.items()}),F,
        materials={},conductors={'positive':positive,'negative':metal(35e6)},reference=metal(58e6),ground_thickness=35e-6,length=.02)


@pytest.mark.parametrize('coated',[False,True])
def test_field_free_detached_canonical_normalization(monkeypatch,coated):
    def forbidden(*a,**kw):pytest.fail('normalization reached fields')
    monkeypatch.setattr(CrossSection,'mesh',forbidden);monkeypatch.setattr(api,'fem_shape_current_factors',forbidden)
    doc=document(coated=coated);raw=doc.dumps()
    assert raw==Document.loads(raw).dumps()==normalize_saved(raw)
    copy=doc.to_dict();copy['reference']['conductivity']=1.
    assert doc.dumps()==raw and doc.cross_section.to_dict()==doc.to_dict()['cross_section']


@pytest.mark.parametrize('where',['root','section','signal','reference','coating'])
@pytest.mark.parametrize('change',['extra','missing'])
def test_exact_keys(where,change):
    raw=document().to_dict();value={'root':raw,'section':raw['cross_section'],'mesh':raw['cross_section']['mesh'],
        'signal':raw['conductors']['negative'],'reference':raw['reference'],'coating':raw['conductors']['positive']['coatings'][0]}[where]
    if change=='extra':value['unexpected']=1
    else:value.pop(next(iter(value)))
    with pytest.raises(ValueError):Document.from_dict(raw)


@pytest.mark.parametrize('kind',['missing-signal','extra-signal','face','perfect','dc','skin','core','material','length','reference','schema','duplicate','nonfinite'])
def test_invalid_inputs_are_rejected_before_fields(monkeypatch,kind):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**kw:pytest.fail('invalid input reached mesh'))
    raw=document().to_dict()
    if kind=='missing-signal':raw['conductors'].pop('positive')
    if kind=='extra-signal':raw['conductors']['extra']=metal(58e6)
    if kind=='face':raw['reference']={'kind':'surfaces'}
    if kind=='perfect':raw['conductors']['positive']={'kind':'perfect'}
    if kind=='dc':raw['frequency_hz']=[0.]
    if kind=='skin':raw['ground_thickness_m']=1e-8
    if kind=='core':raw['conductors']['positive']['coatings'][0]['thickness_m']=.001
    if kind=='material':raw['materials']={'unknown':{'kind':'unknown'}}
    if kind=='length':raw['length_m']=-1.
    if kind=='reference':raw['reference_ohms']=0.
    if kind=='schema':raw['schema']='sipi.fem-shape-transmission-line/unsupported'
    if kind=='duplicate':
        with pytest.raises(ValueError):Document.loads('{"schema":"x",'+document().dumps()[1:])
        return
    if kind=='nonfinite':raw['length_m']=float('nan')
    with pytest.raises(ValueError):Document.loads(json.dumps(raw))


def test_frequency_budget_precedes_analyze(monkeypatch):
    monkeypatch.setattr(Document,'analyze',lambda self:pytest.fail('budget reached analyze'))
    raw=document().to_dict();raw['frequency_hz']=[2e9,3e9,5e9]
    with pytest.raises(ValueError,match='max_evaluations'):execute_saved(Document.from_dict(raw).dumps(),max_evaluations=2)


def test_request_accepts_explicit_diagnostics():
    value=SavedExecutionRequest(document().dumps(),diagnostics=('characteristic',))
    assert value.input_json==document().dumps()


def test_failed_nonfinite_observations_have_explicit_json_markers():
    cause=api.FEMShapeCurrentError('nonfinite',stage='extensions',extension_parts=np.array([np.nan,np.inf,-np.inf]),diagnostics={'bad':np.nan})
    error=api.FEMShapeLineError(cause,stage='current',input_json=document().dumps(),factors=None,mesh_observation=None)
    raw=error.to_dict();partial=raw['partial_current']
    assert partial['extension_factors_per_m']==['nan','+inf','-inf']
    assert partial['diagnostics']=={'bad':'nan'} and raw['current_solver'] is None
    assert json.loads(json.dumps(raw,allow_nan=False))==raw


def test_mesh_controls_keep_existing_optional_defaults_and_reject_unknown_keys():
    raw=document().to_dict();raw['cross_section']['mesh'].pop('edge_size')
    cross=Document.from_dict(raw).cross_section
    assert 'edge_size' not in cross.mesh_options
    assert cross.section.mesh_settings(**cross.mesh_options)['edge_size']>0
    raw['cross_section']['mesh']['unexpected']=1
    with pytest.raises(ValueError):Document.from_dict(raw)


def test_current_record_is_already_json_compatible():
    from test_fem_shape_current import plate
    factors=api.fem_shape_current_factors(*plate())
    record=api.fem_shape_current_record(factors,{})
    assert json.loads(json.dumps(record,allow_nan=False))==record
