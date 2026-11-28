# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The stored finite-resolution study record and its opt-in gate, without field solves."""
import importlib
import json
from types import SimpleNamespace
from pathlib import Path
import numpy as np
import pytest
import resolution_studies as support

DATA = json.loads(support.RECORD.read_text(encoding='utf-8'))
GENERATOR = support.RECORD.with_name('generate_finite_resolution_studies.py')
PLATFORMS = ('ubuntu-latest', 'macos-15', 'windows-latest')


def test_record_contract_and_reproduction_tolerance():
    assert DATA['schema'] == 'sipi.finite-resolution-studies/1'
    assert DATA['environment_variable'] == support.ENVIRONMENT == 'SIPI_RESOLUTION_STUDIES'
    assert DATA['reproduction_matrix_relative'] == support.MATRIX_RELATIVE == 1e-9
    assert sorted(DATA['quantities']) == sorted(['R_ohm_per_m', 'L_internal_h_per_m', 'L_external_h_per_m',
                                                 'C_f_per_m', 'G_s_per_m', 'C0_f_per_m'])
    assert DATA['study_source'] and DATA['product_commit'] and DATA['command'].startswith('PYTHONPATH=src python')
    text = GENERATOR.read_text(encoding='utf-8')
    for name in DATA['modules']:
        assert repr(name) in text


@pytest.mark.parametrize('name', sorted(DATA['modules']))
def test_every_study_was_accepted_on_every_platform_and_suite(name):
    entry = DATA['modules'][name]
    assert '0.01 max(|a|, |b|)' in entry['criterion']
    for case in entry['cases']:
        labels = set(case['study'])
        assert {f'{p}/source' for p in PLATFORMS} <= labels
        for outcome in case['study'].values():
            assert outcome['completed'] and outcome['accepted']
            ratios = outcome['worst_difference_over_allowance']
            assert set(ratios) >= {'volume', 'panel', 'joint:panel', 'joint:volume', 'outer:0', 'outer:1'}
            assert all(0 <= value <= 1 for value in ratios.values())
        covered = [label for row in case['variants'] for label in row['recorded_by']]
        assert sorted(covered) == sorted(labels)
        assert any('local_check_matrix_relative' in row for row in case['variants'])
        for row in case['variants']:
            assert sorted(row['quantities']) == sorted(DATA['quantities'])
            assert all(np.isfinite(np.asarray(value, dtype=float)).all() for value in row['quantities'].values())
            assert row.get('local_check_matrix_relative', 0) <= support.MATRIX_RELATIVE


@pytest.mark.parametrize('name', sorted(DATA['modules']))
def test_study_tests_are_defined_only_with_the_gate(name):
    module = importlib.import_module(name)
    entry = DATA['modules'][name]
    assert hasattr(module, entry['test']) is support.ENABLED
    assert hasattr(module, 'test_base_resolution_reproduces_the_recorded_study')
    for case in entry['cases']:
        assert json.loads(module.inputs(case['index'])[0].dumps()) == case['base_input']


def test_matrix_relative_scale():
    assert support.matrix_relative([1., 2.], [1., 2.]) == 0
    assert support.matrix_relative([1., 2.+4e-9], [1., 2.]) == pytest.approx(2e-9)
    with pytest.raises(AssertionError):
        support.matrix_relative([1.], [1., 2.])


def line(variant, mesh, scale=1.):
    """A stand-in for a solved line carrying a recorded variant's values, scaled."""
    q = {key: np.asarray(value, dtype=float) * scale for key, value in variant['quantities'].items()}
    return SimpleNamespace(R=q['R_ohm_per_m'], C=q['C_f_per_m'], G=q['G_s_per_m'],
        conductor=SimpleNamespace(L_internal=q['L_internal_h_per_m']),
        dielectric=SimpleNamespace(C0=q['C0_f_per_m'][0], L=q['L_external_h_per_m'][0]),
        mesh_record=lambda: dict(mesh, signal_nodes=[]))


def test_mesh_variants_take_the_exact_path_and_unknown_meshes_the_tolerance_path():
    name = 'test_two_ground_linear_corner_face_resolution'
    variants = DATA['modules'][name]['cases'][0]['variants']
    assert support.MATRIX_RELATIVE < 2.2e-5 < support.MESH_VARIANT_RELATIVE <= .01 / 100
    for row in variants:
        path, labels, errors = support.compare(name, 0, line(row, row['dielectric_mesh']))
        assert path == 'exact' and labels == row['recorded_by'] and max(errors.values()) == 0
        with pytest.raises(AssertionError):
            support.compare(name, 0, line(row, row['dielectric_mesh'], 1 + 1e-8))
    other = dict(nodes_float64_le_sha256='0' * 64, triangles_int64_le_sha256='0' * 64)
    path, labels, errors = support.compare(name, 0, line(variants[0], other, 1 + 5e-5))
    assert path == 'tolerance' and labels == variants[0]['recorded_by']
    assert max(errors.values()) == pytest.approx(5e-5, rel=1e-6)
    with pytest.raises(AssertionError):
        support.compare(name, 0, line(variants[0], other, 1 + 2e-4))


@pytest.mark.parametrize('name', sorted(support.GATED))
def test_other_study_tests_are_defined_only_with_the_gate(name):
    module = importlib.import_module(name)
    assert hasattr(module, support.GATED[name]) is support.ENABLED


LINE = json.loads(support.LINE_STUDY_RECORD.read_text(encoding='utf-8'))


def test_line_study_base_record_was_accepted_on_every_platform_and_suite():
    assert LINE['schema'] == 'sipi.linear-line-study-base/1'
    assert LINE['module'] in support.GATED and support.GATED[LINE['module']] == LINE['test']
    assert LINE['reproduction_matrix_relative'] == support.MATRIX_RELATIVE
    assert LINE['quantities'] == ['C0_f_per_m', 'L_h_per_m', 'R_ohm_per_m', 'impedance_real_ohm']
    assert '0.01' in LINE['criterion'] and LINE['study_source'] and LINE['product_commit']
    assert [row['index'] for row in LINE['rows']] == [0, 1, 2]
    for row in LINE['rows']:
        assert {f'{p}/{s}' for p in PLATFORMS for s in ('source', 'installed')} == set(row['study'])
        assert all(o['passed'] and 0 <= o['worst_difference_over_allowance'] <= 1 for o in row['study'].values())
        covered = [label for variant in row['variants'] for label in variant['recorded_by']]
        assert sorted(covered) == sorted(row['study'])
        assert any('local_check_matrix_relative' in variant for variant in row['variants'])
        for variant in row['variants']:
            assert sorted(variant['quantities']) == LINE['quantities']
            assert variant.get('local_check_matrix_relative', 0) <= support.MATRIX_RELATIVE


def test_line_study_variants_take_the_exact_path_and_unknown_meshes_the_tolerance_path():
    variants = LINE['rows'][0]['variants']
    for row in variants:
        values = {key: np.asarray(value, dtype=float) for key, value in row['quantities'].items()}
        path, labels, errors = support.compare_variants(values, row['dielectric_mesh'], variants)
        assert path == 'exact' and labels == row['recorded_by'] and max(errors.values()) == 0
        with pytest.raises(AssertionError):
            support.compare_variants({k: v * (1 + 1e-8) for k, v in values.items()}, row['dielectric_mesh'], variants)
    other = dict(nodes_float64_le_sha256='0' * 64, triangles_int64_le_sha256='0' * 64)
    values = {key: np.asarray(value, dtype=float) * (1 + 5e-5) for key, value in variants[0]['quantities'].items()}
    assert support.compare_variants(values, other, variants)[0] == 'tolerance'
    with pytest.raises(AssertionError):
        support.compare_variants({k: v * 4 for k, v in values.items()}, other, variants)
