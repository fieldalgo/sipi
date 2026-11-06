# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Mitered normal-thickness films: exact geometry, field limits and saved studies."""
import importlib.metadata as metadata

import numpy as np
import pytest
from scipy.constants import epsilon_0
from shapely.geometry import LineString
from shapely.ops import unary_union
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import (CrossSectionDocument, ImpedanceDesignDocument, capacitance_matrix,
    conformal_coated_microstrip, coupled_conformal_coated_microstrip, microstrip, coupled_microstrip)
from sipi.templates import coated_microstrip, coupled_coated_microstrip
from sipi.dielectric import ConstantDielectric, PrincipalAxisDielectric, dispersive_line
from sipi.line_model import TransmissionLineDocument
from sipi.volume_line import VolumeLineDocument
from sipi.study import ImpedanceStudyDocument
from sipi.polygons import trace_shape

FACTORIES=(conformal_coated_microstrip,coupled_conformal_coated_microstrip)
COARSE=dict(edge_size=4e-6,far_size=.25e-3,grade=.2)
FINE=dict(edge_size=1e-6,far_size=.125e-3,grade=.1)


def parameters(factory,**changes):
    p=dict(width=.5e-3,substrate_height=.5e-3,eps_r=4,thickness=35e-6,
           top_width=.4e-3,tan_delta=.01,coating_thickness=20e-6,
           coating_eps_r=3.5,coating_tan_delta=.02,air_height=4e-3,box_width=8e-3)
    if factory is coupled_conformal_coated_microstrip:p['gap']=.3e-3
    p.update(changes);return p


@pytest.mark.parametrize('factory',FACTORIES)
@pytest.mark.parametrize('top',[None,.4e-3])
def test_film_area_normal_side_distance_height_and_symmetry(factory,top):
    p=parameters(factory,top_width=top);section=factory(**p)
    film=section.dielectric_regions[0]._shape;metal=unary_union([trace_shape(t) for t in section.traces])
    w,t,d,h=p['width'],p['thickness'],p['coating_thickness'],p['substrate_height']
    top=w if top is None else top
    # Independent offset-line intersection; no half-angle expression.
    slope=(w-top)/(2*t);delta=d/(np.hypot(1,slope)+slope)
    expected=section.width*d+2*delta*t*len(section.traces)
    assert film.difference(metal).area==pytest.approx(expected,rel=1e-12)
    assert film.bounds[1]==h and film.bounds[3]==pytest.approx(h+t+d,rel=1e-12)
    assert section.height-film.bounds[3]==pytest.approx(p['air_height'],rel=1e-12)
    cut=film.intersection(LineString([(-section.width,h+d+t/2),(section.width,h+d+t/2)]))
    segments=list(cut.geoms) if hasattr(cut,'geoms') else [cut]
    segments.sort(key=lambda part:part.bounds[0])
    for trace,segment in zip(section.traces,segments):
        x=segment.bounds[0];y=h+d+t/2
        distance=abs(x-slope*(y-h)-(trace.x-w/2))/np.hypot(1,slope)
        assert distance==pytest.approx(d,rel=1e-12)
    from shapely.affinity import scale
    assert film.symmetric_difference(scale(film,xfact=-1,yfact=1,origin=(0,0))).area<1e-12*film.area
    assert not film.interiors and all(film.covers(trace_shape(t)) for t in section.traces)


@pytest.mark.parametrize('gap',[20e-6,40e-6,60e-6])
def test_meeting_side_films_union_without_overlapping_materials_or_pockets(gap):
    p=parameters(coupled_conformal_coated_microstrip,top_width=None,gap=gap)
    section=coupled_conformal_coated_microstrip(**p)
    film=section.dielectric_regions[0]._shape
    assert film.is_valid and not film.interiors and len(section.dielectric_regions)==1
    h,t,d=p['substrate_height'],p['thickness'],p['coating_thickness']
    cut=film.intersection(LineString([(-section.width,h+d+t/2),(section.width,h+d+t/2)]))
    count=len(cut.geoms) if hasattr(cut,'geoms') else 1
    assert count==(1 if gap<=2*d else 2)
    assert CrossSectionDocument.loads(CrossSectionDocument(section).dumps()).dumps()==CrossSectionDocument(section).dumps()


@pytest.mark.parametrize('factory',FACTORIES)
def test_thin_conductor_reduces_to_existing_planar_coating(factory):
    p=parameters(factory,thickness=0,top_width=None)
    conformal=factory(**p).analyze(**FINE)
    other=coated_microstrip if factory is conformal_coated_microstrip else coupled_coated_microstrip
    flat=dict(p);flat['coating_height']=flat.pop('coating_thickness')
    planar=other(**flat).analyze(**FINE)
    np.testing.assert_allclose(conformal.C-1j*conformal.C_loss,planar.C-1j*planar.C_loss,rtol=.005,atol=0)


@pytest.mark.parametrize('factory',FACTORIES)
def test_air_film_reduces_to_uncoated_same_exterior(factory):
    p=parameters(factory,coating_eps_r=1,coating_tan_delta=0)
    coated=factory(**p).analyze(**FINE)
    other=microstrip if factory is conformal_coated_microstrip else coupled_microstrip
    bare={k:v for k,v in p.items() if not k.startswith('coating_')}
    bare['air_height']+=p['thickness']+p['coating_thickness']
    uncoated=other(**bare).analyze(**FINE)
    np.testing.assert_allclose(coated.C-1j*coated.C_loss,uncoated.C-1j*uncoated.C_loss,rtol=.005,atol=0)


@pytest.mark.parametrize('factory',FACTORIES)
def test_complex_field_independent_fem_mesh_outer_and_dielectric_monotonicity(factory):
    skfem=require_tool('scikit-fem')
    from skfem.helpers import dot,grad
    p=parameters(factory);section=factory(**p);meshed=section.mesh(**COARSE);mesh=meshed.mesh
    clock=Stopwatch()
    with clock('openphysics'): actual=meshed.line_parameters()
    eps=meshed.eps_r*(1-1j*meshed.tan_delta)
    with clock('reference'):
        basis=skfem.Basis(skfem.MeshTri(mesh.nodes.T,mesh.triangles.T),skfem.ElementTriP1())
        @skfem.BilinearForm(dtype=complex)
        def form(u,v,w):return w.eps*dot(grad(u),grad(v))
        k=skfem.asm(form,basis,eps=eps[:,None]);fields=[]
        fixed=np.unique(np.concatenate([meshed.ground,*meshed.signals.values()]))
        for nodes in meshed.signals.values():
            v=np.zeros(basis.N,complex);v[nodes]=1
            fields.append(skfem.solve(*skfem.condense(k,np.zeros(basis.N,complex),x=v,D=fixed)))
        u=np.array(fields).T;expected=epsilon_0*(u.T@(k@u))
    cc=actual.C-1j*actual.C_loss
    error=float(abs(cc/expected-1).max())
    record=make_record(case=factory.__name__+'-complex-capacitance',physics='mitered normal-thickness dielectric film',
        api='sipi.'+factory.__name__,discretization='exact polygon film union and conforming P1 regions',
        tool='scikit-fem',tool_discretization='independent complex P1 assembly and energy',
        matched=['same mesh, metal priority, substrate/film loss and open exterior'],
        not_matched=['no measured deposition shape, meniscus, rounded corners or 3D fields'],
        observables=[observable('complex C','F/m','max relative difference',error,1e-9)],
        analytical_acceptance='exact film area/normal distances, planar and air limits, separate mesh/domain convergence',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    assert error<1e-9
    refined=section.analyze(**FINE)
    outer=factory(**dict(p,box_width=2*p['box_width'],air_height=2*p['air_height'])).analyze(**FINE)
    fine=refined.C-1j*refined.C_loss;wide=outer.C-1j*outer.C_loss
    mesh_change=float(abs(cc/fine-1).max());outer_change=float(abs(wide/fine-1).max())
    assert mesh_change<.01 and outer_change<.01
    print(factory.__name__,'complex C mesh/outer',mesh_change,outer_change)
    # Same-mesh real dielectric increase must raise the Maxwell C quadratic form.
    coating=np.array([mesh.region_names[i]=='coating' for i in mesh.regions])
    bare=capacitance_matrix(mesh,np.where(coating,1.,meshed.eps_r),meshed.signals,meshed.ground)
    real=capacitance_matrix(mesh,meshed.eps_r,meshed.signals,meshed.ground)
    assert np.linalg.eigvalsh(real-bare).min()>=-1e-12*abs(real).max()
    assert np.linalg.eigvalsh(actual.C_loss).min()>0


@pytest.mark.parametrize('factory',FACTORIES)
def test_geometry_json_and_layer_material_override_replay(factory):
    section=factory(**parameters(factory));document=CrossSectionDocument(section,mesh=COARSE)
    restored=CrossSectionDocument.loads(document.dumps())
    assert document.to_dict()['schema']=='sipi.cross-section/3' and restored.dumps()==document.dumps()
    constant=ConstantDielectric(3.5,.02)
    line=TransmissionLineDocument(restored,[1e6,1e9],
        materials={'coating':PrincipalAxisDielectric(constant,constant,.3)},
        conductor={'kind':'perfect'},length=.01)
    result=TransmissionLineDocument.loads(line.dumps()).analyze()
    original=document.analyze()
    np.testing.assert_allclose(result.C,np.broadcast_to(original.C,result.C.shape),rtol=1e-10,atol=0)
    np.testing.assert_allclose(result.dielectric.C_complex.imag,
        np.broadcast_to(-original.C_loss,result.C.shape),rtol=1e-10,atol=0)
    assert result.dielectric.layer_permittivity['coating'].shape==(2,2,2)


@pytest.mark.parametrize('factory',FACTORIES)
def test_seeded_geometry_tolerances_frequency_materials_and_fixed_pitch(factory):
    p=parameters(factory);pair=factory is coupled_conformal_coated_microstrip
    model=PrincipalAxisDielectric(ConstantDielectric(2.5,.01),ConstantDielectric(4,.02))
    spec=dict(kind='normal',count=2,seed=230,correlation=[[1,.6],[.6,1]],variables=[
        dict(name='width',mean=.5e-3,std=10e-6),dict(name='coating_thickness',mean=20e-6,std=2e-6)])
    plan=ImpedanceStudyDocument(factory.__name__,p,sampling=spec,quantity='z_diff' if pair else 'z0',
        mesh=COARSE,fixed_pitch_m=.8e-3 if pair else None,frequency=1e8,materials={'coating':model})
    replay=ImpedanceStudyDocument.loads(plan.dumps())
    np.testing.assert_array_equal(replay.samples(),plan.samples())
    result=replay.analyze();assert result.failed==0 and result.summary is not None
    for row in result.rows:
        if pair:assert row.parameters['width']+row.parameters['gap']==pytest.approx(.8e-3,rel=1e-12)
        sweep=dispersive_line(row.document.section,[1e8],materials={'coating':model},**row.document.mesh_options)
        mode=np.array([1,-1]) if pair else np.ones(1)
        expected=(2 if pair else 1)*np.sqrt((mode@sweep.L@mode)/(mode@sweep.C[0]@mode))
        assert row.impedance==pytest.approx(expected,rel=1e-10)


@pytest.mark.parametrize('factory',FACTORIES)
def test_saved_width_goal_has_requested_and_refined_acceptance(factory):
    p=parameters(factory,top_width=None);pair=factory is coupled_conformal_coated_microstrip
    goal=ImpedanceDesignDocument(factory.__name__,p,variable='width',bounds=[.3e-3,1.2e-3],
        quantity='z_diff' if pair else 'z0',target=100 if pair else 60,tolerance=1,
        max_evaluations=24,mesh=COARSE)
    result=ImpedanceDesignDocument.loads(goal.dumps()).solve()
    assert abs(result.residual)<=1 and abs(result.refined_residual)<=1
    assert result.document.to_dict()['schema']=='sipi.cross-section/3'
    print(factory.__name__,'width goal',result.parameter,result.residual,result.refined_residual)


def test_conformal_region_is_preserved_in_matched_volume_extraction():
    section=conformal_coated_microstrip(**parameters(conformal_coated_microstrip,box_width=4e-3,air_height=1e-3))
    doc=VolumeLineDocument(CrossSectionDocument(section),[1e3],materials={},conductivity=58e6,length=.01,
        mesh=dict(ground_thickness=.1e-3,padding=1e-3,metal_size=15e-6,
                  far_size=.3e-3,grade=.2,min_angle=28))
    restored=VolumeLineDocument.loads(doc.dumps());assert restored.dumps()==doc.dumps()
    result=restored.analyze()
    assert np.all(result.C>0) and np.all(result.G>0)
    assert np.linalg.svd(result.network.s,compute_uv=False).max()<=1+1e-10
    assert result.input_json==doc.dumps()


@pytest.mark.parametrize('factory',FACTORIES)
@pytest.mark.parametrize('changes',[
    dict(coating_thickness=0),dict(coating_thickness=-1),dict(coating_thickness=True),
    dict(coating_thickness=np.nan),dict(coating_thickness=1e-300),
    dict(coating_eps_r=.5),dict(coating_tan_delta=-.01),dict(top_width=.6e-3),
    dict(air_height=0),dict(air_height=1e-300),
])
def test_invalid_or_unresolved_film_inputs_are_rejected(factory,changes):
    with pytest.raises(ValueError):factory(**parameters(factory,**changes))


def test_lateral_coating_is_not_silently_clipped_and_upper_air_can_be_thin():
    p=parameters(conformal_coated_microstrip,box_width=.51e-3,top_width=None)
    with pytest.raises(ValueError,match='outside box_width'):conformal_coated_microstrip(**p)
    section=conformal_coated_microstrip(**parameters(conformal_coated_microstrip,air_height=1e-6))
    assert section.height-section.dielectric_regions[0]._shape.bounds[3]==pytest.approx(1e-6,rel=1e-10)
