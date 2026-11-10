# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Mesh-budget diagnostics retain completed work without accepting a failed solve."""
from types import SimpleNamespace
import json
import numpy as np
import pytest
from meshine import MeshSizeLimitError
import sipi
import sipi.design as design
import sipi.crosssection as crosssection
from sipi import CrossSection, CrossSectionDocument, GoalSeekError, GoalMeshSizeLimitError
from sipi.dielectric import ConstantDielectric
from sipi.templates import stripline, coupled_stripline
from sipi.design_document import ImpedanceDesignDocument
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject


@pytest.mark.parametrize('failure_at',[1,2,3,4],ids=['first','second','interior','refinement'])
@pytest.mark.parametrize('material_mode',['none','fixed','factory'])
@pytest.mark.parametrize('quantity',['z0','z_diff','z_diff_forward'])
def test_field_limit_context_preserves_original_cause_completed_rows_and_material(failure_at,material_mode,quantity,monkeypatch):
    calls=[];material_calls=[];cause=MeshSizeLimitError('test point budget exceeded')
    mesh=dict(edge_size=.01,far_size=1.,grade=.2)
    def factory(width):
        return (stripline(width=width,plane_spacing=10,eps_r=4) if quantity=='z0' else
                coupled_stripline(width=width,gap=1,plane_spacing=10,eps_r=4))
    def fake(section,**options):
        calls.append((section,options))
        if len(calls)==failure_at:raise cause
        value=1/section.traces[0].width
        return SimpleNamespace(z0=value,z_diff_forward=value,even_odd=lambda:{'z_diff':value})
    def material_field(doc,value,selected_quantity, *, mesh_reuse=None):
        assert selected_quantity==quantity
        return fake(doc.section,**doc.mesh_options)
    def models(value):
        material_calls.append(value)
        return {'dielectric':ConstantDielectric(4+value)}
    monkeypatch.setattr(CrossSection,'analyze',fake)
    monkeypatch.setattr(design,'_analyze_material',material_field)
    options={} if material_mode=='none' else dict(frequency=1e8)
    if material_mode=='fixed':options['materials']={'dielectric':ConstantDielectric(4)}
    if material_mode=='factory':options['material_factory']=models
    with pytest.raises(GoalMeshSizeLimitError) as caught:
        sipi.seek_impedance(factory,[1,2],2/3,tolerance=1e-12,quantity=quantity,mesh=mesh,max_evaluations=4,**options)
    error=caught.value
    assert isinstance(error,GoalSeekError) and isinstance(error,MeshSizeLimitError)
    assert error.__cause__ is cause and error.cause_type=='MeshSizeLimitError'
    expected_parameters=[1.,2.,1.5]
    assert error.parameter==([1.,2.,1.5,1.5][failure_at-1])
    assert error.stage==('refinement' if failure_at==4 else 'search')
    assert error.attempts==failure_at==len(calls) and len(error.history)==failure_at-1
    assert [(x.parameter,x.impedance,x.stage) for x in error.history]==[(w,1/w,'search') for w in expected_parameters[:failure_at-1]]
    failed=CrossSectionDocument.loads(error.input_json)
    expected_mesh=factory(error.parameter).mesh_settings(**mesh)
    if failure_at==4:
        for key in ['edge_size','far_size','grade']:expected_mesh[key]/=2
    assert failed.to_dict()==CrossSectionDocument(factory(error.parameter),mesh=expected_mesh).to_dict()
    assert failed.mesh_options==expected_mesh
    if material_mode=='none':assert error.material_evaluation_json is None
    else:
        snapshot=json.loads(error.material_evaluation_json)
        assert snapshot['frequency_hz']==1e8
        assert snapshot['materials']['dielectric']['parameters']['eps_r']==(4 if material_mode=='fixed' else 4+error.parameter)
    assert material_calls==(expected_parameters[:min(failure_at,3)] if material_mode=='factory' else [])
    assert not hasattr(cause,'history')


@pytest.mark.parametrize('source',['factory','material-factory','field-value','field-runtime'])
def test_other_error_identity_and_factory_mesh_error_are_not_reclassified(source,monkeypatch):
    cause=MeshSizeLimitError('factory mesh') if source in ('factory','material-factory') else (ValueError('field value') if source=='field-value' else RuntimeError('field runtime'))
    def factory(width):
        if source=='factory':raise cause
        return stripline(width=width,plane_spacing=10,eps_r=4)
    def fail(*a,**kw):raise cause
    options={}
    if source=='material-factory':options=dict(frequency=1e8,material_factory=fail)
    if source.startswith('field-'):monkeypatch.setattr(CrossSection,'analyze',fail)
    with pytest.raises(type(cause)) as caught:sipi.seek_impedance(factory,[1,2],1,**options)
    assert caught.value is cause and not isinstance(caught.value,GoalSeekError)


@pytest.mark.parametrize('mode',['none','fixed','factory'])
def test_real_refinement_point_limit_keeps_exact_failed_snapshot_and_completed_values(mode,monkeypatch):
    mesh=dict(edge_size=10e-6,far_size=.2e-3,grade=.2)
    def factory(width):return stripline(width=width,plane_spacing=1e-3,eps_r=4,box_width=6e-3)
    target=factory(.3e-3).analyze(**mesh).z0
    original=crosssection.generate;calls=[]
    def bounded(*args,**kwargs):
        calls.append(dict(kwargs))
        if len(calls)==4:kwargs['max_points']=4
        return original(*args,**kwargs)
    options={} if mode=='none' else dict(frequency=1e8)
    if mode=='fixed':options['materials']={'dielectric':ConstantDielectric(4)}
    if mode=='factory':options['material_factory']=lambda value:{'dielectric':ConstantDielectric(4)}
    with monkeypatch.context() as patched:
        patched.setattr(crosssection,'generate',bounded)
        with pytest.raises(MeshSizeLimitError) as caught:
            sipi.seek_impedance(factory,[.2e-3,.4e-3],target,tolerance=.1,mesh=mesh,**options)
    error=caught.value
    assert isinstance(error,GoalMeshSizeLimitError) and error.stage=='refinement'
    assert type(error.__cause__) is MeshSizeLimitError and 'more than 4 points' in str(error.__cause__)
    assert error.attempts==4 and len(error.history)==3
    for row in error.history:
        assert row.stage=='search'
        assert row.impedance==pytest.approx(factory(row.parameter).analyze(**mesh).z0,rel=1e-12)
    failed=CrossSectionDocument.loads(error.input_json)
    expected=factory(error.parameter).mesh_settings(**mesh)
    for key in ['edge_size','far_size','grade']:expected[key]/=2
    assert failed.mesh_options==expected and failed.section.traces[0].width==error.parameter
    # Replay after removing the test-only budget injection is an ordinary solve.
    assert np.isfinite(failed.analyze().z0)


@pytest.mark.parametrize('saved_mode',['none','fixed','material-leaf'])
def test_saved_request_record_and_project_preserve_actual_failed_goal_without_reexecution(saved_mode,monkeypatch,tmp_path,capsys):
    p=dict(width=.3e-3,plane_spacing=1e-3,eps_r=4,box_width=6e-3)
    mesh=dict(edge_size=10e-6,far_size=.2e-3,grade=.2)
    target=stripline(**p).analyze(**mesh).z0
    controls=dict(variable='width',bounds=[.2e-3,.4e-3],target=target,tolerance=.1,mesh=mesh)
    if saved_mode!='none':controls.update(frequency=1e8,materials={'dielectric':ConstantDielectric(4)})
    if saved_mode=='material-leaf':controls.update(variable='dk',bounds=[3.,5.],material_variables={'dk':dict(region='dielectric',path=['eps_r'])})
    goal=ImpedanceDesignDocument('stripline',p,**controls)
    request=SavedExecutionRequest(goal.dumps());original=crosssection.generate;calls=[]
    original_mesh=CrossSection.mesh;is_refinement=False
    def observed_mesh(self,**options):
        nonlocal is_refinement
        is_refinement=options.get('edge_size')==mesh['edge_size']/2
        return original_mesh(self,**options)
    def bounded(*args,**kwargs):
        calls.append(1)
        if is_refinement:kwargs['max_points']=4
        return original(*args,**kwargs)
    monkeypatch.setattr(CrossSection,'mesh',observed_mesh)
    monkeypatch.setattr(crosssection,'generate',bounded)
    receipt=request.run();result=receipt['execution']
    assert result['status']=='failed' and result['result'] is None
    error=result['error']
    assert error['type']=='GoalMeshSizeLimitError' and error['stage']=='refinement' and error['attempts']==4
    assert error['cause_type']=='MeshSizeLimitError' and len(error['history'])==3
    assert error['unit']=='ohm'
    if saved_mode=='none':assert error['material_evaluation'] is None
    else:
        assert error['material_evaluation']['frequency_hz']==1e8
        assert error['material_evaluation']['materials']['dielectric']['parameters']['eps_r']==4
    assert error['input']['traces'][0]['width']==(p['width'] if saved_mode=='material-leaf' else error['parameter'])
    json.dumps(receipt,allow_nan=False)
    from sipi import cli
    calls.clear()
    source=tmp_path/'input.json';output=tmp_path/'failed.json'
    source.write_text(goal.dumps(),encoding='utf-8')
    assert cli.main(['run',str(source),'--output',str(output)])==1
    assert json.loads(output.read_text(encoding='utf-8'))==receipt
    captured=capsys.readouterr();assert not captured.out and not captured.err
    assert len(calls)==(2 if saved_mode=='material-leaf' else 4)
    assert not list(tmp_path.glob('.sipi-result-*'))
    # Synthetic record declaration tests transport, never installed provenance.
    record=SavedExecutionRecord(request,receipt,run_id='test:mesh-limit',artifacts=[dict(component='sipi',version='test-only',kind='wheel',sha256='1'*64)])
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**kw:pytest.fail('Loading failure metadata solved a field'))
    restored=SavedExecutionRecord.loads(record.dumps())
    assert restored.receipt==receipt and restored.prepare().to_dict()==request.to_dict()
    project=SavedProject(request,project_id='mesh-limit',design_id='a',title='Mesh limit',label='A').attach_record('a',record,select=True)
    replay=SavedProject.loads(project.dumps())
    assert replay.current_record('a').receipt==receipt
