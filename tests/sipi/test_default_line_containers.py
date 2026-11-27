# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved containers that admit transmission-line/8 by new versions only.

Older container versions keep refusing a nested transmission-line/8, so their
accepted documents and results are unchanged. A new version that wraps a
transmission-line/8 runs the same line document and gives the same network,
bit for bit, as that line document on its own.
"""
import json

import numpy as np
import pytest

from sipi.circuit_document import CircuitDocument
from sipi.crosssection import CrossSection
from sipi.default_line import DefaultPanelTransmissionLineDocument as Line8
from sipi.execution import execute_saved, normalize_saved, saved_schemas
from sipi.termination import terminate_network

from test_default_line import line7, line8

NEAR, FAR = 'near:signal', 'far:signal'
RLGC = dict(kind='rlgc', frequency_hz=[0, 1e6, 1e9], R=[[10]], L=[[400e-9]], G=[[0]], C=[[100e-12]],
            length_m=1, reference_ohms=50, names=['signal'])


def wrap(doc):
    return dict(kind='transmission-line', document=doc.to_dict())


def circuit(network, schema='sipi.circuit/2', excitation=None, terminations=None):
    return CircuitDocument(network, schema=schema,
                           excitation=excitation or dict(kind='sources', voltages={NEAR: 1}),
                           terminations={FAR: 100} if terminations is None else terminations)


@pytest.fixture(scope='module')
def panel():
    """A panel-default transmission-line/8 and its stand-alone result."""
    doc = line8()
    assert doc.current_method == 'panel'
    return doc, doc.analyze()


def test_circuit1_keeps_refusing_line8_before_any_solve(monkeypatch):
    monkeypatch.setattr(CrossSection, 'mesh', lambda *a, **k: pytest.fail('validation solved fields'))
    for doc in (line8(), line8(current_method='volume-p1')):
        with pytest.raises(ValueError, match='nested transmission-line/8 requires circuit/2'):
            circuit(wrap(doc), schema='sipi.circuit/1')
        text = circuit(wrap(doc)).dumps().replace('sipi.circuit/2', 'sipi.circuit/1')
        with pytest.raises(ValueError, match='nested transmission-line/8 requires circuit/2'):
            normalize_saved(text)
        with pytest.raises(ValueError, match='nested transmission-line/8 requires circuit/2'):
            CircuitDocument.loads(text)
    for schema in ('sipi.circuit/0', 'sipi.circuit/3'):
        with pytest.raises(ValueError, match='unsupported circuit schema'):
            circuit(RLGC, schema=schema)


def test_circuit2_writes_the_line8_defaults_and_normalizes_without_solving(monkeypatch):
    monkeypatch.setattr(CrossSection, 'mesh', lambda *a, **k: pytest.fail('validation solved fields'))
    assert {'sipi.circuit/1', 'sipi.circuit/2'} <= set(saved_schemas())
    doc = line8()
    raw = doc.to_dict()
    sparse = {k: v for k, v in raw.items() if k not in ('current_method', 'panel')}
    saved = circuit(dict(kind='transmission-line', document=sparse))
    data = saved.to_dict()
    assert data['schema'] == 'sipi.circuit/2' and data['network']['document'] == raw
    text = saved.dumps()
    assert normalize_saved(text) == text and CircuitDocument.loads(text).dumps() == text
    assert Line8.from_dict(data['network']['document']).dumps() == doc.dumps()


def test_circuit2_without_line8_is_circuit1_with_a_new_schema_name():
    for network in (RLGC, wrap(line7())):
        old = circuit(network, schema='sipi.circuit/1')
        new = circuit(network)
        assert new.to_dict() == dict(old.to_dict(), schema='sipi.circuit/2')
        assert new.dumps() == old.dumps().replace('"sipi.circuit/1"', '"sipi.circuit/2"')
    a, b = circuit(RLGC, schema='sipi.circuit/1').analyze(), circuit(RLGC).analyze()
    for key in ('a', 'b', 'voltage', 'current', 'network_power'):
        np.testing.assert_array_equal(getattr(a.response, key), getattr(b.response, key))


def test_circuit2_line8_is_the_standalone_line8_bit_for_bit(panel):
    doc, direct = panel
    saved = circuit(wrap(doc), terminations={FAR: 100})
    expected = terminate_network(direct.network, source_voltages={NEAR: 1}, terminations={FAR: 100})
    out = CircuitDocument.loads(saved.dumps()).analyze()
    assert out.input_json == saved.dumps()
    assert out.extraction.input_json == doc.dumps()
    np.testing.assert_array_equal(out.network.s, direct.network.s)
    np.testing.assert_array_equal(out.network.frequency, direct.network.frequency)
    np.testing.assert_array_equal(out.network.z_ref, direct.network.z_ref)
    for key in 'RLGC':
        np.testing.assert_array_equal(getattr(out.extraction, key), getattr(direct, key))
    for key in ('a', 'b', 'voltage', 'current', 'network_power'):
        np.testing.assert_array_equal(getattr(out.response, key), getattr(expected, key))


def test_circuit2_line8_execution_matches_the_line8_execution(panel):
    doc, _ = panel
    saved = circuit(wrap(doc))
    out = execute_saved(saved.dumps())
    line = execute_saved(doc.dumps())
    assert out['status'] == line['status'] == 'complete'
    assert out['input'] == saved.to_dict()
    assert out['result']['network'] == line['result']['network']
    json.dumps(out, allow_nan=False)


def test_existing_assembly_and_transformation_keep_refusing_line8(monkeypatch):
    from sipi.assembly_document import NetworkAssemblyDocument
    from sipi.network_document import NetworkTransformDocument
    monkeypatch.setattr(CrossSection, 'mesh', lambda *a, **k: pytest.fail('validation solved fields'))
    line = wrap(line8())
    assembly = dict(schema='sipi.network-assembly/1', network=line, connections=[dict(
        network=wrap(line7()), ports=[[FAR, NEAR]])])
    transform = dict(schema='sipi.network-transforms/2', network=line,
                     operations=[dict(kind='renormalize', reference_ohms=75)])
    for cls, data in ((NetworkAssemblyDocument, assembly), (NetworkTransformDocument, transform)):
        with pytest.raises(ValueError, match='nested transmission-line/8 requires'):
            cls.from_dict(data)
        for schema in ('sipi.circuit/1', 'sipi.circuit/2'):
            kind = 'network-assembly' if cls is NetworkAssemblyDocument else 'network-transform'
            with pytest.raises(ValueError, match='nested transmission-line/8 requires'):
                circuit(dict(kind=kind, document=data), schema=schema)
