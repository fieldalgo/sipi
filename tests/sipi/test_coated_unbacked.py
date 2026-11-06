# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Coated coplanar sections without backing ground: fields and saved studies."""
import importlib.metadata as metadata
import numpy as np
import pytest
from scipy.constants import c, epsilon_0
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import (coated_unbacked_coplanar, coupled_coated_unbacked_coplanar,
                  CrossSectionDocument, ImpedanceDesignDocument)
from sipi.templates import unbacked_coplanar, coupled_unbacked_coplanar
from sipi.study import ImpedanceStudyDocument
from test_unbacked_coplanar import free_space_panels

FACTORIES=(coated_unbacked_coplanar,coupled_coated_unbacked_coplanar)
COARSE=dict(edge_size=4e-6,far_size=.25e-3,grade=.2)
FINE=dict(edge_size=1e-6,far_size=.125e-3,grade=.1)
VAC_COARSE=dict(COARSE,far_size=.5e-3)
VAC_FINE=dict(FINE,far_size=.25e-3)


def params(factory,physical=False):
    p=dict(width=.5e-3,gap=.2e-3,ground_width=1e-3,substrate_height=.5e-3,
           eps_r=1,coating_height=.1e-3,coating_eps_r=1,air_height=12e-3,lower_air_height=12e-3,box_width=24e-3)
    if factory is coupled_coated_unbacked_coplanar:p.update(gap=.3e-3,ground_gap=.2e-3)
    if physical:p.update(eps_r=4,coating_eps_r=3.5,thickness=.035e-3,top_width=.4e-3,
                         tan_delta=.01,coating_tan_delta=.02,air_height=6e-3,lower_air_height=6e-3,box_width=12e-3)
    return p


def modes(line):
    if len(line.names)==1:return np.array([line.z0])
    p=line.even_odd();return np.array([p['z_even'],p['z_odd']])


def reference(factory,count=160):
    intervals=([(-.25,.25),(-1.45,-.45),(.45,1.45)]
        if factory is coated_unbacked_coplanar else
        [(-.65,-.15),(.15,.65),(-1.85,-.85),(.85,1.85)])
    cap=free_space_panels(intervals,count)
    modal=[cap[0,0]] if factory is coated_unbacked_coplanar else [cap[0,0]+cap[0,1],cap[0,0]-cap[0,1]]
    return 1/(c*np.array(modal))


@pytest.mark.parametrize('factory',FACTORIES)
def test_vacuum_independent_panels_mesh_and_domain(factory):
    exact=reference(factory)
    np.testing.assert_allclose(reference(factory,80),exact,rtol=.003)
    values=[modes(factory(**params(factory)).analyze(**m)) for m in (VAC_COARSE,VAC_FINE)]
    errors=[abs(v/exact-1) for v in values]
    print(factory.__name__,'reference',exact,'FEM',values,'errors',errors)
    assert np.all(errors[-1] < .02) and np.all(errors[-1] < errors[0])
    wide=modes(factory(**dict(params(factory),box_width=48e-3,air_height=24e-3,lower_air_height=24e-3)).analyze(**VAC_FINE))
    np.testing.assert_allclose(wide,values[-1],rtol=.01)
    print('expanded',wide)


@pytest.mark.parametrize('factory',FACTORIES)
def test_finite_coating_convergence_and_air_limit(factory):
    p=params(factory,True)
    coarse,fine=[factory(**p).analyze(**m) for m in (COARSE,FINE)]
    wide=factory(**dict(p,box_width=24e-3,air_height=12e-3,lower_air_height=12e-3)).analyze(**FINE)
    print(factory.__name__,'coated coarse/fine/outer',modes(coarse),modes(fine),modes(wide))
    np.testing.assert_allclose(modes(coarse),modes(fine),rtol=.005)
    np.testing.assert_allclose(modes(wide),modes(fine),rtol=.01)
    air=factory(**dict(p,coating_eps_r=1,coating_tan_delta=0)).analyze(**FINE)
    plain={k:v for k,v in p.items() if not k.startswith('coating_')}
    plain['air_height']+=p['coating_height']
    original=unbacked_coplanar if factory is coated_unbacked_coplanar else coupled_unbacked_coplanar
    uncoated=original(**plain).analyze(**FINE)
    np.testing.assert_allclose(modes(air),modes(uncoated),rtol=.005)
    assert np.linalg.eigvalsh(fine.C-air.C).min()>0


@pytest.mark.parametrize('factory',FACTORIES)
def test_independent_complex_capacitance(factory):
    skfem=require_tool('scikit-fem')
    from skfem.helpers import dot,grad
    m=factory(**params(factory,True)).mesh(**COARSE)
    clock=Stopwatch()
    with clock('reference'):
        basis=skfem.Basis(skfem.MeshTri(m.mesh.nodes.T,m.mesh.triangles.T),skfem.ElementTriP1())
        @skfem.BilinearForm(dtype=complex)
        def form(u,v,w):return w.eps*dot(grad(u),grad(v))
        k=skfem.asm(form,basis,eps=(m.eps_r*(1-1j*m.tan_delta))[:,None])
        fixed=np.unique(np.concatenate([m.ground,*m.signals.values()]))
        fields=[]
        for nodes in m.signals.values():
            v=np.zeros(basis.N,dtype=complex);v[nodes]=1
            fields.append(skfem.solve(*skfem.condense(k,np.zeros(basis.N,dtype=complex),x=v,D=fixed)))
        u=np.array(fields).T
        expected=epsilon_0*(u.T@(k@u))
    with clock('openphysics'):
        line=m.line_parameters();observed=line.C-1j*line.C_loss
    error=float(np.max(abs(observed/expected-1)))
    record=make_record(case=factory.__name__,physics='coated unbacked coplanar electrostatics',
        api='sipi.'+factory.__name__,discretization='conforming triangular P1 extraction',
        tool='scikit-fem',tool_discretization='complex P1 assembly and independent energy matrix',
        matched=['same mesh, coating/substrate permittivity and loss, finite rectangular coplanar grounds',
                 'open outer boundaries and only coplanar ground traces'],
        not_matched=['same-mesh agreement is not mesh or domain convergence'],
        observables=[observable('complex C','F/m','max relative difference',error,1e-9)],
        analytical_acceptance='neutral free-space panel reference and separate finite-coating mesh/domain checks',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'))
    emit(record)
    assert error<1e-9


@pytest.mark.parametrize('factory',FACTORIES)
def test_geometry_area_and_json(factory):
    section=factory(**params(factory,True))
    signals=[t for t in section.traces if not t.ground]
    grounds=[t for t in section.traces if t.ground]
    assert len(grounds)==2 and all(t.top_width is None for t in grounds)
    assert all(t.top_width==.4e-3 for t in signals)
    assert section.height==pytest.approx(.0126)
    assert (section.bottom,section.top,section.sides)==('open','open','open')
    assert [l.name for l in section.layers]==['lower_air','substrate','coating','air']
    assert all(t.y==pytest.approx(.0065) for t in section.traces)
    automatic=factory(**dict(params(factory),lower_air_height=None))
    assert automatic.layers[0].thickness==pytest.approx(.005)
    doc=CrossSectionDocument(section,mesh=COARSE)
    restored=CrossSectionDocument.loads(doc.dumps())
    assert restored.dumps()==doc.dumps()
    np.testing.assert_array_equal(doc.analyze().C,restored.analyze().C)
    mesh=section.mesh(**COARSE)
    points=mesh.mesh.nodes[mesh.mesh.triangles]
    a,b=points[:,1]-points[:,0],points[:,2]-points[:,0]
    areas=abs(a[:,0]*b[:,1]-a[:,1]*b[:,0])/2
    metal=(2*1e-3+len(signals)*(.5e-3+.4e-3)/2)*.035e-3
    assert areas[mesh.eps_r==3.5].sum()==pytest.approx(section.width*.1e-3-metal,rel=1e-12)
    assert areas[mesh.eps_r==4].sum()==pytest.approx(section.width*.5e-3,rel=1e-12)
    assert areas[mesh.eps_r==1].sum()==pytest.approx(section.width*.012,rel=1e-12)
    assert np.all(mesh.mesh.nodes[mesh.ground,1]>0)


@pytest.mark.parametrize('factory',FACTORIES)
@pytest.mark.parametrize('change',[dict(gap=0),dict(ground_width=True),dict(coating_height=.035e-3),
    dict(coating_eps_r=0),dict(coating_tan_delta=-1),dict(air_height=0),dict(top_width=1e-3),dict(box_width=1e-3),
    dict(lower_air_height=0),dict(lower_air_height=-1),dict(lower_air_height=True),
    dict(lower_air_height=np.nan),dict(lower_air_height=np.inf)])
def test_bad_dimensions(factory,change):
    with pytest.raises(ValueError):factory(**dict(params(factory,True),**change))


@pytest.mark.parametrize('factory',FACTORIES)
def test_air_clearance_is_measured_above_coating(factory):
    section=factory(**dict(params(factory,True),air_height=5e-6))
    assert section.layers[-1].thickness==pytest.approx(5e-6)
    assert section.height==pytest.approx(.006605)


@pytest.mark.parametrize('factory',FACTORIES)
@pytest.mark.parametrize('kind',['sweep','corners','uniform','normal'])
def test_study_replay_and_pitch(factory,kind):
    p=params(factory,True)
    sampling=dict(kind=kind,variables=[dict(name='width',lower=.45e-3,upper=.55e-3)])
    if kind!='corners':sampling['count']=2
    if kind in ('normal','uniform'):sampling['seed']=317
    if kind=='normal':
        sampling['variables']=[dict(name='width',mean=.5e-3,std=.01e-3)]
        sampling['correlation']=[[1]]
    paired=factory is coupled_coated_unbacked_coplanar
    doc=ImpedanceStudyDocument(factory.__name__,p,sampling=sampling,quantity='z_diff' if paired else 'z0',
        mesh=COARSE,fixed_pitch_m=.8e-3 if paired else None)
    restored=ImpedanceStudyDocument.loads(doc.dumps())
    np.testing.assert_array_equal(doc.samples(),restored.samples())
    if paired:
        for values in restored.sample_parameters():
            cs=factory(**values)
            np.testing.assert_allclose([t.x for t in cs.traces[:2]],[-.4e-3,.4e-3],rtol=1e-12)
            assert cs.traces[-1].x0-cs.traces[1].x1==pytest.approx(.2e-3,rel=1e-12)
    if kind=='sweep':assert restored.analyze().failed==0


@pytest.mark.parametrize('factory',FACTORIES)
def test_clearance_failure_rows_and_quantity(factory):
    q='z_diff' if factory is coupled_coated_unbacked_coplanar else 'z0'
    spec=dict(kind='normal',count=2,seed=3,correlation=[[1]],
              variables=[dict(name='coating_height',mean=.01e-3,std=1e-6)])
    result=ImpedanceStudyDocument(factory.__name__,params(factory,True),sampling=spec,quantity=q,mesh=COARSE).analyze()
    assert result.failed==2 and result.summary is None
    with pytest.raises(ValueError):
        ImpedanceStudyDocument(factory.__name__,params(factory,True),quantity=q,
            sampling=dict(kind='corners',variables=[dict(name='coating_height',lower=20e-6,upper=120e-6)]))
    bad = 'z0' if q=='z_diff' else 'z_diff'
    with pytest.raises(ValueError,match='quantity'):
        ImpedanceStudyDocument(factory.__name__,params(factory,True),sampling=spec,quantity=bad)


@pytest.mark.parametrize('factory',FACTORIES)
def test_saved_goal_with_independent_target(factory):
    paired=factory is coupled_coated_unbacked_coplanar
    target=2*reference(factory)[1] if paired else reference(factory)[0]
    doc=ImpedanceDesignDocument(factory.__name__,params(factory),variable='width',bounds=(.4e-3,.6e-3),
        target=target,quantity='z_diff' if paired else 'z0',tolerance=1,mesh=VAC_FINE)
    result=ImpedanceDesignDocument.loads(doc.dumps()).solve()
    assert result.parameter==pytest.approx(.5e-3,rel=.04)
    assert abs(result.residual)<=1 and abs(result.refined_residual)<=1
    print(factory.__name__,'goal',target,result.parameter,result.residual,result.refined_residual)
