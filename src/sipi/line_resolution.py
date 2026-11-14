# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit finite mesh/domain agreement, not a field error certificate."""
from dataclasses import dataclass
from types import MappingProxyType
from collections.abc import Mapping

import numpy as np

from .line_model import TransmissionLineDocument, TransmissionLineResult
from .network import _scalar
from .sampling import _integer

__all__ = ['ResolutionTolerance', 'ResolutionComparison', 'ResolutionFailure',
           'ResolutionEvaluation', 'LineResolutionAssessment', 'assess_line_resolution']

_QUANTITIES = ('R', 'L_internal', 'L_external', 'C', 'G', 'C0')


@dataclass(frozen=True)
class ResolutionTolerance:
    """Elementwise absolute SI allowance plus relative times max(|a|,|b|).

    Both zero requests exact agreement. No denominator floor or inferred
    absolute tolerance is applied to zero or small mutual entries.
    """
    relative: float
    absolute: float

    def __post_init__(self):
        for key in ('relative', 'absolute'):
            object.__setattr__(self, key, _scalar(key, getattr(self, key), zero=True))
        if self.relative > 1:
            raise ValueError('relative resolution tolerance must be at most one')


def _frozen_arrays(values):
    result = {}
    for key, value in values.items():
        array = np.array(value, dtype=float, copy=True)
        if not np.all(np.isfinite(array)):
            raise ValueError('resolution comparison is not finite')
        array.setflags(write=False)
        result[key] = array
    return MappingProxyType(result)


@dataclass(frozen=True)
class ResolutionComparison:
    """Actual differences and allowances, each (frequency, signal, signal)."""
    stage: str
    reference_index: int
    evaluation_index: int
    differences: Mapping
    allowances: Mapping

    def __post_init__(self):
        object.__setattr__(self, 'differences', _frozen_arrays(self.differences))
        object.__setattr__(self, 'allowances', _frozen_arrays(self.allowances))

    @property
    def accepted(self):
        return all(np.all(value <= self.allowances[key]) for key, value in self.differences.items())


@dataclass(frozen=True)
class ResolutionFailure:
    stage: str
    input_json: str
    kind: str
    message: str


@dataclass(frozen=True)
class ResolutionEvaluation:
    stage: str
    input_json: str
    result: TransmissionLineResult


@dataclass(frozen=True)
class LineResolutionAssessment:
    """Finite agreement for selected quantities only; no accuracy guarantee.

    Mesh compares the finer input against the original. Each larger domain
    compares against that finer input, using exactly the same mesh settings.
    A failed solve keeps completed evaluations and its exact input/stage.
    """
    tolerances: Mapping
    evaluations: tuple
    comparisons: tuple
    expected_evaluations: int
    failure: ResolutionFailure | None = None

    def __post_init__(self):
        object.__setattr__(self, 'tolerances', MappingProxyType(dict(self.tolerances)))
        object.__setattr__(self, 'evaluations', tuple(self.evaluations))
        object.__setattr__(self, 'comparisons', tuple(self.comparisons))

    @property
    def completed(self):
        return self.failure is None and len(self.evaluations) == self.expected_evaluations

    @property
    def accepted(self):
        return self.completed and all(row.accepted for row in self.comparisons)


def _metric(result, key):
    if key == 'L_internal':
        return np.zeros_like(result.R) if result.conductor is None else result.conductor.L_internal
    if key in ('C0', 'L_external'):
        value = result.dielectric.C0 if key == 'C0' else result.dielectric.L
        return np.broadcast_to(value, result.C.shape)
    return getattr(result, key)


def _compare(reference, actual, tolerances, stage, reference_index, evaluation_index):
    if reference.names != actual.names or not np.array_equal(reference.frequency, actual.frequency):
        raise ValueError('resolution evaluations changed signal or frequency order')
    differences, allowances = {}, {}
    for key, tolerance in tolerances.items():
        a, b = _metric(reference, key), _metric(actual, key)
        if a.shape != b.shape:
            raise ValueError('resolution evaluations changed matrix shape')
        with np.errstate(over='ignore', invalid='ignore'):
            differences[key] = abs(b-a)
            allowances[key] = tolerance.absolute+tolerance.relative*np.maximum(abs(a), abs(b))
    return ResolutionComparison(stage, reference_index, evaluation_index, differences, allowances)


def _outer_input(outer, refined):
    if not isinstance(outer, TransmissionLineDocument):
        raise TypeError('outer documents must be TransmissionLineDocument objects')
    data, expected = outer.to_dict(), refined.to_dict()
    geometry, baseline = data['cross_section'], expected['cross_section']
    if len(geometry['layers']) != len(baseline['layers']):
        raise ValueError('outer expansion must preserve all internal interfaces')
    width, old_width = geometry['box']['width'], baseline['box']['width']
    height, old_height = geometry['layers'][-1]['thickness'], baseline['layers'][-1]['thickness']
    if width < old_width or height < old_height or (width == old_width and height == old_height):
        raise ValueError('each outer document must strictly expand width or top padding without shrinking')
    if width != old_width and baseline['box']['sides'] != 'open':
        raise ValueError('outer expansion must not move a grounded side wall')
    if height != old_height and baseline['box']['top'] != 'open':
        raise ValueError('outer expansion must not move a grounded top plane')
    geometry['box']['width'] = old_width
    geometry['layers'][-1]['thickness'] = old_height
    if data != expected:
        raise ValueError('outer documents must preserve refined mesh, physical geometry, materials and ports')
    return TransmissionLineDocument.loads(outer.dumps())


def assess_line_resolution(line, *, outer_documents, tolerances, refinement_factor=.5, max_solves=4):
    """Evaluate original, finer and explicitly larger domains without repairs.

    Uses the line document's resolved edge_size/far_size/grade. Only those three settings are
    scaled; all material/geometry/frequency/port inputs are retained. Each
    outer document must use those finer settings and expand an open side or
    the topmost layer under an open top, without moving traces/interfaces.
    At least one explicit outer document is required. No shape change or
    shift of a physical ground plane counts as numerical refinement.

    tolerances maps selected R, L_internal, L_external, C, G, C0 quantities
    to ResolutionTolerance objects in their SI units. Every matrix entry at
    every supplied frequency must meet its allowance. Unselected quantities
    are not assessed. max_solves bounds full line evaluations, not individual
    linear solves inside each extraction. Preflight performs no field work.

    Accepted finite differences are necessary observations, not an absolute
    error bound, asymptotic convergence proof or measured-accuracy certificate.
    A completed assessment may be unaccepted. Exceptions during evaluation
    retain completed results and stop subsequent solves; interrupts propagate.
    """
    if not isinstance(line, TransmissionLineDocument):
        raise TypeError('line must be a TransmissionLineDocument')
    factor = _scalar('refinement_factor', refinement_factor)
    if factor >= 1:
        raise ValueError('refinement_factor must be below one')
    limit = _integer(max_solves, 3, 16)
    if not isinstance(outer_documents, (tuple, list)) or not outer_documents:
        raise ValueError('provide one or more explicit outer documents')
    expected_count = 2+len(outer_documents)
    if expected_count > limit:
        raise ValueError('resolution evaluation budget exceeded before any field solve')
    if (not isinstance(tolerances, Mapping) or not tolerances
            or any(key not in _QUANTITIES or not isinstance(value, ResolutionTolerance)
                   for key, value in tolerances.items())):
        raise ValueError('tolerances must select named quantities with ResolutionTolerance values')
    tolerances = dict(tolerances)
    base = TransmissionLineDocument.loads(line.dumps())
    raw = base.to_dict()
    mesh = raw['cross_section']['mesh']
    if not {'edge_size', 'far_size', 'grade'} <= set(mesh):
        raise ValueError('resolution assessment requires explicit edge_size, far_size and grade')
    for key in ('edge_size', 'far_size', 'grade'):
        mesh[key] *= factor
    refined = TransmissionLineDocument.from_dict(raw)
    outer = [_outer_input(doc, refined) for doc in outer_documents]
    stages = [('base', base), ('mesh', refined)]+[(f'outer:{i}', doc) for i, doc in enumerate(outer)]
    evaluations, comparisons = [], []
    for stage, doc in stages:
        text = doc.dumps()
        try:
            result = doc.analyze()
            evaluations.append(ResolutionEvaluation(stage, text, result))
            if stage != 'base':
                index = 0 if stage == 'mesh' else 1
                comparisons.append(_compare(evaluations[index].result, result, tolerances,
                                             stage, index, len(evaluations)-1))
        except Exception as error:
            failure = ResolutionFailure(stage, text, type(error).__name__, str(error))
            return LineResolutionAssessment(tolerances, evaluations, comparisons, expected_count, failure)
    return LineResolutionAssessment(tolerances, evaluations, comparisons, expected_count)
