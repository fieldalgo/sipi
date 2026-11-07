# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Bracket a feasible/infeasible length boundary for explicit sampled RLGC."""
from dataclasses import dataclass, asdict
import json

from .band import NetworkBandDocument, BandAssessment, assess_band
from .circuit_document import _json_copy, _network_input
from .document import _keys, _unique_object
from .network import _scalar
from .sampling import _integer

__all__ = ['LineLengthDesignDocument', 'LineLengthDesign', 'LengthEvaluation', 'LengthGoalError']


@dataclass(frozen=True)
class LengthEvaluation:
    length_m: float
    passed: bool
    minimum_margin: float


class LengthGoalError(RuntimeError):
    """No accepted boundary; completed evaluations and a failed attempt are retained."""
    def __init__(self, message, history, *, failed_length_m=None, cause_type=None):
        super().__init__(message)
        self.history = tuple(history)
        self.failed_length_m = failed_length_m
        self.cause_type = cause_type


@dataclass(frozen=True)
class LineLengthDesign:
    feasible_length_m: float
    infeasible_length_m: float
    tolerance_m: float
    feasible: BandAssessment
    infeasible: BandAssessment
    history: tuple[LengthEvaluation, ...]
    input_json: str

    def to_dict(self):
        return dict(feasible_length_m=self.feasible_length_m,
            infeasible_length_m=self.infeasible_length_m,
            interval_width_m=self.infeasible_length_m-self.feasible_length_m,
            tolerance_m=self.tolerance_m, feasible=self.feasible.to_dict(),
            infeasible=self.infeasible.to_dict(), history=[asdict(row) for row in self.history],
            scope='sampled-band-bracket-boundary')


class LineLengthDesignDocument:
    """sipi.line-length-design/1: given RLGC, explicit band limits and a length bracket.

    The source must be an RLGC input with length_m=0; length is the only varied
    input. Zero baseline is a dimensional network contract, not a field solve.
    A feasible lower and infeasible upper endpoint are required. No monotonicity,
    global maximum, unsampled-frequency or field-convergence claim is made.
    """
    def __init__(self, network, *, limits, bounds, tolerance=1e-6, max_evaluations=64,
                 basis='single-ended'):
        self._assign(dict(schema='sipi.line-length-design/1', network=network, limits=limits,
                          bounds_m=bounds, tolerance_m=tolerance, max_evaluations=max_evaluations, basis=basis))

    def _assign(self, data):
        data = _json_copy(data)
        _keys(data, ('schema', 'network', 'limits', 'bounds_m', 'tolerance_m', 'max_evaluations', 'basis'),
              where='line length design')
        if data['schema'] != 'sipi.line-length-design/1':
            raise ValueError('unsupported line-length-design schema')
        source = data['network']
        if not isinstance(source, dict) or source.get('kind') != 'rlgc':
            raise ValueError('line length design requires explicit RLGC input')
        # Reuse the existing RLGC, frequency, reference, basis and limit validators.
        band = NetworkBandDocument(source, limits=data['limits'], basis=data['basis']).to_dict()
        if source['length_m'] != 0:
            raise ValueError('RLGC source length_m must be zero; the design bracket supplies length')
        bounds = data['bounds_m']
        if not isinstance(bounds, list) or len(bounds) != 2:
            raise ValueError('bounds_m must contain two nonnegative finite lengths')
        bounds = [_scalar('length bound', x, zero=True) for x in bounds]
        if bounds[0] >= bounds[1]:
            raise ValueError('lower length must be below upper length')
        self._data = dict(schema=data['schema'], network=band['network'], limits=band['limits'],
            basis=band['basis'], bounds_m=bounds,
            tolerance_m=_scalar('tolerance_m', data['tolerance_m']),
            max_evaluations=_integer(data['max_evaluations'], 2, 10000))

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

    def solve(self):
        data = self.to_dict(); history = []
        def evaluate(length):
            if len(history) >= data['max_evaluations']:
                raise LengthGoalError('evaluation budget exhausted before length convergence', history)
            source = dict(data['network'], length_m=length)
            try:
                network, _, _, _ = _network_input(source)
                if data['basis'] == 'mixed-mode':
                    network = network.mixed_mode()
                result = assess_band(network, data['limits'])
            except Exception as exc:
                raise LengthGoalError('length evaluation failed: '+str(exc), history,
                                      failed_length_m=length, cause_type=type(exc).__name__) from exc
            history.append(LengthEvaluation(length, result.passed, result.minimum_margin))
            return result
        lower, upper = data['bounds_m']
        feasible, infeasible = evaluate(lower), evaluate(upper)
        if not feasible.passed:
            raise LengthGoalError('lower length must satisfy every sampled limit', history)
        if infeasible.passed:
            raise LengthGoalError('upper length must violate at least one sampled limit', history)
        while upper-lower > data['tolerance_m']:
            midpoint = lower+(upper-lower)/2
            if midpoint == lower or midpoint == upper:
                raise LengthGoalError('length resolution exhausted before interval convergence', history)
            result = evaluate(midpoint)
            if result.passed:
                lower, feasible = midpoint, result
            else:
                upper, infeasible = midpoint, result
        return LineLengthDesign(lower, upper, data['tolerance_m'], feasible, infeasible,
                                tuple(history), self.dumps())
