# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Bounded 3D capacitance: analytical fields, independent FEM and input gates."""
import numpy as np
import pytest
from importlib import metadata
from galerkin.mesh3d import box_mesh, Mesh3D
from sipi.capacitance3d import extract_capacitance_3d
from sipi.constants import epsilon_0
from crosscheck import require_tool, Stopwatch, emit, make_record, observable


def plates(n=4):
    mesh=box_mesh(.004,.003,.002,n,n,n)
    return mesh,dict(conductors={'top':mesh.boundary['z1']},ground=mesh.boundary['z0'])


@pytest.mark.parametrize('layered',[False,True])
@pytest.mark.parametrize('n',[2,4,8])
def test_plate_and_layered_series_have_exact_affine_fields(layered,n):
    mesh,kw=plates(n)
    eps=np.where(mesh.nodes[mesh.tets].mean(axis=1)[:,2]<.001,2.,6.) if layered else 3.8
    exact=epsilon_0*.004*.003/(.001/2+.001/6) if layered else epsilon_0*3.8*.004*.003/.002
    result=extract_capacitance_3d(mesh,eps_r=eps,**kw)
    assert result.C[0,0]==pytest.approx(exact,rel=1e-11)
    z=mesh.nodes[:,2]
    phi=np.where(z<=.001,.75*z/.001,.75+.25*(z-.001)/.001) if layered else z/.002
    np.testing.assert_allclose(result.potentials[:,0],phi,rtol=0,atol=1e-11)
    assert result.ground_charge[0]==pytest.approx(-exact,rel=1e-11)
    assert result.num_tets==len(mesh.tets)


@pytest.mark.parametrize('layered', [False, True])
def test_extruded_curved_coax_converges_to_bounded_analytical_solution(layered):
    from galerkin.mesh import annulus_mesh
    from meshine.mesh import TriMesh
    from meshine.extrude import extrude
    a, b, length = .14e-3, .4e-3, 1e-3
    exact = 2*np.pi*epsilon_0*(4. if layered else 3.8)*length/np.log(b/a)
    values = []
    for nr, nt, nz in [(4, 32, 2), (8, 64, 2), (16, 128, 2), (8, 64, 1), (8, 64, 4)]:
        base = annulus_mesh(a, b, nr, nt)
        footprint = TriMesh(base.nodes, base.triangles, np.zeros(len(base.triangles), dtype=int),
                            ['dielectric'], base.boundary_edges)
        levels = [0, length/2, length] if layered else [0, length]
        raw = extrude(footprint, levels, divisions=nz)
        mesh = Mesh3D(raw.nodes, raw.tetrahedra)
        eps = np.where(mesh.nodes[mesh.tets].mean(axis=1)[:, 2] < length/2, 2., 6.) if layered else 3.8
        result = extract_capacitance_3d(mesh, eps_r=eps,
            conductors={'inner': raw.boundary_nodes['inner']}, ground=raw.boundary_nodes['outer'])
        values.append(result.C[0, 0])
        assert result.energy_charge_relative < 1e-10
        assert result.charge_balance_relative < 1e-10
    errors = np.abs(np.array(values[:3])/exact-1)
    assert errors[0] > errors[1] > errors[2]
    assert errors[2] < .005
    axial = np.array([values[3], values[1], values[4]])
    assert np.ptp(axial)/np.max(axial) < 1e-4
    # The physical outer cylinder is ground and both end caps are insulating.
    # Changing polygonization is not a nested-space variational monotonicity test.


def electrodes(n=8):
    mesh=box_mesh(.004,.004,.002,n,n,n)
    x,y,z=mesh.nodes.T
    a=np.flatnonzero((x>=.0005-1e-15)&(x<=.0015+1e-15)&(y>=.001-1e-15)&(y<=.003+1e-15)&np.isclose(z,.001))
    b=np.flatnonzero((x>=.0025-1e-15)&(x<=.0035+1e-15)&(y>=.001-1e-15)&(y<=.003+1e-15)&np.isclose(z,.001))
    ground=np.unique(np.concatenate(list(mesh.boundary.values())))
    return mesh,{'left':a,'right':b},ground


def test_internal_electrodes_match_independent_fem_and_energy_charge_routes():
    skfem=require_tool('scikit-fem')
    from skfem.helpers import dot,grad
    mesh,signals,ground=electrodes()
    eps=np.where(mesh.nodes[mesh.tets].mean(axis=1)[:,2]<.001,2.,6.)
    clock=Stopwatch()
    with clock('openphysics'):
        result=extract_capacitance_3d(mesh,eps_r=eps,conductors=signals,ground=ground)
    with clock('reference'):
        basis=skfem.Basis(skfem.MeshTet(mesh.nodes.T,mesh.tets.T),skfem.ElementTetP1())
        @skfem.BilinearForm
        def form(u,v,w): return w.eps*dot(grad(u),grad(v))
        k=skfem.asm(form,basis,eps=epsilon_0*eps[:,None])
        fixed=np.concatenate([ground,*signals.values()]);fields=[]
        for nodes in signals.values():
            values=np.zeros(basis.N);values[nodes]=1
            fields.append(skfem.solve(*skfem.condense(k,np.zeros(basis.N),x=values,D=fixed)))
        u=np.array(fields).T
    expected=u.T@k@u
    record=make_record(case='bounded_capacitance3d_two_electrodes',physics='bounded 3D static electrostatics',
        api='sipi.capacitance3d.extract_capacitance_3d',discretization='tetrahedral P1 reaction charge matrix',
        tool='scikit-fem',tool_discretization='independent tetrahedral P1 assembly, solve and energy',
        matched=['same conforming tetrahedra, nodal PEC/ground sets and piecewise real permittivity',
                 'finite grounded enclosure; same CODATA 2022 permittivity'],
        not_matched=['mesh accuracy and exterior-boundary convergence',
                     'full-wave ports, radiation, losses, via geometry and frequency response'],
        observables=[observable('C','F','max entrywise relative difference',np.max(abs(result.C/expected-1)),1e-10),
                     observable('potential','V','maximum absolute difference',np.max(abs(result.potentials-u)),1e-10)],
        analytical_acceptance='separate affine uniform/layered plates at 1e-11; geometry/material scaling and fixed-domain refinement trend',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'))
    emit(record)
    np.testing.assert_allclose(result.potentials,u,rtol=0,atol=1e-10)
    np.testing.assert_allclose(result.C,u.T@k@u,rtol=1e-10,atol=0)
    np.testing.assert_allclose(result.C,result.energy_C,rtol=1e-11,atol=0)
    assert result.C[0,1]<0 and np.linalg.eigvalsh(result.C).min()>0
    for name in ('free_residual_relative','charge_balance_relative','energy_charge_relative','symmetry_relative'):
        assert getattr(result,name)<1e-11


def test_geometry_material_scaling_and_conductor_order_preserve_contract():
    mesh,signals,ground=electrodes()
    base=extract_capacitance_3d(mesh,eps_r=3.8,conductors=signals,ground=ground)
    scaled=Mesh3D(mesh.nodes*7,mesh.tets.copy())
    got=extract_capacitance_3d(scaled,eps_r=3.8*2,conductors=dict(reversed(list(signals.items()))),ground=ground)
    assert got.names==('right','left')
    np.testing.assert_allclose(got.C,14*base.C[::-1,::-1],rtol=1e-11,atol=0)
    np.testing.assert_allclose(got.potentials,base.potentials[:,::-1],rtol=0,atol=1e-11)
    before=base.C.copy();mesh.nodes[:]=0
    np.testing.assert_array_equal(base.C,before)
    for array in (base.C,base.energy_C,base.potentials,base.ground_charge):assert not array.flags.writeable


def test_fixed_bounded_electrode_geometry_mesh_refines_without_plate_model():
    matrices=[]
    for n in (8,16,24):
        mesh,signals,ground=electrodes(n)
        matrices.append(extract_capacitance_3d(mesh,eps_r=3.8,conductors=signals,ground=ground).C)
    changes=[np.linalg.norm(b-a)/np.linalg.norm(b) for a,b in zip(matrices,matrices[1:])]
    assert changes[1]<changes[0]
    # A convergence trend, not a declared physical error bar for an open via.
    assert all(np.linalg.eigvalsh(c).min()>0 for c in matrices)


@pytest.mark.parametrize('eps',[True,0.,-1.,np.nan,np.inf,1+0j,[1.,2.],np.eye(3)])
def test_invalid_permittivity_is_rejected(eps):
    mesh,kw=plates(2)
    with pytest.raises(ValueError,match='eps_r'):extract_capacitance_3d(mesh,eps_r=eps,**kw)


@pytest.mark.parametrize('nodes',[[],[True],[0.5],[-1],[999],[0,0]])
def test_invalid_conductor_indices_are_rejected(nodes):
    mesh,kw=plates(2);kw['conductors']={'bad':nodes}
    with pytest.raises(ValueError):extract_capacitance_3d(mesh,**kw)


def test_overlap_empty_names_and_ungrounded_components_are_rejected():
    mesh,kw=plates(2)
    for signals in ({},{'':mesh.boundary['z1']},{'s':mesh.boundary['z0']}):
        with pytest.raises(ValueError):extract_capacitance_3d(mesh,conductors=signals,ground=kw['ground'])
    count=mesh.num_nodes
    disconnected=Mesh3D(np.concatenate([mesh.nodes,mesh.nodes+[.01,0,0]]),np.concatenate([mesh.tets,mesh.tets+count]))
    with pytest.raises(ValueError,match='component'):extract_capacitance_3d(disconnected,**kw)


def test_invalid_tetrahedra_and_unused_nodes_are_rejected():
    mesh,kw=plates(2)
    for bad in (Mesh3D(np.vstack([mesh.nodes,[9,9,9]]),mesh.tets.copy()),
                Mesh3D(mesh.nodes,np.vstack([mesh.tets,mesh.tets[:1]]))):
        with pytest.raises(ValueError):extract_capacitance_3d(bad,**kw)
    mesh.nodes[:,2]=0
    with pytest.raises(ValueError,match='volume'):extract_capacitance_3d(mesh,**kw)


def test_low_precision_relative_material_does_not_underflow_si_permittivity():
    mesh,kw=plates(2)
    got=extract_capacitance_3d(mesh,eps_r=np.ones(len(mesh.tets),dtype=np.float16),**kw)
    assert got.C[0,0]==pytest.approx(epsilon_0*.004*.003/.002,rel=1e-11)
