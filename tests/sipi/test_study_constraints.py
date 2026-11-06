# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Fixed stack height, derived geometry, strict schemas and legacy serialization."""
from pathlib import Path
import numpy as np
import pytest

from sipi import CrossSectionDocument
from sipi.study import ImpedanceStudyDocument
from sipi.templates import layered_stripline, coupled_layered_stripline

PARAMS = dict(width=.5e-3, lower_height=.4e-3, upper_height=.6e-3,
              lower_eps_r=2., upper_eps_r=6., thickness=.035e-3, box_width=6e-3)
MESH = dict(edge_size=10e-6, far_size=.25e-3, grade=.3)


def sampling(kind='sweep', variable='lower_height'):
    spec = dict(kind=kind, variables=[dict(name=variable, lower=.3e-3, upper=.7e-3)])
    if kind != 'corners': spec['count'] = 2
    if kind in ('uniform', 'normal'): spec['seed'] = 131
    if kind == 'normal':
        spec.update(variables=[dict(name=variable, mean=.5e-3, std=.02e-3)], correlation=[[1]])
    return spec


def document(pair=False, spec=None, **kw):
    args = dict(PARAMS)
    if pair: args['gap'] = .3e-3
    return ImpedanceStudyDocument('coupled_layered_stripline' if pair else 'layered_stripline',
        args, quantity='z_diff' if pair else 'z0', sampling=sampling() if spec is None else spec,
        mesh=MESH, fixed_plane_spacing_m=.001, **kw)


def test_legacy_canonical_v1_is_byte_preserved():
    # Captured from f4115ee before introducing v2; this is an input format fixture,
    # not regenerated numerical reference data.
    text = (Path(__file__).parent/'fixtures/impedance-study-v1.json').read_text().rstrip('\n')
    assert ImpedanceStudyDocument.loads(text).dumps() == text
    data = ImpedanceStudyDocument.loads(text).to_dict()
    again = ImpedanceStudyDocument(data['template'], data['parameters'], quantity=data['quantity'],
        sampling=data['sampling'], mesh=data['mesh'], fixed_pitch_m=None, fixed_plane_spacing_m=None)
    assert again.dumps() == text
    assert 'fixed_plane_spacing_m' not in data


@pytest.mark.parametrize('pair', [False, True])
@pytest.mark.parametrize('variable', ['lower_height', 'upper_height'])
@pytest.mark.parametrize('kind', ['sweep', 'corners', 'uniform', 'normal'])
def test_v2_replays_all_sampling_modes_and_preserves_total_height(pair, variable, kind):
    plan = document(pair, sampling(kind, variable))
    replay = ImpedanceStudyDocument.loads(plan.dumps())
    assert replay.dumps() == plan.dumps()
    assert replay.to_dict()['schema'] == 'sipi.impedance-study/2'
    np.testing.assert_array_equal(replay.samples(), plan.samples())
    factory = coupled_layered_stripline if pair else layered_stripline
    for sampled, params in zip(replay.samples()[:, 0], replay.sample_parameters()):
        assert params[variable] == sampled
        assert params['lower_height']+params['upper_height'] == pytest.approx(.001, rel=1e-12)
        section = factory(**params)
        assert section.height == pytest.approx(.001, rel=1e-12)
        assert all(t.y1 < section.height for t in section.traces)


def test_fixed_pitch_and_plane_spacing_compose_independently():
    spec = sampling('corners')
    spec['variables'].append(dict(name='width', lower=.4e-3, upper=.6e-3))
    plan = document(True, spec, fixed_pitch_m=.8e-3)
    assert plan.samples().shape == (4, 2)
    for params in plan.sample_parameters():
        section = coupled_layered_stripline(**params)
        np.testing.assert_allclose([t.x for t in section.traces], [-.4e-3, .4e-3], rtol=1e-12)
        assert section.height == pytest.approx(.001, rel=1e-12)


@pytest.mark.parametrize('pair', [False, True])
def test_actual_fixed_height_analysis_matches_saved_cross_sections(pair):
    result = document(pair).analyze()
    assert result.failed == 0 and result.summary is not None
    for row in result.rows:
        saved = CrossSectionDocument.loads(row.document.dumps())
        assert saved.section.height == pytest.approx(.001, rel=1e-12)
        line = saved.analyze()
        expected = line.even_odd()['z_diff'] if pair else line.z0
        assert row.impedance == pytest.approx(expected, rel=1e-10)


def test_v2_null_constraint_roundtrips_without_silent_version_change():
    data = document().to_dict()
    data['fixed_plane_spacing_m'] = None
    plan = ImpedanceStudyDocument.from_dict(data)
    assert plan.to_dict()['schema'] == 'sipi.impedance-study/2'
    assert plan.to_dict()['fixed_plane_spacing_m'] is None
    assert plan.sample_parameters()[0]['upper_height'] == .6e-3
    assert ImpedanceStudyDocument.loads(plan.dumps()).dumps() == plan.dumps()


@pytest.mark.parametrize('edit', [
    lambda d: d.update(schema='sipi.impedance-study/1'),
    lambda d: d.update(schema='sipi.impedance-study/3'),
    lambda d: d.pop('fixed_plane_spacing_m'),
    lambda d: d.update(unknown=1),
    lambda d: d.update(fixed_plane_spacing_m=True),
    lambda d: d.update(fixed_plane_spacing_m=0),
    lambda d: d.update(fixed_plane_spacing_m=.002),
    lambda d: d['sampling']['variables'][0].update(name='width'),
    lambda d: d['sampling'].update(kind='corners',variables=[
        dict(name='lower_height',lower=.3e-3,upper=.7e-3),
        dict(name='upper_height',lower=.3e-3,upper=.7e-3)]),
])
def test_invalid_v2_contract_is_rejected(edit):
    data = document().to_dict()
    edit(data)
    with pytest.raises(ValueError):
        ImpedanceStudyDocument.from_dict(data)


def test_two_independent_heights_are_rejected_for_valid_corners_object():
    spec = dict(kind='corners', variables=[dict(name=n, lower=.3e-3, upper=.7e-3)
                                         for n in ('lower_height', 'upper_height')])
    with pytest.raises(ValueError, match='exactly one sampled layer height'):
        document(spec=spec)


def test_constraint_is_rejected_for_other_templates():
    with pytest.raises(ValueError, match='fixed plane spacing'):
        ImpedanceStudyDocument('microstrip',dict(width=.5e-3,substrate_height=.5e-3,eps_r=4),
            quantity='z0', fixed_plane_spacing_m=.001,
            sampling=dict(kind='sweep', count=2, variables=[dict(name='substrate_height',lower=.3e-3,upper=.7e-3)]))


@pytest.mark.parametrize('variable', ['lower_height', 'upper_height'])
def test_bounded_derived_layer_or_copper_contact_is_rejected(variable):
    spec = sampling(variable=variable)
    spec['variables'][0]['upper'] = .99e-3 if variable == 'lower_height' else 1.1e-3
    with pytest.raises(ValueError):
        document(spec=spec)


def test_invalid_normal_derived_height_is_retained_without_resampling():
    spec = sampling('normal')
    spec['variables'][0].update(mean=1.1e-3, std=1e-8)
    plan = document(spec=spec)
    rows = plan.analyze()
    assert rows.failed == 2 and rows.summary is None
    for sample, row in zip(plan.samples()[:, 0], rows.rows):
        assert row.parameters['lower_height'] == sample
        assert row.parameters['upper_height'] < 0
        assert row.error_type == 'ValueError' and row.document is None
