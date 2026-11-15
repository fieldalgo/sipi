# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Request-local geometry reuse keeps every independent material sample."""
from contextlib import nullcontext
import importlib
import json

import numpy as np
import pytest
from sipi import CrossSection, CrossSectionDocument
from sipi.dielectric import DebyeDielectric, dielectric_to_dict
from sipi.execution_request import SavedExecutionRequest
import sipi._two_ground_current_reuse as current_scope
import sipi._two_ground_mesh_reuse as mesh_scope


def document(kind):
    if kind=='scalar':
        from test_two_ground_line_study import document as make
        doc=make('attenuation',physical=True)
    elif kind=='pair':
        from test_two_ground_pair_study import document as make
        doc=make(physical=True)
    else:
        from test_two_ground_sampled_pair_study import document as make
        doc=make(frequencies=[2e9,3.5e9,5e9],physical=True)
    raw=doc.to_dict();study=raw['study'];study['schema']='sipi.impedance-study/4'
    study['parameters']['width']=.0006 if kind=='scalar' else .00043
    if kind!='scalar':study['parameters']['gap']=.00028
    study['material_evaluation']['materials']={'dielectric':dielectric_to_dict(DebyeDielectric(3.,(.7,),(1e9,)))}
    study['material_variables']={'strength':dict(region='dielectric',path=['strengths',0])}
    study['sampling']=dict(kind='uniform',count=4,seed=19,variables=[dict(name='strength',lower=.5,upper=.9)])
    return type(doc).from_dict(raw)


def module(kind):
    return importlib.import_module('sipi.two_ground_'+{'scalar':'line','pair':'pair','grid':'sampled_pair'}[kind]+'_study')


@pytest.mark.parametrize('kind',['scalar','pair','grid'])
def test_actual_four_material_rows_keep_full_receipt_with_one_geometry_solve(monkeypatch,kind,record_property):
    import galerkin.laplace_two_ground as shared
    from sipi.two_ground_panel_line import TwoGroundPanelTransmissionLineDocument as Line
    doc=document(kind);request=SavedExecutionRequest(doc.dumps(),max_evaluations=4)
    solve=shared.solve_two_ground_rectangle;generate=CrossSection.mesh;analyze=Line.analyze
    currents=[];meshes=[];fields=[]
    def current(polygons,*,width,height,panels_per_edge=32,ground_modes=128,interpolation_degree=12):
        currents.append(dict(polygons=[p.tolist() for p in polygons],width=width,height=height,
            panels=panels_per_edge,modes=ground_modes,degree=interpolation_degree))
        return solve(polygons,width=width,height=height,panels_per_edge=panels_per_edge,
            ground_modes=ground_modes,interpolation_degree=interpolation_degree)
    def mesh(self,**options):
        meshes.append(CrossSectionDocument(self,mesh=options).dumps());return generate(self,**options)
    def line(self):
        result=analyze(self);fields.append(dict(C=result.C.tolist(),G=result.G.tolist()));return result
    monkeypatch.setattr(shared,'solve_two_ground_rectangle',current);monkeypatch.setattr(CrossSection,'mesh',mesh)
    monkeypatch.setattr(Line,'analyze',line)
    with monkeypatch.context() as context:
        context.setattr(module(kind),'_current_reuse_scope',nullcontext)
        context.setattr(module(kind),'_mesh_reuse_scope',nullcontext)
        uncached=request.run()
    before=dict(currents=list(currents),meshes=list(meshes),fields=list(fields));currents.clear();meshes.clear();fields.clear()
    cached=request.run();after=dict(currents=list(currents),meshes=list(meshes),fields=list(fields))
    record_property('two_ground_study_reuse',json.dumps(dict(kind=kind,uncached=uncached,cached=cached,
        uncached_calls=before,cached_calls=after),sort_keys=True))
    assert cached==uncached and cached['execution']['status']=='complete'
    rows=cached['execution']['result']['rows'];assert len(rows)==4
    for label in ('currents','meshes'):
        assert len(before[label])==4 and len(after[label])==1
        assert all(row==after[label][0] for row in before[label])
    samples=[row['sample_values'][0] for row in rows];assert len(set(samples))==4
    values=[row['value'] if kind=='scalar' else row['values_ohm'] for row in rows]
    assert len({json.dumps(v) for v in values})==4
    assert before['fields']==after['fields'] and len(fields)==4
    for key in ('C','G'):assert len({json.dumps(row[key]) for row in fields})==4
    assert current_scope._SCOPE.get() is None and mesh_scope._SCOPE.get() is None


@pytest.mark.parametrize('kind',['scalar','pair','grid'])
def test_budget_refusal_and_interrupt_restore_outer_scopes(monkeypatch,kind):
    doc=document(kind)
    from sipi.two_ground_panel_line import TwoGroundPanelTransmissionLineDocument
    calls=[]
    def interrupt(self):
        assert current_scope._SCOPE.get() is not None and mesh_scope._SCOPE.get() is not None
        calls.append(self.dumps());raise KeyboardInterrupt('original row interrupt')
    monkeypatch.setattr(TwoGroundPanelTransmissionLineDocument,'analyze',interrupt)
    with current_scope._current_reuse_scope() as old_current, mesh_scope._mesh_reuse_scope() as old_mesh:
        for budget in (True,3):
            with pytest.raises(ValueError):doc.analyze(max_evaluations=budget)
            assert current_scope._SCOPE.get() is old_current and mesh_scope._SCOPE.get() is old_mesh
        assert not calls
        with pytest.raises(KeyboardInterrupt,match='original row interrupt'):doc.analyze(max_evaluations=4)
        assert len(calls)==1
        assert current_scope._SCOPE.get() is old_current and mesh_scope._SCOPE.get() is old_mesh
    assert current_scope._SCOPE.get() is None and mesh_scope._SCOPE.get() is None


@pytest.mark.parametrize('kind',['scalar','pair','grid'])
def test_all_failed_rows_are_retained_and_requests_are_separate(monkeypatch,kind):
    from sipi.two_ground_panel_line import TwoGroundPanelTransmissionLineDocument,TwoGroundPanelLineError
    calls=[];scopes=[]
    def refuse(self):
        calls.append(self.dumps());scopes.append((current_scope._SCOPE.get(),mesh_scope._SCOPE.get()))
        cause=ArithmeticError('original per-row current refusal')
        raise TwoGroundPanelLineError(cause,stage='current',input_json=self.dumps(),factors=None,
            settings=self.current_options,mesh_observation=None)
    monkeypatch.setattr(TwoGroundPanelTransmissionLineDocument,'analyze',refuse)
    doc=document(kind);first=doc.analyze(max_evaluations=4);second=doc.analyze(max_evaluations=4)
    assert first.to_dict()==second.to_dict() and first.failed==4 and len(calls)==8
    assert all(pair[0] is scopes[0][0] and pair[1] is scopes[0][1] for pair in scopes[:4])
    assert scopes[0][0] is not scopes[4][0] and scopes[0][1] is not scopes[4][1]
    assert all(not cache for pair in scopes for cache in pair)
    assert current_scope._SCOPE.get() is None and mesh_scope._SCOPE.get() is None


def test_actual_geometry_samples_request_distinct_current_and_mesh(monkeypatch,record_property):
    import galerkin.laplace_two_ground as shared
    doc=document('pair');raw=doc.to_dict()
    raw['study']['schema']='sipi.impedance-study/3';raw['study'].pop('material_variables')
    raw['study']['sampling']['variables']=[dict(name='width',lower=.00043,upper=.00044)]
    doc=type(doc).from_dict(raw)
    solve=shared.solve_two_ground_rectangle;generate=CrossSection.mesh;currents=[];meshes=[]
    def current(polygons,*,width,height,panels_per_edge=32,ground_modes=128,interpolation_degree=12):
        currents.append([p.tolist() for p in polygons])
        return solve(polygons,width=width,height=height,panels_per_edge=panels_per_edge,
            ground_modes=ground_modes,interpolation_degree=interpolation_degree)
    def mesh(self,**options):
        meshes.append(CrossSectionDocument(self,mesh=options).dumps());return generate(self,**options)
    monkeypatch.setattr(shared,'solve_two_ground_rectangle',current);monkeypatch.setattr(CrossSection,'mesh',mesh)
    result=doc.analyze(max_evaluations=4)
    record_property('two_ground_study_geometry_misses',json.dumps(dict(result=result.to_dict(),
        current_inputs=currents,mesh_inputs=meshes),sort_keys=True))
    assert result.failed==0 and len(result.rows)==len(currents)==len(meshes)==4
    assert len({json.dumps(row) for row in currents})==len(set(meshes))==4
