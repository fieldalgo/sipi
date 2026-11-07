# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved periodic requests, canonical replay, explicit ports and pre-field guards."""
import json
from types import SimpleNamespace

import numpy as np
import pytest

from sipi import (CrossSectionDocument, LineNetwork, LumpedNetworkDocument,
    NetworkAssemblyDocument, NetworkTransformDocument, microstrip, coupled_microstrip,
    periodic_response, periodic_impulse, rlgc_network)
from sipi.circuit_document import _network_input
from sipi.execution import execute_saved, normalize_saved
from sipi.line_model import TransmissionLineDocument
from sipi.volume_line import VolumeLineDocument
from sipi.periodic_document import PeriodicNetworkDocument

FREQUENCY = [0., 1e8, 2e8]


def rlgc():
    return dict(kind='rlgc', frequency_hz=FREQUENCY, R=[[10.]], L=[[250e-9]],
        G=[[.001]], C=[[100e-12]], length_m=.03, reference_ohms=50., names=['s'])


def field(kind='transmission-line', *, pair=False):
    kwargs = dict(width=.4e-3, substrate_height=.5e-3, thickness=.1e-3,
                  eps_r=4., air_height=.5e-3, box_width=3e-3)
    section = coupled_microstrip(gap=.3e-3, **kwargs) if pair else microstrip(**kwargs)
    cross = CrossSectionDocument(section, mesh=dict(edge_size=20e-6, far_size=.2e-3, grade=.2))
    if kind == 'transmission-line':
        inner = TransmissionLineDocument(cross, FREQUENCY, materials={},
                                          conductor={'kind': 'perfect'}, length=.02)
    else:
        inner = VolumeLineDocument(CrossSectionDocument(section), FREQUENCY, materials={}, conductivity=58e6, length=.02,
            mesh=dict(ground_thickness=.1e-3, padding=2e-3, metal_size=50e-6,
                      far_size=.5e-3, grade=.2, min_angle=28))
    return dict(kind=kind, document=inner.to_dict())


def source(kind):
    if kind == 'rlgc': return rlgc()
    if kind in ('transmission-line', 'volume-line'): return field(kind)
    if kind == 'touchstone':
        rng = np.random.default_rng(124)
        s = .1*(rng.normal(size=(3, 3, 3))+1j*rng.normal(size=(3, 3, 3)))
        s[0] = s[0].real
        net = LineNetwork(FREQUENCY, s, [25., 60., 80.], ('x', 'z', 'y'))
        return dict(kind=kind, text=net.touchstone(), ports=3, port_names=list(net.port_names))
    if kind == 'lumped-network':
        return dict(kind=kind, document=LumpedNetworkDocument(FREQUENCY,
                    resistance=10., inductance=2e-9).to_dict())
    if kind == 'network-transform':
        return dict(kind=kind, document=NetworkTransformDocument(rlgc(), operations=[
            dict(kind='renormalize', reference_ohms=[30., 70.])]).to_dict())
    inner = source('lumped-network')
    return dict(kind='network-assembly', document=NetworkAssemblyDocument(inner,
        connections=[dict(network=dict(kind='lumped-network',document=LumpedNetworkDocument(
            FREQUENCY, resistance=20., port_names=('in', 'out')).to_dict()),
            ports=[['far', 'in']])]).to_dict())


KINDS = ['rlgc', 'touchstone', 'lumped-network', 'network-transform',
         'network-assembly', 'transmission-line', 'volume-line']


def document(kind='rlgc', *, pair=False, basis='single-ended', impulse=True):
    raw = field(pair=True) if pair else source(kind)
    _, _, _, names = _network_input(raw)
    if basis == 'mixed-mode': names = ('d_near', 'd_far', 'c_near', 'c_far')
    # Reversed insertion order makes accidental dictionary order observable.
    incident = {name: (.2*np.arange(5)+i).tolist() for i, name in reversed(list(enumerate(names)))}
    return PeriodicNetworkDocument(raw, incident=incident, basis=basis, include_impulse=impulse)


def decoded(value):
    return np.array(value['real'])+1j*np.array(value['imag'])


@pytest.mark.parametrize('kind', KINDS)
def test_all_source_kinds_normalize_without_fields(kind, monkeypatch):
    def forbidden(*args, **kwargs): pytest.fail('normalization solved fields')
    monkeypatch.setattr(TransmissionLineDocument, 'analyze', forbidden)
    monkeypatch.setattr(VolumeLineDocument, 'analyze', forbidden)
    doc = document(kind)
    restored = PeriodicNetworkDocument.loads(doc.dumps())
    assert doc.sample_count == 5
    assert normalize_saved(doc.dumps()) == restored.dumps() == doc.dumps()
    data = restored.to_dict(); data['incident'].clear()
    assert restored.to_dict()['incident']


@pytest.mark.parametrize('kind', KINDS[:5])
@pytest.mark.parametrize('impulse', [False, True])
def test_network_sources_direct_and_saved_replay(kind, impulse):
    doc = document(kind, impulse=impulse)
    source_obj, _, _, _ = _network_input(doc.to_dict()['network'])
    original = source_obj if isinstance(source_obj, LineNetwork) else source_obj.analyze().network
    a = np.column_stack([doc.to_dict()['incident'][name] for name in original.port_names])
    expected = periodic_response(original, a)
    actual = PeriodicNetworkDocument.loads(doc.dumps()).analyze(max_evaluations=5)
    assert actual.input_json == doc.dumps()
    assert actual.network.port_names == original.port_names
    for key in ('time', 'incident', 'reflected', 'voltage', 'current', 'z_ref'):
        np.testing.assert_array_equal(getattr(actual.response, key), getattr(expected, key))
    np.testing.assert_array_equal(actual.source_network.s, original.s)
    output = execute_saved(doc.dumps(), max_evaluations=5)
    assert output['status'] == 'complete' and output['error'] is None
    assert output['input'] == doc.to_dict()
    assert output['result']['coverage'] == 'sampled-periodic-steady-state'
    np.testing.assert_array_equal(decoded(output['result']['network']['s']), original.s)
    for key, field_name in [('incident_sqrt_w', 'incident'), ('reflected_sqrt_w', 'reflected'),
                            ('voltage_v', 'voltage'), ('current_a', 'current'), ('time_s', 'time')]:
        np.testing.assert_array_equal(output['result']['response'][key], getattr(expected, field_name))
    if impulse:
        expected_h = periodic_impulse(original)
        np.testing.assert_array_equal(actual.impulse.weights, expected_h.weights)
        np.testing.assert_array_equal(output['result']['impulse']['weights'], expected_h.weights)
    else:
        assert actual.impulse is None and output['result']['impulse'] is None
    json.dumps(output, allow_nan=False)


@pytest.mark.parametrize('pair', [False, True])
def test_real_pec_field_direct_and_mixed_saved_response(pair, monkeypatch):
    doc = document(pair=pair, kind='transmission-line', basis='mixed-mode' if pair else 'single-ended')
    inner = TransmissionLineDocument.from_dict(doc.to_dict()['network']['document'])
    direct = inner.analyze()
    count = []
    original_analyze = TransmissionLineDocument.analyze
    def counted(self):
        count.append(self.dumps())
        return original_analyze(self)
    monkeypatch.setattr(TransmissionLineDocument, 'analyze', counted)
    result = doc.analyze(max_evaluations=5)
    assert count == [inner.dumps()]
    assert result.extraction.input_json == inner.dumps()
    network = direct.network.mixed_mode() if pair else direct.network
    np.testing.assert_allclose(result.network.s, network.s, atol=1e-12, rtol=0)
    a = np.column_stack([doc.to_dict()['incident'][name] for name in network.port_names])
    expected = periodic_response(network, a)
    for key in ('reflected', 'voltage', 'current'):
        np.testing.assert_allclose(getattr(result.response, key), getattr(expected, key), atol=1e-12, rtol=0)
    assert result.response.basis == doc.to_dict()['basis']


@pytest.mark.parametrize('kind', ['transmission-line', 'volume-line'])
def test_budget_before_field_or_fft_and_one_extract(kind, monkeypatch):
    doc = document(kind)
    cls = TransmissionLineDocument if kind == 'transmission-line' else VolumeLineDocument
    calls = []
    names = _network_input(doc.to_dict()['network'])[3]
    net = LineNetwork(FREQUENCY, np.zeros((3, len(names), len(names))), 50., names)
    def fake(self):
        calls.append(self.dumps()); return SimpleNamespace(network=net)
    monkeypatch.setattr(cls, 'analyze', fake)
    for execute in (lambda: doc.analyze(max_evaluations=4),
                    lambda: execute_saved(doc.dumps(), max_evaluations=4)):
        with pytest.raises(ValueError, match='before field/FFT'): execute()
    assert calls == []
    result = doc.analyze(max_evaluations=5)
    assert len(calls) == 1 and result.extraction.network is net


@pytest.mark.parametrize('change', ['frequency', 'ports', 'refs', 'basis', 'dc'])
def test_post_extraction_identity_and_dc_guards(change, monkeypatch):
    doc = document('transmission-line')
    names = _network_input(doc.to_dict()['network'])[3]
    frequency = np.array(FREQUENCY)
    refs = np.full(len(names), 50.)
    s = np.zeros((3, len(names), len(names)), complex)
    basis = 'single-ended'
    if change == 'frequency': frequency *= 2
    elif change == 'ports': names = tuple(reversed(names))
    elif change == 'refs': refs[0] = 75.
    elif change == 'basis': basis = 'mixed-mode'
    else: s[0, 0, 0] = 1e-20j
    net = LineNetwork(frequency, s, refs, names, basis)
    monkeypatch.setattr(TransmissionLineDocument, 'analyze', lambda self: SimpleNamespace(network=net))
    with pytest.raises(ValueError, match='exactly real' if change == 'dc' else 'changed the saved'):
        doc.analyze()


@pytest.mark.parametrize('mutate', [
    lambda d: d.update(schema='sipi.periodic-network/2'),
    lambda d: d.update(extra=1), lambda d: d.pop('basis'),
    lambda d: d.update(include_impulse=1), lambda d: d.update(basis='unknown'),
    lambda d: d.update(basis='mixed-mode'),
    lambda d: d['incident'].pop('near:s'),
    lambda d: d['incident'].update(unknown=[0]*5),
    lambda d: d['incident'].update({'near:s': [0]*4}),
    lambda d: d['incident'].update({'near:s': [False]*5}),
    lambda d: d['incident'].update({'near:s': ['0']*5}),
    lambda d: d['incident'].update({'near:s': [float('nan')]*5}),
    lambda d: d['network'].update(frequency_hz=[1,2,3]),
    lambda d: d['network'].update(frequency_hz=[0,1,3]),
    lambda d: d['network'].update(kind='periodic-network'),
])
def test_strict_invalid_inputs(mutate):
    data = document().to_dict(); mutate(data)
    with pytest.raises(ValueError): PeriodicNetworkDocument.from_dict(data)


def test_duplicate_and_overflow_json_and_known_complex_dc():
    text = document().dumps()
    with pytest.raises(ValueError): PeriodicNetworkDocument.loads(text.replace('"basis":', '"basis":"single-ended", "basis":', 1))
    for number in ('NaN', 'Infinity', '1e999'):
        with pytest.raises(ValueError): PeriodicNetworkDocument.loads(text.replace('0.0', number, 1))
    net = LineNetwork([0,1], [[[.1j]], [[.2]]], [50.], ('p',))
    raw = dict(kind='touchstone', text=net.touchstone(), ports=1, port_names=['p'])
    with pytest.raises(ValueError, match='exactly real'):
        PeriodicNetworkDocument(raw, incident={'p':[0,0,0]})


@pytest.mark.parametrize('bad', [True, 1, 10001, 3.5])
def test_invalid_budgets_and_diagnostics(bad):
    doc = document()
    with pytest.raises(ValueError): doc.analyze(max_evaluations=bad)
    with pytest.raises(ValueError): execute_saved(doc.dumps(), max_evaluations=bad)
    with pytest.raises(ValueError, match='top-level'):
        execute_saved(doc.dumps(), diagnostics=['characteristic'])
