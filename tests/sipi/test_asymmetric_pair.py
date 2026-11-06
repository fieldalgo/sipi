# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Unequal manufacturing pair, forward-current impedance and saved designs."""
import importlib.metadata as metadata
import numpy as np
import pytest
from scipy.constants import c,epsilon_0
from crosscheck import Stopwatch,emit,make_record,observable,require_tool
from sipi import (asymmetric_coupled_microstrip,coupled_microstrip,CrossSectionDocument,
                  ImpedanceDesignDocument,LineParameters,rlgc_characteristic)
from sipi.dielectric import ConstantDielectric,PrincipalAxisDielectric
from sipi.study import ImpedanceStudyDocument
from test_coupled_coplanar import panel_reference

PARAMS=dict(left_width=.4e-3,right_width=.65e-3,gap=.25e-3,substrate_height=.5e-3,
    eps_r=4,left_thickness=35e-6,right_thickness=50e-6,left_top_width=.32e-3,
    right_top_width=.55e-3,tan_delta=.02,air_height=6e-3,box_width=12e-3)
COARSE=dict(edge_size=4e-6,far_size=.25e-3,grade=.2)
FINE=dict(edge_size=1e-6,far_size=.125e-3,grade=.1)
GOAL_MESH=dict(edge_size=2e-6,far_size=.125e-3,grade=.1)


def section(**changes):return asymmetric_coupled_microstrip(**dict(PARAMS,**changes))


def test_geometry_dimensions_positions_and_v2_replay():
    cs=section();left,right=cs.traces
    assert (left.name,right.name)==('positive','negative')
    assert right.x-right.width/2-(left.x+left.width/2)==pytest.approx(PARAMS['gap'],rel=1e-12)
    assert left.x-left.width/2==pytest.approx(-(right.x+right.width/2),rel=1e-12)
    assert left.y==right.y==PARAMS['substrate_height']
    assert (left.thickness,right.thickness)==(35e-6,50e-6)
    assert (left.top_width,right.top_width)==(.32e-3,.55e-3)
    doc=CrossSectionDocument(cs,mesh=COARSE)
    assert doc.to_dict()['schema']=='sipi.cross-section/2'
    assert CrossSectionDocument.loads(doc.dumps()).dumps()==doc.dumps()
    defaults=asymmetric_coupled_microstrip(left_width=.4e-3,right_width=.65e-3,gap=.25e-3,
        substrate_height=.5e-3,eps_r=4,left_thickness=35e-6,right_thickness=50e-6)
    assert defaults.layers[1].thickness==pytest.approx(5e-3+50e-6)
    assert defaults.width==pytest.approx(max(10e-3,4*1.3e-3))


@pytest.mark.parametrize('thickness,top',[(0,None),(35e-6,None),(35e-6,.4e-3),(35e-6,.6e-3)])
def test_equal_pair_is_byte_identical_to_existing_template(thickness,top):
    common=dict(gap=.3e-3,substrate_height=.5e-3,eps_r=4,tan_delta=.02)
    old=coupled_microstrip(width=.5e-3,thickness=thickness,top_width=top,**common)
    new=asymmetric_coupled_microstrip(left_width=.5e-3,right_width=.5e-3,
        left_thickness=thickness,right_thickness=thickness,left_top_width=top,right_top_width=top,**common)
    assert CrossSectionDocument(new).dumps()==CrossSectionDocument(old).dumps()


def test_vacuum_image_charge_reference_and_mesh_refinement():
    reference=panel_reference([(-.65e-3,-.25e-3),(0,.65e-3)],.5e-3,160)
    earlier=panel_reference([(-.65e-3,-.25e-3),(0,.65e-3)],.5e-3,80)
    assert abs(earlier/reference-1).max()<.003
    d=np.array([1.,-1.]);target=float(d@np.linalg.solve(reference,d)/c)
    values=[]
    for mesh in [dict(COARSE,far_size=.5e-3),dict(FINE,far_size=.25e-3)]:
        line=section(eps_r=1,tan_delta=0,left_thickness=0,right_thickness=0,
            left_top_width=None,right_top_width=None,air_height=12e-3,box_width=24e-3).analyze(**mesh)
        values.append((float(abs(line.C/reference-1).max()),abs(line.z_diff_forward/target-1)))
    print('vacuum panel forward Z',target,'coarse/fine C/Z errors',values)
    assert max(values[1])<.02 and all(b<a for a,b in zip(*values))


def test_independent_complex_field_and_separate_mesh_outer_convergence():
    skfem=require_tool('scikit-fem')
    from skfem.helpers import dot,grad
    cs=section();m=cs.mesh(**COARSE);clock=Stopwatch()
    with clock('openphysics'):actual=m.line_parameters();cc=actual.C-1j*actual.C_loss
    with clock('reference'):
        basis=skfem.Basis(skfem.MeshTri(m.mesh.nodes.T,m.mesh.triangles.T),skfem.ElementTriP1())
        @skfem.BilinearForm(dtype=complex)
        def form(u,v,w):return w.eps*dot(grad(u),grad(v))
        k=skfem.asm(form,basis,eps=(m.eps_r*(1-1j*m.tan_delta))[:,None])
        fixed=np.unique(np.concatenate([m.ground,*m.signals.values()]));fields=[]
        for nodes in m.signals.values():
            v=np.zeros(basis.N,complex);v[nodes]=1
            fields.append(skfem.solve(*skfem.condense(k,np.zeros(basis.N,complex),x=v,D=fixed)))
        u=np.array(fields).T;expected=epsilon_0*(u.T@(k@u))
    error=float(abs(cc/expected-1).max())
    record=make_record(case='asymmetric-surface-pair',physics='unequal lossy dielectric cross-section',
        api='sipi.asymmetric_coupled_microstrip',discretization='independent widths, thicknesses and top widths on conforming P1 mesh',
        tool='scikit-fem',tool_discretization='independent complex P1 assembly and energy',
        matched=['same mesh, material coefficients, conductor order and backing ground'],
        not_matched=['no measured etching, longitudinal variations or three-dimensional transitions'],
        observables=[observable('complex C','F/m','max relative difference',error,1e-9)],
        analytical_acceptance='independent vacuum image panels, symmetric reduction and mesh/outer convergence',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    assert error<1e-9
    fine=cs.analyze(**FINE);outer=section(air_height=12e-3,box_width=24e-3).analyze(**FINE)
    fc=fine.C-1j*fine.C_loss;oc=outer.C-1j*outer.C_loss
    changes=float(abs(cc/fc-1).max()),float(abs(oc/fc-1).max())
    print('asymmetric complex C mesh/outer',changes,'fine forward',fine.z_diff_forward)
    assert max(changes)<.01
    assert np.linalg.eigvalsh(fine.C).min()>0 and np.linalg.eigvalsh(fine.C_loss).min()>0
    with pytest.raises(ValueError):fine.even_odd()


def test_mirrored_dimensions_permute_capacitance_and_preserve_forward_impedance():
    original=section().analyze(**FINE)
    mirror=section(left_width=PARAMS['right_width'],right_width=PARAMS['left_width'],
        left_thickness=PARAMS['right_thickness'],right_thickness=PARAMS['left_thickness'],
        left_top_width=PARAMS['right_top_width'],right_top_width=PARAMS['left_top_width']).analyze(**FINE)
    # Independent unstructured meshes need not be exact mirror images.
    np.testing.assert_allclose(mirror.C,original.C[::-1,::-1],rtol=.005,atol=0)
    assert mirror.z_diff_forward==pytest.approx(original.z_diff_forward,rel=.005)


def sqrt_spd(matrix):
    eigenvectors=np.linalg.eigh(matrix)
    eigenvalues,vectors=eigenvectors
    return (vectors*np.sqrt(eigenvalues))@vectors.T


@pytest.mark.parametrize('count',[1,2,3])
def test_real_impedance_matrix_against_independent_symmetric_geometric_mean(count):
    rng=np.random.default_rng(871+count)
    a,b=rng.normal(size=(2,count,count))
    cap=(a@a.T+np.eye(count))*1e-11;ind=(b@b.T+np.eye(count))*1e-7
    line=LineParameters(tuple(str(x) for x in range(count)),cap,np.eye(count)*1e-11,ind,cap*.03)
    actual=line.characteristic_impedance_matrix()
    root=sqrt_spd(cap);inverse=np.linalg.inv(root)
    reference=inverse@sqrt_spd(root@ind@root)@inverse
    assert abs(actual-reference).max()/abs(reference).max()<1e-10
    np.testing.assert_allclose(actual@cap@actual,ind,rtol=1e-10,atol=1e-20)
    assert not actual.flags.writeable and np.linalg.eigvalsh(actual).min()>0
    if count==1:assert actual[0,0]==pytest.approx(line.z0,rel=1e-12)
    if count==2:
        current=np.array([1.,-1.]);v=actual@current
        assert line.z_diff_forward==pytest.approx(v[0]-v[1],rel=1e-12)
    else:
        with pytest.raises(ValueError,match='exactly two'):line.z_diff_forward


def test_symmetric_limit_loss_exclusion_and_coordinate_scaling():
    cap=np.array([[120,-30],[-30,120]])*1e-12
    ind=np.array([[400,70],[70,400]])*1e-9
    c0=np.linalg.inv(ind)/c**2
    line=LineParameters(('a','b'),cap,c0,ind,cap*.2)
    assert line.z_diff_forward==pytest.approx(line.even_odd()['z_diff'],rel=1e-12)
    no_loss=LineParameters(line.names,cap,c0,ind,np.zeros_like(cap))
    np.testing.assert_array_equal(line.characteristic_impedance_matrix(),no_loss.characteristic_impedance_matrix())
    lossy=rlgc_characteristic([1],R=np.zeros((2,2)),L=ind,G=2*np.pi*line.C_loss,C=cap)
    assert abs(lossy.z_characteristic.imag).max()>1
    for scale in (1e-100,1e100):
        scaled=LineParameters(line.names,cap*scale,c0*scale,ind*scale,line.C_loss*scale)
        np.testing.assert_allclose(scaled.characteristic_impedance_matrix(),line.characteristic_impedance_matrix(),
                                   rtol=1e-10,atol=0)


def test_nonphysical_or_unrepresentable_forward_impedance_rejected():
    for cap in (-np.eye(2),np.diag([1e-30,1.]),np.array([[1.,.2],[.1,1.]])):
        line=LineParameters(('a','b'),cap,np.eye(2),np.eye(2),np.zeros((2,2)))
        with pytest.raises(ValueError):line.characteristic_impedance_matrix()


def sampling(kind='sweep'):
    if kind=='normal':
        return dict(kind=kind,count=4,seed=83,correlation=[[1,.7],[.7,1]],variables=[
            dict(name='left_width',mean=.4e-3,std=.03e-3),dict(name='right_width',mean=.65e-3,std=.04e-3)])
    return dict(kind=kind,count=3,variables=[dict(name='left_width',lower=.35e-3,upper=.5e-3)])


@pytest.mark.parametrize('material',[False,True])
def test_correlated_saved_study_and_forward_goal_with_refined_mesh(material):
    kwargs=({} if not material else dict(frequency=1e9,materials={'substrate':
        PrincipalAxisDielectric(ConstantDielectric(4,.02),ConstantDielectric(5,.03),.3)}))
    study=ImpedanceStudyDocument('asymmetric_coupled_microstrip',PARAMS,
        sampling=sampling('normal'),quantity='z_diff_forward',mesh=COARSE,**kwargs)
    restored=ImpedanceStudyDocument.loads(study.dumps())
    np.testing.assert_array_equal(restored.samples(),study.samples())
    result=restored.analyze(max_evaluations=4)
    assert all(row.complete for row in result.rows) and result.summary is not None
    assert result.quantity=='z_diff_forward' and result.input_json==study.dumps()
    for row in result.rows:
        assert row.document is not None
    goal=ImpedanceDesignDocument('asymmetric_coupled_microstrip',PARAMS,variable='left_width',
        bounds=[.3e-3,1.2e-3],target=100,quantity='z_diff_forward',tolerance=1,mesh=GOAL_MESH,**kwargs)
    target=ImpedanceDesignDocument.loads(goal.dumps()).solve()
    print('asymmetric goal material',material,'width',target.parameter,'residuals',target.residual,target.refined_residual)
    assert abs(target.residual)<=1 and abs(target.refined_residual)<=1
    assert target.material_evaluation_json is not None if material else target.material_evaluation_json is None


def test_unbounded_invalid_rows_preserved_without_resampling():
    sample=sampling('normal');sample['count']=8
    for v in sample['variables']:v['std']=1e-3
    study=ImpedanceStudyDocument('asymmetric_coupled_microstrip',PARAMS,
        sampling=sample,quantity='z_diff_forward',mesh=COARSE)
    planned=study.samples();result=study.analyze(max_evaluations=8)
    assert len(result.rows)==8 and any(not row.complete for row in result.rows)
    assert result.summary is None
    for row,values in zip(result.rows,planned):
        assert row.parameters['left_width']==values[0] and row.parameters['right_width']==values[1]
        if not row.complete:assert row.error_type is not None


def test_existing_pair_forward_quantity_and_tilted_material_are_explicit():
    params=dict(width=.5e-3,gap=.3e-3,substrate_height=.5e-3,eps_r=4)
    sample=dict(kind='sweep',count=2,variables=[dict(name='width',lower=.45e-3,upper=.55e-3)])
    kwargs=dict(frequency=1e9,materials={'substrate':PrincipalAxisDielectric(
        ConstantDielectric(4),ConstantDielectric(5),.3)})
    doc=ImpedanceStudyDocument('coupled_microstrip',params,sampling=sample,quantity='z_diff_forward',
        fixed_pitch_m=.8e-3,mesh=COARSE,**kwargs)
    assert all(r.complete for r in doc.analyze(max_evaluations=2).rows)
    with pytest.raises(ValueError,match='diagonal'):
        ImpedanceStudyDocument('coupled_microstrip',params,sampling=sample,quantity='z_diff',**kwargs)
    with pytest.raises(ValueError):
        ImpedanceStudyDocument('asymmetric_coupled_microstrip',PARAMS,sampling=sampling(),
            quantity='z_diff_forward',fixed_pitch_m=.8e-3)
    with pytest.raises(ValueError,match='quantity'):
        ImpedanceStudyDocument('asymmetric_coupled_microstrip',PARAMS,sampling=sampling(),quantity='z_diff')


@pytest.mark.parametrize('changes',[
    dict(left_width=0),dict(right_width=-1),dict(gap=0),dict(left_width=True),
    dict(left_thickness=-1),dict(right_thickness=float('inf')),dict(right_top_width=0),
    dict(left_top_width=True),dict(air_height=10e-6),dict(box_width=.5e-3),
    dict(left_top_width=3e-3,right_top_width=3e-3),dict(substrate_height=0),
])
def test_invalid_manufacturing_dimensions(changes):
    with pytest.raises(ValueError):section(**changes)
