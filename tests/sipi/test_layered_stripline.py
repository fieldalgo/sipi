# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Two-dielectric geometry and independent symmetric-interface Cohn limits."""
import numpy as np
import pytest
from scipy.optimize import brentq

from sipi import (CrossSection, CrossSectionDocument, Layer, Trace, layered_stripline,
                  coupled_layered_stripline, seek_impedance)
from sipi.study import ImpedanceStudyDocument
from test_sipi_references import stripline_z0, coupled_stripline_z

PARAMS = dict(width=.5e-3, lower_height=.5e-3, upper_height=.5e-3,
              lower_eps_r=2., upper_eps_r=6., box_width=12e-3)
COARSE = dict(edge_size=8e-6, far_size=.25e-3, grade=.3)
FINE = dict(edge_size=.5e-6, far_size=.0625e-3, grade=.075)
FAST = dict(edge_size=10e-6, far_size=.25e-3, grade=.3)
FACTORIES = [layered_stripline, coupled_layered_stripline]


def params(factory, **extra):
    return dict(PARAMS, **({'gap': .3e-3} if factory is coupled_layered_stripline else {}), **extra)


@pytest.mark.parametrize('factory', FACTORIES)
def test_symmetric_interface_matches_independent_cohn_with_convergence(factory):
    # Interface is a symmetry plane of the potential, so the exact capacitance
    # equals vacuum capacitance times the arithmetic mean of the permittivities.
    # This reduction is NOT valid for unequal heights or nonzero metal thickness.
    reference = (np.array(coupled_stripline_z(.5e-3, .3e-3, 1e-3, 4.))
                 if factory is coupled_layered_stripline else np.array([stripline_z0(.5e-3, 1e-3, 4.)]))
    errors, values = [], []
    for mesh in (COARSE, FINE):
        line = factory(**params(factory)).analyze(**mesh)
        z = (np.array([line.even_odd()['z_even'], line.even_odd()['z_odd']])
             if factory is coupled_layered_stripline else np.array([line.z0]))
        values.append(z)
        errors.append(abs(z/reference-1))
    assert np.all(errors[-1] <= .005)
    assert np.all(errors[-1] < errors[0])
    np.testing.assert_allclose(line.C, 4*line.C0, rtol=.003)
    wide = factory(**dict(params(factory), box_width=24e-3)).analyze(**FINE)
    wz = (np.array([wide.even_odd()['z_even'], wide.even_odd()['z_odd']])
          if factory is coupled_layered_stripline else np.array([wide.z0]))
    np.testing.assert_allclose(wz, values[-1], rtol=.002)
    print(factory.__name__, 'reference', reference, 'FEM', values, 'relative errors', errors,
          'expanded', wz, 'eps ratio error', np.max(abs(line.C/(4*line.C0)-1)))


@pytest.mark.parametrize('factory', FACTORIES)
def test_symmetric_interface_loss_matches_dielectric_weighting(factory):
    line = factory(**params(factory, lower_tan_delta=.01, upper_tan_delta=.02)).analyze(**FINE)
    expected = (2*.01+6*.02)/(2+6)
    np.testing.assert_allclose(line.C_loss, expected*line.C, rtol=.003)
    print(factory.__name__, 'loss-ratio error', np.max(abs(line.C_loss/(expected*line.C)-1)))


@pytest.mark.parametrize('factory', FACTORIES)
def test_unequal_heights_finite_taper_and_json_preserve_material_boundary(factory):
    options = dict(params(factory), lower_height=.3e-3, upper_height=.7e-3,
                   thickness=.035e-3, top_width=.4e-3, lower_tan_delta=.01, upper_tan_delta=.02)
    section = factory(**options)
    assert section.height == pytest.approx(1e-3)
    assert [l.name for l in section.layers] == ['lower', 'upper']
    assert [l.eps_r for l in section.layers] == [2, 6]
    assert [l.thickness for l in section.layers] == [.3e-3, .7e-3]
    assert all(t.y == .3e-3 and t.y1 == pytest.approx(.335e-3) for t in section.traces)
    doc = CrossSectionDocument(section, mesh=FAST)
    replay = CrossSectionDocument.loads(doc.dumps())
    assert replay.dumps() == doc.dumps()
    a, b = doc.analyze(), replay.analyze()
    for field in ('C', 'C0', 'C_loss', 'L'):
        np.testing.assert_array_equal(getattr(a, field), getattr(b, field))
    assert np.linalg.eigvalsh(a.C).min() > 0
    assert np.linalg.eigvalsh(a.C_loss).min() > 0


def test_single_factory_matches_explicit_layers_and_trace():
    section = layered_stripline(**PARAMS)
    explicit = CrossSection([Layer('lower', .5e-3, 2), Layer('upper', .5e-3, 6)],
                            [Trace('signal', 0, .5e-3, .5e-3)], 12e-3, top='ground')
    assert CrossSectionDocument(section).dumps() == CrossSectionDocument(explicit).dumps()


@pytest.mark.parametrize('factory', FACTORIES)
@pytest.mark.parametrize('change', [dict(lower_height=0), dict(upper_height=-1), dict(lower_eps_r=.5),
    dict(upper_eps_r=True), dict(lower_tan_delta=-1), dict(upper_tan_delta=float('nan')),
    dict(thickness=.5e-3), dict(box_width=.4e-3), dict(top_width=.6e-3)])
def test_invalid_dimensions_and_materials_are_rejected(factory, change):
    with pytest.raises(ValueError):
        factory(**dict(params(factory), **change))


@pytest.mark.parametrize('factory', FACTORIES)
@pytest.mark.parametrize('kind', ['sweep', 'corners', 'uniform', 'normal'])
def test_layered_studies_replay_independent_material_inputs(factory, kind):
    spec = dict(kind=kind, variables=[dict(name='upper_eps_r', lower=5., upper=7.)])
    if kind != 'corners': spec['count'] = 2
    if kind in ('uniform', 'normal'): spec['seed'] = 711
    if kind == 'normal':
        spec.update(variables=[dict(name='upper_eps_r', mean=6., std=.1)], correlation=[[1]])
    quantity = 'z0' if factory is layered_stripline else 'z_diff'
    plan = ImpedanceStudyDocument(factory.__name__, params(factory), quantity=quantity,
                                  sampling=spec, mesh=FAST)
    replay = ImpedanceStudyDocument.loads(plan.dumps())
    assert plan.dumps() == replay.dumps()
    np.testing.assert_array_equal(plan.samples(), replay.samples())
    if kind == 'sweep':
        result = replay.analyze()
        assert result.failed == 0 and result.summary is not None
        assert result.rows[1].impedance < result.rows[0].impedance
        assert all(row.parameters['lower_eps_r'] == 2 for row in result.rows)


def test_layered_pair_fixed_pitch_and_quantity():
    spec = dict(kind='sweep', count=2, variables=[dict(name='width', lower=.4e-3, upper=.6e-3)])
    plan = ImpedanceStudyDocument('coupled_layered_stripline', params(coupled_layered_stripline),
                                   sampling=spec, quantity='z_diff', fixed_pitch_m=.8e-3)
    for values in plan.sample_parameters():
        section = coupled_layered_stripline(**values)
        np.testing.assert_allclose([t.x for t in section.traces], [-.4e-3, .4e-3], rtol=1e-15)
    with pytest.raises(ValueError, match='quantity=z_diff'):
        ImpedanceStudyDocument('coupled_layered_stripline', params(coupled_layered_stripline),
                               sampling=spec, quantity='z0')


def test_invalid_unbounded_material_samples_remain_failed_rows():
    plan = ImpedanceStudyDocument('layered_stripline', PARAMS, quantity='z0', mesh=FAST,
        sampling=dict(kind='normal', count=2, seed=13, correlation=[[1]],
                      variables=[dict(name='upper_eps_r', mean=.5, std=.001)]))
    result = plan.analyze()
    assert result.failed == 2 and result.summary is None
    assert all(row.document is None and row.error_type == 'ValueError' for row in result.rows)


def test_layered_width_goal_matches_cohn_at_symmetric_interface():
    target = 50.
    expected = brentq(lambda w: stripline_z0(w, 1e-3, 4.)-target, .3e-3, .8e-3)
    result = seek_impedance(lambda w: layered_stripline(**dict(PARAMS, width=w)),
                            (.3e-3, .8e-3), target, tolerance=.2, mesh=FINE)
    assert result.parameter == pytest.approx(expected, rel=.01)
    assert abs(result.residual) <= .2 and abs(result.refined_residual) <= .2
    print('design', result.parameter, 'reference width', expected,
          'residuals', result.residual, result.refined_residual)
