# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Two substrate layers below surface copper: independent fields and limits."""
from dataclasses import replace
from importlib import metadata
import numpy as np
import pytest
from sipi import (layered_microstrip, coupled_layered_microstrip, microstrip,
                  coupled_microstrip, CrossSectionDocument, seek_impedance)
from sipi.constants import epsilon_0
from crosscheck import require_tool, Stopwatch, make_record, observable, emit

PARAMS=dict(width=.5e-3,lower_height=.3e-3,upper_height=.7e-3,
            lower_eps_r=3.,upper_eps_r=5.,thickness=35e-6,
            lower_tan_delta=.01,upper_tan_delta=.03,air_height=.01,box_width=.02)
COARSE=dict(edge_size=5e-6,far_size=.25e-3,grade=.2)
FINE=dict(edge_size=2.5e-6,far_size=.125e-3,grade=.1)

def section(pair=False,**changes):
    p={**PARAMS,**changes}
    return coupled_layered_microstrip(**p,gap=.3e-3) if pair else layered_microstrip(**p)

@pytest.mark.parametrize('pair',[False,True])
@pytest.mark.parametrize('thickness,top',[(0.,None),(35e-6,None),(35e-6,.4e-3)])
def test_explicit_surface_geometry_and_json(pair,thickness,top):
    s=section(pair,thickness=thickness,top_width=top)
    assert [x.name for x in s.layers]==['lower','upper','air']
    assert [(x.eps_r,x.tan_delta) for x in s.layers]==[(3.,.01),(5.,.03),(1.,0.)]
    assert s.top==s.sides=='open' and s.bottom=='ground'
    assert s.height==pytest.approx(.011,rel=1e-15)
    assert all(t.y==.001 and t.y1==.001+thickness for t in s.traces)
    if pair:assert s.traces[1].x0-s.traces[0].x1==pytest.approx(.3e-3,rel=1e-12)
    doc=CrossSectionDocument(s,mesh=COARSE)
    assert CrossSectionDocument.loads(doc.dumps()).dumps()==doc.dumps()
    auto=section(pair,air_height=None,box_width=None)
    assert auto.layers[-1].thickness==pytest.approx(.010035,rel=1e-15)
    assert auto.width==pytest.approx(.02,rel=1e-15)

@pytest.mark.parametrize('pair',[False,True])
@pytest.mark.parametrize('change',[dict(lower_height=0),dict(upper_height=-1),
    dict(lower_height=True),dict(upper_height=float('inf')),dict(lower_eps_r=.5),
    dict(upper_eps_r=True),dict(lower_tan_delta=-.01),dict(upper_tan_delta=float('nan')),
    dict(thickness=-1),dict(air_height=20e-6),dict(box_width=.4e-3),
    dict(thickness=0,top_width=.3e-3),dict(top_width=.03)])
def test_invalid_dimensions_materials_and_clipping(pair,change):
    with pytest.raises(ValueError):section(pair,**change)

@pytest.fixture(scope='module',params=[False,True],ids=['single','pair'])
def fields(request):
    pair=request.param;m=section(pair).mesh(**COARSE)
    return pair,m,m.line_parameters(),section(pair).analyze(**FINE)

def test_independent_complex_and_vacuum_energy(fields):
    pair,m,actual,_=fields;skfem=require_tool('scikit-fem')
    from skfem.helpers import dot,grad
    clock=Stopwatch()
    with clock('openphysics'):actual=m.line_parameters()
    with clock('reference'):
        basis=skfem.Basis(skfem.MeshTri(m.mesh.nodes.T,m.mesh.triangles.T),skfem.ElementTriP1())
        @skfem.BilinearForm(dtype=complex)
        def form(u,v,w):return w.eps*dot(grad(u),grad(v))
        y=m.mesh.nodes[m.mesh.triangles,1].mean(axis=1)
        # Material assignment comes from the specified physical heights, not
        # the engine's per-element material coefficients.
        eps=np.where(y<.3e-3,3*(1-.01j),np.where(y<1e-3,5*(1-.03j),1.))
        fixed=np.unique(np.concatenate([m.ground,*m.signals.values()]));expected=[]
        for coeff in (eps,np.ones_like(eps)):
            k=skfem.asm(form,basis,eps=coeff[:,None]);columns=[]
            for nodes in m.signals.values():
                v=np.zeros(basis.N,complex);v[nodes]=1
                columns.append(skfem.solve(*skfem.condense(k,np.zeros(basis.N,complex),x=v,D=fixed)))
            u=np.array(columns).T;expected.append(epsilon_0*(u.T@(k@u)))
    errors=[float(np.max(abs(a-b))/np.max(abs(b))) for a,b in
        [(actual.C,expected[0].real),(actual.C_loss,-expected[0].imag),(actual.C0,expected[1].real)]]
    record=make_record(case='layered-surface-'+('pair' if pair else 'single'),
        physics='piecewise lossy electrostatics',api='sipi.templates',
        discretization='two substrate layers below surface copper, P1',
        tool='scikit-fem',tool_discretization='independent P1 complex/vacuum energy',
        matched=['same mesh, conductor order and boundary conditions','independently assigned materials from specified heights'],
        not_matched=['no measured-board or independent geometric mesh'],
        observables=[observable(k,'F/m','max normalized matrix difference',v,1e-10) for k,v in zip(('C','C_loss','C0'),errors)],
        analytical_acceptance='vacuum identity, uniform-substrate limit; separate mesh, box and air gates',stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    assert max(errors)<=1e-10

def test_separate_mesh_and_open_boundary_convergence(fields,record_property):
    pair,_,coarse,fine=fields
    def vector(line):return np.array([line.even_odd()['z_diff'],line.even_odd()['z_common']]) if pair else np.array([line.z0])
    changes={}
    for label,other,gate in [('mesh',coarse,.01),('box',section(pair,box_width=.04).analyze(**FINE),.005),
                             ('air',section(pair,air_height=.02).analyze(**FINE),.005)]:
        delta=max(float(np.max(abs(other.C-fine.C))/np.max(abs(fine.C))),float(np.max(abs(vector(other)/vector(fine)-1))))
        changes[label]=delta;assert delta<=gate,(label,delta)
    record_property('relative_changes',str(changes))
    for matrix in (fine.C,fine.C0,fine.C_loss,fine.L):
        np.testing.assert_allclose(matrix,matrix.T,atol=0,rtol=1e-12)
        assert np.linalg.eigvalsh(matrix).min()>0

def test_vacuum_and_uniform_substrate_limits(fields):
    pair,m,_,_=fields
    vacuum=replace(m,eps_r=np.ones_like(m.eps_r),tan_delta=np.zeros_like(m.tan_delta)).line_parameters()
    np.testing.assert_array_equal(vacuum.C,vacuum.C0)
    np.testing.assert_array_equal(vacuum.C_loss,np.zeros_like(vacuum.C))
    layered=section(pair,lower_eps_r=4.,upper_eps_r=4.,lower_tan_delta=.02,upper_tan_delta=.02).analyze(**FINE)
    p=dict(width=.5e-3,substrate_height=.001,eps_r=4.,thickness=35e-6,tan_delta=.02,air_height=.01,box_width=.02)
    single=(coupled_microstrip(**p,gap=.3e-3) if pair else microstrip(**p)).analyze(**FINE)
    for key in ('C','C0','C_loss','L'):
        a,b=getattr(layered,key),getattr(single,key)
        assert np.max(abs(a-b))/np.max(abs(b))<=.005
    a,b=(layered.even_odd()['z_diff'],single.even_odd()['z_diff']) if pair else (layered.z0,single.z0)
    assert abs(a/b-1)<=.005

@pytest.mark.parametrize('pair',[False,True])
def test_direct_width_goal_retains_both_substrate_layers_and_refinement(pair):
    target=100. if pair else 75.
    result=seek_impedance(lambda w:section(pair,width=w),(.2e-3,1.5e-3),target,
                         quantity='z_diff' if pair else 'z0',mesh=COARSE,tolerance=.5)
    assert abs(result.residual)<=.5 and abs(result.refined_residual)<=.5
    assert result.history[-1].stage=='refinement'
    assert [(l.name,l.eps_r,l.thickness) for l in result.document.section.layers[:2]]==[
        ('lower',3.,.3e-3),('upper',5.,.7e-3)]
