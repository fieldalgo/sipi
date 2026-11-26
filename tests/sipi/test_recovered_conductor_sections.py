# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Recovered currents on five PCB sections against recorded boundary-panel values.

Criteria fixed before the study, relative to the panel [0,0] factor:
(i) default mesh and level 0 within 2%; (ii) level 1 within 1%; (iii) coupled
observed order >= 0.8, or levels 1-2 within 0.5%; (iv) coupled off-diagonal
within 1% of the largest diagonal; (v) symmetric positive semidefinite total;
(vi) recovery cost beyond the shared P1 solve at most that solve's time.
Level L meshes use edge 5 um, far .2 mm and grade .1, each times 2**-L.
The panel values are the recorded panel-path results (256 panels per edge,
128 for the grounded coplanar section); recorded recovery values reproduce
an internal study on the same default meshes.
"""
import time

import numpy as np
import pytest
from sipi import coupled_microstrip, grounded_coplanar, microstrip, stripline
from sipi.conductor import _surface_current_basis
from sipi.recovered_conductor import recovered_surface_current_factors

SECTIONS = {
    'coupled': lambda: coupled_microstrip(width=.5e-3, gap=.3e-3, substrate_height=1e-3,
                                          thickness=.05e-3, eps_r=4),
    'microstrip-narrow': lambda: microstrip(width=.3e-3, substrate_height=.2e-3, eps_r=4,
                                            thickness=35e-6),
    'microstrip-wide': lambda: microstrip(width=1e-3, substrate_height=.5e-3, eps_r=4,
                                          thickness=17.5e-6),
    'grounded-coplanar': lambda: grounded_coplanar(width=.3e-3, gap=.2e-3, ground_width=1e-3,
                                                   substrate_height=.2e-3, eps_r=4,
                                                   thickness=35e-6, air_height=3e-3,
                                                   box_width=9e-3),
    'stripline': lambda: stripline(width=.2e-3, plane_spacing=.5e-3, eps_r=4, thickness=17.5e-6),
}
PANEL = {'coupled': np.array([[1744.857, 10.415], [10.415, 1744.857]]),
         'microstrip-narrow': 2961.585, 'microstrip-wide': 1179.868,
         'grounded-coplanar': 3100.801, 'stripline': 4120.476}
# Default-mesh node count, support width, total factor (1/m) and C0 (F/m).
RECORDED = {
    'coupled': (9166, 0.00011999999999999998,
                [[1740.3720568448668, 10.801938062124037], [10.801938062124037, 1740.3954358749688]],
                [[2.6326298495402902e-11, -1.1213923540739919e-11],
                 [-1.1213923540739919e-11, 2.6326206465096014e-11]]),
    'microstrip-narrow': (4099, 8e-05, [[2954.6128253998736]], [[3.419754939942737e-11]]),
    'microstrip-wide': (11092, 0.0002, [[1176.3332200498457]], [[3.772522831913857e-11]]),
    'grounded-coplanar': (16129, 7.999999999999999e-05, [[3091.7047207186642]],
                          [[3.858773711327407e-11]]),
    'stripline': (4448, 9.65e-05, [[4106.47805165869]], [[3.225220070089997e-11]]),
}
NAMES = tuple(SECTIONS)


def _level(section, level):
    scale = 2.**-level
    return section.mesh(edge_size=5e-6*scale, far_size=.2e-3*scale, grade=.1*scale)


def _solve(meshed):
    return recovered_surface_current_factors(meshed.mesh, meshed.signals, meshed.ground)


def _error(name, total):
    return total[0, 0]/np.atleast_2d(PANEL[name])[0, 0]-1


@pytest.fixture(scope='module', params=NAMES)
def study(request):
    name, section = request.param, SECTIONS[request.param]()
    default = section.mesh()
    levels = [0, 1, 2] if name == 'coupled' else [0, 1]
    return name, default, _solve(default), {L: _solve(_level(section, L)).total for L in levels}


def test_default_mesh_reproduces_recorded_values(study):
    name, default, result, _ = study
    nodes, width, total, c0 = RECORDED[name]
    if default.mesh.num_nodes != nodes:
        pytest.skip(f'mesher produced {default.mesh.num_nodes} nodes, recorded mesh has {nodes}; '
                    'reproduction is defined on the recorded triangulation')
    assert result.diagnostics['support_width'] == pytest.approx(width, rel=1e-12, abs=0)
    np.testing.assert_allclose(result.total, total, rtol=1e-12, atol=0)
    np.testing.assert_allclose(result.C0, c0, rtol=1e-12, atol=0)


@pytest.mark.slow
def test_preregistered_panel_comparison(study, record_property):
    name, _, result, levels = study
    errors = {'default': _error(name, result.total)}
    errors.update({f'L{L}': _error(name, total) for L, total in levels.items()})
    for key, value in errors.items():
        record_property(f'{name}_{key}_relative_error', value)
    assert abs(errors['default']) <= .02 and abs(errors['L0']) <= .02, errors      # (i)
    assert abs(errors['L1']) <= .01, errors                                         # (ii)
    for total in [result.total, *levels.values()]:                                  # (v)
        np.testing.assert_array_equal(total, total.T)
        assert np.min(np.linalg.eigvalsh(total)) >= 0
    for part in result.parts:
        np.testing.assert_array_equal(part, part.T)
    if name == 'coupled':
        panel = PANEL[name]
        off = abs(result.total[0, 1]-panel[0, 1])/np.max(np.diag(panel))
        record_property('coupled_offdiagonal_error', off)
        assert off <= .01                                                           # (iv)
        t0, t1, t2 = (np.diag(levels[L]) for L in (0, 1, 2))
        order = np.log2(abs(t1-t0)/abs(t2-t1))
        record_property('coupled_observed_order', order.tolist())
        assert np.all(order >= .8) or np.all(abs(t1/t2-1) <= .005), order           # (iii)


@pytest.mark.parametrize('name', NAMES)
def test_recovery_cost_at_most_p1_solve(name, record_property):
    meshed = SECTIONS[name]().mesh()
    args = meshed.mesh, meshed.signals, meshed.ground
    solve, total = [], []
    for _ in range(5):
        t0 = time.perf_counter()
        _surface_current_basis(*args)
        t1 = time.perf_counter()
        recovered_surface_current_factors(*args)
        total.append(time.perf_counter()-t1)
        solve.append(t1-t0)
    ratio = (np.median(total)-np.median(solve))/np.median(solve)
    record_property(f'{name}_extra_cost_over_solve', ratio)
    assert ratio <= 1, ratio                                                        # (vi)
