# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved unequal broadside inputs preserve copper, clearances and forward goals."""
import numpy as np
import pytest
from sipi import CrossSection, ImpedanceDesignDocument, seek_impedance
from sipi.template_document import TemplateSectionDocument
from sipi.study import ImpedanceStudyDocument
from sipi.execution import normalize_saved, execute_saved
from test_asymmetric_broadside import PARAMS, COARSE, section

NAME = 'asymmetric_layered_broadside_stripline'


def study(kind='sweep', **changes):
    sampling = dict(kind=kind, variables=[dict(name='lower_width', lower=.39e-3, upper=.41e-3)])
    if kind != 'corners':
        sampling['count'] = 2
    if kind in ('uniform', 'normal'):
        sampling['seed'] = 73
    if kind == 'normal':
        sampling.update(variables=[dict(name='lower_width', mean=.4e-3, std=.005e-3)], correlation=[[1.]])
    opts = dict(quantity='z_diff_forward', mesh=COARSE, sampling=sampling)
    opts.update(changes)
    return ImpedanceStudyDocument(NAME, PARAMS, **opts)


def assert_geometry(s, p):
    low, high = s.traces
    assert (low.name, high.name) == ('positive', 'negative')
    assert (low.width, high.width) == (p['lower_width'], p['upper_width'])
    assert (low.thickness, high.thickness) == (p['lower_thickness'], p['upper_thickness'])
    assert (low.x, high.x) == (-p['offset']/2, p['offset']/2)
    assert low.y == p['lower_height']
    assert high.y-low.y1 == pytest.approx(p['gap'], rel=1e-12)
    assert s.height-high.y1 == pytest.approx(p['upper_height'], rel=1e-12)
    assert [l.eps_r for l in s.layers] == [p['lower_eps_r'], p['gap_eps_r'], p['upper_eps_r']]
    assert s.top == s.bottom == 'ground' and s.sides == 'open'


def test_template_and_all_sampling_inputs_roundtrip_without_solving(monkeypatch):
    monkeypatch.setattr(CrossSection, 'mesh', lambda *a, **k: pytest.fail('Input preparation solved fields'))
    doc = TemplateSectionDocument(NAME, PARAMS, mesh=COARSE)
    assert normalize_saved(doc.dumps()) == doc.dumps()
    assert TemplateSectionDocument.loads(doc.dumps()).dumps() == doc.dumps()
    assert_geometry(doc.cross_section.section, PARAMS)
    for kind in ('sweep', 'corners', 'uniform', 'normal'):
        sample = study(kind)
        assert normalize_saved(sample.dumps()) == sample.dumps()
        assert ImpedanceStudyDocument.loads(sample.dumps()).sample_parameters() == sample.sample_parameters()


def test_uniform_lower_width_uses_explicit_pcg64_without_changing_gap_or_upper_copper():
    doc = study('uniform')
    expected = np.random.Generator(np.random.PCG64(73)).uniform([.39e-3], [.41e-3], size=(2, 1))[:, 0]
    rows = doc.sample_parameters()
    np.testing.assert_array_equal([p['lower_width'] for p in rows], expected)
    for p in rows:
        assert p['gap'] == PARAMS['gap'] and p['upper_width'] == PARAMS['upper_width']
        assert p['upper_thickness'] == PARAMS['upper_thickness']
        assert_geometry(section(**p), p)


@pytest.mark.parametrize('quantity', ['z_diff', 'z0', 'z_common'])
def test_inapplicable_symmetry_objectives_are_rejected(quantity):
    with pytest.raises(ValueError, match='requires quantity'):
        study(quantity=quantity)


def test_horizontal_pitch_and_two_layer_plane_constraint_are_not_reinterpreted():
    with pytest.raises(ValueError, match='fixed pitch'):
        study(fixed_pitch_m=.001)
    with pytest.raises(ValueError, match='fixed plane spacing'):
        study(fixed_plane_spacing_m=.00122, sampling=dict(kind='sweep', count=2,
              variables=[dict(name='lower_height', lower=.3e-3, upper=.4e-3)]))


def test_correlated_width_and_upper_thickness_preserve_actual_rows_and_common_execution():
    doc = study(sampling=dict(kind='normal', count=3, seed=74, correlation=[[1., .6], [.6, 1.]],
        variables=[dict(name='lower_width', mean=.4e-3, std=.005e-3),
                   dict(name='upper_thickness', mean=45e-6, std=1e-6)]))
    # Closed-form positive square root for the specified 2x2 correlation.
    a, b = (np.sqrt(1.6)+np.sqrt(.4))/2, (np.sqrt(1.6)-np.sqrt(.4))/2
    root = np.array([[a, b], [b, a]])
    expected = np.array([.4e-3, 45e-6]) + (
        np.random.Generator(np.random.PCG64(74)).standard_normal((3, 2))@root.T)*[.005e-3, 1e-6]
    np.testing.assert_allclose(doc.samples(), expected, rtol=1e-14, atol=0)
    result = doc.analyze()
    assert result.failed == 0 and len(result.rows) == 3
    for row in result.rows:
        assert_geometry(row.document.section, row.parameters)
        direct = section(**row.parameters).analyze(**COARSE)
        assert row.impedance == direct.z_diff_forward
    common = execute_saved(doc.dumps(), max_evaluations=3)
    assert common['status'] == 'complete'
    assert [r['value'] for r in common['result']['rows']] == [r.impedance for r in result.rows]


def test_invalid_normal_upper_thickness_keeps_failed_rows_before_meshing(monkeypatch):
    doc = study(sampling=dict(kind='normal', count=2, seed=74, correlation=[[1.]],
        variables=[dict(name='upper_thickness', mean=-45e-6, std=1e-12)]))
    monkeypatch.setattr(CrossSection, 'mesh', lambda *a, **k: pytest.fail('Invalid copper was meshed'))
    result = doc.analyze()
    assert result.failed == 2 and result.summary is None
    assert all(r.document is None and r.error_type == 'ValueError' and r.parameters['upper_thickness'] < 0
               for r in result.rows)


def test_gap_material_sweep_replays_common_executor_with_unchanged_copper():
    doc = study(sampling=dict(kind='sweep', count=2,
        variables=[dict(name='gap_eps_r', lower=3.5, upper=4.5)]))
    result = doc.analyze()
    assert result.failed == 0 and result.rows[1].impedance < result.rows[0].impedance
    for row in result.rows:
        assert_geometry(row.document.section, row.parameters)
    common = execute_saved(doc.dumps())
    assert common['status'] == 'complete'
    assert [r['value'] for r in common['result']['rows']] == [r.impedance for r in result.rows]


def test_saved_lower_width_goal_replays_direct_history_and_separate_half_mesh():
    doc = ImpedanceDesignDocument(NAME, PARAMS, variable='lower_width', bounds=[.2e-3, .8e-3],
        target=50., quantity='z_diff_forward', mesh=COARSE, tolerance=.5, search_tolerance=.05)
    assert normalize_saved(doc.dumps()) == doc.dumps()
    result = ImpedanceDesignDocument.loads(doc.dumps()).solve()
    direct = seek_impedance(lambda width: section(lower_width=width), [.2e-3, .8e-3], 50.,
        quantity='z_diff_forward', mesh=COARSE, tolerance=.5, search_tolerance=.05)
    assert [vars(v) for v in result.history] == [vars(v) for v in direct.history]
    assert result.refined_impedance == direct.refined_impedance
    assert result.history[-1].stage == 'refinement'
    assert abs(result.residual) <= .5 and abs(result.refined_residual) <= .5
    assert_geometry(result.document.section, dict(PARAMS, lower_width=result.parameter))
