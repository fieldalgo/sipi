# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved lines selecting the recovered P1 current method, and its versions."""
import json

import numpy as np
import pytest
from sipi import CrossSectionDocument
from sipi.conductor import surface_impedance
from sipi.default_line import DefaultPanelTransmissionLineDocument as Default
from sipi.execution import execute_saved, normalize_saved, saved_schemas
from sipi.line_model import TransmissionLineDocument
from sipi.method_line import MethodTransmissionLineDocument as Method
from sipi.recovered_conductor import recovered_surface_current_factors
from sipi.recovered_line import RecoveredTransmissionLineDocument as Recovered
from sipi.templates import microstrip

W = 'volume-p1-recovered'
PANEL = dict(panels_per_edge=64, ground_modes=512, interpolation_degree=14)
METAL = dict(conductivity=58e6, relative_permeability=1., roughness=dict(kind='hammerstad', rms_m=0.))
SURFACE = dict(kind='surface', ground_thickness=35e-6, **METAL)
BOUNDARIES = dict(kind='surface-boundaries', ground_thickness=35e-6, conductors={'signal': METAL},
                  reference=dict(METAL, conductivity=41e6))


def section(**changes):
    return CrossSectionDocument(microstrip(**dict(dict(width=.3e-3, substrate_height=.2e-3, eps_r=4,
                                                       thickness=35e-6), **changes)))


def line(conductor=SURFACE, schema='sipi.transmission-line/3', **changes):
    return TransmissionLineDocument(section(**changes), [1e9, 5e9], materials={}, conductor=conductor,
                                    length=.02, schema=schema)


def test_recovered_document_is_strict_and_canonical():
    doc = Recovered(line())
    text = doc.dumps()
    assert json.loads(text)['recovery'] == dict(support_fraction=.4)
    assert Recovered.loads(text).dumps() == text and normalize_saved(text) == text
    assert {'sipi.recovered-transmission-line/1', 'sipi.method-transmission-line/2',
            'sipi.transmission-line/9'} <= set(saved_schemas())
    data = doc.to_dict()
    for change, match in [(lambda d: d.update(extra=1), 'recovered transmission line'),
                          (lambda d: d['recovery'].update(extra=1), 'recovery controls'),
                          (lambda d: d['recovery'].update(support_fraction=.5), 'support_fraction'),
                          (lambda d: d['recovery'].update(support_fraction=True), 'support_fraction'),
                          (lambda d: d.update(schema='sipi.recovered-transmission-line/2'), 'schema'),
                          (lambda d: d['line'].update(schema='sipi.transmission-line/8'), '/1 through /7')]:
        bad = json.loads(json.dumps(data))
        change(bad)
        with pytest.raises(ValueError, match=match):
            Recovered.from_dict(bad)
    with pytest.raises(ValueError, match="perfect.*'volume-p1'"):
        Recovered(line(dict(kind='perfect')))
    with pytest.raises(TypeError):
        Recovered(line().to_dict())


@pytest.mark.parametrize('conductor', [SURFACE, BOUNDARIES], ids=['surface', 'boundaries'])
def test_recovered_line_uses_library_factors_on_the_same_mesh(conductor):
    nested = line(conductor)
    result = Recovered(nested, support_fraction=.3).analyze()
    meshed = nested.cross_section.section.mesh(**nested.cross_section.mesh_options)
    factors = recovered_surface_current_factors(meshed.mesh, meshed.signals, meshed.ground,
                                                support_fraction=.3)
    for key in ('parts', 'current_integrals', 'C0'):
        np.testing.assert_array_equal(getattr(result.current_factors, key), getattr(factors, key))
    assert dict(result.current_factors.diagnostics) == dict(factors.diagnostics)
    volume = nested.analyze()
    for key in ('C', 'G'):
        np.testing.assert_array_equal(getattr(result, key), getattr(volume, key))
    np.testing.assert_array_equal(result.dielectric.L, volume.dielectric.L)
    f = np.array([1e9, 5e9])
    signal = surface_impedance(f, conductivity=58e6)
    if conductor is SURFACE:
        np.testing.assert_array_equal(result.conductor.R, signal.real[:, None, None]*factors.total)
    else:
        reference = surface_impedance(f, conductivity=41e6)
        expected = signal.real[:, None, None]*factors.parts[0]+reference.real[:, None, None]*factors.parts[1]
        np.testing.assert_allclose(result.conductor.R, expected, rtol=1e-14, atol=0)
    assert np.all(result.R[:, 0, 0] > volume.R[:, 0, 0])  # the P1 gradient factor is low


def test_uncharacterised_geometry_is_refused_not_replaced():
    doc = Method(line(top_width=.25e-3), current_method=W, recovery=dict(support_fraction=.4),
                 schema='sipi.method-transmission-line/2')
    with pytest.raises(ValueError, match='trapezoid'):
        doc.analyze()
    with pytest.raises(ValueError, match='trapezoid'):
        execute_saved(doc.dumps())


def test_method_version_2_keeps_version_1_meanings_and_adds_recovered():
    v1 = dict(schema='sipi.method-transmission-line/1')
    v2 = dict(schema='sipi.method-transmission-line/2')
    for method, extra in (('volume-p1', {}), ('panel', dict(panel=PANEL))):
        first = Method(line(), current_method=method, **extra)
        second = Method(line(), current_method=method, **extra, **v2)
        assert first.to_dict() == dict(second.to_dict(), **v1)
        assert first.equivalent_document().dumps() == second.equivalent_document().dumps()
    with pytest.raises(ValueError, match="requires sipi.method-transmission-line/2"):
        Method(line(), current_method=W, recovery=dict(support_fraction=.4))
    with pytest.raises(ValueError, match='method transmission line'):
        Method(line(), current_method=W, **v2)  # recovery controls are required
    with pytest.raises(ValueError, match='method transmission line'):
        Method(line(), current_method='volume-p1', recovery=dict(support_fraction=.4), **v2)
    doc = Method(line(), current_method=W, recovery=dict(support_fraction=.35), **v2)
    assert Method.loads(doc.dumps()).dumps() == doc.dumps() == normalize_saved(doc.dumps())
    equivalent = doc.equivalent_document()
    assert isinstance(equivalent, Recovered)
    assert equivalent.to_dict() == dict(schema='sipi.recovered-transmission-line/1', line=line().to_dict(),
                                        recovery=dict(support_fraction=.35))


def test_line_version_9_defaults_to_panel_and_records_recovery():
    args = (section(), [1e9, 5e9])
    kwargs = dict(materials={}, conductor=SURFACE, length=.02)
    eight = Default(*args, **kwargs)
    nine = Default(*args, **kwargs, schema='sipi.transmission-line/9')
    assert nine.current_method == 'panel'
    assert eight.to_dict() == dict(nine.to_dict(), schema='sipi.transmission-line/8')
    assert eight.equivalent_document().dumps() == nine.equivalent_document().dumps()
    named = Default(*args, **kwargs, current_method=W, schema='sipi.transmission-line/9')
    assert named.to_dict()['recovery'] == dict(support_fraction=.4) and 'panel' not in named.to_dict()
    assert Default.loads(named.dumps()).dumps() == named.dumps() == normalize_saved(named.dumps())
    assert named.method_document().to_dict()['schema'] == 'sipi.method-transmission-line/2'
    with pytest.raises(ValueError, match='requires sipi.transmission-line/9'):
        Default(*args, **kwargs, current_method=W)
    with pytest.raises(ValueError, match='transmission line'):
        Default(*args, **kwargs, recovery=dict(support_fraction=.4))  # version 8 has no recovery field
    with pytest.raises(ValueError, match='recovery controls require'):
        Default(*args, **kwargs, recovery=dict(support_fraction=.4), schema='sipi.transmission-line/9')
    with pytest.raises(ValueError, match='panel controls require'):
        Default(*args, **kwargs, current_method=W, panel=PANEL, schema='sipi.transmission-line/9')
    with pytest.raises(ValueError, match='perfect'):
        Default(*args, materials={}, conductor=dict(kind='perfect'), length=.02, current_method=W,
                schema='sipi.transmission-line/9')


def test_execution_records_method_and_diagnostics_bit_identically():
    nested = line()
    direct = Recovered(nested).analyze()
    expected = execute_saved(Recovered(nested).dumps())
    solver = expected['result']['current_solver']
    assert solver['kind'] == 'p1-volume-shape-derivative' and solver['settings'] == dict(support_fraction=.4)
    assert solver['diagnostics'] == {key: (list(v) if isinstance(v, tuple) else v)
                                     for key, v in direct.current_factors.diagnostics.items()}
    assert solver['surface_current_factors_per_m'] == direct.current_factors.parts.tolist()
    assert expected['result']['R_ohm_per_m'] == execute_saved(Recovered(nested).dumps())['result']['R_ohm_per_m']
    for doc in (Method(nested, current_method=W, recovery=dict(support_fraction=.4),
                       schema='sipi.method-transmission-line/2'),
                Default(section(), [1e9, 5e9], materials={}, conductor=SURFACE, length=.02,
                        current_method=W, schema='sipi.transmission-line/9')):
        out = execute_saved(doc.dumps())
        assert out['status'] == 'complete' and out['input'] == doc.to_dict()
        assert out['result']['current_method'] == dict(method=W,
                                                       equivalent_schema='sipi.recovered-transmission-line/1')
        assert out['result']['current_solver'] == solver
        for key in ('R_ohm_per_m', 'L_h_per_m', 'G_s_per_m', 'C_f_per_m', 'network'):
            assert out['result'][key] == expected['result'][key]
