# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Optional requested-mesh matrices preserve search selection and failure gates."""
from dataclasses import fields
import json
import numpy as np
import pytest
from meshine import MeshSizeLimitError
import sipi
import sipi.design as design
from sipi.dielectric import ConstantDielectric
from sipi.templates import stripline, coupled_stripline


MESH = dict(edge_size=.01, far_size=1., grade=.2)


def factory(quantity):
    def section(width):
        p = dict(width=width, plane_spacing=10, eps_r=4)
        return stripline(**p) if quantity == 'z0' else coupled_stripline(**p, gap=1)
    return section


def instrument(monkeypatch, quantity, material_mode, *, failure_at=None,
               refinement_scale=1.):
    """Synthetic reciprocal diagonal matrices isolate control flow, not accuracy."""
    n = 1 if quantity == 'z0' else 2
    matrices = {k: np.eye(n) for k in ('C', 'C0', 'L', 'C_loss')}
    calls, model_calls = [], []
    cause = MeshSizeLimitError('injected field limit')

    def analyze(section, **mesh):
        calls.append((section.traces[0].width, dict(mesh)))
        if len(calls) == failure_at:
            raise cause
        width = section.traces[0].width
        scale = refinement_scale if mesh['grade'] == MESH['grade']/2 else 1.
        # Reuse all backing arrays to detect snapshots taken too late.
        matrices['C'][:] = np.eye(n)*width**2/scale**2
        matrices['L'][:] = np.eye(n)
        matrices['C0'][:] = np.eye(n)*len(calls)
        matrices['C_loss'][:] = np.eye(n)*len(calls)/100
        return sipi.LineParameters(tuple(f's{i}' for i in range(n)), **matrices)

    def material(doc, value, selected_quantity, *, mesh_reuse=None):
        assert selected_quantity == quantity
        return analyze(doc.section, **doc.mesh_options)

    def models(width):
        model_calls.append(width)
        return {'dielectric': ConstantDielectric(4+width)}

    monkeypatch.setattr(sipi.CrossSection, 'analyze', analyze)
    monkeypatch.setattr(design, '_analyze_material', material)
    options = {} if material_mode == 'none' else dict(frequency=1e8)
    if material_mode == 'fixed':
        options['materials'] = {'dielectric': ConstantDielectric(4)}
    if material_mode == 'factory':
        options['material_factory'] = models
    return options, calls, model_calls, matrices, cause


@pytest.mark.parametrize('quantity', ['z0', 'z_diff', 'z_diff_forward'])
@pytest.mark.parametrize('material_mode', ['none', 'fixed', 'factory'])
@pytest.mark.parametrize('selection', ['lower', 'upper', 'interior', 'tie'])
def test_requested_snapshot_matches_selection_without_extra_solves(
        quantity, material_mode, selection, monkeypatch):
    options, calls, model_calls, backing, _ = instrument(monkeypatch, quantity, material_mode)
    factor = 1 if quantity == 'z0' else 2
    target = factor*dict(lower=1., upper=.5, interior=2/3, tie=.75)[selection]
    tolerance = factor*(.25 if selection == 'tie' else 1e-12)
    result, line = sipi.seek_impedance(factory(quantity), [1, 2], target,
        quantity=quantity, tolerance=tolerance, mesh=MESH, max_evaluations=4,
        return_line=True, **options)
    width = dict(lower=1., upper=2., interior=1.5, tie=1.)[selection]
    selected_index = dict(lower=1, upper=2, interior=3, tie=1)[selection]
    assert type(result) is sipi.ImpedanceDesign
    assert [f.name for f in fields(result)] == ['parameter', 'target', 'impedance',
        'refined_impedance', 'quantity', 'document', 'history', 'material_evaluation_json']
    assert result.parameter == width
    assert len(calls) == len(result.history) == (4 if selection == 'interior' else 3)
    assert result.history[-1].stage == 'refinement'
    assert calls[-1][0] == width
    for key in ('edge_size', 'far_size', 'grade'):
        assert calls[-1][1][key] == MESH[key]/2
    assert model_calls == ([c[0] for c in calls[:-1]] if material_mode == 'factory' else [])
    value = line.even_odd()['z_diff'] if quantity == 'z_diff' else getattr(line, quantity)
    assert value == pytest.approx(result.impedance, rel=1e-14)
    assert line.C0[0, 0] == selected_index
    assert line.C_loss[0, 0] == selected_index/100
    for key in backing:
        array = getattr(line, key)
        assert not np.shares_memory(array, backing[key]) and not array.flags.writeable
        saved = array.copy()
        backing[key][:] = -100
        np.testing.assert_array_equal(array, saved)
        with pytest.raises(ValueError):
            array[0, 0] = 0
    if material_mode == 'none':
        assert result.material_evaluation_json is None
    else:
        data = json.loads(result.material_evaluation_json)
        assert data['frequency_hz'] == 1e8
        assert data['materials']['dielectric']['parameters']['eps_r'] == (
            4+width if material_mode == 'factory' else 4)


@pytest.mark.parametrize('material_mode', ['none', 'fixed', 'factory'])
@pytest.mark.parametrize('failure_at', [1, 2, 3, 4])
def test_optional_result_cannot_escape_failed_search_or_refinement(
        material_mode, failure_at, monkeypatch):
    options, calls, _, _, cause = instrument(monkeypatch, 'z0', material_mode,
                                           failure_at=failure_at)
    with pytest.raises(sipi.GoalMeshSizeLimitError) as caught:
        sipi.seek_impedance(factory('z0'), [1, 2], 2/3, tolerance=1e-12,
            mesh=MESH, max_evaluations=4, return_line=True, **options)
    error = caught.value
    assert error.__cause__ is cause
    assert error.attempts == failure_at == len(calls)
    assert len(error.history) == failure_at-1
    assert error.stage == ('refinement' if failure_at == 4 else 'search')
    assert sipi.CrossSectionDocument.loads(error.input_json).section.traces[0].width == error.parameter
    assert (error.material_evaluation_json is None) == (material_mode == 'none')


@pytest.mark.parametrize('failure', ['bracket', 'budget', 'refinement'])
def test_optional_result_preserves_acceptance_gates(failure, monkeypatch):
    _, calls, _, _, _ = instrument(monkeypatch, 'z0', 'none',
        refinement_scale=2. if failure == 'refinement' else 1.)
    target = dict(bracket=3., budget=2/3, refinement=1.)[failure]
    match = dict(bracket='not bracketed', budget='evaluation limit', refinement='refined mesh misses')[failure]
    with pytest.raises(sipi.GoalSeekError, match=match) as caught:
        sipi.seek_impedance(factory('z0'), [1, 2], target, tolerance=1e-12,
            mesh=MESH, max_evaluations=3, return_line=True)
    assert len(calls) == len(caught.value.history) == (3 if failure == 'refinement' else 2)


@pytest.mark.parametrize('value', [None, 0, 1, 'true', [], np.bool_(True)])
def test_return_line_requires_boolean_before_factory(value):
    def forbidden(width):
        pytest.fail('Invalid control reached the geometry factory')
    with pytest.raises(ValueError, match='return_line must be a boolean'):
        sipi.seek_impedance(forbidden, [1, 2], 1, return_line=value)


def test_default_does_not_capture_matrices(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(sipi.CrossSection, 'analyze',
        lambda self, **kw: SimpleNamespace(z0=1/self.traces[0].width))
    result = sipi.seek_impedance(factory('z0'), [1, 2], 1, mesh=MESH)
    assert type(result) is sipi.ImpedanceDesign
    assert not hasattr(result, 'line') and result.parameter == 1
