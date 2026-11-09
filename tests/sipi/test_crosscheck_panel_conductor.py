# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent quadratic volume field with explicit grounded guard, report-only."""
from importlib import metadata
import numpy as np
import pytest
from scipy.sparse.linalg import splu
from meshine import Domain, rectangle, generate
from crosscheck import Stopwatch, emit, make_record, observable, relative_difference, require_tool
from sipi.panel_conductor import panel_surface_current_factors
from test_panel_conductor import circles
from sipi.constants import epsilon_0

@pytest.mark.parametrize('size',[.08,.04,.02])
def test_grounded_guard_against_quadratic_volume_reference(size):
    sk=require_tool('scikit-fem')
    from skfem.helpers import dot,grad
    section=circles();polygons=[t.corners()+[2,0] for t in section.traces]
    domain=Domain(size=size);domain.add_region('vacuum',rectangle(0,0,4,2),holes=polygons)
    mesh=generate(domain,smooth=0,candidate_order='stable');clock=Stopwatch()
    with clock('openphysics'):
        ours=panel_surface_current_factors(section,panels_per_edge=8,interpolation_degree=12)
    with clock('reference'):
        m=sk.MeshTri(mesh.nodes.T.copy(),mesh.triangles.T.copy());element=sk.ElementTriP2();basis=sk.Basis(m,element)
        facets=m.boundary_facets();mid=m.p[:,m.facets[:,facets]].mean(axis=1).T
        boundaries=[facets[np.linalg.norm(mid-center,axis=1)<radius*1.1] for center,radius in [(np.array([1.6,.5]),.08),(np.array([2.4,.5]),.1),(np.array([2.,.5]),.1)]]
        boundaries[-1]=np.concatenate((boundaries[-1],facets[mid[:,1]==0]))
        groups=[basis.get_dofs(facets=f).all() for f in boundaries]
        fixed=np.unique(np.concatenate(groups));assert sum(map(len,groups))==len(fixed)
        @sk.BilinearForm
        def stiffness(u,v,w):return dot(grad(u),grad(v))
        @sk.BilinearForm
        def mass(u,v,w):return u*v
        K=stiffness.assemble(basis).tocsc();V=np.zeros((basis.N,2))
        for i in range(2):V[groups[i],i]=1.
        free=np.setdiff1d(np.arange(basis.N),fixed)
        factor=splu(K[free][:,free].tocsc());V[free]=factor.solve(-(K[free][:,fixed]@V[fixed]));del factor
        C0=epsilon_0*(V.T@(K@V));J=epsilon_0*(K@V)@np.linalg.inv(C0)
        parts=[];integrals=[]
        for boundary,nodes in zip(boundaries,groups):
            fb=sk.FacetBasis(m,element,facets=boundary,intorder=4)
            M=mass.assemble(fb)[nodes][:,nodes];weights=np.asarray(M.sum(axis=1)).ravel()
            assert np.all(weights>0)
            parts.append(J[nodes].T@(J[nodes]/weights[:,None]));integrals.append(J[nodes].sum(axis=0))
        np.testing.assert_allclose(integrals,[[1,0],[0,1],[-1,-1]],rtol=0,atol=1e-10)
    observations=[observable('C0','F/m','relative difference',relative_difference(ours.C0,C0))]
    observations += [observable(label,'1/m','relative difference',relative_difference(ours.parts[i],part)) for i,(label,part) in enumerate(zip(['left Q','right Q','reference Q'],parts))]
    record=make_record(case=f'panel-guard-volume-{size}',physics='PEC vacuum current dual with zero-voltage guard',api='sipi.panel_conductor',discretization='constant Galerkin boundary panels; capacitance current reduction',tool='scikit-fem',tool_discretization='independent ElementTriP2 voltage field and lumped boundary mass',matched=['same three 64-vertex polygons and rectangle','guard and bottom at zero voltage; side/top zero normal derivative','two signal voltage bases and current normalization'],not_matched=['different boundary/volume discretizations; differences report-only, not monotonic accuracy proof'],observables=observations,stopwatch=clock,analytical_acceptance='current conservation, scaling, permutation and separate qualified panel sequence')
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
