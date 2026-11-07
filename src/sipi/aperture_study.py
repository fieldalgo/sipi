# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved local-capacitance studies and bounded goals, retaining failed samples."""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
import json
from types import MappingProxyType

import numpy as np

from .aperture_section import ApertureSectionDocument
from .document import _keys, _unique_object
from .sampling import _copy, _integer, _scalar, _validate_sampling, _sample_values

__all__ = ['ApertureStudyDocument', 'CapacitanceStudy', 'CapacitanceStudyRow',
           'ApertureDesignDocument', 'CapacitanceDesign', 'CapacitanceEvaluation', 'CapacitanceGoalError']


def _parameters(document):
    data = document.to_dict()
    values = dict(data['aperture'], **data['dielectric'])
    for i, conductor in enumerate(data['conductors']):
        values.update({f'conductor_{i}_{name}': conductor[name] for name in ('diameter', 'x', 'y')})
    return values


def _document(data, parameters):
    result = _copy(data)
    result['aperture'].update({k: parameters[k] for k in ('width', 'height')})
    result['dielectric'].update({k: parameters[k] for k in ('eps_r', 'tan_delta')})
    for i, conductor in enumerate(result['conductors']):
        conductor.update({k: parameters[f'conductor_{i}_{k}'] for k in ('diameter', 'x', 'y')})
    return ApertureSectionDocument.from_dict(result)


def _quantity(quantity, document):
    allowed = ('c11',) if len(document.section.conductors) == 1 else ('c11', 'c22', 'mutual', 'differential', 'common')
    if not isinstance(quantity, str) or quantity not in allowed:
        raise ValueError('unsupported real capacitance quantity for this conductor count')
    return quantity


def _value(document, quantity):
    c = document.analyze().real
    if quantity == 'c11':
        result = c[0, 0]
    elif quantity == 'c22':
        result = c[1, 1]
    elif quantity == 'mutual':
        result = -c[0, 1]
    elif quantity == 'differential':
        result = (c[0, 0]+c[1, 1]-2*c[0, 1])/4
    else:
        result = c[0, 0]+c[1, 1]+2*c[0, 1]
    if not np.isfinite(result) or result <= 0:
        raise ValueError('selected capacitance must be positive and finite')
    return float(result)


class _SavedInput:
    @classmethod
    def from_dict(cls, data):
        out = cls.__new__(cls)
        out._data = cls._validate(data)
        return out

    @classmethod
    def loads(cls, text):
        def reject(value):
            raise ValueError(f'nonfinite JSON number: {value}')
        return cls.from_dict(json.loads(text, object_pairs_hook=_unique_object, parse_constant=reject))

    def dumps(self):
        return json.dumps(self._data, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)

    def to_dict(self):
        return json.loads(self.dumps())


@dataclass(frozen=True)
class CapacitanceStudyRow:
    index: int
    parameters: object
    document: ApertureSectionDocument | None
    capacitance: float | None
    error_type: str | None
    error: str | None

    def __post_init__(self):
        object.__setattr__(self, 'parameters', MappingProxyType(dict(self.parameters)))

    @property
    def complete(self):
        return self.error is None


@dataclass(frozen=True)
class CapacitanceStudy:
    input_json: str
    quantity: str
    rows: tuple[CapacitanceStudyRow, ...]
    summary: object | None

    def __post_init__(self):
        object.__setattr__(self, 'rows', tuple(self.rows))
        if self.summary is not None:
            object.__setattr__(self, 'summary', MappingProxyType(dict(self.summary)))

    @property
    def failed(self):
        return sum(not row.complete for row in self.rows)


class ApertureStudyDocument(_SavedInput):
    """Strict aperture-study/1, with real C targets in F/m and nominal mesh settings.

    Variables: width, height, eps_r, tan_delta, conductor_0/1_diameter/x/y.
    Indices follow saved conductor order. Bounds are checked at every corner;
    this does not prove all intermediate configurations avoid conductor contact.
    Invalid samples remain failed rows, never resampled or omitted.
    """
    def __init__(self, document: ApertureSectionDocument, *, sampling, quantity='c11'):
        if not isinstance(document, ApertureSectionDocument):
            raise TypeError('document must be an ApertureSectionDocument')
        self._data = self._validate(dict(schema='sipi.aperture-study/1', section=document.to_dict(),
                                        quantity=quantity, sampling=sampling))

    @staticmethod
    def _validate(data):
        data = _copy(data)
        _keys(data, ('schema', 'section', 'quantity', 'sampling'), where='aperture study')
        if data['schema'] != 'sipi.aperture-study/1':
            raise ValueError('unsupported aperture-study schema')
        doc = ApertureSectionDocument.from_dict(data['section'])
        quantity = _quantity(data['quantity'], doc)
        nominal = _parameters(doc)
        sampling = _validate_sampling(data['sampling'], nominal)
        variables = sampling['variables']
        if sampling['kind'] != 'normal':
            for corner in product(*[(v['lower'], v['upper']) for v in variables]):
                parameters = dict(nominal)
                parameters.update(zip((v['name'] for v in variables), corner))
                _document(doc.to_dict(), parameters)
        return dict(schema=data['schema'], section=doc.to_dict(), quantity=quantity, sampling=sampling)

    def samples(self):
        return _sample_values(self._data['sampling'])

    def sample_parameters(self):
        nominal = _parameters(ApertureSectionDocument.from_dict(self._data['section']))
        names = [v['name'] for v in self._data['sampling']['variables']]
        return [dict(nominal, **dict(zip(names, map(float, row)))) for row in self.samples()]

    def analyze(self, *, max_evaluations=128):
        """Evaluate all rows within budget; summarize only if every row succeeds."""
        budget = _integer(max_evaluations, 2, 10000)
        parameters = self.sample_parameters()
        if len(parameters) > budget:
            raise ValueError('sample count exceeds max_evaluations before any solve')
        rows = []
        for i, values in enumerate(parameters):
            doc = None
            try:
                doc = _document(self._data['section'], values)
                value = _value(doc, self._data['quantity'])
                rows.append(CapacitanceStudyRow(i, values, doc, value, None, None))
            except Exception as exc:
                rows.append(CapacitanceStudyRow(i, values, doc, None, type(exc).__name__, str(exc)))
        summary = None
        if all(row.complete for row in rows):
            c = np.array([row.capacitance for row in rows])
            summary = dict(minimum=float(c.min()), maximum=float(c.max()), mean=float(c.mean()),
                sample_std=float(c.std(ddof=1)), p05=float(np.quantile(c, .05, method='linear')),
                p95=float(np.quantile(c, .95, method='linear')))
        return CapacitanceStudy(self.dumps(), self._data['quantity'], tuple(rows), summary)


@dataclass(frozen=True)
class CapacitanceEvaluation:
    parameter: float
    capacitance: float
    stage: str


@dataclass(frozen=True)
class CapacitanceDesign:
    parameter: float
    target: float
    capacitance: float
    refined_capacitance: float
    quantity: str
    document: ApertureSectionDocument
    history: tuple[CapacitanceEvaluation, ...]
    input_json: str

    @property
    def residual(self):
        return self.capacitance-self.target

    @property
    def refined_residual(self):
        return self.refined_capacitance-self.target


class CapacitanceGoalError(RuntimeError):
    """Failed bounded goal, preserving completed evaluations and failed parameter."""
    def __init__(self, message, history, *, parameter=None):
        super().__init__(message)
        self.history = tuple(history)
        self.parameter = parameter


class ApertureDesignDocument(_SavedInput):
    """Saved single-variable bracket and real target/tolerance in F/m.

    Offset bounds may be negative. Success requires both requested and refined
    meshes to meet the target. This is not impedance or a physical yield model.
    """
    def __init__(self, document: ApertureSectionDocument, *, variable, bounds, target,
                 quantity='c11', tolerance=1e-13, max_evaluations=40):
        if not isinstance(document, ApertureSectionDocument):
            raise TypeError('document must be an ApertureSectionDocument')
        self._data = self._validate(dict(schema='sipi.aperture-design/1', section=document.to_dict(),
            variable=variable, bounds=bounds, target_f_per_m=target, quantity=quantity,
            tolerance_f_per_m=tolerance, max_evaluations=max_evaluations))

    @staticmethod
    def _validate(data):
        data = _copy(data)
        _keys(data, ('schema', 'section', 'variable', 'bounds', 'target_f_per_m', 'quantity',
                     'tolerance_f_per_m', 'max_evaluations'), where='aperture design')
        if data['schema'] != 'sipi.aperture-design/1':
            raise ValueError('unsupported aperture-design schema')
        if not isinstance(data['bounds'], list) or len(data['bounds']) != 2:
            raise ValueError('bounds must contain two finite numbers')
        data['bounds'] = [_scalar(v) for v in data['bounds']]
        if data['bounds'][0] >= data['bounds'][1]:
            raise ValueError('lower bound must be below upper bound')
        data['target_f_per_m'] = _scalar(data['target_f_per_m'], positive=True)
        data['tolerance_f_per_m'] = _scalar(data['tolerance_f_per_m'], positive=True)
        data['max_evaluations'] = _integer(data['max_evaluations'], 3, 10000)
        doc = ApertureSectionDocument.from_dict(data['section'])
        study = ApertureStudyDocument(doc, quantity=data['quantity'], sampling=dict(kind='sweep', count=2,
            variables=[dict(name=data['variable'], lower=data['bounds'][0], upper=data['bounds'][1])]))
        data['section'] = study.to_dict()['section']
        return data

    def solve(self):
        data = self.to_dict()
        base = ApertureSectionDocument.from_dict(data['section'])
        nominal = _parameters(base)
        history = []
        target, tolerance = data['target_f_per_m'], data['tolerance_f_per_m']

        def evaluate(parameter, stage='search'):
            if stage == 'search' and len(history) >= data['max_evaluations']-1:
                raise CapacitanceGoalError('evaluation limit reached before convergence', history, parameter=parameter)
            values = dict(nominal)
            values[data['variable']] = parameter
            try:
                doc = _document(data['section'], values)
                if stage == 'refinement':
                    options = doc.mesh_options
                    options['size'] /= 2
                    options['angular_divisions'] *= 2
                    doc = ApertureSectionDocument(doc.section, mesh=options)
                value = _value(doc, data['quantity'])
            except Exception as exc:
                raise CapacitanceGoalError(f'{stage} evaluation failed: {type(exc).__name__}: {exc}',
                                          history, parameter=parameter) from exc
            history.append(CapacitanceEvaluation(parameter, value, stage))
            return value-target, doc

        lower, upper = data['bounds']
        fl, dl = evaluate(lower)
        fu, du = evaluate(upper)
        if abs(fl) <= tolerance or abs(fu) <= tolerance:
            x, residual, doc = (lower, fl, dl) if abs(fl) <= abs(fu) else (upper, fu, du)
        else:
            if (fl > 0) == (fu > 0):
                raise CapacitanceGoalError('target is not bracketed by endpoint capacitances', history)
            while True:
                x = lower/2+upper/2
                if x == lower or x == upper:
                    raise CapacitanceGoalError('parameter resolution exhausted', history, parameter=x)
                residual, doc = evaluate(x)
                if abs(residual) <= tolerance:
                    break
                if (residual > 0) == (fl > 0):
                    lower, fl = x, residual
                else:
                    upper = x
        refined_residual, _ = evaluate(x, 'refinement')
        if abs(refined_residual) > tolerance:
            raise CapacitanceGoalError('refined mesh misses target; tighten mesh settings and rerun',
                                      history, parameter=x)
        return CapacitanceDesign(x, target, residual+target, refined_residual+target, data['quantity'],
                                 doc, tuple(history), self.dumps())
