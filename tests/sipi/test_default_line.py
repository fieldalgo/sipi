# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""transmission-line/8 defaults to panel currents by running existing documents unchanged."""
import json
import numpy as np
import pytest
from sipi import CrossSectionDocument
from sipi.crosssection import CrossSection
from sipi.templates import microstrip, stripline, unbacked_coplanar
from sipi.line_model import TransmissionLineDocument
from sipi.method_line import MethodTransmissionLineDocument as Method
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.default_line import DefaultPanelTransmissionLineDocument as Line8, DEFAULT_PANEL_CONTROLS
from sipi.execution import execute_saved, normalize_saved, saved_schemas

MESH = dict(edge_size=2.5e-6, far_size=.1e-3, grade=.05)
GROUND = dict(panels_per_edge=64, ground_modes=512, interpolation_degree=14)
OPEN = dict(panels_per_edge=64, interpolation_degree=12)
METAL = dict(conductivity=58e6, relative_permeability=1., roughness=dict(kind='hammerstad', rms_m=.5e-6))
ROUGH = dict(kind='surface', conductivity=58e6, ground_thickness=35e-6, relative_permeability=1.,
             roughness=METAL['roughness'])


def section(kind='microstrip'):
    make = dict(microstrip=lambda: microstrip(width=.3e-3, substrate_height=.2e-3, eps_r=4, thickness=35e-6),
                stripline=lambda: stripline(width=.2e-3, plane_spacing=.5e-3, eps_r=4, thickness=17.5e-6),
                unbacked=lambda: unbacked_coplanar(width=.3e-3, gap=.2e-3, ground_width=1e-3,
                                                   substrate_height=.2e-3, eps_r=4, thickness=35e-6),
                flat=lambda: microstrip(width=.3e-3, substrate_height=.2e-3, eps_r=4),
                sides=_sides)[kind]
    return CrossSectionDocument(make(), mesh=MESH)


def _sides():
    s = microstrip(width=.3e-3, substrate_height=.2e-3, eps_r=4, thickness=35e-6)
    return CrossSection(s.layers, s.traces, s.width, bottom='ground', top='open', sides='ground')


def fields(kind='microstrip', conductor=ROUGH, frequency=(2e9,)):
    return dict(cross_section=section(kind).to_dict(), frequency_hz=list(frequency), materials={},
                conductor=conductor, length_m=.02, reference_ohms=50.)


def line7(kind='microstrip', **changes):
    return TransmissionLineDocument.from_dict(dict(fields(kind, **changes), schema='sipi.transmission-line/7'))


def line8(kind='microstrip', **changes):
    extra = {k: changes.pop(k) for k in ('current_method', 'panel') if k in changes}
    return Line8.from_dict(dict(fields(kind, **changes), schema='sipi.transmission-line/8', **extra))


def same(a, b):
    for key in 'RLGC':
        np.testing.assert_array_equal(getattr(a, key), getattr(b, key))
    np.testing.assert_array_equal(a.network.s, b.network.s)


def test_defaults_are_written_into_the_saved_document():
    assert DEFAULT_PANEL_CONTROLS[('ground', 'open', 'open')] == GROUND
    assert DEFAULT_PANEL_CONTROLS[('ground', 'ground', 'open')] == GROUND
    assert DEFAULT_PANEL_CONTROLS[('open', 'open', 'open')] == OPEN
    for kind, panel in (('microstrip', GROUND), ('stripline', GROUND), ('unbacked', OPEN)):
        doc = line8(kind)
        data = doc.to_dict()
        assert data['current_method'] == 'panel' and data['panel'] == panel
        assert {k: v for k, v in data.items() if k not in ('schema', 'current_method', 'panel')} == \
            {k: v for k, v in line7(kind).to_dict().items() if k != 'schema'}
        text = doc.dumps()
        assert Line8.loads(text).dumps() == text and normalize_saved(text) == text
        explicit = line8(kind, current_method='panel', panel=panel)
        assert explicit.dumps() == text
    boundaries = dict(kind='surface-boundaries', ground_thickness=35e-6, conductors={'signal': METAL}, reference=METAL)
    assert line8(conductor=boundaries).current_method == 'panel'
    p1 = line8(current_method='volume-p1').to_dict()
    assert p1['current_method'] == 'volume-p1' and 'panel' not in p1
    assert 'sipi.transmission-line/8' in saved_schemas()
    built = Line8(section(), [2e9], materials={}, conductor=ROUGH, length=.02)
    assert built.dumps() == line8().dumps()


def test_strict_keys_and_values():
    with pytest.raises(ValueError, match="'panel' or 'volume-p1'"):
        line8(current_method='auto')
    with pytest.raises(ValueError, match="require current_method 'panel'"):
        line8(current_method='volume-p1', panel=GROUND)
    with pytest.raises(ValueError, match='panel controls'):
        line8(panel=dict(GROUND, extra=1))
    with pytest.raises(ValueError, match='panel controls'):
        line8('unbacked', panel=GROUND)  # an open box has no ground modes
    with pytest.raises(ValueError):
        line8(panel=dict(GROUND, panels_per_edge=257))
    with pytest.raises(ValueError, match='transmission line'):
        Line8.from_dict(dict(fields(), schema='sipi.transmission-line/8', extra=1))
    with pytest.raises(ValueError, match='duplicate'):
        text = line8().dumps()
        Line8.loads(text[:-1] + ', "schema": "sipi.transmission-line/8"}')
    with pytest.raises(ValueError, match='unsupported'):
        Line8.from_dict(dict(fields(), schema='sipi.transmission-line/7'))


@pytest.mark.parametrize('kind,changes,match', [
    ('microstrip', dict(conductor=dict(kind='surface-faces', ground_thickness=35e-6, reference=METAL,
                                       conductors={'signal': {f: METAL for f in ('bottom', 'top', 'left', 'right')}})),
     'surface-faces \\(per-face metal\\) has no panel default'),
    ('microstrip', dict(conductor=dict(kind='surface-faces', ground_thickness=35e-6, reference=METAL,
                                       conductors={'signal': {f: METAL for f in ('bottom', 'top', 'left', 'right')}}),
                        current_method='panel'), 'does not support surface-faces'),
    ('microstrip', dict(conductor=dict(kind='perfect')), 'perfect conductors have no default current_method'),
    ('sides', {}, 'two grounds with open sides, or open bottom'),
    ('flat', dict(conductor=dict(kind='perfect'), current_method='panel'), 'positive conductor thickness'),
    ('stripline', dict(conductor=dict(kind='perfect'), current_method='panel'), 'surface or surface-boundaries'),
], ids=['faces-default', 'faces-panel', 'perfect-default', 'grounded-sides', 'zero-thickness', 'two-ground-perfect'])
def test_refusals_name_the_reason_and_the_explicit_p1_choice(kind, changes, match):
    with pytest.raises(ValueError, match=match) as error:
        line8(kind, **dict(changes))
    if 'perfect' not in match:
        assert "current_method 'volume-p1'" in str(error.value)
    p1 = line8(kind, **dict(changes, current_method='volume-p1'))
    assert p1.equivalent_document().dumps() == line7(kind, **{k: v for k, v in changes.items()
                                                              if k != 'current_method'}).dumps()


def test_existing_documents_do_not_accept_line8():
    data = line8().to_dict()
    with pytest.raises(ValueError, match='transmission line'):
        TransmissionLineDocument.from_dict(data)
    with pytest.raises(ValueError, match='unsupported transmission-line schema'):
        TransmissionLineDocument.from_dict({k: v for k, v in data.items() if k not in ('current_method', 'panel')})
    with pytest.raises(ValueError):
        Method.from_dict(dict(schema='sipi.method-transmission-line/1', line=data, current_method='volume-p1'))
    with pytest.raises(ValueError):
        PanelTransmissionLineDocument.from_dict(dict(schema='sipi.panel-transmission-line/2', line=data,
                                                     panel=GROUND))


@pytest.mark.parametrize('kind', ['microstrip', 'stripline', 'unbacked'])
def test_panel_default_is_the_method_line_bit_for_bit(kind):
    doc = line8(kind)
    method = Method(line7(kind), current_method='panel', panel=GROUND if kind != 'unbacked' else OPEN)
    assert doc.method_document().dumps() == method.dumps()
    assert doc.equivalent_document().dumps() == method.equivalent_document().dumps()
    a, b = doc.analyze(), method.analyze()
    same(a, b)
    assert a.input_json == doc.dumps()
    assert a.R[0, 0, 0] > 0


def test_volume_p1_is_line7_bit_for_bit():
    doc, source = line8(current_method='volume-p1'), line7()
    assert doc.equivalent_document().dumps() == source.dumps()
    a, b = doc.analyze(), source.analyze()
    same(a, b)
    assert a.input_json == doc.dumps() and b.input_json == source.dumps()


def test_execution_records_the_method_and_equivalent_result():
    for doc in (line8(current_method='volume-p1'), line8()):
        out = execute_saved(doc.dumps(), diagnostics=('characteristic',))
        ref = execute_saved(doc.method_document().dumps(), diagnostics=('characteristic',))
        assert out['status'] == 'complete' and out['input'] == doc.to_dict()
        assert out['result'] == ref['result']
        assert out['result']['current_method'] == dict(method=doc.current_method,
            equivalent_schema=json.loads(doc.equivalent_document().dumps())['schema'])
        json.dumps(out, allow_nan=False)
