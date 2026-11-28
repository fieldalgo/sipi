# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Editable template inputs bound to their exact resolved cross-section."""
from dataclasses import dataclass, field
from inspect import signature
import json

from ._validation import _json_copy, _keys, _unique_object
from .document import CrossSectionDocument
from .sampling import _scalar
from ._template_registry import _TEMPLATES, _TEMPLATES_V2
from . import templates as _templates

__all__ = ['TemplateSectionDocument']

_V1, _V2 = 'sipi.template-section/1', 'sipi.template-section/2'
# Box parameters a version-2 document resolves and writes, when the template has them.
_BOX_PARAMETERS = ('box_width', 'air_height', 'lower_air_height')


def _build(template, parameters, mesh, schema=_V1):
    if not isinstance(template, str) or template not in _TEMPLATES:
        raise ValueError('unsupported section template')
    parameters = _json_copy(parameters)
    if not isinstance(parameters, dict):
        raise ValueError('parameters must be a template argument object')
    factory = (_TEMPLATES if schema == _V1 else _TEMPLATES_V2)[template]
    spec = signature(factory)
    try:
        bound = spec.bind(**parameters)
    except TypeError as exc:
        raise ValueError('unknown or missing template parameters') from exc
    bound.apply_defaults()
    if any(v is None and spec.parameters[k].default is not None for k, v in bound.arguments.items()):
        raise ValueError('only optional template parameters with None defaults may be null')
    parameters = {k: None if v is None else _scalar(v) for k, v in bound.arguments.items()}
    if schema == _V1:
        section = factory(**parameters)
    else:
        section = _resolve_box(template, factory, parameters)
    partial = CrossSectionDocument(section, mesh=mesh)
    cross_section = CrossSectionDocument(section, mesh=section.mesh_settings(**partial.mesh_options))
    return parameters, cross_section


def _resolve_box(template, factory, parameters):
    """Build with the v2 boxes and write the resolved box values into parameters.

    A None box_width, air_height or lower_air_height becomes the value the v2
    rule chose, so the saved parameters rebuild the same geometry under any
    later rule. The rebuild with the written values must be exact.
    """
    section, chosen = _templates._resolved_defaults(factory, parameters)
    resolved = dict(parameters)
    for key in _BOX_PARAMETERS:
        if key in resolved and resolved[key] is None:
            resolved[key] = section.width if key == 'box_width' else chosen[key]
    if resolved != parameters:
        explicit = factory(**resolved)
        if CrossSectionDocument(explicit).dumps() != CrossSectionDocument(section).dumps():
            raise ValueError(f'template {template!r}: resolved box parameters do not rebuild the section')
        parameters.update(resolved)
        section = explicit
    return section


def _validated(data):
    data = _json_copy(data)
    if not isinstance(data, dict) or data.get('schema') not in (_V1, _V2):
        raise ValueError('unsupported template-section schema')
    schema = data['schema']
    keys = ('schema', 'template', 'parameters', 'cross_section')
    _keys(data, keys if schema == _V1 else keys+('box_rule',), where='template section')
    if schema == _V2:
        if data['box_rule'] != 'v2':
            raise ValueError("sipi.template-section/2 records box_rule 'v2'")
        if not isinstance(data['parameters'], dict) or any(
                data['parameters'].get(key, 0) is None for key in _BOX_PARAMETERS):
            raise ValueError('sipi.template-section/2 stores resolved box parameters, not null')
    saved = CrossSectionDocument.from_dict(data['cross_section'])
    parameters, rebuilt = _build(data['template'], data['parameters'], saved.mesh_options, schema)
    if saved.dumps() != rebuilt.dumps():
        raise ValueError('stored geometry and resolved mesh do not match the template parameters')
    out = dict(schema=schema, template=data['template'], parameters=parameters, cross_section=saved.to_dict())
    if schema == _V2:
        out['box_rule'] = 'v2'
    return out


@dataclass(frozen=True, init=False)
class TemplateSectionDocument:
    """Keep editable factory inputs and exact geometry together, without solving.

    All existing factory defaults and mesh controls are resolved when creating
    the document. Loading checks that the stored geometry is exactly reproduced
    by those parameters in the current engine. A changed factory or inconsistent
    file rejects instead of silently substituting a different geometry.

    Edit by constructing a new document; explicitly pass the old mesh options
    if fixed controls are intended. Existing arbitrary geometry documents stay
    supported separately, with no attempt to infer template inputs from them.

    schema 'sipi.template-section/1' builds with the v1 default boxes, as it
    always has; pass it explicitly to create one. 'sipi.template-section/2'
    (the default for new documents since 2026-11-28) builds with the v2 boxes
    of sipi.templates.box_rule, writes the resolved box_width, air_height and
    lower_air_height (where the template has them) into parameters, and records
    box_rule 'v2'. Neither version follows the caller's box_rule context.
    """
    _data_json: str = field(repr=False)

    def __init__(self, template, parameters, *, mesh=None, schema=_V2):
        if schema not in (_V1, _V2):
            raise ValueError('unsupported template-section schema')
        resolved, cross_section = _build(template, parameters, mesh, schema)
        data = dict(schema=schema, template=template,
                    parameters=resolved, cross_section=cross_section.to_dict())
        if schema == _V2:
            data['box_rule'] = 'v2'
        object.__setattr__(self, '_data_json', json.dumps(data, sort_keys=True, indent=2,
                                                       ensure_ascii=False, allow_nan=False))

    @classmethod
    def from_dict(cls, data):
        result = cls.__new__(cls)
        object.__setattr__(result, '_data_json', json.dumps(_validated(data), sort_keys=True,
                                                          indent=2, ensure_ascii=False, allow_nan=False))
        return result

    @classmethod
    def loads(cls, text):
        def reject(value):
            raise ValueError('nonfinite JSON number: '+value)
        return cls.from_dict(json.loads(text, object_pairs_hook=_unique_object, parse_constant=reject))

    def dumps(self):
        return self._data_json

    def to_dict(self):
        return json.loads(self._data_json)

    @property
    def template(self):
        return self.to_dict()['template']

    @property
    def parameters(self):
        return self.to_dict()['parameters']

    @property
    def cross_section(self):
        return CrossSectionDocument.from_dict(self.to_dict()['cross_section'])

    @property
    def section(self):
        return self.cross_section.section

    @property
    def mesh_options(self):
        return self.cross_section.mesh_options

    def analyze(self):
        return self.cross_section.analyze()
