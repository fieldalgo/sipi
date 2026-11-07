# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Distinct modes against independent scalar circuits, exact crossings and power."""
from dataclasses import replace
import importlib.metadata as metadata

import numpy as np
import pytest
from scipy.linalg import expm
from scipy.spatial.transform import Rotation

from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import (rlgc_modes, ModeTrackingError, rlgc_characteristic, rlgc_propagation,
                  CrossSection, CrossSectionDocument, coupled_microstrip)
from sipi.dielectric import PrincipalAxisDielectric, DebyeDielectric, ConstantDielectric
from sipi.line_model import TransmissionLineDocument
from sipi.volume_line import VolumeLineDocument
from test_characteristic_matrix import D, T, F, transformed, arbitrary_matrices, relative


@pytest.mark.parametrize('lossless', [False, True])
def test_tracked_modes_against_independent_scalar_media_and_power(lossless):
    tool = require_tool('scikit-rf'); clock = Stopwatch()
    diagonal = dict(D, R=np.zeros(3), G=np.zeros(3)) if lossless else D
    values = transformed(diagonal)
    with clock('openphysics'):
        result = rlgc_modes(F, **values, names=('first', 'second', 'third'))
    with clock('reference'):
        media = [tool.media.DistributedCircuit(tool.Frequency.from_f(F, unit='Hz'),
            **{key: value[i] for key, value in diagonal.items()}) for i in range(3)]
        gamma = np.array([m.gamma for m in media]).T
        zc = np.array([m.z0 for m in media]).T
        order = np.lexsort((gamma[0].real, gamma[0].imag))
        gamma, zc = gamma[:, order], zc[:, order]
        modal_voltage = np.sqrt(2/(1/zc).real)
        modal_current = modal_voltage/zc
        ar = .25*abs(modal_current)**2*diagonal['R'][order]
        ag = .25*modal_voltage**2*diagonal['G'][order]
    gamma_error = relative(result.gamma, gamma)
    assert gamma_error < 1e-10
    np.testing.assert_allclose(result.alpha_conductor, ar, rtol=1e-10, atol=1e-12)
    np.testing.assert_allclose(result.alpha_dielectric, ag, rtol=1e-10, atol=1e-12)
    np.testing.assert_allclose(result.overlap, 1, rtol=0, atol=1e-10)
    powers = .5*np.einsum('fij,fij->fj', result.voltage.conj(), result.current).real
    np.testing.assert_allclose(powers, 1, rtol=0, atol=1e-10)
    errors = []
    for k in range(len(F)):
        actual = result.voltage[k]@np.diag(np.exp(-result.gamma[k]*.02))@np.linalg.inv(result.voltage[k])
        expected = T@np.diag(np.exp(-np.array([m.gamma[k] for m in media])*.02))@np.linalg.inv(T)
        errors.append(relative(actual, expected))
        for j in range(3):
            v, i = result.voltage[k, :, j], result.current[k, :, j]
            assert .25*(i.conj()@values['R']@i+v.conj()@values['G']@v).real == pytest.approx(
                result.gamma[k, j].real, abs=1e-10)
    assert max(errors) < 1e-10
    record = make_record(case='tracked-three-modes-'+('lossless' if lossless else 'lossy'),
        physics='distinct forward modes and single-mode attenuation contributions', api='sipi.rlgc_modes',
        discretization='characteristic eigensystem, one-watt normalization and power-metric assignment',
        tool='scikit-rf', tool_discretization='independent DistributedCircuit modes under known nonorthogonal transform',
        matched=['RLGC, frequencies, power-dual conductor coordinates and line length'],
        not_matched=['no physical field, measured coupon or degenerate-mode continuation'],
        observables=[observable('modal gamma', '1/m', 'max relative difference', gamma_error, 1e-10),
                     observable('forward transfer', '1', 'max relative difference', max(errors), 1e-10)],
        analytical_acceptance='one-watt modes, exact per-mode conductor/dielectric power identity and crossing labels',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi', version=metadata.version('sipi')); emit(record)
    if lossless:
        np.testing.assert_array_equal(result.alpha_conductor, 0)
        np.testing.assert_array_equal(result.alpha_dielectric, 0)


def test_single_mode_matches_existing_propagation_and_losses():
    values = dict(R=[[2]], L=[[300e-9]], G=[[.003]], C=[[100e-12]])
    actual = rlgc_modes(F, **values); old = rlgc_propagation(F, **values)
    np.testing.assert_allclose(actual.gamma, old.gamma, rtol=1e-12)
    np.testing.assert_allclose(actual.alpha_conductor, old.alpha_conductor, rtol=1e-12)
    np.testing.assert_allclose(actual.alpha_dielectric, old.alpha_dielectric, rtol=1e-12)


def test_crossing_between_samples_keeps_conductor_mode_labels():
    f = np.array([1e9, 2e9, 3e9])
    c = np.array([np.diag(row) for row in ([60, 140], [90, 110], [130, 70])])*1e-12
    values = dict(R=np.eye(2)*2, L=np.eye(2)*300e-9, G=np.zeros((2, 2)), C=c)
    result = rlgc_modes(f, **values)
    expected = np.sqrt((2+2j*np.pi*f[:, None]*300e-9)*(2j*np.pi*f[:, None]*c.diagonal(axis1=1, axis2=2)))
    np.testing.assert_allclose(result.gamma, expected, rtol=1e-12)
    assert result.gamma[0, 0].imag < result.gamma[0, 1].imag
    assert result.gamma[-1, 0].imag > result.gamma[-1, 1].imag
    np.testing.assert_allclose(result.overlap, 1, atol=1e-12)


@pytest.mark.parametrize('delta', [0, 1e-10])
def test_repeated_or_near_roots_rejected_without_changing_matrix_api(delta):
    l = np.array([200, 300, 400])*1e-9
    c = 4e-17/l; c[1] *= 1+delta
    values = transformed(dict(R=np.zeros(3), L=l, G=np.zeros(3), C=c))
    rlgc_characteristic(F, **values)
    with pytest.raises(ModeTrackingError, match='unresolved') as caught:
        rlgc_modes(F, **values)
    assert caught.value.index == 0 and caught.value.frequency == F[0]


def rotating_matrices(transforms):
    n = len(transforms[0]); d = np.arange(1, n+1)*5e-9
    # All uncoupled characteristic impedances are 50 ohms: overlap metric is scalar.
    diagonal = dict(R=np.zeros(n), L=50*d, G=np.zeros(n), C=d/50)
    return {key: np.array([transformed(diagonal, t)[key] for t in transforms]) for key in diagonal}


def test_ambiguous_rotation_requires_finer_frequency_grid():
    def rotate(angle):
        c, s = np.cos(angle), np.sin(angle)
        return np.array([[c, -s], [s, c]])
    with pytest.raises(ModeTrackingError, match='ambiguous') as caught:
        rlgc_modes([1e9, 2e9], **rotating_matrices([np.eye(2), rotate(np.pi/4)]))
    assert caught.value.index == 1 and caught.value.frequency == 2e9
    result = rlgc_modes([1e9, 1.5e9, 2e9], **rotating_matrices([np.eye(2), rotate(np.pi/8), rotate(np.pi/4)]))
    np.testing.assert_allclose(result.overlap[1:], np.cos(np.pi/8), atol=1e-10)


def test_unique_but_low_overlap_is_rejected():
    transform = Rotation.from_rotvec(np.ones(3)/np.sqrt(3)*(np.pi/3+.02)).as_matrix()
    with pytest.raises(ModeTrackingError, match='overlap below'):
        rlgc_modes([1e9, 2e9], **rotating_matrices([np.eye(3), transform]))


def test_noncommuting_forms_phase_alignment_and_block_telegrapher():
    values = arbitrary_matrices()
    f = np.logspace(4, 8, 13)
    result = rlgc_modes(f, **values)
    characteristic = rlgc_characteristic(f, **values)
    for k, hz in enumerate(f):
        v, i, gamma = result.voltage[k], result.current[k], result.gamma[k]
        z = values['R']+2j*np.pi*hz*values['L']; y = values['G']+2j*np.pi*hz*values['C']
        block = np.block([[np.zeros_like(z), -z], [-y, np.zeros_like(z)]])
        exact = expm(block*.01)@np.vstack([v, i])
        np.testing.assert_allclose(exact, np.vstack([v, i])*np.exp(-gamma*.01), rtol=1e-10, atol=1e-12)
        if k:
            a, b = characteristic.y_characteristic[k-1:k+1]
            h = .25*(a+a.conj().T+b+b.conj().T)
            inner = np.einsum('ij,ij->j', result.voltage[k-1].conj(), h@v)
            assert np.max(abs(inner.imag)) < 1e-10 and np.all(inner.real > 0)


def test_power_dual_coordinate_covariance_and_read_only_results():
    f = np.logspace(4, 8, 13); values = arbitrary_matrices()
    original = rlgc_modes(f, **values)
    inverse = np.linalg.inv(T)
    changed = {key: (T@a@T.T if key in ('R', 'L') else inverse.T@a@inverse) for key, a in values.items()}
    result = rlgc_modes(f, **changed)
    for key in ('gamma', 'alpha_conductor', 'alpha_dielectric', 'overlap', 'assignment_gap'):
        np.testing.assert_allclose(getattr(result, key), getattr(original, key), rtol=1e-10, atol=1e-10)
        assert not getattr(result, key).flags.writeable
    for key in ('frequency', 'voltage', 'current'):
        assert not getattr(result, key).flags.writeable
    before = result.frequency.copy(); f[:] = 7; changed['R'][:] = 0
    np.testing.assert_array_equal(result.frequency, before)
    with pytest.raises(ValueError, match='one watt'):
        replace(result, voltage=2*result.voltage)
    with pytest.raises(ValueError):
        replace(result, alpha_conductor=-result.alpha_conductor)
    with pytest.raises(ValueError):
        replace(result, gamma=-result.gamma)
    with pytest.raises(ValueError, match='must be real'):
        replace(result, alpha_conductor=result.alpha_conductor+1j)


@pytest.mark.parametrize('bad', [[], [0], [-1], [1, 1], [True], [1, np.inf]])
def test_invalid_frequency_rejected(bad):
    with pytest.raises(ValueError):
        rlgc_modes(bad, **arbitrary_matrices())


@pytest.mark.parametrize('kind', ['shared', 'volume'])
def test_actual_asymmetric_material_line_modes_need_no_additional_field_solve(kind, monkeypatch):
    section = coupled_microstrip(width=.4e-3, gap=.2e-3, substrate_height=.5e-3,
        thickness=.1e-3, eps_r=4, air_height=.5e-3, box_width=2e-3)
    model = PrincipalAxisDielectric(DebyeDielectric(2, [2], [1e4]), ConstantDielectric(5, .02), .4)
    f = np.logspace(3, 5, 5)
    if kind == 'shared':
        doc = TransmissionLineDocument(CrossSectionDocument(section,
            mesh=dict(edge_size=10e-6, far_size=.25e-3, grade=.2)), f,
            materials={'substrate': model}, conductor={'kind': 'perfect'}, length=.01)
    else:
        doc = VolumeLineDocument(CrossSectionDocument(section), f, materials={'substrate': model},
            conductivity=58e6, length=.01, mesh=dict(ground_thickness=.1e-3, padding=2e-3,
                metal_size=50e-6, far_size=.5e-3, grade=.2, min_angle=28))
    line = doc.analyze()
    def forbidden(*a, **kw):
        pytest.fail('modal diagnostics started another field solve')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    monkeypatch.setattr('sipi.volume_line.mesh_conductor_section', forbidden)
    result = line.modes()
    direct = rlgc_modes(line.frequency, R=line.R, L=line.L, G=line.G, C=line.C, names=line.names)
    np.testing.assert_array_equal(result.gamma, direct.gamma)
    np.testing.assert_allclose(result.alpha_conductor+result.alpha_dielectric, result.gamma.real, rtol=1e-10, atol=1e-10)
    assert result.names == line.names
