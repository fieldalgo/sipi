"""Frozen module-inclusion evidence must reject missing or unfinished builds."""
import importlib.util
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

spec = importlib.util.spec_from_file_location('frozen_imports',
    Path(__file__).resolve().parents[1] / 'packaging/frozen_imports.py')
frozen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frozen)


def report():
    root = ET.Element('nuitka-compilation-report', nuitka_version='2.8.10', mode='onefile', completion='yes')
    for name in frozen.DYNAMIC_MODULES:
        ET.SubElement(root, 'module', name=name, kind='CompiledPythonModule', source_path=name+'.py')
    return root


def test_real_installed_compatibility_modules_and_report(tmp_path):
    sources = frozen.preflight()
    assert len(sources) == 4 and all(len(row['sha256']) == 64 for row in sources)
    path = tmp_path/'compilation.xml'
    ET.ElementTree(report()).write(path)
    assert [row['name'] for row in frozen.verify_report(path)] == [row['name'] for row in sources]


@pytest.mark.parametrize('problem', ['missing', 'duplicate', 'uncompiled', 'unfinished', 'wrong-version', 'wrong-mode'])
def test_unusable_compilation_reports_are_rejected(tmp_path, problem):
    root = report()
    if problem == 'missing': root.remove(root[0])
    elif problem == 'duplicate': ET.SubElement(root, 'module', **root[0].attrib)
    elif problem == 'uncompiled': root[0].set('kind', 'UncompiledPythonModule')
    elif problem == 'unfinished': root.set('completion', 'no')
    elif problem == 'wrong-version': root.set('nuitka_version', '0.0')
    elif problem == 'wrong-mode': root.set('mode', 'standalone')
    path = tmp_path/'compilation.xml'; ET.ElementTree(root).write(path)
    with pytest.raises(ValueError): frozen.verify_report(path)
