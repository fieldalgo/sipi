# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved lines whose surface currents use the auxiliary recovered P1 method.

``sipi.recovered-transmission-line/1`` wraps a canonical transmission-line
document and replaces only its surface-current factors by
``recovered_surface_current_factors`` on the same saved mesh. The P1 basis and
C0 are those of the nested line, so C, G and external L are unchanged; R and
internal L use the recovered factors with the same surface-impedance laws.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from numbers import Real
from types import MappingProxyType
import json

import numpy as np

from .boundary_conductor import _boundary_from_factors
from .conductor import ConductorLoss
from .dielectric import dielectric_from_dict, _material_samples, _dispersive_from_mesh
from .document import CrossSectionDocument, _keys, _unique_object
from .line_model import TransmissionLineDocument, TransmissionLineResult, _conductor
from .network import rlgc_network
from .recovered_conductor import RecoveredCurrentFactors, recovered_surface_current_factors

__all__ = ['RecoveredTransmissionLineDocument', 'RecoveredTransmissionLineResult']

_SCHEMA = 'sipi.recovered-transmission-line/1'
_KINDS = ('surface', 'surface-boundaries')
_FLUX_LIMIT = .05


@dataclass(frozen=True)
class RecoveredTransmissionLineResult(TransmissionLineResult):
    """Matched RLGC with the recovered current factors and their controls."""
    current_factors: RecoveredCurrentFactors
    recovery_settings: Mapping

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, 'recovery_settings', MappingProxyType(dict(self.recovery_settings)))

    def current_record(self):
        """JSON-ready method, controls and diagnostics of the current solve."""
        factors = self.current_factors
        diagnostics = {key: (list(value) if isinstance(value, tuple) else value)
                       for key, value in factors.diagnostics.items()}
        return dict(kind='p1-volume-shape-derivative', settings=dict(self.recovery_settings),
                    diagnostics=diagnostics,
                    surface_current_factors_per_m=factors.parts.tolist(),
                    current_integrals=factors.current_integrals.tolist())


def _fraction(value):
    if (isinstance(value, (bool, np.bool_)) or not isinstance(value, Real)
            or not 0 < float(value) < .5):
        raise ValueError('support_fraction must be a real number in (0, 0.5)')
    return float(value)


class RecoveredTransmissionLineDocument:
    """Strict line with recovered P1 surface currents on its saved mesh.

    The nested line is transmission-line/1 through /7 with a ``surface`` or
    ``surface-boundaries`` conductor. ``perfect`` conductors carry no surface
    loss and ``surface-faces`` metals need per-face factors the recovery does
    not provide; both are refused. ``recovery`` holds ``support_fraction`` in
    (0, 0.5), written out in full. Geometry the recovery has not been
    characterised for is refused in analyze() with the reason, and a
    boundary-gradient flux error above 5% asks for refinement as the P1 line
    does. There is no fallback to another current method.
    """
    def __init__(self, line, *, support_fraction=0.4):
        if not isinstance(line, TransmissionLineDocument):
            raise TypeError('line must be a TransmissionLineDocument')
        self._data = self._validate(dict(schema=_SCHEMA, line=line.to_dict(),
                                         recovery=dict(support_fraction=support_fraction)))

    @staticmethod
    def _validate(data):
        if not isinstance(data, dict):
            raise ValueError('recovered transmission line must be an object')
        _keys(data, ('schema', 'line', 'recovery'), where='recovered transmission line')
        if data['schema'] != _SCHEMA:
            raise ValueError('unsupported recovered-transmission-line schema')
        if (not isinstance(data['line'], dict) or data['line'].get('schema') not in
                tuple(f'sipi.transmission-line/{v}' for v in range(1, 8))):
            raise ValueError('recovered line requires a nested transmission-line/1 through /7')
        line = TransmissionLineDocument.from_dict(data['line']).to_dict()
        kind = line['conductor']['kind']
        if kind not in _KINDS:
            raise ValueError(f'recovered currents require surface or surface-boundaries conductors, not {kind}; '
                             "use current_method 'volume-p1' for it")
        if not isinstance(data['recovery'], dict):
            raise ValueError('recovery controls must be an object')
        _keys(data['recovery'], ('support_fraction',), where='recovery controls')
        return dict(schema=_SCHEMA, line=line,
                    recovery=dict(support_fraction=_fraction(data['recovery']['support_fraction'])))

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
    def recovery_options(self):
        return dict(self._data['recovery'])

    def analyze(self):
        """Mesh once, recover the surface currents and propagate the line."""
        data = self.to_dict()
        line = data['line']
        doc = CrossSectionDocument.from_dict(line['cross_section'])
        section = doc.section
        materials = {k: dielectric_from_dict(v) for k, v in line['materials'].items()}
        f, samples = _material_samples(section, line['frequency_hz'], materials)
        _, metal_samples = _conductor(line['conductor'], section, f, line['schema'])
        meshed = section.mesh(**doc.mesh_options)
        factors = recovered_surface_current_factors(meshed.mesh, meshed.signals, meshed.ground,
                                                    **data['recovery'])
        flux = factors.diagnostics['gradient_current_error']
        if flux > _FLUX_LIMIT:
            raise ValueError(f'surface-current flux error {flux:.3%} exceeds 5%; refine the mesh')
        if line['conductor']['kind'] == 'surface-boundaries':
            names, f, metals, depth, correction, zs = metal_samples
            if factors.names != names:
                raise ValueError('meshing changed the signal boundary order')
            loss = _boundary_from_factors(factors, f, metals, depth, correction, zs)
        else:
            f, depth, correction, zs = metal_samples
            resistance = zs.real[:, None, None]*factors.total
            internal = (zs.imag/f/(2*np.pi))[:, None, None]*factors.total
            loss = ConductorLoss(f, resistance, internal, depth, correction, factors)
        dielectric = _dispersive_from_mesh(meshed, f, samples, c0=factors.C0)
        network = rlgc_network(f, R=loss.R, L=dielectric.L+loss.L_internal, G=dielectric.G, C=dielectric.C,
                               length=line['length_m'], z_ref=line['reference_ohms'], names=dielectric.names)
        return RecoveredTransmissionLineResult(dielectric, loss, network, self.dumps(), doc.mesh_options,
                                               factors, data['recovery'])
