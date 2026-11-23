# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit conductor-current method lines run existing documents unchanged."""
import json
import numpy as np
import pytest
from sipi import CrossSectionDocument
from sipi.templates import microstrip, stripline, unbacked_coplanar, grounded_coplanar
from sipi.line_model import TransmissionLineDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.two_ground_panel_line import TwoGroundPanelTransmissionLineDocument
from sipi.method_line import MethodTransmissionLineDocument as Method
from sipi.execution import execute_saved, normalize_saved, saved_schemas

MESH = dict(edge_size=2.5e-6, far_size=.1e-3, grade=.05)
PANEL = dict(panels_per_edge=64, ground_modes=512, interpolation_degree=14)
ROUGH = dict(kind='surface', conductivity=58e6, ground_thickness=35e-6, relative_permeability=1.,
             roughness=dict(kind='hammerstad', rms_m=.5e-6))


def section(kind='microstrip', **changes):
    make = dict(microstrip=lambda: microstrip(width=.3e-3, substrate_height=.2e-3, eps_r=4, thickness=35e-6),
                stripline=lambda: stripline(width=.2e-3, plane_spacing=.5e-3, eps_r=4, thickness=17.5e-6),
                unbacked=lambda: unbacked_coplanar(width=.3e-3, gap=.2e-3, ground_width=1e-3,
                                                   substrate_height=.2e-3, eps_r=4, thickness=35e-6),
                flat=lambda: microstrip(width=.3e-3, substrate_height=.2e-3, eps_r=4))[kind]
    return CrossSectionDocument(make(), mesh=MESH)


def line(kind='microstrip', conductor=ROUGH, schema='sipi.transmission-line/2', frequency=(1e9, 5e9)):
    return TransmissionLineDocument(section(kind), list(frequency), materials={}, conductor=conductor,
                                    length=.02, schema=schema)


def same(a, b):
    for key in 'RLGC':
        np.testing.assert_array_equal(getattr(a, key), getattr(b, key))
    np.testing.assert_array_equal(a.network.s, b.network.s)


def test_method_is_required_and_strict():
    with pytest.raises(TypeError):
        Method(line())
    for kwargs in (dict(current_method='auto'), dict(current_method=None),
                   dict(current_method='volume-p1', panel=PANEL), dict(current_method='panel')):
        with pytest.raises(ValueError):
            Method(line(), **kwargs)
    with pytest.raises(ValueError, match='panel controls'):
        Method(line(), current_method='panel', panel=dict(PANEL, extra=1))
    with pytest.raises(TypeError):
        Method(line().to_dict(), current_method='volume-p1')
    doc = Method(line(), current_method='panel', panel=PANEL)
    text = doc.dumps()
    assert Method.loads(text).dumps() == text and normalize_saved(text) == text
    assert 'sipi.method-transmission-line/1' in saved_schemas()
    assert set(doc.to_dict()) == {'schema', 'line', 'current_method', 'panel'}
    assert set(Method(line(), current_method='volume-p1').to_dict()) == {'schema', 'line', 'current_method'}
    with pytest.raises(ValueError, match='duplicate'):
        Method.loads(text[:-1] + ', "schema": "sipi.method-transmission-line/1"}')
    data = doc.to_dict()
    data['panel']['panels_per_edge'] = 257
    with pytest.raises(ValueError):
        Method.from_dict(data)


def test_equivalent_documents_and_surface_conversion():
    vol = Method(line(), current_method='volume-p1').equivalent_document()
    assert isinstance(vol, TransmissionLineDocument) and vol.dumps() == line().dumps()
    panel = Method(line(), current_method='panel', panel=PANEL).equivalent_document().to_dict()
    assert panel['schema'] == 'sipi.panel-transmission-line/1' and panel['panel'] == PANEL
    nested = panel['line']
    metal = dict(conductivity=58e6, relative_permeability=1., roughness=dict(kind='hammerstad', rms_m=.5e-6))
    assert nested['schema'] == 'sipi.transmission-line/3'
    assert nested['conductor'] == dict(kind='surface-boundaries', ground_thickness=35e-6,
                                       conductors={'signal': metal}, reference=metal)
    original = line().to_dict()
    assert {k: v for k, v in nested.items() if k not in ('schema', 'conductor')} == \
        {k: v for k, v in original.items() if k not in ('schema', 'conductor')}
    first = dict(ROUGH); first.pop('roughness'); first['roughness_rms'] = .5e-6
    converted = Method(line(conductor=first, schema='sipi.transmission-line/1'), current_method='panel',
                       panel=PANEL).equivalent_document().to_dict()['line']['conductor']
    assert converted['reference'] == metal
    boundaries = line(conductor=dict(kind='surface-boundaries', ground_thickness=35e-6,
                                     conductors={'signal': metal}, reference=metal), schema='sipi.transmission-line/3')
    kept = Method(boundaries, current_method='panel', panel=PANEL).equivalent_document()
    assert kept.to_dict()['line'] == boundaries.to_dict()
    two = Method(line('stripline'), current_method='panel', panel=PANEL).equivalent_document().to_dict()
    assert two['schema'] == 'sipi.two-ground-panel-transmission-line/1'
    assert two['conductors'] == {'signal': metal} and two['reference'] == dict(
        kind='surfaces', bottom=metal, top=metal, sides=None, conductors={})


@pytest.mark.parametrize('kind,conductor,match', [
    ('unbacked', ROUGH, 'bottom ground with open top and sides'),
    ('flat', dict(kind='perfect'), 'positive conductor thickness'),
    ('stripline', dict(kind='perfect'), 'surface or surface-boundaries'),
], ids=['open-bottom', 'zero-thickness', 'two-ground-perfect'])
def test_panel_refusals_have_no_fallback(kind, conductor, match):
    source = line(kind, conductor=conductor)
    with pytest.raises(ValueError, match=match):
        Method(source, current_method='panel', panel=PANEL)
    assert Method(source, current_method='volume-p1').equivalent_document().dumps() == source.dumps()


def test_shared_kernel_wall_refusal_happens_in_analyze_without_fallback(monkeypatch):
    doc = Method(TransmissionLineDocument(CrossSectionDocument(grounded_coplanar(width=.3e-3, gap=.2e-3,
        ground_width=1e-3, substrate_height=.2e-3, eps_r=4, thickness=35e-6), mesh=MESH), [1e9],
        materials={}, conductor=ROUGH, length=.02, schema='sipi.transmission-line/2'),
        current_method='panel', panel=PANEL)
    import sipi.line_model as volume
    monkeypatch.setattr(volume, '_surface_from_mesh', lambda *a, **k: pytest.fail('volume fallback'))
    with pytest.raises(ValueError, match='one cluster extent away'):
        doc.analyze()


@pytest.mark.parametrize('kind', ['microstrip', 'stripline'])
def test_results_are_the_existing_documents_bit_for_bit(kind):
    source = line(kind, frequency=(2e9,))
    vol, pan = Method(source, current_method='volume-p1'), Method(source, current_method='panel', panel=PANEL)
    a, b = vol.analyze(), source.analyze()
    same(a, b)
    assert a.input_json == vol.dumps() and b.input_json == source.dumps()
    eq = pan.equivalent_document()
    c = pan.analyze()
    d = type(eq).from_dict(eq.to_dict()).analyze()
    same(c, d)
    assert c.input_json == pan.dumps()
    assert isinstance(eq, PanelTransmissionLineDocument if kind == 'microstrip' else TwoGroundPanelTransmissionLineDocument)
    np.testing.assert_array_equal(c.C, d.C)
    assert c.R[0, 0, 0] > a.R[0, 0, 0]


def test_execution_records_the_method_and_equivalent_result():
    for doc in (Method(line(frequency=(2e9,)), current_method='volume-p1'),
                Method(line(frequency=(2e9,)), current_method='panel', panel=PANEL)):
        out = execute_saved(doc.dumps(), diagnostics=('characteristic',))
        ref = execute_saved(doc.equivalent_document().dumps(), diagnostics=('characteristic',))
        record = out['result'].pop('current_method')
        assert record == dict(method=doc.current_method, equivalent_schema=ref['input']['schema'])
        assert out['status'] == 'complete' and out['result'] == ref['result'] and out['input'] == doc.to_dict()
        json.dumps(out, allow_nan=False)
