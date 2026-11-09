# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Editable template inputs bound to their exact resolved cross-section."""
from dataclasses import dataclass, field
from inspect import signature
import json

from .circuit_document import _json_copy
from .document import CrossSectionDocument, _keys, _unique_object
from .sampling import _scalar
from .study import _TEMPLATES

__all__ = ['TemplateSectionDocument']


def _build(template, parameters, mesh):
    if not isinstance(template, str) or template not in _TEMPLATES:
        raise ValueError('unsupported section template')
    parameters = _json_copy(parameters)
    if not isinstance(parameters, dict):
        raise ValueError('parameters must be a template argument object')
    factory = _TEMPLATES[template]
    spec = signature(factory)
    try:
        bound = spec.bind(**parameters)
    except TypeError as exc:
        raise ValueError('unknown or missing template parameters') from exc
    bound.apply_defaults()
    if any(v is None and spec.parameters[k].default is not None for k, v in bound.arguments.items()):
        raise ValueError('only optional template parameters with None defaults may be null')
    parameters = {k: None if v is None else _scalar(v) for k, v in bound.arguments.items()}
    section = factory(**parameters)
    partial = CrossSectionDocument(section, mesh=mesh)
    cross_section = CrossSectionDocument(section, mesh=section.mesh_settings(**partial.mesh_options))
    return parameters, cross_section


def _validated(data):
    data = _json_copy(data)
    _keys(data, ('schema', 'template', 'parameters', 'cross_section'), where='template section')
    if data['schema'] != 'sipi.template-section/1':
        raise ValueError('unsupported template-section schema')
    saved = CrossSectionDocument.from_dict(data['cross_section'])
    parameters, rebuilt = _build(data['template'], data['parameters'], saved.mesh_options)
    if saved.dumps() != rebuilt.dumps():
        raise ValueError('stored geometry and resolved mesh do not match the template parameters')
    return dict(schema='sipi.template-section/1', template=data['template'],
                parameters=parameters, cross_section=saved.to_dict())


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
    """
    _data_json: str = field(repr=False)

    def __init__(self, template, parameters, *, mesh=None):
        resolved, cross_section = _build(template, parameters, mesh)
        data = dict(schema='sipi.template-section/1', template=template,
                    parameters=resolved, cross_section=cross_section.to_dict())
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
