# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Stripline study contracts and the homogeneous-dielectric impedance scaling law."""
import numpy as np
import pytest
from sipi import templates
from sipi.study import ImpedanceStudyDocument

MESH = dict(edge_size=.1e-3, far_size=.4e-3, grade=.3)
CASES = [
    ('offset_stripline', dict(width=.4e-3, plane_spacing=1e-3, trace_height=.35e-3,
                             eps_r=4), 'z0'),
    ('coupled_stripline', dict(width=.4e-3, gap=.3e-3, plane_spacing=1e-3,
                              eps_r=4), 'z_diff'),
    ('broadside_stripline', dict(width=.4e-3, gap=.2e-3, plane_spacing=1e-3,
                                thickness=.1e-3, eps_r=4), 'z_diff'),
]


def sampling(kind='sweep'):
    variables = [dict(name='width', lower=.3e-3, upper=.5e-3)]
    out = dict(kind=kind, variables=variables)
    if kind != 'corners':
        out['count'] = 2
    if kind in ('normal', 'uniform'):
        out['seed'] = 128
    if kind == 'normal':
        out['variables'] = [dict(name='width', mean=.4e-3, std=.01e-3)]
        out['correlation'] = [[1]]
    return out


@pytest.mark.parametrize('name,params,quantity', CASES)
@pytest.mark.parametrize('kind', ['sweep', 'corners', 'uniform', 'normal'])
def test_new_templates_replay_all_sampling_modes(name, params, quantity, kind):
    doc = ImpedanceStudyDocument(name, params, quantity=quantity, sampling=sampling(kind), mesh=MESH)
    replay = ImpedanceStudyDocument.loads(doc.dumps())
    assert replay.dumps() == doc.dumps()
    np.testing.assert_array_equal(replay.samples(), doc.samples())
    for values in replay.sample_parameters():
        assert len(getattr(templates, name)(**values).traces) == (1 if quantity == 'z0' else 2)


@pytest.mark.parametrize('name,params,quantity', CASES)
def test_homogeneous_dielectric_impedance_scaling(name, params, quantity):
    spec = dict(kind='sweep', count=2, variables=[dict(name='eps_r', lower=1., upper=4.)])
    doc = ImpedanceStudyDocument(name, params, quantity=quantity, sampling=spec, mesh=MESH)
    result = ImpedanceStudyDocument.loads(doc.dumps()).analyze()
    assert result.failed == 0
    assert result.summary is not None
    assert result.rows[0].impedance / result.rows[1].impedance == pytest.approx(2., rel=1e-9)
    assert all(row.document is not None and row.impedance > 0 for row in result.rows)


def test_edge_coupled_stripline_fixed_pitch_preserves_centres():
    name, params, quantity = CASES[1]
    doc = ImpedanceStudyDocument(name, params, quantity=quantity, sampling=sampling(),
                                 mesh=MESH, fixed_pitch_m=.7e-3)
    for values in doc.sample_parameters():
        traces = templates.coupled_stripline(**values).traces
        assert [t.x for t in traces] == pytest.approx([-.35e-3, .35e-3])
        assert values['gap'] == pytest.approx(.7e-3-values['width'])


def test_broadside_vertical_gap_is_not_a_horizontal_fixed_pitch():
    name, params, quantity = CASES[2]
    with pytest.raises(ValueError, match='fixed pitch'):
        ImpedanceStudyDocument(name, params, quantity=quantity, sampling=sampling(),
                                mesh=MESH, fixed_pitch_m=.6e-3)


@pytest.mark.parametrize('name,params,quantity', CASES)
def test_incorrect_quantity_is_rejected(name, params, quantity):
    with pytest.raises(ValueError, match='quantity'):
        ImpedanceStudyDocument(name, params, quantity='z_diff' if quantity == 'z0' else 'z0',
                                sampling=sampling(), mesh=MESH)


@pytest.mark.parametrize('case,variable', [(0, 'trace_height'), (2, 'gap')])
def test_bounds_crossing_ground_are_rejected_before_solving(case, variable):
    name, params, quantity = CASES[case]
    spec = dict(kind='sweep', count=2, variables=[dict(name=variable, lower=.3e-3, upper=2e-3)])
    with pytest.raises(ValueError):
        ImpedanceStudyDocument(name, params, quantity=quantity, sampling=spec, mesh=MESH)
