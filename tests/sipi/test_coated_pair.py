# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Planar-coated pair: geometry, independent electrostatics and saved studies."""
import importlib.metadata as metadata
import numpy as np
import pytest
from scipy.constants import c,epsilon_0
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import coupled_coated_microstrip, coupled_microstrip, CrossSectionDocument, ImpedanceDesignDocument
from sipi.study import ImpedanceStudyDocument
from test_coupled_coplanar import panel_reference

VACUUM = dict(width=.5e-3,gap=.3e-3,substrate_height=.5e-3,eps_r=1,
              coating_height=.1e-3,coating_eps_r=1,air_height=24e-3,box_width=48e-3)
PHYSICAL = dict(VACUUM,eps_r=4,coating_eps_r=3.5,thickness=.035e-3,
                top_width=.4e-3,tan_delta=.01,coating_tan_delta=.02,air_height=6e-3,box_width=12e-3)
COARSE = dict(edge_size=4e-6,far_size=.25e-3,grade=.2)
FINE = dict(edge_size=1e-6,far_size=.125e-3,grade=.1)
VACUUM_COARSE = dict(COARSE,far_size=.5e-3)
VACUUM_FINE = dict(FINE,far_size=.25e-3)


def modes(line):
    p=line.even_odd()
    return np.array([p['z_even'],p['z_odd']])


def reference(count):
    cap=panel_reference([(-.65e-3,-.15e-3),(.15e-3,.65e-3)],.5e-3,count)
    return 1/(c*np.array([cap[0,0]+cap[0,1],cap[0,0]-cap[0,1]]))


def test_vacuum_panel_reference_mesh_and_domain_convergence():
    exact=reference(160)
    np.testing.assert_allclose(reference(80),exact,rtol=.003)
    values=[modes(coupled_coated_microstrip(**VACUUM).analyze(**m)) for m in (VACUUM_COARSE,VACUUM_FINE)]
    errors=[abs(z/exact-1) for z in values]
    print('vacuum reference',exact,'FEM',values,'errors',errors)
    assert np.all(errors[-1] < .02)
    assert np.all(errors[-1] < errors[0])
    wide=modes(coupled_coated_microstrip(**dict(VACUUM,box_width=96e-3,air_height=48e-3)).analyze(**VACUUM_FINE))
    np.testing.assert_allclose(wide,values[-1],rtol=.01)
    print('vacuum reference',exact,'FEM',values,'errors',errors,'expanded',wide)


def test_coating_mesh_domain_air_limit_and_capacitance_order():
    coarse,fine=[coupled_coated_microstrip(**PHYSICAL).analyze(**m) for m in (COARSE,FINE)]
    wide=coupled_coated_microstrip(**dict(PHYSICAL,box_width=24e-3,air_height=12e-3)).analyze(**FINE)
    print('coated coarse/fine/expanded',modes(coarse),modes(fine),modes(wide))
    np.testing.assert_allclose(modes(coarse),modes(fine),rtol=.005)
    np.testing.assert_allclose(modes(wide),modes(fine),rtol=.01)
    air=coupled_coated_microstrip(**dict(PHYSICAL,coating_eps_r=1,coating_tan_delta=0)).analyze(**FINE)
    plain_params={k:v for k,v in PHYSICAL.items() if not k.startswith('coating_')}
    plain_params['air_height']+=PHYSICAL['coating_height']
    plain=coupled_microstrip(**plain_params).analyze(**FINE)
    np.testing.assert_allclose(modes(air),modes(plain),rtol=.005)
    assert np.linalg.eigvalsh(fine.C-air.C).min() > 0
    print('coated coarse/fine/expanded',modes(coarse),modes(fine),modes(wide),
          'air/plain',modes(air),modes(plain))


def test_independent_complex_p1_matrix_for_finite_coating():
    skfem=require_tool('scikit-fem')
    from skfem.helpers import dot,grad
    m=coupled_coated_microstrip(**PHYSICAL).mesh(**COARSE)
    clock=Stopwatch()
    with clock('reference'):
        basis=skfem.Basis(skfem.MeshTri(m.mesh.nodes.T,m.mesh.triangles.T),skfem.ElementTriP1())
        @skfem.BilinearForm(dtype=complex)
        def form(u,v,w):return w.eps*dot(grad(u),grad(v))
        k=skfem.asm(form,basis,eps=(m.eps_r*(1-1j*m.tan_delta))[:,None])
        fixed=np.unique(np.concatenate([m.ground,*m.signals.values()]))
        fields=[]
        for nodes in m.signals.values():
            boundary=np.zeros(basis.N,dtype=complex);boundary[nodes]=1
            fields.append(skfem.solve(*skfem.condense(k,np.zeros(basis.N,dtype=complex),x=boundary,D=fixed)))
        u=np.array(fields).T
        expected=epsilon_0*(u.T@(k@u))
    with clock('openphysics'):
        line=m.line_parameters()
        observed=line.C-1j*line.C_loss
    error=float(np.max(abs(observed/expected-1)))
    record=make_record(case='planar-coated-pair',physics='complex electrostatic capacitance matrix',
        api='sipi.coupled_coated_microstrip',discretization='conforming triangular P1 extraction',
        tool='scikit-fem',tool_discretization='independent complex P1 assembly and energy bilinear form',
        matched=['identical mesh, finite tapered conductors, dielectric and coating permittivities/losses',
                 'ground plane and natural open top/side boundaries'],
        not_matched=['same-mesh agreement does not establish domain or mesh convergence'],
        observables=[observable('complex C','F/m','max relative difference',error,1e-9)],
        analytical_acceptance='vacuum image-charge panel reference; separate refinement/domain and coating limits',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'))
    emit(record)
    assert error < 1e-9


def test_geometry_material_areas_and_json_roundtrip():
    section=coupled_coated_microstrip(**PHYSICAL)
    assert [x.name for x in section.layers]==['substrate','coating','air']
    assert section.height==pytest.approx(.0066)
    np.testing.assert_allclose([x.x for x in section.traces],[-.4e-3,.4e-3],rtol=1e-12)
    assert all(x.y==.5e-3 and x.top_width==.4e-3 for x in section.traces)
    doc=CrossSectionDocument(section,mesh=COARSE)
    replay=CrossSectionDocument.loads(doc.dumps())
    assert replay.dumps()==doc.dumps()
    np.testing.assert_array_equal(doc.analyze().C,replay.analyze().C)
    mesh=section.mesh(**COARSE)
    points=mesh.mesh.nodes[mesh.mesh.triangles]
    a,b=points[:,1]-points[:,0],points[:,2]-points[:,0]
    areas=abs(a[:,0]*b[:,1]-a[:,1]*b[:,0])/2
    expected=section.width*PHYSICAL['coating_height']-2*(.5e-3+.4e-3)/2*.035e-3
    assert areas[mesh.eps_r==3.5].sum()==pytest.approx(expected,rel=1e-12)
    for interface in (.5e-3,.6e-3):
        assert not np.any((points[:,:,1].min(axis=1)<interface-1e-12)&
                          (points[:,:,1].max(axis=1)>interface+1e-12))


@pytest.mark.parametrize('change',[dict(gap=0),dict(coating_height=.035e-3),dict(coating_height=0),
    dict(coating_eps_r=True),dict(coating_tan_delta=-1),dict(air_height=0),
    dict(top_width=1e-3),dict(box_width=1e-3)])
def test_invalid_geometry(change):
    with pytest.raises(ValueError):coupled_coated_microstrip(**dict(PHYSICAL,**change))


@pytest.mark.parametrize('kind',['sweep','corners','uniform','normal'])
def test_study_json_fixed_pitch_and_saved_coating_parameters(kind):
    sampling=dict(kind=kind,variables=[dict(name='width',lower=.45e-3,upper=.55e-3)])
    if kind!='corners':sampling['count']=2
    if kind in ('normal','uniform'):sampling['seed']=1707
    if kind=='normal':
        sampling['variables']=[dict(name='width',mean=.5e-3,std=.01e-3)]
        sampling['correlation']=[[1]]
    plan=ImpedanceStudyDocument('coupled_coated_microstrip',PHYSICAL,sampling=sampling,
        quantity='z_diff',mesh=COARSE,fixed_pitch_m=.8e-3)
    replay=ImpedanceStudyDocument.loads(plan.dumps())
    np.testing.assert_array_equal(plan.samples(),replay.samples())
    for params in replay.sample_parameters():
        section=coupled_coated_microstrip(**params)
        np.testing.assert_allclose([x.x for x in section.traces],[-.4e-3,.4e-3],rtol=1e-12)
        assert section.layers[1].eps_r==3.5
    if kind=='sweep':assert replay.analyze().failed==0


def test_coating_clearance_bounds_and_failed_normal_rows():
    sampling=dict(kind='corners',variables=[dict(name='coating_height',lower=.03e-3,upper=.1e-3)])
    with pytest.raises(ValueError,match='exceed'):
        ImpedanceStudyDocument('coupled_coated_microstrip',PHYSICAL,sampling=sampling,quantity='z_diff')
    sampling=dict(kind='normal',count=2,seed=3,correlation=[[1]],
                  variables=[dict(name='coating_height',mean=.01e-3,std=1e-6)])
    plan=ImpedanceStudyDocument('coupled_coated_microstrip',PHYSICAL,sampling=sampling,quantity='z_diff',mesh=COARSE)
    result=plan.analyze()
    assert result.failed==2 and result.summary is None
    assert all(row.error and row.document is None for row in result.rows)


def test_saved_goal_matches_independent_vacuum_target_and_refinement():
    target=2*reference(160)[1]
    plan=ImpedanceDesignDocument('coupled_coated_microstrip',VACUUM,variable='width',
        bounds=(.4e-3,.6e-3),target=target,quantity='z_diff',tolerance=1.,mesh=VACUUM_FINE)
    replay=ImpedanceDesignDocument.loads(plan.dumps())
    result=replay.solve()
    assert result.parameter==pytest.approx(.5e-3,rel=.04)
    assert abs(result.residual)<=1 and abs(result.refined_residual)<=1
    assert result.history[-1].stage=='refinement'
    print('goal',target,'width',result.parameter,'residuals',result.residual,result.refined_residual)
