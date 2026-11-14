# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict saved FEM factories, constraint mapping and field-free budgets."""
import json
import pytest
from sipi import CrossSection
from sipi.fem_shape_goal_document import FEMShapeLineQuantityDesignDocument as Document
from sipi.fem_shape_study import FEMShapeLineQuantityStudyDocument
from sipi.study import ImpedanceStudyDocument
from sipi.execution import normalize_saved,execute_saved
from sipi.execution_request import SavedExecutionRequest
from test_fem_shape_study import document as sampling,source,MESH
import sipi.fem_shape_goal_document as api


def document(paired=False):
    return Document(sampling('differential_forward_impedance_real' if paired else 'impedance_real'),
        target=92.8 if paired else 70.35,tolerance=.2,max_evaluations=12)


@pytest.mark.parametrize('paired',[False,True])
def test_field_free_detached_roundtrip(monkeypatch,paired):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('normalization meshed'))
    doc=document(paired);text=doc.dumps();assert text==Document.loads(text).dumps()==normalize_saved(text)
    assert SavedExecutionRequest(text).input_json==text and doc.study.to_dict()==doc.to_dict()['study']
    raw=doc.to_dict();raw['target']=1.;assert doc.dumps()==text


@pytest.mark.parametrize('kind',['extra','missing','schema','target','tolerance','budget','kind','count','variables','bounds','duplicate','nonfinite'])
def test_strict_invalid_inputs_before_fields(monkeypatch,kind):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('invalid input meshed'))
    raw=document().to_dict();s=raw['study']['study']['sampling']
    if kind=='extra':raw['extra']=0
    if kind=='missing':raw.pop('tolerance')
    if kind=='schema':raw['schema']='bad'
    if kind=='target':raw['target']=0
    if kind=='tolerance':raw['tolerance']=0
    if kind=='budget':raw['max_evaluations']=2
    if kind=='kind':s['kind']='corners';s.pop('count')
    if kind=='count':s['count']=3
    if kind=='variables':s['variables'].append(dict(name='box_width',lower=.007,upper=.009))
    if kind=='bounds':s['variables'][0]['lower']=0
    if kind=='duplicate':
        with pytest.raises(ValueError):Document.loads('{"target":1,'+document().dumps()[1:])
        return
    if kind=='nonfinite':raw['target']=float('nan')
    with pytest.raises(ValueError):Document.loads(json.dumps(raw))


def test_saved_budget_precedes_goal_work(monkeypatch):
    monkeypatch.setattr(Document,'solve',lambda self:pytest.fail('budget invoked goal'))
    with pytest.raises(ValueError,match='max_evaluations'):execute_saved(document().dumps(),max_evaluations=11)


def test_source_study_is_not_analyzed_and_material_variable_factory_is_exact(monkeypatch):
    doc=Document(sampling('attenuation',material=True),target=1.,tolerance=.1,max_evaluations=12)
    monkeypatch.setattr(FEMShapeLineQuantityStudyDocument,'analyze',lambda *a,**k:pytest.fail('source study ran'))
    captured=[]
    def seek(factory,bounds,target,**options):
        for value in (bounds[0],sum(bounds)/2,bounds[1]):captured.append(factory(value).to_dict())
        assert bounds==[.01,.03] and target==1. and options['quantity']=='attenuation';return 'verified factory'
    monkeypatch.setattr(api,'seek_fem_shape_line_quantity',seek)
    assert doc.solve()=='verified factory'
    for raw,loss in zip(captured,(.01,.02,.03)):
        assert raw['materials']['dielectric']['parameters']['tan_delta']==loss
        assert raw['length_m']==0 and raw['conductors']==doc.study.to_dict()['conductors']


def test_fixed_pitch_survives_every_factory_input(monkeypatch):
    raw=sampling('differential_forward_impedance_real').to_dict()
    raw['study']=ImpedanceStudyDocument('coupled_stripline',source(True).to_dict()['parameters'],
        quantity='z_diff_forward',frequency=2e9,materials={},mesh=MESH,fixed_pitch_m=.0007,
        sampling=source(True).to_dict()['sampling']).to_dict()
    doc=Document(FEMShapeLineQuantityStudyDocument.from_dict(raw),target=92.8,tolerance=.2)
    def seek(factory,bounds,target,**options):
        for value in (*bounds,sum(bounds)/2):
            traces=factory(value).cross_section.section.traces
            assert abs(traces[1].x-traces[0].x)==pytest.approx(.0007,rel=1e-15)
        return True
    monkeypatch.setattr(api,'seek_fem_shape_line_quantity',seek);assert doc.solve()


def test_diagnostics_rejected_for_saved_goal():
    with pytest.raises(ValueError):SavedExecutionRequest(document().dumps(),diagnostics=('characteristic',))
