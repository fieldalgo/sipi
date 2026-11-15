# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Internal section-document loading without study or product composition."""
import json
from pathlib import Path
import subprocess
import sys

import sipi
from sipi import study, templates
from sipi._template_registry import _TEMPLATES
from sipi.template_document import TemplateSectionDocument


def test_existing_study_catalog_keeps_factory_identity():
    assert study._TEMPLATES is _TEMPLATES
    for name, factory in _TEMPLATES.items():
        assert factory is getattr(templates, name)


def test_section_documents_load_without_study_or_product_modules(tmp_path):
    # Deliberately bypass the broad public initializer, not its actual providers.
    # This checks an internal boundary, not standalone package installation.
    reference = Path(__file__).parent/'reference_data/template_section/reference.json'
    rows = json.loads(reference.read_text())['cases']
    inputs = tmp_path/'inputs.json'
    inputs.write_text(json.dumps(rows))
    expected = [TemplateSectionDocument(row['template'], row['supplied_parameters']).dumps()
                for row in rows]
    script = '''
import importlib.abc, json, pathlib, sys, types
blocked = {'study', 'corner_study', 'impedance_material', 'circuit_document',
           'execution', 'execution_request', 'execution_record', 'project',
           'project_io', 'cli', '_workbench'}
class Boundary(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith('sipi.') and fullname.split('.')[1] in blocked:
            raise AssertionError('Unexpected study/product dependency: ' + fullname)
sys.meta_path.insert(0, Boundary())
package = types.ModuleType('sipi')
package.__path__ = [sys.argv[1]]
package.__package__ = 'sipi'
sys.modules['sipi'] = package
from sipi.template_document import TemplateSectionDocument
from sipi.crosssection import CrossSection

def forbidden_mesh(*args, **kwargs):
    raise AssertionError('Document preparation generated a mesh')
CrossSection.mesh = forbidden_mesh
rows = json.loads(pathlib.Path(sys.argv[2]).read_text())
output = []
for row in rows:
    doc = TemplateSectionDocument(row['template'], row['supplied_parameters'])
    assert doc.cross_section.to_dict() == row['cross_section']
    assert TemplateSectionDocument.loads(doc.dumps()).dumps() == doc.dumps()
    output.append(doc.dumps())
assert not any('sipi.' + name in sys.modules for name in blocked)
print(json.dumps(output))
'''
    result = subprocess.run(
        [sys.executable, '-I', '-c', script, str(Path(sipi.__file__).parent), str(inputs)],
        cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
