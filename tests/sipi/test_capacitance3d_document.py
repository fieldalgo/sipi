# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit-mesh replay, strict rejection and transport parity for static C."""
import json

import numpy as np
import pytest
from galerkin.mesh3d import box_mesh

from sipi.capacitance3d import extract_capacitance_3d
from sipi.capacitance3d_document import Capacitance3DDocument
from sipi.constants import epsilon_0
from sipi.execution import execute_saved, normalize_saved


def plate(layered=False):
    mesh = box_mesh(.004, .003, .002, 2, 2, 2)
    eps = np.where(mesh.nodes[mesh.tets].mean(axis=1)[:, 2] < .001, 2., 6.) if layered else 3.8
    kwargs = dict(eps_r=eps, conductors={'상부': mesh.boundary['z1']}, ground=mesh.boundary['z0'])
    return mesh, kwargs


def data():
    mesh, kwargs = plate()
    return Capacitance3DDocument(mesh, **kwargs).to_dict()


@pytest.mark.parametrize('layered', [False, True])
def test_roundtrip_direct_api_transport_and_analytical_plate(layered):
    mesh, kwargs = plate(layered)
    direct = extract_capacitance_3d(mesh, **kwargs)
    document = Capacitance3DDocument(mesh, **kwargs)
    restored = Capacitance3DDocument.loads(document.dumps())
    assert restored.dumps() == document.dumps() == normalize_saved(document.dumps())
    np.testing.assert_array_equal(restored.analyze().C, direct.C)
    np.testing.assert_array_equal(restored.analyze().potentials, direct.potentials)
    out = execute_saved(document.dumps())
    assert out['input'] == document.to_dict() and out['status'] == 'complete' and out['error'] is None
    result = out['result']
    assert result['model'] == 'bounded-static-3d' and result['names'] == ['상부']
    np.testing.assert_array_equal(result['capacitance_f'], direct.C)
    np.testing.assert_array_equal(result['energy_capacitance_f'], direct.energy_C)
    np.testing.assert_array_equal(result['ground_charge_c_at_unit_voltage'], direct.ground_charge)
    assert result['mesh'] == dict(nodes=mesh.num_nodes, tetrahedra=len(mesh.tets))
    for key, value in result['consistency'].items():
        assert value == getattr(direct, key)
    assert 'potentials' not in result and 'tetrahedra' not in result
    expected = epsilon_0*.004*.003/(.001/2+.001/6) if layered else epsilon_0*3.8*.004*.003/.002
    assert result['capacitance_f'][0][0] == pytest.approx(expected, rel=1e-11)
    json.dumps(out, allow_nan=False)


def test_order_is_a_list_and_snapshot_is_detached():
    mesh = box_mesh(.004, .003, .002, 4, 4, 4)
    ground = np.flatnonzero(np.isclose(mesh.nodes[:, 0], .002))
    kwargs = dict(conductors={'z-last': mesh.boundary['x0'], 'a-first': mesh.boundary['x1']}, ground=ground)
    direct = extract_capacitance_3d(mesh, **kwargs)
    doc = Capacitance3DDocument(mesh, **kwargs)
    serialized = doc.to_dict()
    replay = Capacitance3DDocument.from_dict(serialized)
    serialized['mesh']['nodes'][0][0] = 999
    serialized['conductors'].reverse()
    mesh.nodes[:] = 0
    kwargs['conductors']['z-last'][:] = 0
    assert replay.dumps() == doc.dumps()
    out = execute_saved(replay.dumps())['result']
    assert out['names'] == ['z-last', 'a-first']
    np.testing.assert_array_equal(out['capacitance_f'], direct.C)
    reversed_data = doc.to_dict(); reversed_data['conductors'].reverse()
    reverse = execute_saved(json.dumps(reversed_data))['result']
    np.testing.assert_array_equal(reverse['capacitance_f'], direct.C[::-1, ::-1])


def test_normalization_never_assembles_or_solves(monkeypatch):
    text = json.dumps(data())
    def forbidden(*args, **kwargs):
        pytest.fail('validation performed a field calculation')
    import sipi.capacitance3d as core
    monkeypatch.setattr(core, 'assemble_stiffness_3d', forbidden)
    monkeypatch.setattr(core, 'splu', forbidden)
    canonical = normalize_saved(text)
    assert canonical == Capacitance3DDocument.loads(text).dumps()


@pytest.mark.parametrize('path,value', [
    (('schema',), 'sipi.capacitance-3d/2'), (('length_unit',), 'mm'),
    (('unprescribed_boundary',), 'open'), (('extra',), 1),
    (('mesh', 'extra'), 1), (('mesh', 'nodes'), []),
    (('mesh', 'nodes', 0), [0, 0]), (('mesh', 'nodes', 0, 0), True),
    (('mesh', 'nodes', 0, 0), float('nan')), (('mesh', 'nodes', 0, 0), 10**400),
    (('mesh', 'tetrahedra'), []), (('mesh', 'tetrahedra', 0), [0, 1, 2]),
    (('mesh', 'tetrahedra', 0, 0), True), (('mesh', 'tetrahedra', 0, 0), 1.5),
    (('mesh', 'tetrahedra', 0, 0), 1.0), (('mesh', 'tetrahedra', 0, 0), -1),
    (('mesh', 'tetrahedra', 0, 0), 10**100),
    (('conductors',), {}), (('conductors',), []), (('conductors', 0, 'name'), []),
    (('conductors', 0, 'name'), ' '), (('conductors', 0, 'nodes'), [True]),
    (('conductors', 0, 'extra'), 1), (('conductors', 0, 'nodes'), [1.0]),
    (('ground',), []), (('ground',), [False]), (('ground',), [1, 1]),
    (('eps_r',), 0), (('eps_r',), True), (('eps_r',), [1]),
    (('eps_r',), [True]*48), (('eps_r',), float('inf')), (('eps_r',), '3.8'),
])
def test_invalid_values_are_rejected_before_coercion(path, value):
    bad = data(); parent = bad
    for key in path[:-1]: parent = parent[key]
    parent[path[-1]] = value
    with pytest.raises(ValueError): Capacitance3DDocument.from_dict(bad)
    with pytest.raises(ValueError): normalize_saved(json.dumps(bad))


def test_missing_duplicate_and_conflicting_boundaries_rejected():
    bad = data(); del bad['unprescribed_boundary']
    with pytest.raises(ValueError): Capacitance3DDocument.from_dict(bad)
    bad = data(); bad['conductors'].append(bad['conductors'][0].copy())
    with pytest.raises(ValueError, match='unique'): Capacitance3DDocument.from_dict(bad)
    bad = data(); bad['ground'] = bad['conductors'][0]['nodes']
    with pytest.raises(ValueError, match='disjoint'): Capacitance3DDocument.from_dict(bad)
    bad = data(); bad['mesh']['tetrahedra'].append(bad['mesh']['tetrahedra'][0])
    with pytest.raises(ValueError, match='duplicate'): Capacitance3DDocument.from_dict(bad)


@pytest.mark.parametrize('fragment', ['"eps_r":NaN', '"eps_r":Infinity',
    '"eps_r":1e999', '"eps_r":3.8,"eps_r":3.8'])
def test_raw_text_ambiguity_and_overflow_rejected(fragment):
    text = json.dumps(data()).replace('"eps_r": 3.8', fragment)
    for load in (Capacitance3DDocument.loads, normalize_saved, execute_saved):
        with pytest.raises(ValueError): load(text)


def test_budget_and_line_diagnostics_do_not_solve_static_mesh(monkeypatch):
    text = json.dumps(data())
    def forbidden(*args, **kwargs): pytest.fail('invalid transport options reached a solve')
    monkeypatch.setattr(Capacitance3DDocument, 'analyze', forbidden)
    with pytest.raises(ValueError, match='max_input_bytes'):
        execute_saved(text, max_input_bytes=len(text.encode())-1)
    with pytest.raises(ValueError, match='diagnostics'):
        execute_saved(text, diagnostics=['modes'])
    with pytest.raises(TypeError): Capacitance3DDocument.loads(data())
