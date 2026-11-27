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


def assembly(network, schema='sipi.network-assembly/2', other=None):
    from sipi.assembly_document import NetworkAssemblyDocument
    return NetworkAssemblyDocument(network, schema=schema, connections=[dict(
        network=network if other is None else other, ports=[[FAR, NEAR]])])


def transforms(network, schema='sipi.network-transforms/3', operations=None):
    from sipi.network_document import NetworkTransformDocument
    return NetworkTransformDocument(network, schema=schema,
        operations=operations or [dict(kind='renormalize', reference_ohms=75)])


def test_new_assembly_and_transformation_versions_admit_line8_without_solving(monkeypatch):
    monkeypatch.setattr(CrossSection, 'mesh', lambda *a, **k: pytest.fail('validation solved fields'))
    assert {'sipi.network-assembly/2', 'sipi.network-transforms/3'} <= set(saved_schemas())
    doc = line8()
    raw = doc.to_dict()
    sparse = dict(kind='transmission-line',
                  document={k: v for k, v in raw.items() if k not in ('current_method', 'panel')})
    for saved in (assembly(sparse), transforms(sparse),
                  transforms(dict(kind='network-assembly', document=assembly(sparse).to_dict()))):
        text = saved.dumps()
        assert normalize_saved(text) == text and type(saved).loads(text).dumps() == text
        assert json.loads(text)['schema'] in ('sipi.network-assembly/2', 'sipi.network-transforms/3')
        assert raw in (json.loads(text)['network'].get('document'),
                       json.loads(text)['network'].get('document', {}).get('network', {}).get('document'))
    # Gated schemas stay refused where they were refused before.
    with pytest.raises(ValueError, match='nested network-assembly/2 requires'):
        transforms(dict(kind='network-assembly', document=assembly(sparse).to_dict()),
                   schema='sipi.network-transforms/2')
    for schema in ('sipi.network-transforms/1', 'sipi.network-transforms/2'):
        with pytest.raises(ValueError, match='nested transmission-line/8 requires'):
            transforms(sparse, schema=schema)
    with pytest.raises(ValueError, match='nested transmission-line/8 requires'):
        transforms(wrap(line7()), operations=[dict(kind='cascade', side='right', network=sparse)],
                   schema='sipi.network-transforms/2')
    for kind, nested in (('network-assembly', assembly(RLGC)), ('network-transform', transforms(RLGC))):
        with pytest.raises(ValueError, match=f'nested {nested.to_dict()["schema"][5:]} requires'):
            circuit(dict(kind=kind, document=nested.to_dict()), schema='sipi.circuit/1')


def test_new_versions_without_line8_are_the_old_versions_with_a_new_schema_name():
    pairs = ((assembly(RLGC, schema='sipi.network-assembly/1'), assembly(RLGC)),
             (transforms(RLGC, schema='sipi.network-transforms/2'), transforms(RLGC)),
             (transforms(RLGC, schema='sipi.network-transforms/2',
                         operations=[dict(kind='cascade', side='right', network=RLGC)]),
              transforms(RLGC, operations=[dict(kind='cascade', side='right', network=RLGC)])))
    for old, new in pairs:
        o, n = old.to_dict(), new.to_dict()
        assert n == dict(o, schema=n['schema'])
        np.testing.assert_array_equal(old.analyze().network.s, new.analyze().network.s)


def test_assembly2_and_transforms3_with_line8_are_the_standalone_line8_bit_for_bit(panel):
    from sipi.connection import connect_networks
    doc, direct = panel
    line = wrap(doc)
    saved = assembly(line)
    names = saved.to_dict()['connections'][0]['port_names']
    joined = connect_networks(direct.network, direct.network, [[FAR, NEAR]], port_names=names)
    out = type(saved).loads(saved.dumps()).analyze()
    np.testing.assert_array_equal(out.network.s, joined.s)
    for network in out.source_networks:
        np.testing.assert_array_equal(network.s, direct.network.s)
    assert all(e.input_json == doc.dumps() for e in out.extractions)
    renormalized = transforms(line).analyze()
    np.testing.assert_array_equal(renormalized.network.s, direct.network.renormalized(75).s)
    np.testing.assert_array_equal(renormalized.source_network.s, direct.network.s)
    nested = transforms(dict(kind='network-assembly', document=saved.to_dict())).analyze()
    np.testing.assert_array_equal(nested.network.s, joined.renormalized(75).s)
    wrapped = circuit(dict(kind='network-assembly', document=saved.to_dict())).analyze()
    expected = terminate_network(joined, source_voltages={NEAR: 1}, terminations={FAR: 100})
    for key in ('a', 'b', 'voltage', 'current', 'network_power'):
        np.testing.assert_array_equal(getattr(wrapped.response, key), getattr(expected, key))


TWO = (1e9, 3e9)
LIMITS = [dict(name='loss', input_port=NEAR, output_port=FAR, frequency_hz=list(TWO), minimum=.5, maximum=None)]


@pytest.fixture(scope='module')
def panel2():
    """A panel-default transmission-line/8 at the two band endpoints and its result."""
    doc = line8(frequency=TWO)
    return doc, doc.analyze()


def test_band2_and_length_design3_admit_line8_and_old_versions_refuse_it(monkeypatch):
    from sipi.band import NetworkBandDocument
    from sipi.length_design import LineLengthDesignDocument
    monkeypatch.setattr(CrossSection, 'mesh', lambda *a, **k: pytest.fail('validation solved fields'))
    assert {'sipi.network-band/2', 'sipi.line-length-design/3'} <= set(saved_schemas())
    raw = line8(frequency=TWO).to_dict()
    sparse = {k: v for k, v in raw.items() if k not in ('current_method', 'panel')}
    line, zero = (dict(kind='transmission-line', document=dict(sparse, length_m=x)) for x in (.02, 0.))
    band = NetworkBandDocument(line, limits=LIMITS, schema='sipi.network-band/2')
    design = LineLengthDesignDocument(zero, bounds=[0, 10], limits=LIMITS, schema='sipi.line-length-design/3')
    assert band.to_dict()['network']['document'] == raw
    assert design.to_dict()['network']['document'] == dict(raw, length_m=0.)
    for saved in (band, design):
        text = saved.dumps()
        assert normalize_saved(text) == text and type(saved).loads(text).dumps() == text
    with pytest.raises(ValueError, match='nested transmission-line/8 requires'):
        NetworkBandDocument(line, limits=LIMITS)
    with pytest.raises(ValueError, match='nested transmission-line/8 requires'):
        LineLengthDesignDocument(zero, bounds=[0, 10], limits=LIMITS, schema='sipi.line-length-design/2')
    nested = dict(kind='network-assembly', document=assembly(RLGC).to_dict())
    with pytest.raises(ValueError, match='nested network-assembly/2 requires'):
        NetworkBandDocument(nested, limits=[dict(LIMITS[0], frequency_hz=[0, 1e9])])
    NetworkBandDocument(nested, limits=[dict(LIMITS[0], frequency_hz=[0, 1e9])], schema='sipi.network-band/2')
    # Without line/8 the new versions are the old ones with a new schema name.
    rlgc_limits = [dict(LIMITS[0], frequency_hz=[0, 1e9])]
    old, new = (NetworkBandDocument(RLGC, limits=rlgc_limits, schema=s).to_dict()
                for s in ('sipi.network-band/1', 'sipi.network-band/2'))
    assert new == dict(old, schema='sipi.network-band/2')
    seven = dict(kind='transmission-line', document=dict(line7(frequency=TWO).to_dict(), length_m=0.))
    old, new = (LineLengthDesignDocument(seven, bounds=[0, 10], limits=LIMITS, schema=s).to_dict()
                for s in ('sipi.line-length-design/2', 'sipi.line-length-design/3'))
    assert new == dict(old, schema='sipi.line-length-design/3')


def test_band2_with_line8_is_the_standalone_line8_bit_for_bit(panel2):
    from sipi.band import NetworkBandDocument, assess_band
    doc, direct = panel2
    out = NetworkBandDocument(wrap(doc), limits=LIMITS, schema='sipi.network-band/2').analyze()
    expected = assess_band(direct.network, LIMITS)
    np.testing.assert_array_equal(out.network.s, direct.network.s)
    assert out.extraction.input_json == doc.dumps()
    assert out.checks == expected.checks and out.passed == expected.passed


def test_length_design3_with_line8_is_the_standalone_line8_bit_for_bit():
    from sipi.length_design import LineLengthDesignDocument
    doc = Line8.from_dict(dict(line8(frequency=TWO).to_dict(), length_m=0.))
    direct = doc.analyze()
    design = LineLengthDesignDocument(wrap(doc), bounds=[0, 10], limits=LIMITS,
                                      schema='sipi.line-length-design/3')
    out = design.solve()
    for key in 'RLGC':
        np.testing.assert_array_equal(getattr(out.extraction, key), getattr(direct, key))
    resolved = json.loads(out.resolved_network_json)
    reference = LineLengthDesignDocument(resolved, bounds=[0, 10], limits=LIMITS).solve()
    assert out.history == reference.history
    assert (out.feasible_length_m, out.infeasible_length_m) == \
        (reference.feasible_length_m, reference.infeasible_length_m)
    assert out.feasible.checks == reference.feasible.checks
