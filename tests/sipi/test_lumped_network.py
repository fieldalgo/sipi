# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent lumped circuit laws, references and saved-input composition."""
from decimal import Decimal, localcontext
from itertools import product
import importlib.metadata as metadata
import json
import numpy as np
import pytest

from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import (lumped_network, LumpedNetworkDocument, NetworkAssemblyDocument,
                  NetworkTransformDocument, cascade_networks, deembed_network,
                  CrossSectionDocument, microstrip)
from sipi.circuit_document import CircuitDocument
from sipi.line_model import TransmissionLineDocument
from sipi.termination import terminate_network


@pytest.mark.parametrize('placement', ['series', 'shunt'])
@pytest.mark.parametrize('resistance', [0., .23, 50.])
def test_independent_abcd_circuit_laws_and_power(placement, resistance):
    skrf = require_tool('scikit-rf')
    from skrf.circuit import Circuit
    f = np.geomspace(1e3, 1e11, 17); refs = np.array([25., 85.])
    z = resistance+1j*(2*np.pi*f*1.2e-9-1/(2*np.pi*f*2.2e-12))
    clock = Stopwatch()
    with clock('openphysics'):
        actual = lumped_network(f, resistance=resistance, inductance=1.2e-9,
                                capacitance=2.2e-12, placement=placement, z_ref=refs)
    with clock('reference'):
        frequency = skrf.Frequency.from_f(f, unit='Hz')
        # Direct ABCD at actual refs avoids a singular S->Z renormalization.
        reference = (Circuit.SeriesImpedance(frequency, z, 'reference', z0=refs)
                     if placement == 'series' else
                     Circuit.ShuntAdmittance(frequency, 1/z, 'reference', z0=refs))
    error = float(abs(actual.s-reference.s).max())
    a = np.array([1+.2j, -.3+.4j]); b = actual.s@a
    v = np.sqrt(refs)*(a+b); i = (a-b)/np.sqrt(refs)
    if placement == 'series':
        current, voltage = i[:, 0], v[:, 0]-v[:, 1]
        law = float(abs(i.sum(axis=1)).max())
    else:
        current, voltage = i.sum(axis=1), v[:, 0]
        law = float(abs(v[:, 0]-v[:, 1]).max())
    # Balanced Ohm law avoids subtractive-current amplification for |Z|~72 Mohm.
    zn = z/max(refs); divisor = np.maximum(1, abs(zn))
    balanced = float(abs(voltage/np.sqrt(max(refs))/divisor
                         -(zn/divisor)*current*np.sqrt(max(refs))).max())
    moderate = f >= 1e6
    raw_ohm = float(abs(voltage[moderate]-z[moderate]*current[moderate]).max())
    power = .5*np.real(np.sum(v*np.conj(i), axis=1))
    balance = float(abs(power-.5*resistance*abs(current)**2).max())
    record = make_record(case=f'lumped-{placement}-R{resistance}', physics='passive lumped circuit',
        api='sipi.lumped_network', discretization='scaled branch scattering with exact DC limits',
        tool='scikit-rf', tool_discretization='independent ABCD series impedance or shunt admittance',
        matched=['RLC, exp(+j omega t), frequencies and unequal real port references'],
        not_matched=['no geometric extraction, parasitic estimation or measured component model'],
        observables=[observable(name, unit, 'max absolute difference', value, 1e-10)
            for name, unit, value in [('S', '1', error), ('KCL/KVL', 'SI', law),
                ('balanced constitutive law', '1', balanced), ('Ohm law >=1MHz', 'V', raw_ohm),
                ('dissipated power', 'W', balance)]],
        analytical_acceptance='DC limits, resonance, Decimal resistance and Thevenin response',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi', version=metadata.version('sipi')); emit(record)
    assert max(error, law, balanced, raw_ohm, balance) < 1e-10
    np.testing.assert_allclose(actual.s, actual.s.swapaxes(-1, -2), atol=1e-14, rtol=0)
    assert np.linalg.svd(actual.s, compute_uv=False).max() <= 1+1e-10
    if resistance == 0:
        np.testing.assert_allclose(actual.s.conj().swapaxes(-1, -2)@actual.s,
                                   np.broadcast_to(np.eye(2), actual.s.shape), atol=1e-12, rtol=0)


@pytest.mark.parametrize('placement', ['series', 'shunt'])
def test_decimal_resistance_1000_extreme_cases_per_placement(placement):
    small = np.nextafter(0., 1.)
    values = [small, 2*small, 3*small, 1e-320, 1e-300, 1e-200, 1., 50., 1e200, 1e300]
    with localcontext() as ctx:
        ctx.prec = 100
        for r1, r2, resistance in product(values, repeat=3):
            a, b, z = map(Decimal.from_float, (r1, r2, resistance))
            if placement == 'series':
                den = a+b+z
                expected = [[(z+b-a)/den, 2*(a*b).sqrt()/den],
                            [2*(a*b).sqrt()/den, (z+a-b)/den]]
            else:
                den = (a+b)*z+a*b
                expected = [[((b-a)*z-a*b)/den, 2*(a*b).sqrt()*z/den],
                            [2*(a*b).sqrt()*z/den, ((a-b)*z-a*b)/den]]
            expected = np.array([[float(x) for x in row] for row in expected])
            actual = lumped_network([0], resistance=resistance, z_ref=[r1, r2], placement=placement).s[0]
            np.testing.assert_allclose(actual, expected, atol=1e-12, rtol=0)
            if abs(expected[0, 1]) > np.finfo(float).tiny:
                assert abs(actual[0, 1]/expected[0, 1]-1) < 1e-12


@pytest.mark.parametrize('placement', ['series', 'shunt'])
def test_dc_resonance_and_frequency_limits(placement):
    through = np.array([[0., 1.], [1., 0.]])
    open_branch = np.eye(2) if placement == 'series' else through
    short_branch = through if placement == 'series' else -np.eye(2)
    np.testing.assert_array_equal(lumped_network([0], capacitance=1e-12, resistance=20,
        inductance=1e-9, placement=placement).s[0], open_branch)
    np.testing.assert_array_equal(lumped_network([0], inductance=1e-9,
        placement=placement).s[0], short_branch)
    # omega=1, L=C=1: exact cancellation is a short, without an admittance infinity.
    resonant = lumped_network([1/(2*np.pi)], inductance=1, capacitance=1, placement=placement)
    np.testing.assert_allclose(resonant.s[0], short_branch, atol=1e-12, rtol=0)
    capacitor = lumped_network([1e-20, 1e30], capacitance=1, placement=placement)
    inductor = lumped_network([1e-20, 1e30], inductance=1, placement=placement)
    np.testing.assert_allclose(capacitor.s, [open_branch, short_branch], atol=1e-12, rtol=0)
    np.testing.assert_allclose(inductor.s, [short_branch, open_branch], atol=1e-12, rtol=0)


@pytest.mark.parametrize('placement', ['series', 'shunt'])
def test_reference_and_common_impedance_scaling(placement):
    f = np.geomspace(1e6, 1e10, 11)
    args = dict(resistance=.23, inductance=1.2e-9, capacitance=2.2e-12, placement=placement)
    original = lumped_network(f, **args)
    other = lumped_network(f, z_ref=[25, 85], **args)
    np.testing.assert_allclose(original.renormalized([25, 85]).s, other.s, atol=1e-12, rtol=0)
    for factor in (1e-200, 1e200):
        scaled = lumped_network(f, resistance=.23*factor, inductance=1.2e-9*factor,
            capacitance=2.2e-12/factor, z_ref=np.array([25., 85.])*factor, placement=placement)
        np.testing.assert_allclose(scaled.s, other.s, atol=1e-12, rtol=0)


@pytest.mark.parametrize('placement', ['series', 'shunt'])
@pytest.mark.parametrize('capacitance', [None, 2.2e-12])
def test_thevenin_voltage_current_and_dc_power(placement, capacitance):
    f = np.array([0, 1e6, 1e9, 1e10]); source = 1.7+.2j; rs, rl, r, l = 37., 83., .23, 1.2e-9
    net = lumped_network(f, resistance=r, inductance=l, capacitance=capacitance,
                         placement=placement, z_ref=[25, 85])
    actual = terminate_network(net, source_voltages={'near': source}, terminations={'near': rs, 'far': rl})
    z = r+2j*np.pi*f*l
    if capacitance is not None:
        z[1:] += 1/(2j*np.pi*f[1:]*capacitance)
    if placement == 'series':
        current = source/(rs+rl+z)
        if capacitance is not None: current[0] = 0
        voltage = np.column_stack([source-rs*current, rl*current])
        currents = np.column_stack([current, -current])
    else:
        admittance = 1/z
        if capacitance is not None: admittance[0] = 0
        v = source/(1+rs*(1/rl+admittance))
        voltage = np.column_stack([v, v])
        currents = np.column_stack([(source-v)/rs, -v/rl])
        current = currents.sum(axis=1)
    np.testing.assert_allclose(actual.voltage, voltage, atol=1e-12, rtol=1e-12)
    np.testing.assert_allclose(actual.current, currents, atol=1e-12, rtol=1e-12)
    weight = np.where(f == 0, 1., .5)
    np.testing.assert_allclose(actual.network_power, weight*r*abs(current)**2, atol=1e-12, rtol=0)
    np.testing.assert_allclose(actual.source_power,
        actual.network_power+actual.termination_power, atol=1e-12, rtol=0)


def test_cascade_and_deembedding_singular_s_fixture():
    f = [0, 1e6, 1e9]
    left = lumped_network(f, resistance=100, port_names=('input', 'joint'))
    dut = lumped_network(f, resistance=20, inductance=1e-9, port_names=('joint', 'output'))
    assert np.linalg.det(left.s[0]) == 0
    joined = cascade_networks(left, dut)
    expected = lumped_network(f, resistance=120, inductance=1e-9)
    np.testing.assert_allclose(joined.s, expected.s, atol=1e-12, rtol=0)
    recovered = deembed_network(joined, left=left)
    np.testing.assert_allclose(recovered.s, dut.s, atol=1e-12, rtol=0)
    opened = lumped_network(f, capacitance=1e-12)
    with pytest.raises(ValueError, match='transmission'):
        deembed_network(joined, left=opened)


def source(document):
    return dict(kind='lumped-network', document=document.to_dict())


def test_strict_saved_snapshot_and_read_only_result():
    frequency, refs, names = [0, 1e9], [25, 85], ['a', 'b']
    doc = LumpedNetworkDocument(frequency, resistance=3, z_ref=refs, port_names=names)
    saved = doc.dumps(); frequency[0] = 3; refs[0] = 99; names[0] = 'mutated'
    doc.to_dict()['branch']['resistance_ohms'] = 999
    assert doc.dumps() == saved == LumpedNetworkDocument.loads(saved).dumps()
    data = json.loads(saved)
    assert data['schema'] == 'sipi.lumped-network/1' and data['branch']['capacitance_f'] is None
    net = doc.analyze()
    for array in (net.frequency, net.s, net.z_ref):
        assert not array.flags.writeable
    assert net.port_names == ('a', 'b') and net.basis == 'single-ended'


def test_saved_assembly_transform_and_driven_response():
    first = LumpedNetworkDocument([0, 1e9], resistance=3, port_names=('input', 'a'))
    second = LumpedNetworkDocument([0, 1e9], resistance=7, port_names=('b', 'output'))
    assembly = NetworkAssemblyDocument(source(first), connections=[
        dict(network=source(second), ports=[['a', 'b']])])
    transformed = NetworkTransformDocument(dict(kind='network-assembly', document=assembly.to_dict()),
        operations=[dict(kind='renormalize', reference_ohms=[25, 85])])
    circuit = CircuitDocument(dict(kind='network-transform', document=transformed.to_dict()),
        excitation=dict(kind='sources', voltages={'input': 1}), terminations={'input': 50, 'output': 50})
    actual = CircuitDocument.loads(circuit.dumps()).analyze()
    np.testing.assert_allclose(actual.response.voltage[:, 1], 50/110, atol=1e-12, rtol=0)
    assert actual.extraction.extraction.extractions == (None, None)
    direct = CircuitDocument(source(first), excitation=dict(kind='sources', voltages={'input': 1}),
                             terminations={}).analyze()
    assert direct.extraction is None
    reduced = NetworkTransformDocument(source(first), operations=[
        dict(kind='terminate-ports', loads={'a': 50})]).analyze()
    np.testing.assert_allclose(reduced.network.s[:, 0, 0], 3/103, atol=1e-12, rtol=0)


def test_geometry_assembly_extracts_once_and_metadata_fails_before_mesh(monkeypatch):
    cross = CrossSectionDocument(microstrip(width=.35e-3, substrate_height=.2e-3, eps_r=4.3),
        mesh=dict(edge_size=30e-6, far_size=.5e-3, grade=.2, min_angle=28))
    line = TransmissionLineDocument(cross, [0, 1e3], materials={}, conductor={'kind': 'perfect'}, length=.01)
    import sipi.crosssection as owner
    calls = []; original = owner.CrossSection.mesh
    def counted(*args, **kwargs):
        calls.append(1); return original(*args, **kwargs)
    monkeypatch.setattr(owner.CrossSection, 'mesh', counted)
    component = dict(kind='transmission-line', document=line.to_dict())
    resistor = LumpedNetworkDocument([0, 1e3], resistance=5, port_names=('in', 'joint'))
    doc = NetworkAssemblyDocument(source(resistor), connections=[
        dict(network=component, ports=[['joint', 'near:signal']])])
    saved = NetworkAssemblyDocument.loads(doc.dumps()); assert not calls
    broken = saved.to_dict(); broken['connections'][0]['ports'] = [['absent', 'near:signal']]
    with pytest.raises(ValueError): NetworkAssemblyDocument.from_dict(broken)
    assert not calls
    actual = saved.analyze()
    assert len(calls) == 1 and actual.extractions[0] is None and actual.extractions[1] is not None


@pytest.mark.parametrize('kwargs', [
    {'resistance': -1}, {'resistance': True}, {'resistance': float('inf')},
    {'inductance': -1}, {'inductance': [1]}, {'inductance': np.bool_(True)},
    {'capacitance': 0}, {'capacitance': -1}, {'capacitance': True}, {'capacitance': float('nan')},
    {'placement': 'parallel'}, {'placement': None}, {'placement': ['series']},
    {'z_ref': 0}, {'z_ref': [50, -1]}, {'z_ref': [True, 50]}, {'z_ref': [50]},
    {'port_names': 'ab'}, {'port_names': None}, {'port_names': ['a', 'a']},
    {'port_names': ['a', 'b\n']}, {'port_names': ['a', 1]},
])
def test_invalid_parameters_rejected(kwargs):
    with pytest.raises(ValueError): lumped_network([0, 1e9], **kwargs)
    with pytest.raises(ValueError): LumpedNetworkDocument([0, 1e9], **kwargs)


@pytest.mark.parametrize('frequency', [[], [1, 1], [-1], [[1]], [True], [float('inf')]])
def test_invalid_frequencies(frequency):
    with pytest.raises(ValueError): lumped_network(frequency)


@pytest.mark.parametrize('frequency,kwargs', [
    ([1e300], {'inductance': 1e300}), ([1e-300], {'inductance': 1e-300}),
    ([1e300], {'capacitance': 1e300}), ([1e-300], {'capacitance': 1e-300}),
])
def test_unrepresentable_reactance_is_explicit_error(frequency, kwargs):
    with pytest.raises(ValueError, match='normal finite float'): lumped_network(frequency, **kwargs)
    with pytest.raises(ValueError, match='normal finite float'): LumpedNetworkDocument(frequency, **kwargs)


def test_intermediate_overflow_and_underflow_do_not_reject_representable_values():
    # f*C is subnormal although the final capacitive reactance is normal.
    # Splitting exponents avoids losing precision in this intermediate product.
    actual = lumped_network([1e-300], capacitance=1e-9)
    assert np.isfinite(actual.s).all()
    pure = lumped_network([1e308], resistance=5)
    np.testing.assert_allclose(pure.s[0], [[5/105, 100/105], [100/105, 5/105]], atol=1e-12, rtol=0)
    # Extreme L and f individually remain valid when their product is moderate.
    np.testing.assert_allclose(lumped_network([1e-300], inductance=1e300).s,
        lumped_network([1], inductance=1).s, atol=1e-12, rtol=0)


@pytest.mark.parametrize('mutate', [
    lambda d: d.update(schema='sipi.lumped-network/2'), lambda d: d.update(extra=1),
    lambda d: d.pop('branch'), lambda d: d.update(branch=None),
    lambda d: d['branch'].update(extra=1), lambda d: d['branch'].pop('capacitance_f'),
    lambda d: d.update(port_names='ab'), lambda d: d.update(frequency_hz=[True]),
])
def test_invalid_saved_document(mutate):
    data = LumpedNetworkDocument([0, 1e9]).to_dict(); mutate(data)
    with pytest.raises(ValueError): LumpedNetworkDocument.from_dict(data)


@pytest.mark.parametrize('text', ['{"schema":1,"schema":2}', '{"a":NaN}', '{"a":Infinity}'])
def test_duplicate_and_nonfinite_json(text):
    with pytest.raises(ValueError): LumpedNetworkDocument.loads(text)
