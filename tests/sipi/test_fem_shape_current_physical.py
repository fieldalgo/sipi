# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Analytic, independent P2, mesh and multisignal current-energy checks."""
import json
from importlib.metadata import version
import numpy as np
import pytest
from galerkin import rectangle_mesh, annulus_mesh
import sipi.fem_shape_conductor as api
from sipi import CrossSection, Layer, Trace
from sipi.templates import coupled_stripline
from quadratic_shape_energy import quadratic_shape_energy


def solve_with_reference(mesh, signals, ground, monkeypatch):
    velocities = []; original = api.solve_dirichlet
    def velocity_solve(*a, **kw):
        value = original(*a, **kw); velocities.append(value.copy()); return value
    with monkeypatch.context() as patch:
        patch.setattr(api, 'solve_dirichlet', velocity_solve)
        result = api.fem_shape_current_factors(mesh, signals, ground)
    vectors = np.array(velocities).reshape(2, len(signals)+1, 2, mesh.num_nodes).swapaxes(-1, -2)
    reference = quadratic_shape_energy(mesh, signals, ground, vectors)
    return result, reference


def observations(result, reference):
    return dict(names=result.names, original_parts=result.base.parts.tolist(),
        original_flux=result.current_integrals.tolist(), C0=result.C0.tolist(),
        Q=result.extension_parts.tolist(), finite_differences=result.finite_difference_parts.tolist(),
        step_m=result.step_m, diagnostics=dict(result.diagnostics),
        P2={k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in reference.items()},
        reference_version=version('scikit-fem'), reference_license='BSD-3-Clause')


def max_boundary_error(a, b):
    return max(float(np.max(abs(x-y))/np.max(abs(y))) for ex, ey in zip(a, b) for x, y in zip(ex, ey))


@pytest.mark.parametrize('kind', ['plate','coax64','coax128'])
def test_analytic_current_energies_and_independent_p2(kind, monkeypatch, record_property):
    if kind == 'plate':
        mesh = rectangle_mesh(.002, .001, 8, 4); signals = {'signal': mesh.boundary['top']}; ground = mesh.boundary['bottom']; expected = np.array([500.,500.])
    else:
        fine = kind == 'coax128'; mesh = annulus_mesh(.001,.002,16 if fine else 8,128 if fine else 64)
        signals = {'inner': mesh.boundary['inner']}; ground = mesh.boundary['outer']; expected = 1/(2*np.pi*np.array([.001,.002]))
    result, reference = solve_with_reference(mesh, signals, ground, monkeypatch)
    record_property('shape_energy', json.dumps(observations(result, reference)))
    gate = 1e-10 if kind == 'plate' else .01
    assert np.max(abs(result.extension_parts[...,0,0]/expected-1)) <= gate
    assert np.max(abs(reference['parts'][...,0,0]/expected-1)) <= gate
    assert max_boundary_error(result.extension_parts, reference['parts']) <= gate


@pytest.fixture(scope='module')
def closed_fields():
    section = coupled_stripline(width=.0004,gap=.0003,plane_spacing=.002,eps_r=4.,thickness=.00005,box_width=.008)
    return [section.mesh(edge_size=5e-6*f,far_size=.0002*f,grade=.1*f) for f in (1.,.5)]


@pytest.fixture(scope='module')
def closed_results(closed_fields):
    rows = []
    with pytest.MonkeyPatch.context() as patch:
        for field in closed_fields:
            rows.append(solve_with_reference(field.mesh, field.signals, field.ground, patch))
    return rows


def test_closed_pair_independent_reference_and_mesh(closed_results, record_property):
    record_property('closed_shape_energy', json.dumps([observations(*row) for row in closed_results]))
    coarse, fine = closed_results; result, reference = fine
    assert max_boundary_error(result.extension_parts, reference['parts']) <= .01
    assert np.max(abs(result.C0-reference['C0']))/np.max(abs(reference['C0'])) <= .001
    assert max_boundary_error(coarse[0].extension_parts, result.extension_parts) <= .01
    assert max_boundary_error(coarse[1]['parts'], reference['parts']) <= .01


def test_closed_pair_signal_order_reversal(closed_fields, closed_results):
    field = closed_fields[0]
    other = api.fem_shape_current_factors(field.mesh, dict(reversed(list(field.signals.items()))), field.ground)
    np.testing.assert_allclose(other.extension_parts[:,[1,0,2],::-1,::-1], closed_results[0][0].extension_parts, rtol=1e-8, atol=0)
    np.testing.assert_allclose(other.C0[::-1,::-1], closed_results[0][0].C0, rtol=1e-8, atol=0)


@pytest.mark.parametrize('count', [3,4])
def test_refined_three_and_four_signal_independent_energy(count, monkeypatch, record_property):
    section = CrossSection([Layer('vacuum',.002)],
        [Trace('s'+str(i), (i-(count-1)/2)*.0008, .0004, .00095, .0001) for i in range(count)], .008, top='ground')
    factor = .5 if count == 3 else .25
    field = section.mesh(edge_size=5e-6*factor,far_size=.0002*factor,grade=.1*factor)
    result, reference = solve_with_reference(field.mesh, field.signals, field.ground, monkeypatch)
    record_property('multisignal_shape_energy', json.dumps(observations(result, reference)))
    assert result.names == tuple('s'+str(i) for i in range(count))
    assert len(result.samples) == 8*(count+1)
    assert max_boundary_error(result.extension_parts, reference['parts']) <= .01
    assert np.max(abs(result.C0-reference['C0']))/np.max(abs(reference['C0'])) <= .001
