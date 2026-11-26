# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved transmission lines whose conductor currents default to the panel method.

``sipi.transmission-line/8`` holds the same fields as transmission-line/7 plus
the conductor-current method. Normalization always writes ``current_method``
and, for the panel method, the panel controls into the saved document, so a
stored line never depends on a later change of defaults. Calculation reuses the
delegation of ``sipi.method-transmission-line/1``; this module adds no
numerical path. Transmission-line/1-7 documents are not changed.
"""
import dataclasses
import json

from .document import _keys, _unique_object
from .line_model import TransmissionLineDocument
from .method_line import MethodTransmissionLineDocument

__all__ = ['DefaultPanelTransmissionLineDocument', 'DEFAULT_PANEL_CONTROLS']

_SCHEMA = 'sipi.transmission-line/8'
_LINE_KEYS = ('schema', 'cross_section', 'frequency_hz', 'materials', 'conductor', 'length_m', 'reference_ohms')
_DEFAULT_KINDS = ('surface', 'surface-boundaries')
_VOLUME = "set current_method 'volume-p1' to use the P1 volume-mesh surface currents"

# Default panel controls by boundary combination (bottom, top, sides). These
# are the candidate values of the default-method design and are not final:
# a separate measurement of the 64->128 panel change and run time decides
# them. Every default lives here; saved documents record the values they used.
DEFAULT_PANEL_CONTROLS = {
    ('ground', 'open', 'open'): dict(panels_per_edge=64, ground_modes=512, interpolation_degree=14),
    ('ground', 'ground', 'open'): dict(panels_per_edge=64, ground_modes=512, interpolation_degree=14),
    ('open', 'open', 'open'): dict(panels_per_edge=64, interpolation_degree=12),
}


def _line7(data):
    """The canonical transmission-line/7 document with the same content."""
    line = {key: data[key] for key in _LINE_KEYS if key != 'schema'}
    return TransmissionLineDocument.from_dict(dict(line, schema='sipi.transmission-line/7'))


def _method(line, method, panel):
    data = dict(schema='sipi.method-transmission-line/1', line=line.to_dict(), current_method=method)
    if panel is not None:
        data['panel'] = panel
    return MethodTransmissionLineDocument.from_dict(data)


class DefaultPanelTransmissionLineDocument:
    """Strict ``sipi.transmission-line/8``; panel conductor currents by default.

    The line fields are those of transmission-line/7. ``current_method`` is
    ``'panel'`` or ``'volume-p1'``. When it is omitted, ``surface`` and
    ``surface-boundaries`` conductors use ``'panel'``; ``perfect`` conductors
    have no default and ``surface-faces`` conductors (per-face metals) are
    refused for the panel method, so ``'volume-p1'`` must be named for them.
    Omitted panel controls take ``DEFAULT_PANEL_CONTROLS`` for the boundary
    combination: a bottom ground with open top and sides, two grounds with open
    sides, or open bottom, top and sides. Other combinations are refused for
    the panel method. Normalization checks what it can decide without a field
    solve (boundaries, conductor kind, thickness, controls, panel count);
    kernel range and refinement checks run in analyze(). A panel refusal never
    falls back to the P1 method.
    """
    def __init__(self, cross_section, frequency, *, materials, conductor, length, z_ref=50.0,
                 current_method=None, panel=None):
        line = TransmissionLineDocument(cross_section, frequency, materials=materials, conductor=conductor,
                                        length=length, z_ref=z_ref, schema='sipi.transmission-line/7')
        data = dict(line.to_dict(), schema=_SCHEMA)
        if current_method is not None:
            data['current_method'] = current_method
        if panel is not None:
            data['panel'] = panel
        self._data = self._validate(data)

    @staticmethod
    def _validate(data):
        if not isinstance(data, dict):
            raise ValueError('transmission line must be an object')
        present = tuple(key for key in ('current_method', 'panel') if key in data)
        _keys(data, _LINE_KEYS + present, where='transmission line')
        if data['schema'] != _SCHEMA:
            raise ValueError('unsupported transmission-line schema')
        line = _line7(data)
        kind = line.to_dict()['conductor']['kind']
        method = data.get('current_method')
        if method is None:
            if kind == 'surface-faces':
                raise ValueError('surface-faces (per-face metal) has no panel default in transmission-line/8; '
                                 + _VOLUME + ', or use a face panel line document')
            if kind not in _DEFAULT_KINDS:
                raise ValueError(f'{kind} conductors have no default current_method in transmission-line/8; '
                                 "set current_method 'panel' or 'volume-p1'")
            method = 'panel'
        if not isinstance(method, str) or method not in ('panel', 'volume-p1'):
            raise ValueError("current_method must be 'panel' or 'volume-p1'")
        if method == 'volume-p1':
            if 'panel' in data:
                raise ValueError("panel controls require current_method 'panel'")
            _method(line, method, None)
            return dict(line.to_dict(), schema=_SCHEMA, current_method=method)
        if kind == 'surface-faces':
            raise ValueError('the panel current method does not support surface-faces (per-face metal); '
                             + _VOLUME + ', or use a face panel line document')
        section = line.cross_section.section
        boundaries = (section.bottom, section.top, section.sides)
        if boundaries not in DEFAULT_PANEL_CONTROLS:
            raise ValueError('panel current method requires a bottom ground with open top and sides, '
                             'two grounds with open sides, or open bottom, top and sides; ' + _VOLUME)
        panel = data['panel'] if 'panel' in data else dict(DEFAULT_PANEL_CONTROLS[boundaries])
        try:
            normalized = _method(line, method, panel).to_dict()['panel']
        except ValueError as error:
            raise ValueError(f'{error}; {_VOLUME}') from error
        return dict(line.to_dict(), schema=_SCHEMA, current_method=method, panel=normalized)

    @classmethod
    def from_dict(cls, data):
        out = cls.__new__(cls)
        out._data = cls._validate(data)
        return out

    @classmethod
    def loads(cls, text):
        def reject(value):
            raise ValueError('nonfinite JSON number: ' + value)
        return cls.from_dict(json.loads(text, object_pairs_hook=_unique_object, parse_constant=reject))

    def dumps(self):
        """Canonical input JSON with the method and panel controls written out."""
        return json.dumps(self._data, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)

    def to_dict(self):
        return json.loads(self.dumps())

    @property
    def current_method(self):
        return self._data['current_method']

    @property
    def line(self):
        """The transmission-line/7 document with the same line content."""
        return _line7(self.to_dict())

    def method_document(self):
        """The ``sipi.method-transmission-line/1`` document with the same content."""
        data = self.to_dict()
        return _method(_line7(data), data['current_method'], data.get('panel'))

    def equivalent_document(self):
        """A fresh copy of the existing document that this input runs."""
        return self.method_document().equivalent_document()

    @property
    def cross_section(self):
        return self.line.cross_section

    def analyze(self):
        """Run the equivalent document; the result retains this input."""
        return dataclasses.replace(self.equivalent_document().analyze(), input_json=self.dumps())
