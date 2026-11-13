# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved quasi-static geometry and explicit constant series resistance."""
from dataclasses import dataclass
import json
import numpy as np

from .circuit_document import _json_copy
from .document import CrossSectionDocument, _keys, _unique_object
from .template_document import TemplateSectionDocument
from .network import _frequencies, _scalar, quasistatic_network

__all__ = ['QuasistaticLineDocument', 'QuasistaticLineResult']


def _section(data):
    cls = (TemplateSectionDocument if isinstance(data, dict)
           and data.get('schema') == 'sipi.template-section/1' else CrossSectionDocument)
    return cls.from_dict(data)


@dataclass(frozen=True)
class QuasistaticLineResult:
    """One extracted cross-section and its specified uniform-line network.

    Resistance is an explicitly supplied scalar times the identity, not a
    conductor-loss estimate. No internal inductance or dispersive material
    model is inferred. input_json retains the exact canonical request.
    """
    line: object
    network: object
    input_json: str


class QuasistaticLineDocument:
    """Pure input: editable or explicit section, frequencies, R, length and Zref.

    Validation never meshes, solves or reads files. Analysis extracts one
    cross-section, retaining its C/L and constant-loss-tangent G(f), then uses
    the existing full coupled uniform-line network. Frequency samples must be
    finite, nonnegative and strictly increasing. R >= 0 (ohm/m), length >= 0
    (m), and real Zref > 0 (ohm) apply uniformly to all signals/ports. This is
    not a skin-effect model or a physical high-frequency validity certificate.
    """
    def __init__(self, section, frequency, *, resistance, length, z_ref=50.):
        if not isinstance(section, (CrossSectionDocument, TemplateSectionDocument)):
            raise ValueError('section must be an explicit or editable cross-section document')
        self._assign(dict(schema='sipi.quasistatic-line/1', section=section.to_dict(),
            frequency_hz=_frequencies(frequency).tolist(), resistance_ohm_per_m=resistance,
            length_m=length, reference_ohms=z_ref))

    def _assign(self, value):
        data = _json_copy(value)
        _keys(data, ('schema', 'section', 'frequency_hz', 'resistance_ohm_per_m',
                     'length_m', 'reference_ohms'), where='quasistatic line')
        if data['schema'] != 'sipi.quasistatic-line/1':
            raise ValueError('unsupported quasistatic-line schema')
        section = _section(data['section'])
        data['section'] = section.to_dict()
        data['frequency_hz'] = _frequencies(data['frequency_hz']).tolist()
        data['resistance_ohm_per_m'] = _scalar('resistance', data['resistance_ohm_per_m'], zero=True)
        data['length_m'] = _scalar('length', data['length_m'], zero=True)
        data['reference_ohms'] = _scalar('z_ref', data['reference_ohms'])
        self._json = json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)

    @classmethod
    def from_dict(cls, data):
        result = cls.__new__(cls)
        result._assign(data)
        return result

    @classmethod
    def loads(cls, text):
        def reject(value):
            raise ValueError('nonfinite JSON number: '+value)
        return cls.from_dict(json.loads(text, object_pairs_hook=_unique_object, parse_constant=reject))

    def dumps(self):
        return self._json

    def to_dict(self):
        return json.loads(self._json)

    @property
    def section(self):
        return _section(self.to_dict()['section'])

    def analyze(self):
        data = self.to_dict()
        line = self.section.analyze()
        network = quasistatic_network(line, data['frequency_hz'],
            R=np.eye(len(line.names))*data['resistance_ohm_per_m'],
            length=data['length_m'], z_ref=data['reference_ohms'])
        return QuasistaticLineResult(line, network, self.dumps())
