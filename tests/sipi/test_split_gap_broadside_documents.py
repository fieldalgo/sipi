# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved split-gap materials, interface sampling and a refined forward goal."""
import numpy as np
import pytest
from sipi import CrossSection, ImpedanceDesignDocument, seek_impedance
from sipi.template_document import TemplateSectionDocument
from sipi.study import ImpedanceStudyDocument
from sipi.execution import normalize_saved, execute_saved
from test_split_gap_broadside import PARAMS, COARSE, section

NAME = 'split_gap_broadside_stripline'


def study(kind='sweep', **changes):
    sampling = dict(kind=kind, variables=[dict(name='lower_top_width', lower=.31e-3, upper=.33e-3)])
    if kind != 'corners':
        sampling['count'] = 2
    if kind in ('uniform', 'normal'):
        sampling['seed'] = 73
    if kind == 'normal':
        sampling.update(variables=[dict(name='lower_top_width', mean=.32e-3, std=.005e-3)],
                        correlation=[[1.]])
    return ImpedanceStudyDocument(NAME, PARAMS, **dict(
        dict(quantity='z_diff_forward', mesh=COARSE, sampling=sampling), **changes))


def assert_geometry(s, p):
    low, high = s.traces
    assert (low.name, high.name) == ('positive', 'negative')
    assert (low.x, high.x) == (-p['offset']/2, p['offset']/2)
    assert low.y == p['lower_height']
    assert high.y-low.y1 == pytest.approx(p['gap'], rel=1e-12)
    assert s.height-high.y1 == pytest.approx(p['upper_height'], rel=1e-12)
    assert s.layers[1].thickness == p['gap_lower_height']
    assert s.layers[2].thickness == p['gap']-p['gap_lower_height']
    assert [l.eps_r for l in s.layers] == [p[k+'_eps_r'] for k in ('lower', 'gap_lower', 'gap_upper', 'upper')]
    assert [l.tan_delta for l in s.layers] == [p[k+'_tan_delta'] for k in ('lower', 'gap_lower', 'gap_upper', 'upper')]
    for t, key in zip(s.traces, ('lower', 'upper')):
        assert t.top_width == p[key+'_top_width']
        np.testing.assert_allclose(t.corners()[2:, 0],
            [t.x+p[key+'_top_width']/2, t.x-p[key+'_top_width']/2], rtol=1e-14, atol=0)


def test_editable_and_sampling_documents_roundtrip_without_field_solves(monkeypatch):
    monkeypatch.setattr(CrossSection, 'mesh', lambda *a, **k: pytest.fail('Input preparation meshed'))
    editable = TemplateSectionDocument(NAME, PARAMS, mesh=COARSE)
    assert normalize_saved(editable.dumps()) == editable.dumps()
    assert TemplateSectionDocument.loads(editable.dumps()).dumps() == editable.dumps()
    for kind in ('sweep', 'corners', 'uniform', 'normal'):
        doc = study(kind)
        assert normalize_saved(doc.dumps()) == doc.dumps()
        assert ImpedanceStudyDocument.loads(doc.dumps()).dumps() == doc.dumps()


def test_uniform_top_width_keeps_bottom_width_gap_and_clearances():
    rows = study('uniform').sample_parameters()
    expected = .31e-3+.02e-3*np.random.Generator(np.random.PCG64(73)).random((2, 1))[:, 0]
    np.testing.assert_array_equal([r['lower_top_width'] for r in rows], expected)
    for p in rows:
        assert p['lower_width'] == PARAMS['lower_width']
        assert p['upper_top_width'] == PARAMS['upper_top_width']
        assert p['gap'] == PARAMS['gap']
        assert_geometry(section(**p), p)


@pytest.mark.parametrize('quantity', ['z_diff', 'z0', 'z_common'])
def test_inapplicable_symmetric_quantities_rejected(quantity):
    with pytest.raises(ValueError, match='requires quantity'):
        study(quantity=quantity)


def test_horizontal_pitch_and_two_layer_plane_constraint_remain_inapplicable():
    with pytest.raises(ValueError, match='fixed pitch'):
        study(fixed_pitch_m=.001)
    with pytest.raises(ValueError, match='fixed plane spacing'):
        study(fixed_plane_spacing_m=.00122, sampling=dict(kind='sweep', count=2,
              variables=[dict(name='lower_height', lower=.3e-3, upper=.4e-3)]))


def test_correlated_bottom_top_widths_match_reference_samples_and_common_execution():
    doc = study(sampling=dict(kind='normal', count=3, seed=74, correlation=[[1., .6], [.6, 1.]],
        variables=[dict(name='lower_width', mean=.4e-3, std=.005e-3),
                   dict(name='lower_top_width', mean=.32e-3, std=.003e-3)]))
    a, b = (np.sqrt(1.6)+np.sqrt(.4))/2, (np.sqrt(1.6)-np.sqrt(.4))/2
    root = np.array([[a, b], [b, a]])
    expected = np.array([.4e-3, .32e-3]) + (
        np.random.Generator(np.random.PCG64(74)).standard_normal((3, 2))@root.T)*[.005e-3, .003e-3]
    np.testing.assert_allclose(doc.samples(), expected, rtol=1e-14, atol=0)
    result = doc.analyze()
    assert result.failed == 0 and len(result.rows) == 3
    for row in result.rows:
        assert_geometry(row.document.section, row.parameters)
        assert row.impedance == section(**row.parameters).analyze(**COARSE).z_diff_forward
    common = execute_saved(doc.dumps(), max_evaluations=3)
    assert common['status'] == 'complete'
    assert [r['value'] for r in common['result']['rows']] == [r.impedance for r in result.rows]


def test_invalid_normal_top_width_retained_before_meshing(monkeypatch):
    doc = study(sampling=dict(kind='normal', count=2, seed=74, correlation=[[1.]],
        variables=[dict(name='upper_top_width', mean=-.55e-3, std=1e-12)]))
    monkeypatch.setattr(CrossSection, 'mesh', lambda *a, **k: pytest.fail('Invalid etch face was meshed'))
    result = doc.analyze()
    assert result.failed == 2 and result.summary is None
    assert all(r.document is None and r.error_type == 'ValueError' and r.parameters['upper_top_width'] < 0
               for r in result.rows)


def test_gap_material_sweep_keeps_faces_and_replays_common_executor():
    doc = study(sampling=dict(kind='sweep', count=2,
        variables=[dict(name='gap_lower_eps_r', lower=3.5, upper=4.5)]))
    result = doc.analyze()
    assert result.failed == 0 and result.rows[1].impedance < result.rows[0].impedance
    for row in result.rows:
        assert_geometry(row.document.section, row.parameters)
    common = execute_saved(doc.dumps())
    assert common['status'] == 'complete'
    assert [r['value'] for r in common['result']['rows']] == [r.impedance for r in result.rows]


def test_saved_top_width_goal_preserves_history_and_separate_half_mesh(record_property):
    doc = ImpedanceDesignDocument(NAME, PARAMS, variable='lower_top_width', bounds=[.3e-3, .65e-3],
        target=50., quantity='z_diff_forward', mesh=COARSE, tolerance=.5, search_tolerance=.05)
    assert normalize_saved(doc.dumps()) == doc.dumps()
    result = ImpedanceDesignDocument.loads(doc.dumps()).solve()
    direct = seek_impedance(lambda width: section(lower_top_width=width), [.3e-3, .65e-3], 50.,
        quantity='z_diff_forward', mesh=COARSE, tolerance=.5, search_tolerance=.05)
    assert [vars(v) for v in result.history] == [vars(v) for v in direct.history]
    assert result.refined_impedance == direct.refined_impedance
    assert result.history[-1].stage == 'refinement'
    assert abs(result.residual) <= .5 and abs(result.refined_residual) <= .5
    assert_geometry(result.document.section, dict(PARAMS, lower_top_width=result.parameter))

    record_property('goal_summary', str(dict(parameter=result.parameter, impedance=result.impedance,
        refined_impedance=result.refined_impedance, residual=result.residual,
        refined_residual=result.refined_residual)))


def test_interface_sweep_preserves_gap_materials_and_matches_common_executor():
    doc = study(sampling=dict(kind='sweep', count=2,
        variables=[dict(name='gap_lower_height', lower=.08e-3, upper=.12e-3)]))
    result = doc.analyze()
    assert result.failed == 0
    # Extending the lower-permittivity gap region increases forward impedance.
    assert result.rows[1].impedance > result.rows[0].impedance
    for row in result.rows:
        assert_geometry(row.document.section, row.parameters)
        assert row.parameters['gap'] == PARAMS['gap']
        assert row.impedance == section(**row.parameters).analyze(**COARSE).z_diff_forward
    common = execute_saved(doc.dumps(), max_evaluations=2)
    assert [r['value'] for r in common['result']['rows']] == [r.impedance for r in result.rows]


def test_outside_gap_normal_samples_are_retained_before_meshing(monkeypatch):
    doc = study(sampling=dict(kind='normal', count=2, seed=75, correlation=[[1.]],
        variables=[dict(name='gap_lower_height', mean=.3e-3, std=1e-12)]))
    monkeypatch.setattr(CrossSection, 'mesh', lambda *a, **k: pytest.fail('Invalid interface was meshed'))
    result = doc.analyze()
    assert result.failed == 2 and result.summary is None
    assert all(r.document is None and r.error_type == 'ValueError'
               and r.parameters['gap_lower_height'] > r.parameters['gap'] for r in result.rows)
