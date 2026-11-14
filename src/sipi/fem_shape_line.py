# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved whole-boundary FEM shape currents and same-mesh dielectric fields."""
from dataclasses import dataclass
import hashlib
import json
import numpy as np

from .document import CrossSectionDocument, _keys, _unique_object
from .dielectric import dielectric_from_dict, dielectric_to_dict, _material_samples, _dispersive_from_mesh
from .line_model import TransmissionLineResult, _surface_metal
from .boundary_conductor import _boundary_samples, _boundary_from_factors
from .fem_shape_conductor import FEMShapeCurrentFactors, FEMShapeCurrentError, fem_shape_current_factors
from .network import _frequencies, _scalar, rlgc_network

__all__ = ['FEMShapeTransmissionLineDocument', 'FEMShapeTransmissionLineResult', 'FEMShapeLineError']
_SCHEMA = 'sipi.fem-shape-transmission-line/1'


def _safe(value):
    """Explicit nonfinite markers are for failed observations, never results."""
    if isinstance(value, np.ndarray): return _safe(value.tolist())
    if isinstance(value, dict): return {k: _safe(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)): return [_safe(v) for v in value]
    if isinstance(value, (float, np.floating)) and not np.isfinite(value):
        return 'nan' if np.isnan(value) else ('+inf' if value > 0 else '-inf')
    return value


def _sample(sample):
    return dict(extension=sample.extension, group=sample.group, level=sample.level,
        sign=sample.sign, displacement_m=sample.displacement_m,
        capacitance_per_permittivity=sample.capacitance_per_permittivity.tolist())


def _gradient(base):
    return dict(names=list(base.names), vacuum_capacitance_f_per_m=base.C0.tolist(),
        surface_current_factors_per_m=base.parts.tolist(), current_integrals=base.current_integrals.tolist(),
        current_flux_error=base.current_error)


def fem_shape_current_record(factors, mesh_observation):
    return dict(kind='fem-geometry-energy', mesh=mesh_observation, names=list(factors.names),
        vacuum_capacitance_f_per_m=factors.C0.tolist(), surface_current_factors_per_m=factors.parts.tolist(),
        extension_factors_per_m=factors.extension_parts.tolist(),
        finite_difference_factors_per_m=factors.finite_difference_parts.tolist(),
        step_m=factors.step_m, samples=[_sample(s) for s in factors.samples],
        diagnostics=_safe(dict(factors.diagnostics)), original_gradient=_gradient(factors.base))


def _mesh_record(field):
    def digest(array, dtype):
        return hashlib.sha256(np.asarray(array, dtype=dtype).tobytes(order='C')).hexdigest()
    return dict(nodes=field.mesh.num_nodes, triangles=field.mesh.num_triangles,
        nodes_float64_le_sha256=digest(field.mesh.nodes, '<f8'),
        triangles_int64_le_sha256=digest(field.mesh.triangles, '<i8'),
        signal_nodes=[dict(name=name, int64_le_sha256=digest(nodes, '<i8')) for name, nodes in field.signals.items()],
        ground_int64_le_sha256=digest(field.ground, '<i8'))


class FEMShapeLineError(ValueError):
    """Staged failure retaining complete currents or typed partial observations."""
    def __init__(self, cause, *, stage, input_json, factors, mesh_observation):
        super().__init__(str(cause)); self.stage = stage; self.cause_type = type(cause).__name__
        self.current_factors = factors; self.input_json = input_json
        partial = None
        if isinstance(cause, FEMShapeCurrentError):
            partial = dict(stage=cause.stage, cause_type=type(cause.__cause__).__name__ if cause.__cause__ else type(cause).__name__,
                original_gradient=None if cause.base is None else _gradient(cause.base),
                extension_factors_per_m=_safe(cause.extension_parts),
                finite_difference_factors_per_m=_safe(cause.finite_difference_parts),
                samples=[_sample(s) for s in cause.samples], failed_request=_safe(cause.request),
                diagnostics=_safe(dict(cause.diagnostics)), nonfinite_encoding='nan/+inf/-inf strings in failed observations only')
        self._record = json.dumps(dict(type=type(self).__name__, message=str(self), stage=stage,
            cause_type=self.cause_type, input=json.loads(input_json), mesh=mesh_observation,
            current_solver=None if factors is None else fem_shape_current_record(factors, mesh_observation),
            partial_current=partial), allow_nan=False)

    def to_dict(self): return json.loads(self._record)


@dataclass(frozen=True)
class FEMShapeTransmissionLineResult(TransmissionLineResult):
    current_factors: FEMShapeCurrentFactors
    mesh_json: str

    @property
    def mesh_observation(self): return json.loads(self.mesh_json)

    def current_record(self): return fem_shape_current_record(self.current_factors, self.mesh_observation)


def _metals(data):
    if not isinstance(data['conductors'], dict):
        raise ValueError('conductors must be keyed by signal name')
    values = {name: _surface_metal(value, 'sipi.transmission-line/7') for name, value in data['conductors'].items()}
    reference, ref_record = _surface_metal(data['reference'], 'sipi.transmission-line/7')
    return {name: pair[0] for name, pair in values.items()}, reference, {name: pair[1] for name, pair in values.items()}, ref_record


class FEMShapeTransmissionLineDocument:
    """Strict opt-in saved line, sharing one mesh for vacuum and dielectric.

    One explicit whole-boundary metal per signal and one common reference
    metal. The current method retains its strict derivative/PSD gates and the
    original gradient flux gate. Normalization performs no fields or meshing.
    """
    def __init__(self, cross_section, frequency, *, materials, conductors, reference,
                 ground_thickness, length, z_ref=50.):
        if not isinstance(cross_section, CrossSectionDocument):
            raise TypeError('cross_section must be a CrossSectionDocument')
        self._data = self._validate(dict(schema=_SCHEMA, cross_section=cross_section.to_dict(),
            frequency_hz=_frequencies(frequency).tolist(),
            materials={name: dielectric_to_dict(value) for name, value in materials.items()},
            conductors=conductors, reference=reference, ground_thickness_m=ground_thickness,
            length_m=length, reference_ohms=z_ref))

    @staticmethod
    def _validate(data):
        _keys(data, ('schema','cross_section','frequency_hz','materials','conductors','reference',
                    'ground_thickness_m','length_m','reference_ohms'), where='FEM shape line')
        if data['schema'] != _SCHEMA:
            raise ValueError('unsupported fem-shape-transmission-line schema')
        cross = CrossSectionDocument.from_dict(data['cross_section']); section = cross.section
        if not isinstance(data['materials'], dict): raise ValueError('materials must be an object')
        materials = {name: dielectric_from_dict(value) for name, value in data['materials'].items()}
        f, _ = _material_samples(section, data['frequency_hz'], materials)
        conductors, reference, records, ref_record = _metals(data)
        thickness = _scalar('ground_thickness_m', data['ground_thickness_m'])
        names, *_ = _boundary_samples(section, f, conductors, reference, thickness)
        if not 1 <= len(names) <= 4: raise ValueError('FEM shape line needs 1..4 signals')
        if 'ground' in names: raise ValueError("'ground' is reserved by the shared capacitance API")
        return dict(schema=_SCHEMA, cross_section=cross.to_dict(), frequency_hz=f.tolist(),
            materials={name: dielectric_to_dict(value) for name, value in materials.items()},
            conductors=records, reference=ref_record, ground_thickness_m=thickness,
            length_m=_scalar('length_m', data['length_m'], zero=True),
            reference_ohms=_scalar('reference_ohms', data['reference_ohms']))

    @classmethod
    def from_dict(cls, data):
        result = cls.__new__(cls); result._data = cls._validate(data); return result

    @classmethod
    def loads(cls, text):
        def reject(value): raise ValueError('nonfinite JSON number: '+value)
        return cls.from_dict(json.loads(text, object_pairs_hook=_unique_object, parse_constant=reject))

    def dumps(self): return json.dumps(self._data, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
    def to_dict(self): return json.loads(self.dumps())
    @property
    def cross_section(self): return CrossSectionDocument.from_dict(self.to_dict()['cross_section'])

    def analyze(self):
        data = self.to_dict(); cross = self.cross_section; section = cross.section
        factors = None; mesh_observation = None; stage = 'material-admission'
        try:
            materials = {name: dielectric_from_dict(value) for name, value in data['materials'].items()}
            f, samples = _material_samples(section, data['frequency_hz'], materials)
            stage = 'conductor-admission'; conductors, reference, _, _ = _metals(data)
            names, _, metals, depth, correction, zs = _boundary_samples(section, f, conductors, reference, data['ground_thickness_m'])
            stage = 'mesh'; field = section.mesh(**cross.mesh_options); mesh_observation = _mesh_record(field)
            if tuple(field.signals) != names: raise ValueError('mesh changed signal order')
            stage = 'current'; factors = fem_shape_current_factors(field.mesh, field.signals, field.ground)
            if factors.names != names: raise ValueError('current solve changed signal order')
            stage = 'conductor'; loss = _boundary_from_factors(factors, f, metals, depth, correction, zs)
            stage = 'dielectric'; dielectric = _dispersive_from_mesh(field, f, samples, c0=factors.C0)
            stage = 'network'; network = rlgc_network(f, R=loss.R, L=dielectric.L+loss.L_internal,
                G=dielectric.G, C=dielectric.C, length=data['length_m'], z_ref=data['reference_ohms'], names=names)
            return FEMShapeTransmissionLineResult(dielectric, loss, network, self.dumps(), cross.mesh_options,
                factors, json.dumps(mesh_observation, allow_nan=False))
        except Exception as exc:
            raise FEMShapeLineError(exc, stage=stage, input_json=self.dumps(), factors=factors,
                mesh_observation=mesh_observation) from exc
