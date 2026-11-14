# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Admission, explicit derivatives, evidence and failure propagation."""
from dataclasses import replace
import numpy as np
import pytest
from galerkin import Mesh, rectangle_mesh
import sipi.fem_shape_conductor as api
from sipi import fem_shape_current_factors, FEMShapeCurrentError, FEMShapeSample


def plate():
    mesh = rectangle_mesh(.002, .001, 8, 4)
    return mesh, {'signal': mesh.boundary['top']}, mesh.boundary['bottom']


@pytest.fixture(scope='module')
def result(): return fem_shape_current_factors(*plate())


def test_plate_exact_energies_and_complete_requests(result):
    np.testing.assert_allclose(result.extension_parts[..., 0, 0], 500., rtol=1e-10, atol=0)
    np.testing.assert_allclose(result.total, [[1000.]], rtol=1e-10, atol=0)
    np.testing.assert_allclose(result.current_integrals, [[1.], [-1.]], rtol=1e-10, atol=0)
    assert result.current_error == result.base.current_error
    assert result.C0 is result.base.C0 and result.names == ('signal',)
    np.testing.assert_array_equal(result.L_external, result.base.L_external)
    assert len(result.samples) == 16
    assert max(result.diagnostics['finite_difference_errors']) < 1e-4
    assert result.diagnostics['step_error'] < 1e-4
    assert result.diagnostics['normal_velocity_error'] <= 1e-12


@pytest.mark.parametrize('key', ['extension_parts', 'finite_difference_parts', 'parts', 'total'])
def test_observations_cannot_be_mutated(result, key):
    with pytest.raises(ValueError): getattr(result, key).setflags(write=True)


def test_samples_and_diagnostics_are_readonly(result):
    with pytest.raises(ValueError): result.samples[0].capacitance_per_permittivity.setflags(write=True)
    with pytest.raises(TypeError): result.diagnostics['new'] = 1


@pytest.mark.parametrize('change', [dict(step_m=0.), dict(step_m=np.nan), dict(samples=()),
    dict(samples=None), dict(extension_parts=np.ones((1, 2, 1, 1))),
    dict(finite_difference_parts=np.ones((1, 2, 2, 1, 1))), dict(base=object())], ids=['step','nan','missing','none','energy-shape','FD-shape','base'])
def test_incomplete_result_is_rejected(result, change):
    with pytest.raises((ValueError, TypeError)): replace(result, **change)


def test_changed_request_order_or_step_is_rejected(result):
    with pytest.raises(ValueError): replace(result, samples=result.samples[::-1])
    bad = replace(result.samples[0], displacement_m=result.step_m*2)
    with pytest.raises(ValueError): replace(result, samples=(bad, *result.samples[1:]))


@pytest.mark.parametrize('change', [dict(extension=2),dict(group=-1),dict(level=2),dict(sign=0),dict(displacement_m=0.),dict(capacitance_per_permittivity=[1.]),dict(capacitance_per_permittivity=[[np.nan]])])
def test_invalid_sample_is_rejected(result, change):
    with pytest.raises(ValueError): replace(result.samples[0], **change)


@pytest.mark.parametrize('kind', ['empty','five','overlap','interior','name','nonpositive','too-large','not-mesh'])
def test_rejection_precedes_field_solves(monkeypatch, kind):
    mesh, signals, ground = plate()
    if kind == 'empty': signals = {}
    if kind == 'five': signals = {str(i): nodes for i, nodes in enumerate([ground]*5)}
    if kind == 'overlap': ground = signals['signal']
    if kind == 'interior': signals = {'signal': np.array([10, 11])}
    if kind == 'name': signals = {'': signals['signal']}
    if kind == 'nonpositive': mesh.triangles[0] = mesh.triangles[0, ::-1]
    if kind == 'too-large': mesh.nodes = np.zeros((300001, 2))
    if kind == 'not-mesh': mesh = object()
    monkeypatch.setattr(api, '_surface_current_basis', lambda *a: pytest.fail('field reached'))
    with pytest.raises((ValueError, TypeError)): fem_shape_current_factors(mesh, signals, ground)


@pytest.mark.parametrize('completed', [0, 1, 7])
def test_failed_capacitance_keeps_original_and_partial_evidence(monkeypatch, completed):
    calls = []; real = api.capacitance_matrix
    def solve(*a, **kw):
        if len(calls) == completed: raise RuntimeError('injected field failure')
        answer = real(*a, **kw); calls.append(answer.copy()); return answer
    monkeypatch.setattr(api, 'capacitance_matrix', solve)
    with pytest.raises(FEMShapeCurrentError) as caught: fem_shape_current_factors(*plate())
    error = caught.value
    assert isinstance(error.__cause__, RuntimeError)
    assert error.stage == 'capacitance-differences' and error.base is not None
    assert len(error.samples) == completed and error.request is not None
    assert error.extension_parts.shape == (2, 2, 1, 1)
    for sample, original in zip(error.samples, calls):
        np.testing.assert_array_equal(sample.capacitance_per_permittivity, original/api.epsilon_0)


@pytest.mark.parametrize('where', ['basis','extension','capacitance'])
def test_interrupt_is_not_converted(monkeypatch, where):
    def stop(*a, **kw): raise KeyboardInterrupt('cancelled')
    monkeypatch.setattr(api, {'basis':'_surface_current_basis','extension':'solve_dirichlet','capacitance':'capacitance_matrix'}[where], stop)
    with pytest.raises(KeyboardInterrupt): fem_shape_current_factors(*plate())


def test_failed_basis_is_typed_without_fabricated_base(monkeypatch):
    def fail(*a): raise RuntimeError('basis failure')
    monkeypatch.setattr(api, '_surface_current_basis', fail)
    with pytest.raises(FEMShapeCurrentError) as caught: fem_shape_current_factors(*plate())
    assert caught.value.stage == 'basis' and caught.value.base is None and caught.value.samples == ()


def test_wrong_capacitance_derivative_is_rejected_with_all_samples(monkeypatch):
    real = api.capacitance_matrix
    monkeypatch.setattr(api, 'capacitance_matrix', lambda *a, **kw: 1.01*real(*a, **kw))
    with pytest.raises(FEMShapeCurrentError, match='finite-difference') as caught: fem_shape_current_factors(*plate())
    assert len(caught.value.samples) == 16 and caught.value.stage == 'checks'
    assert max(caught.value.diagnostics['finite_difference_errors']) > .001


def test_nonfinite_extension_retains_typed_partial(monkeypatch):
    monkeypatch.setattr(api, 'element_gradient', lambda mesh, v: np.full((mesh.num_triangles, 2), np.nan))
    with pytest.raises(FEMShapeCurrentError, match='nonfinite') as caught: fem_shape_current_factors(*plate())
    assert caught.value.stage == 'extensions' and caught.value.base is not None
    assert np.isnan(caught.value.extension_parts).all()


@pytest.mark.parametrize('transform', ['rotation','translation','reflection','small','large'])
def test_plate_geometric_invariants(result, transform):
    mesh, signals, ground = plate(); points = mesh.nodes.copy(); factor = 1.
    if transform == 'rotation':
        a = np.deg2rad(37); points = points@np.array([[np.cos(a), np.sin(a)],[-np.sin(a), np.cos(a)]])
    if transform == 'translation': points += [.02, -.03]
    if transform == 'reflection': points[:, 0] *= -1
    if transform in ('small','large'):
        factor = .001 if transform == 'small' else 1000.; points *= factor
    actual = fem_shape_current_factors(Mesh(points, mesh.triangles.copy(), {}), signals, ground)
    np.testing.assert_allclose(actual.extension_parts*factor, result.extension_parts, rtol=1e-8, atol=0)
    np.testing.assert_allclose(actual.C0, result.C0, rtol=1e-8, atol=0)


def test_all_offset_meshes_are_checked_before_deformed_solves(monkeypatch):
    original = api._signed_areas; calls = []
    def areas(*a):
        value = original(*a); calls.append(True)
        if len(calls) == 2: value[0] = -abs(value[0])
        return value
    monkeypatch.setattr(api, '_signed_areas', areas)
    monkeypatch.setattr(api, 'capacitance_matrix', lambda *a, **kw: pytest.fail('deformed solve reached'))
    with pytest.raises(FEMShapeCurrentError, match='inverts') as caught: fem_shape_current_factors(*plate())
    assert caught.value.stage == 'offset-preflight'
    assert caught.value.base is not None and caught.value.samples == ()
    assert caught.value.request == (0,0,0,-1,caught.value.request[-1])
