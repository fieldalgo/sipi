# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Analytic fields, independent assembly, saved execution and material leaves."""
from types import SimpleNamespace
from importlib import metadata
import json
import numpy as np
import pytest
from scipy.constants import epsilon_0
from galerkin import Mesh
from galerkin.mesh import rectangle_mesh,annulus_mesh
from sipi.dielectric import TensorDebyeDielectric
from crosscheck import require_tool,Stopwatch,make_record,observable,emit
from sipi import CrossSection,CrossSectionDocument,coupled_microstrip
import sipi.dielectric as dielectric
from sipi.line_model import TransmissionLineDocument
from sipi.study import ImpedanceStudyDocument
from sipi.design_document import ImpedanceDesignDocument
from sipi.execution import normalize_saved
from sipi.execution_request import SavedExecutionRequest

F=np.array([1e6,1e8,1e10])


def model():
    return TensorDebyeDielectric([2,3],[[4,.5],[.25,3]],[1e8,1e10],[0,np.pi/4])


def test_aligned_layered_complex_series_capacitor():
    base=rectangle_mesh(.01,.002,16,8)
    regions=(base.nodes[base.triangles].mean(axis=1)[:,1]>=.001).astype(int)
    mesh=Mesh(base.nodes,base.triangles,base.boundary,regions=regions,region_names=['lower','upper'])
    meshed=SimpleNamespace(mesh=mesh,signals={'top':mesh.boundary['top']},ground=mesh.boundary['bottom'])
    lower=TensorDebyeDielectric([2,3],[[4,.5],[.25,3]],[1e8,1e10],[0,0])
    upper=dielectric.ConstantDielectric(4,.03)
    out=dielectric._dispersive_from_mesh(meshed,F,{'lower':lower.permittivity(F),'upper':upper.permittivity(F)})
    yy=3+.5/(1+1j*F/1e8)+3/(1+1j*F/1e10)
    exact=epsilon_0*.01/(.001/yy+.001/(4*(1-.03j)))
    np.testing.assert_allclose(out.C_complex[:,0,0],exact,rtol=1e-9,atol=0)
    np.testing.assert_allclose(out.G[:,0,0],-2*np.pi*F*exact.imag,rtol=1e-9,atol=0)


def test_common_shape_transformed_elliptic_coax_convergence():
    angle=.4;c,s=np.cos(angle),np.sin(angle);q=np.array([[c,-s],[s,c]])
    root=q@np.diag(np.sqrt([2.,5.]))@q.T
    material=TensorDebyeDielectric([2,5],[[8,20],[2,5]],[1e8,1e10],[angle,angle],angle)
    factor=1+4/(1+1j*F/1e8)+1/(1+1j*F/1e10)
    exact=2*np.pi*epsilon_0*np.sqrt(10)*factor/np.log(3)
    errors=[]
    for nr,nt in [(16,64),(32,128),(64,256)]:
        base=annulus_mesh(.5e-3,1.5e-3,nr,nt)
        mesh=Mesh(base.nodes@root.T,base.triangles.copy(),base.boundary,
            regions=np.zeros(base.num_triangles,int),region_names=['material'])
        meshed=SimpleNamespace(mesh=mesh,signals={'inner':mesh.boundary['inner']},ground=mesh.boundary['outer'])
        out=dielectric._dispersive_from_mesh(meshed,F,{'material':material.permittivity(F)})
        errors.append(float(np.max(abs(out.C_complex[:,0,0]/exact-1))))
    print('tensor Debye transformed coax errors',errors)
    assert errors[2]<errors[1]<errors[0]
    assert errors[-1]<.001 and np.log2(errors[-2]/errors[-1])>=1.5


def test_unequal_angle_frequency_fields_independent_fem_and_separate_outer_sizes():
    skfem=require_tool('scikit-fem')
    from skfem.helpers import grad
    p=dict(width=.5e-3,gap=.3e-3,substrate_height=.5e-3,eps_r=4,
        thickness=35e-6,air_height=4e-3,box_width=8e-3)
    coarse=dict(edge_size=4e-6,far_size=.25e-3,grade=.2)
    fine=dict(edge_size=1e-6,far_size=.125e-3,grade=.1)
    section=coupled_microstrip(**p);material=model();clock=Stopwatch()
    with clock('openphysics'):actual=dielectric.dispersive_line(section,F,materials={'substrate':material},**coarse)
    meshed=section.mesh(**coarse);mesh=meshed.mesh
    basis=skfem.Basis(skfem.MeshTri(mesh.nodes.T,mesh.triangles.T),skfem.ElementTriP1())
    @skfem.BilinearForm(dtype=complex)
    def form(u,v,w):return np.einsum('ij...,j...,i...->...',w.eps,grad(u),grad(v))
    fixed=np.unique(np.concatenate([meshed.ground,*meshed.signals.values()]));errors=[]
    for i,f in enumerate(F):
        # Sample coefficients directly from the independent rational construction.
        eps_tensor=np.diag([2.,3.]).astype(complex)
        for values,pole,angle in zip([[4,.5],[.25,3]],[1e8,1e10],[0,np.pi/4]):
            c,s=np.cos(angle),np.sin(angle);q=np.array([[c,-s],[s,c]])
            eps_tensor+=(q@np.diag(values)@q.T)/(1+1j*f/pole)
        eps=np.array([eps_tensor if mesh.region_names[k]=='substrate' else np.eye(2) for k in mesh.regions])
        with clock('reference'):
            k=skfem.asm(form,basis,eps=eps.transpose(1,2,0)[:,:,:,None]);columns=[]
            for nodes in meshed.signals.values():
                v=np.zeros(basis.N,complex);v[nodes]=1
                columns.append(skfem.solve(*skfem.condense(k,np.zeros(basis.N,complex),x=v,D=fixed)))
            u=np.array(columns).T;expected=epsilon_0*(u.T@(k@u))
        errors.append(float(np.max(abs(actual.C_complex[i]-expected))/np.max(abs(expected))))
    record=make_record(case='tensor-debye-unequal-angle-coupled-line',physics='reciprocal transverse tensor relaxation',
        api='sipi.dielectric.dispersive_line',discretization='oriented positive-semidefinite residues on shared P1 mesh',
        tool='scikit-fem',tool_discretization='independent rational tensors, complex P1 assembly and energy',
        matched=['same mesh, boundaries and three declared frequencies'],
        not_matched=['no independent geometric mesh or measured material data'],
        observables=[observable('complex C','F/m','maximum normalized matrix error',max(errors),1e-9)],
        analytical_acceptance='series capacitor, transformed coax and separate mesh/box/air checks',stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    assert max(errors)<1e-9
    refined=dielectric.dispersive_line(section,F,materials={'substrate':material},**fine)
    changes={'mesh':float(np.max(abs(actual.C_complex/refined.C_complex-1)))}
    assert changes['mesh']<.01
    for label,change in [('box',dict(box_width=16e-3)),('air',dict(air_height=8e-3))]:
        other=dielectric.dispersive_line(coupled_microstrip(**dict(p,**change)),F,materials={'substrate':material},**fine)
        changes[label]=float(np.max(abs(other.C_complex/refined.C_complex-1)))
        assert changes[label]<.01
    print('tensor Debye coupled mesh/outer',changes)
    network=actual.network(length=.01,R=np.zeros((2,2)))
    np.testing.assert_allclose(network.s,network.s.swapaxes(-1,-2),rtol=0,atol=1e-10)
    assert np.linalg.svd(network.s,compute_uv=False).max()<=1+1e-10


def test_saved_line_and_immutable_request_preserve_model_and_output():
    section=coupled_microstrip(width=.5e-3,gap=.3e-3,substrate_height=.5e-3,
        eps_r=4,thickness=35e-6,air_height=4e-3,box_width=8e-3)
    document=TransmissionLineDocument(CrossSectionDocument(section,mesh=dict(edge_size=10e-6,far_size=.25e-3,grade=.2)),
        F,materials={'substrate':model()},conductor={'kind':'perfect'},length=.01)
    restored=TransmissionLineDocument.loads(document.dumps())
    assert restored.dumps()==document.dumps()==normalize_saved(document.dumps())
    direct=document.analyze();again=restored.analyze()
    for name in ['R','L','G','C']:
        np.testing.assert_allclose(getattr(again,name),getattr(direct,name),rtol=1e-10,atol=0)
    request=SavedExecutionRequest(document.dumps(),max_evaluations=3)
    receipt=request.run()
    assert receipt['execution']['status']=='complete'
    assert receipt['execution']['input']==json.loads(document.dumps())
    assert receipt['request']['input']['materials']['substrate']['schema']=='sipi.dielectric/3'
    np.testing.assert_allclose(receipt['execution']['result']['C_f_per_m'],direct.C,rtol=1e-10,atol=0)


def test_material_leaf_study_and_original_failed_normal_rows(monkeypatch):
    p=dict(left_width=.3e-3,right_width=.5e-3,gap=.3e-3,substrate_height=.5e-3,
        eps_r=4,left_thickness=35e-6,right_thickness=50e-6,air_height=6e-3,box_width=12e-3)
    args=dict(quantity='z_diff_forward',mesh=dict(edge_size=5e-6,far_size=.25e-3,grade=.2),
        frequency=1e8,materials={'substrate':model()},
        material_variables={'d':dict(region='substrate',path=['strengths',0,0])})
    doc=ImpedanceStudyDocument('asymmetric_coupled_microstrip',p,**args,
        sampling=dict(kind='uniform',count=2,seed=71,variables=[dict(name='d',lower=2.,upper=4.)]))
    assert doc.to_dict()['schema']=='sipi.impedance-study/4' and normalize_saved(doc.dumps())==doc.dumps()
    result=doc.analyze();assert result.failed==0
    for row,sample in zip(result.rows,doc.samples()):
        evaluation=json.loads(row.material_evaluation_json)
        assert evaluation['materials']['substrate']['parameters']['strengths'][0][0]==sample[0]
        material=dielectric.dielectric_from_dict(evaluation['materials']['substrate'])
        replay=dielectric.dispersive_line(row.document.section,[1e8],materials={'substrate':material},**row.document.mesh_options)
        from sipi.quasistatic import LineParameters
        line=LineParameters(replay.names,replay.C[0],replay.C0,replay.L,-replay.C_complex[0].imag)
        assert line.z_diff_forward==pytest.approx(row.impedance,rel=1e-10)
    bad=ImpedanceStudyDocument('asymmetric_coupled_microstrip',p,**args,
        sampling=dict(kind='normal',count=2,seed=71,correlation=[[1.]],variables=[dict(name='d',mean=-1.,std=1e-9)]))
    def forbidden(*a,**k):pytest.fail('negative residue reached mesh')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    failed=bad.analyze();assert failed.failed==2 and failed.summary is None and len(failed.rows)==2
    for row,sample in zip(failed.rows,bad.samples()):
        actual=json.loads(row.material_evaluation_json)['materials']['substrate']['parameters']['strengths'][0][0]
        assert actual==sample[0] and actual<0


def test_material_pole_goal_against_independent_stripline_formula():
    from test_sipi_references import stripline_z0
    f=1e8;p=dict(width=.5e-3,plane_spacing=1e-3,eps_r=1)
    material=TensorDebyeDielectric([2,2],[[3,3]],[f],[-.5],.3)
    target=stripline_z0(p['width'],p['plane_spacing'],3.5)
    doc=ImpedanceDesignDocument('stripline',p,variable='pole',bounds=[f/2,2*f],
        target=target,tolerance=.1,max_evaluations=30,
        mesh=dict(edge_size=1e-6,far_size=.125e-3,grade=.1),frequency=f,
        materials={'dielectric':material},material_variables={'pole':dict(region='dielectric',path=['relaxation_hz',0])})
    assert doc.dumps()==ImpedanceDesignDocument.loads(doc.dumps()).dumps()==normalize_saved(doc.dumps())
    assert doc.to_dict()['schema']=='sipi.impedance-design/3'
    result=doc.solve()
    assert result.parameter==pytest.approx(f,rel=.015)
    assert abs(result.residual)<=.1 and abs(result.refined_residual)<=.1
    chosen=json.loads(result.material_evaluation_json)['materials']['dielectric']
    assert chosen['parameters']['relaxation_hz']==[result.parameter]
    original=doc.to_dict()['material_evaluation']['materials']['dielectric']
    assert original['parameters']['relaxation_hz']==[f]
    print('tensor Debye Cohn pole goal',result.parameter,f,result.residual,result.refined_residual)
