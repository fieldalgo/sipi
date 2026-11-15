# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict saved corner goals and unchanged physical factory transformations."""
from dataclasses import FrozenInstanceError
import json
import pytest
from sipi import CrossSection, CornerFEMShapeLineQuantityDesignDocument as Document
from sipi.execution import normalize_saved,execute_saved
from sipi.execution_request import SavedExecutionRequest
from sipi.fem_shape_goal_document import FEMShapeLineQuantityDesignDocument
from sipi.fem_shape_study import FEMShapeLineQuantityStudyDocument
from sipi.study import ImpedanceStudyDocument
from test_fem_shape_goal_document import document as original
from test_fem_shape_study import document as sampling,source,MESH
import sipi.corner_fem_goal_document as api


def document(paired=False):return Document(original(paired),2.5e-6)


@pytest.mark.parametrize('bad',[None,True,0.,-1.,float('nan'),float('inf'),'1e-6',1e-5])
def test_bad_corner_precedes_fields(bad,monkeypatch):
    raw=document().to_dict();raw['corner_size']=bad
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('invalid corner meshed'))
    with pytest.raises(ValueError):Document.from_dict(raw)


@pytest.mark.parametrize('change',['extra','missing','schema','nested','edge','budget','variables','nonfinite'])
def test_strict_nested_contract_before_fields(change,monkeypatch):
    raw=document().to_dict();design=raw['design']
    if change=='extra':raw['result']={}
    elif change=='missing':del raw['design']
    elif change=='schema':raw['schema']='sipi.corner-fem-shape-line-quantity-design/2'
    elif change=='nested':design['corner_size']=1e-6
    elif change=='edge':design['study']['study']['mesh']['edge_size']=1e-6
    elif change=='budget':design['max_evaluations']=2
    elif change=='variables':design['study']['study']['sampling']['count']=3
    else:design['target']=float('nan')
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('invalid goal meshed'))
    with pytest.raises(ValueError):Document.loads(json.dumps(raw))


@pytest.mark.parametrize('paired',[False,True])
def test_snapshot_roundtrip_and_original_rejection(paired,monkeypatch):
    saved=document(paired);text=saved.dumps()
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('normalization meshed'))
    assert normalize_saved(text)==Document.loads(text).dumps()==text
    raw=saved.to_dict();raw['corner_size']=999
    nested=saved.design.to_dict();nested['target']=999
    assert saved.dumps()==text and saved.corner_size==2.5e-6
    with pytest.raises(FrozenInstanceError):saved._data_json='{}'
    with pytest.raises(ValueError,match='duplicate'):Document.loads('{"corner_size":1e-6,'+text[1:])
    with pytest.raises(ValueError):FEMShapeLineQuantityDesignDocument.from_dict(saved.to_dict())
    with pytest.raises(TypeError):Document({},1e-6)


def test_nested_budget_and_diagnostics_precede_solves(monkeypatch):
    monkeypatch.setattr(Document,'solve',lambda *a:pytest.fail('budget invoked goal'))
    with pytest.raises(ValueError,match='before any solve'):execute_saved(document().dumps(),max_evaluations=11)
    with pytest.raises(ValueError):SavedExecutionRequest(document().dumps(),diagnostics=('characteristic',))


def test_material_factory_keeps_corner_and_never_samples_study(monkeypatch):
    saved=Document(FEMShapeLineQuantityDesignDocument(sampling('attenuation',material=True),target=1.,tolerance=.1,max_evaluations=12),2.5e-6)
    monkeypatch.setattr(FEMShapeLineQuantityStudyDocument,'analyze',lambda *a,**k:pytest.fail('source study ran'))
    def seek(factory,bounds,target,**options):
        assert bounds==[.01,.03] and target==1. and options==dict(quantity='attenuation',tolerance=.1,max_evaluations=12)
        for value in (*bounds,sum(bounds)/2):
            doc=factory(value);raw=doc.line.to_dict()
            assert doc.corner_size==2.5e-6
            assert raw['materials']['dielectric']['parameters']['tan_delta']==value
            assert raw['length_m']==0 and raw['conductors']==saved.design.study.to_dict()['conductors']
        return True
    monkeypatch.setattr(api,'seek_corner_fem_shape_line_quantity',seek);assert saved.solve()


def test_fixed_pitch_factory_retains_separate_corner(monkeypatch):
    raw=sampling('differential_forward_impedance_real').to_dict()
    raw['study']=ImpedanceStudyDocument('coupled_stripline',source(True).to_dict()['parameters'],quantity='z_diff_forward',frequency=2e9,materials={},mesh=MESH,fixed_pitch_m=.0007,sampling=source(True).to_dict()['sampling']).to_dict()
    saved=Document(FEMShapeLineQuantityDesignDocument(FEMShapeLineQuantityStudyDocument.from_dict(raw),target=92.8,tolerance=.2),2.5e-6)
    def seek(factory,bounds,target,**options):
        for value in (*bounds,sum(bounds)/2):
            doc=factory(value);traces=doc.cross_section.section.traces
            assert abs(traces[1].x-traces[0].x)==pytest.approx(.0007,rel=1e-15) and doc.corner_size==2.5e-6
        return True
    monkeypatch.setattr(api,'seek_corner_fem_shape_line_quantity',seek);assert saved.solve()
