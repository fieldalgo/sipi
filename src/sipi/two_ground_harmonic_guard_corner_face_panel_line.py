# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit saved corner-power face currents and matched dielectric line fields."""
from dataclasses import dataclass
import json

from ._two_ground_mesh_reuse import _reuse_mesh
from .document import CrossSectionDocument, _keys
from .dielectric import (dielectric_from_dict, dielectric_to_dict,
    _material_samples, _dispersive_from_mesh)
from .face_conductor import _face_samples
from .fem_shape_line import _mesh_record
from .network import _frequencies, _scalar, rlgc_network
from .shape_face_panel_line import _metals
from .two_ground_face_conductor import TwoGroundFaceCurrentFactors
from .two_ground_harmonic_guard_corner_conductor import (_arguments,
    two_ground_harmonic_guard_corner_conductor_loss_by_face)
from .two_ground_face_panel_line import (TwoGroundFacePanelTransmissionLineDocument,
    TwoGroundFacePanelTransmissionLineResult)
from .two_ground_panel_line import (TwoGroundPanelLineError,
    two_ground_current_record)

__all__ = ['TwoGroundHarmonicGuardCornerFacePanelTransmissionLineDocument',
    'TwoGroundHarmonicGuardCornerFacePanelTransmissionLineResult', 'TwoGroundHarmonicGuardCornerFacePanelLineError',
    'two_ground_harmonic_guard_corner_face_current_record']
_SCHEMA = 'sipi.two-ground-harmonic-guard-corner-face-panel-transmission-line/1'


def two_ground_harmonic_guard_corner_face_current_record(factors, settings):
    """Detached SI face records with the original whole-current evidence."""
    whole = two_ground_current_record(factors.base, settings)
    whole['kind'] = 'two-ground-harmonic-corner-fixed-guard'
    return dict(kind='two-ground-harmonic-corner-faces-fixed-guard', settings=dict(settings),
        names=list(factors.names), labels=list(factors.labels),
        vacuum_capacitance_f_per_m=factors.C0.tolist(),
        surface_current_factors_per_m=factors.parts.tolist(),
        current_integrals=factors.current_integrals.tolist(),
        whole_current=whole)


class TwoGroundHarmonicGuardCornerFacePanelLineError(TwoGroundPanelLineError):
    """Retain exact input, completed face work and actual dielectric mesh."""
    def __init__(self, cause, *, stage, input_json, factors, settings, mesh_observation):
        ValueError.__init__(self, str(cause))
        self.stage = stage
        self.cause_type = type(cause).__name__
        self.input_json = input_json
        self.current_factors = factors
        self._record = json.dumps(dict(type=type(self).__name__, message=str(self),
            stage=stage, cause_type=self.cause_type, input=json.loads(input_json),
            current_solver=None if factors is None else two_ground_harmonic_guard_corner_face_current_record(factors, settings),
            dielectric_mesh=mesh_observation), allow_nan=False)


@dataclass(frozen=True)
class TwoGroundHarmonicGuardCornerFacePanelTransmissionLineResult(TwoGroundFacePanelTransmissionLineResult):
    """Same-geometry RLGC with immutable face controls and mesh identity."""
    current_factors: TwoGroundFaceCurrentFactors

    def __post_init__(self):
        if not isinstance(self.current_factors, TwoGroundFaceCurrentFactors):
            raise TypeError('current_factors must retain two-ground face currents')
        super().__post_init__()

    def current_record(self):
        return two_ground_harmonic_guard_corner_face_current_record(self.current_factors, self.panel_settings)


class TwoGroundHarmonicGuardCornerFacePanelTransmissionLineDocument(TwoGroundFacePanelTransmissionLineDocument):
    """Explicit SI input for separate trace-face and two-foil surface laws.

    Exactly two finite rectangular/tapered signals and one fixed-potential guard
    are admitted. Both planes and the guard retain separate metal laws. The separate schema never reinterprets existing panel inputs.
    Ground modes record the actual fine count, compared with half that count.
    Normalization performs local material, geometry and resource admission
    without a field solve or an optional shared-capability import.
    """
    def __init__(self, cross_section, frequency, *, materials, conductors, reference,
            ground_thickness, length, z_ref=50., panels_per_edge=32,
            ground_modes=256, interpolation_degree=24):
        if not isinstance(cross_section, CrossSectionDocument):
            raise TypeError('cross_section must be a CrossSectionDocument')
        if not isinstance(materials, dict):
            raise ValueError('materials must be an object')
        self._data = self._validate(dict(schema=_SCHEMA, cross_section=cross_section.to_dict(),
            frequency_hz=_frequencies(frequency).tolist(),
            materials={name:dielectric_to_dict(value) for name,value in materials.items()},
            conductors=conductors, reference=reference, ground_thickness_m=ground_thickness,
            length_m=length, reference_ohms=z_ref, panel=dict(panels_per_edge=panels_per_edge,
                ground_modes=ground_modes, interpolation_degree=interpolation_degree)))

    @staticmethod
    def _validate(data):
        _keys(data, ('schema', 'cross_section', 'frequency_hz', 'materials', 'conductors',
            'reference', 'ground_thickness_m', 'length_m', 'reference_ohms', 'panel'),
            where='two-ground corner face panel line')
        if data['schema'] != _SCHEMA:
            raise ValueError('unsupported two-ground-harmonic-guard-corner-face-panel-transmission-line schema')
        cross = CrossSectionDocument.from_dict(data['cross_section'])
        section = cross.section
        if not isinstance(data['materials'], dict):
            raise ValueError('materials must be an object')
        materials = {name:dielectric_from_dict(value) for name,value in data['materials'].items()}
        f, _ = _material_samples(section, data['frequency_hz'], materials)
        conductors, reference, records, ref_record = _metals(data)
        thickness = _scalar('ground_thickness_m', data['ground_thickness_m'])
        _keys(data['panel'], ('panels_per_edge', 'ground_modes', 'interpolation_degree'),
              where='panel controls')
        _, count, modes, degree, _ = _arguments(section, **data['panel'])
        _face_samples(section, f, conductors, reference, thickness)
        if 'ground' in (t.name for t in section.traces):
            raise ValueError("'ground' is reserved by the shared capacitance API")
        return dict(schema=_SCHEMA, cross_section=cross.to_dict(), frequency_hz=f.tolist(),
            materials={name:dielectric_to_dict(value) for name,value in materials.items()},
            conductors=records, reference=ref_record, ground_thickness_m=thickness,
            length_m=_scalar('length_m', data['length_m'], zero=True),
            reference_ohms=_scalar('reference_ohms', data['reference_ohms']),
            panel=dict(panels_per_edge=count, ground_modes=modes, interpolation_degree=degree))

    def analyze(self):
        data = self.to_dict()
        cross = self.cross_section
        section, options = cross.section, self.current_options
        factors, mesh_observation, stage = None, None, 'material-admission'
        try:
            materials = {name:dielectric_from_dict(value) for name,value in data['materials'].items()}
            f, samples = _material_samples(section, data['frequency_hz'], materials)
            stage = 'conductor-admission'
            conductors, reference, _, _ = _metals(data)
            _arguments(section, **options)
            _face_samples(section, f, conductors, reference, data['ground_thickness_m'])
            stage = 'current'
            loss = two_ground_harmonic_guard_corner_conductor_loss_by_face(section, f, conductors=conductors,
                reference=reference, ground_thickness=data['ground_thickness_m'], **options)
            factors = loss.factors
            stage = 'mesh'
            meshed = _reuse_mesh(cross, section)
            mesh_observation = _mesh_record(meshed)
            if tuple(meshed.signals) != factors.names:
                raise ValueError('dielectric mesh changed two-ground face signal order')
            stage = 'dielectric'
            dielectric = _dispersive_from_mesh(meshed, f, samples, c0=factors.C0)
            stage = 'network'
            network = rlgc_network(f, R=loss.R, L=dielectric.L+loss.L_internal,
                G=dielectric.G, C=dielectric.C, length=data['length_m'],
                z_ref=data['reference_ohms'], names=dielectric.names)
            return TwoGroundHarmonicGuardCornerFacePanelTransmissionLineResult(dielectric, loss, network,
                self.dumps(), cross.mesh_options, factors, options,
                json.dumps(mesh_observation, sort_keys=True))
        except Exception as exc:
            raise TwoGroundHarmonicGuardCornerFacePanelLineError(exc, stage=stage, input_json=self.dumps(),
                factors=factors, settings=options, mesh_observation=mesh_observation) from exc
