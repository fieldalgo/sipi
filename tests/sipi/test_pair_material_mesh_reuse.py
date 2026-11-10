# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Mesh reuse must not change pair objectives, attempt budgets or failures."""
import json
from types import SimpleNamespace

import numpy as np
import pytest
from meshine import MeshSizeLimitError

import sipi.crosssection as crosssection
import sipi.dielectric as dielectric
import sipi.pair_design as module
from sipi import CrossSection, CrossSectionDocument, PairImpedanceGoalError, seek_pair_impedances
from sipi.dielectric import ConstantDielectric, PrincipalAxisDielectric
from sipi.impedance_material import _analyze_material, _material_input
from sipi.templates import coupled_stripline

MESH = dict(edge_size=5e-6, far_size=.125e-3, grade=.15)
BOUNDS = ((2., 6.), (2., 6.))


def geometry(a, b):
    return coupled_stripline(width=.3e-3, gap=.3e-3, plane_spacing=1e-3,
                             eps_r=1, box_width=.006)


def models(a, b):
    return {'dielectric': PrincipalAxisDielectric(
        ConstantDielectric(a, .01), ConstantDielectric(b, .02), 0)}


@pytest.fixture
def targets():
    # Place the search using a fresh actual solution. Independent physical
    # accuracy remains covered by the separate Cohn/complex-field tests.
    line = _analyze_material(CrossSectionDocument(geometry(4, 5), mesh=MESH),
                             _material_input(1e8, models(4, 5)), 'z_diff')
    modes = line.even_odd()
    return (modes['z_diff'], modes['z_common'])


def solve(targets, **kwargs):
    return seek_pair_impedances(geometry, BOUNDS, targets, tolerances=(1., .5),
        initial=(3., 3.), mesh=MESH, frequency=1e8,
        material_factory=kwargs.pop('material_factory', models), **kwargs)


def observe_mesh(monkeypatch):
    calls = []
    original = CrossSection.mesh
    def mesh(section, **options):
        calls.append(CrossSectionDocument(section, mesh=options).dumps())
        return original(section, **options)
    monkeypatch.setattr(CrossSection, 'mesh', mesh)
    return calls


def choose_known_point(monkeypatch):
    def optimize(objective, initial, **kwargs):
        chosen = np.array([.5, .75])  # Physical parameters (4, 5).
        first = objective(chosen)
        np.testing.assert_array_equal(objective(chosen), first)
        return SimpleNamespace(success=True, x=chosen)
    monkeypatch.setattr(module, 'least_squares', optimize)


def test_actual_tensor_pair_search_reuses_mesh_and_refines_in_each_call(targets, monkeypatch):
    calls = observe_mesh(monkeypatch)
    callbacks = []
    def model(a, b):
        callbacks.append((a, b))
        return models(a, b)
    result = solve(targets, material_factory=model)
    assert len(result.history) > 3 and len(calls) == 2
    assert callbacks == [row.parameters for row in result.history[:-1]]
    assert len(set(callbacks)) == len(callbacks)
    assert calls == [result.history[0].input_json, result.refined_input_json]
    assert all(abs(x) <= t for x, t in zip(result.residuals, result.tolerances))
    assert all(abs(x) <= t for x, t in zip(result.refined_residuals, result.tolerances))
    for row in result.history:
        expected = _material_input(1e8, models(*row.parameters))
        assert json.loads(row.material_evaluation_json) == expected
    assert result.history[-1].material_evaluation_json == result.material_evaluation_json
    # A second already-satisfying search still builds both meshes independently.
    second = seek_pair_impedances(geometry, BOUNDS, targets, tolerances=(1., .5),
        initial=(4., 5.), mesh=MESH, frequency=1e8, material_factory=models,
        max_evaluations=2)
    assert len(second.history) == 2 and len(calls) == 4
    assert calls[0] == calls[2] and calls[1] == calls[3]


def test_actual_refinement_limit_keeps_attempts_and_current_frozen_input(targets, monkeypatch):
    choose_known_point(monkeypatch)
    calls = observe_mesh(monkeypatch)
    original = crosssection.generate
    def limited(*args, **kwargs):
        if len(calls) == 2:
            kwargs['max_points'] = 4
        return original(*args, **kwargs)
    monkeypatch.setattr(crosssection, 'generate', limited)
    with pytest.raises(PairImpedanceGoalError) as caught:
        solve(targets, max_evaluations=4)
    error = caught.value
    assert error.stage == 'refinement/extraction'
    assert error.attempts == 3 and len(error.history) == 2 and len(calls) == 2
    assert isinstance(error.__cause__, MeshSizeLimitError)
    assert error.cause_type == 'MeshSizeLimitError'
    assert error.failed_parameters == (4., 5.)
    assert error.input_json == calls[-1]
    assert CrossSectionDocument.loads(error.input_json).mesh_options == dict(
        edge_size=MESH['edge_size']/2, far_size=MESH['far_size']/2,
        grade=MESH['grade']/2, min_angle=28.)
    assert error.material_evaluation_json == error.history[-1].material_evaluation_json
    assert json.loads(error.material_evaluation_json) == _material_input(1e8, models(4, 5))


def test_cached_mesh_rejects_current_invalid_material_before_extraction(targets, monkeypatch):
    choose_known_point(monkeypatch)
    calls = observe_mesh(monkeypatch)
    def material(a, b):
        value = models(a, b)
        return value if a == 3 else {'unknown': value['dielectric']}
    with pytest.raises(PairImpedanceGoalError) as caught:
        solve(targets, material_factory=material)
    error = caught.value
    assert error.stage == 'search/extraction' and error.attempts == 2
    assert len(error.history) == len(calls) == 1
    assert error.cause_type == 'ValueError' and isinstance(error.__cause__, ValueError)
    assert error.input_json == error.history[0].input_json
    assert set(json.loads(error.material_evaluation_json)['materials']) == {'unknown'}
    assert set(json.loads(error.history[0].material_evaluation_json)['materials']) == {'dielectric'}


def test_reused_mesh_still_performs_material_field_and_preserves_its_failure(targets, monkeypatch):
    choose_known_point(monkeypatch)
    calls = observe_mesh(monkeypatch)
    original = dielectric.capacitance_matrix
    fields = []
    cause = ArithmeticError('injected changed-material field failure')
    def capacitance(mesh, eps, *args):
        if np.ndim(eps) > 0:
            fields.append(eps)
            if len(fields) == 2:
                raise cause
        return original(mesh, eps, *args)
    monkeypatch.setattr(dielectric, 'capacitance_matrix', capacitance)
    with pytest.raises(PairImpedanceGoalError) as caught:
        solve(targets)
    error = caught.value
    assert error.stage == 'search/extraction' and error.attempts == 2
    assert len(error.history) == len(calls) == 1 and len(fields) == 2
    assert error.__cause__ is cause and error.cause_type == 'ArithmeticError'
    assert json.loads(error.material_evaluation_json) == _material_input(1e8, models(4, 5))
    assert error.material_evaluation_json != error.history[0].material_evaluation_json


def test_mesh_reuse_does_not_extend_the_parameter_evaluation_budget(targets, monkeypatch):
    choose_known_point(monkeypatch)
    calls = observe_mesh(monkeypatch)
    seen = []
    def material(a, b):
        seen.append((a, b))
        return models(a, b)
    with pytest.raises(PairImpedanceGoalError) as caught:
        solve(targets, max_evaluations=2, material_factory=material)
    error = caught.value
    assert error.stage == 'budget' and error.attempts == 1
    assert len(error.history) == len(calls) == 1 and seen == [(3., 3.)]
