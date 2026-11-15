# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The shared validator can load without a SIPI package or numerical runtime."""
from pathlib import Path
import subprocess
import sys

import pytest

from sipi import _validation
from sipi import circuit_document, document, execution


def test_validator_loads_in_isolated_python_without_site_packages(tmp_path):
    # Copy only the module: importing sipi itself still loads its broad facade.
    target = tmp_path / 'validation.py'
    target.write_bytes(Path(_validation.__file__).read_bytes())
    script = '''
import builtins, runpy, sys
original_import = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'sipi', 'numpy', 'scipy', 'galerkin', 'meshine', 'shapely'}:
        raise AssertionError('Domain/runtime dependency: ' + name)
    return original_import(name, *args, **kwargs)
builtins.__import__ = guarded
v = runpy.run_path(sys.argv[1])
source = {'label':'material', 'values':(1, {'x':2.})}
copy = v['_json_copy'](source)
source['values'][1]['x'] = 3.
assert copy == {'label':'material', 'values':[1, {'x':2.}]}
v['_keys'](copy, ('label','values'), where='sample')
assert v['_number'](1, 'length') == 1.
assert v['_name']('material', 'label') == 'material'
assert v['_integer']('budget', 3, 1, 4) == 3
assert v['_unique_object']([('x', 1)]) == {'x':1}
assert v['_float']('1.25') == 1.25
try:
    v['_float']('1e999')
except ValueError as exc:
    assert str(exc) == 'nonfinite JSON number: 1e999'
else:
    raise AssertionError('overflow accepted')
'''
    result = subprocess.run([sys.executable, '-I', '-S', '-c', script, str(target)],
                            cwd=tmp_path, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('module,names', [
    (document, ('_keys', '_number', '_name', '_unique_object')),
    (circuit_document, ('_keys', '_unique_object', '_json_copy')),
    (execution, ('_unique_object', '_integer', '_reject_number', '_float')),
])
def test_existing_helper_import_paths_remain_aliases(module, names):
    for name in names:
        assert getattr(module, name) is getattr(_validation, name)
