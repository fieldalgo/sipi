# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""sipi.template-section/2 records the resolved v2 box; /1 keeps v1."""
import inspect
import json

import pytest

from sipi import CrossSectionDocument, templates
from sipi._template_registry import _TEMPLATES
from sipi.template_document import TemplateSectionDocument
from test_template_box_rule import NAMES, inputs, raw, text


@pytest.mark.parametrize('name', NAMES)
def test_template_section_2_writes_the_resolved_box(name):
    doc = TemplateSectionDocument(name, inputs(name), schema='sipi.template-section/2')
    data = doc.to_dict()
    assert data['schema'] == 'sipi.template-section/2' and data['box_rule'] == 'v2'
    for key in ('box_width', 'air_height', 'lower_air_height'):
        if key in inspect.signature(_TEMPLATES[name]).parameters:
            assert isinstance(data['parameters'][key], float)
    assert data['parameters']['box_width'] == doc.section.width
    assert text(doc.section) == text(raw(name, 'v2'))
    # The written box rebuilds the same geometry under either rule.
    for rule in templates.BOX_RULES:
        with templates.box_rule(rule):
            assert TemplateSectionDocument.loads(doc.dumps()).dumps() == doc.dumps()
            assert text(getattr(templates, name)(**data['parameters'])) == text(doc.section)


def test_new_documents_default_to_version_2():
    doc = TemplateSectionDocument('microstrip', inputs('microstrip'))
    assert doc.dumps() == TemplateSectionDocument('microstrip', inputs('microstrip'),
                                                  schema='sipi.template-section/2').dumps()
    with templates.box_rule('v1'):
        assert TemplateSectionDocument('microstrip', inputs('microstrip')).dumps() == doc.dumps()


def test_template_section_1_stays_v1_and_2_rejects_changes():
    V1 = 'sipi.template-section/1'
    first = TemplateSectionDocument('microstrip', inputs('microstrip'), schema=V1)
    with templates.box_rule('v2'):
        assert TemplateSectionDocument('microstrip', inputs('microstrip'), schema=V1).dumps() == first.dumps()
    assert TemplateSectionDocument.loads(first.dumps()).dumps() == first.dumps()
    assert first.to_dict()['schema'] == 'sipi.template-section/1' and 'box_rule' not in first.to_dict()
    assert first.to_dict()['parameters']['box_width'] is None
    assert first.section.width == raw('microstrip', 'v1').width
    second = TemplateSectionDocument('microstrip', inputs('microstrip'), schema='sipi.template-section/2').to_dict()
    for change in (dict(box_rule='v1'), dict(parameters=dict(second['parameters'], box_width=None)),
                   dict(parameters=dict(second['parameters'], box_width=second['parameters']['box_width']*2))):
        with pytest.raises(ValueError):
            TemplateSectionDocument.from_dict(dict(second, **change))
    with pytest.raises(ValueError, match='template section'):
        TemplateSectionDocument.from_dict({k: v for k, v in second.items() if k != 'box_rule'})
    with pytest.raises(ValueError):
        TemplateSectionDocument('microstrip', inputs('microstrip'), schema='sipi.template-section/3')
    from sipi.execution import normalize_saved, saved_schemas
    assert 'sipi.template-section/2' in saved_schemas()
    text2 = json.dumps(second, sort_keys=True, indent=2)
    assert normalize_saved(text2) == TemplateSectionDocument.from_dict(second).dumps()
