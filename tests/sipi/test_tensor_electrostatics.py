# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Reciprocal transverse tensors: analytic fields, convergence and independent FEM."""
import importlib.metadata as metadata
import numpy as np
import pytest
from scipy.constants import epsilon_0,mu_0
from galerkin import Mesh
from galerkin.mesh import rectangle_mesh,annulus_mesh
from crosscheck import Stopwatch,emit,make_record,observable,require_tool
from sipi import capacitance_matrix,line_parameters,coupled_microstrip


def rotation(angle):
    return np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])


def plates():
    mesh=rectangle_mesh(.01,.002,16,8)
    return mesh,{'top':mesh.boundary['top']},mesh.boundary['bottom']


@pytest.mark.parametrize('varying',[False,True])
@pytest.mark.parametrize('loss',[0.,.03])
def test_isotropic_tensor_reproduces_legacy_coefficients_and_line_parameters(varying,loss):
    mesh,signals,ground=plates()
    eps=np.where(mesh.nodes[mesh.triangles].mean(axis=1)[:,1]<.001,3.,5.) if varying else 4.
    tensor=np.asarray(eps)[...,None,None]*np.eye(2)
    scalar=capacitance_matrix(mesh,eps*(1-1j*loss),signals,ground)
    actual=capacitance_matrix(mesh,tensor*(1-1j*loss),signals,ground)
    np.testing.assert_allclose(actual,scalar,rtol=1e-12,atol=0)
    original=line_parameters(mesh,eps,signals,ground,tan_delta=loss)
    result=line_parameters(mesh,tensor,signals,ground,tan_delta=loss)
    for name in ('C','C0','L','C_loss'):
        np.testing.assert_allclose(getattr(result,name),getattr(original,name),rtol=1e-12,atol=0)


def test_layered_anisotropic_capacitor_has_exact_series_solution_and_vacuum_inductance():
    mesh,signals,ground=plates()
    bottom=mesh.nodes[mesh.triangles].mean(axis=1)[:,1]<.001
    eps=np.where(bottom[:,None,None],np.diag([2.,4.]),np.diag([5.,3.]))
    tangent=np.where(bottom,.03,.1)
    expected=epsilon_0*.01/(.001/(4*(1-.03j))+.001/(3*(1-.1j)))
    actual=capacitance_matrix(mesh,eps*(1-1j*tangent)[:,None,None],signals,ground)[0,0]
    assert actual==pytest.approx(expected,rel=1e-9)
    result=line_parameters(mesh,eps,signals,ground,tan_delta=tangent)
    assert result.C[0,0]==pytest.approx(expected.real,rel=1e-9)
    assert result.C_loss[0,0]==pytest.approx(-expected.imag,rel=1e-9)
    assert result.C0[0,0]==pytest.approx(epsilon_0*.01/.002,rel=1e-9)
    assert result.L[0,0]==pytest.approx(mu_0*.002/.01,rel=1e-9)
    # Local scalar tangents also broadcast with a global non-isotropic tensor.
    global_result=line_parameters(mesh,np.diag([2.,4.]),signals,ground,tan_delta=tangent)
    global_exact=epsilon_0*.01/(.001/(4*(1-.03j))+.001/(4*(1-.1j)))
    assert global_result.C[0,0]-1j*global_result.C_loss[0,0]==pytest.approx(global_exact,rel=1e-9)


@pytest.mark.parametrize('angle',[0.,.4])
def test_transformed_elliptic_coax_converges_to_exact_tensor_field(angle):
    q=rotation(angle);tensor=q@np.diag([2.,5.])@q.T
    root=q@np.diag(np.sqrt([2.,5.]))@q.T
    exact=2*np.pi*epsilon_0*np.sqrt(np.linalg.det(tensor))*(1-.03j)/np.log(3)
    errors=[]
    for nr,nt in ((16,64),(32,128),(64,256)):
        base=annulus_mesh(.5e-3,1.5e-3,nr,nt)
        mesh=Mesh(base.nodes@root.T,base.triangles.copy(),base.boundary)
        actual=capacitance_matrix(mesh,tensor*(1-.03j),{'inner':mesh.boundary['inner']},mesh.boundary['outer'])[0,0]
        errors.append(abs(actual/exact-1))
    assert errors[2]<errors[1]<errors[0]
    assert errors[-1]<.001 and np.log2(errors[-2]/errors[-1])>=1.5
    print('elliptic tensor coax',angle,errors)


def test_rigid_rotation_and_uniform_geometric_scaling_preserve_capacitance():
    base=annulus_mesh(.5e-3,1.5e-3,24,96)
    tensor=np.array([[3.,.7],[.7,4.]])-1j*np.array([[.05,-.02],[-.02,.03]])
    signals={'inner':base.boundary['inner']};ground=base.boundary['outer']
    original=capacitance_matrix(base,tensor,signals,ground)
    q=rotation(.71)
    mesh=Mesh(7*base.nodes@q.T,base.triangles.copy(),base.boundary)
    actual=capacitance_matrix(mesh,q@tensor@q.T,signals,ground)
    np.testing.assert_allclose(actual,original,rtol=1e-12,atol=0)


def test_open_coupled_section_complex_tensor_against_independent_fem_and_convergence():
    skfem=require_tool('scikit-fem')
    from skfem.helpers import grad
    parameters=dict(width=.5e-3,gap=.3e-3,substrate_height=.5e-3,eps_r=4,
                    thickness=35e-6,air_height=4e-3,box_width=8e-3)
    tensor=np.array([[3.5,.7],[.7,4.5]])-1j*np.array([[.05,-.02],[-.02,.03]])
    assert np.any(tensor.imag>0)  # Off-diagonal signs alone do not determine passivity.
    coarse=dict(edge_size=4e-6,far_size=.25e-3,grade=.2)
    fine=dict(edge_size=1e-6,far_size=.125e-3,grade=.1)
    values=[];clock=Stopwatch()
    for label,params,options in [('coarse',parameters,coarse),('fine',parameters,fine),
        ('outer',dict(parameters,air_height=8e-3,box_width=16e-3),fine)]:
        section=coupled_microstrip(**params).mesh(**options);mesh=section.mesh
        eps=np.where((section.eps_r==4)[:,None,None],tensor,np.eye(2))
        with clock('openphysics'):
            actual=capacitance_matrix(mesh,eps,section.signals,section.ground)
        values.append(actual)
        assert np.linalg.eigvalsh(actual.real).min()>0
        assert np.linalg.eigvalsh(-actual.imag).min()>0
        np.testing.assert_allclose(actual,actual.T,rtol=1e-12,atol=0)
        if label=='coarse':
            with clock('reference'):
                basis=skfem.Basis(skfem.MeshTri(mesh.nodes.T,mesh.triangles.T),skfem.ElementTriP1())
                @skfem.BilinearForm(dtype=complex)
                def form(u,v,w):return np.einsum('ij...,j...,i...->...',w.eps,grad(u),grad(v))
                k=skfem.asm(form,basis,eps=eps.transpose(1,2,0)[:,:,:,None])
                fixed=np.unique(np.concatenate([section.ground,*section.signals.values()]));fields=[]
                for nodes in section.signals.values():
                    v=np.zeros(basis.N,complex);v[nodes]=1
                    fields.append(skfem.solve(*skfem.condense(k,np.zeros(basis.N,complex),x=v,D=fixed)))
                u=np.array(fields).T;expected=epsilon_0*(u.T@(k@u))
            error=float(abs(actual/expected-1).max())
    record=make_record(case='transverse-tensor-coupled-line',physics='reciprocal anisotropic electrostatics',
        api='sipi.capacitance_matrix',discretization='shared P1 tensor stiffness and energy matrix',
        tool='scikit-fem',tool_discretization='independent complex anisotropic P1 assembly and energy',
        matched=['same geometry, mesh, reciprocal positive-real/positive-loss material tensors and boundaries'],
        not_matched=['same-mesh agreement is not convergence or measured-material evidence'],
        observables=[observable('complex C','F/m','max relative difference',error,1e-9)],
        analytical_acceptance='layered capacitor and transformed elliptic coax; separate mesh/outer checks',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    assert error<1e-9
    mesh_error=float(abs(values[0]/values[1]-1).max())
    outer_error=float(abs(values[2]/values[1]-1).max())
    assert mesh_error<.01 and outer_error<.01
    print('tensor coupled C mesh/outer',mesh_error,outer_error)


@pytest.mark.parametrize('eps',[
    np.eye(3),np.ones((2,2,2)),np.ones((1,2,2)),np.ones((2,2,2,2)),
    [[True,False],[False,True]],[[4,False],[False,3]],
    [['4','0'],['0','3']],[[np.inf,0],[0,3]],[[4,np.nan],[np.nan,3]],
    [[0,0],[0,3]],[[1,2],[2,1]],[[4,.2],[.3,3]],
    np.eye(2)*(4+.01j),np.array([[4,.1j],[.1j,3]])])
def test_invalid_tensor_shape_reciprocity_positivity_or_passivity_is_rejected(eps):
    mesh,signals,ground=plates()
    with pytest.raises(ValueError):capacitance_matrix(mesh,eps,signals,ground)


@pytest.mark.parametrize('tangent',[True,[True,0.],-1.,np.nan,1j,[[.1,0],[0,.2]],np.ones((256,1)),[.1]])
def test_tensor_line_rejects_directional_or_invalid_tangent(tangent):
    mesh,signals,ground=plates()
    with pytest.raises(ValueError):line_parameters(mesh,np.diag([3.,4.]),signals,ground,tan_delta=tangent)


@pytest.mark.parametrize('field',['permittivity','tangent'])
def test_mixed_booleans_do_not_become_numeric_line_materials(field):
    mesh,signals,ground=plates()
    eps=[[4,False],[False,3]] if field=='permittivity' else np.diag([3.,4.])
    tangent=([True]+[.03]*(mesh.num_triangles-1)) if field=='tangent' else .03
    with pytest.raises(ValueError):line_parameters(mesh,eps,signals,ground,tan_delta=tangent)


def test_complex_tensor_is_explicit_capacitance_input_not_implicit_line_loss():
    mesh,signals,ground=plates();eps=np.eye(2)*(4-.03j)
    with pytest.raises(ValueError,match='real tensor'):
        line_parameters(mesh,eps,signals,ground)
    original=eps.copy();capacitance_matrix(mesh,eps,signals,ground)
    np.testing.assert_array_equal(eps,original)


@pytest.mark.parametrize('difference,accepted',[(1e-13,True),(1e-9,False)])
def test_only_roundoff_asymmetry_is_accepted(difference,accepted):
    mesh,signals,ground=plates();eps=np.array([[4.,.2+difference],[.2,3.]])
    if accepted:
        actual=capacitance_matrix(mesh,eps,signals,ground)
        expected=capacitance_matrix(mesh,(eps+eps.T)/2,signals,ground)
        np.testing.assert_allclose(actual,expected,rtol=1e-12,atol=0)
    else:
        with pytest.raises(ValueError,match='symmetric'):
            capacitance_matrix(mesh,eps,signals,ground)
