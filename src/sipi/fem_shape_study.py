# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit checked FEM-current geometry/material samples and failure evidence."""
from dataclasses import dataclass
import json
import numpy as np

from .document import CrossSectionDocument, _keys, _unique_object
from .study import ImpedanceStudyDocument, _TEMPLATES, _parameters
from .sampling import _integer
from .impedance_material import _models, _sample_material
from .line_input import _source_study
from .line_study import LineQuantityStudy, LineQuantityStudyRow, _summary, _json
from .fem_shape_line import FEMShapeTransmissionLineDocument, FEMShapeLineError

__all__ = ['FEMShapeLineQuantityStudyDocument', 'FEMShapeLineQuantityStudy',
           'FEMShapeLineQuantityStudyRow']
_SCHEMA = 'sipi.fem-shape-line-quantity-study/1'
_PAIR = ('differential_forward_impedance_real', 'common_forward_impedance_real')
_QUANTITIES = ('impedance_real', 'attenuation') + _PAIR


def _line(study, parameters, evaluation, data):
    section = _TEMPLATES[study['template']](**parameters)
    count = 2 if study['quantity'] == 'z_diff_forward' else 1
    if sum(not trace.ground for trace in section.traces) != count:
        raise ValueError(f'FEM shape study requires exactly {count} signal(s)')
    return FEMShapeTransmissionLineDocument(CrossSectionDocument(section, mesh=study['mesh']),
        [evaluation['frequency_hz']], materials=_models(evaluation),
        conductors=data['conductors'], reference=data['reference'],
        ground_thickness=data['ground_thickness_m'], length=0., z_ref=50.)


def _quantity(line, names, frequency, quantity):
    if tuple(line.names) != names or tuple(line.frequency) != (frequency,):
        raise ValueError('extraction changed signal names or frequency')
    if quantity in _PAIR:
        characteristic = line.characteristic()
        if (characteristic.basis != 'single-ended' or tuple(characteristic.names) != names
                or tuple(characteristic.frequency) != tuple(line.frequency)):
            raise ValueError('characteristic changed signal coordinates or frequency')
        coordinate = 1 if quantity == 'common_forward_impedance_real' else 0
        value = float(characteristic.mixed_mode().z_characteristic[0, coordinate, coordinate].real)
    else:
        propagation = line.propagation()
        if propagation.modes != ('single',) or tuple(propagation.frequency) != tuple(line.frequency):
            raise ValueError('propagation changed scalar mode or frequency')
        value = float(propagation.z_characteristic[0, 0].real if quantity == 'impedance_real'
                      else propagation.gamma[0, 0].real)
    if not np.isfinite(value) or value < 0 or (quantity != 'attenuation' and value == 0):
        raise ValueError('solver returned an invalid FEM line quantity')
    return value


@dataclass(frozen=True)
class FEMShapeLineQuantityStudyRow(LineQuantityStudyRow):
    cause_details_json: str | None = None

    @property
    def cause_details(self):
        return None if self.cause_details_json is None else json.loads(self.cause_details_json)

    def to_dict(self):
        out = super().to_dict()
        out['cause_details'] = self.cause_details
        out['current_solver'] = None if self.result is None else self.result.current_record()
        return out


@dataclass(frozen=True)
class FEMShapeLineQuantityStudy(LineQuantityStudy):
    def to_dict(self):
        out = super().to_dict()
        out['scope'] = 'stated-fem-shape-samples-descriptive-not-production-yield'
        return out


class FEMShapeLineQuantityStudyDocument:
    """Sample a scalar or launched pair quantity using explicit FEM currents.

    Source study/3 or /4 defines geometry/material sampling and a fixed positive
    frequency. The source's z0/z_diff_forward selects scalar/paired inputs; its
    quasi-static calculation is not run. Metals are fixed per signal plus one
    common reference. Every sample creates a zero-length, 50-ohm-reference line.
    Re(Zdd) and Re(Zcc) describe Ic=0 and Id=0 launches, not independent modes.

    Generate and budget all samples before fields. Attempt duplicates and later
    rows after failures; preserve typed partial currents. Summaries require all
    rows to succeed, without clipping, resampling or weighting. The same nominal
    mesh controls do not reuse one mesh or certify each row's convergence.
    Budgets count line attempts, not internal capacitance or scalar solves.
    """
    def __init__(self, study, *, conductors, reference, ground_thickness, quantity):
        if isinstance(study, ImpedanceStudyDocument): study = study.to_dict()
        self._data = self._validate(dict(schema=_SCHEMA, study=study, conductors=conductors,
            reference=reference, ground_thickness_m=ground_thickness, quantity=quantity))

    @staticmethod
    def _validate(data):
        _keys(data, ('schema','study','conductors','reference','ground_thickness_m','quantity'),
              where='FEM shape line quantity study')
        if data['schema'] != _SCHEMA: raise ValueError('unsupported FEM shape line quantity study schema')
        if not isinstance(data['quantity'], str) or data['quantity'] not in _QUANTITIES:
            raise ValueError('unsupported FEM shape line quantity')
        study = _source_study(data['study'], paired=data['quantity'] in _PAIR)
        nominal = _line(study, study['parameters'], study['material_evaluation'], data).to_dict()
        return dict(schema=_SCHEMA, study=study, conductors=nominal['conductors'],
            reference=nominal['reference'], ground_thickness_m=nominal['ground_thickness_m'],
            quantity=data['quantity'])

    @classmethod
    def from_dict(cls, data):
        result = cls.__new__(cls); result._data = cls._validate(data); return result

    @classmethod
    def loads(cls, text):
        def reject(value): raise ValueError('nonfinite JSON number: '+value)
        return cls.from_dict(json.loads(text, object_pairs_hook=_unique_object, parse_constant=reject))

    def dumps(self): return json.dumps(self._data, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
    def to_dict(self): return json.loads(self.dumps())
    def samples(self): return ImpedanceStudyDocument.from_dict(self._data['study']).samples()

    def analyze(self, *, max_evaluations=128):
        return _analyze_fem_shape_study(self, max_evaluations=max_evaluations)


def _analyze_fem_shape_study(document, *, max_evaluations=128, data=None, line_factory=None):
    budget = _integer(max_evaluations, 2, 10000)
    data = document.to_dict() if data is None else data
    factory = _line if line_factory is None else line_factory
    study = data['study']; samples = document.samples()
    if len(samples) > budget: raise ValueError('sample count exceeds max_evaluations before any solve')
    rows = []
    for index, values in enumerate(samples):
        parameters_json = material_json = input_json = details = None
        line = None; value = None; phase = 'parameters'; error_type = error = None
        try:
            parameters = _parameters(study, values); parameters_json = _json(parameters)
            phase = 'materials'; evaluation = _sample_material(study, values); material_json = _json(evaluation)
            phase = 'input'; doc = factory(study, parameters, evaluation, data); input_json = doc.dumps()
            phase = 'extraction'; line = doc.analyze()
            names = tuple(trace.name for trace in doc.cross_section.section.traces if not trace.ground)
            phase = 'diagnostic'; value = _quantity(line, names, evaluation['frequency_hz'], data['quantity'])
            phase = 'complete'
        except Exception as exc:
            value = None; error_type = type(exc).__name__; error = str(exc)
            if isinstance(exc, FEMShapeLineError): details = _json(exc.to_dict())
        rows.append(FEMShapeLineQuantityStudyRow(index, tuple(map(float, values)), parameters_json,
            material_json, input_json, value, phase, error_type, error, line, details))
    summary = _summary([row.value for row in rows]) if all(row.complete for row in rows) else None
    return FEMShapeLineQuantityStudy(document.dumps(), data['quantity'],
        tuple(v['name'] for v in study['sampling']['variables']), tuple(rows), summary)
