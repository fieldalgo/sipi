# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved two-ground currents with matched dielectric fields and RLGC."""
from dataclasses import dataclass
import json

from .document import CrossSectionDocument, _keys, _unique_object
from .dielectric import dielectric_from_dict, dielectric_to_dict, _material_samples, _dispersive_from_mesh
from .fem_shape_line import _mesh_record
from .network import _frequencies, _scalar, rlgc_network
from .panel_line import PanelTransmissionLineResult
from .shape_reference_panel_line import _metals
from .two_ground_conductor import _current_arguments, _loss_samples, two_ground_conductor_loss

__all__ = ['TwoGroundPanelTransmissionLineDocument', 'TwoGroundPanelTransmissionLineResult',
           'TwoGroundPanelLineError', 'two_ground_current_record']
_SCHEMA = 'sipi.two-ground-panel-transmission-line/1'


def two_ground_current_record(factors, settings):
    """Detached SI record retaining all individual reference-surface factors."""
    return dict(kind='two-ground-rectangle-panels', settings=dict(settings),
        names=list(factors.names), ground_trace_names=list(factors.ground_trace_names),
        vacuum_capacitance_f_per_m=factors.C0.tolist(),
        surface_current_factors_per_m=factors.parts.tolist(),
        current_integrals=factors.current_integrals.tolist(),
        boundary_labels=list(factors.boundary_labels),
        boundary_surface_current_factors_per_m=factors.boundary_parts.tolist(),
        boundary_current_integrals=factors.boundary_integrals.tolist(),
        diagnostics=dict(factors.diagnostics))


class TwoGroundPanelLineError(ValueError):
    """Preserve completed current work, exact input and the failing stage."""
    def __init__(self, cause, *, stage, input_json, factors, settings, mesh_observation):
        super().__init__(str(cause))
        self.stage = stage
        self.cause_type = type(cause).__name__
        self.input_json = input_json
        self.current_factors = factors
        self._record = json.dumps(dict(type=type(self).__name__, message=str(self),
            stage=stage, cause_type=self.cause_type, input=json.loads(input_json),
            current_solver=None if factors is None else two_ground_current_record(factors, settings),
            dielectric_mesh=mesh_observation), allow_nan=False)

    def to_dict(self):
        return json.loads(self._record)


@dataclass(frozen=True)
class TwoGroundPanelTransmissionLineResult(PanelTransmissionLineResult):
    """Matched RLGC with immutable current controls and actual mesh identity."""
    dielectric_mesh_json: str

    def current_record(self):
        return two_ground_current_record(self.current_factors, self.panel_settings)

    def mesh_record(self):
        return json.loads(self.dielectric_mesh_json)


class TwoGroundPanelTransmissionLineDocument:
    """Strict SI input; two grounded planes and finite convex conductors.

    Normalization is field-free and does not import the optional shared solver.
    Whole signal/reference surface laws, dielectric samples, resource limits
    and skin/core admission are checked before analyze() requests a field.
    Generic shared numerical admission remains an analyze-time check.
    """
    def __init__(self, cross_section, frequency, *, materials, conductors, reference,
                 ground_thickness, length, z_ref=50., panels_per_edge=32,
                 ground_modes=128, interpolation_degree=12):
        if not isinstance(cross_section, CrossSectionDocument):
            raise TypeError('cross_section must be a CrossSectionDocument')
        if not isinstance(materials, dict):
            raise ValueError('materials must be an object')
        self._data = self._validate(dict(schema=_SCHEMA, cross_section=cross_section.to_dict(),
            frequency_hz=_frequencies(frequency).tolist(),
            materials={name: dielectric_to_dict(value) for name, value in materials.items()},
            conductors=conductors, reference=reference, ground_thickness_m=ground_thickness,
            length_m=length, reference_ohms=z_ref, panel=dict(panels_per_edge=panels_per_edge,
                ground_modes=ground_modes, interpolation_degree=interpolation_degree)))

    @staticmethod
    def _validate(data):
        _keys(data, ('schema', 'cross_section', 'frequency_hz', 'materials', 'conductors',
                    'reference', 'ground_thickness_m', 'length_m', 'reference_ohms', 'panel'),
              where='two-ground panel line')
        if data['schema'] != _SCHEMA:
            raise ValueError('unsupported two-ground-panel-transmission-line schema')
        cross = CrossSectionDocument.from_dict(data['cross_section'])
        section = cross.section
        if not isinstance(data['materials'], dict):
            raise ValueError('materials must be an object')
        materials = {name: dielectric_from_dict(value) for name, value in data['materials'].items()}
        f, _ = _material_samples(section, data['frequency_hz'], materials)
        conductors, reference, records, ref_record = _metals(data)
        thickness = _scalar('ground_thickness_m', data['ground_thickness_m'])
        _loss_samples(section, f, conductors, reference, thickness)
        _keys(data['panel'], ('panels_per_edge', 'ground_modes', 'interpolation_degree'),
              where='panel controls')
        _, count, modes, degree, _ = _current_arguments(section, **data['panel'])
        if 'ground' in (t.name for t in section.traces):
            raise ValueError("'ground' is reserved by the shared capacitance API")
        return dict(schema=_SCHEMA, cross_section=cross.to_dict(), frequency_hz=f.tolist(),
            materials={name: dielectric_to_dict(value) for name, value in materials.items()},
            conductors=records, reference=ref_record, ground_thickness_m=thickness,
            length_m=_scalar('length_m', data['length_m'], zero=True),
            reference_ohms=_scalar('reference_ohms', data['reference_ohms']),
            panel=dict(panels_per_edge=count, ground_modes=modes, interpolation_degree=degree))

    @classmethod
    def from_dict(cls, data):
        result = cls.__new__(cls)
        result._data = cls._validate(data)
        return result

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
    def cross_section(self):
        return CrossSectionDocument.from_dict(self.to_dict()['cross_section'])

    @property
    def current_options(self):
        return dict(self._data['panel'])

    def analyze(self):
        data = self.to_dict()
        cross = self.cross_section
        section, options = cross.section, self.current_options
        factors, mesh_observation, stage = None, None, 'material-admission'
        try:
            materials = {name: dielectric_from_dict(value) for name, value in data['materials'].items()}
            f, samples = _material_samples(section, data['frequency_hz'], materials)
            stage = 'conductor-admission'
            conductors, reference, _, _ = _metals(data)
            _loss_samples(section, f, conductors, reference, data['ground_thickness_m'])
            stage = 'current'
            loss = two_ground_conductor_loss(section, f, conductors=conductors, reference=reference,
                ground_thickness=data['ground_thickness_m'], **options)
            factors = loss.factors
            stage = 'mesh'
            meshed = section.mesh(**cross.mesh_options)
            mesh_observation = _mesh_record(meshed)
            if tuple(meshed.signals) != factors.names:
                raise ValueError('dielectric mesh changed two-ground signal order')
            stage = 'dielectric'
            dielectric = _dispersive_from_mesh(meshed, f, samples, c0=factors.C0)
            stage = 'network'
            network = rlgc_network(f, R=loss.R, L=dielectric.L+loss.L_internal,
                G=dielectric.G, C=dielectric.C, length=data['length_m'],
                z_ref=data['reference_ohms'], names=dielectric.names)
            return TwoGroundPanelTransmissionLineResult(dielectric, loss, network, self.dumps(),
                cross.mesh_options, factors, options, json.dumps(mesh_observation, sort_keys=True))
        except Exception as exc:
            raise TwoGroundPanelLineError(exc, stage=stage, input_json=self.dumps(), factors=factors,
                settings=options, mesh_observation=mesh_observation) from exc
