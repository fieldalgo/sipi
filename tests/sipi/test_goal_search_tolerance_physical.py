# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Finite buried grounds: a tighter search threshold with independent field energy."""
from importlib import metadata
import numpy as np
import sipi
from sipi.constants import epsilon_0,mu_0
from crosscheck import require_tool,Stopwatch,make_record,observable,emit


def test_buried_pair_search_margin_reference_and_outer_domain():
    skfem=require_tool('scikit-fem')
    from skfem.helpers import dot,grad
    p=dict(width=.0003,gap=.0003,ground_gap=.0003,ground_width=.0008,
        plane_spacing=.001,trace_height=.0004,eps_r=4.,thickness=.000035,
        tan_delta=.02,box_width=.006)
    factory=lambda width:sipi.coupled_coplanar_stripline(**{**p,'width':width})
    mesh=factory(p['width']).mesh_settings();mesh['edge_size']/=2;mesh['far_size']/=4
    clock=Stopwatch()
    with clock('openphysics'):
        result,line=sipi.seek_impedance(factory,[.00015,.00065],100.,quantity='z_diff',
            tolerance=.5,search_tolerance=.25,mesh=mesh,max_evaluations=32,return_line=True)
    assert abs(result.residual)<=.25 and abs(result.refined_residual)<=.5
    assert .00015<=result.parameter<=.00065 and len(result.history)<=32
    assert result.history[-1].stage=='refinement'
    assert all(t.y==p['trace_height'] for t in result.document.section.traces)
    m=result.document.section.mesh(**mesh)
    with clock('reference'):
        basis=skfem.Basis(skfem.MeshTri(m.mesh.nodes.T,m.mesh.triangles.T),skfem.ElementTriP1())
        @skfem.BilinearForm(dtype=complex)
        def form(u,v,w):return w.eps*dot(grad(u),grad(v))
        fixed=np.unique(np.concatenate([m.ground,*m.signals.values()]));expected=[]
        for eps in (m.eps_r*(1-1j*m.tan_delta),np.ones_like(m.eps_r)):
            k=skfem.asm(form,basis,eps=eps[:,None]);solutions=[]
            for nodes in m.signals.values():
                v=np.zeros(basis.N,complex);v[nodes]=1
                solutions.append(skfem.solve(*skfem.condense(k,np.zeros(basis.N,complex),x=v,D=fixed)))
            u=np.array(solutions).T;expected.append(epsilon_0*(u.T@(k@u)))
    c,c0=expected[0].real,expected[1].real
    reference_l=epsilon_0*mu_0*np.linalg.inv(c0);odd=np.array([1.,-1.])/np.sqrt(2)
    reference_z=2*np.sqrt((odd@reference_l@odd)/(odd@c@odd))
    errors=[float(np.max(abs(a-b))/np.max(abs(b))) for a,b in
        [(line.C,c),(line.C0,c0),(line.C_loss,-expected[0].imag),(line.L,reference_l)]]
    assert max(errors)<1e-10 and abs(reference_z-result.impedance)/reference_z<1e-10
    assert abs(reference_z-100)<=.25
    outer=sipi.coupled_coplanar_stripline(**{**p,'width':result.parameter,'box_width':.012}).analyze(**mesh)
    outer_change=abs(outer.even_odd()['z_diff']/result.impedance-1)
    assert outer_change<.005
    record=make_record(case='buried-pair-goal-search-threshold',physics='lossy homogeneous electrostatics',
        api='sipi.seek_impedance',discretization='P1 bounded width search with tighter requested residual and separate refined acceptance',
        tool='scikit-fem',tool_discretization='independent complex/vacuum P1 assembly and Dirichlet energy',
        matched=['selected geometry, requested mesh, material and ground boundary conditions'],
        not_matched=['no measured manufacturing data or three-dimensional ground transition'],
        observables=[observable(name,unit,'relative difference',error,1e-10) for name,unit,error in
            zip(['C','C0','C_loss','L'],['F/m','F/m','F/m','H/m'],errors)],
        analytical_acceptance='requested residual0.25ohm; refined0.5ohm; separate doubled-box change0.5percent',stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    print('selected width/residual/refined/outer',result.parameter,result.residual,result.refined_residual,outer_change)
