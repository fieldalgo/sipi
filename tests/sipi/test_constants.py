# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Physical-reference revision remains independent of installed SciPy tables."""
import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize('epsilon,mu', [(8.8541878128e-12, 1.25663706212e-6), (1e-11, 2e-6)])
def test_field_and_surface_laws_do_not_inherit_runtime_constant_changes(epsilon, mu):
    # A fresh interpreter ensures all four extraction modules see the modified
    # SciPy table before import. The second case is deliberately conspicuous.
    script = '''
import sys, numpy as np, scipy.constants
scipy.constants.epsilon_0 = float(sys.argv[1])
scipy.constants.mu_0 = float(sys.argv[2])
from galerkin import Mesh
from sipi.constants import CODATA_REVISION, epsilon_0, mu_0, SPEED_OF_LIGHT
from sipi import line_parameters
from sipi.conductor import surface_impedance
from sipi import conductor, conductor_diffusion, dielectric, quasistatic
assert CODATA_REVISION == 2022
assert epsilon_0 == 8.8541878188e-12 and mu_0 == 1.25663706127e-6
assert SPEED_OF_LIGHT == 299792458.
for module in (conductor, conductor_diffusion, dielectric, quasistatic):
    assert module.epsilon_0 == epsilon_0 and module.mu_0 == mu_0
# Linear parallel-plate potential is represented exactly by these two P1 cells.
mesh = Mesh(np.array([[0.,0.],[2.,0.],[2.,1.],[0.,1.]]), np.array([[0,1,2],[0,2,3]]), {})
line = line_parameters(mesh, 4., {'right':[1,2]}, [0,3])
np.testing.assert_allclose(line.C, [[4*8.8541878188e-12/2]], rtol=1e-14, atol=0)
np.testing.assert_allclose(line.L, [[2*1.25663706127e-6]], rtol=1e-14, atol=0)
f = np.array([1e6,1e9])
z = surface_impedance(f, conductivity=58e6)
np.testing.assert_allclose(z, (1+1j)*np.sqrt(np.pi*f*1.25663706127e-6/58e6), rtol=1e-14, atol=0)
# Published measured values are rounded independently; do not replace one.
assert 0 < abs(epsilon_0*mu_0*SPEED_OF_LIGHT**2-1) < 2e-12
'''
    env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    subprocess.run([sys.executable, '-c', script, str(epsilon), str(mu)], env=env, check=True)
