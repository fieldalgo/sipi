# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved scalar loss inversion preserves original samples, budgets and network replay."""
import numpy as np
import pytest

from sipi import infer_shunt_loss, rlgc_network, rlgc_propagation
from sipi.execution import execute_saved, normalize_saved
from sipi.loss_inference_document import ShuntLossInferenceDocument


def document(alpha=None):
    return ShuntLossInferenceDocument([1e8, 1e9], alpha=[.2, 2.] if alpha is None else alpha,
        R=2., L=400e-9, C=150e-12, max_error_np_per_m=1e-9)


def test_roundtrip_normalization_has_no_solver_and_copies_inputs(monkeypatch):
    import sipi.loss_inference as implementation
    def fail(*a, **k): pytest.fail('normalization solved')
    monkeypatch.setattr(implementation, 'brentq', fail)
    monkeypatch.setattr(implementation, 'rlgc_propagation', fail)
    data = document().to_dict()
    doc = ShuntLossInferenceDocument.from_dict(data)
    saved = doc.dumps()
    assert len(data) == 7 and data['R_ohm_per_m'] == [2., 2.]
    assert normalize_saved(saved) == ShuntLossInferenceDocument.loads(saved).dumps() == saved
    data['R_ohm_per_m'][0] = -1
    doc.to_dict()['alpha_np_per_m'].clear()
    assert doc.dumps() == saved


@pytest.mark.parametrize('compatible', [True, False])
def test_saved_and_common_results_retain_candidate_and_acceptance(compatible):
    alpha = [.2, 2.] if compatible else [0., 0.]
    doc = document(alpha)
    direct = infer_shunt_loss([1e8, 1e9], alpha=alpha, R=2., L=400e-9, C=150e-12,
                             max_error_np_per_m=1e-9)
    assert ShuntLossInferenceDocument.loads(doc.dumps()).analyze().to_dict() == direct.to_dict()
    output = execute_saved(doc.dumps())
    assert output['status'] == 'complete' and output['error'] is None
    assert output['input'] == doc.to_dict() and output['result'] == direct.to_dict()
    assert output['result']['accepted'] is compatible


def test_budget_precedes_solving_and_actual_bracket_failure_propagates(monkeypatch):
    import sipi.loss_inference_document as implementation
    data = document().to_dict()
    data.update(frequency_hz=[1, 2], alpha_np_per_m=[1e100]*2,
                R_ohm_per_m=0., L_h_per_m=1., C_f_per_m=1.)
    with pytest.raises(RuntimeError, match='bracket'):
        execute_saved(ShuntLossInferenceDocument.from_dict(data).dumps())
    monkeypatch.setattr(implementation, 'infer_shunt_loss', lambda *a, **k: pytest.fail('budget allowed solve'))
    doc = ShuntLossInferenceDocument([1, 2, 3], alpha=[1]*3, R=0, L=1, C=1, max_error_np_per_m=1e-9)
    with pytest.raises(ValueError, match='max_evaluations'):
        execute_saved(doc.dumps(), max_evaluations=2)


@pytest.mark.parametrize('change', [dict(schema='sipi.shunt-loss-inference/2'), dict(extra=1),
    dict(frequency_hz=[0, 1e9]), dict(alpha_np_per_m=1), dict(alpha_np_per_m=[-1, 0]),
    dict(R_ohm_per_m=None), dict(L_h_per_m=True), dict(C_f_per_m=[1]),
    dict(C_f_per_m=0), dict(max_error_np_per_m=0), dict(alpha_np_per_m=[float('nan')]*2)],
    ids=['version', 'extra', 'dc', 'scalar-alpha', 'negative-alpha', 'null-r', 'bool-l', 'short-c',
         'zero-c', 'zero-limit', 'nan-alpha'])
def test_invalid_saved_fields_rejected(change):
    data = document().to_dict(); data.update(change)
    with pytest.raises(ValueError): ShuntLossInferenceDocument.from_dict(data)


@pytest.mark.parametrize('key', list(document().to_dict()))
def test_each_saved_field_is_required(key):
    data = document().to_dict(); data.pop(key)
    with pytest.raises(ValueError): ShuntLossInferenceDocument.from_dict(data)


def test_duplicate_and_nonfinite_json_rejected():
    text = document().dumps()
    with pytest.raises(ValueError):
        ShuntLossInferenceDocument.loads(text.replace('"max_error_np_per_m": 1e-09',
            '"max_error_np_per_m": 1e-09, "max_error_np_per_m": 1'))
    with pytest.raises(ValueError):
        ShuntLossInferenceDocument.loads(text.replace('1e-09', 'Infinity'))


def test_inferred_conductance_replays_finite_network_and_preserves_passivity():
    f = np.geomspace(1e5, 1e10, 21)
    r, l, c = 50+2*np.sqrt(f/1e9), np.full(len(f), 400e-9), np.full(len(f), 150e-12)
    g = 2*np.pi*f*c*.02
    matrices = {k: v[:, None, None] for k, v in (('R', r), ('L', l), ('C', c), ('G', g))}
    p = rlgc_propagation(f, **matrices)
    doc = ShuntLossInferenceDocument(f, alpha=p.alpha[:, 0], R=r, L=l, C=c, max_error_np_per_m=1e-9)
    output = execute_saved(doc.dumps())['result']
    inferred = np.array(output['G_s_per_m'])[:, None, None]
    original = rlgc_network(f, **matrices, length=.03, z_ref=50.)
    replay = rlgc_network(f, **(matrices | dict(G=inferred)), length=.03, z_ref=50.)
    np.testing.assert_allclose(replay.s, original.s, rtol=1e-9, atol=1e-12)
    assert np.max(np.linalg.svd(replay.s, compute_uv=False)) <= 1+1e-12
    # Finite-line reflections make -log|S21|/length a different observable.
    assert np.max(abs(-np.log(abs(original.s[:, 1, 0]))/.03-p.alpha[:, 0])) > 1e-3
