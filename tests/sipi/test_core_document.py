# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Core/coating JSON: physical names and coordinates survive remeshing."""
import copy
import numpy as np
import pytest
from sipi import CrossSection, CrossSectionDocument, Trace
from sipi.circuit_document import CircuitDocument
from sipi.dielectric import ConstantDielectric
from sipi.execution import execute_saved, normalize_saved
from sipi.termination import terminate_network
from sipi.volume_line import VolumeLineDocument, volume_line
from test_metal_cores import CORE, OPTIONS, F, section, volume, conductivity


def document():
    return VolumeLineDocument(CrossSectionDocument(section()), F, materials={},
        mesh=dict(OPTIONS, min_angle=28.), length=.1,
        conductivity=dict(signals={'signal': 20e6}, ground=58e6),
        metal_cores={'signal': dict(vertices=CORE, conductivity=58e6)})


@pytest.fixture(scope='module')
def saved():
    doc = document()
    return doc, doc.analyze(keep_fields=True)


def test_strict_roundtrip_copies_geometry_without_meshing(monkeypatch):
    import sipi.volume_line as implementation
    monkeypatch.setattr(implementation, 'mesh_conductor_section', lambda *a, **k: pytest.fail('Normalization meshed'))
    raw = document().to_dict()
    doc = VolumeLineDocument.from_dict(raw)
    text = doc.dumps()
    assert raw['schema'] == 'sipi.volume-line/3'
    assert normalize_saved(text) == VolumeLineDocument.loads(text).dumps() == text
    raw['metal_cores']['signal']['vertices'][0][0] = 1.
    raw['metal_cores']['signal']['conductivity'] = 1.
    doc.to_dict()['metal_cores'].clear()
    assert doc.dumps() == text


def test_saved_direct_fields_and_exact_dc(saved):
    doc, result = saved
    v = volume()
    direct = volume_line(v, F, materials={l.name: ConstantDielectric(l.eps_r, l.tan_delta)
        for l in section().layers}, conductivity=conductivity(v), length=.1, keep_fields=True)
    for key in ('R', 'L', 'C', 'G'):
        np.testing.assert_array_equal(getattr(result, key), getattr(direct, key))
    np.testing.assert_array_equal(result.network.s, direct.network.s)
    np.testing.assert_array_equal(result.conductor.current_density, direct.conductor.current_density)
    core_area, area = .36e-3*.06e-3, .4e-3*.1e-3
    exact = 1/(58e6*core_area+20e6*(area-core_area))+1/(58e6*.002*.1e-3)
    assert result.R[0, 0, 0] == pytest.approx(exact, rel=1e-10)
    assert result.input_json == doc.dumps()


def test_executor_and_nested_circuit_replay_same_network(saved):
    doc, result = saved
    output = execute_saved(doc.dumps())
    assert output['status'] == 'complete' and output['input'] == doc.to_dict()
    for key, field in [('R', 'R_ohm_per_m'), ('L', 'L_h_per_m'), ('C', 'C_f_per_m'), ('G', 'G_s_per_m')]:
        np.testing.assert_array_equal(output['result'][field], getattr(result, key))
    circuit = CircuitDocument(dict(kind='volume-line', document=doc.to_dict()),
        excitation=dict(kind='sources', voltages={'near:signal': 1.}),
        terminations={'far:signal': 75.})
    restored = CircuitDocument.loads(circuit.dumps())
    actual = restored.analyze()
    expected = terminate_network(result.network, source_voltages={'near:signal': 1.},
                                 terminations={'far:signal': 75.})
    np.testing.assert_array_equal(actual.network.s, result.network.s)
    np.testing.assert_allclose(actual.response.voltage, expected.voltage, rtol=1e-12, atol=0)
    np.testing.assert_allclose(actual.response.current, expected.current, rtol=1e-12, atol=0)
    assert restored.to_dict()['network']['document'] == doc.to_dict()


def test_saved_remeshing_reassigns_coordinates_and_conductivity(saved):
    doc, previous = saved
    data = doc.to_dict()
    for key in ('metal_size', 'far_size', 'grade'): data['mesh'][key] /= 2
    result = VolumeLineDocument.from_dict(data).analyze(keep_fields=True)
    assert result.conductor.current_density.shape != previous.conductor.current_density.shape
    np.testing.assert_allclose(result.R[0], previous.R[0], rtol=1e-10, atol=0)
    assert max(result.conductor.current_error) < 1e-10


def test_explicit_ground_core_retains_common_return_dc():
    base = section()
    shield = Trace('shield', .00065, .3e-3, .5e-3, .1e-3, ground=True)
    cs = CrossSection(base.layers, [*base.traces, shield], base.width)
    vertices = ((.00055, .00052), (.00075, .00052), (.00075, .00058), (.00055, .00058))
    doc = VolumeLineDocument(CrossSectionDocument(cs), [0], materials={},
        mesh=dict(OPTIONS, min_angle=28.), length=.1,
        conductivity=dict(signals={'signal': 58e6}, ground=20e6),
        metal_cores={'shield': dict(vertices=vertices, conductivity=58e6)})
    result = VolumeLineDocument.loads(doc.dumps()).analyze()
    area = .2e-3*.06e-3
    exact = 1/(58e6*.4e-3*.1e-3)+1/(58e6*area+20e6*((.002+.3e-3)*.1e-3-area))
    assert result.R[0, 0, 0] == pytest.approx(exact, rel=1e-10)
    assert result.names == ('signal',)


@pytest.mark.parametrize('bad', [None, {}, [], {'unknown': dict(vertices=CORE, conductivity=58e6)},
    {'signal': {}}, {'signal': dict(vertices=CORE)},
    {'signal': dict(vertices=CORE, conductivity=58e6, thickness=1e-6)},
    *[{'signal': dict(vertices=CORE, conductivity=v)} for v in (True, 0, -1, float('nan'), float('inf'), [58e6])],
    {'signal': dict(vertices=[(0, 0)], conductivity=58e6)},
    {'signal': dict(vertices=((-2e-4, .00052), (2e-4, .00052), (2e-4, .00058)), conductivity=58e6)},
], ids=['none', 'empty', 'list', 'unknown', 'missing-both', 'missing-material', 'extra',
        'bool', 'zero', 'negative', 'nan', 'infinite', 'array', 'short', 'touch'])
def test_invalid_core_data_fails_before_meshing(monkeypatch, bad):
    import sipi.volume_line as implementation
    data = document().to_dict()
    data['metal_cores'] = bad
    monkeypatch.setattr(implementation, 'mesh_conductor_section', lambda *a, **k: pytest.fail('Invalid input meshed'))
    with pytest.raises(ValueError): VolumeLineDocument.from_dict(data).analyze()


def test_versions_cannot_drop_or_invent_interfaces():
    data = document().to_dict()
    for version in (1, 2):
        with pytest.raises(ValueError):
            VolumeLineDocument.from_dict(dict(data, schema=f'sipi.volume-line/{version}'))
    absent = copy.deepcopy(data)
    del absent['metal_cores']
    with pytest.raises(ValueError): VolumeLineDocument.from_dict(absent)
    scalar = copy.deepcopy(data)
    scalar['conductor']['conductivity'] = 58e6
    with pytest.raises(ValueError): VolumeLineDocument.from_dict(scalar)
    text = document().dumps()
    with pytest.raises(ValueError):
        VolumeLineDocument.loads(text.replace('"metal_cores": {', '"metal_cores": {}, "metal_cores": {'))


def test_saved_core_keeps_skin_depth_failure_transport():
    data = document().to_dict()
    data['frequency_hz'] = [0, 1e8]
    with pytest.raises(ValueError, match='skin depth'):
        execute_saved(VolumeLineDocument.from_dict(data).dumps())
