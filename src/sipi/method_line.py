# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved transmission lines with an explicitly selected conductor-current method.

``sipi.method-transmission-line/1`` wraps a canonical transmission-line
document and records which existing calculation supplies the surface
currents. Each method runs an existing document unchanged, so its result is
the result of that document; this module adds no numerical path.
``sipi.method-transmission-line/2`` admits the same methods with the same
meaning plus ``volume-p1-recovered``, which runs
``sipi.recovered-transmission-line/1``. Version 1 keeps its two values.
"""
import dataclasses
import json

from .document import _keys, _unique_object
from .line_model import TransmissionLineDocument
from .open_panel_line import OpenPanelTransmissionLineDocument
from .panel_line import PanelTransmissionLineDocument
from .recovered_line import RecoveredTransmissionLineDocument
from .two_ground_panel_line import TwoGroundPanelTransmissionLineDocument


__all__ = ['MethodTransmissionLineDocument', 'CURRENT_METHODS', 'METHODS_BY_SCHEMA', 'RECOVERED_METHOD']

_SCHEMA = 'sipi.method-transmission-line/1'
CURRENT_METHODS = ('panel', 'volume-p1')  # the values of version 1, unchanged
RECOVERED_METHOD = 'volume-p1-recovered'
METHODS_BY_SCHEMA = {_SCHEMA: CURRENT_METHODS,
                     'sipi.method-transmission-line/2': CURRENT_METHODS+(RECOVERED_METHOD,)}
_PANEL_KEYS = ('panels_per_edge', 'ground_modes', 'interpolation_degree')
_OPEN_PANEL_KEYS = ('panels_per_edge', 'interpolation_degree')  # no ground plane, no ground modes
_OPEN = ('open', 'open', 'open')


def _metal(conductor):
    """The whole-surface metal record equivalent to a ``surface`` conductor."""
    if 'roughness_rms' in conductor:  # transmission-line/1 Hammerstad RMS, zero included
        roughness = dict(kind='hammerstad', rms_m=conductor['roughness_rms'])
    else:
        roughness = conductor['roughness']
    return dict(conductivity=conductor['conductivity'],
                relative_permeability=conductor['relative_permeability'], roughness=roughness)


def _boundary_line(line, section):
    """A line whose conductor is perfect or surface-boundaries, or a refusal."""
    conductor = line['conductor']
    if conductor['kind'] in ('perfect', 'surface-boundaries'):
        return line
    if conductor['kind'] != 'surface':
        raise ValueError('panel current method supports perfect, surface and surface-boundaries conductors')
    metal = _metal(conductor)
    out = dict(line)
    if out['schema'] in ('sipi.transmission-line/1', 'sipi.transmission-line/2'):
        out['schema'] = 'sipi.transmission-line/3'
    out['conductor'] = dict(kind='surface-boundaries', ground_thickness=conductor['ground_thickness'],
        conductors={t.name: metal for t in section.traces if not t.ground}, reference=metal)
    return TransmissionLineDocument.from_dict(out).to_dict()


def _two_ground(line, section, panel):
    conductor = line['conductor']
    if conductor['kind'] == 'surface':
        signals = {t.name: _metal(conductor) for t in section.traces if not t.ground}
        reference = _metal(conductor)
    elif conductor['kind'] == 'surface-boundaries':
        signals, reference = conductor['conductors'], conductor['reference']
    else:
        raise ValueError('two-ground panel current method requires surface or surface-boundaries conductors')
    surfaces = dict(kind='surfaces', bottom=reference, top=reference, sides=None,
                    conductors={t.name: reference for t in section.traces if t.ground})
    return TwoGroundPanelTransmissionLineDocument.from_dict(dict(
        schema='sipi.two-ground-panel-transmission-line/1', cross_section=line['cross_section'],
        frequency_hz=line['frequency_hz'], materials=line['materials'], conductors=signals,
        reference=surfaces, ground_thickness_m=conductor['ground_thickness'], length_m=line['length_m'],
        reference_ohms=line['reference_ohms'], panel=panel))


def _equivalent(data):
    """The existing document that performs the selected calculation."""
    line = TransmissionLineDocument.from_dict(data['line'])
    if data['current_method'] == 'volume-p1':
        return line
    if data['current_method'] == RECOVERED_METHOD:
        return RecoveredTransmissionLineDocument.from_dict(dict(
            schema='sipi.recovered-transmission-line/1', line=line.to_dict(), recovery=data['recovery']))
    section = line.cross_section.section
    value = line.to_dict()
    boundaries = (section.bottom, section.top, section.sides)
    if boundaries == ('ground', 'open', 'open'):
        nested = _boundary_line(value, section)
        version = 2 if nested['schema'] == 'sipi.transmission-line/7' else 1
        return PanelTransmissionLineDocument.from_dict(dict(
            schema=f'sipi.panel-transmission-line/{version}', line=nested, panel=data['panel']))
    if boundaries == ('ground', 'ground', 'open'):
        return _two_ground(value, section, data['panel'])
    if boundaries == _OPEN:
        return OpenPanelTransmissionLineDocument.from_dict(dict(
            schema='sipi.open-panel-transmission-line/1', line=_boundary_line(value, section),
            panel=data['panel']))
    raise ValueError('panel current method requires a bottom ground with open top and sides, '
                     'two grounds with open sides, or open bottom, top and sides')


class MethodTransmissionLineDocument:
    """Strict saved line whose conductor-current method is explicit.

    ``current_method`` has no default. ``volume-p1`` runs the nested line as
    it is (the P1 volume-mesh surface currents of transmission-line/1-7).
    ``panel`` runs the existing panel line: a bottom ground with open top and
    sides uses ``sipi.panel-transmission-line``; two grounds with open sides use
    ``sipi.two-ground-panel-transmission-line``; open bottom, top and sides
    (grounded traces only) use ``sipi.open-panel-transmission-line``. A
    ``surface`` conductor is passed on as the same metal on every boundary. The
    panel controls are required and saved: panels_per_edge, ground_modes and
    interpolation_degree, without ground_modes for an open box. Anything the panel documents refuse is refused here;
    there is no fallback to the other method. Normalization performs no field
    solve; shared panel admission and refinement checks run in analyze().

    Version 2 (``schema='sipi.method-transmission-line/2'``) also admits
    ``volume-p1-recovered`` with required ``recovery`` controls
    (``support_fraction``); it runs ``sipi.recovered-transmission-line/1`` on the
    nested line's own mesh. Its refusals (perfect or per-face conductors,
    uncharacterised corners, supports meeting other conductors or open walls)
    are not replaced by another method. Version 1 refuses that value.
    """
    def __init__(self, line, *, current_method, panel=None, recovery=None, schema=_SCHEMA):
        if not isinstance(line, TransmissionLineDocument):
            raise TypeError('line must be a TransmissionLineDocument')
        data = dict(schema=schema, line=line.to_dict(), current_method=current_method)
        if panel is not None:
            data['panel'] = panel
        if recovery is not None:
            data['recovery'] = recovery
        self._data = self._validate(data)

    @staticmethod
    def _validate(data):
        if not isinstance(data, dict):
            raise ValueError('method transmission line must be an object')
        schema = data.get('schema')
        if not isinstance(schema, str) or schema not in METHODS_BY_SCHEMA:
            raise ValueError('unsupported method-transmission-line schema')
        method = data.get('current_method')
        if not isinstance(method, str) or method not in METHODS_BY_SCHEMA[schema]:
            if schema == _SCHEMA:
                hint = (f"; {RECOVERED_METHOD!r} requires sipi.method-transmission-line/2"
                        if method == RECOVERED_METHOD else '')
                raise ValueError("current_method must be 'panel' or 'volume-p1'" + hint)
            raise ValueError('current_method must be ' + ', '.join(repr(m) for m in METHODS_BY_SCHEMA[schema]))
        extra = {'panel': ('panel',), RECOVERED_METHOD: ('recovery',)}.get(method, ())
        keys = ('schema', 'line', 'current_method') + extra
        _keys(data, keys, where='method transmission line')
        out = dict(schema=schema, line=TransmissionLineDocument.from_dict(data['line']).to_dict(),
                   current_method=method)
        if method == RECOVERED_METHOD:
            out['recovery'] = data['recovery']
            out['recovery'] = _equivalent(out).to_dict()['recovery']
        if method == 'panel':
            if not isinstance(data['panel'], dict):
                raise ValueError('panel controls must be an object')
            section = TransmissionLineDocument.from_dict(data['line']).cross_section.section
            _keys(data['panel'], _OPEN_PANEL_KEYS if (section.bottom, section.top, section.sides) == _OPEN
                  else _PANEL_KEYS, where='panel controls')
            out['panel'] = dict(data['panel'])
            out['panel'] = _equivalent(out).to_dict()['panel']
        return out

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
        return json.dumps(self._data, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)

    def to_dict(self):
        return json.loads(self.dumps())

    @property
    def line(self):
        return TransmissionLineDocument.from_dict(self.to_dict()['line'])

    @property
    def current_method(self):
        return self._data['current_method']

    def equivalent_document(self):
        """A fresh copy of the existing document that this input runs."""
        return _equivalent(self.to_dict())

    def analyze(self):
        """Run the equivalent document; the result retains this input."""
        return dataclasses.replace(self.equivalent_document().analyze(), input_json=self.dumps())
