# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved fixed-frequency material studies and independently checked width goals."""
import importlib.metadata as metadata
import json

import numpy as np
import pytest
from scipy.constants import epsilon_0, mu_0
from scipy.optimize import brentq
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import CrossSection, CrossSectionDocument, ImpedanceDesignDocument, GoalSeekError, seek_impedance
from sipi.dielectric import (ConstantDielectric, DebyeDielectric, PrincipalAxisDielectric,
                            TabulatedDielectric, dielectric_from_dict, dispersive_line)
from sipi.study import ImpedanceStudyDocument
from test_sipi_references import stripline_z0

F = 1e8
MESH = dict(edge_size=4e-6,far_size=.25e-3,grade=.2)


def material(angle=0):
    return PrincipalAxisDielectric(DebyeDielectric(2,[2],[F]),ConstantDielectric(5,.02),angle)


def parameters(pair=False):
    out=dict(width=.5e-3,substrate_height=.5e-3,eps_r=4,thickness=35e-6,
             air_height=4e-3,box_width=8e-3)
    if pair: out['gap']=.3e-3
    return out


def sampling(kind='sweep'):
    if kind=='normal':
        return dict(kind=kind,count=20,seed=591,correlation=[[1,.6],[.6,1]],variables=[
            dict(name='width',mean=.5e-3,std=.01e-3),dict(name='substrate_height',mean=.5e-3,std=.01e-3)])
    out=dict(kind=kind,variables=[dict(name='width',lower=.45e-3,upper=.55e-3)])
    if kind!='corners': out['count']=2
    if kind=='uniform': out['seed']=591
    return out


def study(pair=False, **kw):
    args=dict(sampling=sampling(),quantity='z_diff' if pair else 'z0',mesh=MESH,
              frequency=F,materials={'substrate':material()})
    args.update(kw)
    return ImpedanceStudyDocument('coupled_microstrip' if pair else 'microstrip',parameters(pair),**args)


@pytest.mark.parametrize('kind',['sweep','corners','uniform','normal'])
def test_new_material_study_preserves_sampling_and_fixed_pitch(kind,monkeypatch):
    def forbidden(*args,**kwargs): pytest.fail('parsing reached meshing')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    spec=sampling(kind)
    original=study(True,sampling=spec,fixed_pitch_m=.8e-3)
    restored=ImpedanceStudyDocument.loads(original.dumps())
    assert restored.dumps()==original.dumps()
    assert restored.to_dict()['schema']=='sipi.impedance-study/3'
    legacy=study(True,sampling=spec,fixed_pitch_m=.8e-3,frequency=None,materials=None)
    np.testing.assert_array_equal(restored.samples(),legacy.samples())
    assert restored.sample_parameters()==legacy.sample_parameters()
    for p in restored.sample_parameters(): assert p['width']+p['gap']==pytest.approx(.8e-3,rel=1e-12)
    spec['variables'][0]['name']='changed'; copy=restored.to_dict()
    copy['material_evaluation']['frequency_hz']=7
    assert restored.dumps()==original.dumps()


def test_material_study_preserves_fixed_plane_spacing_and_v2_serialization():
    p=dict(width=.5e-3,gap=.3e-3,lower_height=.4e-3,upper_height=.6e-3,lower_eps_r=2,upper_eps_r=6)
    spec=dict(kind='corners',variables=[dict(name='lower_height',lower=.3e-3,upper=.6e-3),
                                      dict(name='width',lower=.4e-3,upper=.6e-3)])
    args=dict(sampling=spec,quantity='z_diff',fixed_plane_spacing_m=.001,fixed_pitch_m=.8e-3,mesh=MESH)
    old=ImpedanceStudyDocument('coupled_layered_stripline',p,**args)
    new=ImpedanceStudyDocument('coupled_layered_stripline',p,frequency=F,materials={'lower':material()},**args)
    assert new.sample_parameters()==old.sample_parameters()
    data=new.to_dict(); data.pop('material_evaluation'); data['schema']='sipi.impedance-study/2'
    assert ImpedanceStudyDocument.from_dict(data).dumps()==old.dumps()
    for values in new.sample_parameters():
        assert values['lower_height']+values['upper_height']==pytest.approx(.001,rel=1e-12)


@pytest.mark.parametrize('pair',[False,True])
def test_tensor_study_rows_against_independent_complex_field_impedance(pair):
    skfem=require_tool('scikit-fem')
    from skfem.helpers import grad
    plan=study(pair); clock=Stopwatch()
    with clock('openphysics'): actual=ImpedanceStudyDocument.loads(plan.dumps()).analyze()
    assert actual.failed==0 and actual.input_json==plan.dumps()
    errors=[]
    for row in actual.rows:
        meshed=row.document.section.mesh(**row.document.mesh_options); mesh=meshed.mesh
        eps=np.array([material().permittivity(F) if mesh.region_names[r]=='substrate' else np.eye(2)
                      for r in mesh.regions])
        with clock('reference'):
            basis=skfem.Basis(skfem.MeshTri(mesh.nodes.T,mesh.triangles.T),skfem.ElementTriP1())
            @skfem.BilinearForm(dtype=complex)
            def form(u,v,w): return np.einsum('ij...,j...,i...->...',w.eps,grad(u),grad(v))
            caps=[]; fixed=np.unique(np.concatenate([meshed.ground,*meshed.signals.values()]))
            for coefficient in (eps,np.tile(np.eye(2),(mesh.num_triangles,1,1))):
                k=skfem.asm(form,basis,eps=coefficient.transpose(1,2,0)[:,:,:,None]); fields=[]
                for nodes in meshed.signals.values():
                    v=np.zeros(basis.N,complex); v[nodes]=1
                    fields.append(skfem.solve(*skfem.condense(k,np.zeros(basis.N,complex),x=v,D=fixed)))
                u=np.array(fields).T; caps.append(epsilon_0*(u.T@(k@u)))
            c,c0=caps[0].real,caps[1].real; l=mu_0*epsilon_0*np.linalg.inv(c0)
            mode=np.array([1,-1]) if pair else np.ones(1)
            expected=(2 if pair else 1)*np.sqrt((mode@l@mode)/(mode@c@mode))
        errors.append(float(abs(row.impedance/expected-1)))
    error=max(errors)
    record=make_record(case='material-impedance-study-'+('pair' if pair else 'single'),
        physics='fixed-frequency real quasi-static modal impedance',api='sipi.study.ImpedanceStudyDocument',
        discretization='geometry samples with complex constitutive overrides and vacuum inductance',
        tool='scikit-fem',tool_discretization='independent complex/vacuum P1 solves and modal quadratic forms',
        matched=['same sampled widths, mesh, boundaries, frequency and principal dielectric axes'],
        not_matched=['no conductor R, complex characteristic impedance or statistical yield certification'],
        observables=[observable('quasi-static impedance','ohm','max relative difference',error,1e-9)],
        analytical_acceptance='homogeneous dielectric scaling and independent Cohn stripline width goal',stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi')); emit(record)
    assert error<1e-9
    assert actual.summary['minimum']==min(row.impedance for row in actual.rows)


@pytest.mark.parametrize('model',[ConstantDielectric(4,.02),DebyeDielectric(2,[2],[F])])
def test_homogeneous_frequency_impedance_follows_real_capacitance_scaling(model):
    p=dict(width=.5e-3,plane_spacing=1e-3,eps_r=1)
    args=dict(quantity='z0',sampling=sampling(),mesh=MESH)
    vacuum=ImpedanceStudyDocument('stripline',p,**args).analyze()
    actual=ImpedanceStudyDocument('stripline',p,frequency=F,materials={'dielectric':model},**args).analyze()
    assert actual.failed==vacuum.failed==0
    factor=np.sqrt(model.permittivity(F).real)
    for row,reference in zip(actual.rows,vacuum.rows):
        assert row.impedance==pytest.approx(reference.impedance/factor,rel=1e-10)


def test_scalar_override_reproduces_legacy_constant_study():
    original=study(frequency=None,materials=None).analyze()
    constant=study(materials={'substrate':ConstantDielectric(4)}).analyze()
    np.testing.assert_allclose([r.impedance for r in original.rows],[r.impedance for r in constant.rows],rtol=1e-10)


def test_saved_dispersive_goal_matches_independent_cohn_width_and_preserves_replay():
    model=DebyeDielectric(2,[2],[F])
    doc=ImpedanceDesignDocument('stripline',dict(width=.5e-3,plane_spacing=1e-3,eps_r=1),
        variable='width',bounds=[.3e-3,1.2e-3],target=50,tolerance=.25,max_evaluations=24,
        frequency=F,materials={'dielectric':model},mesh=dict(edge_size=.5e-6,far_size=.125e-3,grade=.075))
    restored=ImpedanceDesignDocument.loads(doc.dumps()); assert restored.dumps()==doc.dumps()
    result=restored.solve()
    expected=brentq(lambda w:stripline_z0(w,1e-3,3)-50,.3e-3,1.2e-3)
    assert result.parameter==pytest.approx(expected,rel=.01)
    assert abs(result.residual)<=.25 and abs(result.refined_residual)<=.25
    assert result.history[-1].stage=='refinement'
    saved=json.loads(result.material_evaluation_json)
    assert saved==doc.to_dict()['material_evaluation']
    models={k:dielectric_from_dict(v) for k,v in saved['materials'].items()}
    sweep=dispersive_line(result.document.section,[saved['frequency_hz']],materials=models,**result.document.mesh_options)
    assert np.sqrt(sweep.L[0,0]/sweep.C[0,0,0])==pytest.approx(result.impedance,rel=1e-10)
    print('material Cohn goal',result.parameter,expected,result.residual,result.refined_residual)


@pytest.mark.parametrize('pair',[False,True])
def test_real_tensor_width_goals_check_requested_and_refined_mesh(pair):
    doc=ImpedanceDesignDocument('coupled_microstrip' if pair else 'microstrip',parameters(pair),
        variable='width',bounds=[.3e-3,.9e-3],target=100 if pair else 60,
        quantity='z_diff' if pair else 'z0',tolerance=1,max_evaluations=24,mesh=MESH,
        frequency=F,materials={'substrate':material()})
    result=ImpedanceDesignDocument.loads(doc.dumps()).solve()
    assert abs(result.residual)<=1 and abs(result.refined_residual)<=1
    assert result.material_evaluation_json is not None
    print('tensor material goal',pair,result.parameter,result.residual,result.refined_residual)


def test_normal_failures_are_retained_and_budget_checked_before_solving(monkeypatch):
    spec=dict(kind='normal',count=3,seed=7,correlation=[[1]],
              variables=[dict(name='width',mean=-.001,std=1e-6)])
    plan=study(sampling=spec)
    def forbidden(*args,**kwargs): pytest.fail('invalid geometry/budget reached meshing')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    with pytest.raises(ValueError,match='max_evaluations'): plan.analyze(max_evaluations=2)
    result=plan.analyze(max_evaluations=3)
    assert result.failed==3 and result.summary is None
    for row,width in zip(result.rows,plan.samples()[:,0]):
        assert row.parameters['width']==width and row.error_type=='ValueError' and row.document is None


@pytest.mark.parametrize('angle',[.4,-.2])
def test_tilted_tensor_pair_is_rejected_before_geometry(angle,monkeypatch):
    def forbidden(*args,**kwargs): pytest.fail('tilted pair reached meshing')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    with pytest.raises(ValueError,match='diagonal'): study(True,materials={'substrate':material(angle)})
    # Single-line orientation is allowed; a rotation of equal axes is still isotropic.
    study(materials={'substrate':material(angle)})
    same=ConstantDielectric(4,.02)
    study(True,materials={'substrate':PrincipalAxisDielectric(same,same,angle)})


@pytest.mark.parametrize('name',['eps_r','tan_delta'])
def test_material_variables_cannot_be_silently_overridden(name):
    spec=dict(kind='sweep',count=2,variables=[dict(name=name,lower=3 if name=='eps_r' else .01,
                                                upper=5 if name=='eps_r' else .03)])
    with pytest.raises(ValueError,match='geometry parameters only'): study(sampling=spec)
    with pytest.raises(ValueError,match='geometry parameters only'):
        ImpedanceDesignDocument('microstrip',parameters(),variable=name,bounds=[1,2],target=50,
                                 frequency=F,materials={'substrate':material()})


@pytest.mark.parametrize('edit',[
    lambda d:d.update(schema='sipi.impedance-study/2'),
    lambda d:d.pop('material_evaluation'),lambda d:d.pop('fixed_plane_spacing_m'),
    lambda d:d.update(material_evaluation=None),
    lambda d:d['material_evaluation'].update(extra=0),
    lambda d:d['material_evaluation'].pop('frequency_hz'),
    lambda d:d['material_evaluation'].update(frequency_hz=True),
    lambda d:d['material_evaluation'].update(frequency_hz=-1),
    lambda d:d['material_evaluation'].update(frequency_hz=[1]),
    lambda d:d['material_evaluation'].update(materials=[]),
    lambda d:d['material_evaluation']['materials'].update(unknown={}),
])
def test_invalid_material_study_contract_fails_before_geometry(edit,monkeypatch):
    raw=study().to_dict(); edit(raw)
    def forbidden(*args,**kwargs): pytest.fail('invalid input reached meshing')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    with pytest.raises(ValueError): ImpedanceStudyDocument.from_dict(raw)


@pytest.mark.parametrize('edit',[
    lambda d:d.pop('material_evaluation'),lambda d:d.update(schema='sipi.impedance-design/1'),
    lambda d:d.update(material_evaluation=None),
    lambda d:d['material_evaluation'].update(extra=0),
    lambda d:d['material_evaluation'].update(materials=[]),
    lambda d:d['material_evaluation'].update(frequency_hz=None),
])
def test_invalid_material_goal_contract_fails_before_geometry(edit,monkeypatch):
    doc=ImpedanceDesignDocument('microstrip',parameters(),variable='width',bounds=[.3e-3,.9e-3],
        target=60,frequency=F,materials={'substrate':material()})
    raw=doc.to_dict(); edit(raw)
    def forbidden(*args,**kwargs): pytest.fail('invalid goal reached meshing')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    with pytest.raises(ValueError): ImpedanceDesignDocument.from_dict(raw)


def test_frequency_material_pairing_and_nested_table_ranges_are_explicit(monkeypatch):
    for kw in (dict(frequency=None),dict(materials=None),dict(frequency=True),dict(frequency=float('nan'))):
        with pytest.raises(ValueError): study(**kw)
    table=PrincipalAxisDielectric(TabulatedDielectric([1e9,1e10],[4,3],[.01,.02]),ConstantDielectric(3))
    def forbidden(*args,**kwargs): pytest.fail('table range error reached meshing')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    with pytest.raises(ValueError,match='extrapolation'): study(materials={'substrate':table})
    with pytest.raises(ValueError,match='together'):
        seek_impedance(lambda _:None,[.3e-3,.9e-3],60,frequency=F)


def test_legacy_goal_input_keeps_material_metadata_absent():
    doc=ImpedanceDesignDocument('stripline',dict(width=.5e-3,plane_spacing=1e-3,eps_r=4),
        variable='width',bounds=[.3e-3,.8e-3],target=50)
    assert doc.to_dict()['schema']=='sipi.impedance-design/1'
    assert 'material_evaluation' not in doc.to_dict()
