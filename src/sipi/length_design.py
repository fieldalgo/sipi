# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Bracket a sampled length boundary from explicit or once-extracted RLGC."""
from dataclasses import dataclass, asdict
import json

import numpy as np

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
    def __init__(self, message, history, *, failed_length_m=None, cause_type=None, source_evaluation=None):
        super().__init__(message)
        self.history = tuple(history)
        self.failed_length_m = failed_length_m
        self.cause_type = cause_type
        self._source_evaluation_json = (None if source_evaluation is None else
                                       json.dumps(source_evaluation, sort_keys=True, allow_nan=False))

    @property
    def source_evaluation(self):
        return None if self._source_evaluation_json is None else json.loads(self._source_evaluation_json)


@dataclass(frozen=True)
class LineLengthDesign:
    feasible_length_m: float
    infeasible_length_m: float
    tolerance_m: float
    feasible: BandAssessment
    infeasible: BandAssessment
    history: tuple[LengthEvaluation, ...]
    input_json: str
    resolved_network_json: str | None = None
    extraction: object | None = None

    def to_dict(self):
        out = dict(feasible_length_m=self.feasible_length_m,
            infeasible_length_m=self.infeasible_length_m,
            interval_width_m=self.infeasible_length_m-self.feasible_length_m,
            tolerance_m=self.tolerance_m, feasible=self.feasible.to_dict(),
            infeasible=self.infeasible.to_dict(), history=[asdict(row) for row in self.history],
            scope='sampled-band-bracket-boundary')
        if self.resolved_network_json is not None:
            out['source_evaluation'] = dict(phase='complete', field_extractions=1,
                length_evaluations=len(self.history), evaluations=1+len(self.history),
                resolved_network=json.loads(self.resolved_network_json))
        return out


class LineLengthDesignDocument:
    """Saved band-constrained length brackets, without global-optimum claims.

    Version 1 requires an RLGC input with length_m=0; length is the only varied
    input. Zero baseline is a dimensional network contract, not a field solve.
    A feasible lower and infeasible upper endpoint are required. No monotonicity,
    global maximum, unsampled-frequency or field-convergence claim is made.
    Version 2 instead accepts a zero-length transmission/volume line document:
    extract its complete frequency grid once, then hold RLGC fixed. The one
    extraction attempt and each length-network attempt consume the saved budget.
    An extraction job can contain multiple internal field solves; the budget is
    not a bound on their count, memory or time. Parsing never solves fields.
    """
    def __init__(self, network, *, limits, bounds, tolerance=1e-6, max_evaluations=64,
                 basis='single-ended', schema='sipi.line-length-design/1'):
        self._assign(dict(schema=schema, network=network, limits=limits,
                          bounds_m=bounds, tolerance_m=tolerance, max_evaluations=max_evaluations, basis=basis))

    def _assign(self, data):
        data = _json_copy(data)
        _keys(data, ('schema', 'network', 'limits', 'bounds_m', 'tolerance_m', 'max_evaluations', 'basis'),
              where='line length design')
        if data['schema'] not in ('sipi.line-length-design/1', 'sipi.line-length-design/2'):
            raise ValueError('unsupported line-length-design schema')
        field = data['schema'] == 'sipi.line-length-design/2'
        source = data['network']
        kinds = ('transmission-line', 'volume-line') if field else ('rlgc',)
        if not isinstance(source, dict) or source.get('kind') not in kinds:
            raise ValueError('line length design requires '+('a transmission/volume field source' if field else 'explicit RLGC input'))
        # Reuse the existing RLGC, frequency, reference, basis and limit validators.
        band = NetworkBandDocument(source, limits=data['limits'], basis=data['basis']).to_dict()
        baseline = band['network']['document'] if field else band['network']
        if baseline['length_m'] != 0:
            raise ValueError('source length_m must be zero; the design bracket supplies length')
        bounds = data['bounds_m']
        if not isinstance(bounds, list) or len(bounds) != 2:
            raise ValueError('bounds_m must contain two nonnegative finite lengths')
        bounds = [_scalar('length bound', x, zero=True) for x in bounds]
        if bounds[0] >= bounds[1]:
            raise ValueError('lower length must be below upper length')
        self._data = dict(schema=data['schema'], network=band['network'], limits=band['limits'],
            basis=band['basis'], bounds_m=bounds,
            tolerance_m=_scalar('tolerance_m', data['tolerance_m']),
            max_evaluations=_integer(data['max_evaluations'], 3 if field else 2, 10000))

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
        field = data['schema'] == 'sipi.line-length-design/2'
        attempts = length_attempts = field_attempts = 0
        source = data['network']; extraction = None; resolved_json = None

        def failure(message, phase, *, failed_length_m=None, cause_type=None):
            metadata = (None if not field else dict(phase=phase, field_extractions=field_attempts,
                length_evaluations=length_attempts, evaluations=attempts,
                resolved_network=None if resolved_json is None else json.loads(resolved_json)))
            return LengthGoalError(message, history, failed_length_m=failed_length_m,
                                   cause_type=cause_type, source_evaluation=metadata)

        if field:
            field_attempts = attempts = 1
            try:
                document, _, frequency, ports = _network_input(source)
                extraction = document.analyze()
                if (not np.array_equal(extraction.frequency, frequency)
                        or tuple(extraction.network.port_names) != tuple(ports)):
                    raise ValueError('extraction changed frequency or port order')
                reference = extraction.network.z_ref
                if not np.all(reference == reference[0]):
                    raise ValueError('extracted RLGC requires one common real port reference')
                source = dict(kind='rlgc', frequency_hz=extraction.frequency.tolist(),
                    R=extraction.R.tolist(), L=extraction.L.tolist(), G=extraction.G.tolist(), C=extraction.C.tolist(),
                    length_m=0., reference_ohms=float(reference[0]), names=list(extraction.names))
                resolved_json = json.dumps(source, sort_keys=True, allow_nan=False)
            except Exception as exc:
                raise failure('field extraction failed: '+str(exc), 'extraction', cause_type=type(exc).__name__) from exc

        def evaluate(length):
            nonlocal attempts, length_attempts
            if attempts >= data['max_evaluations']:
                raise failure('evaluation budget exhausted before length convergence', 'budget')
            attempts += 1; length_attempts += 1
            try:
                network, _, _, _ = _network_input(dict(source, length_m=length))
                if data['basis'] == 'mixed-mode':
                    network = network.mixed_mode()
                result = assess_band(network, data['limits'])
            except Exception as exc:
                raise failure('length evaluation failed: '+str(exc), 'network',
                              failed_length_m=length, cause_type=type(exc).__name__) from exc
            history.append(LengthEvaluation(length, result.passed, result.minimum_margin))
            return result
        lower, upper = data['bounds_m']
        feasible, infeasible = evaluate(lower), evaluate(upper)
        if not feasible.passed:
            raise failure('lower length must satisfy every sampled limit', 'bracket')
        if infeasible.passed:
            raise failure('upper length must violate at least one sampled limit', 'bracket')
        while upper-lower > data['tolerance_m']:
            midpoint = lower+(upper-lower)/2
            if midpoint == lower or midpoint == upper:
                raise failure('length resolution exhausted before interval convergence', 'resolution')
            result = evaluate(midpoint)
            if result.passed:
                lower, feasible = midpoint, result
            else:
                upper, infeasible = midpoint, result
        return LineLengthDesign(lower, upper, data['tolerance_m'], feasible, infeasible,
                                tuple(history), self.dumps(), resolved_json, extraction)
