# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Unequal finite-ground surface pair: fields, truncation and saved studies."""
from dataclasses import replace
from importlib import metadata
import json

import numpy as np
import pytest

from sipi import (asymmetric_coupled_grounded_coplanar, CrossSection,
                  CrossSectionDocument, ImpedanceDesignDocument)
from sipi.templates import coupled_grounded_coplanar
from sipi.constants import epsilon_0
from sipi.study import ImpedanceStudyDocument
from sipi.dielectric import ConstantDielectric
from sipi.execution import normalize_saved, execute_saved
from sipi.yield_assessment import ImpedanceYieldDocument
from sipi.line_study import LineQuantityStudyDocument
from sipi.line_model import TransmissionLineDocument
from crosscheck import require_tool, Stopwatch, make_record, observable, emit

PARAMS=dict(left_width=.3e-3,right_width=.5e-3,gap=.3e-3,
    substrate_height=.5e-3,eps_r=4.,tan_delta=.02,
    ground_gap=.25e-3,ground_width=1.5e-3,ground_thickness=35e-6,
    left_thickness=35e-6,right_thickness=50e-6,air_height=5e-3,box_width=12e-3)
COARSE=dict(edge_size=5e-6,far_size=.25e-3,grade=.2)
FINE=dict(edge_size=2.5e-6,far_size=.125e-3,grade=.1)
PITCH=.7e-3


def section(**changes):
    return asymmetric_coupled_grounded_coplanar(**dict(PARAMS,**changes))


def study(**changes):
    options=dict(quantity='z_diff_forward',mesh=COARSE,fixed_pitch_m=PITCH,
        sampling=dict(kind='uniform',count=2,seed=71,
            variables=[dict(name='left_width',lower=.28e-3,upper=.32e-3)]))
    options.update(changes)
    return ImpedanceStudyDocument('asymmetric_coupled_grounded_coplanar',PARAMS,**options)


def test_explicit_geometry_ground_clearance_taper_and_json():
    s=section(left_top_width=.25e-3,right_top_width=.45e-3);a,b,l,r=s.traces
    assert (a.name,b.name,l.name,r.name)==('positive','negative','ground_left','ground_right')
    assert [x.ground for x in s.traces]==[False,False,True,True]
    assert all(x.y==.5e-3 for x in s.traces)
    assert [x.thickness for x in s.traces]==[35e-6,50e-6,35e-6,35e-6]
    assert l.top_width is None and r.top_width is None
    assert a.x0-l.x1==pytest.approx(.25e-3,rel=1e-12)
    assert r.x0-b.x1==pytest.approx(.25e-3,rel=1e-12)
    assert b.x0-a.x1==pytest.approx(.3e-3,rel=1e-12)
    assert b.x-a.x==pytest.approx(PITCH,rel=1e-12)
    assert abs(a.x0+b.x1)<=np.spacing(max(abs(a.x0),abs(b.x1)))
    assert s.top=='open' and s.bottom=='ground' and s.sides=='open'
    doc=CrossSectionDocument(s,mesh=COARSE)
    assert CrossSectionDocument.loads(doc.dumps()).dumps()==doc.dumps()
    auto=section(box_width=None,air_height=None)
    assert auto.width==pytest.approx(.010,rel=1e-15)
    assert auto.layers[1].thickness==pytest.approx(.005+50e-6,rel=1e-15)
    # Explicit ground thickness does not follow signal thickness.
    assert section(left_thickness=70e-6).traces[2].thickness==35e-6


@pytest.mark.parametrize('thickness,top',[(0,None),(35e-6,None),(35e-6,.25e-3),(35e-6,.4e-3)])
@pytest.mark.parametrize('width',[.3e-3,.7e-3,.1234567e-3])
def test_equal_inputs_reduce_to_existing_coplanar_geometry(thickness,top,width):
    common={k:v for k,v in PARAMS.items() if not k.startswith(('left_','right_')) and k!='ground_thickness'}
    old=coupled_grounded_coplanar(width=width,thickness=thickness,top_width=top,**common)
    new=asymmetric_coupled_grounded_coplanar(left_width=width,right_width=width,
        left_thickness=thickness,right_thickness=thickness,ground_thickness=thickness,
        left_top_width=top,right_top_width=top,**common)
    assert CrossSectionDocument(new).dumps()==CrossSectionDocument(old).dumps()


@pytest.mark.parametrize('change',[dict(left_width=0),dict(right_width=True),dict(gap=0),
    dict(ground_gap=0),dict(ground_width=-1),dict(ground_thickness=-1),
    dict(substrate_height=0),dict(left_thickness=-1),dict(right_thickness=5e-3),
    dict(ground_thickness=5e-3),dict(eps_r=.5),dict(tan_delta=-.1),
    dict(air_height=35e-6),dict(box_width=4e-3),dict(left_top_width=3e-3),
    dict(left_thickness=0,left_top_width=.2e-3)])
def test_invalid_geometry_and_materials_before_meshing(change):
    with pytest.raises(ValueError):section(**change)


@pytest.fixture(scope='module')
def fields():
    m=section().mesh(**COARSE)
    return m,m.line_parameters(),section().analyze(**FINE)


def test_independent_piecewise_complex_and_vacuum_energy(fields):
    skfem=require_tool('scikit-fem')
    from skfem.helpers import dot,grad
    m,_,_=fields;clock=Stopwatch()
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
    record=make_record(case='asymmetric-grounded-coplanar',physics='piecewise lossy electrostatics',
        api='sipi.asymmetric_coupled_grounded_coplanar',discretization='P1 unequal surface conductors and finite coplanar grounds',
        tool='scikit-fem',tool_discretization='independent piecewise complex/vacuum P1 energy assembly',
        matched=['same mesh, grounded backing plane and finite ground traces, insulated outer boundaries',
                 'same substrate/air complex coefficients and signal order'],
        not_matched=['no measured-board validation or independent geometric mesh'],
        observables=[observable(name,'F/m','max normalized matrix difference',error,1e-10)
            for name,error in zip(('C','C_loss','C0'),errors)],
        analytical_acceptance='coefficient scaling, vacuum identity, equal-pair geometry and reflected conductor permutation; separate mesh/outer/ground-width checks',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    assert max(errors)<1e-10


def relative(a,b):
    return [float(np.max(abs(a.C-b.C))/np.max(abs(b.C))),float(abs(a.z_diff_forward/b.z_diff_forward-1))]


def test_mesh_outer_ground_width_scaling_and_passivity(fields):
    m,coarse,fine=fields;changes=dict(mesh=relative(coarse,fine))
    assert max(changes['mesh'])<.015
    for name,change,gate in [('box',dict(box_width=24e-3),.005),
                              ('air',dict(air_height=10e-3),.005),
                              ('ground_width',dict(ground_width=3e-3),.01)]:
        other=section(**change).analyze(**FINE);changes[name]=relative(other,fine)
        print('coplanar unequal sensitivity',name,changes[name])
        assert max(changes[name])<gate
    for matrix in (fine.C,fine.C0,fine.C_loss,fine.L):
        np.testing.assert_allclose(matrix,matrix.T,atol=0,rtol=1e-12)
        assert np.linalg.eigvalsh(matrix).min()>0
    scaled=replace(m,eps_r=4*m.eps_r).line_parameters()
    np.testing.assert_allclose(scaled.C,4*coarse.C,atol=0,rtol=1e-12)
    np.testing.assert_allclose(scaled.C_loss,4*coarse.C_loss,atol=0,rtol=1e-12)
    np.testing.assert_array_equal(scaled.C0,coarse.C0)
    np.testing.assert_array_equal(scaled.L,coarse.L)
    assert scaled.z_diff_forward==pytest.approx(coarse.z_diff_forward/2,rel=1e-12)
    vacuum=section(eps_r=1.,tan_delta=0.).analyze(**COARSE)
    np.testing.assert_allclose(vacuum.C,vacuum.C0,atol=0,rtol=1e-12)
    print('coplanar unequal all sensitivities',changes,'fine Z',fine.z_diff_forward)


def test_horizontal_reflection_swaps_signal_order():
    a=section(left_top_width=.25e-3,right_top_width=.45e-3)
    b=section(left_width=.5e-3,right_width=.3e-3,left_thickness=50e-6,right_thickness=35e-6,
        left_top_width=.45e-3,right_top_width=.25e-3)
    for x,y in zip(a.traces,[b.traces[i] for i in [1,0,3,2]]):
        assert (x.x,x.y,x.width,x.thickness,x.top_width)==(-y.x,y.y,y.width,y.thickness,y.top_width)
    la,lb=a.analyze(**FINE),b.analyze(**FINE);errors=[]
    for key in ('C','C0','C_loss','L'):
        va,vb=getattr(la,key),getattr(lb,key)[::-1,::-1]
        errors.append(float(np.max(abs(va-vb))/np.max(abs(va))))
    errors.append(float(abs(la.z_diff_forward/lb.z_diff_forward-1)))
    print('coplanar unequal reflected permutation',errors)
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
        a,b,l,r=asymmetric_coupled_grounded_coplanar(**p).traces
        assert a.x0-l.x1==pytest.approx(p['ground_gap'],rel=1e-12)
        assert r.x0-b.x1==pytest.approx(p['ground_gap'],rel=1e-12)


def test_correlated_ground_gap_widths_and_invalid_normal(monkeypatch):
    plan=study(sampling=dict(kind='normal',count=3,seed=41,
        correlation=[[1.,.4,.2],[.4,1.,.3],[.2,.3,1.]],variables=[
            dict(name='left_width',mean=.3e-3,std=.01e-3),dict(name='right_width',mean=.5e-3,std=.01e-3),
            dict(name='ground_gap',mean=.25e-3,std=.01e-3)]))
    assert ImpedanceStudyDocument.loads(plan.dumps()).dumps()==plan.dumps()
    assert plan.analyze().failed==0
    bad=study(fixed_pitch_m=None,sampling=dict(kind='normal',count=2,seed=41,
        correlation=[[1.]],variables=[dict(name='ground_gap',mean=-.1e-3,std=1e-9)]))
    def forbidden(*args,**kwargs):pytest.fail('invalid ground gap meshed')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    out=bad.analyze();assert out.failed==2 and out.summary is None
    assert all(row.parameters['ground_gap']<0 and row.document is None for row in out.rows)


@pytest.mark.parametrize('change',[dict(quantity='z_diff'),dict(fixed_pitch_m=.8e-3),
    dict(fixed_plane_spacing_m=1e-3),
    dict(sampling=dict(kind='sweep',count=2,variables=[dict(name='gap',lower=.2e-3,upper=.4e-3)])),
    dict(sampling=dict(kind='sweep',count=2,variables=[dict(name='left_width',lower=.2e-3,upper=2e-3)])),
    dict(fixed_pitch_m=None,sampling=dict(kind='sweep',count=2,
         variables=[dict(name='ground_width',lower=1e-3,upper=10e-3)]))])
def test_invalid_constraints_and_bounds_before_fields(change,monkeypatch):
    def forbidden(*args,**kwargs):pytest.fail('invalid bounded input meshed')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    with pytest.raises(ValueError):study(**change)


def test_material_yield_and_full_loss_line_replay():
    doc=study(fixed_pitch_m=None,frequency=1e9,materials={'substrate':ConstantDielectric(4.,.02)},
        material_variables={'dk':dict(region='substrate',path=['eps_r'])},
        sampling=dict(kind='uniform',count=2,seed=31,variables=[dict(name='dk',lower=3.8,upper=4.2)]))
    assert doc.to_dict()['schema']=='sipi.impedance-study/4'
    direct=doc.analyze()
    output=execute_saved(ImpedanceYieldDocument(doc,minimum=1.,maximum=1000.).dumps(),max_evaluations=2)
    assert output['status']=='complete' and output['result']['passed']==2
    for row,expected in zip(output['result']['rows'],direct.rows):
        assert row['impedance_ohm']==expected.impedance
    lossy=LineQuantityStudyDocument(doc,conductor=dict(kind='perfect'),
        quantity='differential_forward_impedance_real',schema='sipi.line-quantity-study/2')
    assert normalize_saved(lossy.dumps())==lossy.dumps()
    solved=lossy.analyze(max_evaluations=2);assert solved.failed==0;u=np.array([1.,-1.])
    for row in solved.rows:
        replay=TransmissionLineDocument.loads(row.input_json).analyze()
        np.testing.assert_allclose(row.result.characteristic().z_characteristic,replay.characteristic().z_characteristic,atol=0,rtol=1e-10)
        assert row.value==pytest.approx(float((u@replay.characteristic().z_characteristic[0]@u).real),rel=1e-10)
        assert json.loads(row.material_evaluation_json)['materials']['substrate']['parameters']['eps_r']==row.sample_values[0]


def test_100ohm_fixed_pitch_goal_refinement_and_outer_sizes():
    doc=ImpedanceDesignDocument('asymmetric_coupled_grounded_coplanar',PARAMS,variable='left_width',
        bounds=[.1e-3,.8e-3],target=100.,quantity='z_diff_forward',tolerance=1.,
        fixed_pitch_m=PITCH,max_evaluations=24,mesh=FINE)
    assert normalize_saved(doc.dumps())==doc.dumps()
    result=doc.solve()
    assert abs(result.residual)<=1. and abs(result.refined_residual)<=1.
    p=dict(PARAMS,left_width=result.parameter,gap=PITCH-(result.parameter+.5e-3)/2)
    residuals=[]
    for change in (dict(box_width=24e-3),dict(air_height=10e-3)):
        outer=asymmetric_coupled_grounded_coplanar(**dict(p,**change)).analyze(**FINE).z_diff_forward
        assert abs(outer-100.)<=1. and abs(outer/result.impedance-1)<.005
        residuals.append(outer-100.)
    print('coplanar unequal goal width/requested/refined/box/air',result.parameter,result.residual,result.refined_residual,residuals)


def test_thin_vacuum_pair_against_independent_image_panel_integral():
    from scipy.constants import c
    from test_coupled_coplanar import panel_reference
    # Dimensions are explicit and independent of SIPI geometry/mesh/solver.
    intervals=np.array([[-.55,-.25],[.05,.55],[-2.3,-.8],[.8,2.3]])*1e-3
    u=np.array([1.,-1.]);references=[]
    for count in (80,160):
        cap=panel_reference(intervals,.5e-3,count)[:2,:2]
        references.append((cap,float(u@np.linalg.solve(cap,u)/c)))
    cap,z=references[-1]
    reference_changes=[float(np.max(abs(references[0][0]-cap))/np.max(abs(cap))),abs(references[0][1]/z-1)]
    assert max(reference_changes)<.003
    p=dict(PARAMS,eps_r=1.,tan_delta=0.,left_thickness=0.,right_thickness=0.,ground_thickness=0.)
    errors=[];lines=[]
    for mesh in (COARSE,FINE):
        line=asymmetric_coupled_grounded_coplanar(**p).analyze(**mesh);lines.append(line)
        errors.append([float(np.max(abs(line.C-cap))/np.max(abs(cap))),abs(line.z_diff_forward/z-1)])
    print('coplanar unequal thin reference refinement',reference_changes,'C/Z errors',errors,'reference Z',z)
    assert max(errors[-1])<.02
    assert np.all(np.array(errors[-1])<errors[0])
    wide=asymmetric_coupled_grounded_coplanar(**dict(p,box_width=24e-3,air_height=10e-3)).analyze(**FINE)
    changes=relative(wide,lines[-1]);print('coplanar unequal thin outer C/Z',changes)
    assert max(changes)<.01
