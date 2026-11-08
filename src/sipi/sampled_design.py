# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Two-parameter real impedance goals at explicit finite frequency samples."""
from dataclasses import dataclass
import json

import numpy as np
from scipy.optimize import least_squares

from .document import CrossSectionDocument, _mesh
from .dielectric import dispersive_line
from .impedance_material import _material_input, _models, _validate_material_input
from .network import _frequencies
from .pair_design import _least_squares_two
from .quasistatic import LineParameters
from .sampling import _numbers, _integer

__all__ = ['SampledImpedanceEvaluation', 'SampledImpedanceDesign',
           'SampledImpedanceGoalError', 'seek_sampled_impedance']


def _sweep_input(frequencies, materials):
    encoded = _material_input(float(frequencies[0]), materials)
    return dict(frequencies_hz=list(map(float, frequencies)), materials=encoded['materials'])


def _analyze_sweep(document, value, quantity):
    frequencies = value['frequencies_hz']
    for frequency in frequencies:
        _validate_material_input(dict(frequency_hz=frequency, materials=value['materials']),
                                 document.section, 'z0' if quantity == 'z0' else 'z_diff')
    sweep = dispersive_line(document.section, frequencies, materials=_models(value),
                            **document.mesh_options)
    values = []
    for i in range(len(frequencies)):
        line = LineParameters(sweep.names, sweep.C[i], sweep.C0, sweep.L, -sweep.C_complex[i].imag)
        values.append(line.z0 if quantity == 'z0' else line.even_odd()[quantity])
    return sweep.names, np.array(values)


@dataclass(frozen=True)
class SampledImpedanceEvaluation:
    parameters: tuple[float, float]
    impedances: tuple[float, ...]
    stage: str
    input_json: str
    material_sweep_json: str
    quantity: str

    def to_dict(self):
        return dict(parameters=list(self.parameters), impedances_ohm=list(self.impedances),
            quantity=self.quantity, stage=self.stage, input=json.loads(self.input_json),
            material_sweep=json.loads(self.material_sweep_json))


class SampledImpedanceGoalError(RuntimeError):
    """Completed batches and available inputs at the actual failed attempt."""
    def __init__(self, message, history, *, quantity, frequencies, attempts, stage,
                 failed_parameters=None, cause_type=None, input_json=None, material_sweep_json=None):
        super().__init__(message)
        self.history = tuple(history)
        self.quantity = quantity
        self.frequencies = tuple(frequencies)
        self.attempts = attempts
        self.stage = stage
        self.failed_parameters = failed_parameters
        self.cause_type = cause_type
        self.input_json = input_json
        self.material_sweep_json = material_sweep_json


@dataclass(frozen=True)
class SampledImpedanceDesign:
    parameters: tuple[float, float]
    quantity: str
    frequencies: tuple[float, ...]
    targets: tuple[float, ...]
    tolerances: tuple[float, ...]
    impedances: tuple[float, ...]
    refined_impedances: tuple[float, ...]
    input_json: str
    refined_input_json: str
    material_sweep_json: str
    history: tuple[SampledImpedanceEvaluation, ...]

    @property
    def residuals(self):
        return tuple(a-b for a, b in zip(self.impedances, self.targets))

    @property
    def refined_residuals(self):
        return tuple(a-b for a, b in zip(self.refined_impedances, self.targets))

    @property
    def document(self):
        return CrossSectionDocument.loads(self.input_json)

    @property
    def refined_document(self):
        return CrossSectionDocument.loads(self.refined_input_json)

    def to_dict(self):
        return dict(parameters=list(self.parameters), quantity=self.quantity,
            frequencies_hz=list(self.frequencies), targets_ohm=list(self.targets),
            tolerances_ohm=list(self.tolerances), impedances_ohm=list(self.impedances),
            refined_impedances_ohm=list(self.refined_impedances),
            residuals_ohm=list(self.residuals), refined_residuals_ohm=list(self.refined_residuals),
            evaluations=len(self.history), history=[row.to_dict() for row in self.history],
            input=json.loads(self.input_json), refined_input=json.loads(self.refined_input_json),
            material_sweep=json.loads(self.material_sweep_json),
            scope='bounded-two-parameter-finite-frequency-impedance-goal')


def seek_sampled_impedance(factory, bounds, frequencies, targets, *, tolerances,
                           quantity='z0', initial=None, mesh=None, max_evaluations=64,
                           materials=None, material_factory=None):
    """Seek one real quasi-static quantity at 2..64 specified frequency samples.

    Two positive bounded factory parameters drive geometry and optionally
    material_factory(p0,p1). Fixed materials exclude material_factory; absent
    both means empty overrides. Frequencies are strictly increasing, finite
    and nonnegative. Targets/tolerances have the same length, in ohms.
    z0 needs one signal; z_diff/z_common use the existing symmetric pair guard.
    All quantities use Re(C_complex) and vacuum L, not complex lossy impedance.

    Every uncached geometry/material/field batch attempt, including failures
    and Jacobian probes, counts once. A batch meshes once for C0 and all sampled
    complex capacitances. The budget does not count internal solves or limit
    time/memory. One final frozen geometry/model refinement is reserved, halving
    resolved edge_size/far_size/grade. Both meshes must meet every sampled goal.

    Shared normalized two-parameter least_squares uses 1%-interval Jacobian
    probes and xtol=ftol=1e-4, gtol=1e-3. No continuous-band, global uniqueness,
    material identification or physical accuracy guarantee follows. Callbacks
    must be deterministic; inputs and per-batch model snapshots permit replay.
    """
    if not callable(factory):
        raise TypeError('factory must be callable')
    ranges = _numbers(bounds)
    if ranges.shape != (2, 2) or np.any(ranges <= 0) or np.any(ranges[:, 0] >= ranges[:, 1]):
        raise ValueError('bounds must contain two increasing positive finite pairs')
    frequencies = _frequencies(frequencies)
    if not 2 <= len(frequencies) <= 64:
        raise ValueError('frequencies must contain 2 to 64 ordered samples')
    if not isinstance(quantity, str) or quantity not in ('z0', 'z_diff', 'z_common'):
        raise ValueError('quantity must be z0, z_diff or z_common')
    target, tolerance = _numbers(targets), _numbers(tolerances)
    for name, values in [('targets', target), ('tolerances', tolerance)]:
        if values.shape != frequencies.shape or np.any(values <= 0):
            raise ValueError(f'{name} must contain one positive finite value per frequency')
    budget = _integer(max_evaluations, 2, 10000)
    options = _mesh({} if mesh is None else mesh)
    if material_factory is not None:
        if not callable(material_factory) or materials is not None:
            raise ValueError('material_factory must be callable and excludes materials')
        fixed = None
    else:
        fixed = _sweep_input(frequencies, {} if materials is None else materials)
    fixed_text = None if fixed is None else json.dumps(fixed, sort_keys=True, allow_nan=False)
    lower, upper = ranges[:, 0], ranges[:, 1]
    span = upper-lower
    start = lower+span/2 if initial is None else _numbers(initial)
    if start.shape != (2,) or np.any(start < lower) or np.any(start > upper):
        raise ValueError('initial must contain two parameters inside bounds')
    history, cache = [], {}
    attempts, identity = 0, None

    def failure(message, stage, parameters=None, *, cause=None, text=None, sweep_text=None):
        return SampledImpedanceGoalError(message, history, quantity=quantity,
            frequencies=frequencies, attempts=attempts, stage=stage, failed_parameters=parameters,
            cause_type=None if cause is None else type(cause).__name__, input_json=text,
            material_sweep_json=(fixed_text if material_factory is None and sweep_text is None else sweep_text))

    def evaluate(parameters, selected=None):
        nonlocal attempts, identity
        stage = 'search' if selected is None else 'refinement'
        if attempts >= (budget-1 if selected is None else budget):
            raise failure('evaluation budget exhausted before target verification', 'budget', parameters,
                          sweep_text=None if selected is None else selected.material_sweep_json)
        attempts += 1
        phase = 'factory' if selected is None else 'input'
        text = None
        current_text = fixed_text if selected is None else selected.material_sweep_json
        try:
            if selected is None:
                section = factory(*parameters)
                phase = 'validation'
                doc = CrossSectionDocument(section, mesh=options)
            else:
                requested = CrossSectionDocument.loads(selected.input_json)
                section = requested.section
                fine = section.mesh_settings(**requested.mesh_options)
                for key in ('edge_size', 'far_size', 'grade'):
                    fine[key] /= 2
                doc = CrossSectionDocument(section, mesh=fine)
            text = doc.dumps()
            names = tuple(t.name for t in doc.section.traces if not t.ground)
            if len(names) != (1 if quantity == 'z0' else 2) or (identity is not None and names != identity):
                raise ValueError('quantity needs fixed ordered scalar or paired signal names')
            identity = names
            phase = 'material'
            if selected is None:
                current = fixed if material_factory is None else _sweep_input(frequencies, material_factory(*parameters))
                current_text = json.dumps(current, sort_keys=True, allow_nan=False)
            else:
                current = json.loads(current_text)
            phase = 'extraction'
            actual_names, values = _analyze_sweep(doc, current, quantity)
            phase = 'diagnostic'
            values = _numbers(values)
            if tuple(actual_names) != names or values.shape != target.shape or np.any(values <= 0):
                raise ValueError('solver returned invalid names or sampled impedances')
            with np.errstate(over='raise', invalid='raise', divide='raise'):
                normalized = (values-target)/tolerance
            if not np.all(np.isfinite(normalized)):
                raise ValueError('normalized residuals must remain finite')
        except Exception as exc:
            raise failure(f'{stage} {phase} failed: {exc}', stage+'/'+phase, parameters,
                          cause=exc, text=text, sweep_text=current_text) from exc
        row = SampledImpedanceEvaluation(parameters, tuple(float(v) for v in values), stage, text, current_text, quantity)
        history.append(row)
        return row, normalized

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
            result = _least_squares_two(objective, u, budget, least_squares)
        except SampledImpedanceGoalError:
            raise
        except Exception as exc:
            raise failure(f'optimizer failed: {exc}', 'optimizer', cause=exc) from exc
        if not result.success:
            parameters = physical(result.x)
            row = cache.get(parameters, (None, None))[0]
            raise failure('optimizer did not converge: '+str(result.message), 'convergence', parameters,
                text=None if row is None else row.input_json,
                sweep_text=None if row is None else row.material_sweep_json)
        u = result.x
        residual = objective(u)
    chosen = cache[physical(u)][0]
    if np.any(abs(residual) > 1):
        raise failure('stationary candidate misses sampled targets', 'convergence', chosen.parameters,
                      text=chosen.input_json, sweep_text=chosen.material_sweep_json)
    refined, residual = evaluate(chosen.parameters, selected=chosen)
    if np.any(abs(residual) > 1):
        raise failure('refined mesh misses sampled targets; tighten mesh settings and rerun',
                      'refinement/target', chosen.parameters, text=refined.input_json,
                      sweep_text=refined.material_sweep_json)
    return SampledImpedanceDesign(chosen.parameters, quantity, tuple(frequencies), tuple(target),
        tuple(tolerance), chosen.impedances, refined.impedances, chosen.input_json,
        refined.input_json, chosen.material_sweep_json, tuple(history))
