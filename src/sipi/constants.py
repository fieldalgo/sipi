# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit CODATA 2022 SI values, independent of a runtime's SciPy tables.

Source: https://physics.nist.gov/cuu/Constants/Table/allascii.txt
The published rounded epsilon_0 and mu_0 values are retained separately;
neither is recomputed to force their rounded product with c**2 to equal one.
These measured constants have uncertainty; only the speed of light is exact.
"""

CODATA_REVISION = 2022
epsilon_0 = 8.8541878188e-12  # F/m; standard uncertainty 1.4e-21 F/m
mu_0 = 1.25663706127e-6      # H/m; standard uncertainty 2.0e-16 H/m
SPEED_OF_LIGHT = 299792458.0  # m/s, exact

__all__ = ['CODATA_REVISION', 'epsilon_0', 'mu_0', 'SPEED_OF_LIGHT']
