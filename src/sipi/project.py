# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Immutable local project snapshots with explicit, request-bound results."""
from dataclasses import dataclass, field
import json

from .circuit_document import _json_copy
from .document import _keys, _unique_object
from .execution import _integer, _reject_number, _float
from .execution_request import SavedExecutionRequest
from .execution_record import SavedExecutionRecord, _canonical, _digest, _matches, _RUN, _DIGEST

__all__ = ['SavedProject']

_DEFAULT_LIMIT = 16 * 1024 * 1024


def _label(value, name, limit):
    if (not isinstance(value, str) or not value.strip()
            or len(value.encode('utf-8')) > limit
            or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise ValueError(f'{name} must be nonempty text within {limit} UTF-8 bytes without controls')


def _request(design):
    if not isinstance(design['source_text'], str):
        raise ValueError('source_text must be original JSON text')
    controls = design['controls']
    _keys(controls, ('max_input_bytes', 'max_evaluations', 'diagnostics'), where='design controls')
    request = SavedExecutionRequest(design['source_text'], **controls)
    if _canonical(controls) != _canonical(request.controls):
        raise ValueError('design controls must be canonical')
    return request


def _new_design(design_id, label, request):
    if not isinstance(request, SavedExecutionRequest):
        raise ValueError('request must be a SavedExecutionRequest')
    return dict(design_id=design_id, label=label, source_text=request.source_text,
                controls=request.controls, records=[], selected_run_id=None)


def _index(data, design_id):
    if not _matches(_RUN, design_id):
        raise ValueError('invalid design_id')
    for i, design in enumerate(data['designs']):
        if design['design_id'] == design_id:
            return i
    raise ValueError('design_id is not in this project')


def _validated(data, limit):
    data = _json_copy(data)
    text = _canonical(data)
    if len(text.encode('utf-8')) > limit:
        raise ValueError('saved project exceeds max_project_bytes')
    _keys(data, ('schema', 'project_id', 'title', 'designs', 'content_sha256'), where='project')
    if data['schema'] != 'sipi.project/1' or not _matches(_RUN, data['project_id']):
        raise ValueError('unsupported project schema or invalid project_id')
    _label(data['title'], 'title', 512)
    if not _matches(_DIGEST, data['content_sha256']) or data['content_sha256'] != _digest(data):
        raise ValueError('project content digest mismatch')
    designs = data['designs']
    if not isinstance(designs, list) or not 1 <= len(designs) <= 64:
        raise ValueError('project must contain 1..64 designs')
    design_ids = set()
    run_ids = set()
    for design in designs:
        _keys(design, ('design_id', 'label', 'source_text', 'controls', 'records', 'selected_run_id'),
              where='project design')
        ident = design['design_id']
        if not _matches(_RUN, ident) or ident in design_ids:
            raise ValueError('design IDs must be valid and unique')
        design_ids.add(ident)
        _label(design['label'], 'label', 256)
        request = _request(design)
        records = design['records']
        if not isinstance(records, list) or len(run_ids) + len(records) > 128:
            raise ValueError('project must contain at most 128 execution records')
        selected = design['selected_run_id']
        if selected is not None and not _matches(_RUN, selected):
            raise ValueError('selected_run_id must be null or a valid run ID')
        found = selected is None
        for raw in records:
            record = SavedExecutionRecord.from_dict(raw, max_record_bytes=limit)
            run_id = record.run_id
            if run_id in run_ids:
                raise ValueError('execution run IDs must be unique across the project')
            run_ids.add(run_id)
            if run_id == selected:
                found = True
                if _canonical(record.receipt['request']) != _canonical(request.to_dict()):
                    raise ValueError('selected result does not match the current design request')
        if not found:
            raise ValueError('selected_run_id does not identify a record in this design')
    return text


@dataclass(frozen=True, init=False)
class SavedProject:
    """Preserve A/B inputs and result history without automatic calculation.

    Edits return new snapshots. Results are selected explicitly and only for the
    current semantic request; changing input or execution controls clears the
    selection but retains history. Hosts still admit responses by their active
    run tokens, including when an identical request is run repeatedly.

    This envelope performs no file I/O. Digests detect content changes, not
    authenticity; embedded artifact metadata remains host-declared.
    """
    _data_json: str = field(repr=False)
    _max_project_bytes: int = field(repr=False)

    def __init__(self, request, *, project_id, design_id, title, label,
                 max_project_bytes=_DEFAULT_LIMIT):
        data = dict(schema='sipi.project/1', project_id=project_id, title=title,
                    designs=[_new_design(design_id, label, request)])
        data['content_sha256'] = _digest(data)
        self._assign(data, max_project_bytes)

    def _assign(self, data, limit):
        limit = _integer('max_project_bytes', limit, 1, 64 * 1024 * 1024)
        object.__setattr__(self, '_data_json', _validated(data, limit))
        object.__setattr__(self, '_max_project_bytes', limit)

    @classmethod
    def from_dict(cls, data, *, max_project_bytes=_DEFAULT_LIMIT):
        result = cls.__new__(cls)
        result._assign(data, max_project_bytes)
        return result

    @classmethod
    def loads(cls, text, *, max_project_bytes=_DEFAULT_LIMIT):
        limit = _integer('max_project_bytes', max_project_bytes, 1, 64 * 1024 * 1024)
        if not isinstance(text, str):
            raise ValueError('saved project must be JSON text')
        if len(text.encode('utf-8')) > limit:
            raise ValueError('saved project exceeds max_project_bytes')
        data = json.loads(text, object_pairs_hook=_unique_object,
                          parse_constant=_reject_number, parse_float=_float)
        return cls.from_dict(data, max_project_bytes=limit)

    def dumps(self):
        return self._data_json

    def to_dict(self):
        return json.loads(self._data_json)

    @property
    def design_ids(self):
        return tuple(d['design_id'] for d in self.to_dict()['designs'])

    def design(self, design_id):
        """Return a detached design including its original input and history."""
        data = self.to_dict()
        return data['designs'][_index(data, design_id)]

    def prepare(self, design_id):
        """Prepare the current saved request without executing it."""
        return _request(self.design(design_id))

    def current_record(self, design_id):
        """Return the explicitly selected record, or None; never select latest."""
        design = self.design(design_id)
        for raw in design['records']:
            if raw['run_id'] == design['selected_run_id']:
                return SavedExecutionRecord.from_dict(raw, max_record_bytes=self._max_project_bytes)
        return None

    def _replace(self, data):
        data['content_sha256'] = _digest(data)
        return self.from_dict(data, max_project_bytes=self._max_project_bytes)

    def add_design(self, design_id, label, request):
        data = self.to_dict()
        data['designs'].append(_new_design(design_id, label, request))
        return self._replace(data)

    def duplicate_design(self, source_id, design_id, label):
        """Copy the current request into a new design, without result history."""
        return self.add_design(design_id, label, self.prepare(source_id))

    def update_design(self, design_id, request, *, label=None):
        if not isinstance(request, SavedExecutionRequest):
            raise ValueError('request must be a SavedExecutionRequest')
        data = self.to_dict()
        design = data['designs'][_index(data, design_id)]
        if _canonical(_request(design).to_dict()) != _canonical(request.to_dict()):
            design['selected_run_id'] = None
        design.update(source_text=request.source_text, controls=request.controls)
        if label is not None:
            design['label'] = label
        return self._replace(data)

    def remove_design(self, design_id):
        data = self.to_dict()
        del data['designs'][_index(data, design_id)]
        return self._replace(data)

    def attach_record(self, design_id, record, *, select=False):
        """Append history; selection requires explicit intent and matching input.

        A late response can be retained as history, but this method does not
        certify it is the host's currently active invocation.
        """
        if not isinstance(record, SavedExecutionRecord) or type(select) is not bool:
            raise ValueError('record must be a SavedExecutionRecord and select must be boolean')
        data = self.to_dict()
        design = data['designs'][_index(data, design_id)]
        design['records'].append(record.to_dict())
        if select:
            design['selected_run_id'] = record.run_id
        return self._replace(data)

    def select_record(self, design_id, run_id):
        data = self.to_dict()
        data['designs'][_index(data, design_id)]['selected_run_id'] = run_id
        return self._replace(data)

    def remove_record(self, design_id, run_id):
        data = self.to_dict()
        design = data['designs'][_index(data, design_id)]
        if not _matches(_RUN, run_id) or not any(r['run_id'] == run_id for r in design['records']):
            raise ValueError('run_id is not in this design')
        design['records'] = [r for r in design['records'] if r['run_id'] != run_id]
        if design['selected_run_id'] == run_id:
            design['selected_run_id'] = None
        return self._replace(data)
