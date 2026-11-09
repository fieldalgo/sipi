# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Unequal coated microstrip pair: fields, truncation and saved studies."""
from dataclasses import replace
from importlib import metadata
import json

import numpy as np
import pytest

from sipi import asymmetric_coupled_conformal_coated_microstrip
from sipi import (CrossSection,
                  CrossSectionDocument, ImpedanceDesignDocument)
from sipi.templates import coupled_conformal_coated_microstrip, asymmetric_coupled_microstrip
from sipi.constants import epsilon_0, mu_0
from sipi.study import ImpedanceStudyDocument
from sipi.dielectric import ConstantDielectric
from sipi.execution import normalize_saved, execute_saved
from sipi.yield_assessment import ImpedanceYieldDocument
from sipi.line_study import LineQuantityStudyDocument
from sipi.line_model import TransmissionLineDocument
from crosscheck import require_tool, Stopwatch, make_record, observable, emit

PARAMS=dict(left_width=.3e-3,right_width=.5e-3,gap=.3e-3,
    substrate_height=.5e-3,eps_r=4.,tan_delta=.02,
    coating_thickness=20e-6,coating_eps_r=3.3,coating_tan_delta=.015,
    left_thickness=35e-6,right_thickness=50e-6,air_height=6e-3,box_width=12e-3)
COARSE=dict(edge_size=5e-6,far_size=.25e-3,grade=.2)
FINE=dict(edge_size=2.5e-6,far_size=.125e-3,grade=.1)
PITCH=.7e-3


def section(**changes):
    return asymmetric_coupled_conformal_coated_microstrip(**dict(PARAMS,**changes))


def study(**changes):
    options=dict(quantity='z_diff_forward',mesh=COARSE,fixed_pitch_m=PITCH,
        sampling=dict(kind='uniform',count=2,seed=71,
            variables=[dict(name='left_width',lower=.28e-3,upper=.32e-3)]))
    options.update(changes)
    return ImpedanceStudyDocument('asymmetric_coupled_conformal_coated_microstrip',PARAMS,**options)


def test_explicit_geometry_ground_clearance_taper_and_json():
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    from sipi.polygons import trace_shape
    cs=section(left_top_width=.25e-3,right_top_width=.45e-3);a,b=cs.traces
    assert (a.name,b.name)==('positive','negative') and not a.ground and not b.ground
    assert (a.width,b.width)==(.3e-3,.5e-3) and (a.thickness,b.thickness)==(35e-6,50e-6)
    assert (a.top_width,b.top_width)==(.25e-3,.45e-3)
    assert a.y==b.y==.5e-3 and b.x0-a.x1==pytest.approx(.3e-3,rel=1e-12)
    assert b.x-a.x==pytest.approx(PITCH,rel=1e-12) and a.x0==-b.x1
    assert cs.bottom=='ground' and cs.top==cs.sides=='open'
    assert [l.name for l in cs.layers]==['substrate','air']
    assert len(cs.dielectric_regions)==1
    region=cs.dielectric_regions[0];film=region._shape
    assert region.name=='coating' and region.eps_r==3.3 and region.tan_delta==.015
    h,d=PARAMS['substrate_height'],PARAMS['coating_thickness']
    metal=unary_union([trace_shape(t) for t in cs.traces]);expected=cs.width*d
    for t in cs.traces:
        slope=(t.width-t.top_width)/(2*t.thickness)
        delta=d/(np.hypot(1,slope)+slope)
        expected+=2*delta*t.thickness
        y=h+d+t.thickness/2
        cut=film.intersection(LineString([(t.x-t.width/2-2*d,y),(t.x+t.width/2+2*d,y)]))
        distance=abs(cut.bounds[0]-slope*(y-h)-(t.x-t.width/2))/np.hypot(1,slope)
        assert distance==pytest.approx(d,rel=1e-12)
    assert film.difference(metal).area==pytest.approx(expected,rel=1e-12)
    assert film.bounds[1]==h and film.bounds[3]==pytest.approx(h+50e-6+d,rel=1e-12)
    assert cs.height-film.bounds[3]==pytest.approx(6e-3,rel=1e-12)
    assert not film.interiors and film.is_valid
    assert all(film.covers(trace_shape(t)) for t in cs.traces)
    doc=CrossSectionDocument(cs,mesh=COARSE)
    assert doc.to_dict()['schema']=='sipi.cross-section/3'
    assert CrossSectionDocument.loads(doc.dumps()).dumps()==doc.dumps()
    auto=section(box_width=None,air_height=None)
    assert auto.width==pytest.approx(.010,rel=1e-15)
    assert auto.height-auto.dielectric_regions[0]._shape.bounds[3]==pytest.approx(.005+50e-6,rel=1e-15)


@pytest.mark.parametrize('thickness,top',[(0,None),(35e-6,None),(35e-6,.1e-3)])
@pytest.mark.parametrize('width',[.3e-3,.7e-3,.1234567e-3])
@pytest.mark.parametrize('box',[12e-3,None])
def test_equal_inputs_reduce_to_existing_coplanar_geometry(thickness,top,width,box):
    common={k:v for k,v in PARAMS.items() if not k.startswith(('left_','right_')) and k!='ground_thickness'}
    common['box_width']=box
    old=coupled_conformal_coated_microstrip(width=width,thickness=thickness,top_width=top,**common)
    new=asymmetric_coupled_conformal_coated_microstrip(left_width=width,right_width=width,
        left_thickness=thickness,right_thickness=thickness,
        left_top_width=top,right_top_width=top,**common)
    assert CrossSectionDocument(new).dumps()==CrossSectionDocument(old).dumps()


@pytest.mark.parametrize('change',[dict(left_width=0),dict(right_width=True),dict(gap=0),

    dict(substrate_height=0),dict(left_thickness=-1),dict(right_thickness=-1),
    dict(eps_r=.5),dict(tan_delta=-.1),
    dict(air_height=0),dict(coating_thickness=-1),dict(coating_thickness=0),
    dict(coating_eps_r=.5),dict(coating_tan_delta=-1),dict(coating_thickness=float("inf")),dict(box_width=.5e-3),dict(left_top_width=3e-3),
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
    record=make_record(case='asymmetric-conformal-microstrip',physics='piecewise lossy electrostatics',
        api='sipi.asymmetric_coupled_conformal_coated_microstrip',discretization='P1 unequal surface conductors with a local normal-thickness mitered film',
        tool='scikit-fem',tool_discretization='independent piecewise complex/vacuum P1 energy assembly',
        matched=['same mesh and grounded backing plane, no lateral grounds, insulated other boundaries',
                 'same substrate/local-film/air complex coefficients and signal order'],
        not_matched=['no measured-board validation or independent geometric mesh'],
        observables=[observable(name,'F/m','max normalized matrix difference',error,1e-10)
            for name,error in zip(('C','C_loss','C0'),errors)],
        analytical_acceptance='coefficient scaling, vacuum identity, equal-pair geometry and reflected conductor permutation; separate mesh/outer checks',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    assert max(errors)<1e-10


def relative(a,b):
    return [float(np.max(abs(a.C-b.C))/np.max(abs(b.C))),float(abs(a.z_diff_forward/b.z_diff_forward-1))]


def test_mesh_outer_ground_width_scaling_and_passivity(fields):
    m,coarse,fine=fields;changes=dict(mesh=relative(coarse,fine))
    assert max(changes['mesh'])<.015
    for name,change,gate in [('box',dict(box_width=24e-3),.005),
                              ('air',dict(air_height=12e-3),.005)]:
        other=section(**change).analyze(**FINE);changes[name]=relative(other,fine)
        print('conformal microstrip unequal sensitivity',name,changes[name])
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
    vacuum=section(eps_r=1.,tan_delta=0.,coating_eps_r=1.,coating_tan_delta=0.).analyze(**COARSE)
    np.testing.assert_allclose(vacuum.C,vacuum.C0,atol=0,rtol=1e-12)
    common=replace(m,tan_delta=np.full_like(m.tan_delta,.02)).line_parameters()
    np.testing.assert_allclose(common.C_loss,.02*common.C,atol=0,rtol=1e-12)
    np.testing.assert_allclose(coarse.L,mu_0*epsilon_0*np.linalg.inv(coarse.C0),atol=0,rtol=1e-12)
    print('conformal microstrip unequal all sensitivities',changes,'fine Z',fine.z_diff_forward)


def test_horizontal_reflection_swaps_signal_order():
    a=section(left_top_width=.25e-3,right_top_width=.45e-3)
    b=section(left_width=.5e-3,right_width=.3e-3,left_thickness=50e-6,right_thickness=35e-6,
        left_top_width=.45e-3,right_top_width=.25e-3)
    for x,y in zip(a.traces,[b.traces[i] for i in [1,0]]):
        assert (x.x,x.y,x.width,x.thickness,x.top_width)==(-y.x,y.y,y.width,y.thickness,y.top_width)
    la,lb=a.analyze(**FINE),b.analyze(**FINE);errors=[]
    for key in ('C','C0','C_loss','L'):
        va,vb=getattr(la,key),getattr(lb,key)[::-1,::-1]
        errors.append(float(np.max(abs(va-vb))/np.max(abs(va))))
    errors.append(float(abs(la.z_diff_forward/lb.z_diff_forward-1)))
    print('conformal microstrip unequal reflected permutation',errors)
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
        a,b=asymmetric_coupled_conformal_coated_microstrip(**p).traces
        assert b.x0-a.x1==pytest.approx(p['gap'],rel=1e-12)


def test_correlated_widths_and_invalid_normal(monkeypatch):
    plan=study(sampling=dict(kind='normal',count=3,seed=41,correlation=[[1.,.4],[.4,1.]],variables=[
        dict(name='left_width',mean=.3e-3,std=.01e-3),dict(name='right_width',mean=.5e-3,std=.01e-3)]))
    assert ImpedanceStudyDocument.loads(plan.dumps()).dumps()==plan.dumps()
    assert plan.analyze().failed==0
    bad=study(fixed_pitch_m=None,sampling=dict(kind='normal',count=2,seed=41,correlation=[[1.]],variables=[dict(name='gap',mean=-.1e-3,std=1e-9)]))
    def forbidden(*args,**kwargs):pytest.fail('invalid negative gap meshed')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    out=bad.analyze();assert out.failed==2 and out.summary is None
    assert all(row.parameters['gap']<0 and row.document is None for row in out.rows)


@pytest.mark.parametrize('change',[dict(quantity='z_diff'),dict(fixed_pitch_m=.8e-3),
    dict(fixed_plane_spacing_m=1e-3),
    dict(sampling=dict(kind='sweep',count=2,variables=[dict(name='gap',lower=.2e-3,upper=.4e-3)])),
    dict(sampling=dict(kind='sweep',count=2,variables=[dict(name='left_width',lower=.2e-3,upper=2e-3)])),
    dict(fixed_pitch_m=None,sampling=dict(kind='sweep',count=2,
         variables=[dict(name='box_width',lower=.5e-3,upper=20e-3)]))])
def test_invalid_constraints_and_bounds_before_fields(change,monkeypatch):
    def forbidden(*args,**kwargs):pytest.fail('invalid bounded input meshed')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    with pytest.raises(ValueError):study(**change)


def test_material_yield_and_full_loss_line_replay():
    doc=study(fixed_pitch_m=None,frequency=1e9,materials={'substrate':ConstantDielectric(4.,.02),'coating':ConstantDielectric(3.3,.015)},
        material_variables={'dk':dict(region='coating',path=['eps_r'])},
        sampling=dict(kind='uniform',count=2,seed=31,variables=[dict(name='dk',lower=3.1,upper=3.5)]))
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
        assert json.loads(row.material_evaluation_json)['materials']['coating']['parameters']['eps_r']==row.sample_values[0]


def test_100ohm_fixed_pitch_goal_refinement_and_outer_sizes():
    doc=ImpedanceDesignDocument('asymmetric_coupled_conformal_coated_microstrip',PARAMS,variable='left_width',
        bounds=[.08e-3,.85e-3],target=100.,quantity='z_diff_forward',tolerance=1.,
        fixed_pitch_m=PITCH,max_evaluations=30,mesh=FINE)
    assert normalize_saved(doc.dumps())==doc.dumps()
    result=doc.solve()
    assert abs(result.residual)<=1. and abs(result.refined_residual)<=1.
    p=dict(PARAMS,left_width=result.parameter,gap=PITCH-(result.parameter+.5e-3)/2)
    residuals=[]
    for change in (dict(box_width=24e-3),dict(air_height=12e-3)):
        outer=asymmetric_coupled_conformal_coated_microstrip(**dict(p,**change)).analyze(**FINE).z_diff_forward
        assert abs(outer-100.)<=1. and abs(outer/result.impedance-1)<.005
        residuals.append(outer-100.)
    print('conformal microstrip unequal goal width/requested/refined/box/air',result.parameter,result.residual,result.refined_residual,residuals)


def test_thin_vacuum_pair_against_independent_image_panel_integral():
    from scipy.constants import c
    from test_coupled_coplanar import panel_reference
    # Dimensions are explicit and independent of SIPI geometry/mesh/solver.
    intervals=np.array([[-.55,-.25],[.05,.55]])*1e-3
    u=np.array([1.,-1.]);references=[]
    for count in (80,160):
        cap=panel_reference(intervals,.5e-3,count)[:2,:2]
        references.append((cap,float(u@np.linalg.solve(cap,u)/c)))
    cap,z=references[-1]
    reference_changes=[float(np.max(abs(references[0][0]-cap))/np.max(abs(cap))),abs(references[0][1]/z-1)]
    assert max(reference_changes)<.003
    p=dict(PARAMS,eps_r=1.,tan_delta=0.,coating_eps_r=1.,coating_tan_delta=0.,left_thickness=0.,right_thickness=0.)
    errors=[];lines=[]
    for mesh in (COARSE,FINE):
        line=asymmetric_coupled_conformal_coated_microstrip(**p).analyze(**mesh);lines.append(line)
        errors.append([float(np.max(abs(line.C-cap))/np.max(abs(cap))),abs(line.z_diff_forward/z-1)])
    print('conformal microstrip unequal thin reference refinement',reference_changes,'C/Z errors',errors,'reference Z',z)
    assert max(errors[-1])<.02
    assert np.all(np.array(errors[-1])<errors[0])
    wide=asymmetric_coupled_conformal_coated_microstrip(**dict(p,box_width=24e-3,air_height=12e-3)).analyze(**FINE)
    changes=relative(wide,lines[-1]);print('conformal microstrip unequal thin outer C/Z',changes)
    assert max(changes)<.01


def test_air_is_above_film_and_short_air_matches_equal_template():
    short=section(air_height=1e-6)
    assert short.height==pytest.approx(.571e-3,rel=1e-15)
    assert short.height-short.dielectric_regions[0]._shape.bounds[3]==pytest.approx(1e-6,rel=1e-10)
    common={k:v for k,v in PARAMS.items() if not k.startswith(('left_','right_'))};common['air_height']=1e-6
    old=coupled_conformal_coated_microstrip(width=.3e-3,thickness=35e-6,**common)
    new=asymmetric_coupled_conformal_coated_microstrip(left_width=.3e-3,right_width=.3e-3,left_thickness=35e-6,right_thickness=35e-6,**common)
    assert CrossSectionDocument(old).dumps()==CrossSectionDocument(new).dumps()


def test_vacuum_film_reduces_to_uncoated_at_same_top_height():
    coated=section(coating_eps_r=1.,coating_tan_delta=0.).analyze(**FINE)
    p={k:v for k,v in PARAMS.items() if not k.startswith('coating_')}
    p['air_height']=PARAMS['air_height']+max(PARAMS['left_thickness'],PARAMS['right_thickness'])+PARAMS['coating_thickness']
    uncoated=asymmetric_coupled_microstrip(**p).analyze(**FINE)
    errors=[float(np.max(abs(getattr(coated,key)-getattr(uncoated,key)))/np.max(abs(getattr(uncoated,key))))
            for key in ('C','C_loss','C0')]
    errors.append(float(abs(coated.z_diff_forward/uncoated.z_diff_forward-1)))
    print('conformal microstrip unequal vacuum-film reduction C/Closs/C0/Z',errors)
    assert max(errors)<.005


def test_correlated_coating_thickness_and_width_then_invalid_normal(monkeypatch):
    spec=dict(kind='normal',count=3,seed=41,correlation=[[1.,.4],[.4,1.]],variables=[
        dict(name='left_width',mean=.3e-3,std=.01e-3),
        dict(name='coating_thickness',mean=20e-6,std=2e-6)])
    plan=study(sampling=spec)
    result=plan.analyze();assert result.failed==0
    for values,row in zip(plan.samples(),result.rows):
        film=row.document.section.dielectric_regions[0]._shape
        assert film.bounds[3]==pytest.approx(.5e-3+50e-6+values[1],rel=1e-12)
        assert row.document.section.height-film.bounds[3]==pytest.approx(PARAMS['air_height'],rel=1e-12)
    bad=study(fixed_pitch_m=None,sampling=dict(kind='normal',count=2,seed=41,
        correlation=[[1.]],variables=[dict(name='coating_thickness',mean=-1e-6,std=1e-9)]))
    def forbidden(*args,**kwargs):pytest.fail('negative coating thickness meshed')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    out=bad.analyze();assert out.failed==2 and out.summary is None
    assert all(row.parameters['coating_thickness']<0 and row.document is None for row in out.rows)


@pytest.mark.parametrize('gap',[20e-6,40e-6,60e-6])
def test_unequal_height_side_films_meet_or_keep_explicit_air_gap(gap):
    from shapely.geometry import LineString
    cs=section(gap=gap);film=cs.dielectric_regions[0]._shape
    y=.5e-3+20e-6+35e-6/2
    cut=film.intersection(LineString([(-cs.width,y),(cs.width,y)]))
    segments=list(cut.geoms) if hasattr(cut,'geoms') else [cut]
    assert len(segments)==(1 if gap<=40e-6 else 2)
    assert not film.interiors and film.is_valid
    assert len(cs.dielectric_regions)==1
    document=CrossSectionDocument(cs)
    assert CrossSectionDocument.loads(document.dumps()).dumps()==document.dumps()


@pytest.mark.parametrize('change',[dict(coating_thickness=1e-300),dict(air_height=1e-300),
    dict(left_top_width=.4e-3),dict(right_top_width=.6e-3),dict(box_width=1.11e-3)])
def test_unresolved_overhanging_or_clipped_film_rejects(change):
    with pytest.raises(ValueError):section(**change)


def test_thin_conductors_reduce_to_planar_film_with_same_materials():
    from sipi import Layer
    p=dict(PARAMS,left_thickness=0.,right_thickness=0.)
    conformal=section(left_thickness=0.,right_thickness=0.).analyze(**FINE)
    bare=asymmetric_coupled_microstrip(**{k:v for k,v in p.items() if not k.startswith('coating_')})
    planar=CrossSection([bare.layers[0],Layer('coating',20e-6,3.3,.015),bare.layers[1]],bare.traces,bare.width).analyze(**FINE)
    errors=[float(np.max(abs(getattr(conformal,k)-getattr(planar,k)))/np.max(abs(getattr(planar,k)))) for k in ['C','C_loss','C0']]
    errors.append(float(abs(conformal.z_diff_forward/planar.z_diff_forward-1)))
    print('conformal unequal thin-planar reduction',errors)
    assert max(errors)<.005


def test_increasing_local_film_permittivity_raises_energy(fields):
    from sipi import capacitance_matrix
    m,_,_=fields;mesh=m.mesh
    film=np.array([mesh.region_names[i]=='coating' for i in mesh.regions])
    bare=capacitance_matrix(mesh,np.where(film,1.,m.eps_r),m.signals,m.ground)
    coated=capacitance_matrix(mesh,m.eps_r,m.signals,m.ground)
    assert np.any(film)
    assert np.linalg.eigvalsh(coated-bare).min()>=-1e-12*np.max(abs(coated))
