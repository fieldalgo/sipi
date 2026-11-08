# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Exact uniform-scalar reuse against direct and independent complex fields."""
import importlib.metadata as metadata
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.constants import epsilon_0, mu_0
from galerkin import Mesh
from galerkin.mesh import rectangle_mesh
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi.templates import stripline, coupled_stripline, coupled_layered_stripline
from sipi.dielectric import DebyeDielectric, _dispersive_from_mesh
from sipi.quasistatic import capacitance_matrix
import sipi.dielectric as module

F=np.array([0.,1e8,1e9,1e10,1e12])
MODEL=DebyeDielectric(2.,[4.],[1e9])
MESH=dict(edge_size=1e-6,far_size=.125e-3,grade=.1)


def section(kind,box=8e-3):
    if kind=='scalar':
        return stripline(width=.5e-3,plane_spacing=1e-3,eps_r=1.,box_width=box)
    if kind=='pair':
        return coupled_stripline(width=.5e-3,gap=.1e-3,plane_spacing=1e-3,eps_r=1.,box_width=box)
    return coupled_layered_stripline(width=.5e-3,gap=.1e-3,lower_height=.5e-3,
        upper_height=.5e-3,lower_eps_r=1.,upper_eps_r=1.,box_width=box)


@pytest.fixture(scope='module',params=['scalar','pair','layered'])
def uniform_mesh(request):
    return request.param,section(request.param).mesh(**MESH)


def samples_for(meshed):
    return {name:MODEL.permittivity(F) for name in meshed.mesh.region_names}


@pytest.mark.parametrize('provided',[False,True])
def test_uniform_matches_direct_complex_fields_and_reuses_vacuum(uniform_mesh,provided,monkeypatch):
    kind,m=uniform_mesh;sample=samples_for(m)
    c0=capacitance_matrix(m.mesh,1.,m.signals,m.ground);original=c0.copy();calls=[]
    def counted(*args,**kwargs):
        calls.append(np.array(args[1],copy=True));return capacitance_matrix(*args,**kwargs)
    monkeypatch.setattr(module,'capacitance_matrix',counted)
    result=_dispersive_from_mesh(m,F,sample,c0=c0 if provided else None)
    assert len(calls)==(0 if provided else 1)
    for i,eps in enumerate(MODEL.permittivity(F)):
        direct=capacitance_matrix(m.mesh,eps,m.signals,m.ground)
        np.testing.assert_allclose(result.C_complex[i],direct,rtol=1e-10,atol=0)
    np.testing.assert_array_equal(c0,original)
    np.testing.assert_allclose(result.L,mu_0*epsilon_0*np.linalg.inv(c0),rtol=1e-12,atol=0)
    np.testing.assert_allclose(result.G,-2*np.pi*F[:,None,None]*result.C_complex.imag,rtol=1e-12,atol=0)
    assert result.names==tuple(m.signals) and not result.C_complex.flags.writeable
    for value in sample.values():value[:]=9
    for value in result.layer_permittivity.values():
        np.testing.assert_array_equal(value,MODEL.permittivity(F))
    print('uniform extraction',kind,'provided C0',provided,'matrix calls',len(calls))


def plate():
    base=rectangle_mesh(.01,.002,16,8)
    regions=(base.nodes[base.triangles].mean(axis=1)[:,1]>=.001).astype(int)
    mesh=Mesh(base.nodes,base.triangles,base.boundary,regions=regions,region_names=['lower','upper'])
    return SimpleNamespace(mesh=mesh,signals={'top':mesh.boundary['top']},ground=mesh.boundary['bottom'])


@pytest.mark.parametrize('case',['near','frequency-change','tensor','isotropic-tensor','unused-region'])
def test_actual_element_equality_and_general_paths_keep_complex_plate_solution(case,monkeypatch):
    m=plate();a=MODEL.permittivity(F);b=a.copy()
    if case=='near':b+=1e-12
    if case=='frequency-change':b[1:]+=1
    samples=dict(lower=a,upper=b)
    if case in ('tensor','isotropic-tensor'):
        samples['lower']=a[:,None,None]*np.eye(2)
        if case=='tensor':samples['lower'][:,0,0]*=2
    if case=='unused-region':samples['unused']=np.full(len(F),8.-1j)
    calls=[]
    def counted(*args,**kwargs):
        calls.append(np.array(args[1],copy=True));return capacitance_matrix(*args,**kwargs)
    monkeypatch.setattr(module,'capacitance_matrix',counted)
    result=_dispersive_from_mesh(m,F,samples)
    expected_calls={'near':6,'frequency-change':5,'tensor':6,'isotropic-tensor':6,'unused-region':1}
    assert len(calls)==expected_calls[case]
    exact=epsilon_0*.01/(.001/a+.001/b)
    np.testing.assert_allclose(result.C_complex[:,0,0],exact,rtol=1e-10,atol=0)
    # Exact equality is decided per frequency from actual elements, not labels
    # or allclose, and tensor inputs keep their existing extraction semantics.
    for i in range(len(F)):
        values=[samples[m.mesh.region_names[r]][i] for r in m.mesh.regions]
        if case in ('tensor','isotropic-tensor'):
            values=[v*np.eye(2) if np.ndim(v)==0 else v for v in values]
        direct=capacitance_matrix(m.mesh,np.array(values),m.signals,m.ground)
        np.testing.assert_allclose(result.C_complex[i],direct,rtol=1e-10,atol=0)


@pytest.mark.parametrize('eps',[-1.+0j,4.+.01j,complex(np.inf,0),complex(np.nan,0)])
def test_invalid_uniform_samples_still_raise(eps):
    m=plate();samples={name:np.full(len(F),eps) for name in m.mesh.region_names}
    with pytest.raises(ValueError):_dispersive_from_mesh(m,F,samples)


def test_independent_complex_p1_uniform_pair():
    skfem=require_tool('scikit-fem');clock=Stopwatch()
    from skfem.helpers import dot,grad
    m=section('pair').mesh(**MESH);mesh=m.mesh
    with clock('openphysics'):
        result=_dispersive_from_mesh(m,F,samples_for(m))
    basis=skfem.Basis(skfem.MeshTri(mesh.nodes.T,mesh.triangles.T),skfem.ElementTriP1())
    @skfem.BilinearForm(dtype=complex)
    def form(u,v,w):return w.eps*dot(grad(u),grad(v))
    fixed=np.unique(np.concatenate([m.ground,*m.signals.values()]));errors=[]
    for i,eps in enumerate(MODEL.permittivity(F)):
        with clock('reference'):
            k=skfem.asm(form,basis,eps=eps);fields=[]
            for nodes in m.signals.values():
                v=np.zeros(basis.N,complex);v[nodes]=1
                fields.append(skfem.solve(*skfem.condense(k,np.zeros(basis.N,complex),x=v,D=fixed)))
            v=np.array(fields).T;reference=epsilon_0*(v.T@(k@v))
        errors.append(float(np.max(abs((result.C_complex[i]-reference)/reference))))
    record=make_record(case='sipi-uniform-scalar-reuse',physics='uniform complex electrostatics',
        api='sipi.dielectric.dispersive_line',discretization='vacuum P1 energy with exact scalar scaling',
        tool='scikit-fem',tool_discretization='independent complex P1 assembly and Dirichlet energy',
        matched=['same mesh, conductors, reference and scalar Debye coefficients at five frequencies'],
        not_matched=['independent mesh generation; convergence checked separately'],
        observables=[observable('complex capacitance','F/m','max component relative error',max(errors),1e-10)],
        analytical_acceptance='complex plate identity and separate thin Cohn mesh/domain gates',stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    print('uniform independent component relative errors',errors)
    assert max(errors)<=1e-10


def test_thin_pair_requested_refined_and_outer_domain_cohn():
    from test_sipi_references import coupled_stripline_z
    expected=np.array([[2*z[1],z[0]/2] for z in
        [coupled_stripline_z(.5e-3,.1e-3,1e-3,e.real) for e in MODEL.permittivity(F)]])
    observations=[]
    for box,mesh in [(8e-3,MESH),(8e-3,{k:v/2 for k,v in MESH.items()}),(16e-3,MESH)]:
        m=section('pair',box).mesh(**mesh);result=_dispersive_from_mesh(m,F,samples_for(m))
        c=result.C;l=result.L
        values=np.array([[2*np.sqrt((l[0,0]-l[0,1])/(row[0,0]-row[0,1])),
            .5*np.sqrt((l[0,0]+l[0,1])/(row[0,0]+row[0,1]))] for row in c])
        errors=values-expected;observations.append(errors.tolist())
        assert np.max(abs(errors))<=.5
    print('uniform Cohn requested/refined/outer residuals ohm',observations)
