# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict saved Maxwell inputs and transport replay without hidden solves."""
import json
from dataclasses import replace

import numpy as np
import pytest
from test_ports3d import coax, solve
from sipi.ports3d_document import TEMPorts3DDocument
from sipi.execution import execute_saved, normalize_saved


def document():
    mesh, ports, _ = coax()
    return TEMPorts3DDocument(mesh, ports=ports, frequency=[5e8, 1e9], eps_r=4.)


def test_saved_direct_and_transport_parity_with_detached_input():
    mesh, ports, _ = coax(2, 16, 3)
    ports = [replace(ports[0], name='입력'), replace(ports[1], name='출력')]
    direct = solve(mesh, ports, [5e8, 1e9])
    doc = TEMPorts3DDocument(mesh, ports=ports, frequency=[5e8, 1e9], eps_r=4.)
    data = doc.to_dict(); restored = TEMPorts3DDocument.from_dict(data)
    data['ports'].reverse(); data['mesh']['nodes'][0][0] = 123; mesh.nodes[:] = 0
    assert doc.dumps() == restored.dumps() == normalize_saved(doc.dumps())
    replay = TEMPorts3DDocument.loads(doc.dumps()).analyze()
    np.testing.assert_allclose(replay.network.s, direct.network.s, rtol=0, atol=1e-10)
    output = execute_saved(doc.dumps(), max_evaluations=2)
    assert output['status'] == 'complete' and output['error'] is None
    assert output['input'] == doc.to_dict()
    result = output['result']; network = result['network']
    assert result['model'] == 'bounded-homogeneous-3d-local-tem-admittance'
    assert network['port_names'] == ['입력', '출력']
    assert network['frequency_hz'] == [5e8, 1e9] and network['basis'] == 'single-ended'
    np.testing.assert_allclose(np.array(network['s']['real'])+1j*np.array(network['s']['imag']),
                               direct.network.s, rtol=0, atol=1e-10)
    np.testing.assert_allclose(network['reference_ohms'], direct.network.z_ref, rtol=1e-12)
    np.testing.assert_allclose(result['port_norm'], direct.port_norm, rtol=1e-12)
    for key, values in result['consistency'].items():
        np.testing.assert_allclose(values, getattr(direct, key), rtol=0, atol=1e-10)
    assert result['mesh'] == dict(nodes=mesh.num_nodes, tetrahedra=direct.num_tets, edges=direct.num_edges)
    assert 'fields' not in result
    json.dumps(output, allow_nan=False)


def test_normalize_and_constructor_do_not_solve_any_port_or_volume(monkeypatch):
    data = document().to_dict()
    import sipi.ports3d as core
    def forbidden(*args, **kw): pytest.fail('normalization performed a field solve')
    for key in ('splu', '_port_mode', 'assemble_curlcurl_3d', 'assemble_edge_mass_3d'):
        monkeypatch.setattr(core, key, forbidden)
    doc = TEMPorts3DDocument.from_dict(data)
    assert doc.dumps() == normalize_saved(json.dumps(data)) == TEMPorts3DDocument.loads(doc.dumps()).dumps()


@pytest.mark.parametrize('path,value', [
    (('schema',), 'sipi.tem-ports-3d/2'), (('length_unit',), 'mm'),
    (('unprescribed_boundary',), 'open'), (('port_boundary',), 'multimode'), (('extra',), 1),
    (('mesh', 'extra'), 1), (('mesh', 'nodes'), []), (('mesh', 'nodes', 0), [0, 0]),
    (('mesh', 'nodes', 0, 0), True), (('mesh', 'nodes', 0, 0), 10**400),
    (('mesh', 'tetrahedra'), []), (('mesh', 'tetrahedra', 0), [0, 1, 2]),
    (('mesh', 'tetrahedra', 0, 0), True), (('mesh', 'tetrahedra', 0, 0), 1.0),
    (('ports',), {}), (('ports',), []), (('ports', 0, 'name'), []),
    (('ports', 0, 'extra'), 1), (('ports', 0, 'signal'), [True]),
    (('ports', 0, 'ground'), [1.0]), (('ports', 0, 'faces'), []),
    (('ports', 0, 'faces', 0), [0, 1]), (('ports', 0, 'faces', 0, 0), True),
    (('ports', 0, 'faces', 0, 0), 1.0), (('ports', 0, 'faces', 0, 0), -1),
    (('eps_r',), [4]), (('eps_r',), True), (('eps_r',), float('inf')),
    (('frequency_hz',), 1e9), (('frequency_hz',), []),
    (('frequency_hz', 0), True), (('frequency_hz', 0), 0), (('frequency_hz', 0), float('nan')),
])
def test_invalid_saved_values_rejected_before_numeric_coercion(path, value):
    data = document().to_dict(); parent = data
    for key in path[:-1]: parent = parent[key]
    parent[path[-1]] = value
    for load in (TEMPorts3DDocument.from_dict,):
        with pytest.raises(ValueError): load(data)
    with pytest.raises(ValueError): normalize_saved(json.dumps(data))


@pytest.mark.parametrize('fragment', ['"eps_r":NaN', '"eps_r":Infinity', '"eps_r":1e999',
                                      '"eps_r":4.0,"eps_r":4.0'])
def test_duplicate_keys_and_nonfinite_json_numbers_rejected(fragment):
    text = json.dumps(document().to_dict()).replace('"eps_r": 4.0', fragment)
    for load in (TEMPorts3DDocument.loads, normalize_saved, execute_saved):
        with pytest.raises(ValueError): load(text)


def test_missing_contract_and_duplicate_or_overlapping_ports_rejected():
    data = document().to_dict(); del data['port_boundary']
    with pytest.raises(ValueError): TEMPorts3DDocument.from_dict(data)
    data = document().to_dict(); data['ports'][1]['name'] = data['ports'][0]['name']
    with pytest.raises(ValueError, match='unique'): TEMPorts3DDocument.from_dict(data)
    data = document().to_dict(); data['ports'][1] = dict(data['ports'][0], name='other')
    with pytest.raises(ValueError, match='disjoint'): TEMPorts3DDocument.from_dict(data)


def test_frequency_budget_input_bytes_and_diagnostics_reject_before_field_work(monkeypatch):
    data = document().to_dict(); data['frequency_hz'] = [1e8, 5e8, 1e9]
    text = json.dumps(data)
    def forbidden(*args, **kwargs): pytest.fail('invalid transport option reached field work')
    monkeypatch.setattr(TEMPorts3DDocument, 'analyze', forbidden)
    with pytest.raises(ValueError, match='frequency count'):
        execute_saved(text, max_evaluations=2)
    with pytest.raises(ValueError, match='max_input_bytes'):
        execute_saved(text, max_input_bytes=len(text.encode())-1)
    with pytest.raises(ValueError, match='diagnostics'):
        execute_saved(text, diagnostics=['modes'])
    with pytest.raises(TypeError): TEMPorts3DDocument.loads(data)


def test_solver_failure_propagates_without_successful_partial_output(monkeypatch):
    text = document().dumps()
    def failed(*args, **kwargs): raise ValueError('Maxwell residual rejection at requested frequency')
    monkeypatch.setattr(TEMPorts3DDocument, 'analyze', failed)
    with pytest.raises(ValueError, match='Maxwell residual rejection'): execute_saved(text)
