# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Unequal buried pair: independent fields, fixed pitch and saved targets."""
from dataclasses import replace
from importlib import metadata
import json

import numpy as np
import pytest

from sipi import (asymmetric_coupled_stripline, CrossSection, CrossSectionDocument,
                  ImpedanceDesignDocument)
from sipi.templates import coupled_stripline, stripline
from sipi.constants import epsilon_0, mu_0
from sipi.study import ImpedanceStudyDocument
from sipi.dielectric import ConstantDielectric
from sipi.execution import normalize_saved, execute_saved
from sipi.yield_assessment import ImpedanceYieldDocument
from sipi.line_study import LineQuantityStudyDocument
from crosscheck import require_tool, Stopwatch, make_record, observable, emit

PARAMS = dict(left_width=.3e-3, right_width=.5e-3, gap=.4e-3, plane_spacing=1e-3,
    eps_r=4., left_thickness=35e-6, right_thickness=50e-6, tan_delta=.02, box_width=6e-3)
COARSE = dict(edge_size=5e-6, far_size=.25e-3, grade=.2)
FINE = dict(edge_size=2.5e-6, far_size=.125e-3, grade=.1)
PITCH = .8e-3


def section(**changes):
    return asymmetric_coupled_stripline(**dict(PARAMS, **changes))


def study(**changes):
    options = dict(quantity='z_diff_forward', mesh=COARSE, fixed_pitch_m=PITCH,
        sampling=dict(kind='uniform', count=2, seed=71,
            variables=[dict(name='left_width',lower=.28e-3,upper=.32e-3)]))
    options.update(changes)
    return ImpedanceStudyDocument('asymmetric_coupled_stripline', PARAMS, **options)


def test_explicit_geometry_midpoints_horizontal_span_and_json():
    s = section(left_top_width=.25e-3, right_top_width=.45e-3)
    left,right = s.traces
    assert (left.name,right.name)==('positive','negative')
    assert left.y+left.thickness/2==pytest.approx(.5e-3,rel=1e-15)
    assert right.y+right.thickness/2==pytest.approx(.5e-3,rel=1e-15)
    assert left.y != right.y
    assert right.x0-left.x1==pytest.approx(.4e-3,rel=1e-12)
    # Algebraically equal endpoint expressions can differ by one float ULP.
    assert abs(left.x0+right.x1)<=np.spacing(max(abs(left.x0),abs(right.x1)))
    assert right.x-left.x==pytest.approx(PITCH,rel=1e-12)
    assert s.top=='ground' and s.bottom=='ground' and s.sides=='open'
    assert len(s.layers)==1 and s.layers[0].eps_r==4.
    doc=CrossSectionDocument(s,mesh=COARSE)
    assert doc.to_dict()['schema']=='sipi.cross-section/2'
    assert CrossSectionDocument.loads(doc.dumps()).dumps()==doc.dumps()
    assert section(box_width=None).width==max(12e-3,4*1.2e-3)


@pytest.mark.parametrize('thickness,top',[(0,None),(35e-6,None),(35e-6,.25e-3),(35e-6,.4e-3)])
def test_symmetric_reduction_is_identical_geometry(thickness,top):
    shared=dict(gap=.4e-3,plane_spacing=1e-3,eps_r=4.,tan_delta=.02)
    old=coupled_stripline(width=.3e-3,thickness=thickness,top_width=top,**shared)
    new=asymmetric_coupled_stripline(left_width=.3e-3,right_width=.3e-3,
        left_thickness=thickness,right_thickness=thickness,left_top_width=top,right_top_width=top,**shared)
    assert CrossSectionDocument(new).dumps()==CrossSectionDocument(old).dumps()


def test_left_right_swap_is_reflected_geometry():
    a=section(left_top_width=.25e-3,right_top_width=.45e-3)
    b=section(left_width=.5e-3,right_width=.3e-3,left_thickness=50e-6,right_thickness=35e-6,
              left_top_width=.45e-3,right_top_width=.25e-3)
    for x,y in zip(a.traces,reversed(b.traces)):
        assert (x.x,x.y,x.width,x.thickness,x.top_width)==(-y.x,y.y,y.width,y.thickness,y.top_width)


@pytest.mark.parametrize('change',[dict(left_width=0),dict(right_width=True),dict(gap=0),
    dict(gap=float('nan')),dict(plane_spacing=0),dict(left_thickness=-1),
    dict(right_thickness=1e-3),dict(eps_r=.5),dict(eps_r=True),dict(tan_delta=-.1),
    dict(box_width=1e-3),dict(left_top_width=3e-3),dict(left_thickness=0,left_top_width=.2e-3)])
def test_invalid_geometry_before_mesh(change):
    with pytest.raises(ValueError):section(**change)


@pytest.fixture(scope='module')
def fields():
    m=section().mesh(**COARSE)
    return m,m.line_parameters(),section().analyze(**FINE),section(box_width=12e-3).analyze(**FINE)


def test_independent_complex_and_vacuum_energy(fields):
    skfem=require_tool('scikit-fem')
    from skfem.helpers import dot,grad
    m,_,_,_=fields;clock=Stopwatch()
    with clock('openphysics'):actual=m.line_parameters()
    with clock('reference'):
        basis=skfem.Basis(skfem.MeshTri(m.mesh.nodes.T,m.mesh.triangles.T),skfem.ElementTriP1())
        @skfem.BilinearForm(dtype=complex)
        def form(u,v,w):return w.eps*dot(grad(u),grad(v))
        fixed=np.unique(np.concatenate([m.ground,*m.signals.values()]))
        expected=[]
        for eps in (m.eps_r*(1-1j*m.tan_delta),np.ones_like(m.eps_r)):
            k=skfem.asm(form,basis,eps=eps[:,None]);columns=[]
            for nodes in m.signals.values():
                v=np.zeros(basis.N,complex);v[nodes]=1
                columns.append(skfem.solve(*skfem.condense(k,np.zeros(basis.N,complex),x=v,D=fixed)))
            u=np.array(columns).T;expected.append(epsilon_0*(u.T@(k@u)))
    errors=[float(np.max(abs(a-b))/np.max(abs(b))) for a,b in
        [(actual.C,expected[0].real),(actual.C_loss,-expected[0].imag),(actual.C0,expected[1].real)]]
    record=make_record(case='asymmetric-buried-pair',physics='homogeneous lossy electrostatics',
        api='sipi.asymmetric_coupled_stripline',discretization='P1 unequal conductors centred vertically between planes',
        tool='scikit-fem',tool_discretization='independent complex/vacuum P1 energy assembly',
        matched=['same mesh, grounded planes, insulated sides and conductor order','same homogeneous material coefficients'],
        not_matched=['no measured-board validation or independent geometric mesh'],
        observables=[observable(name,'F/m','max normalized matrix difference',error,1e-10)
            for name,error in zip(('C','C_loss','C0'),errors)],
        analytical_acceptance='homogeneous scaling, identical symmetric geometry, isolated-stripline limit; separate mesh/box gates',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    assert max(errors)<1e-10


def test_homogeneous_identities_and_separate_mesh_box_convergence(fields):
    m,coarse,fine,outer=fields
    errors=[]
    for other,gate in [(coarse,.015),(outer,.005)]:
        values=[float(np.max(abs(other.C-fine.C))/np.max(abs(fine.C))),
                float(abs(other.z_diff_forward/fine.z_diff_forward-1))]
        errors.append(values);assert max(values)<gate
    for matrix in (fine.C,fine.C0,fine.C_loss,fine.L):
        np.testing.assert_allclose(matrix,matrix.T,atol=0,rtol=1e-12)
        assert np.linalg.eigvalsh(matrix).min()>0
    np.testing.assert_allclose(coarse.C,4*coarse.C0,atol=0,rtol=1e-12)
    np.testing.assert_allclose(coarse.C_loss,.02*coarse.C,atol=0,rtol=1e-12)
    np.testing.assert_allclose(coarse.L,mu_0*epsilon_0*np.linalg.inv(coarse.C0),atol=0,rtol=1e-12)
    changed=replace(m,eps_r=4*m.eps_r).line_parameters()
    assert changed.z_diff_forward==pytest.approx(coarse.z_diff_forward/2,rel=1e-12)
    u=np.array([1.,-1.])
    expected=np.sqrt(mu_0*epsilon_0/4)*(u@np.linalg.solve(coarse.C0,u))
    assert coarse.z_diff_forward==pytest.approx(expected,rel=1e-12)
    print('unequal buried C/Z mesh/outer',errors,'fine Z',fine.z_diff_forward)


def test_wide_separation_approaches_two_isolated_striplines():
    pair=section(gap=5e-3,box_width=32e-3).analyze(**FINE)
    singles=[stripline(width=w,thickness=t,plane_spacing=1e-3,eps_r=4.,tan_delta=.02,
        box_width=32e-3).analyze(**FINE).C[0,0] for w,t in [(.3e-3,35e-6),(.5e-3,50e-6)]]
    self_error=abs(np.diag(pair.C)/singles-1)
    cross=abs(pair.C[0,1])/max(np.diag(pair.C))
    print('isolated self/cross errors',self_error.tolist(),cross)
    assert max(self_error)<.01 and cross<1e-4


@pytest.mark.parametrize('kind',['sweep','corners','uniform','normal'])
@pytest.mark.parametrize('name',['left_width','right_width'])
def test_fixed_pitch_sampling_and_canonical_replay(kind,name):
    spec=dict(kind=kind,variables=[dict(name=name,lower=PARAMS[name]*.9,upper=PARAMS[name]*1.1)])
    if kind!='corners':spec['count']=3
    if kind in ('uniform','normal'):spec['seed']=19
    if kind=='normal':
        spec['variables']=[dict(name=name,mean=PARAMS[name],std=PARAMS[name]*.01)]
        spec['correlation']=[[1.]]
    doc=study(sampling=spec)
    assert normalize_saved(doc.dumps())==doc.dumps()
    for row,p in zip(doc.samples(),doc.sample_parameters()):
        assert p[name]==row[0]
        assert p['gap']==pytest.approx(PITCH-(p['left_width']+p['right_width'])/2,rel=1e-12)
        section_=asymmetric_coupled_stripline(**p)
        assert section_.traces[1].x-section_.traces[0].x==pytest.approx(PITCH,rel=1e-12)


def test_correlated_widths_normal_failures_and_forward_only_contract(monkeypatch):
    spec=dict(kind='normal',count=3,seed=19,correlation=[[1.,.5],[.5,1.]],variables=[
        dict(name='left_width',mean=.3e-3,std=.01e-3),dict(name='right_width',mean=.5e-3,std=.01e-3)])
    doc=study(sampling=spec)
    for p in doc.sample_parameters():
        assert p['gap']+(p['left_width']+p['right_width'])/2==pytest.approx(PITCH,rel=1e-12)
    with pytest.raises(ValueError,match='z_diff_forward'):study(quantity='z_diff')
    with pytest.raises(ValueError):study(fixed_pitch_m=.9e-3)
    with pytest.raises(ValueError):study(sampling=dict(kind='sweep',count=2,
        variables=[dict(name='gap',lower=.3e-3,upper=.5e-3)]))
    invalid=study(sampling=dict(kind='normal',count=2,seed=3,correlation=[[1.]],
        variables=[dict(name='left_width',mean=2e-3,std=1e-9)]))
    def forbidden(*args,**kwargs):pytest.fail('invalid normal geometry reached meshing')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    result=invalid.analyze()
    assert result.failed==2 and result.summary is None
    assert all(row.parameters['gap']<0 and row.document is None for row in result.rows)


def test_material_binding_yield_and_lossy_study_homogeneous_reference():
    spec=dict(kind='uniform',count=2,seed=71,variables=[dict(name='dk',lower=3.8,upper=4.2)])
    doc=study(fixed_pitch_m=None,frequency=1e9,materials={'dielectric':ConstantDielectric(4.,.02)},
        material_variables={'dk':dict(region='dielectric',path=['eps_r'])},sampling=spec)
    assert doc.to_dict()['schema']=='sipi.impedance-study/4'
    assert normalize_saved(doc.dumps())==doc.dumps()
    direct=doc.analyze()
    result=execute_saved(ImpedanceYieldDocument(doc,minimum=1.,maximum=1000.).dumps(),max_evaluations=2)
    assert result['status']=='complete' and result['result']['passed']==2
    for row,reference in zip(result['result']['rows'],direct.rows):
        assert row['impedance_ohm']==reference.impedance
    lossy=LineQuantityStudyDocument(doc,conductor=dict(kind='perfect'),
        quantity='differential_forward_impedance_real',schema='sipi.line-quantity-study/2')
    solved=lossy.analyze(max_evaluations=2)
    assert solved.failed==0
    c0=section().analyze(**COARSE).C0;u=np.array([1.,-1.])
    for row in solved.rows:
        dk=row.sample_values[0]
        expected=np.sqrt(mu_0*epsilon_0/(dk*(1-.02j)))*np.linalg.inv(c0)
        np.testing.assert_allclose(row.result.characteristic().z_characteristic[0],expected,atol=0,rtol=1e-10)
        assert row.value==pytest.approx(float((u@expected@u).real),rel=1e-10)
        assert json.loads(row.material_evaluation_json)['materials']['dielectric']['parameters']['eps_r']==dk


def test_fixed_pitch_100ohm_goal_refinement_and_outer_box():
    doc=ImpedanceDesignDocument('asymmetric_coupled_stripline',PARAMS,variable='left_width',
        bounds=[.2e-3,.9e-3],target=100.,quantity='z_diff_forward',tolerance=1.,
        fixed_pitch_m=PITCH,max_evaluations=24,mesh=FINE)
    assert normalize_saved(doc.dumps())==doc.dumps()
    result=doc.solve()
    assert abs(result.residual)<=1. and abs(result.refined_residual)<=1.
    p=dict(PARAMS,left_width=result.parameter,gap=PITCH-(result.parameter+.5e-3)/2,box_width=12e-3)
    enlarged=asymmetric_coupled_stripline(**p).analyze(**FINE).z_diff_forward
    assert abs(enlarged-100.)<=1. and abs(enlarged/result.impedance-1)<.005
    assert result.document.section.traces[1].x-result.document.section.traces[0].x==pytest.approx(PITCH,rel=1e-12)
    print('asymmetric buried goal width/residual/refined/outer',result.parameter,result.residual,
          result.refined_residual,enlarged-100.)
