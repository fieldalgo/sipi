# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""PSD material validation is invariant under a positive cell-unit scale."""
import numpy as np
import pytest
import sipi


def response(kind, negative=None):
    signals = int(kind) if kind in ('3', '4') else 2
    first = np.zeros((signals, signals)); first[:2, :2] = [[80., -40.], [-40., 20.]]
    second = np.zeros_like(first); second[:2, :2] = [[32., 32.], [32., 32.]]
    if negative is not None:
        first = np.diag([80., negative]+[0.]*(signals-2))
    time = np.linspace(0., 4e-9, 41)
    drive = np.minimum(time/1e-9, 1.)[:, None]*np.array([1., -.4, .2, -.1])[:signals]
    options = dict(R=np.eye(signals)*20., L=np.eye(signals)*450e-9,
        G=np.eye(signals)*.002, C_inf=np.eye(signals)*210e-12,
        delta_C=np.array([first, second])*1e-12, relaxation_hz=[1e9, 1e8],
        length=.1, cells=4, source_resistance=[25.]*signals, load_resistance=[100.]*signals)
    function = sipi.psd_coupled_debye_rlgc_ladder_response
    if signals != 2:
        function = sipi.psd_multiconductor_debye_rlgc_ladder_response
        options['signals'] = signals
    elif kind == 'capacitive':
        function = sipi.psd_coupled_debye_capacitive_ladder_response
        options['load_capacitance'] = np.eye(2)*20e-12
    elif kind == 'reactive':
        function = sipi.psd_coupled_debye_reactive_ladder_response
        options.update(load_capacitance=np.eye(2)*20e-12,
                       load_branch_resistance=np.eye(2)*50., load_branch_inductance=np.eye(2)*5e-9)
    return function(time, drive, **options)


@pytest.mark.parametrize('kind', ['resistive', 'capacitive', 'reactive', '3', '4'])
def test_roundoff_in_unscaled_null_eigenvalue_does_not_change_physical_response(kind, monkeypatch):
    expected = response(kind)
    original = np.linalg.eigvalsh
    unscaled_null_queries = []

    def backend(matrix, *args, **kwargs):
        eigen = original(matrix, *args, **kwargs)
        scale = np.max(abs(matrix))
        # Model the backend-dependent sign of an exact zero in a dimensional
        # rank-deficient matrix. Normalized input validation remains untouched.
        if scale not in (0., 1.) and eigen[0] == 0 and eigen[-1] > 0:
            unscaled_null_queries.append(scale)
            eigen[0] = -np.finfo(float).eps*eigen[-1]
        return eigen

    monkeypatch.setattr(np.linalg, 'eigvalsh', backend)
    actual = response(kind)
    assert unscaled_null_queries == []
    assert actual.to_dict(include_states=True) == expected.to_dict(include_states=True)
    assert actual.power_balance_relative_error <= 1e-10
    assert actual.total_power_balance_relative_error <= 1e-10
    assert np.min(actual.relaxation_loss) >= 0


@pytest.mark.parametrize('kind', ['resistive', 'capacitive', 'reactive', '3', '4'])
@pytest.mark.parametrize('negative', [-1e-13, -1e-20])
def test_negative_input_is_still_rejected_without_clipping_or_tolerance(kind, negative):
    with pytest.raises(ValueError, match='positive semidefinite'):
        response(kind, negative)
