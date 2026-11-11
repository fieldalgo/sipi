# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Aperture meshes must not depend on unspecified equal-key quicksort order."""
import types

import numpy as np
import pytest
import meshine.refine as refinement

from sipi import EllipticalAperture, RoundConductor, capacitance_matrix


class _AlternateEqualKeys:
    """A valid alternative NumPy quicksort result, only for equal keys."""
    def __getattr__(self, name):
        return getattr(np, name)

    def argsort(self, values, *args, **kwargs):
        order = np.argsort(values, *args, **kwargs)
        if kwargs.get('kind') == 'quicksort':
            sorted_values = np.asarray(values)[order]
            edges = np.r_[0, np.flatnonzero(sorted_values[1:] != sorted_values[:-1]) + 1,
                          len(order)]
            for start, end in zip(edges[:-1], edges[1:]):
                order[start:end] = order[start:end][::-1]
        return order


@pytest.mark.parametrize('diameter', [.0002, .00025939941406250005])
def test_aperture_mesh_and_energy_survive_alternate_equal_key_order(monkeypatch, diameter):
    section = EllipticalAperture(.0008, .0008, (RoundConductor('s', diameter),), eps_r=3.96)
    original = section.mesh(size=.0001, angular_divisions=16)
    # Simulate an allowed library-version difference in candidate sorting.
    # Keep every other NumPy operation and the mesher's geometry/algorithm.
    separate = refinement._separate
    alternate = types.FunctionType(
        separate.__code__, dict(separate.__globals__, np=_AlternateEqualKeys()),
        separate.__name__, separate.__defaults__, separate.__closure__)
    alternate.__kwdefaults__ = separate.__kwdefaults__
    monkeypatch.setattr(refinement, '_separate', alternate)
    replay = section.mesh(size=.0001, angular_divisions=16)
    np.testing.assert_array_equal(replay.mesh.nodes, original.mesh.nodes)
    np.testing.assert_array_equal(replay.mesh.triangles, original.mesh.triangles)
    np.testing.assert_array_equal(replay.ground, original.ground)
    for name in original.signals:
        np.testing.assert_array_equal(replay.signals[name], original.signals[name])
    expected = capacitance_matrix(original.mesh, section.eps_r, original.signals, original.ground)
    actual = capacitance_matrix(replay.mesh, section.eps_r, replay.signals, replay.ground)
    np.testing.assert_array_equal(actual, expected)
