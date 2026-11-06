# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved goal contracts, constraint forwarding and an independent Cohn width."""
import pytest
from scipy.optimize import brentq

from sipi import CrossSection, CrossSectionDocument, GoalSeekError, ImpedanceDesignDocument
from sipi.design import DesignEvaluation
from test_sipi_references import stripline_z0

MESH = dict(edge_size=.5e-6, far_size=.125e-3, grade=.075)


def document(**kw):
    values = dict(variable='width', bounds=[.3e-3, .8e-3], target=50.,
                  tolerance=.2, max_evaluations=20, mesh=MESH)
    values.update(kw)
    return ImpedanceDesignDocument('stripline', dict(width=.5e-3, plane_spacing=1e-3, eps_r=4), **values)


def test_goal_json_replay_matches_independent_cohn_width():
    original = document()
    restored = ImpedanceDesignDocument.loads(original.dumps())
    assert original.dumps() == restored.dumps()
    result = restored.solve()
    expected = brentq(lambda w: stripline_z0(w, 1e-3, 4)-50., .3e-3, .8e-3)
    assert result.parameter == pytest.approx(expected, rel=.01)
    assert abs(result.residual) <= .2 and abs(result.refined_residual) <= .2
    assert result.history[-1].stage == 'refinement'
    assert result.document.section.traces[0].width == result.parameter
    print('saved design width',result.parameter,'Cohn width',expected,
          'residuals',result.residual,result.refined_residual)


def test_parsing_has_no_meshing_or_solver_side_effects(monkeypatch):
    def forbidden(*a, **kw):
        pytest.fail('parsing must not mesh or solve')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    monkeypatch.setattr(CrossSectionDocument, 'analyze', forbidden)
    doc = document()
    assert ImpedanceDesignDocument.loads(doc.dumps()).dumps() == doc.dumps()


def test_input_and_returned_dict_mutations_are_isolated():
    source = document().to_dict()
    doc = ImpedanceDesignDocument.from_dict(source)
    before = doc.dumps()
    source['bounds'][0] = 99
    source['parameters']['eps_r'] = 99
    doc.to_dict()['parameters']['width'] = 99
    assert doc.dumps() == before


@pytest.mark.parametrize('edit', [
    lambda d:d.update(schema='sipi.impedance-design/2'),
    lambda d:d.update(extra=1), lambda d:d.pop('mesh'),
    lambda d:d.pop('fixed_plane_spacing_m'),
    lambda d:d.update(template='eval'), lambda d:d.update(variable='unknown'),
    lambda d:d.update(variable=True), lambda d:d.update(quantity='z_diff'),
    lambda d:d.update(bounds=[0,.8e-3]), lambda d:d.update(bounds=[.8e-3,.3e-3]),
    lambda d:d.update(bounds=[True,.8e-3]), lambda d:d.update(bounds=[.3e-3]),
    lambda d:d.update(bounds='0.3,0.8'), lambda d:d.update(target_ohm=0),
    lambda d:d.update(target_ohm=True), lambda d:d.update(target_ohm=float('nan')),
    lambda d:d.update(tolerance_ohm=-1), lambda d:d.update(tolerance_ohm='0.1'),
    lambda d:d.update(max_evaluations=True), lambda d:d.update(max_evaluations=2),
    lambda d:d.update(max_evaluations=10001), lambda d:d.update(mesh={'edge_size':-1}),
])
def test_invalid_goal_input_is_rejected(edit):
    data = document().to_dict()
    edit(data)
    with pytest.raises(ValueError):
        ImpedanceDesignDocument.from_dict(data)


@pytest.mark.parametrize('text', ['{"schema":1,"schema":2}', '{"x":Infinity}',
                                  '{"x":NaN}', '{"x":{"v":1,"v":2}}'])
def test_json_duplicates_and_nonfinite_numbers_are_rejected(text):
    with pytest.raises(ValueError):
        ImpedanceDesignDocument.loads(text)


@pytest.mark.parametrize('kind', ['pitch', 'plane'])
def test_saved_constraints_and_solve_options_reach_design_engine(monkeypatch, kind):
    parameters = dict(width=.5e-3, gap=.3e-3, lower_height=.4e-3, upper_height=.6e-3,
                      lower_eps_r=2, upper_eps_r=6)
    options = dict(variable='width', bounds=[.3e-3,.6e-3], fixed_pitch_m=.8e-3)
    if kind == 'plane':
        options = dict(variable='lower_height',bounds=[.3e-3,.6e-3],fixed_plane_spacing_m=.001)
    doc = ImpedanceDesignDocument('coupled_layered_stripline',parameters,quantity='z_diff',
                                  target=100,tolerance=.25,max_evaluations=12,mesh=MESH,**options)
    def inspect(factory,bounds,target,**kwargs):
        assert list(bounds) == options['bounds']
        assert target == 100 and kwargs['quantity'] == 'z_diff'
        assert kwargs['tolerance'] == .25 and kwargs['max_evaluations'] == 12
        assert kwargs['mesh'] == doc.to_dict()['mesh']
        for value in bounds:
            section = factory(value)
            if kind == 'pitch':
                assert [t.x for t in section.traces] == pytest.approx([-.4e-3,.4e-3],rel=1e-12)
            else:
                assert section.height == pytest.approx(.001,rel=1e-12)
                assert section.traces[0].y == value
        return 'verified engine boundary'
    monkeypatch.setattr('sipi.design_document.seek_impedance',inspect)
    assert ImpedanceDesignDocument.loads(doc.dumps()).solve() == 'verified engine boundary'


def test_failure_and_completed_history_are_not_replaced(monkeypatch):
    failure = GoalSeekError('controlled failed bracket',[DesignEvaluation(.3e-3,70,'search')])
    def fail(*args,**kwargs):raise failure
    monkeypatch.setattr('sipi.design_document.seek_impedance',fail)
    with pytest.raises(GoalSeekError) as caught:
        document().solve()
    assert caught.value is failure
    assert caught.value.history[0].impedance == 70


def test_unneeded_or_conflicting_constraint_is_rejected():
    with pytest.raises(ValueError,match='fixed plane spacing'):
        document(fixed_plane_spacing_m=.001)
