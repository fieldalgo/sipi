# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Unequal bottom widths at a fixed physical centre-to-centre distance."""
import numpy as np
import pytest

from sipi import asymmetric_coupled_microstrip, CrossSection, ImpedanceDesignDocument
from sipi.study import ImpedanceStudyDocument
from sipi.dielectric import ConstantDielectric

PARAMS = dict(left_width=.4e-3, right_width=.65e-3, gap=.25e-3,
    substrate_height=.5e-3, eps_r=4, left_thickness=35e-6, right_thickness=50e-6,
    left_top_width=.32e-3, right_top_width=.55e-3, tan_delta=.02,
    air_height=6e-3, box_width=12e-3)
PITCH = .775e-3
MESH = dict(edge_size=2e-6, far_size=.125e-3, grade=.1)


def sampling(kind='sweep', widths=('left_width',)):
    variables = [dict(name=n, lower=PARAMS[n]*.9, upper=PARAMS[n]*1.1) for n in widths]
    spec = dict(kind=kind, variables=variables)
    if kind != 'corners': spec['count'] = 4
    if kind in ('uniform', 'normal'): spec['seed'] = 93
    if kind == 'normal':
        spec['variables'] = [dict(name=n, mean=PARAMS[n], std=PARAMS[n]*.01) for n in widths]
        spec['correlation'] = (np.eye(len(widths))*.3+np.ones((len(widths),len(widths)))*.7).tolist()
    return spec


def document(spec=None, **kwargs):
    return ImpedanceStudyDocument('asymmetric_coupled_microstrip', PARAMS,
        sampling=sampling() if spec is None else spec, quantity='z_diff_forward',
        fixed_pitch_m=PITCH, mesh=MESH, **kwargs)


@pytest.mark.parametrize('kind', ['sweep','corners','uniform','normal'])
@pytest.mark.parametrize('width', ['left_width','right_width'])
def test_one_width_sampling_preserves_physical_pitch_and_replay(kind, width):
    plan = document(sampling(kind, (width,)))
    restored = ImpedanceStudyDocument.loads(plan.dumps())
    assert restored.dumps() == plan.dumps()
    np.testing.assert_array_equal(plan.samples(), restored.samples())
    for row, params in zip(restored.samples(), restored.sample_parameters()):
        assert params[width] == row[0]
        assert params['gap'] == pytest.approx(PITCH-(params['left_width']+params['right_width'])/2, rel=1e-12)
        pair = asymmetric_coupled_microstrip(**params)
        assert pair.traces[1].x-pair.traces[0].x == pytest.approx(PITCH, rel=1e-12)
    # Keeping distance does not fix the common centre: the bottom span is centred.
    centres = [sum(t.x for t in asymmetric_coupled_microstrip(**p).traces)/2 for p in plan.sample_parameters()]
    assert np.ptp(centres) > 0
    changed = restored.sample_parameters(); changed[0]['gap'] = 9
    assert restored.dumps() == plan.dumps() and restored.sample_parameters()[0]['gap'] != 9


@pytest.mark.parametrize('kind', ['corners','uniform','normal'])
def test_both_widths_and_thickness_compose(kind):
    plan = document(sampling(kind, ('left_width','right_width','left_thickness')))
    for values, params in zip(plan.samples(),plan.sample_parameters()):
        np.testing.assert_array_equal(values, [params[n] for n in ('left_width','right_width','left_thickness')])
        pair = asymmetric_coupled_microstrip(**params)
        assert pair.traces[1].x-pair.traces[0].x == pytest.approx(PITCH,rel=1e-12)
    assert ImpedanceStudyDocument.loads(plan.dumps()).dumps() == plan.dumps()


@pytest.mark.parametrize('edit', [
    lambda d: d.update(fixed_pitch_m=.8e-3),
    lambda d: d.update(fixed_pitch_m=0),
    lambda d: d.update(fixed_pitch_m=True),
    lambda d: d['sampling']['variables'][0].update(name='gap'),
    lambda d: d['sampling']['variables'][0].update(name='left_thickness'),
    lambda d: d['sampling'].update(kind='corners', variables=[
        dict(name='left_width',lower=.35e-3,upper=.45e-3),dict(name='gap',lower=.2e-3,upper=.3e-3)]),
    lambda d: d['sampling']['variables'][0].update(upper=1e-3),
])
def test_invalid_constraint_or_nonpositive_corner_gap_rejected_before_mesh(edit,monkeypatch):
    data = document().to_dict(); edit(data)
    def forbidden(*a,**k): pytest.fail('invalid bounded input reached meshing')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    with pytest.raises(ValueError): ImpedanceStudyDocument.from_dict(data)


def test_negative_normal_gap_is_retained_as_failed_row_without_mesh(monkeypatch):
    spec = sampling('normal'); spec['variables'][0].update(mean=1.1e-3,std=1e-8)
    plan = document(spec)
    def forbidden(*a,**k): pytest.fail('negative derived gap reached meshing')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    result = plan.analyze(max_evaluations=4)
    assert result.failed == 4 and result.summary is None
    for values,row in zip(plan.samples(),result.rows):
        assert row.parameters['left_width'] == values[0] and row.parameters['gap'] < 0
        assert row.error_type == 'ValueError' and row.document is None


def test_material_saved_study_replays_derived_geometry():
    spec = sampling(); spec['count'] = 2
    plan = document(spec, frequency=1e9, materials={'substrate':ConstantDielectric(4,.02)})
    restored = ImpedanceStudyDocument.loads(plan.dumps())
    assert restored.to_dict()['schema'] == 'sipi.impedance-study/3'
    result = restored.analyze(max_evaluations=2)
    assert result.failed == 0 and result.input_json == plan.dumps()
    for row in result.rows:
        pair = row.document.section
        assert pair.traces[1].x-pair.traces[0].x == pytest.approx(PITCH,rel=1e-12)


def test_saved_forward_goal_checks_requested_and_refined_mesh_at_fixed_pitch():
    goal = ImpedanceDesignDocument('asymmetric_coupled_microstrip',PARAMS,
        variable='left_width',bounds=[.3e-3,.8e-3],target=100,quantity='z_diff_forward',
        tolerance=1,mesh=MESH,fixed_pitch_m=PITCH)
    restored = ImpedanceDesignDocument.loads(goal.dumps())
    assert restored.dumps() == goal.dumps()
    result = restored.solve()
    pair = result.document.section
    assert pair.traces[1].x-pair.traces[0].x == pytest.approx(PITCH,rel=1e-12)
    assert abs(result.residual) <= 1 and abs(result.refined_residual) <= 1
    print('unequal fixed-pitch goal',result.parameter,result.residual,result.refined_residual)
