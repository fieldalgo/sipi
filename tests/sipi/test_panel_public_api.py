# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Every panel route calls galerkin's public SI panel module, with the internal results bit for bit.

The public module ``galerkin.panel_electrostatics`` takes ``box_size`` (width, height)
in m and names conductor selections ``ground_indices`` and ``signal_indices``. SIPI
sections are already in m, so each route passes the same numbers. Here each route's
actual call is repeated on the internal solver with the internal keyword names and
every result field must be equal, not close.
"""
import dataclasses
import importlib
from pathlib import Path

import numpy as np
import pytest

import galerkin.panel_electrostatics as public
import sipi

# route module, solver getter, public function, internal module and function
ROUTES = [
    ('panel_conductor', '_panel_solver', 'solve_grounded_rectangle', 'laplace_boundary'),
    ('open_panel_conductor', '_open_solver', 'solve_open_rectangle', 'laplace_open_box'),
    ('two_ground_conductor', '_solver', 'solve_two_ground_rectangle', 'laplace_two_ground'),
    ('two_ground_face_conductor', '_solver', 'solve_two_ground_rectangle_edges', 'laplace_two_ground'),
    ('two_ground_corner_conductor', '_solver', 'solve_two_ground_corner_rectangle_edges', 'laplace_two_ground'),
    ('two_ground_linear_corner_conductor', '_solver', 'solve_two_ground_linear_corner_rectangle_edges',
     'laplace_corner_linear_field'),
    ('two_ground_harmonic_three_active_corner_conductor', '_solver',
     'solve_two_ground_harmonic_corner_three_active_edges', 'laplace_corner_harmonic_field'),
    ('two_ground_harmonic_guard_corner_conductor', '_solver', 'solve_two_ground_harmonic_corner_guard_edges',
     'laplace_corner_harmonic_guard_field'),
]
_INTERNAL_NAMES = {'ground_indices': 'grounds', 'signal_indices': 'signals', 'signal_index': 'signal'}


@pytest.mark.parametrize('route,getter,name,internal', ROUTES, ids=[r[0] for r in ROUTES])
def test_each_route_resolves_to_the_public_module(route, getter, name, internal):
    assert getattr(importlib.import_module('sipi.'+route), getter)() is getattr(public, name)


def test_no_sipi_module_names_an_internal_panel_module():
    for path in Path(sipi.__file__).parent.rglob('*.py'):
        assert 'galerkin.laplace_' not in path.read_text(encoding='utf-8'), path.name


def _internal_call(internal, name, args, kwargs):
    kwargs = dict(kwargs)
    width, height = kwargs.pop('box_size')
    kwargs = {_INTERNAL_NAMES.get(key, key): value for key, value in kwargs.items()}
    return getattr(importlib.import_module('galerkin.'+internal), name)(*args, width=width, height=height, **kwargs)


def _assert_identical(a, b, where='result'):
    assert type(a) is type(b), where
    if dataclasses.is_dataclass(a):
        for field in dataclasses.fields(a):
            _assert_identical(getattr(a, field.name), getattr(b, field.name), where+'.'+field.name)
    elif isinstance(a, np.ndarray):
        assert a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes(), where
    elif isinstance(a, (tuple, list)):
        assert len(a) == len(b), where
        for i, (x, y) in enumerate(zip(a, b)):
            _assert_identical(x, y, f'{where}[{i}]')
    elif isinstance(a, float):
        assert np.float64(a).tobytes() == np.float64(b).tobytes(), where
    else:
        assert a == b, where


def _sections():
    from test_panel_conductor import circles
    from test_open_panel_line import SECTIONS, PANEL
    from test_two_ground_conductor import ROWS, section as two_ground
    from test_two_ground_face_conductor import section as face
    from test_two_ground_corner_conductor import section as corner
    from test_two_ground_linear_corner_conductor import section as linear
    from sipi.panel_conductor import panel_surface_current_factors
    from sipi.open_panel_conductor import open_panel_surface_current_factors
    from sipi.two_ground_conductor import two_ground_current_factors
    from sipi.two_ground_face_conductor import two_ground_face_current_factors
    from sipi.two_ground_corner_conductor import two_ground_corner_face_current_factors
    from sipi.two_ground_linear_corner_conductor import two_ground_linear_corner_face_current_factors
    return {
        'panel_conductor': lambda: panel_surface_current_factors(circles(), panels_per_edge=2, interpolation_degree=12),
        'open_panel_conductor': lambda: open_panel_surface_current_factors(SECTIONS['coupled'](), **PANEL),
        'two_ground_conductor': lambda: two_ground_current_factors(two_ground(ROWS[0]), panels_per_edge=16),
        'two_ground_face_conductor': lambda: two_ground_face_current_factors(face(), panels_per_edge=16),
        'two_ground_corner_conductor': lambda: two_ground_corner_face_current_factors(corner(0)),
        'two_ground_linear_corner_conductor': lambda: two_ground_linear_corner_face_current_factors(linear(0)),
    }


# The two harmonic routes take minutes per solve; their routing is checked above and
# their RLGC is held to the registered values by their own tests.
SOLVED = [r for r in ROUTES if 'harmonic' not in r[0]]


@pytest.mark.parametrize('route,getter,name,internal', SOLVED, ids=[r[0] for r in SOLVED])
def test_route_result_equals_the_internal_solver_bit_for_bit(monkeypatch, route, getter, name, internal):
    module = importlib.import_module('sipi.'+route)
    solver, calls = getattr(module, getter)(), []

    def recorded(*args, **kwargs):
        result = solver(*args, **kwargs)
        calls.append((args, kwargs, result))
        return result
    monkeypatch.setattr(module, getter, lambda: recorded)
    _sections()[route]()
    assert len(calls) == 1
    args, kwargs, result = calls[0]
    assert len(kwargs['box_size']) == 2 and 'width' not in kwargs and 'height' not in kwargs
    _assert_identical(result, _internal_call(internal, name, args, kwargs))
