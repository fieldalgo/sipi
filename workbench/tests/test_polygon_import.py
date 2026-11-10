"""Read-only polygon import validation must not solve or rewrite geometry."""
from pathlib import Path
import copy
import json
import runpy
import sys

import pytest
import sipi

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'desktop'))
from engine import execute


@pytest.fixture(scope='module')
def cases():
    return runpy.run_path(str(Path(__file__).with_name('polygon_cases.py')))['cases']


@pytest.mark.parametrize('name',['concave','clockwise','asymmetric-pair','normal-film'])
def test_v3_import_validation_preserves_vertices_materials_and_mesh_without_solving(cases,name,monkeypatch):
    monkeypatch.setattr(sipi.CrossSection,'mesh',lambda *a,**k:pytest.fail('Validation attempted a field solve'))
    original=copy.deepcopy(cases[name]);raw=json.dumps(original)
    output=execute(dict(action='document',document_text=raw))
    assert output['document']==original and cases[name]==original
    assert execute(dict(action='document',document=output['document']))['document']==original
    assert output['document']['schema']=='sipi.cross-section/3'


@pytest.mark.parametrize('failure',['duplicate','nonfinite','self-intersection','outside-region'])
def test_invalid_v3_input_fails_before_meshing(cases,failure,monkeypatch):
    monkeypatch.setattr(sipi.CrossSection,'mesh',lambda *a,**k:pytest.fail('Invalid geometry attempted a solve'))
    doc=copy.deepcopy(cases['concave'])
    if failure=='self-intersection':doc['traces'][0]['vertices']=[[0,.0008],[.0003,.0012],[0,.0012],[.0003,.0008]]
    if failure=='outside-region':doc['dielectric_regions'][0]['vertices'][0][0]=-.1
    raw=json.dumps(doc)
    if failure=='duplicate':raw=raw.replace('"schema":', '"schema":"sipi.cross-section/3","schema":',1)
    if failure=='nonfinite':raw=raw.replace('0.00035','NaN',1)
    with pytest.raises(ValueError):execute(dict(action='document',document_text=raw))


def test_display_layer_limit_does_not_change_engine_geometry_contract(cases,monkeypatch):
    monkeypatch.setattr(sipi.CrossSection,'mesh',lambda *a,**k:pytest.fail('Validation attempted a solve'))
    doc=copy.deepcopy(cases['normal-film'])
    doc['layers']=[dict(name='layer'+str(i),thickness=.005/65,eps_r=4,tan_delta=0) for i in range(65)]
    assert execute(dict(action='document',document=doc))['document']==doc
