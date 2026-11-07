"""Reviewed dynamic imports for the pinned NumPy compatibility namespaces."""
import hashlib
import importlib
from pathlib import Path
import xml.etree.ElementTree as ET


# Both pinned packages construct these import names at runtime. The compiler
# cannot infer the FFT module from __import__(__package__ + '.fft').
DYNAMIC_MODULES = tuple(prefix + suffix for prefix in
    ('array_api_compat.numpy.', 'scipy._external.array_api_compat.numpy.')
    for suffix in ('fft', 'linalg'))


def preflight():
    """Verify exact installed module paths and exercise their public operations."""
    import numpy as np
    result = []
    for name in DYNAMIC_MODULES:
        module = importlib.import_module(name)
        if name.endswith('.fft'):
            np.testing.assert_array_equal(module.fft(np.array([1., 0., 0., 0.])), np.ones(4))
        else:
            if module.vector_norm(np.array([3., 4.])) != 5.:
                raise ValueError('Compatibility linear-algebra preflight failed: ' + name)
        path = Path(module.__file__)
        result.append(dict(name=name, source=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    return result


def verify_report(path):
    """Require compiled modules in a completed pinned onefile build report.

    This verifies inclusion, not executable behavior. The real smoke remains
    mandatory; a module's presence alone cannot establish a working EXE.
    """
    root = ET.parse(path).getroot()
    if (root.tag != 'nuitka-compilation-report' or root.get('nuitka_version') != '2.8.10'
            or root.get('mode') != 'onefile' or root.get('completion') != 'yes'):
        raise ValueError('Expected a completed Nuitka 2.8.10 onefile compilation report')
    result = []
    for name in DYNAMIC_MODULES:
        found = [row for row in root.findall('module') if row.get('name') == name]
        if len(found) != 1 or found[0].get('kind') != 'CompiledPythonModule':
            raise ValueError('Required dynamic module was not compiled exactly once: ' + name)
        result.append(dict(name=name, kind=found[0].get('kind'), source=found[0].get('source_path')))
    return result
