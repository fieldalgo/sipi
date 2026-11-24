# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved panel-current line for sections with no ground plane (open box)."""
from dataclasses import dataclass
from types import MappingProxyType
from collections.abc import Mapping
import json

import numpy as np

from .document import CrossSectionDocument, _keys, _unique_object
from .line_model import TransmissionLineDocument, TransmissionLineResult, _conductor
from .open_panel_conductor import open_panel_surface_current_factors, open_panel_conductor_loss_by_boundary
from .panel_conductor import PanelCurrentFactors
from .dielectric import dielectric_from_dict, _material_samples, _dispersive_from_mesh
from .network import rlgc_network
from .sampling import _integer


__all__ = ['OpenPanelTransmissionLineDocument', 'OpenPanelTransmissionLineResult']

_SCHEMA = 'sipi.open-panel-transmission-line/1'


@dataclass(frozen=True)
class OpenPanelTransmissionLineResult(TransmissionLineResult):
    """Matched RLGC with retained open-box panel controls and the input snapshot."""
    current_factors: PanelCurrentFactors
    panel_settings: Mapping

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, 'panel_settings', MappingProxyType(dict(self.panel_settings)))


class OpenPanelTransmissionLineDocument:
    """Strict panel line for open bottom, top and sides with grounded traces.

    The nested line is transmission-line/1 through /7 with a perfect or
    surface-boundaries conductor; its section has no ground plane, so its
    grounded traces (CrossSection requires one) are the reference. Panel currents (galerkin.laplace_open_box) supply the
    vacuum capacitance and external L; the existing dielectric solver supplies
    C/G on one saved volume mesh. The two panel controls are required:
    panels_per_edge and interpolation_degree (there are no ground modes).
    Normalization performs no field solve.
    """
    def __init__(self, line, *, panels_per_edge=32, interpolation_degree=12):
        if not isinstance(line, TransmissionLineDocument):
            raise TypeError('line must be a TransmissionLineDocument')
        self._data = self._validate(dict(schema=_SCHEMA, line=line.to_dict(), panel=dict(
            panels_per_edge=panels_per_edge, interpolation_degree=interpolation_degree)))

    @staticmethod
    def _validate(data):
        if not isinstance(data, dict):
            raise ValueError('open panel transmission line must be an object')
        _keys(data, ('schema', 'line', 'panel'), where='open panel transmission line')
        if data['schema'] != _SCHEMA:
            raise ValueError('unsupported open-panel-transmission-line schema')
        if (not isinstance(data['line'], dict) or data['line'].get('schema') not in
                tuple(f'sipi.transmission-line/{v}' for v in range(1, 8))):
            raise ValueError('open panel line requires a nested transmission-line/1 through /7')
        line = TransmissionLineDocument.from_dict(data['line'])
        value = line.to_dict()
        section = line.cross_section.section
        if value['conductor']['kind'] not in ('perfect', 'surface-boundaries'):
            raise ValueError('open panel line requires perfect or surface-boundaries conductor')
        if (section.bottom, section.top, section.sides) != ('open', 'open', 'open'):
            raise ValueError('open panel line requires open bottom, top and sides')
        if any(t.thickness <= 0 for t in section.traces):
            raise ValueError('open panel line requires positive conductor thickness')
        if not isinstance(data['panel'], dict):
            raise ValueError('panel controls must be an object')
        _keys(data['panel'], ('panels_per_edge', 'interpolation_degree'), where='panel controls')
        opts = dict(panels_per_edge=_integer(data['panel']['panels_per_edge'], 1, 256),
                    interpolation_degree=_integer(data['panel']['interpolation_degree'], 10, 16))
        if opts['interpolation_degree'] not in (10, 12, 14, 16):
            raise ValueError('interpolation_degree must be 10, 12, 14 or 16')
        if len(section.traces) > 16 or sum(len(t.corners()) for t in section.traces)*opts['panels_per_edge'] > 2048:
            raise ValueError('open panel line exceeds shared conductor or panel count limit')
        return dict(schema=_SCHEMA, line=value, panel=opts)

    @classmethod
    def from_dict(cls, data):
        out = cls.__new__(cls)
        out._data = cls._validate(data)
        return out

    @classmethod
    def loads(cls, text):
        def reject(value):
            raise ValueError('nonfinite JSON number: '+value)
        return cls.from_dict(json.loads(text, object_pairs_hook=_unique_object, parse_constant=reject))

    def dumps(self):
        return json.dumps(self._data, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)

    def to_dict(self):
        return json.loads(self.dumps())

    @property
    def line(self):
        return TransmissionLineDocument.from_dict(self.to_dict()['line'])

    @property
    def panel_options(self):
        return dict(self._data['panel'])

    def analyze(self):
        data = self.to_dict()
        line = data['line']
        doc = CrossSectionDocument.from_dict(line['cross_section'])
        section = doc.section
        materials = {k: dielectric_from_dict(v) for k, v in line['materials'].items()}
        f, samples = _material_samples(section, line['frequency_hz'], materials)
        _, metal_samples = _conductor(line['conductor'], section, f, line['schema'])
        if metal_samples is None:
            loss = None
            factors = open_panel_surface_current_factors(section, **data['panel'])
        else:
            names, _, metals, _, _, _ = metal_samples
            loss = open_panel_conductor_loss_by_boundary(
                section, f, conductors=dict(zip(names, metals[:-1])), reference=metals[-1],
                ground_thickness=line['conductor']['ground_thickness'], **data['panel'])
            factors = loss.factors
        meshed = section.mesh(**doc.mesh_options)
        if tuple(meshed.signals) != factors.names:
            raise ValueError('dielectric mesh changed panel signal order')
        dielectric = _dispersive_from_mesh(meshed, f, samples, c0=factors.C0)
        R = np.zeros_like(dielectric.C) if loss is None else loss.R
        L = dielectric.L if loss is None else dielectric.L+loss.L_internal
        network = rlgc_network(f, R=R, L=L, G=dielectric.G, C=dielectric.C, length=line['length_m'],
                               z_ref=line['reference_ohms'], names=dielectric.names)
        return OpenPanelTransmissionLineResult(dielectric, loss, network, self.dumps(), doc.mesh_options,
                                               factors, data['panel'])
