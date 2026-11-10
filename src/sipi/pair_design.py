# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Bounded two-parameter, two-mode impedance design with mesh verification."""
from dataclasses import dataclass
import json

import numpy as np
from scipy.optimize import least_squares

from .document import CrossSectionDocument, _mesh
from .impedance_material import (_material_input, _analyze_material, _frequency,
                                 _MaterialMeshReuse)
from .sampling import _numbers, _integer

__all__ = ['PairImpedanceEvaluation', 'PairImpedanceDesign',
           'PairImpedanceGoalError', 'seek_pair_impedances']


def _least_squares_two(objective, initial, budget, optimizer):
    """Shared numerical policy; callers own caches, budgets and diagnostics."""
    def jacobian(u):
        columns = []
        for i in range(2):
            left, right = u.copy(), u.copy()
            left[i], right[i] = max(0., u[i]-.01), min(1., u[i]+.01)
            columns.append((objective(right)-objective(left))/(right[i]-left[i]))
        return np.array(columns).T
    return optimizer(objective, initial, jac=jacobian, bounds=(0., 1.),
                     xtol=1e-4, ftol=1e-4, gtol=1e-3, max_nfev=budget-1)


@dataclass(frozen=True)
class PairImpedanceEvaluation:
    parameters: tuple[float, float]
    impedances: tuple[float, float]
    stage: str
    input_json: str
    material_evaluation_json: str | None = None

    def to_dict(self):
        out = dict(parameters=list(self.parameters), impedances_ohm=list(self.impedances),
                   stage=self.stage, input=json.loads(self.input_json))
        if self.material_evaluation_json is not None:
            out['material_evaluation'] = json.loads(self.material_evaluation_json)
        return out


class PairImpedanceGoalError(RuntimeError):
    """Completed rows, attempted evaluations and original failure context."""
    def __init__(self, message, history, *, attempts, stage, failed_parameters=None,
                 cause_type=None, input_json=None, material_evaluation_json=None):
        super().__init__(message)
        self.history = tuple(history)
        self.attempts = attempts
        self.stage = stage
        self.failed_parameters = failed_parameters
        self.cause_type = cause_type
        self.input_json = input_json
        self.material_evaluation_json = material_evaluation_json


@dataclass(frozen=True)
class PairImpedanceDesign:
    parameters: tuple[float, float]
    targets: tuple[float, float]
    tolerances: tuple[float, float]
    impedances: tuple[float, float]
    refined_impedances: tuple[float, float]
    input_json: str
    refined_input_json: str
    history: tuple[PairImpedanceEvaluation, ...]
    material_evaluation_json: str | None = None

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
        return dict(parameters=list(self.parameters), quantities=['z_diff', 'z_common'],
            targets_ohm=list(self.targets), tolerances_ohm=list(self.tolerances),
            impedances_ohm=list(self.impedances), refined_impedances_ohm=list(self.refined_impedances),
            residuals_ohm=list(self.residuals), refined_residuals_ohm=list(self.refined_residuals),
            evaluations=len(self.history), history=[row.to_dict() for row in self.history],
            input=json.loads(self.input_json), refined_input=json.loads(self.refined_input_json),
            material_evaluation=(None if self.material_evaluation_json is None
                                 else json.loads(self.material_evaluation_json)),
            scope='bounded-two-parameter-symmetric-pair-impedance-goal')


def seek_pair_impedances(factory, bounds, targets, *, tolerances, initial=None,
                         mesh=None, max_evaluations=64, frequency=None, materials=None,
                         material_factory=None):
    """Seek (z_diff, z_common) with two positive bounded factory parameters.

    factory(p0, p1) returns a CrossSection with two ordered symmetric signals.
    bounds contains two (lower, upper) pairs in the factory's units; targets
    and absolute tolerances are ordered (z_diff, z_common), in ohms. The default
    initial point is the midpoint. Fixed frequency/materials use Re(C_complex)
    and vacuum L, not a complex lossy or terminal characteristic impedance.

    Alternatively supply material_factory(p0,p1), a fixed frequency, and no
    materials. Each completed row freezes its actual mapping. Refinement reuses
    both the chosen geometry and chosen mapping without calling either factory.

    Parameters are normalized to [0,1] and residuals by tolerances. Bounded
    least_squares uses 1%-range central/one-sided difference probes, xtol=ftol
    1e-4 and gtol=1e-3. Local convergence does not establish feasibility,
    uniqueness, a global optimum or outer-domain/physical accuracy.

    Every uncached parameter evaluation, including failures and Jacobian
    probes, consumes the budget. Repeated parameter tuples use the existing
    objective cache without another attempt. Separately, material evaluations
    with identical full geometry documents and mesh controls reuse one mesh
    and vacuum capacitance within this search. They still validate and evaluate
    the current material and consume an attempt. Changed documents evict that
    entry, and refinement builds a separate mesh. Reserve one final attempt
    at the frozen selected input with edge_size/far_size/grade halved, keeping
    min_angle and all physical inputs. Both meshes must satisfy both targets.
    An initial point already satisfying both targets skips optimization but
    still requires refinement. The budget does not bound internal field solves,
    memory or elapsed time. Control errors precede factory calls; subsequent
    failures retain history and context in PairImpedanceGoalError.
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
    options = _mesh({} if mesh is None else mesh)
    if material_factory is not None:
        if not callable(material_factory) or materials is not None or frequency is None:
            raise ValueError('material_factory requires a fixed frequency, is callable, and excludes materials')
        frequency = _frequency(frequency)
        material = None
    else:
        material = _material_input(frequency, materials)
    material_text = None if material is None else json.dumps(material, sort_keys=True, allow_nan=False)
    lower, upper = ranges[:, 0], ranges[:, 1]
    span = upper-lower
    start = lower+span/2 if initial is None else _numbers(initial)
    if start.shape != (2,) or np.any(start < lower) or np.any(start > upper):
        raise ValueError('initial must contain two parameters inside bounds')
    history = []
    attempts = 0
    identity = None
    cache = {}
    material_mesh = _MaterialMeshReuse()

    def failure(message, stage, parameters=None, *, cause=None, text=None, material_json=None):
        return PairImpedanceGoalError(message, history, attempts=attempts, stage=stage,
            failed_parameters=parameters, cause_type=None if cause is None else type(cause).__name__,
            input_json=text, material_evaluation_json=(material_text if material_factory is None
                                                      and material_json is None else material_json))

    def evaluate(parameters, selected=None):
        nonlocal attempts, identity
        stage = 'search' if selected is None else 'refinement'
        if attempts >= (budget-1 if selected is None else budget):
            raise failure('evaluation budget exhausted before target verification', 'budget', parameters,
                          material_json=None if selected is None else selected.material_evaluation_json)
        attempts += 1
        phase = 'factory' if selected is None else 'input'
        text = None
        current_text = material_text if selected is None else selected.material_evaluation_json
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
            if len(names) != 2 or (identity is not None and names != identity):
                raise ValueError('two ordered signal names must stay fixed across inputs')
            identity = names
            phase = 'material'
            if selected is None:
                current = (material if material_factory is None else
                           _material_input(frequency, material_factory(*parameters)))
                current_text = None if current is None else json.dumps(current, sort_keys=True, allow_nan=False)
            else:
                current = None if current_text is None else json.loads(current_text)
            phase = 'extraction'
            line = doc.analyze() if current is None else _analyze_material(
                doc, current, 'z_diff', mesh_reuse=material_mesh)
            phase = 'diagnostic'
            if tuple(line.names) != names:
                raise ValueError('extraction changed ordered signal names')
            modes = line.even_odd()
            values = _numbers([modes['z_diff'], modes['z_common']])
            if values.shape != (2,) or np.any(values <= 0):
                raise ValueError('solver returned invalid pair impedances')
            with np.errstate(over='raise', invalid='raise', divide='raise'):
                normalized = (values-target)/tolerance
            if not np.all(np.isfinite(normalized)):
                raise ValueError('normalized residuals must remain finite')
        except Exception as exc:
            raise failure(f'{stage} {phase} failed: {exc}', stage+'/'+phase, parameters,
                          cause=exc, text=text, material_json=current_text) from exc
        row = PairImpedanceEvaluation(parameters, tuple(float(v) for v in values), stage, text, current_text)
        history.append(row)
        return row, normalized

    def physical(u):
        # Exact bound values avoid an unnecessary rounded endpoint reconstruction.
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
        except PairImpedanceGoalError:
            raise
        except Exception as exc:
            raise failure(f'optimizer failed: {exc}', 'optimizer', cause=exc) from exc
        if not result.success:
            parameters = physical(result.x)
            row = cache.get(parameters, (None, None))[0]
            raise failure('optimizer did not converge: '+str(result.message), 'convergence', parameters,
                          text=None if row is None else row.input_json,
                          material_json=None if row is None else row.material_evaluation_json)
        u = result.x
        residual = objective(u)
    chosen = cache[physical(u)][0]
    if np.any(abs(residual) > 1):
        raise failure('stationary candidate misses one or both targets', 'convergence', chosen.parameters,
                      text=chosen.input_json, material_json=chosen.material_evaluation_json)
    refined, residual = evaluate(chosen.parameters, selected=chosen)
    if np.any(abs(residual) > 1):
        raise failure('refined mesh misses target; tighten mesh settings and rerun', 'refinement/target',
                      chosen.parameters, text=refined.input_json, material_json=refined.material_evaluation_json)
    return PairImpedanceDesign(chosen.parameters, tuple(target), tuple(tolerance), chosen.impedances,
        refined.impedances, chosen.input_json, refined.input_json, tuple(history), chosen.material_evaluation_json)
