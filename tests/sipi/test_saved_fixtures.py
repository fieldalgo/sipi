# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved fixture sequences: independent composition and strict metadata."""
import importlib.metadata as metadata
import numpy as np
import pytest
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import (LineNetwork, LumpedNetworkDocument, NetworkTransformDocument,
                  NetworkTransformResult, NetworkAssemblyDocument, CrossSection,
                  CrossSectionDocument, microstrip, cascade_networks, deembed_network)
from sipi.circuit_document import CircuitDocument
from sipi.line_model import TransmissionLineDocument
from sipi.volume_line import VolumeLineDocument

F = [0, 1e6, 1e9, 10e9]
V2 = 'sipi.network-transforms/2'


def lumped(resistance=7, names=('near', 'far'), refs=50, **kwargs):
    doc = LumpedNetworkDocument(F, resistance=resistance, port_names=names, z_ref=refs, **kwargs)
    return dict(kind='lumped-network', document=doc.to_dict())


def plan(operations=None):
    return NetworkTransformDocument(lumped(), schema=V2, operations=operations or [
        dict(kind='cascade', side='left', network=lumped(100, ('outside', 'inside')))])


@pytest.mark.parametrize('side', ['left', 'right'])
def test_independent_rlc_cascade_and_removal(side):
    skrf = require_tool('scikit-rf')
    from skrf.circuit import Circuit
    source = lumped(7, inductance=2e-9)
    fixture = lumped(500, ('fn', 'ff'), capacitance=2e-12, placement='shunt')
    clock = Stopwatch()
    with clock('openphysics'):
        combined = NetworkTransformDocument(source, schema=V2, operations=[
            dict(kind='cascade', side=side, network=fixture, port_names=['a', 'b'])]).analyze()
        recovered = NetworkTransformDocument(source, schema=V2, operations=[
            dict(kind='cascade', side=side, network=fixture, port_names=['a', 'b']),
            dict(kind='deembed', left=fixture if side == 'left' else None,
                 right=fixture if side == 'right' else None, port_names=['near', 'far'])]).analyze()
    with clock('reference'):
        frequency = skrf.Frequency.from_f(F, unit='Hz')
        z = 7+2j*np.pi*np.array(F)*2e-9
        # DC capacitor is exactly open, hence zero shunt admittance.
        y = np.zeros(len(F), complex)
        y[1:] = 1/(500+1/(2j*np.pi*np.array(F[1:])*2e-12))
        dut = Circuit.SeriesImpedance(frequency, z, 'dut', z0=50)
        fixture_ref = Circuit.ShuntAdmittance(frequency, y, 'fixture', z0=50)
        expected = fixture_ref**dut if side == 'left' else dut**fixture_ref
        removed = fixture_ref.inv**expected if side == 'left' else expected**fixture_ref.inv
    errors = [float(abs(combined.network.s-expected.s).max()),
              float(abs(recovered.network.s-removed.s).max()),
              float(abs(recovered.network.s-dut.s).max())]
    record = make_record(case='saved-'+side+'-fixture', physics='known lumped fixture composition',
        api='sipi.NetworkTransformDocument', discretization='v2 saved cascade and wave-chain removal',
        tool='scikit-rf', tool_discretization='independent ABCD components, cascade and inverse',
        matched=['RLC, DC and positive frequencies, port references and fixture side'],
        not_matched=['no fixture estimation, calibration, noise removal or geometry accuracy claim'],
        observables=[observable(name, '1', 'max absolute difference', value, 1e-10)
                     for name, value in zip(('cascade S', 'removed S', 'recovered DUT S'), errors)],
        analytical_acceptance='pure resistance totals, singular S fixtures and explicit DC open limits',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi', version=metadata.version('sipi')); emit(record)
    assert max(errors) < 1e-10
    assert combined.fixture_extractions == (None,)
    assert recovered.fixture_extractions == (None, None)
    assert len(recovered.fixture_networks) == 2


def test_two_fixtures_references_operation_order_and_loaded_circuit():
    first = lumped(75, ('external_left', 'dut_near'), [25, 50])
    last = lumped(13, ('dut_far', 'external_right'), [50, 85])
    operations = [dict(kind='cascade', side='left', network=first),
        dict(kind='cascade', side='right', network=last),
        dict(kind='deembed', left=first, right=last),
        dict(kind='renormalize', reference_ohms=[40, 60])]
    doc = plan(operations)
    assert doc.port_names == ('dut_near', 'dut_far')
    np.testing.assert_array_equal(doc.z_ref, [40, 60])
    assert not doc.z_ref.flags.writeable
    result = NetworkTransformDocument.loads(doc.dumps()).analyze()
    expected = np.array([[(7+60-40)/107, 2*np.sqrt(40*60)/107],
                         [2*np.sqrt(40*60)/107, (7+40-60)/107]])
    np.testing.assert_allclose(result.network.s, np.broadcast_to(expected, (4, 2, 2)), atol=1e-12, rtol=0)
    assert len(result.fixture_networks) == 4 and result.fixture_extractions == (None,)*4
    assert [x.port_names for x in result.fixture_networks] == [
        ('external_left', 'dut_near'), ('dut_far', 'external_right'),
        ('external_left', 'dut_near'), ('dut_far', 'external_right')]
    circuit = CircuitDocument(dict(kind='network-transform', document=doc.to_dict()),
        excitation=dict(kind='sources', voltages={'dut_near': 1}),
        terminations={'dut_near': 37, 'dut_far': 83})
    solved = CircuitDocument.loads(circuit.dumps()).analyze()
    np.testing.assert_allclose(solved.response.voltage[:, 1], 83/127, atol=1e-12, rtol=0)
    assert len(solved.extraction.fixture_networks) == 4


def test_singular_s_is_valid_but_zero_transmission_fixture_is_rejected():
    original = plan(); result = original.analyze()
    assert np.linalg.det(result.fixture_networks[0].s[0]) == 0
    np.testing.assert_allclose(result.network.s[:, 1, 0], 100/207, atol=1e-12, rtol=0)
    opened = lumped(0, capacitance=1e-12)
    doc = plan([dict(kind='deembed', left=opened, right=None, port_names=['near', 'far'])])
    saved = doc.dumps()
    with pytest.raises(ValueError, match='forward transmission'): doc.analyze()
    assert doc.dumps() == saved


def test_four_port_nonreciprocal_cascade_and_removal_against_independent_connection():
    skrf = require_tool('scikit-rf')
    rng = np.random.default_rng(421)
    # Strong transmission and weak nonsymmetric reflections keep inverses conditioned.
    def network(names):
        s = .02*(rng.normal(size=(4, 4, 4))+1j*rng.normal(size=(4, 4, 4)))
        s[:, :2, 2:] += .8*np.eye(2); s[:, 2:, :2] += .7*np.eye(2)
        return LineNetwork(F, s, 50, names)
    dut = network(('n1', 'n2', 'f1', 'f2'))
    fixture = network(('x1', 'x2', 'y1', 'y2'))
    def data(net):
        return dict(kind='touchstone', text=net.touchstone(), ports=4, port_names=list(net.port_names))
    operations = [dict(kind='cascade', side='right', network=data(fixture))]
    clock = Stopwatch()
    with clock('openphysics'):
        actual = NetworkTransformDocument(data(dut), schema=V2, operations=operations).analyze()
    frequency = skrf.Frequency.from_f(F, unit='Hz')
    with clock('reference'):
        expected = skrf.network.connect(skrf.Network(frequency=frequency, s=dut.s, z0=50), 2,
            skrf.Network(frequency=frequency, s=fixture.s, z0=50), 0, num=2)
    error = float(abs(actual.network.s-expected.s).max())
    record = make_record(case='saved-four-port-fixture', physics='explicit multiconductor composition',
        api='sipi.NetworkTransformDocument', discretization='saved all-near/all-far scattering cascade',
        tool='scikit-rf', tool_discretization='independent multiport connect',
        matched=['same nonsymmetric four-port samples, references and paired wiring'],
        not_matched=['synthetic network is not a physical extraction or measured fixture'],
        observables=[observable('cascade S', '1', 'max absolute difference', error, 1e-10)],
        analytical_acceptance='recovered DUT samples within 1e-12', stopwatch=clock)
    record['openphysics'].update(distribution='sipi', version=metadata.version('sipi')); emit(record)
    np.testing.assert_allclose(actual.network.s, expected.s, atol=1e-10, rtol=0)
    assert actual.network.port_names == ('n1', 'n2', 'y1', 'y2')
    operations.append(dict(kind='deembed', left=None, right=data(fixture), port_names=list(dut.port_names)))
    recovered = NetworkTransformDocument(data(dut), schema=V2, operations=operations).analyze()
    np.testing.assert_allclose(recovered.network.s, dut.s, atol=1e-12, rtol=0)


@pytest.mark.parametrize('kind', ['transmission-line', 'volume-line'])
def test_each_geometry_fixture_occurrence_extracted_once_and_preserved(kind, monkeypatch):
    section = microstrip(width=.4e-3, substrate_height=.5e-3, thickness=.1e-3,
        eps_r=4, tan_delta=.02, air_height=.5e-3, box_width=2e-3)
    cross = CrossSectionDocument(section)
    if kind == 'transmission-line':
        inner = TransmissionLineDocument(cross, [0, 1e3], materials={}, conductor={'kind': 'perfect'}, length=.01)
        owner, method = CrossSection, 'mesh'
    else:
        inner = VolumeLineDocument(cross, [0, 1e3], materials={}, conductivity=58e6, length=.01,
            mesh=dict(ground_thickness=.1e-3, padding=2e-3, metal_size=50e-6,
                      far_size=.5e-3, grade=.2, min_angle=28))
        import sipi.volume_line as owner
        method = 'mesh_conductor_section'
    calls = []; original = getattr(owner, method)
    def counted(*args, **kwargs):
        calls.append(1); return original(*args, **kwargs)
    monkeypatch.setattr(owner, method, counted)
    base = dict(kind='lumped-network', document=LumpedNetworkDocument([0, 1e3], resistance=7).to_dict())
    fixture = dict(kind=kind, document=inner.to_dict())
    doc = NetworkTransformDocument(base, schema=V2, operations=[
        dict(kind='cascade', side='left', network=fixture, port_names=['near', 'far']),
        dict(kind='deembed', left=fixture, right=None, port_names=['near', 'far'])])
    saved = NetworkTransformDocument.loads(doc.dumps()); assert not calls
    with pytest.raises(ValueError, match='unknown network port'):
        CircuitDocument(dict(kind='network-transform', document=saved.to_dict()),
            excitation=dict(kind='sources', voltages={'absent': 1}), terminations={})
    assert not calls
    result = saved.analyze()
    assert len(calls) == 2 and result.extraction is None
    assert len(result.fixture_extractions) == 2
    assert all(x.input_json == inner.dumps() for x in result.fixture_extractions)
    np.testing.assert_allclose(result.network.s, result.source_network.s, atol=1e-12, rtol=0)


def test_assembly_source_and_metadata_after_reduction():
    base = lumped(7, ('a', 'b'))
    assembled = NetworkAssemblyDocument(base, connections=[
        dict(network=lumped(3, ('c', 'd')), ports=[['b', 'c']])])
    doc = NetworkTransformDocument(dict(kind='network-assembly', document=assembled.to_dict()),
        schema=V2, operations=[dict(kind='cascade', side='right', network=lumped(5)),
            dict(kind='terminate-ports', loads={'far': 50}),
            dict(kind='renormalize', reference_ohms=75)])
    result = doc.analyze()
    np.testing.assert_allclose(result.network.s[:, 0, 0], (65-75)/(65+75), atol=1e-12, rtol=0)
    assert result.network.port_names == ('a',) and result.extraction.input_json == assembled.dumps()
    np.testing.assert_array_equal(doc.z_ref, [75])


def test_v1_compatibility_v2_opt_in_snapshots_and_result_defaults():
    operations = [dict(kind='renormalize', reference_ohms=[25, 85])]
    v1 = NetworkTransformDocument(lumped(), operations=operations)
    assert v1.to_dict()['schema'] == 'sipi.network-transforms/1'
    v2 = NetworkTransformDocument(lumped(), operations=operations, schema=V2)
    np.testing.assert_array_equal(v1.analyze().network.s, v2.analyze().network.s)
    raw = plan().to_dict(); doc = NetworkTransformDocument.from_dict(raw); saved = doc.dumps()
    raw['operations'][0]['network']['document']['branch']['resistance_ohms'] = 999
    doc.to_dict()['operations'].clear()
    refs = doc.z_ref; refs.setflags(write=True); refs[:] = 1
    assert saved == doc.dumps() == NetworkTransformDocument.loads(saved).dumps()
    np.testing.assert_array_equal(doc.z_ref, [50, 50])
    net = v1.analyze().network
    old_result = NetworkTransformResult(net, net, '{}', None)
    assert old_result.fixture_networks == old_result.fixture_extractions == ()
    with pytest.raises(ValueError, match='require sipi.network-transforms/2'):
        NetworkTransformDocument(lumped(), operations=plan().to_dict()['operations'])


@pytest.mark.parametrize('mutate', [
    lambda d: d['operations'][0].pop('side'),
    lambda d: d['operations'][0].pop('network'),
    lambda d: d['operations'][0].update(side='up'),
    lambda d: d['operations'][0].update(side=None),
    lambda d: d['operations'][0].update(extra=1),
    lambda d: d['operations'][0].update(port_names='ab'),
    lambda d: d['operations'][0].update(port_names=None),
    lambda d: d['operations'][0].update(port_names=['a']),
    lambda d: d['operations'][0].update(port_names=['a', 'a']),
    lambda d: d['operations'][0].update(port_names=['a', 'b\n']),
    lambda d: d['operations'][0]['network']['document'].update(frequency_hz=[0, 2e6, 1e9, 1e10]),
    lambda d: d['operations'][0]['network']['document'].update(reference_ohms=[50, 75]),
    lambda d: d['operations'][0].update(network=dict(kind='network-assembly', document={})),
    lambda d: d['operations'][0].update(network=dict(kind='network-transform', document={})),
    lambda d: d.update(operations=[dict(kind='deembed', left=None, right=None)]),
    lambda d: d.update(operations=[dict(kind='deembed', left=lumped())]),
    lambda d: d.update(operations=[dict(kind='deembed', right=lumped())]),
    lambda d: d.update(operations=[dict(kind='deembed', left=lumped(refs=[75, 50]), right=None)]),
    lambda d: d.update(operations=[dict(kind='deembed', left=None, right=lumped(refs=[50, 75]))]),
    lambda d: d.update(operations=[dict(kind='deembed', left=lumped(names=('left', 'same')),
                                      right=lumped(names=('same', 'right')))]),
    lambda d: d.update(operations=[dict(kind='renormalize', reference_ohms=[75, 85]),
                                  dict(kind='cascade', side='left', network=lumped())]),
    lambda d: d.update(operations=[dict(kind='terminate-ports', loads={'far': 50}),
                                  dict(kind='cascade', side='left', network=lumped())]),
    lambda d: d.update(operations=[dict(kind='terminate-ports', loads={'far': 50}),
                                  dict(kind='deembed', left=lumped(), right=None)]),
])
def test_invalid_fixture_metadata_rejected_without_geometry(mutate, monkeypatch):
    data = plan().to_dict(); mutate(data)
    def forbidden(*args, **kwargs): pytest.fail('metadata validation reached geometry analysis')
    monkeypatch.setattr(TransmissionLineDocument, 'analyze', forbidden)
    monkeypatch.setattr(VolumeLineDocument, 'analyze', forbidden)
    with pytest.raises(ValueError): NetworkTransformDocument.from_dict(data)


def test_mismatched_fixture_port_count_and_duplicate_default_output_names():
    net = LineNetwork(F, np.zeros((4, 4, 4)), 50, ('a', 'b', 'c', 'd'))
    other = dict(kind='touchstone', text=net.touchstone(), ports=4, port_names=list(net.port_names))
    with pytest.raises(ValueError, match='port counts'):
        plan([dict(kind='cascade', side='left', network=other)])
    with pytest.raises(ValueError, match='unique'):
        plan([dict(kind='cascade', side='left', network=lumped(names=('far', 'joint')))])


def test_extraction_metadata_drift_is_rejected(monkeypatch):
    cross = CrossSectionDocument(microstrip(width=.4e-3, substrate_height=.5e-3, eps_r=4))
    inner = TransmissionLineDocument(cross, F, materials={}, conductor={'kind': 'perfect'}, length=.01)
    doc = plan([dict(kind='cascade', side='right', network=dict(kind='transmission-line', document=inner.to_dict()))])
    class Changed:
        network = LineNetwork(F, np.zeros((4, 2, 2)), [50, 75], ('near:signal', 'far:signal'))
    monkeypatch.setattr(TransmissionLineDocument, 'analyze', lambda self: Changed())
    with pytest.raises(ValueError, match='references'): doc.analyze()
