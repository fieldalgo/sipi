# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Corner target goals preserve search controls, snapshots and actual fields."""
import json
import numpy as np
import pytest
from scipy.constants import epsilon_0, mu_0
from meshine import MeshSizeLimitError
from sipi import (CrossSection, CornerCrossSectionDocument, stripline,
                  seek_corner_impedance, seek_impedance, GoalSeekError, GoalMeshSizeLimitError)
from sipi.dielectric import ConstantDielectric
from test_corner_mesh_control import independent_capacitance

MESH = dict(edge_size=1e-5,far_size=.0002,grade=.15)
BOUNDS = (.00055,.00065)


def factory(width):
    return stripline(width=width,plane_spacing=.002,eps_r=4.,thickness=.0004,box_width=.008)


def solve(**kwargs):
    options=dict(corner_size=2.5e-6,mesh=MESH,tolerance=.1,search_tolerance=.025,max_evaluations=12)
    options.update(kwargs)
    return seek_corner_impedance(factory,BOUNDS,44.3,**options)


@pytest.mark.parametrize('value',[None,True,False,0.,-1.,float('nan'),float('inf'),'1e-6',2e-5])
def test_bad_corner_rejects_without_field(value,monkeypatch):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('unexpected field'))
    with pytest.raises(ValueError):solve(corner_size=value)


def test_duplicate_corner_and_original_path_remain_strict(monkeypatch):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('unexpected field'))
    with pytest.raises(ValueError,match='separately'):
        solve(mesh=dict(MESH,corner_size=1e-6))
    with pytest.raises(ValueError,match='unknown'):
        seek_impedance(factory,BOUNDS,44.3,mesh=dict(MESH,corner_size=1e-6))


def fake_analysis(self,**options):
    return type('Line',(),dict(z0=.02658/self.traces[0].width))()


def test_selected_snapshot_four_control_refinement_and_history(monkeypatch):
    observed=[]
    def analyze(self,**options):
        observed.append((self.traces[0].width,options.copy()))
        return fake_analysis(self,**options)
    monkeypatch.setattr(CrossSection,'analyze',analyze)
    result=solve()
    assert isinstance(result.document,CornerCrossSectionDocument)
    assert result.document.corner_size==2.5e-6
    assert [row.stage for row in result.history]==['search']*3+['refinement']
    assert observed[-1][0]==observed[-2][0]==result.parameter
    for key in ('edge_size','far_size','grade','corner_size'):
        assert observed[-1][1][key]==observed[-2][1][key]/2
    assert observed[-1][1]['min_angle']==28.
    assert CornerCrossSectionDocument.loads(result.document.dumps()).dumps()==result.document.dumps()


@pytest.mark.parametrize('failure',['budget','bracket','refinement'])
def test_failure_retains_original_bounded_semantics(failure,monkeypatch):
    def analyze(self,**options):
        if failure=='bracket':return type('Line',(),dict(z0=50.))()
        line=fake_analysis(self,**options)
        if failure=='refinement' and options['corner_size']==1.25e-6:line.z0+=1
        return line
    monkeypatch.setattr(CrossSection,'analyze',analyze)
    with pytest.raises(GoalSeekError) as caught:
        solve(max_evaluations=3 if failure=='budget' else 12)
    assert len(caught.value.history)==(4 if failure=='refinement' else 2)
    if failure=='refinement':assert caught.value.history[-1].stage=='refinement'


@pytest.mark.parametrize('refinement',[False,True])
def test_mesh_limit_retains_resolved_corner_and_original_cause(refinement,monkeypatch):
    def analyze(self,**options):
        if not refinement or options['corner_size']==1.25e-6:
            raise MeshSizeLimitError('registered point budget')
        return fake_analysis(self,**options)
    monkeypatch.setattr(CrossSection,'analyze',analyze)
    with pytest.raises(GoalMeshSizeLimitError) as caught:solve()
    error=caught.value
    assert isinstance(error.__cause__,MeshSizeLimitError)
    assert error.stage==('refinement' if refinement else 'search')
    assert error.attempts==(4 if refinement else 1)
    saved=CornerCrossSectionDocument.loads(error.input_json)
    assert saved.corner_size==(1.25e-6 if refinement else 2.5e-6)
    assert saved.mesh_options['min_angle']==28.
    assert error.cause_type=='MeshSizeLimitError'


@pytest.mark.parametrize('kind',['geometry','material'])
def test_actual_goal_refinement_material_freeze_and_independent_field(kind,monkeypatch,record_property):
    meshes=[];material_calls=[];original=CrossSection.mesh
    def mesh(self,**options):
        result=original(self,**options);meshes.append(result);return result
    monkeypatch.setattr(CrossSection,'mesh',mesh)
    if kind=='geometry':result,line=solve(return_line=True)
    else:
        def material(value):
            material_calls.append(value)
            return {'dielectric':ConstantDielectric(value)}
        result,line=seek_corner_impedance(lambda value:factory(.0006),(3.8,4.2),44.3,
            corner_size=2.5e-6,mesh=MESH,tolerance=.1,search_tolerance=.025,max_evaluations=12,
            frequency=1e9,material_factory=material,return_line=True)
    reference=independent_capacitance(meshes[-1])
    actual_fine=meshes[-1].line_parameters()
    evaluation=None if result.material_evaluation_json is None else json.loads(result.material_evaluation_json)
    record_property('corner_goal',json.dumps(dict(kind=kind,parameter=result.parameter,
        target=result.target,requested=result.impedance,refined=result.refined_impedance,
        input=result.document.to_dict(),material_evaluation=evaluation,
        history=[dict(parameter=row.parameter,impedance=row.impedance,stage=row.stage) for row in result.history],
        selected_C0=line.C0.tolist(),fine_C0=actual_fine.C0.tolist(),reference_C0=reference,
        nodes=[field.mesh.num_nodes for field in meshes],material_calls=material_calls)))
    assert abs(result.residual)<=.025 and abs(result.refined_residual)<=.1
    assert len(result.history)==4 and result.history[-1].stage=='refinement'
    assert result.document.corner_size==2.5e-6
    assert np.all(abs(actual_fine.C0-reference)<=.005*np.maximum(abs(actual_fine.C0),abs(reference)))
    assert line.z0==result.impedance
    for name in ('C','C0','C_loss','L'):assert not getattr(line,name).flags.writeable
    er=4. if evaluation is None else evaluation['materials']['dielectric']['parameters']['eps_r']
    np.testing.assert_allclose(line.z0,np.sqrt(mu_0*epsilon_0)/(np.sqrt(er)*line.C0[0,0]),rtol=1e-9)
    if kind=='geometry':assert len(meshes)==4
    else:
        assert len(meshes)==2 and material_calls==[3.8,4.2,result.parameter]
        assert evaluation['frequency_hz']==1e9 and er==result.parameter
