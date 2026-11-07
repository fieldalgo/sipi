# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Unequal two-dielectric pair, independent fields and composed constraints."""
from dataclasses import replace
from importlib import metadata
import json

import numpy as np
import pytest

from sipi import (asymmetric_coupled_layered_stripline, asymmetric_coupled_stripline,
                  CrossSection, CrossSectionDocument, ImpedanceDesignDocument)
from sipi.templates import coupled_layered_stripline
from sipi.constants import epsilon_0
from sipi.study import ImpedanceStudyDocument
from sipi.dielectric import ConstantDielectric
from sipi.execution import normalize_saved, execute_saved
from sipi.yield_assessment import ImpedanceYieldDocument
from sipi.line_study import LineQuantityStudyDocument
from sipi.line_model import TransmissionLineDocument
from crosscheck import require_tool, Stopwatch, make_record, observable, emit

PARAMS=dict(left_width=.3e-3,right_width=.5e-3,gap=.4e-3,lower_height=.4e-3,upper_height=.6e-3,
    lower_eps_r=3.,upper_eps_r=5.,left_thickness=35e-6,right_thickness=50e-6,
    lower_tan_delta=.01,upper_tan_delta=.03,box_width=6e-3)
COARSE=dict(edge_size=5e-6,far_size=.25e-3,grade=.2)
FINE=dict(edge_size=2.5e-6,far_size=.125e-3,grade=.1)
PITCH=.8e-3


def section(**changes):
    return asymmetric_coupled_layered_stripline(**dict(PARAMS,**changes))


def study(**changes):
    options=dict(quantity='z_diff_forward',mesh=COARSE,fixed_pitch_m=PITCH,
        sampling=dict(kind='uniform',count=2,seed=71,
            variables=[dict(name='left_width',lower=.28e-3,upper=.32e-3)]))
    options.update(changes)
    return ImpedanceStudyDocument('asymmetric_coupled_layered_stripline',PARAMS,**options)


def test_explicit_interface_geometry_and_tapered_roundtrip():
    s=section(left_top_width=.25e-3,right_top_width=.45e-3);a,b=s.traces
    assert (a.name,b.name)==('positive','negative')
    assert a.y==b.y==.4e-3 and a.y1!=b.y1
    assert s.height==pytest.approx(1e-3,rel=1e-15)
    assert s.height-a.y1==pytest.approx(.6e-3-35e-6,rel=1e-15)
    assert s.height-b.y1==pytest.approx(.6e-3-50e-6,rel=1e-15)
    assert b.x0-a.x1==pytest.approx(.4e-3,rel=1e-12)
    assert abs(a.x0+b.x1)<=np.spacing(max(abs(a.x0),abs(b.x1)))
    assert b.x-a.x==pytest.approx(PITCH,rel=1e-12)
    assert s.top=='ground' and s.bottom=='ground' and s.sides=='open'
    assert [(x.name,x.eps_r,x.tan_delta) for x in s.layers]==[('lower',3.,.01),('upper',5.,.03)]
    doc=CrossSectionDocument(s,mesh=COARSE)
    assert doc.to_dict()['schema']=='sipi.cross-section/2'
    assert CrossSectionDocument.loads(doc.dumps()).dumps()==doc.dumps()
    assert section(box_width=None).width==pytest.approx(.012,rel=1e-15)


@pytest.mark.parametrize('thickness,top',[(0,None),(35e-6,None),(35e-6,.25e-3),(35e-6,.4e-3)])
def test_equal_pair_reduces_to_existing_layered_geometry(thickness,top):
    common={k:v for k,v in PARAMS.items() if not k.startswith(('left_','right_'))}
    old=coupled_layered_stripline(width=.3e-3,thickness=thickness,top_width=top,**common)
    new=asymmetric_coupled_layered_stripline(left_width=.3e-3,right_width=.3e-3,
        left_thickness=thickness,right_thickness=thickness,left_top_width=top,right_top_width=top,**common)
    assert CrossSectionDocument(new).dumps()==CrossSectionDocument(old).dumps()


@pytest.mark.parametrize('change',[dict(left_width=0),dict(right_width=True),dict(gap=0),
    dict(lower_height=0),dict(upper_height=0),dict(left_thickness=-1),
    dict(right_thickness=.6e-3),dict(upper_height=40e-6),dict(lower_eps_r=.5),
    dict(upper_eps_r=True),dict(lower_tan_delta=-.1),dict(upper_tan_delta=float('inf')),
    dict(box_width=1e-3),dict(left_top_width=3e-3),dict(left_thickness=0,left_top_width=.2e-3)])
def test_invalid_geometry_and_materials(change):
    with pytest.raises(ValueError):section(**change)


@pytest.fixture(scope='module')
def fields():
    m=section().mesh(**COARSE)
    return m,m.line_parameters(),section().analyze(**FINE),section(box_width=12e-3).analyze(**FINE)


def test_independent_piecewise_complex_and_vacuum_energy(fields):
    skfem=require_tool('scikit-fem')
    from skfem.helpers import dot,grad
    m,_,_,_=fields;clock=Stopwatch()
    with clock('openphysics'):actual=m.line_parameters()
    with clock('reference'):
        basis=skfem.Basis(skfem.MeshTri(m.mesh.nodes.T,m.mesh.triangles.T),skfem.ElementTriP1())
        @skfem.BilinearForm(dtype=complex)
        def form(u,v,w):return w.eps*dot(grad(u),grad(v))
        fixed=np.unique(np.concatenate([m.ground,*m.signals.values()]));expected=[]
        for eps in (m.eps_r*(1-1j*m.tan_delta),np.ones_like(m.eps_r)):
            k=skfem.asm(form,basis,eps=eps[:,None]);columns=[]
            for nodes in m.signals.values():
                v=np.zeros(basis.N,complex);v[nodes]=1
                columns.append(skfem.solve(*skfem.condense(k,np.zeros(basis.N,complex),x=v,D=fixed)))
            u=np.array(columns).T;expected.append(epsilon_0*(u.T@(k@u)))
    errors=[float(np.max(abs(a-b))/np.max(abs(b))) for a,b in
        [(actual.C,expected[0].real),(actual.C_loss,-expected[0].imag),(actual.C0,expected[1].real)]]
    record=make_record(case='asymmetric-layered-buried-pair',physics='piecewise lossy electrostatics',
        api='sipi.asymmetric_coupled_layered_stripline',discretization='P1 unequal conductors at a two-dielectric interface',
        tool='scikit-fem',tool_discretization='independent piecewise complex/vacuum P1 energy assembly',
        matched=['same mesh, grounded planes, insulated sides and conductor order','same separate lower/upper complex material coefficients'],
        not_matched=['no measured-board validation or independent geometric mesh'],
        observables=[observable(name,'F/m','max normalized matrix difference',error,1e-10)
            for name,error in zip(('C','C_loss','C0'),errors)],
        analytical_acceptance='uniform coefficient scaling, identical symmetric geometry, homogeneous and thin-reflection limits; separate mesh/box gates',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    assert max(errors)<1e-10


def test_scaling_passivity_and_separate_mesh_box_convergence(fields):
    m,coarse,fine,outer=fields;errors=[]
    for other,gate in [(coarse,.015),(outer,.005)]:
        values=[float(np.max(abs(other.C-fine.C))/np.max(abs(fine.C))),
                float(abs(other.z_diff_forward/fine.z_diff_forward-1))]
        errors.append(values);assert max(values)<gate
    for matrix in (fine.C,fine.C0,fine.C_loss,fine.L):
        np.testing.assert_allclose(matrix,matrix.T,atol=0,rtol=1e-12)
        assert np.linalg.eigvalsh(matrix).min()>0
    scaled=replace(m,eps_r=4*m.eps_r).line_parameters()
    np.testing.assert_allclose(scaled.C,4*coarse.C,atol=0,rtol=1e-12)
    np.testing.assert_allclose(scaled.C_loss,4*coarse.C_loss,atol=0,rtol=1e-12)
    np.testing.assert_array_equal(scaled.C0,coarse.C0)
    np.testing.assert_array_equal(scaled.L,coarse.L)
    assert scaled.z_diff_forward==pytest.approx(coarse.z_diff_forward/2,rel=1e-12)
    loss=replace(m,tan_delta=np.full_like(m.tan_delta,.02)).line_parameters()
    np.testing.assert_allclose(loss.C_loss,.02*loss.C,atol=0,rtol=1e-12)
    print('layered unequal C/Z mesh/outer',errors,'fine Z',fine.z_diff_forward)


def test_equal_materials_match_homogeneous_centred_pair():
    t=35e-6;lower=(1e-3-t)/2;upper=1e-3-lower
    layered=section(lower_height=lower,upper_height=upper,lower_eps_r=4.,upper_eps_r=4.,
        lower_tan_delta=.02,upper_tan_delta=.02,left_thickness=t,right_thickness=t).analyze(**FINE)
    homogeneous=asymmetric_coupled_stripline(left_width=.3e-3,right_width=.5e-3,gap=.4e-3,
        plane_spacing=1e-3,eps_r=4.,tan_delta=.02,left_thickness=t,right_thickness=t,box_width=6e-3).analyze(**FINE)
    errors=[float(np.max(abs(layered.C-homogeneous.C))/np.max(abs(homogeneous.C))),
            float(abs(layered.z_diff_forward/homogeneous.z_diff_forward-1))]
    print('layered unequal homogeneous reduction C/Z',errors)
    assert max(errors)<.005


def test_thin_vertical_reflection_swaps_layers():
    a=section(left_thickness=0,right_thickness=0).analyze(**FINE)
    b=section(left_thickness=0,right_thickness=0,lower_height=.6e-3,upper_height=.4e-3,
        lower_eps_r=5.,upper_eps_r=3.,lower_tan_delta=.03,upper_tan_delta=.01).analyze(**FINE)
    errors=[float(np.max(abs(getattr(a,key)-getattr(b,key)))/np.max(abs(getattr(a,key))))
            for key in ('C','C0','L','C_loss')]
    errors.append(float(abs(b.z_diff_forward/a.z_diff_forward-1)))
    print('layered unequal zero-thickness reflection C/C0/L/Closs/Z',errors)
    assert max(errors)<.005


@pytest.mark.parametrize('kind',['sweep','corners','uniform','normal'])
@pytest.mark.parametrize('name',['left_width','right_width'])
def test_fixed_pitch_sample_replay(kind,name):
    spec=dict(kind=kind,variables=[dict(name=name,lower=PARAMS[name]*.9,upper=PARAMS[name]*1.1)])
    if kind!='corners':spec['count']=3
    if kind in ('uniform','normal'):spec['seed']=31
    if kind=='normal':
        spec['variables']=[dict(name=name,mean=PARAMS[name],std=PARAMS[name]*.01)]
        spec['correlation']=[[1.]]
    doc=study(sampling=spec)
    assert normalize_saved(doc.dumps())==doc.dumps()
    for values,p in zip(doc.samples(),doc.sample_parameters()):
        assert p[name]==values[0]
        assert p['gap']+(p['left_width']+p['right_width'])/2==pytest.approx(PITCH,rel=1e-12)


@pytest.mark.parametrize('height',['lower_height','upper_height'])
def test_composed_pitch_stack_corners_and_actual_rows(height):
    doc=study(fixed_plane_spacing_m=1e-3,sampling=dict(kind='corners',variables=[
        dict(name='left_width',lower=.28e-3,upper=.32e-3),dict(name=height,lower=.35e-3,upper=.55e-3)]))
    assert doc.to_dict()['schema']=='sipi.impedance-study/2'
    assert normalize_saved(doc.dumps())==doc.dumps()
    result=doc.analyze(max_evaluations=4)
    assert result.failed==0 and len(result.rows)==4
    for row in result.rows:
        p=row.parameters;s=row.document.section
        assert p['lower_height']+p['upper_height']==pytest.approx(1e-3,rel=1e-12)
        assert s.height==pytest.approx(1e-3,rel=1e-12)
        assert s.traces[1].x-s.traces[0].x==pytest.approx(PITCH,rel=1e-12)
        assert row.impedance==pytest.approx(row.document.analyze().z_diff_forward,rel=1e-12)


def test_correlated_pitch_stack_and_retained_invalid_normal(monkeypatch):
    spec=dict(kind='normal',count=3,seed=41,correlation=[[1.,.4,.2],[.4,1.,.3],[.2,.3,1.]],variables=[
        dict(name='left_width',mean=.3e-3,std=.01e-3),dict(name='right_width',mean=.5e-3,std=.01e-3),
        dict(name='lower_height',mean=.4e-3,std=.01e-3)])
    plan=study(fixed_plane_spacing_m=1e-3,sampling=spec)
    assert ImpedanceStudyDocument.loads(plan.dumps()).dumps()==plan.dumps()
    for p in plan.sample_parameters():
        assert p['lower_height']+p['upper_height']==pytest.approx(1e-3,rel=1e-12)
        assert p['gap']+(p['left_width']+p['right_width'])/2==pytest.approx(PITCH,rel=1e-12)
    bad=study(fixed_pitch_m=None,fixed_plane_spacing_m=1e-3,sampling=dict(kind='normal',count=2,
        seed=41,correlation=[[1.]],variables=[dict(name='lower_height',mean=1.1e-3,std=1e-9)]))
    def forbidden(*args,**kwargs):pytest.fail('invalid derived geometry meshed')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    out=bad.analyze()
    assert out.failed==2 and out.summary is None
    assert all(row.parameters['upper_height']<0 and row.document is None for row in out.rows)


@pytest.mark.parametrize('change',[dict(quantity='z_diff'),dict(fixed_pitch_m=.9e-3),
    dict(fixed_plane_spacing_m=1e-3),
    dict(sampling=dict(kind='sweep',count=2,variables=[dict(name='gap',lower=.3e-3,upper=.5e-3)])),
    dict(sampling=dict(kind='sweep',count=2,variables=[dict(name='left_width',lower=.2e-3,upper=2e-3)])),
    dict(fixed_pitch_m=None,fixed_plane_spacing_m=1e-3,
         sampling=dict(kind='sweep',count=2,variables=[dict(name='lower_height',lower=.3e-3,upper=.99e-3)]))])
def test_invalid_constraints_and_bounded_geometry_before_fields(change,monkeypatch):
    def forbidden(*args,**kwargs):pytest.fail('invalid bounded input meshed')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    with pytest.raises(ValueError):study(**change)


def test_material_bindings_yield_and_full_loss_line_replay():
    doc=study(fixed_pitch_m=None,frequency=1e9,
        materials={'lower':ConstantDielectric(3.,.01),'upper':ConstantDielectric(5.,.03)},
        material_variables={'upper_dk':dict(region='upper',path=['eps_r'])},
        sampling=dict(kind='uniform',count=2,seed=31,variables=[dict(name='upper_dk',lower=4.8,upper=5.2)]))
    assert doc.to_dict()['schema']=='sipi.impedance-study/4'
    direct=doc.analyze()
    output=execute_saved(ImpedanceYieldDocument(doc,minimum=1.,maximum=1000.).dumps(),max_evaluations=2)
    assert output['status']=='complete' and output['result']['passed']==2
    for row,expected in zip(output['result']['rows'],direct.rows):
        assert row['impedance_ohm']==expected.impedance
        assert set(row['material_evaluation']['materials'])=={'lower','upper'}
    lossy=LineQuantityStudyDocument(doc,conductor=dict(kind='perfect'),
        quantity='differential_forward_impedance_real',schema='sipi.line-quantity-study/2')
    assert normalize_saved(lossy.dumps())==lossy.dumps()
    solved=lossy.analyze(max_evaluations=2);assert solved.failed==0
    u=np.array([1.,-1.])
    for row in solved.rows:
        replay=TransmissionLineDocument.loads(row.input_json).analyze()
        np.testing.assert_allclose(row.result.characteristic().z_characteristic,replay.characteristic().z_characteristic,atol=0,rtol=1e-10)
        assert row.value==pytest.approx(float((u@replay.characteristic().z_characteristic[0]@u).real),rel=1e-10)
        material=json.loads(row.material_evaluation_json)['materials']
        assert material['upper']['parameters']['eps_r']==row.sample_values[0]
        assert material['lower']['parameters']['eps_r']==3.


def test_100ohm_fixed_pitch_goal_refinement_and_outer_box():
    doc=ImpedanceDesignDocument('asymmetric_coupled_layered_stripline',PARAMS,variable='left_width',
        bounds=[.1e-3,.8e-3],target=100.,quantity='z_diff_forward',tolerance=1.,
        fixed_pitch_m=PITCH,max_evaluations=24,mesh=FINE)
    assert normalize_saved(doc.dumps())==doc.dumps()
    result=doc.solve()
    assert abs(result.residual)<=1. and abs(result.refined_residual)<=1.
    p=dict(PARAMS,left_width=result.parameter,gap=PITCH-(result.parameter+.5e-3)/2,box_width=12e-3)
    outer=asymmetric_coupled_layered_stripline(**p).analyze(**FINE).z_diff_forward
    assert abs(outer-100.)<=1. and abs(outer/result.impedance-1)<.005
    assert result.document.section.height==pytest.approx(1e-3,rel=1e-12)
    print('layered asymmetric goal width/residual/refined/outer',result.parameter,result.residual,result.refined_residual,outer-100.)
