# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Named metal materials survive JSON, remeshing and common execution."""
import json
import numpy as np
import pytest
from sipi import CrossSectionDocument, coupled_microstrip
from sipi.conductor_mesh import mesh_conductor_section
from sipi.dielectric import ConstantDielectric
from sipi.execution import normalize_saved, execute_saved
from sipi.volume_line import VolumeLineDocument, volume_line
from sipi.circuit_document import CircuitDocument
from sipi.termination import terminate_network
from test_volume_line import MESH

NAMED = dict(signals={'positive': 58e6, 'negative': 20e6}, ground=10e6)


def section():
    return coupled_microstrip(width=.4e-3, gap=.3e-3, substrate_height=.5e-3,
        thickness=.1e-3, eps_r=4., tan_delta=.02, box_width=.003, air_height=.001)


def document(conductivity=None, mesh=None):
    return VolumeLineDocument(CrossSectionDocument(section()), [0, 1e3, 1e4], materials={},
        conductivity=NAMED if conductivity is None else conductivity, length=.1,
        mesh=MESH if mesh is None else mesh)


def test_strict_v2_roundtrip_is_field_free_and_inputs_are_copied(monkeypatch):
    import sipi.volume_line as implementation
    monkeypatch.setattr(implementation, 'mesh_conductor_section', lambda *a, **k: pytest.fail('Normalization meshed'))
    conductivity = dict(signals=dict(NAMED['signals']), ground=NAMED['ground'])
    doc = document(conductivity)
    expected = doc.dumps()
    assert doc.to_dict()['schema'] == 'sipi.volume-line/2'
    assert normalize_saved(expected) == VolumeLineDocument.loads(expected).dumps() == expected
    conductivity['signals']['positive'] = 1
    conductivity['ground'] = 1
    changed = doc.to_dict()
    changed['conductor']['conductivity']['signals'].clear()
    assert doc.dumps() == expected
    assert document(58e6).to_dict()['schema'] == 'sipi.volume-line/1'


@pytest.fixture(scope='module')
def saved_pair():
    doc = document()
    return doc, doc.analyze(keep_fields=True)


def test_saved_named_dc_area_matrix_and_direct_volume_fields(saved_pair):
    doc, saved = saved_pair
    volume = mesh_conductor_section(section(), **MESH, dielectric_interfaces=True)
    sigma = np.zeros(volume.mesh.num_triangles)
    for name, indices in volume.signals.items():
        sigma[indices] = NAMED['signals'][name]
    sigma[volume.ground] = NAMED['ground']
    direct = volume_line(volume, [0, 1e3, 1e4], materials={
        layer.name: ConstantDielectric(layer.eps_r, layer.tan_delta) for layer in section().layers},
        conductivity=sigma, length=.1, keep_fields=True)
    expected = np.diag([1/(58e6*.4e-3*.1e-3), 1/(20e6*.4e-3*.1e-3)])
    expected += np.ones((2, 2))/(10e6*.003*.1e-3)
    np.testing.assert_allclose(saved.R[0], expected, rtol=1e-10, atol=0)
    for name in ('R', 'L', 'C', 'G'):
        np.testing.assert_array_equal(getattr(saved, name), getattr(direct, name))
    np.testing.assert_array_equal(saved.network.s, direct.network.s)
    np.testing.assert_array_equal(saved.conductor.current_density, direct.conductor.current_density)
    assert max(saved.conductor.current_error) < 1e-10
    assert saved.input_json == doc.dumps()
    assert saved.names == ('positive', 'negative')


def test_common_executor_preserves_named_schema_and_same_network(saved_pair):
    doc, direct = saved_pair
    output = execute_saved(doc.dumps())
    assert output['status'] == 'complete' and output['input'] == doc.to_dict()
    for name, key in [('R', 'R_ohm_per_m'), ('L', 'L_h_per_m'), ('C', 'C_f_per_m'), ('G', 'G_s_per_m')]:
        np.testing.assert_array_equal(output['result'][key], getattr(direct, name))
    network = output['result']['network']
    np.testing.assert_array_equal(np.array(network['s']['real'])+1j*np.array(network['s']['imag']), direct.network.s)


def test_circuit_nested_named_volume_matches_direct_termination(saved_pair):
    doc, direct = saved_pair
    sources = {'near:positive': 1.}
    loads = {'far:positive': 100., 'far:negative': 75.}
    circuit = CircuitDocument(dict(kind='volume-line', document=doc.to_dict()),
        excitation=dict(kind='sources', voltages=sources), terminations=loads)
    restored = CircuitDocument.loads(circuit.dumps())
    assert restored.to_dict()['network']['document'] == doc.to_dict()
    result = restored.analyze()
    reference = terminate_network(direct.network, source_voltages=sources, terminations=loads)
    np.testing.assert_array_equal(result.network.s, direct.network.s)
    np.testing.assert_allclose(result.response.voltage, reference.voltage, rtol=1e-12, atol=0)
    np.testing.assert_allclose(result.response.current, reference.current, rtol=1e-12, atol=0)


def test_uniform_named_material_agrees_with_unchanged_v1():
    scalar = document(58e6).analyze()
    named = document(dict(signals={name: 58e6 for name in NAMED['signals']}, ground=58e6)).analyze()
    for actual, expected in [(named.R, scalar.R), (named.L, scalar.L), (named.C, scalar.C),
                             (named.G, scalar.G), (named.network.s, scalar.network.s)]:
        assert np.max(abs(actual-expected))/np.max(abs(expected)) < 1e-12


def test_names_reassign_after_remeshing_with_same_dc_areas():
    refined = dict(MESH, metal_size=MESH['metal_size']/2, far_size=MESH['far_size']/2, grade=MESH['grade']/2)
    a, b = document().analyze(), document(mesh=refined).analyze()
    np.testing.assert_allclose(a.R[0], b.R[0], rtol=1e-10, atol=0)
    assert a.names == b.names
    # Same conductor names do not reuse triangle indices from the old mesh.
    assert a.input_json != b.input_json


@pytest.mark.parametrize('bad', [
    58e6, [], {}, {'signals': {}, 'ground': 10e6},
    {'signals': {'positive': 58e6, 'negative': 20e6, 'extra': 1.}, 'ground': 10e6},
    {'signals': {'positive': 58e6, 'ground': 20e6}, 'ground': 10e6},
    {'signals': [58e6, 20e6], 'ground': 10e6},
    {'signals': {'positive': True, 'negative': 20e6}, 'ground': 10e6},
    {'signals': {'positive': 0., 'negative': 20e6}, 'ground': 10e6},
    {'signals': {'positive': float('nan'), 'negative': 20e6}, 'ground': 10e6},
    {'signals': {'positive': [58e6], 'negative': 20e6}, 'ground': 10e6},
    {'signals': {'positive': 58e6, 'negative': 20e6}, 'ground': False},
    {'signals': {'positive': 58e6, 'negative': 20e6}, 'ground': -1.},
    {'signals': {'positive': 58e6, 'negative': 20e6}, 'ground': 10e6, 'roughness': 0.},
], ids=['scalar', 'list', 'empty', 'missing-name', 'extra-name', 'ground-as-signal', 'signal-array',
        'boolean', 'zero', 'nonfinite', 'array-value', 'boolean-ground', 'negative-ground', 'unknown-field'])
def test_invalid_named_materials_fail_before_meshing(monkeypatch, bad):
    import sipi.volume_line as implementation
    data = document().to_dict()
    data['conductor']['conductivity'] = bad
    monkeypatch.setattr(implementation, 'mesh_conductor_section', lambda *a, **k: pytest.fail('Invalid material meshed'))
    with pytest.raises(ValueError):
        VolumeLineDocument.from_dict(data).analyze()


def test_schema_versions_are_not_silently_interchanged_or_loosened():
    named = document().to_dict()
    named['schema'] = 'sipi.volume-line/1'
    with pytest.raises(ValueError): VolumeLineDocument.from_dict(named)
    scalar = document(58e6).to_dict()
    scalar['schema'] = 'sipi.volume-line/2'
    with pytest.raises(ValueError): VolumeLineDocument.from_dict(scalar)
    named['schema'] = 'sipi.volume-line/3'
    with pytest.raises(ValueError): VolumeLineDocument.from_dict(named)
    text = document().dumps()
    with pytest.raises(ValueError): VolumeLineDocument.loads(text.replace('"ground": 10000000.0', '"ground": 10000000.0, "ground": 1.0'))


def test_signal_named_ground_is_distinct_from_reference_material():
    data = document().to_dict()
    data['cross_section']['traces'][0]['name'] = 'ground'
    sigma = data['conductor']['conductivity']
    sigma['signals']['ground'] = sigma['signals'].pop('positive')
    doc = VolumeLineDocument.from_dict(data)
    assert normalize_saved(doc.dumps()) == doc.dumps()
    result = doc.analyze()
    expected = np.diag([1/(58e6*.4e-3*.1e-3), 1/(20e6*.4e-3*.1e-3)])
    expected += np.ones((2, 2))/(10e6*.003*.1e-3)
    np.testing.assert_allclose(result.R[0], expected, rtol=1e-10, atol=0)
    assert result.names == ('ground', 'negative')


def test_ground_trace_joins_common_material_without_a_signal_entry():
    from sipi import CrossSection, Trace
    base = section()
    shield = Trace('shield', x=.001, y=.5e-3, width=.3e-3, thickness=.1e-3, ground=True)
    cross = CrossSection(base.layers, [*base.traces, shield], base.width,
                         bottom=base.bottom, top=base.top, sides=base.sides)
    doc = VolumeLineDocument(CrossSectionDocument(cross), [0], materials={}, mesh=MESH,
                             conductivity=NAMED, length=.1)
    result = doc.analyze()
    expected = np.diag([1/(58e6*.4e-3*.1e-3), 1/(20e6*.4e-3*.1e-3)])
    expected += np.ones((2, 2))/(10e6*(.003+.3e-3)*.1e-3)
    np.testing.assert_allclose(result.R[0], expected, rtol=1e-10, atol=0)
    bad = doc.to_dict()
    bad['conductor']['conductivity']['signals']['shield'] = 20e6
    with pytest.raises(ValueError, match='signal conductivities'):
        VolumeLineDocument.from_dict(bad)


def test_common_execution_keeps_actual_skin_resolution_failure():
    data = document().to_dict()
    data['frequency_hz'] = [0, 1e8]
    doc = VolumeLineDocument.from_dict(data)
    with pytest.raises(ValueError, match='skin depth'):
        doc.analyze()
    # Ordinary solver failures propagate; only saved goals use a failed result.
    # Preserve the established v1 transport contract for v2 as well.
    for candidate in (doc, VolumeLineDocument.from_dict(dict(data, schema='sipi.volume-line/1',
            conductor=dict(conductivity=58e6, relative_permeability=1.)))):
        with pytest.raises(ValueError, match='skin depth'):
            execute_saved(candidate.dumps())
