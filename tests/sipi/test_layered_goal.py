# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved fixed-coating goals with retained search and field acceptance gates."""
import json

import numpy as np
import pytest
from scipy.linalg import expm

from sipi import CrossSection
from sipi.line_model import TransmissionLineDocument
from sipi.line_goal import seek_line_quantity
from sipi.line_goal_document import LineQuantityDesignDocument
from sipi.execution import execute_saved, normalize_saved
from sipi.line_input import _line_from_values
from test_layered_study import material
from test_line_goal_document import document as legacy


def document(quantity='impedance_real'):
    if quantity == 'differential_forward_impedance_real':
        from test_differential_goal_document import document as original
    elif quantity == 'common_forward_impedance_real':
        from test_common_forward_goal_document import document as original
    else:
        original = legacy
    raw = original().to_dict()
    names = ('positive', 'negative') if 'forward' in quantity else ('signal',)
    raw.update(schema='sipi.line-quantity-design/4', quantity=quantity,
        conductor=dict(kind='surface-boundaries', conductors={n: material() for n in names},
                       reference=material(), ground_thickness=35e-6))
    return LineQuantityDesignDocument.from_dict(raw)


@pytest.fixture(scope='module')
def scalar():
    doc = document()
    return doc, doc.solve()


def test_scalar_target_refined_and_separate_outer_gate(scalar, record_property):
    doc, result = scalar
    assert max(abs(result.residual), abs(result.refined_residual)) <= .5
    raw = result.refined_document.to_dict(); raw['cross_section']['box']['width'] *= 2
    outer = TransmissionLineDocument.from_dict(raw).analyze().propagation().z_characteristic[0, 0].real
    record_property('layered_goal_field_gates', json.dumps(dict(parameter=result.parameter,
        selected=result.value, refined=result.refined_value, outer=float(outer), target=50.,
        outer_relative_change=float(abs(outer/result.refined_value-1)))))
    assert abs(outer-result.target) <= .5
    assert abs(outer/result.refined_value-1) < .005
    for row in result.history:
        saved = json.loads(row.input_json)
        assert saved['schema'] == 'sipi.transmission-line/7'
        assert saved['conductor'] == doc.to_dict()['conductor']


def test_scalar_exact_api_replay_and_independent_transfer(scalar):
    doc, result = scalar; raw = doc.to_dict()
    direct = seek_line_quantity(lambda width: _line_from_values(raw['study'], raw['conductor'], [width],
        line_schema='sipi.transmission-line/7'), [.3e-3, .8e-3], 50., quantity='impedance_real',
        tolerance=.5, max_evaluations=24)
    assert result.history == direct.history and result.to_dict() == direct.to_dict()
    for line, value in ((result.result, result.value), (result.refined_result, result.refined_value)):
        r, l, c, g = (getattr(line, key)[0, 0, 0] for key in ('R', 'L', 'C', 'G'))
        transfer = expm(np.array([[0., r+2j*np.pi*1e9*l], [g+2j*np.pi*1e9*c, 0.]])*.003)
        assert value == pytest.approx(np.sqrt(transfer[0, 1]/transfer[1, 0]).real, rel=1e-8)


@pytest.mark.parametrize('quantity', ['differential_forward_impedance_real', 'common_forward_impedance_real'])
def test_paired_goals_use_full_forward_eigenspace_and_keep_fixed_pitch(quantity, record_property):
    doc = document(quantity); result = doc.solve()
    assert max(abs(result.residual), abs(result.refined_residual)) <= doc.to_dict()['tolerance']
    errors = []
    for line, value in ((result.result, result.value), (result.refined_result, result.refined_value)):
        r, l, c, g = (getattr(line, key)[0] for key in ('R', 'L', 'C', 'G'))
        transfer = expm(np.block([[np.zeros((2, 2)), r+2j*np.pi*1e9*l],
                                 [g+2j*np.pi*1e9*c, np.zeros((2, 2))]])*.003)
        roots, vectors = np.linalg.eig(transfer); forward = vectors[:, abs(roots) > 1]
        assert forward.shape == (4, 2)
        z = np.linalg.solve(forward[2:].T, forward[:2].T).T
        u = np.array([1., -1.]) if quantity.startswith('differential') else np.array([.5, .5])
        expected = (u@z@u).real
        errors.append(float(abs(value/expected-1)))
    assert max(errors) < 1e-10
    record_property('layered_pair_goal_transfer_error', max(errors))
    for row in result.history:
        saved = json.loads(row.input_json); traces = saved['cross_section']['traces']
        assert traces[1]['x']-traces[0]['x'] == pytest.approx(.95e-3, rel=1e-12)
        assert saved['schema'] == 'sipi.transmission-line/7'
        assert saved['conductor'] == doc.to_dict()['conductor']


def test_normalization_copy_and_budget_precede_fields(monkeypatch):
    monkeypatch.setattr(CrossSection, 'mesh', lambda *a, **k: pytest.fail('unexpected field solve'))
    doc = document(); raw = doc.to_dict(); restored = LineQuantityDesignDocument.from_dict(raw)
    raw['conductor']['reference']['coatings'][0]['conductivity'] = -1
    assert doc.dumps() == restored.dumps() == normalize_saved(doc.dumps())
    with pytest.raises(ValueError, match='max_evaluations'):
        execute_saved(doc.dumps(), max_evaluations=23)


def test_dielectric_attenuation_goal_with_fixed_coatings(record_property):
    from sipi.study import ImpedanceStudyDocument
    from sipi.dielectric import ConstantDielectric
    from test_line_goal import MESH
    source = ImpedanceStudyDocument('stripline', dict(width=.5e-3, plane_spacing=1e-3,
        thickness=50e-6, eps_r=1., box_width=4e-3), quantity='z0', frequency=1e9,
        materials={'dielectric': ConstantDielectric(4., .02)}, mesh=MESH,
        material_variables={'loss': dict(region='dielectric', path=['tan_delta'])},
        sampling=dict(kind='sweep', count=2, variables=[dict(name='loss', lower=.01, upper=.1)]))
    doc = LineQuantityDesignDocument(source, conductor=document().to_dict()['conductor'],
        quantity='attenuation', target=1., tolerance=.01, max_evaluations=24,
        schema='sipi.line-quantity-design/4')
    result = doc.solve()
    assert max(abs(result.residual), abs(result.refined_residual)) <= .01
    errors = []
    for line, value in ((result.result, result.value), (result.refined_result, result.refined_value)):
        r, l, c, g = (getattr(line, key)[0, 0, 0] for key in ('R', 'L', 'C', 'G'))
        transfer = expm(np.array([[0., r+2j*np.pi*1e9*l], [g+2j*np.pi*1e9*c, 0.]])*.003)
        expected = np.log(max(abs(np.linalg.eigvals(transfer))))/.003
        errors.append(float(abs(value/expected-1)))
    assert max(errors) < 1e-8
    record_property('layered_attenuation_transfer_error', max(errors))
    for selected in (result.document, result.refined_document):
        assert selected.to_dict()['materials']['dielectric']['parameters']['tan_delta'] == result.parameter
        assert selected.to_dict()['conductor'] == doc.to_dict()['conductor']
    assert source.to_dict()['material_evaluation']['materials']['dielectric']['parameters']['tan_delta'] == .02


def test_real_core_failure_preserves_attempt_and_original_parameter(monkeypatch):
    raw = document().to_dict()
    raw['study']['sampling']['variables'] = [dict(name='thickness', lower=1e-6, upper=50e-6)]
    doc = LineQuantityDesignDocument.from_dict(raw)
    monkeypatch.setattr(CrossSection, 'mesh', lambda *a, **k: pytest.fail('invalid core reached mesh'))
    report = execute_saved(doc.dumps())
    assert report['status'] == 'failed' and report['result'] is None
    error = report['error']
    assert error['stage'] == 'search/factory' and error['attempts'] == 1 and error['history'] == []
    assert error['failed_parameter'] == 1e-6 and error['cause_type'] == 'ValueError'
    assert report['input'] == doc.to_dict()


@pytest.mark.parametrize('version', [1, 2, 3])
def test_old_goals_do_not_admit_layered_records(version, monkeypatch):
    monkeypatch.setattr(CrossSection, 'mesh', lambda *a, **k: pytest.fail('rejection meshed'))
    raw = document().to_dict(); raw['schema'] = f'sipi.line-quantity-design/{version}'
    with pytest.raises(ValueError): LineQuantityDesignDocument.from_dict(raw)


def test_legacy_replay_retains_history_and_numeric_values(monkeypatch):
    from test_line_goal import install_fake
    install_fake(monkeypatch)
    old = legacy().to_dict(); old.update(target=2., tolerance=.01)
    new = dict(old, schema='sipi.line-quantity-design/4')
    a = LineQuantityDesignDocument.from_dict(old).solve()
    b = LineQuantityDesignDocument.from_dict(new).solve()
    assert (a.parameter, a.value, a.refined_value) == (b.parameter, b.value, b.refined_value)
    assert len(a.history) == len(b.history)
    for left, right in zip(a.history, b.history):
        older, newer = left.to_dict(), right.to_dict()
        assert older['input']['schema'] == 'sipi.transmission-line/6'
        assert newer['input']['schema'] == 'sipi.transmission-line/7'
        newer['input']['schema'] = older['input']['schema']
        assert older == newer
