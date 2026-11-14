# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Fixed layered metals in geometry/material studies and unresolved iid yield."""
import json
import statistics

import numpy as np
import pytest
from scipy.linalg import expm

from sipi import CrossSection, CrossSectionDocument
from sipi.study import ImpedanceStudyDocument, _TEMPLATES
from sipi.dielectric import ConstantDielectric
from sipi.line_study import LineQuantityStudyDocument
from sipi.line_yield import LineQuantityYieldDocument, assess_line_yield
from sipi.line_model import TransmissionLineDocument
from sipi.execution import execute_saved, normalize_saved
from test_yield_assessment import independent_interval

MESH = dict(edge_size=5e-6, far_size=.2e-3, grade=.1)
PAIR = ('differential_forward_impedance_real', 'common_forward_impedance_real')


def material():
    return dict(kind='layered', conductivity=58e6, relative_permeability=1., coatings=[
        dict(thickness_m=.2e-6, conductivity=14e6, relative_permeability=3.),
        dict(thickness_m=1e-6, conductivity=40e6, relative_permeability=1.)])


def document(quantity='impedance_real', *, sampling=None, material_variables=False):
    paired = quantity in PAIR
    parameters = dict(width=.5e-3, plane_spacing=1e-3, thickness=50e-6,
                      eps_r=4., tan_delta=.02, box_width=4e-3)
    if paired: parameters['gap'] = .3e-3
    options = {}
    if material_variables:
        options = dict(material_variables={'loss': dict(region='dielectric', path=['tan_delta'])})
    study = ImpedanceStudyDocument('coupled_stripline' if paired else 'stripline', parameters,
        quantity='z_diff_forward' if paired else 'z0', frequency=1e9,
        materials={'dielectric': ConstantDielectric(4., .02)} if material_variables else {}, mesh=MESH,
        sampling=sampling or dict(kind='sweep', count=2, variables=[dict(name='width', lower=.45e-3, upper=.55e-3)]),
        **options)
    names = ('positive', 'negative') if paired else ('signal',)
    conductor = dict(kind='surface-boundaries', conductors={name: material() for name in names},
                     reference=material(), ground_thickness=35e-6)
    return LineQuantityStudyDocument(study, conductor=conductor, quantity=quantity, schema='sipi.line-quantity-study/4')


def yield_document():
    return LineQuantityYieldDocument(document(sampling=dict(kind='uniform', count=4, seed=123,
        variables=[dict(name='width', lower=.45e-3, upper=.55e-3)])),
        minimum=1., maximum=1000., schema='sipi.line-quantity-yield/3')


def test_field_free_roundtrip_and_nested_material_copy(monkeypatch):
    monkeypatch.setattr(CrossSection, 'mesh', lambda *a, **k: pytest.fail('normalization meshed'))
    for doc in (document(), yield_document()):
        text = doc.dumps(); raw = doc.to_dict(); restored = type(doc).from_dict(raw)
        assert restored.dumps() == text == normalize_saved(text)
        target = raw['study'] if raw['schema'].startswith('sipi.line-quantity-yield/') else raw
        target['conductor']['reference']['coatings'][0]['conductivity'] = -1
        assert restored.dumps() == text


@pytest.mark.parametrize('quantity', ['impedance_real', 'attenuation'])
def test_scalar_rows_match_direct_fields_and_independent_transfer(quantity, record_property):
    doc = document(quantity); result = doc.analyze()
    assert not result.failed
    errors = []
    for row in result.rows:
        raw = json.loads(row.input_json)
        assert raw['schema'] == 'sipi.transmission-line/7'
        assert raw['conductor'] == doc.to_dict()['conductor']
        source = doc.to_dict()['study']
        direct = TransmissionLineDocument(CrossSectionDocument(_TEMPLATES[source['template']](
            **json.loads(row.parameters_json)), mesh=MESH), [1e9], materials={}, conductor=raw['conductor'],
            length=0., schema='sipi.transmission-line/7').analyze()
        for key in ('R', 'L', 'C', 'G'):
            np.testing.assert_allclose(getattr(row.result, key), getattr(direct, key), rtol=1e-10)
        r, l, c, g = (getattr(direct, key)[0, 0, 0] for key in ('R', 'L', 'C', 'G'))
        omega, length = 2*np.pi*1e9, .003
        transfer = expm(np.array([[0, r+1j*omega*l], [g+1j*omega*c, 0]])*length)
        expected = (np.sqrt(transfer[0, 1]/transfer[1, 0]).real if quantity == 'impedance_real'
                    else np.log(max(abs(np.linalg.eigvals(transfer))))/length)
        errors.append(float(abs(row.value/expected-1)))
    record_property('scalar_transfer_relative_error', max(errors))
    assert max(errors) < 1e-8
    assert result.summary['mean'] == pytest.approx(statistics.mean(r.value for r in result.rows), rel=1e-12)


@pytest.mark.parametrize('quantity', PAIR)
def test_paired_rows_keep_explicit_forward_quantity(quantity):
    doc = document(quantity); result = doc.analyze(); assert not result.failed
    for row in result.rows:
        line = row.result
        # Keep the actual matrices, including meshing asymmetry. The growing
        # eigenspace of an independent finite transfer identifies V/I without
        # asserting decoupled numerical differential/common modes.
        index = 0 if quantity == PAIR[0] else 1
        r, l, c, g = (getattr(line, key)[0] for key in ('R', 'L', 'C', 'G'))
        from scipy.linalg import solve
        z, y = r+2j*np.pi*1e9*l, g+2j*np.pi*1e9*c
        transfer = expm(np.block([[np.zeros((2, 2)), z], [y, np.zeros((2, 2))]])*.003)
        values, vectors = np.linalg.eig(transfer)
        forward = vectors[:, abs(values) > 1]
        assert forward.shape == (4, 2)
        characteristic = solve(forward[2:].T, forward[:2].T).T
        voltage = np.array([[1., -1.], [.5, .5]])
        current = np.array([[.5, -.5], [1., 1.]])
        expected = (voltage@characteristic@np.linalg.inv(current))[index, index].real
        assert row.value == pytest.approx(expected, rel=1e-10)
        assert json.loads(row.input_json)['schema'] == 'sipi.transmission-line/7'


def test_correlated_geometry_and_dielectric_samples_preserve_original_vectors():
    doc = document('attenuation', material_variables=True, sampling=dict(kind='normal', count=3, seed=3,
        variables=[dict(name='width', mean=.5e-3, std=.01e-3), dict(name='loss', mean=.02, std=.001)],
        correlation=[[1., .4], [.4, 1.]]))
    result = doc.analyze(); assert not result.failed
    for row, values in zip(result.rows, doc.samples()):
        assert row.sample_values == tuple(values)
        raw = json.loads(row.input_json)
        assert raw['cross_section']['traces'][0]['width'] == values[0]
        assert raw['materials']['dielectric']['parameters']['tan_delta'] == values[1]
        assert raw['conductor'] == doc.to_dict()['conductor']


def test_real_core_failures_remain_in_iid_yield_denominator_and_order():
    sample = dict(kind='uniform', count=4, seed=123,
        variables=[dict(name='thickness', lower=1e-6, upper=60e-6)])
    doc = document(sampling=sample); result = doc.analyze()
    assert 0 < result.failed < len(result.rows) and result.summary is None
    for row, values in zip(result.rows, doc.samples()):
        assert row.sample_values == tuple(values)
        if not row.complete:
            assert row.phase == 'input' and row.error_type == 'ValueError'
            assert row.value is None and row.input_json is None
            assert json.loads(row.parameters_json)['thickness'] == values[0]
    assessed = assess_line_yield(result, minimum=1., maximum=1000., confidence=.95)
    n, passed, unknown = len(result.rows), assessed.passed, assessed.unresolved
    assert unknown == result.failed and passed+unknown == n
    expected = (independent_interval(passed, n, .95)[0], independent_interval(passed+unknown, n, .95)[1])
    np.testing.assert_allclose(assessed.confidence_interval, expected, rtol=0, atol=1e-12)
    assert assessed.sample_fraction_bounds == (passed/n, 1.)
    saved = LineQuantityYieldDocument(doc, minimum=1., maximum=1000., schema='sipi.line-quantity-yield/3')
    assert saved.analyze().to_dict() == assessed.to_dict()


def test_saved_execution_matches_direct_yield_and_budget_precedes_mesh(monkeypatch):
    doc = yield_document(); direct = doc.analyze()
    output = execute_saved(doc.dumps())
    assert output['status'] == 'complete' and output['result'] == direct.to_dict()
    monkeypatch.setattr(CrossSection, 'mesh', lambda *a, **k: pytest.fail('budget allowed mesh'))
    with pytest.raises(ValueError, match='max_evaluations'): execute_saved(doc.dumps(), max_evaluations=2)


@pytest.mark.parametrize('version', [1, 2, 3])
def test_old_studies_reject_layered_materials(version):
    raw = document().to_dict(); raw['schema'] = f'sipi.line-quantity-study/{version}'
    with pytest.raises(ValueError): LineQuantityStudyDocument.from_dict(raw)


@pytest.mark.parametrize('version', [1, 2])
def test_old_yield_versions_do_not_admit_new_study(version):
    raw = yield_document().to_dict(); raw['schema'] = f'sipi.line-quantity-yield/{version}'
    with pytest.raises(ValueError): LineQuantityYieldDocument.from_dict(raw)


def test_scalar_legacy_values_and_inputs_keep_version_six():
    from test_line_study import document as legacy
    old = legacy(); raw = old.to_dict(); raw['schema'] = 'sipi.line-quantity-study/4'
    a, b = old.analyze(), LineQuantityStudyDocument.from_dict(raw).analyze()
    for left, right in zip(a.rows, b.rows):
        assert left.value == right.value
        older, newer = json.loads(left.input_json), json.loads(right.input_json)
        assert older['schema'] == 'sipi.transmission-line/6' and newer['schema'] == 'sipi.transmission-line/7'
        newer['schema'] = older['schema']; assert newer == older


@pytest.mark.parametrize('version', [2, 3])
def test_old_yield_selection_does_not_silently_admit_new_study(version, monkeypatch):
    from sipi.yield_design import YieldDesignDocument
    source = yield_document().to_dict()['study']
    monkeypatch.setattr(CrossSection, 'mesh', lambda *a, **k: pytest.fail('rejection meshed'))
    with pytest.raises(ValueError, match='line-quantity-study'):
        YieldDesignDocument([dict(name='candidate', cost=1., study=source)], cost_unit='relative',
            minimum=1., minimum_yield=.8, schema=f'sipi.yield-design/{version}')
