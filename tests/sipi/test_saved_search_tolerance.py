# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved requested-mesh threshold; final physical acceptance is unchanged."""
import json
import numpy as np
import pytest
from scipy.optimize import brentq
from sipi import CrossSection, CrossSectionDocument, ImpedanceDesignDocument, seek_impedance, stripline
from sipi.execution import normalize_saved, execute_saved
from test_execution import documents
from test_material_goals import goal as material_goal
from test_sipi_references import stripline_z0

P = dict(width=.5e-3, plane_spacing=1e-3, eps_r=4.)
MESH = dict(edge_size=.5e-6, far_size=.125e-3, grade=.075)

def goal(**kw):
    options=dict(variable='width',bounds=[.3e-3,.8e-3],target=50.,tolerance=.2,
                 search_tolerance=.1,max_evaluations=20,mesh=MESH)
    options.update(kw)
    return ImpedanceDesignDocument('stripline',P,**options)

@pytest.mark.parametrize('version',[1,2,3])
def test_old_versions_stay_canonical_and_new_threshold_requires_version_four(version,monkeypatch):
    def forbidden(*a,**k): pytest.fail('Loading must not mesh')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    old=next(d for d in documents() if d.to_dict()['schema']==f'sipi.impedance-design/{version}')
    text=old.dumps();raw=old.to_dict();raw['search_tolerance_ohm']=raw['tolerance_ohm']/2
    with pytest.raises(ValueError): ImpedanceDesignDocument.from_dict(raw)
    raw['schema']='sipi.impedance-design/4'
    saved=ImpedanceDesignDocument.from_dict(raw)
    assert normalize_saved(saved.dumps())==saved.dumps()
    restored=saved.to_dict();restored.pop('search_tolerance_ohm');restored['schema']=f'sipi.impedance-design/{version}'
    assert ImpedanceDesignDocument.from_dict(restored).dumps()==text
    returned=saved.to_dict();returned['search_tolerance_ohm']=99
    assert saved.to_dict()['search_tolerance_ohm']==raw['search_tolerance_ohm']

@pytest.mark.parametrize('value',[None,0,-1,True,float('nan'),float('inf'),'.1',[],{},.2000000001])
def test_invalid_serialized_threshold_rejects_before_meshing(value,monkeypatch):
    raw=goal().to_dict();raw['search_tolerance_ohm']=value
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('Invalid input meshed'))
    with pytest.raises(ValueError): ImpedanceDesignDocument.from_dict(raw)

@pytest.mark.parametrize('edit',[
    lambda d:d.pop('search_tolerance_ohm'),lambda d:d.update(extra=1),
    lambda d:d.update(material_variables={}),lambda d:d.update(material_evaluation=None),
    lambda d:d.update(schema='sipi.impedance-design/5')])
def test_strict_v4_fields(edit):
    raw=goal().to_dict();edit(raw)
    with pytest.raises(ValueError): ImpedanceDesignDocument.from_dict(raw)

@pytest.mark.parametrize('kind',['geometry','material'])
def test_saved_threshold_reaches_existing_search_without_changing_other_options(kind,monkeypatch):
    import sipi.design_document as module
    doc=goal() if kind=='geometry' else material_goal(search_tolerance=.1)
    marker=object()
    def inspect(factory,bounds,target,**kw):
        assert kw['search_tolerance']==.1
        assert kw['tolerance']==doc.to_dict()['tolerance_ohm']
        assert kw['max_evaluations']==doc.to_dict()['max_evaluations']
        assert kw['mesh']==doc.to_dict()['mesh']
        assert 'material_factory' in kw if kind=='material' else 'material_factory' not in kw
        return marker
    monkeypatch.setattr(module,'seek_impedance',inspect)
    assert ImpedanceDesignDocument.loads(doc.dumps()).solve() is marker


def test_saved_geometry_goal_matches_direct_history_and_independent_cohn():
    doc=goal();result=doc.solve()
    direct=seek_impedance(lambda w:stripline(**{**P,'width':w}),[.3e-3,.8e-3],50.,
        tolerance=.2,search_tolerance=.1,max_evaluations=20,mesh=doc.to_dict()['mesh'])
    assert result.document.dumps()==direct.document.dumps()
    for field in ('parameter','target','impedance','refined_impedance','quantity','history','material_evaluation_json'):
        assert getattr(result,field)==getattr(direct,field)
    expected=brentq(lambda w:stripline_z0(w,1e-3,4)-50,.3e-3,.8e-3)
    assert result.parameter==pytest.approx(expected,rel=.01)
    assert abs(result.residual)<=.1 and abs(result.refined_residual)<=.2
    assert result.history[-1].stage=='refinement'
    output=execute_saved(doc.dumps(),max_evaluations=20)
    assert output['status']=='complete' and output['result']['parameter']==result.parameter


def test_execution_budget_rejects_before_solve(monkeypatch):
    monkeypatch.setattr(ImpedanceDesignDocument,'solve',lambda *a,**k:pytest.fail('Over budget'))
    with pytest.raises(ValueError,match='budget'): execute_saved(goal().dumps(),max_evaluations=19)


def test_constructor_none_preserves_version_one():
    assert goal(search_tolerance=None).to_dict()['schema']=='sipi.impedance-design/1'
