# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import sipi.panel_shape_conductor as candidate
from sipi import CrossSection, Layer, Trace, PolygonTrace
from sipi.document import CrossSectionDocument
from sipi.constants import epsilon_0, mu_0
from sipi.boundary_conductor import SurfaceMetal

CASES = json.loads((Path(__file__).parent/'data/panel_shape_reference.json').read_text())['cases']


def single():
    return CrossSection([Layer('uniform', .01105, 4.)], [Trace('s', 0., .0008, .0008, 35e-6)], .02)


def relative(a, b):
    return float(np.max(abs(a-b))/np.max(abs(b)))


@pytest.fixture(scope='module', params=CASES, ids=[r['name'] for r in CASES])
def observations(request):
    case=request.param
    section=CrossSectionDocument.from_dict(case['cross_section']).section
    rows=[candidate.panel_shape_current_factors(section,panels_per_edge=n,
          ground_modes=1024,interpolation_degree=16) for n in (32,64)]
    return case,rows


def test_rectangular_holdouts_separate_panel_step_and_reference_checks(observations,record_property):
    case,rows=observations
    cap=epsilon_0*np.array(case['capacitance_per_permittivity'])
    parts=np.array(case['parts']);total=np.array(case['total'])
    errors=[]
    for result in rows:
        error=dict(C0=relative(result.C0,cap),total=relative(result.total,total),
            boundary=[relative(a,b) for a,b in zip(result.parts,parts)],
            mutual=float(abs(result.total[0,-1]-total[0,-1])/abs(total[0,-1])))
        errors.append(error)
        assert max(error['C0'],error['total'],*error['boundary'],error['mutual'])<=1e-3
        assert result.diagnostics['step_relative_change']<=1e-4
        np.testing.assert_allclose(result.current_integrals,np.vstack((np.eye(len(result.names)),-np.ones((1,len(result.names))))),atol=1e-10,rtol=0)
        np.testing.assert_allclose(result.C0@result.L_external,epsilon_0*mu_0*np.eye(len(result.names)),atol=1e-27,rtol=1e-10)
        assert len(result.samples)==1+4*(len(result.names)+1)
        assert np.linalg.eigvalsh(result.parts).min()>0
    assert max(relative(rows[0].parts,rows[1].parts),relative(rows[0].C0,rows[1].C0))<=1e-3
    record_property('panel_shape_current',json.dumps(dict(name=case['name'],errors=errors,
        observations=[dict(parts=r.parts.tolist(),C0=r.C0.tolist(),step=r.step_m,
          step_parts=r.step_parts.tolist(),diagnostics=dict(r.diagnostics)) for r in rows]),sort_keys=True))


def test_snapshot_immutability_and_exact_requests(observations):
    _,rows=observations;r=rows[-1]
    for value in (r.parts,r.C0,r.current_integrals,r.step_parts,r.boundary_step_parts,
                  r.samples[0].capacitance_per_permittivity,r.samples[0].request.polygons[0]):
        with pytest.raises(ValueError):value.setflags(write=True)
    with pytest.raises(TypeError):r.samples[0].diagnostics['current_error']=1.
    with pytest.raises(TypeError):r.diagnostics['solve_count']=0
    request=r.samples[0].request;copy=request.arguments();copy['polygons'][0][0][0]=999.
    assert request.arguments()['polygons'][0][0][0]!=999.
    np.testing.assert_array_equal(r.parts,r.step_parts[1])


@pytest.mark.parametrize('clockwise',[False,True])
@pytest.mark.parametrize('scale',[.001,1.,1000.])
def test_offset_normal_and_linear_edge_motion(scale,clockwise):
    original=scale*np.array([[-2.,0.],[1.,0.],[1.8,1.],[0.,2.],[-1.5,1.]])
    if clockwise:original=original[::-1]
    p,v,length=candidate._offset_velocity(original)
    edge=np.roll(p,-1,axis=0)-p;normal=np.column_stack((edge[:,1],-edge[:,0]))/length[:,None]
    np.testing.assert_allclose(np.sum(v*normal,axis=1),-1,rtol=1e-12)
    np.testing.assert_allclose(np.sum(np.roll(v,-1,axis=0)*normal,axis=1),-1,rtol=1e-12)
    moved=p+.01*scale*v
    moved_edge=np.roll(moved,-1,axis=0)-moved
    np.testing.assert_allclose(np.sum(moved_edge*normal,axis=1),0,atol=1e-12*scale)


def test_circle_above_plane_image_solution(record_property):
    theta=2*np.pi*np.arange(128)/128
    trace=PolygonTrace('wire',np.column_stack((np.cos(theta),3+np.sin(theta))))
    section=CrossSection([Layer('vacuum',480.,1.)],[trace],960.)
    result=candidate.panel_shape_current_factors(section,panels_per_edge=8,ground_modes=4096)
    exact_c=2*np.pi/np.arccosh(3.)
    exact=np.array([3/(2*np.pi*np.sqrt(8)),1/(2*np.pi*np.sqrt(8))])
    np.testing.assert_allclose(result.C0,[[epsilon_0*exact_c]],rtol=1e-3,atol=0)
    np.testing.assert_allclose(result.parts[:,0,0],exact,rtol=1e-3,atol=0)
    record_property('circle_image',json.dumps(dict(parts=result.parts.tolist(),C0=result.C0.tolist(),diagnostics=dict(result.diagnostics)),sort_keys=True))


def guard(scale=1.,permittivity=1.,reverse=False):
    traces=[Trace('a',-.0005,.0003,.001,50e-6),Trace('guard',0.,.0002,.001,50e-6,ground=True),Trace('b',.0005,.0004,.001,60e-6)]
    if reverse:traces.reverse()
    traces=[Trace(t.name,t.x*scale,t.width*scale,t.y*scale,t.thickness*scale,ground=t.ground) for t in traces]
    return CrossSection([Layer('u',.01105*scale,permittivity)],traces,.02*scale)


def test_ground_voltage_permutation_scale_and_material_metadata(record_property):
    a=candidate.panel_shape_current_factors(guard(),panels_per_edge=16,ground_modes=1024)
    metadata=candidate.panel_shape_current_factors(guard(permittivity=4.),panels_per_edge=16,ground_modes=1024)
    np.testing.assert_array_equal(a.parts,metadata.parts)
    np.testing.assert_array_equal(a.C0,metadata.C0)
    b=candidate.panel_shape_current_factors(guard(scale=1000.,permittivity=4.,reverse=True),panels_per_edge=16,ground_modes=1024)
    assert a.names==('a','b') and a.ground_trace_names==('guard',)
    assert b.names==('b','a') and len(a.samples)==17
    np.testing.assert_allclose(a.C0,b.C0[::-1,::-1],rtol=1e-10,atol=1e-25)
    np.testing.assert_allclose(a.parts,1000*b.parts[[1,0,2],::-1,::-1],rtol=1e-6,atol=0)
    np.testing.assert_allclose(a.parts[2],a.boundary_step_parts[1,[1,3]].sum(axis=0),atol=0,rtol=0)
    cap=a.samples[0].capacitance_per_permittivity;ss=cap[np.ix_([0,2],[0,2])]
    potentials=np.zeros((3,2));potentials[[0,2]]=np.linalg.inv(ss)
    np.testing.assert_allclose(cap@potentials, np.vstack((np.array([1.,0.]),cap[1,[0,2]]@np.linalg.inv(ss),np.array([0.,1.]))),atol=1e-12,rtol=0)
    assert a.diagnostics['ground_voltage_error']==0
    record_property('grounded_shape',json.dumps(dict(parts=a.parts.tolist(),C0=a.C0.tolist(),scaled_parts=b.parts.tolist()),sort_keys=True))


@pytest.mark.parametrize('key,value',[(key,value) for key in ('panels_per_edge','ground_modes','interpolation_degree')
 for value in (True,1.5,0,9999)]+[('interpolation_degree',11)]+[('step_fraction',x) for x in (True,0,1e-6,.1,float('nan'),float('inf'),'0.001')])
def test_bad_controls_precede_solver(monkeypatch,key,value):
    monkeypatch.setattr(candidate,'_panel_solver',lambda:pytest.fail('invalid input reached solver'))
    with pytest.raises(ValueError):candidate.panel_shape_current_factors(single(),**{key:value})


@pytest.mark.parametrize('kind',['wrong','top','sides','bottom','zero','concave','collinear','aspect','cap'])
def test_bad_geometry_precedes_solver(monkeypatch,kind):
    monkeypatch.setattr(candidate,'_panel_solver',lambda:pytest.fail('invalid geometry reached solver'))
    if kind=='wrong':section=None
    elif kind in ('top','sides','bottom'):
        section=single();setattr(section,kind,'open' if kind=='bottom' else 'ground')
    elif kind=='zero':section=CrossSection([Layer('u',2.,1.)],[Trace('s',0.,.2,.5)],4.)
    elif kind in ('concave','collinear'):
        p=[(-.2,.5),(.2,.5),(.2,.8),(0.,.6),(-.2,.8)] if kind=='concave' else [(-.2,.5),(0.,.5),(.2,.5),(.2,.8),(-.2,.8)]
        section=CrossSection([Layer('u',2.,1.)],[PolygonTrace('s',p)],4.)
    elif kind=='aspect':section=CrossSection([Layer('u',20.,1.)],[Trace('s',0.,.2,.5,.1)],4.)
    else:section=guard()
    with pytest.raises((TypeError,ValueError)):
        candidate.panel_shape_current_factors(section,panels_per_edge=256 if kind=='cap' else 32)


def fake_solver(**kwargs):
    p=np.array(kwargs['polygons'][0]);width=np.ptp(p[:,0]);c=np.sqrt(width)/kwargs['height']
    return SimpleNamespace(capacitance_per_permittivity=np.array([[c]]),current_integrals=np.array([[1.],[-1.]]),
        **{key:0. for key in candidate._DIAGNOSTICS})


@pytest.mark.parametrize('index',range(9))
def test_each_shared_failure_retains_partial_inputs(monkeypatch,index):
    calls=[]
    def solve(**kwargs):
        calls.append(kwargs)
        if len(calls)==index+1:raise ValueError('original failure')
        return fake_solver(**kwargs)
    monkeypatch.setattr(candidate,'_panel_solver',lambda:solve)
    with pytest.raises(candidate.PanelShapeCurrentError,match='original failure') as caught:
        candidate.panel_shape_current_factors(single())
    error=caught.value
    assert len(error.samples)==index and len(calls)==index+1
    assert error.request.arguments()==calls[-1]
    for sample,request in zip(error.samples,calls):assert sample.request.arguments()==request
    assert isinstance(error.__cause__,ValueError)


@pytest.mark.parametrize('index',[0,4,8])
def test_interrupt_propagates_without_fallback(monkeypatch,index):
    calls=[]
    def solve(**kwargs):
        calls.append(kwargs)
        if len(calls)==index+1:raise KeyboardInterrupt()
        return fake_solver(**kwargs)
    monkeypatch.setattr(candidate,'_panel_solver',lambda:solve)
    with pytest.raises(KeyboardInterrupt):candidate.panel_shape_current_factors(single())
    assert len(calls)==index+1


def test_difference_failure_keeps_both_observations(monkeypatch):
    calls=[]
    def solve(**kwargs):
        calls.append(kwargs);r=fake_solver(**kwargs)
        if len(calls)==9:r.capacitance_per_permittivity*=1.00001
        return r
    monkeypatch.setattr(candidate,'_panel_solver',lambda:solve)
    with pytest.raises(candidate.PanelShapeCurrentError,match='difference steps') as caught:
        candidate.panel_shape_current_factors(single())
    assert len(caught.value.samples)==9
    assert caught.value.step_parts.shape==(2,2,1,1)
    assert caught.value.boundary_step_parts.shape==(2,2,1,1)
    assert caught.value.request is None


def test_relative_comparison_has_no_small_mutual_floor():
    assert candidate._relative(np.array([0.,1e-20]),np.array([0.,2e-20]))==.5
    assert candidate._relative(np.zeros((2,2)),np.zeros((2,2)))==0


@pytest.mark.parametrize('kind',['negative','zero','current'])
def test_invalid_physical_result_retains_complete_samples(monkeypatch,kind):
    def solve(**kwargs):
        r=fake_solver(**kwargs)
        if kind=='negative':r.capacitance_per_permittivity=1/r.capacitance_per_permittivity
        if kind=='zero':r.capacitance_per_permittivity[:]=1.
        if kind=='current':r.current_integrals[:]=0.
        return r
    monkeypatch.setattr(candidate,'_panel_solver',lambda:solve)
    match={'negative':'semidefinite','zero':'positive definite','current':'conservation'}[kind]
    with pytest.raises(candidate.PanelShapeCurrentError,match=match) as caught:
        candidate.panel_shape_current_factors(single())
    assert len(caught.value.samples)==9
    assert caught.value.step_parts.shape==(2,2,1,1)


def test_complete_call_bound_and_no_unrequested_refinement(monkeypatch):
    traces=[Trace(f's{i}',(i-7.5)*.001,.0004,.001,50e-6) for i in range(16)]
    section=CrossSection([Layer('u',.04,1.)],traces,.08)
    calls=[]
    def solve(**kwargs):
        calls.append(kwargs)
        widths=np.array([np.ptp(np.array(p)[:,0]) for p in kwargs['polygons']])
        return SimpleNamespace(capacitance_per_permittivity=np.diag(np.sqrt(widths)/kwargs['height']),
            current_integrals=np.vstack((np.eye(16),-np.ones((1,16)))),
            **{key:0. for key in candidate._DIAGNOSTICS})
    monkeypatch.setattr(candidate,'_panel_solver',lambda:solve)
    result=candidate.panel_shape_current_factors(section,panels_per_edge=8,ground_modes=128,interpolation_degree=14)
    assert len(calls)==69 and len(result.samples)==69
    assert all(c['panels_per_edge']==8 and c['ground_modes']==128 and c['interpolation_degree']==14 for c in calls)


def test_boundary_loss_uses_existing_material_laws(observations,monkeypatch):
    case,rows=observations;factors=rows[-1]
    section=CrossSectionDocument.from_dict(case['cross_section']).section
    monkeypatch.setattr(candidate,'panel_shape_current_factors',lambda *a,**k:factors)
    metals={name:SurfaceMetal(58e6/(i+1),relative_permeability=i+1) for i,name in enumerate(factors.names)}
    ground=SurfaceMetal(45e6);f=np.array([4e9,16e9])
    result=candidate.panel_shape_conductor_loss_by_boundary(section,f,conductors=metals,reference=ground,ground_thickness=35e-6)
    expected=np.zeros_like(result.R)
    for b,metal in enumerate([*metals.values(),ground]):
        expected+=np.sqrt(np.pi*f*mu_0*metal.relative_permeability/metal.conductivity)[:,None,None]*factors.parts[b]
    np.testing.assert_allclose(result.R,expected,rtol=1e-12,atol=0)
    np.testing.assert_allclose(result.L_internal*2*np.pi*f[:,None,None],expected,rtol=1e-12,atol=0)
    assert result.factors is factors


@pytest.mark.parametrize('kind',['dc','skin','missing','wrong'])
def test_loss_admission_precedes_fields(monkeypatch,kind):
    monkeypatch.setattr(candidate,'panel_shape_current_factors',lambda *a,**k:pytest.fail('invalid metal reached fields'))
    metals={'s':SurfaceMetal(58e6)};f=[4e9];section=single();depth=35e-6
    if kind=='dc':f=[0.]
    if kind=='skin':depth=1e-12
    if kind=='missing':metals={}
    if kind=='wrong':section=None
    with pytest.raises((ValueError,TypeError)):
        candidate.panel_shape_conductor_loss_by_boundary(section,f,conductors=metals,reference=SurfaceMetal(58e6),ground_thickness=depth)
