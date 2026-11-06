# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Unbacked finite coplanar conductors: free-space and material references."""
import importlib.metadata as metadata
import numpy as np
import pytest
from scipy.constants import epsilon_0,c
from scipy.integrate import quad
from scipy.linalg import solve
from scipy.special import xlogy,ellipk
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import (unbacked_coplanar,coupled_unbacked_coplanar,
                  CrossSectionDocument,ImpedanceDesignDocument)
from sipi.study import ImpedanceStudyDocument

FACTORIES=(unbacked_coplanar,coupled_unbacked_coplanar)
COARSE=dict(edge_size=4e-6,far_size=.25e-3,grade=.2)
FINE=dict(edge_size=1e-6,far_size=.125e-3,grade=.1)
VAC_COARSE=dict(COARSE,far_size=.5e-3)
VAC_FINE=dict(FINE,far_size=.25e-3)


def primitive(u):
    return u-xlogy(u,abs(u))


def free_space_panels(intervals,count):
    """Constant panel charge with a -log Green kernel and total charge zero.

    An extra unknown common potential is essential: the distant boundary is
    not grounded. Cosine edge clustering; no SIPI geometry, mesh or solver.
    """
    intervals=np.asarray(intervals,dtype=float)
    unit=.5*(1-np.cos(np.linspace(0,np.pi,count+1)))
    length=intervals.max()-intervals.min()
    edges=(intervals[:,0,None]+np.diff(intervals,axis=1)*unit)/length
    left,right=edges[:,:-1].ravel(),edges[:,1:].ravel()
    owner=np.repeat(np.arange(len(intervals)),count);mid=(left+right)/2
    matrix=(primitive(right[None,:]-mid[:,None])-primitive(left[None,:]-mid[:,None]))/(right-left)
    n=len(mid)
    augmented=np.ones((n+1,n+1));augmented[-1,-1]=0;augmented[:-1,:-1]=matrix
    rhs=np.zeros((n+1,len(intervals)))
    rhs[:-1]=2*np.pi*epsilon_0*(owner[:,None]==np.arange(len(intervals)))
    charge=solve(augmented,rhs)[:-1]
    return np.array([charge[owner==i].sum(axis=0) for i in range(len(intervals))])


def intervals(factory):
    return ([(-.65,-.15),(.15,.65),(-1.85,-.85),(.85,1.85)]
            if factory is coupled_unbacked_coplanar else
            [(-.25,.25),(-1.45,-.45),(.45,1.45)])


def reference(factory,count=160):
    cap=free_space_panels(intervals(factory),count)
    modal=[cap[0,0]+cap[0,1],cap[0,0]-cap[0,1]] if factory is coupled_unbacked_coplanar else [cap[0,0]]
    return 1/(c*np.array(modal))


def params(factory,physical=False):
    p=dict(width=.5e-3,gap=.2e-3,ground_width=1e-3,substrate_height=.5e-3,
           eps_r=1,air_height=12e-3,lower_air_height=12e-3,box_width=24e-3)
    if factory is coupled_unbacked_coplanar:p.update(gap=.3e-3,ground_gap=.2e-3)
    if physical:p.update(eps_r=4,thickness=35e-6,top_width=.4e-3,tan_delta=.01,
                         air_height=6e-3,lower_air_height=6e-3,box_width=12e-3)
    return p


def modes(line):
    if len(line.names)==1:return np.array([line.z0])
    m=line.even_odd();return np.array([m['z_even'],m['z_odd']])


@pytest.mark.parametrize('lo,hi',[(-.2,.2),(.1,.8),(-2,-.1)])
def test_log_panel_primitive_against_independent_quadrature(lo,hi):
    expected=quad(lambda u:-np.log(abs(u)),lo,hi,points=[0] if lo<0<hi else None,epsabs=1e-12)[0]
    assert primitive(hi)-primitive(lo)==pytest.approx(expected,abs=1e-12)


@pytest.mark.parametrize('factory',FACTORIES)
def test_reference_neutrality_gauge_reciprocity_scale_and_resolution(factory):
    geom=intervals(factory);cap=free_space_panels(geom,160)
    scale=abs(cap).max()
    assert abs(cap-cap.T).max()/scale<1e-4
    assert abs(cap.sum(axis=0)).max()/scale<1e-12
    assert abs(cap.sum(axis=1)).max()/scale<1e-12
    np.testing.assert_allclose(free_space_panels(np.array(geom)*1e-3,160),cap,rtol=1e-10,atol=0)
    np.testing.assert_allclose(reference(factory,80),reference(factory),rtol=.003)
    count=2 if factory is coupled_unbacked_coplanar else 1
    assert np.linalg.eigvalsh(cap[:count,:count]).min()>0


def test_finite_ground_reference_against_elliptic_and_field_integrals():
    # E(z) is proportional to 1/sqrt((z²-a²)(z²-b²)(z²-d²)). Integrate
    # the normal field on the signal and tangential field across its slot;
    # trigonometric substitutions remove endpoint square-root singularities.
    a,b,d=.25,.45,1.45
    charge=quad(lambda t:1/np.sqrt((b*b-a*a*np.sin(t)**2)*(d*d-a*a*np.sin(t)**2)),0,np.pi/2,epsabs=1e-12)[0]
    voltage=quad(lambda t:1/np.sqrt((a*a+(b*b-a*a)*np.sin(t)**2)*(d*d-a*a-(b*b-a*a)*np.sin(t)**2)),0,np.pi/2,epsabs=1e-12)[0]
    k=a/b*np.sqrt((d*d-b*b)/(d*d-a*a))
    exact=ellipk(1-k*k)/ellipk(k*k)/(4*epsilon_0*c)
    assert voltage/(4*epsilon_0*c*charge)==pytest.approx(exact,rel=1e-12)
    assert reference(unbacked_coplanar)[0]==pytest.approx(exact,rel=.001)
    # Separate large-ground normalization; never use this infinite-ground
    # value as the finite-ground FEM reference.
    large=free_space_panels([(-a,a),(-20-b,-b),(b,20+b)],320)
    infinite=ellipk(1-(a/b)**2)/ellipk((a/b)**2)/(4*epsilon_0*c)
    assert 1/(c*large[0,0])==pytest.approx(infinite,rel=.01)


@pytest.mark.parametrize('factory',FACTORIES)
def test_vacuum_mesh_and_domain_against_independent_free_space(factory):
    p=params(factory);expected=reference(factory)
    values=[modes(factory(**p).analyze(**m)) for m in (VAC_COARSE,VAC_FINE)]
    errors=[abs(v/expected-1) for v in values]
    assert np.all(errors[-1]<.02) and np.all(errors[-1]<errors[0])
    wide=dict(p,air_height=24e-3,lower_air_height=24e-3,box_width=48e-3)
    outer=modes(factory(**wide).analyze(**VAC_FINE))
    np.testing.assert_allclose(outer,values[-1],rtol=.01)
    print(factory.__name__,'reference',expected,'FEM',values,'error',errors,'outer',outer)


@pytest.mark.parametrize('factory',FACTORIES)
def test_finite_copper_substrate_convergence_and_independent_complex_energy(factory):
    skfem=require_tool('scikit-fem')
    from skfem.helpers import dot,grad
    p=params(factory,True);section=factory(**p);mesh=section.mesh(**COARSE)
    clock=Stopwatch()
    with clock('reference'):
        basis=skfem.Basis(skfem.MeshTri(mesh.mesh.nodes.T,mesh.mesh.triangles.T),skfem.ElementTriP1())
        @skfem.BilinearForm(dtype=complex)
        def form(u,v,w):return w.eps*dot(grad(u),grad(v))
        k=skfem.asm(form,basis,eps=(mesh.eps_r*(1-1j*mesh.tan_delta))[:,None])
        fixed=np.unique(np.concatenate([mesh.ground,*mesh.signals.values()]))
        fields=[]
        for nodes in mesh.signals.values():
            v=np.zeros(basis.N,dtype=complex);v[nodes]=1
            fields.append(skfem.solve(*skfem.condense(k,np.zeros(basis.N,dtype=complex),x=v,D=fixed)))
        u=np.array(fields).T;expected=epsilon_0*(u.T@(k@u))
    with clock('openphysics'):
        coarse=mesh.line_parameters();actual=coarse.C-1j*coarse.C_loss
    error=float(np.max(abs(actual/expected-1)))
    record=make_record(case=factory.__name__,physics='unbacked coplanar electrostatics',
        api='sipi.'+factory.__name__,discretization='conforming triangular P1 extraction',
        tool='scikit-fem',tool_discretization='independent complex P1 energy assembly',
        matched=['same finite substrate, tapered signals, rectangular finite grounds and mesh',
                 'all outer boundaries insulated; only coplanar metal traces grounded'],
        not_matched=['same-mesh agreement does not measure truncation or mesh accuracy'],
        observables=[observable('complex C','F/m','max relative difference',error,1e-9)],
        analytical_acceptance='free-space panels and single-line elliptic fields; separate mesh/domain checks',stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    assert error<1e-9
    fine=section.analyze(**FINE)
    outer=factory(**dict(p,box_width=24e-3,air_height=12e-3,lower_air_height=12e-3)).analyze(**FINE)
    np.testing.assert_allclose(modes(coarse),modes(fine),rtol=.005)
    np.testing.assert_allclose(modes(outer),modes(fine),rtol=.01)
    print(factory.__name__,'physical coarse/fine/outer',modes(coarse),modes(fine),modes(outer))


@pytest.mark.parametrize('factory',FACTORIES)
def test_geometry_material_areas_open_boundaries_and_json(factory):
    section=factory(**params(factory,True))
    assert (section.bottom,section.top,section.sides)==('open','open','open')
    assert [l.name for l in section.layers]==['lower_air','substrate','air']
    assert section.height==pytest.approx(.0125)
    assert all(t.y==pytest.approx(.0065) for t in section.traces)
    assert sum(t.ground for t in section.traces)==2
    assert all(t.top_width is None for t in section.traces if t.ground)
    automatic=factory(**dict(params(factory),lower_air_height=None))
    assert automatic.layers[0].thickness==pytest.approx(.005)
    doc=CrossSectionDocument(section,mesh=COARSE)
    restored=CrossSectionDocument.loads(doc.dumps())
    assert restored.dumps()==doc.dumps()
    np.testing.assert_array_equal(doc.analyze().C,restored.analyze().C)
    mesh=section.mesh(**COARSE);points=mesh.mesh.nodes[mesh.mesh.triangles]
    a,b=points[:,1]-points[:,0],points[:,2]-points[:,0]
    areas=abs(a[:,0]*b[:,1]-a[:,1]*b[:,0])/2
    metal=(2e-3+len(mesh.signals)*(.5e-3+.4e-3)/2)*35e-6
    assert areas[mesh.eps_r==1].sum()==pytest.approx(section.width*.012-metal,rel=1e-12)
    assert areas[mesh.eps_r==4].sum()==pytest.approx(section.width*.0005,rel=1e-12)
    assert np.all(mesh.mesh.nodes[mesh.ground,1]>0)


@pytest.mark.parametrize('factory',FACTORIES)
@pytest.mark.parametrize('change',[dict(lower_air_height=0),dict(lower_air_height=-1),
    dict(lower_air_height=True),dict(lower_air_height=np.nan),dict(gap=0),
    dict(ground_width=True),dict(substrate_height=0),dict(air_height=0),
    dict(top_width=1e-3),dict(box_width=1e-3)])
def test_bad_dimensions(factory,change):
    with pytest.raises(ValueError):factory(**dict(params(factory,True),**change))


@pytest.mark.parametrize('factory',FACTORIES)
@pytest.mark.parametrize('kind',['sweep','corners','uniform','normal'])
def test_saved_studies_fixed_signal_pitch_and_ground_clearance(factory,kind):
    sampling=dict(kind=kind,variables=[dict(name='width',lower=.45e-3,upper=.55e-3)])
    if kind!='corners':sampling['count']=2
    if kind in ('uniform','normal'):sampling['seed']=317
    if kind=='normal':sampling.update(variables=[dict(name='width',mean=.5e-3,std=.01e-3)],correlation=[[1]])
    paired=factory is coupled_unbacked_coplanar
    doc=ImpedanceStudyDocument(factory.__name__,params(factory,True),sampling=sampling,
        quantity='z_diff' if paired else 'z0',mesh=COARSE,fixed_pitch_m=.8e-3 if paired else None)
    replay=ImpedanceStudyDocument.loads(doc.dumps())
    np.testing.assert_array_equal(doc.samples(),replay.samples())
    if paired:
        for p in replay.sample_parameters():
            s=factory(**p)
            np.testing.assert_allclose([t.x for t in s.traces[:2]],[-.4e-3,.4e-3],rtol=1e-12)
            assert s.traces[-1].x0-s.traces[1].x1==pytest.approx(.2e-3,rel=1e-12)
    if kind=='sweep':assert replay.analyze().failed==0


@pytest.mark.parametrize('factory',FACTORIES)
def test_invalid_normal_draws_are_retained_and_bad_bounded_domain_rejected(factory):
    q='z_diff' if factory is coupled_unbacked_coplanar else 'z0'
    spec=dict(kind='normal',count=2,seed=3,correlation=[[1]],
              variables=[dict(name='ground_width',mean=-.1e-3,std=1e-6)])
    result=ImpedanceStudyDocument(factory.__name__,params(factory,True),sampling=spec,quantity=q,mesh=COARSE).analyze()
    assert result.failed==2 and result.summary is None
    with pytest.raises(ValueError):
        ImpedanceStudyDocument(factory.__name__,params(factory,True),quantity=q,
            sampling=dict(kind='corners',variables=[dict(name='ground_width',lower=-1e-3,upper=1e-3)]))


@pytest.mark.parametrize('factory',FACTORIES)
def test_saved_goal_against_independent_free_space_target(factory):
    paired=factory is coupled_unbacked_coplanar
    target=2*reference(factory)[1] if paired else reference(factory)[0]
    doc=ImpedanceDesignDocument(factory.__name__,params(factory),variable='width',bounds=(.4e-3,.6e-3),
        target=target,quantity='z_diff' if paired else 'z0',tolerance=1,mesh=VAC_FINE)
    result=ImpedanceDesignDocument.loads(doc.dumps()).solve()
    assert result.parameter==pytest.approx(.5e-3,rel=.04)
    assert abs(result.residual)<=1 and abs(result.refined_residual)<=1
    print(factory.__name__,'goal',target,result.parameter,result.residual,result.refined_residual)
