# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit lossy geometry/material sampling with complete failure accounting."""
from dataclasses import dataclass
import json
from types import MappingProxyType

import numpy as np

from .document import _keys, _unique_object
from .study import ImpedanceStudyDocument, _parameters
from .sampling import _copy, _integer
from .impedance_material import _sample_material
from .line_input import _source_study, _line_from_values, _line_from_inputs
from .line_goal import _UNITS

__all__ = ['LineQuantityStudyDocument', 'LineQuantityStudy', 'LineQuantityStudyRow']


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def _summary(values):
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or len(values) < 2 or not np.all(np.isfinite(values)) or np.any(values < 0):
        raise ValueError('summary requires at least two finite nonnegative values')
    scale = float(values.max())
    normalized = values/scale if scale else values
    out = dict(minimum=float(values.min()), maximum=scale,
        mean=float(normalized.mean()*scale), sample_std=float(normalized.std(ddof=1)*scale),
        p05=float(np.quantile(normalized, .05, method='linear')*scale),
        p95=float(np.quantile(normalized, .95, method='linear')*scale))
    if not all(np.isfinite(value) for value in out.values()):
        raise ValueError('study statistics are not numerically representable')
    return out


@dataclass(frozen=True)
class LineQuantityStudyRow:
    index: int
    sample_values: tuple[float, ...]
    parameters_json: str | None
    material_evaluation_json: str | None
    input_json: str | None
    value: float | None
    phase: str
    error_type: str | None
    error: str | None
    result: object | None = None

    @property
    def complete(self):
        return self.error is None

    def to_dict(self):
        return dict(index=self.index, sample_values=list(self.sample_values), value=self.value,
            phase=self.phase, error_type=self.error_type, error=self.error,
            parameters=None if self.parameters_json is None else json.loads(self.parameters_json),
            material_evaluation=(None if self.material_evaluation_json is None else
                                 json.loads(self.material_evaluation_json)),
            input=None if self.input_json is None else json.loads(self.input_json))


@dataclass(frozen=True)
class LineQuantityStudy:
    input_json: str
    quantity: str
    variable_names: tuple[str, ...]
    rows: tuple[LineQuantityStudyRow, ...]
    summary: object | None

    def __post_init__(self):
        object.__setattr__(self, 'variable_names', tuple(self.variable_names))
        object.__setattr__(self, 'rows', tuple(self.rows))
        if self.summary is not None:
            object.__setattr__(self, 'summary', MappingProxyType(dict(self.summary)))

    @property
    def failed(self):
        return sum(not row.complete for row in self.rows)

    @property
    def unit(self):
        return _UNITS[self.quantity]

    def to_dict(self):
        return dict(quantity=self.quantity, unit=self.unit, variable_names=list(self.variable_names),
            count=len(self.rows), failed=self.failed, summary=None if self.summary is None else dict(self.summary),
            rows=[row.to_dict() for row in self.rows], scope='stated-samples-descriptive-not-production-yield')


class LineQuantityStudyDocument:
    """Sample full-loss line quantities with explicit saved versions 1 and 2.

    The nested study/3 or /4 supplies scalar template inputs, fixed positive
    frequency, sampling and geometry/material constraints. Its z0 selects the
    source contract; the old quasi-static study is not analyzed. Each sample
    instead creates a zero-length line/6 at a fixed 50-ohm reference with the
    supplied fixed conductor. Re(Zc) or Re(gamma) is independent of that reference.
    Version 1 is the constructor default and remains scalar-only. Explicit
    version 2 also accepts a z_diff_forward pair source and the quantity
    differential_forward_impedance_real. It targets Re(Zdd) with launch Ic=0,
    retaining asymmetric coupling rather than asserting an independent mode.

    Every generated sample is attempted in order, including after failures.
    Failed rows retain their sample values and all representable intermediate
    inputs. No clipping, resampling or partial summary is allowed. Invalid
    sampling generation, including overflow, raises before any field work.
    Nominal resolved mesh settings are reused, not a single geometric mesh or
    a per-row convergence guarantee. This is not a yield confidence interval.
    """
    def __init__(self, study, *, conductor, quantity, schema='sipi.line-quantity-study/1'):
        if isinstance(study, ImpedanceStudyDocument):
            study = study.to_dict()
        self._assign(dict(schema=schema, study=study,
                          conductor=conductor, quantity=quantity))

    def _assign(self, data):
        data = _copy(data)
        _keys(data, ('schema', 'study', 'conductor', 'quantity'), where='line quantity study')
        if data['schema'] not in ('sipi.line-quantity-study/1', 'sipi.line-quantity-study/2'):
            raise ValueError('unsupported line-quantity-study schema')
        allowed = ('impedance_real', 'attenuation')
        if data['schema'] == 'sipi.line-quantity-study/2':
            allowed += ('differential_forward_impedance_real',)
        if not isinstance(data['quantity'], str) or data['quantity'] not in allowed:
            raise ValueError('quantity must be '+' or '.join(allowed))
        study = _source_study(data['study'], paired=data['quantity'] == 'differential_forward_impedance_real')
        nominal = _line_from_values(study, data['conductor'])
        self._data = dict(schema=data['schema'], study=study,
            conductor=nominal.to_dict()['conductor'], quantity=data['quantity'])

    @classmethod
    def from_dict(cls, data):
        out = cls.__new__(cls); out._assign(data); return out

    @classmethod
    def loads(cls, text):
        def reject(value):
            raise ValueError(f'nonfinite JSON number: {value}')
        return cls.from_dict(json.loads(text, object_pairs_hook=_unique_object, parse_constant=reject))

    def dumps(self):
        return json.dumps(self._data, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)

    def to_dict(self):
        return json.loads(self.dumps())

    def samples(self):
        return ImpedanceStudyDocument.from_dict(self._data['study']).samples()

    def analyze(self, *, max_evaluations=128):
        budget = _integer(max_evaluations, 2, 10000)
        data = self.to_dict(); study = data['study']; samples = self.samples()
        if len(samples) > budget:
            raise ValueError('sample count exceeds max_evaluations before any solve')
        rows = []
        for index, values in enumerate(samples):
            parameters_json = material_json = input_json = None
            line = None; value = None; phase = 'parameters'; error_type = error = None
            try:
                parameters = _parameters(study, values); parameters_json = _json(parameters)
                phase = 'materials'
                evaluation = _sample_material(study, values); material_json = _json(evaluation)
                phase = 'input'
                doc = _line_from_inputs(study, data['conductor'], parameters, evaluation)
                input_json = doc.dumps()
                phase = 'extraction'
                line = doc.analyze()
                names = tuple(trace.name for trace in doc.cross_section.section.traces if not trace.ground)
                if tuple(line.names) != names or tuple(line.frequency) != (evaluation['frequency_hz'],):
                    raise ValueError('extraction changed signal names or frequency')
                phase = 'diagnostic'
                if data['quantity'] == 'differential_forward_impedance_real':
                    characteristic = line.characteristic()
                    if (characteristic.basis != 'single-ended' or tuple(characteristic.names) != names
                            or tuple(characteristic.frequency) != tuple(line.frequency)):
                        raise ValueError('characteristic changed signal coordinates or frequency')
                    value = float(characteristic.mixed_mode().z_characteristic[0, 0, 0].real)
                else:
                    propagation = line.propagation()
                    if propagation.modes != ('single',) or tuple(propagation.frequency) != tuple(line.frequency):
                        raise ValueError('propagation changed scalar mode or frequency')
                    value = float(propagation.z_characteristic[0, 0].real if data['quantity'] == 'impedance_real'
                                  else propagation.gamma[0, 0].real)
                if not np.isfinite(value) or value < 0 or (data['quantity'] != 'attenuation' and value == 0):
                    raise ValueError('solver returned an invalid line quantity')
                phase = 'complete'
            except Exception as exc:
                value = None; error_type = type(exc).__name__; error = str(exc)
            rows.append(LineQuantityStudyRow(index, tuple(map(float, values)), parameters_json,
                material_json, input_json, value, phase, error_type, error, line))
        summary = _summary([row.value for row in rows]) if all(row.complete for row in rows) else None
        return LineQuantityStudy(self.dumps(), data['quantity'],
            tuple(variable['name'] for variable in study['sampling']['variables']), tuple(rows), summary)
