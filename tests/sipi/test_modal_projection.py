# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent rational projections of real symmetric-pair line matrices."""
from decimal import Decimal, localcontext
from fractions import Fraction

import numpy as np
import pytest

from sipi.quasistatic import LineParameters


def _reference(C, C0, L):
    result = {}
    with localcontext() as context:
        context.prec = 200
        for mode, sign in [('even', 1), ('odd', -1)]:
            components = []
            for matrix in (C, C0, L):
                # Exact input floats and rational arithmetic, independent of
                # the engine's summation and binary floating-point quotient.
                exact = (Fraction(float(matrix[0, 0]))
                         + Fraction(float(matrix[1, 1]))) / 2
                exact += sign * Fraction(float(matrix[0, 1]))
                components.append(Decimal(exact.numerator) / Decimal(exact.denominator))
            capacitance, vacuum, inductance = components
            result['z_' + mode] = float((inductance / capacitance).sqrt())
            result['eps_eff_' + mode] = float(capacitance / vacuum)
    result['z_diff'] = 2 * result['z_odd']
    result['z_common'] = result['z_even'] / 2
    return result


def _check(C, C0, L):
    matrices = [C.copy(), C0.copy(), L.copy()]
    line = LineParameters(('p', 'n'), C, C0, L, np.zeros((2, 2)))
    actual = line.even_odd()
    for key, expected in _reference(C, C0, L).items():
        assert actual[key] == pytest.approx(expected, rel=2e-15, abs=0), key
    swapped = LineParameters(('n', 'p'), C[::-1, ::-1], C0[::-1, ::-1],
                             L[::-1, ::-1], np.zeros((2, 2)))
    assert swapped.even_odd() == actual
    for original, current in zip(matrices, (line.C, line.C0, line.L)):
        np.testing.assert_array_equal(current, original)


@pytest.mark.parametrize('scale', [1e-6, 1., 1e6])
@pytest.mark.parametrize('coupling', [.001, .2, .8])
@pytest.mark.parametrize('mismatch', [0., 1e-8])
def test_modal_projection_against_rational_reference(scale, coupling, mismatch):
    C = np.array([[4*(1+mismatch), -coupling],
                  [-coupling, 4*(1-mismatch)]]) * 1e-11 * scale
    C0 = C / 4
    L = np.array([[3*(1+mismatch), coupling],
                  [coupling, 3*(1-mismatch)]]) * 1e-7 / scale
    _check(C, C0, L)


@pytest.mark.parametrize('scale', [1e-6, 1., 1e6])
def test_nearly_cancelled_even_mode_keeps_diagonal_roundoff(scale):
    # Positive-definite, nearly equal self terms. The diagonal mean rounds
    # before cancellation in a sequential sum, losing a significant fraction
    # of the small even projection. The rational reference retains that bit.
    C = np.array([[1., -(1.-2**-26)],
                  [-(1.-2**-26), np.nextafter(1., 2.)]]) * 1e-11 * scale
    C0 = C / 4
    L = np.array([[1., .2], [.2, 1.]]) * 1e-7 / scale
    assert np.linalg.eigvalsh(C)[0] > 0
    _check(C, C0, L)
