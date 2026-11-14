# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved magnetic materials are physical names, never mesh indices."""
import copy
import numpy as np
import pytest
from sipi import CrossSectionDocument
from sipi.circuit_document import CircuitDocument
from sipi.conductor_mesh import mesh_conductor_section
from sipi.dielectric import ConstantDielectric
from sipi.execution import execute_saved, normalize_saved
from sipi.termination import terminate_network
from sipi.volume_line import VolumeLineDocument, volume_line
from test_core_document import document as core_document
from test_metal_cores import CORE, OPTIONS, section, volume, conductivity

NAMED = dict(signals={'signal': 5.}, ground=3., nonmetal=1., cores={'signal': 2.})


def document():
    return VolumeLineDocument(CrossSectionDocument(section()), [0, 1e3, 1e4],
        materials={}, mesh=dict(OPTIONS, min_angle=28.), length=.1,
        conductivity=dict(signals={'signal': 20e6}, ground=58e6),
        relative_permeability=NAMED,
        metal_cores={'signal': dict(vertices=CORE, conductivity=58e6)})


@pytest.fixture(scope='module')
def saved():
    doc = document()
    return doc, doc.analyze(keep_fields=True)


def test_magnetic_roundtrip_copies_names_and_does_not_mesh(monkeypatch):
    import sipi.volume_line as implementation
    monkeypatch.setattr(implementation, 'mesh_conductor_section', lambda *a, **k: pytest.fail('Normalization meshed'))
    raw = document().to_dict()
    doc = VolumeLineDocument.from_dict(raw)
    text = doc.dumps()
    assert raw['schema'] == 'sipi.volume-line/4'
    assert normalize_saved(text) == VolumeLineDocument.loads(text).dumps() == text
    raw['conductor']['relative_permeability']['cores']['signal'] = 100.
    raw['metal_cores']['signal']['vertices'][0][0] = 1.
    doc.to_dict()['conductor']['relative_permeability']['signals'].clear()
    assert doc.dumps() == text


def test_saved_magnetics_match_direct_all_fields_and_dc(saved):
    doc, result = saved
    v = volume()
    mu = np.ones(v.mesh.num_triangles)
    mu[v.signals['signal']] = 5.
    mu[v.ground] = 3.
    mu[v.core_triangles['signal']] = 2.
    direct = volume_line(v, [0, 1e3, 1e4], conductivity=conductivity(v),
        relative_permeability=mu, length=.1, keep_fields=True,
        materials={l.name: ConstantDielectric(l.eps_r, l.tan_delta) for l in section().layers})
    for name in ('R', 'L', 'C', 'G'):
        np.testing.assert_array_equal(getattr(result, name), getattr(direct, name))
    np.testing.assert_array_equal(result.network.s, direct.network.s)
    np.testing.assert_array_equal(result.conductor.current_density, direct.conductor.current_density)
    area = .36e-3*.06e-3
    exact = 1/(58e6*area+20e6*(.4e-3*.1e-3-area))+1/(58e6*.002*.1e-3)
    assert result.R[0, 0, 0] == pytest.approx(exact, rel=1e-10)
    assert result.input_json == doc.dumps()


def test_saved_magnetics_common_execution_and_circuit(saved):
    doc, result = saved
    output = execute_saved(doc.dumps())
    assert output['input'] == doc.to_dict() and output['status'] == 'complete'
    for name, field in [('R', 'R_ohm_per_m'), ('L', 'L_h_per_m'), ('C', 'C_f_per_m'), ('G', 'G_s_per_m')]:
        np.testing.assert_array_equal(output['result'][field], getattr(result, name))
    circuit = CircuitDocument(dict(kind='volume-line', document=doc.to_dict()),
        excitation=dict(kind='sources', voltages={'near:signal': 1.}),
        terminations={'far:signal': 75.})
    result2 = CircuitDocument.loads(circuit.dumps()).analyze()
    expected = terminate_network(result.network, source_voltages={'near:signal': 1.},
                                 terminations={'far:signal': 75.})
    np.testing.assert_array_equal(result2.network.s, result.network.s)
    np.testing.assert_allclose(result2.response.voltage, expected.voltage, rtol=1e-12, atol=0)


def test_named_magnetics_without_core_preserve_uniform_scalar():
    data = document().to_dict()
    data['metal_cores'] = {}
    data['conductor']['relative_permeability'] = dict(signals={'signal': 2.}, ground=2., nonmetal=2., cores={})
    named = VolumeLineDocument.from_dict(data).analyze()
    scalar_data = copy.deepcopy(data)
    scalar_data.pop('metal_cores')
    scalar_data['schema'] = 'sipi.volume-line/2'
    scalar_data['conductor']['relative_permeability'] = 2.
    scalar = VolumeLineDocument.from_dict(scalar_data).analyze()
    for name in ('R', 'L', 'C', 'G'):
        a, b = getattr(named, name), getattr(scalar, name)
        assert np.max(abs(a-b))/np.max(abs(b)) < 1e-13
    assert np.max(abs(named.network.s-scalar.network.s)) < 1e-13
    doc = VolumeLineDocument(CrossSectionDocument(section()), [0], materials={},
        mesh=dict(OPTIONS, min_angle=28.), length=.1,
        conductivity=dict(signals={'signal': 20e6}, ground=58e6),
        relative_permeability=data['conductor']['relative_permeability'])
    assert doc.to_dict()['schema'] == 'sipi.volume-line/4' and doc.to_dict()['metal_cores'] == {}


def test_saved_remeshing_reassigns_magnetic_materials(saved):
    doc, original = saved
    data = doc.to_dict()
    for key in ('metal_size', 'far_size', 'grade'): data['mesh'][key] /= 2
    fine = VolumeLineDocument.from_dict(data).analyze(keep_fields=True)
    v = mesh_conductor_section(section(), **data['mesh'], dielectric_interfaces=True, metal_cores={'signal': CORE})
    mu = np.ones(v.mesh.num_triangles)
    mu[v.signals['signal']] = 5.
    mu[v.ground] = 3.
    mu[v.core_triangles['signal']] = 2.
    direct = v.impedance(data['frequency_hz'], conductivity=conductivity(v), relative_permeability=mu, keep_fields=True)
    np.testing.assert_array_equal(fine.L, direct.L)
    np.testing.assert_array_equal(fine.conductor.current_density, direct.current_density)
    np.testing.assert_allclose(fine.R[0], original.R[0], rtol=1e-10, atol=0)


def test_grounded_core_has_own_permeability_and_common_return():
    from sipi import CrossSection, Trace
    base = section()
    cs = CrossSection(base.layers, [*base.traces,
        Trace('shield', .00065, .3e-3, .5e-3, .1e-3, ground=True)], base.width)
    core = ((.00055, .00052), (.00075, .00052), (.00075, .00058), (.00055, .00058))
    doc = VolumeLineDocument(CrossSectionDocument(cs), [0, 1e4], materials={},
        mesh=dict(OPTIONS, min_angle=28.), length=.1,
        conductivity=dict(signals={'signal': 58e6}, ground=20e6),
        metal_cores={'shield': dict(vertices=core, conductivity=58e6)},
        relative_permeability=dict(signals={'signal': 2.}, ground=3., nonmetal=1., cores={'shield': 5.}))
    saved = VolumeLineDocument.loads(doc.dumps()).analyze(keep_fields=True)
    v = volume(cs=cs, cores={'shield': core})
    sigma = np.zeros(v.mesh.num_triangles)
    sigma[v.signals['signal']] = 58e6
    sigma[v.ground] = 20e6
    sigma[v.core_triangles['shield']] = 58e6
    mu = np.ones(v.mesh.num_triangles)
    mu[v.signals['signal']] = 2.
    mu[v.ground] = 3.
    mu[v.core_triangles['shield']] = 5.
    direct = v.impedance([0, 1e4], conductivity=sigma, relative_permeability=mu, keep_fields=True)
    np.testing.assert_array_equal(saved.R, direct.R)
    np.testing.assert_array_equal(saved.L, direct.L)
    np.testing.assert_array_equal(saved.conductor.current_density, direct.current_density)
    assert saved.names == ('signal',)


@pytest.mark.parametrize('name', ['ground', '_bottom'])
def test_signal_name_does_not_overwrite_return_or_generated_plate(name):
    data = document().to_dict()
    data['cross_section']['traces'][0]['name'] = name
    data['metal_cores'][name] = data['metal_cores'].pop('signal')
    for field, maps in [('conductivity', ('signals',)), ('relative_permeability', ('signals', 'cores'))]:
        for key in maps:
            values = data['conductor'][field][key]
            values[name] = values.pop('signal')
    data['frequency_hz'] = [0]
    result = VolumeLineDocument.from_dict(data).analyze()
    original = document().analyze()
    np.testing.assert_allclose(result.R[0], original.R[0], rtol=1e-13, atol=0)
    np.testing.assert_allclose(result.L[0], original.L[0], rtol=1e-13, atol=0)
    assert result.names == (name,)


@pytest.mark.parametrize('edit', ['scalar', 'missing-signal', 'extra-signal', 'missing-core',
    'extra-core', 'nonmetal-as-signal', 'missing-field', 'extra-field', 'negative', 'bool',
    'nan', 'array', 'complex', 'zero-ground', 'zero-nonmetal', 'scalar-conductivity', 'no-cores-field'])
def test_invalid_magnetic_documents_fail_before_meshing(monkeypatch, edit):
    import sipi.volume_line as implementation
    data = document().to_dict()
    mu = data['conductor']['relative_permeability']
    if edit == 'scalar': data['conductor']['relative_permeability'] = 2.
    elif edit == 'missing-signal': mu['signals'] = {}
    elif edit == 'extra-signal': mu['signals']['extra'] = 2.
    elif edit == 'missing-core': mu['cores'] = {}
    elif edit == 'extra-core': mu['cores']['extra'] = 2.
    elif edit == 'nonmetal-as-signal': mu['signals'] = {'nonmetal': 2.}
    elif edit == 'missing-field': mu.pop('nonmetal')
    elif edit == 'extra-field': mu['roughness'] = 0.
    elif edit == 'zero-ground': mu['ground'] = 0.
    elif edit == 'zero-nonmetal': mu['nonmetal'] = 0.
    elif edit == 'scalar-conductivity': data['conductor']['conductivity'] = 58e6
    elif edit == 'no-cores-field': data.pop('metal_cores')
    else: mu['cores']['signal'] = dict(negative=-1., bool=True, nan=float('nan'), array=[2.], complex=1+1j)[edit]
    monkeypatch.setattr(implementation, 'mesh_conductor_section', lambda *a, **k: pytest.fail('Invalid magnetics meshed'))
    with pytest.raises(ValueError): VolumeLineDocument.from_dict(data).analyze()


def test_earlier_schemas_do_not_accept_named_permeability():
    for version in (1, 2, 3):
        data = core_document().to_dict()
        data['schema'] = f'sipi.volume-line/{version}'
        data['conductor']['relative_permeability'] = NAMED
        if version < 3: data.pop('metal_cores')
        if version == 1: data['conductor']['conductivity'] = 58e6
        with pytest.raises(ValueError): VolumeLineDocument.from_dict(data)


def test_saved_magnetic_resolution_failure_is_preserved():
    data = document().to_dict()
    data['frequency_hz'] = [0, 1e8]
    with pytest.raises(ValueError, match='skin depth'):
        execute_saved(VolumeLineDocument.from_dict(data).dumps())
