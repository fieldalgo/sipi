# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit panel-current two-parameter forward goals."""
from dataclasses import dataclass
import json
import numpy as np
from scipy.optimize import least_squares
from .panel_line import PanelTransmissionLineDocument, PanelTransmissionLineResult
from .pair_design import _least_squares_two
from .sampling import _integer, _numbers
from .pair_line_goal import ForwardPairEvaluation, ForwardPairGoalError


__all__ = ["PanelPairRefinement", "PanelForwardPairDesign",
           "seek_panel_forward_pair_impedances"]

def _refinements(text):
    out = {}
    for stage in ('volume-refinement', 'panel-refinement', 'joint-refinement'):
        data = json.loads(text)
        if stage != 'panel-refinement':
            for key in ('edge_size', 'far_size', 'grade'):
                data['line']['cross_section']['mesh'][key] /= 2
        if stage != 'volume-refinement':
            data['panel']['panels_per_edge'] *= 2
        out[stage] = PanelTransmissionLineDocument.from_dict(data)
    return out


@dataclass(frozen=True)
class PanelPairRefinement:
    evaluation: ForwardPairEvaluation
    result: PanelTransmissionLineResult

    @property
    def document(self):
        return PanelTransmissionLineDocument.loads(self.evaluation.input_json)


@dataclass(frozen=True)
class PanelForwardPairDesign:
    parameters: tuple[float, float]
    targets: tuple[float, float]
    tolerances: tuple[float, float]
    impedances: tuple[float, float]
    input_json: str
    history: tuple[ForwardPairEvaluation, ...]
    result: PanelTransmissionLineResult
    refinements: tuple[PanelPairRefinement, ...]

    @property
    def document(self):
        return PanelTransmissionLineDocument.loads(self.input_json)

    @property
    def residuals(self):
        return tuple(a-b for a,b in zip(self.impedances, self.targets))

    def to_dict(self):
        return dict(parameters=list(self.parameters),
            quantities=["differential_forward_impedance_real", "common_forward_impedance_real"],
            targets_ohm=list(self.targets),
            tolerances_ohm=list(self.tolerances), impedances_ohm=list(self.impedances),
            residuals_ohm=list(self.residuals), input=self.document.to_dict(),
            evaluations=len(self.history), history=[row.to_dict() for row in self.history],
            refinements=[dict(**r.evaluation.to_dict(), residuals_ohm=[a-b for a,b in zip(r.evaluation.impedances,self.targets)]) for r in self.refinements],
            scope='bounded-two-parameter-panel-forward-pair-impedance-goal')


def seek_panel_forward_pair_impedances(factory, bounds, targets, *, tolerances,
                                 initial=None, max_evaluations=64):
    """Match Re(Zdd), Re(Zcc) with two positive bounded factory parameters.

    The factory returns PanelTransmissionLineDocument: two ordered signals,
    one fixed positive frequency, zero length and fixed panel controls.
    Full complex forward characteristic matrices retain asymmetric coupling.
    Targets use separate Ic=0 and Id=0 launches in power-dual mixed coordinates.

    Reserve three actual attempts for volume-only, panel-only and joint
    refinement of the frozen chosen input. All four inputs must satisfy both
    original absolute targets; relative changes are limited to 0.005 against
    the nominal result and between joint and each single-axis refinement.
    Volume refinement halves edge_size, far_size and grade; panel refinement
    doubles panels_per_edge. Ground modes and interpolation degree stay fixed.

    Every uncached failed attempt and Jacobian probe counts. The budget is
    4..10000 and does not bound internal solves, time or memory. No uniqueness,
    global optimum, outer-domain bound or measured accuracy is certified.
    See the English/Korean usage contract for input and failure details.
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
        return ForwardPairGoalError(message, history, attempts=attempts, stage=stage,
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
            if len(frequency) != 1 or frequency[0] <= 0 or len(names) != 2 or data['length_m'] != 0:
                raise ValueError('goal requires two signals, one positive frequency and zero length')
            current = (frequency[0], names, tuple(sorted(doc.panel_options.items())))
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
        checked.append(PanelPairRefinement(row, refined_line))
    return PanelForwardPairDesign(chosen.parameters, tuple(target), tuple(tolerance), chosen.impedances,
        chosen.input_json, tuple(history), line, tuple(checked))
