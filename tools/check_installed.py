# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Run the imported regression and integration suites outside the source checkout."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
report = root / '.validation'
report.mkdir(exist_ok=True)
env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1',
           OPENPHYSICS_REQUIRE_CROSSCHECK='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
env.pop('PYTHONPATH', None)
with tempfile.TemporaryDirectory(prefix='sipi-installed-') as tmp:
    outside = Path(tmp)
    for name in ('tests', 'integration'):
        shutil.copytree(root / name, outside / name)
    shutil.copy2(root / 'pyproject.toml', outside / 'pyproject.toml')
    subprocess.run([sys.executable, '-m', 'pytest', '-q', 'tests', 'integration',
                    '--junitxml=' + str(report / 'installed.xml')],
                   cwd=outside, env=env, check=True)
