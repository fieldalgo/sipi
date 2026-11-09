# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Two bounded parameters for full-loss differential/common forward targets."""
from dataclasses import dataclass
import json

import numpy as np
from scipy.optimize import least_squares

from .line_model import TransmissionLineDocument, TransmissionLineResult
from .pair_design import _least_squares_two
from .sampling import _integer, _numbers

__all__ = ['ForwardPairEvaluation', 'ForwardPairDesign', 'ForwardPairGoalError',
           'seek_forward_pair_impedances']

_QUANTITIES = ('differential_forward_impedance_real', 'common_forward_impedance_real')


@dataclass(frozen=True)
class ForwardPairEvaluation:
    parameters: tuple[float, float]
    impedances: tuple[float, float]
    stage: str
    input_json: str

    def to_dict(self):
        return dict(parameters=list(self.parameters), impedances_ohm=list(self.impedances),
                    stage=self.stage, input=json.loads(self.input_json))


class ForwardPairGoalError(RuntimeError):
    """Completed rows and the original failed attempt remain inspectable."""
    def __init__(self, message, history, *, attempts, stage, failed_parameters=None,
                 cause_type=None, input_json=None):
        super().__init__(message)
        self.history = tuple(history)
        self.attempts = attempts
        self.stage = stage
        self.failed_parameters = failed_parameters
        self.cause_type = cause_type
        self.input_json = input_json


@dataclass(frozen=True)
class ForwardPairDesign:
    parameters: tuple[float, float]
    targets: tuple[float, float]
    tolerances: tuple[float, float]
    impedances: tuple[float, float]
    refined_impedances: tuple[float, float]
    input_json: str
    refined_input_json: str
    history: tuple[ForwardPairEvaluation, ...]
    result: TransmissionLineResult
    refined_result: TransmissionLineResult

    @property
    def residuals(self):
        return tuple(a-b for a, b in zip(self.impedances, self.targets))

    @property
    def refined_residuals(self):
        return tuple(a-b for a, b in zip(self.refined_impedances, self.targets))

    @property
    def document(self):
        return TransmissionLineDocument.loads(self.input_json)

    @property
    def refined_document(self):
        return TransmissionLineDocument.loads(self.refined_input_json)

    def to_dict(self):
        return dict(parameters=list(self.parameters), quantities=list(_QUANTITIES),
            targets_ohm=list(self.targets), tolerances_ohm=list(self.tolerances),
            impedances_ohm=list(self.impedances), refined_impedances_ohm=list(self.refined_impedances),
            residuals_ohm=list(self.residuals), refined_residuals_ohm=list(self.refined_residuals),
            evaluations=len(self.history), history=[row.to_dict() for row in self.history],
            input=self.document.to_dict(), refined_input=self.refined_document.to_dict(),
            scope='bounded-two-parameter-forward-pair-impedance-goal')


def seek_forward_pair_impedances(factory, bounds, targets, *, tolerances,
                                 initial=None, max_evaluations=64):
    """Seek (Re(Zdd), Re(Zcc)) with two positive bounded factory parameters.

    factory(p0,p1) returns a TransmissionLineDocument with exactly two ordered
    signals, one positive frequency and zero length. Frequency and names stay
    fixed. Geometry, materials and explicit conductor laws may vary; the
    caller owns their physical validity. No callable is serialized.

    With Vd=V1-V2, Id=(I1-I2)/2, Vc=(V1+V2)/2 and Ic=I1+I2, the separate
    forward-current launches Ic=0 and Id=0 define Zdd and Zcc. Both values
    use the full complex characteristic matrix, including asymmetric coupling.
    These are not magnitudes, decoupled eigenmodes or finite terminal inputs;
    neither current constraint is imposed everywhere downstream.

    Bounds, targets and tolerances each have two entries in parameter units
    and ohms respectively. The default start is the bounds midpoint. Reuse
    normalized bounded least squares with 1%-range Jacobian probes and
    xtol=ftol=1e-4, gtol=1e-3. Cached parameter tuples do not consume attempts.
    Every uncached factory/validation/extraction/diagnostic attempt does,
    including failures and probes. Reserve one final attempt to halve all
    edge/far/grade controls of the frozen chosen input without calling the
    factory again. Both meshes must satisfy both absolute target tolerances.

    A stationary candidate missing a target fails even if the optimizer claims
    success. An initial point meeting both targets still requires refinement.
    No uniqueness, feasibility, global optimum, continuity or outer-domain
    accuracy is certified. The attempt budget does not bound internal solves,
    memory or time. Control errors precede factories; subsequent errors retain
    history, available inputs and the original cause in ForwardPairGoalError.
    """
    if not callable(factory):
        raise TypeError('factory must be callable')
    ranges = _numbers(bounds)
    if ranges.shape != (2, 2) or np.any(ranges <= 0) or np.any(ranges[:, 0] >= ranges[:, 1]):
        raise ValueError('bounds must contain two increasing positive finite pairs')
    target = _numbers(targets)
    tolerance = _numbers(tolerances)
    for name, values in [('targets', target), ('tolerances', tolerance)]:
        if values.shape != (2,) or np.any(values <= 0):
            raise ValueError(f'{name} must contain two positive finite numbers')
    budget = _integer(max_evaluations, 2, 10000)
    lower, upper = ranges[:, 0], ranges[:, 1]
    span = upper-lower
    start = lower+span/2 if initial is None else _numbers(initial)
    if start.shape != (2,) or np.any(start < lower) or np.any(start > upper):
        raise ValueError('initial must contain two parameters inside bounds')
    history = []
    attempts = 0
    identity = None
    cache = {}

    def failure(message, stage, parameters=None, *, cause=None, text=None):
        return ForwardPairGoalError(message, history, attempts=attempts, stage=stage,
            failed_parameters=parameters, cause_type=None if cause is None else type(cause).__name__,
            input_json=text)

    def evaluate(parameters, selected=None):
        nonlocal attempts, identity
        stage = 'search' if selected is None else 'refinement'
        if attempts >= (budget-1 if selected is None else budget):
            raise failure('evaluation budget exhausted before target verification', 'budget', parameters)
        attempts += 1
        phase = 'factory' if selected is None else 'refinement-input'
        text = None
        try:
            if selected is None:
                candidate = factory(*parameters)
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
            names = tuple(trace.name for trace in doc.cross_section.section.traces if not trace.ground)
            if len(frequency) != 1 or frequency[0] <= 0 or len(names) != 2 or data['length_m'] != 0:
                raise ValueError('goal requires two signals, one positive frequency and zero length')
            current = (frequency[0], names)
            if identity is not None and current != identity:
                raise ValueError('frequency and ordered signal names must stay fixed')
            identity = current
            phase = 'extraction'
            line = doc.analyze()
            if tuple(line.frequency) != tuple(frequency) or tuple(line.names) != names:
                raise ValueError('extraction changed frequency or ordered signal names')
            phase = 'diagnostic'
            characteristic = line.characteristic()
            if (characteristic.basis != 'single-ended' or tuple(characteristic.names) != names
                    or tuple(characteristic.frequency) != tuple(frequency)):
                raise ValueError('characteristic changed signal coordinates or frequency')
            mixed = characteristic.mixed_mode()
            if (mixed.basis != 'mixed-mode' or tuple(mixed.names) != ('differential', 'common')
                    or tuple(mixed.frequency) != tuple(frequency)):
                raise ValueError('mixed characteristic changed coordinates or frequency')
            matrix = np.asarray(mixed.z_characteristic)
            if matrix.shape != (1, 2, 2) or not np.all(np.isfinite(matrix)):
                raise ValueError('mixed characteristic must be one finite 2-by-2 matrix')
            values = _numbers(np.diag(matrix[0]).real)
            if np.any(values <= 0):
                raise ValueError('solver returned invalid forward impedances')
            with np.errstate(over='raise', invalid='raise', divide='raise'):
                residual = (values-target)/tolerance
            if not np.all(np.isfinite(residual)):
                raise ValueError('normalized residuals must remain finite')
        except Exception as exc:
            raise failure(f'{stage} {phase} failed: {exc}', stage+'/'+phase, parameters,
                          cause=exc, text=text) from exc
        row = ForwardPairEvaluation(parameters, tuple(float(v) for v in values), stage, text)
        history.append(row)
        return row, residual, line

    def physical(u):
        return tuple(float(lower[i] if x == 0 else upper[i] if x == 1 else lower[i]+span[i]*x)
                     for i, x in enumerate(u))

    def objective(u):
        parameters = physical(u)
        if parameters not in cache:
            cache[parameters] = evaluate(parameters)
        return cache[parameters][1].copy()

    u = (start-lower)/span
    residual = objective(u)
    if np.any(abs(residual) > 1):
        try:
            optimized = _least_squares_two(objective, u, budget, least_squares)
        except ForwardPairGoalError:
            raise
        except Exception as exc:
            raise failure(f'optimizer failed: {exc}', 'optimizer', cause=exc) from exc
        if not optimized.success:
            parameters = physical(optimized.x)
            previous = cache.get(parameters)
            raise failure('optimizer did not converge: '+str(optimized.message), 'convergence', parameters,
                          text=None if previous is None else previous[0].input_json)
        u = optimized.x
        residual = objective(u)
    chosen, _, line = cache[physical(u)]
    if np.any(abs(residual) > 1):
        raise failure('stationary candidate misses one or both targets', 'convergence', chosen.parameters,
                      text=chosen.input_json)
    refined, residual, refined_line = evaluate(chosen.parameters, selected=chosen)
    if np.any(abs(residual) > 1):
        raise failure('refined mesh misses target; tighten mesh settings and rerun', 'refinement/target',
                      chosen.parameters, text=refined.input_json)
    return ForwardPairDesign(chosen.parameters, tuple(target), tuple(tolerance), chosen.impedances,
        refined.impedances, chosen.input_json, refined.input_json, tuple(history), line, refined_line)
