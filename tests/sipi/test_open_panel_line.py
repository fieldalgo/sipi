# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Open-box panel currents for sections with no ground plane (unbacked coplanar)."""
import json
import numpy as np
import pytest
from scipy.constants import epsilon_0
from quadratic_conductor import quadratic_surface_factors
from sipi import CrossSectionDocument
from sipi.templates import (unbacked_coplanar, coupled_unbacked_coplanar,
                            asymmetric_coupled_unbacked_coplanar, microstrip)
from sipi.line_model import TransmissionLineDocument
from sipi.conductor import surface_current_factors
from sipi.open_panel_conductor import open_panel_surface_current_factors
from sipi.open_panel_line import OpenPanelTransmissionLineDocument as Open
from sipi.method_line import MethodTransmissionLineDocument as Method
from sipi.execution import execute_saved, normalize_saved, saved_schemas

MESH = dict(edge_size=2.5e-6, far_size=.1e-3, grade=.05)
PANEL = dict(panels_per_edge=64, interpolation_degree=12)
METAL = dict(conductivity=58e6, relative_permeability=1., roughness=dict(kind='hammerstad', rms_m=.5e-6))
ROUGH = dict(kind='surface', conductivity=58e6, ground_thickness=35e-6, relative_permeability=1.,
             roughness=dict(kind='hammerstad', rms_m=.5e-6))
COMMON = dict(gap=.2e-3, ground_width=1e-3, substrate_height=.2e-3, eps_r=4.)

SECTIONS = {
    'single': lambda: unbacked_coplanar(width=.3e-3, thickness=35e-6, **COMMON),
    'coupled': lambda: coupled_unbacked_coplanar(width=.3e-3, ground_gap=.2e-3, thickness=35e-6, **COMMON),
    'asymmetric': lambda: asymmetric_coupled_unbacked_coplanar(
        left_width=.3e-3, right_width=.25e-3, ground_gap=.2e-3, left_thickness=35e-6,
        right_thickness=35e-6, ground_thickness=35e-6, **COMMON),
}


def boundaries(names=('signal',)):
    return dict(kind='surface-boundaries', ground_thickness=35e-6, conductors={n: METAL for n in names},
                reference=METAL)


def line(conductor=None, frequency=(1e9, 5e9), make=SECTIONS['single']):
    return TransmissionLineDocument(CrossSectionDocument(make(), mesh=MESH), list(frequency), materials={},
                                    conductor=conductor or boundaries(), length=.02, schema='sipi.transmission-line/3')


@pytest.mark.parametrize('name', list(SECTIONS))
def test_open_box_capacitance_against_independent_quadratic_volume(name):
    section = SECTIONS[name]()
    factors = open_panel_surface_current_factors(section, **PANEL)
    assert factors.diagnostics['smooth_interpolation_boxes'] > 1
    assert factors.diagnostics['matrix_refinement_error'] <= 1e-10 and factors.current_error <= 1e-10
    meshed = section.mesh()
    p2 = quadratic_surface_factors(meshed.mesh, meshed.signals, meshed.ground)
    # Same box, default mesh; the research study measured 1.1e-4 and 4.3e-5 after refinement.
    assert np.max(abs(p2['C0'] - factors.C0)) / np.max(abs(factors.C0)) < 5e-4
    assert tuple(meshed.signals) == factors.names and factors.ground_trace_names == tuple(
        t.name for t in section.traces if t.ground)


def test_reference_is_every_grounded_trace_and_matches_the_shared_solve():
    from galerkin.laplace_open_box import solve_open_rectangle
    section = SECTIONS['single']()
    factors = open_panel_surface_current_factors(section, **PANEL)
    polygons = [t.corners() + np.array([section.width / 2, 0.]) for t in section.traces]
    shared = solve_open_rectangle(polygons, width=section.width, height=section.height, grounds=[1, 2], **PANEL)
    np.testing.assert_array_equal(factors.C0, epsilon_0 * shared.capacitance_per_permittivity)
    np.testing.assert_array_equal(factors.parts[-1], shared.current_gram[1] + shared.current_gram[2])
    np.testing.assert_allclose(factors.current_integrals, [[1.], [-1.]], atol=1e-10)
    # The P1 volume currents of the same section are lower, as for the grounded panel route.
    volume = surface_current_factors(*(lambda m: (m.mesh, m.signals, m.ground))(section.mesh()))
    assert volume.parts[0, 0, 0] < factors.parts[0, 0, 0]


def test_open_box_factors_refuse_other_boundaries():
    with pytest.raises(ValueError, match='open bottom, top and sides'):
        open_panel_surface_current_factors(microstrip(width=.3e-3, substrate_height=.2e-3, eps_r=4, thickness=35e-6))
    with pytest.raises(TypeError):
        open_panel_surface_current_factors({})


def test_document_is_strict_and_saved():
    doc = Open(line(), **PANEL)
    text = doc.dumps()
    assert Open.loads(text).dumps() == text and normalize_saved(text) == text
    assert 'sipi.open-panel-transmission-line/1' in saved_schemas()
    assert doc.to_dict()['panel'] == PANEL
    data = doc.to_dict()
    for change, match in [(lambda d: d['panel'].update(ground_modes=512), 'panel controls'),
                          (lambda d: d['panel'].update(interpolation_degree=13), 'interpolation_degree'),
                          (lambda d: d['panel'].update(panels_per_edge=257), ''),
                          (lambda d: d.update(schema='sipi.open-panel-transmission-line/2'), 'unsupported'),
                          (lambda d: d['line'].update(schema='sipi.transmission-line/8'), 'transmission-line/1 through /7')]:
        bad = json.loads(json.dumps(data))
        change(bad)
        with pytest.raises(ValueError, match=match or None):
            Open.from_dict(bad)
    backed = TransmissionLineDocument(CrossSectionDocument(microstrip(width=.3e-3, substrate_height=.2e-3,
        eps_r=4, thickness=35e-6), mesh=MESH), [1e9], materials={}, conductor=boundaries(),
        length=.02, schema='sipi.transmission-line/3')
    with pytest.raises(ValueError, match='open bottom, top and sides'):
        Open(backed, **PANEL)
    with pytest.raises(ValueError, match='perfect or surface-boundaries'):
        Open(line(conductor=ROUGH), **PANEL)


def test_line_analysis_and_execution_record():
    doc = Open(line(frequency=(2e9,)), **PANEL)
    result = doc.analyze()
    assert result.R[0, 0, 0] > 0 and result.input_json == doc.dumps()
    assert result.conductor.boundary_labels == ('signal:signal', 'reference')
    out = execute_saved(doc.dumps(), diagnostics=('characteristic',))
    assert out['status'] == 'complete'
    solver = out['result']['current_solver']
    assert solver['kind'] == 'open-rectangle-panels' and solver['settings'] == PANEL
    assert solver['ground_trace_names'] == ['ground_left', 'ground_right']
    assert solver['diagnostics']['smooth_interpolation_boxes'] > 1
    assert out['result']['conductor_boundaries']['labels'] == ['signal:signal', 'reference']
    json.dumps(out, allow_nan=False)
    with pytest.raises(ValueError, match='frequency count exceeds max_evaluations'):
        execute_saved(Open(line(frequency=(1e9, 2e9, 3e9)), **PANEL).dumps(), max_evaluations=2)


def test_method_line_runs_the_open_panel_document_unchanged():
    source = TransmissionLineDocument(CrossSectionDocument(SECTIONS['single'](), mesh=MESH), [2e9], materials={},
                                      conductor=ROUGH, length=.02, schema='sipi.transmission-line/2')
    doc = Method(source, current_method='panel', panel=PANEL)
    assert doc.to_dict()['panel'] == PANEL
    eq = doc.equivalent_document()
    assert isinstance(eq, Open)
    nested = eq.to_dict()['line']
    assert nested['schema'] == 'sipi.transmission-line/3'
    assert nested['conductor'] == dict(kind='surface-boundaries', ground_thickness=35e-6,
                                       conductors={'signal': METAL}, reference=METAL)
    a, b = doc.analyze(), Open.from_dict(eq.to_dict()).analyze()
    for key in 'RLGC':
        np.testing.assert_array_equal(getattr(a, key), getattr(b, key))
    np.testing.assert_array_equal(a.network.s, b.network.s)
    assert a.input_json == doc.dumps()
    volume = Method(source, current_method='volume-p1').analyze()
    assert a.R[0, 0, 0] > volume.R[0, 0, 0]
    out = execute_saved(doc.dumps())
    assert out['result']['current_method'] == dict(method='panel',
                                                   equivalent_schema='sipi.open-panel-transmission-line/1')
