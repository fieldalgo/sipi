# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Bounded scalar goals using extracted lossy line quantities, with refinement."""
from dataclasses import dataclass
import json
import math

from .line_model import TransmissionLineDocument, TransmissionLineResult
from .network import _scalar
from .sampling import _integer

__all__ = ['LineQuantityEvaluation', 'LineQuantityDesign', 'LineQuantityGoalError',
           'seek_line_quantity']

_UNITS = {'impedance_real': 'ohm', 'attenuation': 'Np/m'}


@dataclass(frozen=True)
class LineQuantityEvaluation:
    parameter: float
    value: float
    stage: str
    input_json: str

    def to_dict(self):
        return dict(parameter=self.parameter, value=self.value, stage=self.stage,
                    input=json.loads(self.input_json))


class LineQuantityGoalError(RuntimeError):
    """Completed rows and the failed attempt survive all search/solver failures."""
    def __init__(self, message, history, *, attempts, quantity, failed_parameter=None,
                 stage, cause_type=None, input_json=None):
        super().__init__(message)
        self.history = tuple(history)
        self.attempts = attempts
        self.quantity = quantity
        self.unit = _UNITS[quantity]
        self.failed_parameter = failed_parameter
        self.stage = stage
        self.cause_type = cause_type
        self.input_json = input_json


@dataclass(frozen=True)
class LineQuantityDesign:
    parameter: float
    target: float
    tolerance: float
    quantity: str
    value: float
    refined_value: float
    history: tuple[LineQuantityEvaluation, ...]
    result: TransmissionLineResult
    refined_result: TransmissionLineResult

    @property
    def unit(self):
        return _UNITS[self.quantity]

    @property
    def residual(self):
        return self.value-self.target

    @property
    def refined_residual(self):
        return self.refined_value-self.target

    @property
    def mesh_change(self):
        return self.refined_value-self.value

    @property
    def document(self):
        return TransmissionLineDocument.loads(self.result.input_json)

    @property
    def refined_document(self):
        return TransmissionLineDocument.loads(self.refined_result.input_json)

    def to_dict(self):
        return dict(parameter=self.parameter, quantity=self.quantity, unit=self.unit,
            target=self.target, tolerance=self.tolerance, value=self.value,
            refined_value=self.refined_value, residual=self.residual,
            refined_residual=self.refined_residual, mesh_change=self.mesh_change,
            evaluations=len(self.history), history=[row.to_dict() for row in self.history],
            input=self.document.to_dict(), refined_input=self.refined_document.to_dict(),
            scope='bounded-single-parameter-scalar-line-goal')


def seek_line_quantity(factory, bounds, target, *, quantity, tolerance, max_evaluations=40):
    """Bisect a scalar line metric, retaining full R/L/G/C and input snapshots.

    factory(parameter) returns a TransmissionLineDocument with exactly one
    signal, one positive frequency and zero length. Frequency and signal name
    stay fixed across candidates. Geometry or materials may vary. Parameter
    bounds are positive in the caller's units. This API does not serialize the
    callable or infer manufacturing distributions.

    impedance_real targets Re(Zc) in ohms; attenuation targets Re(gamma) in
    Np/m. Both use the existing full lossy RLGC propagation, not abs(Zc), the
    real quasi-static impedance, or finite-length insertion loss. Pairs and
    mode tracking across geometry changes require a separate contract.

    Both endpoints must evaluate successfully. An endpoint within tolerance
    is eligible; otherwise residual signs must bracket zero. Bisection is not
    a proof of continuity, monotonicity, uniqueness or a global optimum.
    Reserve one attempt to halve edge_size/far_size/grade at the selected
    frozen input; keep min_angle and all physical inputs. Both values must
    satisfy the same absolute tolerance. Outer-domain/physical validity is
    the caller's responsibility, separate from this mesh check.

    Every factory/validation/extraction/diagnostic attempt, including failures,
    counts against max_evaluations. An attempt can include multiple internal
    field solves; the budget does not bound memory or elapsed time. Control
    errors raise ValueError/TypeError before invoking the factory. Subsequent
    failures raise LineQuantityGoalError with completed rows and failure data.
    """
    if not callable(factory):
        raise TypeError('factory must be callable')
    if not isinstance(quantity, str) or quantity not in _UNITS:
        raise ValueError('quantity must be impedance_real or attenuation')
    try:
        lower, upper = bounds
    except (TypeError, ValueError) as exc:
        raise ValueError('bounds must contain two positive finite numbers') from exc
    lower, upper = (_scalar('parameter bound', x) for x in (lower, upper))
    if lower >= upper:
        raise ValueError('lower parameter bound must be below upper')
    target = _scalar('target', target, zero=quantity == 'attenuation')
    tolerance = _scalar('tolerance', tolerance)
    budget = _integer(max_evaluations, 3, 10000)
    history = []; attempts = 0; identity = None

    def failure(message, stage, parameter=None, *, cause=None, text=None):
        return LineQuantityGoalError(message, history, attempts=attempts, quantity=quantity,
            failed_parameter=parameter, stage=stage,
            cause_type=None if cause is None else type(cause).__name__, input_json=text)

    def evaluate(parameter, stage='search', selected=None):
        nonlocal attempts, identity
        limit = budget-1 if stage == 'search' else budget
        if attempts >= limit:
            raise failure('evaluation budget exhausted before target convergence', 'budget', parameter)
        attempts += 1
        phase = 'factory' if selected is None else 'refinement-input'
        text = None
        try:
            if selected is None:
                candidate = factory(parameter)
                if not isinstance(candidate, TransmissionLineDocument):
                    raise TypeError('factory must return TransmissionLineDocument')
                text = candidate.dumps()
                phase = 'validation'
                doc = TransmissionLineDocument.loads(text)
            else:
                data = json.loads(selected.input_json)
                for key in ('edge_size', 'far_size', 'grade'):
                    data['cross_section']['mesh'][key] /= 2
                doc = TransmissionLineDocument.from_dict(data)
            text = doc.dumps(); data = doc.to_dict()
            frequency = data['frequency_hz']
            names = tuple(t.name for t in doc.cross_section.section.traces if not t.ground)
            if len(frequency) != 1 or frequency[0] <= 0 or len(names) != 1 or data['length_m'] != 0:
                raise ValueError('goal requires one signal, one positive frequency and zero length')
            current = (frequency[0], names)
            if identity is not None and current != identity:
                raise ValueError('frequency and signal name must stay fixed across goal inputs')
            identity = current
            phase = 'extraction'
            line = doc.analyze()
            if tuple(line.frequency) != tuple(frequency) or tuple(line.names) != names:
                raise ValueError('extraction changed frequency or signal name')
            phase = 'diagnostic'
            propagation = line.propagation()
            if propagation.modes != ('single',) or tuple(propagation.frequency) != tuple(frequency):
                raise ValueError('propagation changed scalar mode or frequency')
            value = float(propagation.z_characteristic[0, 0].real if quantity == 'impedance_real'
                          else propagation.gamma[0, 0].real)
            if not math.isfinite(value) or value < 0 or (quantity == 'impedance_real' and value == 0):
                raise ValueError('solver returned an invalid goal quantity')
        except Exception as exc:
            raise failure(f'{stage} {phase} failed: {exc}', stage+'/'+phase, parameter,
                          cause=exc, text=text) from exc
        row = LineQuantityEvaluation(parameter, value, stage, text)
        history.append(row)
        return row, line

    left, left_line = evaluate(lower)
    right, right_line = evaluate(upper)
    fl, fu = left.value-target, right.value-target
    if abs(fl) <= tolerance or abs(fu) <= tolerance:
        chosen, line = ((left, left_line) if abs(fl) <= abs(fu) else (right, right_line))
    else:
        if (fl > 0) == (fu > 0):
            raise failure('target is not bracketed by endpoint quantities', 'bracket')
        while True:
            middle = lower+(upper-lower)/2
            if middle == lower or middle == upper:
                raise failure('parameter resolution exhausted before target convergence', 'precision', middle)
            chosen, line = evaluate(middle)
            residual = chosen.value-target
            if abs(residual) <= tolerance:
                break
            if (residual > 0) == (fl > 0):
                lower, fl = middle, residual
            else:
                upper = middle
    refined, refined_line = evaluate(chosen.parameter, 'refinement', chosen)
    if abs(refined.value-target) > tolerance:
        raise failure('refined mesh misses target; tighten mesh and rerun', 'refinement/acceptance',
                      chosen.parameter, text=refined.input_json)
    return LineQuantityDesign(chosen.parameter, target, tolerance, quantity, chosen.value,
        refined.value, tuple(history), line, refined_line)
