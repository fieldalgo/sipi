# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit saved capacitance-shape currents with matched dielectric fields."""
from dataclasses import dataclass
import json
import numpy as np

from .document import CrossSectionDocument, _keys, _unique_object
from .panel_line import PanelTransmissionLineDocument, PanelTransmissionLineResult
from .panel_shape_conductor import (panel_shape_current_factors,
    panel_shape_conductor_loss_by_boundary, PanelShapeCurrentError, _prepare)
from .line_model import _conductor
from .dielectric import dielectric_from_dict, _material_samples, _dispersive_from_mesh
from .network import rlgc_network

__all__ = ['ShapePanelTransmissionLineDocument', 'ShapePanelTransmissionLineResult',
           'ShapePanelLineError']


def _sample_record(sample):
    return dict(stage=sample.request.stage, request=sample.request.arguments(),
                capacitance_per_permittivity=sample.capacitance_per_permittivity.tolist(),
                diagnostics=dict(sample.diagnostics))


def shape_current_record(factors, settings):
    """SI current record, including every exact finite-difference request."""
    return dict(kind='grounded-rectangle-capacitance-shape', settings=dict(settings),
        ground_trace_names=list(factors.ground_trace_names),
        vacuum_capacitance_f_per_m=factors.C0.tolist(),
        surface_current_factors_per_m=factors.parts.tolist(),
        current_integrals=factors.current_integrals.tolist(), diagnostics=dict(factors.diagnostics),
        step_m=factors.step_m, step_factors_per_m=factors.step_parts.tolist(),
        boundary_step_factors_per_m=factors.boundary_step_parts.tolist(),
        samples=[_sample_record(s) for s in factors.samples])


class ShapePanelLineError(ValueError):
    """A staged line failure retaining complete current work or partial requests."""
    def __init__(self, cause, *, stage, input_json, factors, settings):
        super().__init__(str(cause))
        self.stage = stage
        self.cause_type = type(cause).__name__
        self.input_json = input_json
        self.current_factors = factors
        current = None if factors is None else shape_current_record(factors, settings)
        partial = None
        if isinstance(cause, PanelShapeCurrentError):
            partial = dict(cause_type=type(cause.__cause__).__name__ if cause.__cause__ is not None else type(cause).__name__,
                samples=[_sample_record(s) for s in cause.samples],
                failed_request=None if cause.request is None else dict(
                    stage=cause.request.stage, request=cause.request.arguments()),
                step_factors_per_m=None if cause.step_parts is None else cause.step_parts.tolist(),
                boundary_step_factors_per_m=(None if cause.boundary_step_parts is None
                                            else cause.boundary_step_parts.tolist()))
        self._record = json.dumps(dict(type=type(self).__name__, message=str(self),
            stage=stage, cause_type=self.cause_type, input=json.loads(input_json),
            current_solver=current, partial_current=partial), allow_nan=False)

    def to_dict(self):
        return json.loads(self._record)


@dataclass(frozen=True)
class ShapePanelTransmissionLineResult(PanelTransmissionLineResult):
    """Matched RLGC with explicit shape-current samples and saved controls."""


class ShapePanelTransmissionLineDocument:
    """Versioned opt-in wrapper of a panel-line/1 or panel-line/2 document.

    The nested panel line retains its own conductor and dielectric contract.
    Only current extraction changes explicitly. Normalization performs no field
    solves. Shared numerical admission remains part of analyze().
    """
    def __init__(self, line, *, step_fraction=1e-3):
        if not isinstance(line, PanelTransmissionLineDocument):
            raise TypeError('line must be a PanelTransmissionLineDocument')
        self._data = self._validate(dict(schema='sipi.shape-panel-transmission-line/1',
                                        line=line.to_dict(), step_fraction=step_fraction))

    @staticmethod
    def _validate(data):
        _keys(data, ('schema', 'line', 'step_fraction'), where='shape panel line')
        if data['schema'] != 'sipi.shape-panel-transmission-line/1':
            raise ValueError('unsupported shape-panel-transmission-line schema')
        panel = PanelTransmissionLineDocument.from_dict(data['line'])
        line = panel.line
        _prepare(line.cross_section.section, step_fraction=data['step_fraction'], **panel.panel_options)
        return dict(schema=data['schema'], line=panel.to_dict(), step_fraction=float(data['step_fraction']))

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
        return PanelTransmissionLineDocument.from_dict(self.to_dict()['line'])

    @property
    def current_options(self):
        return dict(self.line.panel_options, step_fraction=self._data['step_fraction'])

    def analyze(self):
        data = self.to_dict()
        line = data['line']['line']
        doc = CrossSectionDocument.from_dict(line['cross_section'])
        section = doc.section
        options = self.current_options
        factors = None
        stage = 'material-admission'
        try:
            materials = {k: dielectric_from_dict(v) for k, v in line['materials'].items()}
            f, samples = _material_samples(section, line['frequency_hz'], materials)
            stage = 'conductor-admission'
            _, metal_samples = _conductor(line['conductor'], section, f, line['schema'])
            stage = 'current'
            if metal_samples is None:
                loss = None
                factors = panel_shape_current_factors(section, **options)
            else:
                names, _, metals, _, _, _ = metal_samples
                loss = panel_shape_conductor_loss_by_boundary(section, f,
                    conductors=dict(zip(names, metals[:-1])), reference=metals[-1],
                    ground_thickness=line['conductor']['ground_thickness'], **options)
                factors = loss.factors
            stage = 'mesh'
            meshed = section.mesh(**doc.mesh_options)
            if tuple(meshed.signals) != factors.names:
                raise ValueError('dielectric mesh changed shape-current signal order')
            stage = 'dielectric'
            dielectric = _dispersive_from_mesh(meshed, f, samples, c0=factors.C0)
            R = np.zeros_like(dielectric.C) if loss is None else loss.R
            L = dielectric.L if loss is None else dielectric.L+loss.L_internal
            stage = 'network'
            network = rlgc_network(f, R=R, L=L, G=dielectric.G, C=dielectric.C,
                length=line['length_m'], z_ref=line['reference_ohms'], names=dielectric.names)
            return ShapePanelTransmissionLineResult(dielectric, loss, network, self.dumps(),
                                                    doc.mesh_options, factors, options)
        except Exception as exc:
            raise ShapePanelLineError(exc, stage=stage, input_json=self.dumps(),
                                      factors=factors, settings=options) from exc
