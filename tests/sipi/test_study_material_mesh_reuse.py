# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Real study fields, per-call mesh reuse and retained failed material rows."""
import json

import numpy as np
import pytest

from sipi import CrossSection
from sipi.dielectric import ConstantDielectric, DebyeDielectric
from sipi.execution import execute_saved
from sipi.study import ImpedanceStudyDocument
import sipi.impedance_material as material

MESH = dict(edge_size=5e-6, far_size=.125e-3, grade=.15)
PARAMS = dict(width=.3e-3, plane_spacing=1e-3, eps_r=1, box_width=.006)
F = 1e8


def plan(*, debye=False, sampling=None):
    return ImpedanceStudyDocument('stripline', PARAMS, quantity='z0', mesh=MESH,
        frequency=F, materials={'dielectric':
            DebyeDielectric(2, [4], [F]) if debye else ConstantDielectric(4, .01)},
        material_variables={'dk': dict(region='dielectric',
            path=['strengths', 0] if debye else ['eps_r'])},
        sampling=sampling or dict(kind='sweep', count=3,
            variables=[dict(name='dk', lower=2, upper=6)]))


def count_meshes(monkeypatch):
    original, calls = CrossSection.mesh, []

    def mesh(self, **options):
        result = original(self, **options)
        calls.append(result)
        return result

    monkeypatch.setattr(CrossSection, 'mesh', mesh)
    return calls


@pytest.mark.parametrize('debye', [False, True])
def test_material_rows_recompute_fields_on_one_mesh_and_calls_are_isolated(monkeypatch, debye):
    doc = plan(debye=debye)
    meshes = count_meshes(monkeypatch)
    actual = doc.analyze()
    assert actual.failed == 0 and len(meshes) == 1
    samples = doc.samples()[:, 0]
    # Closed homogeneous scalar expression, independent of model sampling.
    eps_real = 2 + samples / 2 if debye else samples
    invariant = np.array([row.impedance for row in actual.rows]) * np.sqrt(eps_real)
    np.testing.assert_allclose(invariant, invariant[0], rtol=1e-10)
    assert len(set(row.impedance for row in actual.rows)) == 3
    first = meshes[0]
    replay = doc.analyze()
    assert len(meshes) == 2 and meshes[1] is not first
    assert [row.impedance for row in replay.rows] == [row.impedance for row in actual.rows]
    assert replay.summary == actual.summary


@pytest.mark.parametrize('failed_index', [0, 1])
def test_failed_material_field_does_not_poison_later_rows(monkeypatch, failed_index):
    doc = plan(debye=True)
    baseline = doc.analyze()
    meshes = count_meshes(monkeypatch)
    original, calls, c0_values = material._dispersive_from_mesh, [], []

    def evaluate(meshed, frequency, samples, *, c0=None):
        calls.append(meshed)
        c0_values.append(c0)
        if len(calls) - 1 == failed_index:
            raise ArithmeticError('material field failed')
        return original(meshed, frequency, samples, c0=c0)

    monkeypatch.setattr(material, '_dispersive_from_mesh', evaluate)
    result = doc.analyze()
    assert result.failed == 1 and result.summary is None
    assert len(meshes) == 1 and len(calls) == 3
    assert all(mesh is meshes[0] for mesh in calls)
    assert c0_values[0] is None
    if failed_index == 0:
        assert c0_values[1] is None and c0_values[2] is not None
    else:
        assert c0_values[1] is c0_values[2] and c0_values[1] is not None
    for index, (row, old) in enumerate(zip(result.rows, baseline.rows)):
        assert row.index == index
        assert row.material_evaluation_json == old.material_evaluation_json
        assert row.document.dumps() == old.document.dumps()
        if index == failed_index:
            assert row.error_type == 'ArithmeticError'
            assert row.error == 'material field failed'
            assert row.impedance is None
        else:
            assert row.complete and row.impedance == old.impedance


def test_invalid_normal_rows_retain_samples_and_do_not_poison_valid_rows(monkeypatch):
    doc = plan(sampling=dict(kind='normal', count=4, seed=9, correlation=[[1]],
        variables=[dict(name='dk', mean=2, std=2)]))
    samples = doc.samples().copy()
    meshes = count_meshes(monkeypatch)
    output = execute_saved(doc.dumps())
    assert output['status'] == 'incomplete'
    assert output['result']['failed'] == 2 and output['result']['summary'] is None
    assert len(meshes) == 1
    np.testing.assert_array_equal(doc.samples(), samples)
    successful = []
    for index, row in enumerate(output['result']['rows']):
        value = samples[index, 0]
        assert row['material_evaluation']['materials']['dielectric']['parameters']['eps_r'] == value
        if value < 1:
            assert row['error_type'] == 'ValueError' and row['value'] is None
        else:
            assert row['error'] is None
            successful.append(row['value'] * np.sqrt(value))
    np.testing.assert_allclose(successful, successful[0], rtol=1e-10)


def test_geometry_material_corners_keep_order_and_remesh_changed_geometry(monkeypatch):
    doc = plan(sampling=dict(kind='corners', variables=[
        dict(name='width', lower=.25e-3, upper=.35e-3),
        dict(name='dk', lower=2, upper=6)]))
    meshes = count_meshes(monkeypatch)
    result = doc.analyze()
    assert result.failed == 0 and len(meshes) == 2
    assert [row.parameters['width'] for row in result.rows] == [.25e-3]*2 + [.35e-3]*2
    eps = [json.loads(row.material_evaluation_json)['materials']['dielectric']['parameters']['eps_r']
           for row in result.rows]
    assert eps == [2, 6, 2, 6]
    for start in [0, 2]:
        scaled = [result.rows[i].impedance * np.sqrt(eps[i]) for i in [start, start+1]]
        np.testing.assert_allclose(scaled, scaled[0], rtol=1e-10)
    assert result.rows[0].impedance != result.rows[2].impedance


def test_budget_counts_all_planned_rows_before_reuse_or_material_solves(monkeypatch):
    doc = plan()
    monkeypatch.setattr(CrossSection, 'mesh', lambda *a, **k: pytest.fail('budget meshed'))
    monkeypatch.setattr(material, '_dispersive_from_mesh',
                        lambda *a, **k: pytest.fail('budget solved'))
    with pytest.raises(ValueError, match='before any solve'):
        doc.analyze(max_evaluations=2)


def test_geometry_only_study_keeps_original_per_row_mesh_path(monkeypatch):
    doc = ImpedanceStudyDocument('stripline', PARAMS, quantity='z0', mesh=MESH,
        sampling=dict(kind='sweep', count=3,
            variables=[dict(name='width', lower=.25e-3, upper=.35e-3)]))
    meshes = count_meshes(monkeypatch)
    monkeypatch.setattr(material, '_dispersive_from_mesh',
                        lambda *a, **k: pytest.fail('legacy entered material path'))
    result = doc.analyze()
    assert result.failed == 0 and len(meshes) == 3
    assert all(row.material_evaluation_json is None for row in result.rows)
