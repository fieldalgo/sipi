# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Material sampling: strict leaves, retained failures and homogeneous invariants."""
import json
import numpy as np
import pytest
from sipi import CrossSection
from sipi.study import ImpedanceStudyDocument
from sipi.dielectric import (ConstantDielectric, DebyeDielectric, WidebandDielectric,
                            TabulatedDielectric, PrincipalAxisDielectric)
from sipi.execution import execute_saved, normalize_saved, saved_schemas

MESH = dict(edge_size=5e-6, far_size=.25e-3, grade=.2)
PARAMS = dict(width=.5e-3, plane_spacing=1e-3, eps_r=1)
F = 1e8


def plan(model=None, path=None, bounds=(2, 6), **kwargs):
    args = dict(quantity='z0', mesh=MESH, frequency=F,
        materials={'dielectric': ConstantDielectric(4) if model is None else model},
        material_variables={'dk': dict(region='dielectric', path=['eps_r'] if path is None else path)},
        sampling=dict(kind='sweep', count=3, variables=[dict(name='dk', lower=bounds[0], upper=bounds[1])]))
    args.update(kwargs)
    return ImpedanceStudyDocument('stripline', PARAMS, **args)


def test_homogeneous_material_sampling_analytic_scaling_and_replay():
    original = plan()
    restored = ImpedanceStudyDocument.loads(original.dumps())
    assert original.dumps() == restored.dumps() == normalize_saved(original.dumps())
    assert 'sipi.impedance-study/4' in saved_schemas()
    result = restored.analyze()
    assert result.failed == 0
    invariant = np.array([r.impedance for r in result.rows])*np.sqrt([2, 4, 6])
    np.testing.assert_allclose(invariant, invariant[0], rtol=1e-10)
    for row, expected in zip(result.rows, [2, 4, 6]):
        assert json.loads(row.material_evaluation_json)['materials']['dielectric']['parameters']['eps_r'] == expected
        assert 'dk' not in row.parameters
    output = execute_saved(restored.dumps())
    assert output['status'] == 'complete'
    assert output['result']['rows'][2]['material_evaluation']['materials']['dielectric']['parameters']['eps_r'] == 6
    np.testing.assert_allclose([r['value'] for r in output['result']['rows']],
                               [r.impedance for r in result.rows], rtol=1e-12)


def test_debye_pole_sampling_matches_independent_real_permittivity_formula():
    doc = plan(DebyeDielectric(2, [3], [F]), ['relaxation_hz', 0], (F/2, 2*F))
    actual = doc.analyze()
    assert actual.failed == 0
    pole = doc.samples()[:, 0]
    eps_real = 2+3/(1+(F/pole)**2)
    invariant = np.array([r.impedance for r in actual.rows])*np.sqrt(eps_real)
    np.testing.assert_allclose(invariant, invariant[0], rtol=1e-10)


@pytest.mark.parametrize('model,path,bounds', [
    (ConstantDielectric(4,.02), ['tan_delta'], (0,.04)),
    (DebyeDielectric(2,[2],[F]), ['strengths',0], (1,3)),
    (WidebandDielectric(4,.02,F), ['tan_delta_ref'], (.01,.03)),
    (TabulatedDielectric([F/2,2*F],[3,4],[.01,.02]), ['eps_r',1], (3.5,4.5)),
    (PrincipalAxisDielectric(ConstantDielectric(3),ConstantDielectric(5)),
     ['axis1','parameters','eps_r'], (2,4)),
    (PrincipalAxisDielectric(ConstantDielectric(3),ConstantDielectric(5)), ['angle_rad'], (-.1,.1)),
])
def test_numeric_model_leaves_without_field_solving(model,path,bounds,monkeypatch):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k: pytest.fail('normalization meshed'))
    doc = plan(model,path,bounds)
    restored = ImpedanceStudyDocument.loads(doc.dumps())
    assert restored.dumps() == doc.dumps()
    samples = doc.sample_material_evaluations()
    for value, expected in zip(samples,doc.samples()[:,0]):
        leaf = value['materials']['dielectric']['parameters']
        for key in path: leaf = leaf[key]
        assert leaf == expected
    samples[0]['materials'].clear()
    assert doc.sample_material_evaluations()[0]['materials']


@pytest.mark.parametrize('kind',['corners','uniform','normal'])
def test_joint_geometry_material_sampling_retains_order_and_correlation(kind):
    variables = [dict(name='width',lower=.4e-3,upper=.6e-3),dict(name='dk',lower=3,upper=5)]
    sampling = dict(kind=kind,variables=variables)
    if kind != 'corners': sampling.update(count=100,seed=91)
    if kind == 'normal':
        sampling.update(correlation=[[1,-1],[-1,1]],variables=[
            dict(name='width',mean=.5e-3,std=.02e-3),dict(name='dk',mean=4,std=.1)])
    doc = plan(sampling=sampling)
    restored = ImpedanceStudyDocument.loads(doc.dumps())
    np.testing.assert_array_equal(doc.samples(),restored.samples())
    for sample, p, material in zip(doc.samples(),doc.sample_parameters(),doc.sample_material_evaluations()):
        assert p['width'] == sample[0]
        assert material['materials']['dielectric']['parameters']['eps_r'] == sample[1]
    if kind == 'normal':
        z=(doc.samples()-[.5e-3,4])/[.02e-3,.1]
        np.testing.assert_allclose(z[:,0],-z[:,1],atol=1e-12,rtol=0)


def test_invalid_normal_material_rows_retained_and_budget_precedes_meshing(monkeypatch):
    doc = plan(sampling=dict(kind='normal',count=3,seed=9,correlation=[[1]],
                            variables=[dict(name='dk',mean=-2,std=.001)]))
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k: pytest.fail('invalid material meshed'))
    with pytest.raises(ValueError,match='max_evaluations'): doc.analyze(max_evaluations=2)
    result = doc.analyze()
    assert result.failed == 3 and result.summary is None
    for row, sample in zip(result.rows,doc.samples()):
        assert row.error_type == 'ValueError'
        assert json.loads(row.material_evaluation_json)['materials']['dielectric']['parameters']['eps_r'] == sample[0]
    output = execute_saved(doc.dumps())
    assert output['status'] == 'incomplete' and output['result']['failed'] == 3
    assert output['result']['rows'][0]['material_evaluation']['materials']['dielectric']['parameters']['eps_r'] < 0


@pytest.mark.parametrize('change',[
    lambda d: d.update(schema='sipi.impedance-study/3'),
    lambda d: d.update(material_evaluation=None),
    lambda d: d.update(material_variables={}),
    lambda d: d.update(material_variables=[]),
    lambda d: d['material_variables'].update(width=dict(region='dielectric',path=['eps_r'])),
    lambda d: d['material_variables'].update(other=dict(region='dielectric',path=['eps_r'])),
    lambda d: d['material_variables']['dk'].update(region='missing'),
    lambda d: d['material_variables']['dk'].update(path=[]),
    lambda d: d['material_variables']['dk'].update(path='eps_r'),
    lambda d: d['material_variables']['dk'].update(path=['kind']),
    lambda d: d['material_variables']['dk'].update(path=[True]),
    lambda d: d['material_variables']['dk'].update(path=['eps_r',0]),
    lambda d: d['material_variables']['dk'].update(extra=0),
    lambda d: d['sampling']['variables'][0].update(name='width',lower=.4e-3,upper=.6e-3),
    lambda d: d['sampling']['variables'][0].update(lower=-1),
    lambda d: d['sampling']['variables'][0].update(lower=True),
])
def test_invalid_bindings_and_physical_bounded_corners_rejected(change):
    data = plan().to_dict(); change(data)
    with pytest.raises(ValueError): ImpedanceStudyDocument.from_dict(data)


@pytest.mark.parametrize('path',[['strengths'],['strengths',-1],['strengths',True],
                                ['strengths',.0],['strengths',1],['schema']])
def test_sequence_paths_require_existing_exact_integer_leaf(path):
    with pytest.raises(ValueError): plan(DebyeDielectric(2,[2],[F]),path)


def test_tilted_tensor_differential_symmetry_gate_preserved():
    with pytest.raises(ValueError,match='diagonal'):
        ImpedanceStudyDocument('coupled_microstrip',dict(width=.5e-3,gap=.3e-3,substrate_height=.5e-3,eps_r=4),
            quantity='z_diff',frequency=F,
            materials={'substrate':PrincipalAxisDielectric(ConstantDielectric(3),ConstantDielectric(5))},
            material_variables={'angle':dict(region='substrate',path=['angle_rad'])},
            sampling=dict(kind='sweep',count=2,variables=[dict(name='angle',lower=-.1,upper=.1)]))


def test_legacy_material_study_json_unchanged_and_detached_inputs():
    bindings = {'dk':dict(region='dielectric',path=['eps_r'])}
    doc=plan(material_variables=bindings); saved=doc.dumps()
    bindings['dk']['path'][0]='bad'
    assert doc.dumps()==saved
    old=plan(material_variables=None,sampling=dict(kind='sweep',count=2,
        variables=[dict(name='width',lower=.4e-3,upper=.6e-3)]))
    assert old.to_dict()['schema']=='sipi.impedance-study/3'
    assert 'material_variables' not in old.to_dict()
    assert ImpedanceStudyDocument.loads(old.dumps()).dumps()==old.dumps()


def test_sampled_debye_microstrip_against_independent_complex_fem():
    import importlib.metadata as metadata
    from crosscheck import Stopwatch, emit, make_record, observable, require_tool
    from sipi.constants import epsilon_0, mu_0
    skfem = require_tool('scikit-fem')
    from skfem.helpers import dot, grad
    clock = Stopwatch()
    doc = ImpedanceStudyDocument('microstrip',
        dict(width=.5e-3, substrate_height=.5e-3, eps_r=1, air_height=2e-3, box_width=6e-3),
        quantity='z0', frequency=F, materials={'substrate':DebyeDielectric(2,[3],[F])},mesh=MESH,
        material_variables={'pole':dict(region='substrate',path=['relaxation_hz',0])},
        sampling=dict(kind='sweep',count=2,variables=[dict(name='pole',lower=F/2,upper=2*F)]))
    with clock('openphysics'): result = doc.analyze()
    assert result.failed == 0
    errors = []
    for row,pole in zip(result.rows,doc.samples()[:,0]):
        meshed = row.document.section.mesh(**row.document.mesh_options); mesh = meshed.mesh
        # Independent closed Debye expression, not the production model evaluator.
        eps = np.array([2+3/(1+1j*F/pole) if mesh.region_names[r]=='substrate' else 1
                        for r in mesh.regions])
        with clock('reference'):
            basis = skfem.Basis(skfem.MeshTri(mesh.nodes.T,mesh.triangles.T),skfem.ElementTriP1())
            @skfem.BilinearForm(dtype=complex)
            def form(u,v,w): return w.eps*dot(grad(u),grad(v))
            signal = next(iter(meshed.signals.values()))
            fixed = np.unique(np.concatenate([signal,meshed.ground])); caps=[]
            for coeff in (eps,np.ones(mesh.num_triangles)):
                k=skfem.asm(form,basis,eps=coeff[:,None]); u=np.zeros(basis.N,complex);u[signal]=1
                u=skfem.solve(*skfem.condense(k,np.zeros(basis.N,complex),x=u,D=fixed))
                caps.append(epsilon_0*(u@(k@u)))
            expected=np.sqrt(mu_0*epsilon_0/(caps[1].real*caps[0].real))
        errors.append(float(abs(row.impedance/expected-1)))
    error=max(errors)
    record=make_record(case='sampled-material-debye-microstrip',physics='real quasi-static impedance',
        api='sipi.study.ImpedanceStudyDocument',discretization='material pole samples on a planar FEM mesh',
        tool='scikit-fem',tool_discretization='independent complex P1 solve and closed Debye expression',
        matched=['same explicit mesh, boundaries, sampled pole and fixed frequency'],
        not_matched=['no measured material validity, loss target or full-wave propagation'],
        observables=[observable('impedance','ohm','maximum relative difference',error,1e-10)],
        analytical_acceptance='homogeneous Z times sqrt(eps_real) invariant within 1e-10',stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    assert error < 1e-10
