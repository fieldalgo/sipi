# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit sampled panel-current two-parameter forward goals."""
from dataclasses import dataclass
import json
import numpy as np
from scipy.optimize import least_squares
from sipi.panel_line import PanelTransmissionLineDocument, PanelTransmissionLineResult
from sipi.panel_pair_goal import _refinements
from sipi.pair_design import _least_squares_two
from sipi.sampling import _integer, _numbers
from sipi.network import _frequencies

_QUANTITIES = ('differential_forward_impedance_real', 'common_forward_impedance_real')


def _rows(values):
    return tuple(tuple(float(value) for value in row) for row in values)


@dataclass(frozen=True)
class SampledPanelForwardPairEvaluation:
    parameters: tuple[float, float]
    impedances: tuple[tuple[float, float], ...]
    stage: str
    input_json: str

    def to_dict(self):
        return dict(parameters=list(self.parameters), impedances_ohm=[list(row) for row in self.impedances],
                    stage=self.stage, input=json.loads(self.input_json))


class SampledPanelForwardPairGoalError(RuntimeError):
    def __init__(self, message, history, *, frequencies, attempts, stage,
                 failed_parameters=None, cause_type=None, input_json=None):
        super().__init__(message)
        self.history = tuple(history)
        self.frequencies = tuple(float(f) for f in frequencies)
        self.attempts = attempts
        self.stage = stage
        self.failed_parameters = failed_parameters
        self.cause_type = cause_type
        self.input_json = input_json


@dataclass(frozen=True)
class SampledPanelPairRefinement:
    evaluation: SampledPanelForwardPairEvaluation
    result: PanelTransmissionLineResult

    @property
    def document(self):
        return PanelTransmissionLineDocument.loads(self.evaluation.input_json)


@dataclass(frozen=True)
class SampledPanelForwardPairDesign:
    parameters: tuple[float, float]
    frequencies: tuple[float, ...]
    targets: tuple[tuple[float, float], ...]
    tolerances: tuple[tuple[float, float], ...]
    impedances: tuple[tuple[float, float], ...]
    input_json: str
    history: tuple[SampledPanelForwardPairEvaluation, ...]
    result: PanelTransmissionLineResult
    refinements: tuple[SampledPanelPairRefinement, ...]

    @property
    def document(self):
        return PanelTransmissionLineDocument.loads(self.input_json)

    @property
    def residuals(self):
        return _rows(np.asarray(self.impedances)-self.targets)

    def to_dict(self):
        return dict(parameters=list(self.parameters), quantities=list(_QUANTITIES),
            frequencies_hz=list(self.frequencies), targets_ohm=[list(row) for row in self.targets],
            tolerances_ohm=[list(row) for row in self.tolerances],
            impedances_ohm=[list(row) for row in self.impedances],
            residuals_ohm=[list(row) for row in self.residuals], input=self.document.to_dict(),
            evaluations=len(self.history), history=[row.to_dict() for row in self.history],
            refinements=[dict(**r.evaluation.to_dict(),
                residuals_ohm=[list(row) for row in _rows(np.asarray(r.evaluation.impedances)-self.targets)])
                for r in self.refinements],
            scope='bounded-two-parameter-finite-frequency-panel-forward-pair-goal')


def seek_sampled_panel_forward_pair_impedances(factory, bounds, frequencies, targets, *, tolerances,
                                 initial=None, max_evaluations=64):
    """Seek two full-complex forward impedance targets at each supplied frequency.

    Strict (N, 2) full-complex forward targets at 2..64 positive frequencies;
    reserved volume/panel/joint verification at all supplied frequencies.
    No continuous-band, global or measured-accuracy certificate.
    """
    if not callable(factory):
        raise TypeError('factory must be callable')
    frequencies = _frequencies(frequencies)
    if not 2 <= len(frequencies) <= 64 or np.any(frequencies <= 0):
        raise ValueError('frequencies must contain2..64 increasing positive values')
    ranges = _numbers(bounds)
    if ranges.shape != (2, 2) or np.any(ranges <= 0) or np.any(ranges[:, 0] >= ranges[:, 1]):
        raise ValueError('bounds must contain two increasing positive finite pairs')
    target = _numbers(targets)
    tolerance = _numbers(tolerances)
    for name, values in [('targets', target), ('tolerances', tolerance)]:
        if values.shape != (len(frequencies), 2) or np.any(values <= 0):
            raise ValueError(f'{name} must be a positive finite (frequency,2) matrix')
    budget = _integer(max_evaluations, 4, 10000)
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
        return SampledPanelForwardPairGoalError(message, history, frequencies=frequencies, attempts=attempts, stage=stage,
            failed_parameters=parameters, cause_type=None if cause is None else type(cause).__name__,
            input_json=text)

    def evaluate(parameters, selected=None, stage="search"):
        nonlocal attempts, identity
        if attempts >= (budget-3 if selected is None else budget):
            raise failure('evaluation budget exhausted before target verification', 'budget', parameters)
        attempts += 1
        phase = 'factory' if selected is None else 'refinement-input'
        text = None
        try:
            if selected is None:
                candidate = factory(*parameters)
                if not isinstance(candidate, PanelTransmissionLineDocument):
                    raise TypeError('factory must return PanelTransmissionLineDocument')
                text = candidate.dumps()
                phase = 'validation'
                doc = PanelTransmissionLineDocument.loads(text)
            else:
                doc = _refinements(selected.input_json)[stage]
            text = doc.dumps(); data = doc.to_dict()["line"]
            frequency = data['frequency_hz']
            names = tuple(trace.name for trace in doc.line.cross_section.section.traces if not trace.ground)
            if not np.array_equal(frequency, frequencies) or len(names) != 2 or data['length_m'] != 0:
                raise ValueError('goal requires two signals, the exact supplied frequency vector and zero length')
            current = (tuple(frequency), names, tuple(sorted(doc.panel_options.items())))
            if selected is None and identity is not None and current != identity:
                raise ValueError('frequency, ordered signal names and panel settings must stay fixed')
            if selected is None:
                identity = current
                _refinements(text)  # Admit every future frozen refinement before fields.
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
            if matrix.shape != (len(frequencies), 2, 2) or not np.all(np.isfinite(matrix)):
                raise ValueError('mixed characteristic must contain one finite2-by-2 matrix per frequency')
            values = _numbers(np.diagonal(matrix, axis1=1, axis2=2).real)
            if np.any(values <= 0):
                raise ValueError('solver returned invalid forward impedances')
            with np.errstate(over='raise', invalid='raise', divide='raise'):
                residual = (values-target)/tolerance
            if not np.all(np.isfinite(residual)):
                raise ValueError('normalized residuals must remain finite')
        except Exception as exc:
            raise failure(f'{stage} {phase} failed: {exc}', stage+'/'+phase, parameters,
                          cause=exc, text=text) from exc
        row = SampledPanelForwardPairEvaluation(parameters, _rows(values), stage, text)
        history.append(row)
        return row, residual.ravel(), line

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
        except SampledPanelForwardPairGoalError:
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
    checked = []
    for stage in ('volume-refinement', 'panel-refinement', 'joint-refinement'):
        row, residual, refined_line = evaluate(chosen.parameters, selected=chosen, stage=stage)
        if np.any(abs(residual) > 1):
            raise failure('refined input misses one or both targets', stage+'/target',
                          chosen.parameters, text=row.input_json)
        comparisons = [chosen] + ([item.evaluation for item in checked] if stage == 'joint-refinement' else [])
        for previous in comparisons:
            if np.any(abs(np.array(row.impedances)/previous.impedances-1) > .005):
                raise failure('independent refinement exceeds relative convergence limit', stage+'/convergence',
                              chosen.parameters, text=row.input_json)
        checked.append(SampledPanelPairRefinement(row, refined_line))
    return SampledPanelForwardPairDesign(chosen.parameters, tuple(float(f) for f in frequencies), _rows(target), _rows(tolerance), chosen.impedances,
        chosen.input_json, tuple(history), line, tuple(checked))
