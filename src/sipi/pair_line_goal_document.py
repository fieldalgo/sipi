# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved geometry/material inputs for two full-loss forward impedance targets."""
import json

from .document import _keys, _unique_object
from .sampling import _copy, _integer, _scalar
from .study import ImpedanceStudyDocument
from .line_input import _source_study, _line_from_values
from .pair_line_goal import seek_forward_pair_impedances

__all__ = ['ForwardPairDesignDocument']

_SCHEMA = 'sipi.forward-pair-design/1'
_QUANTITIES = ('differential_forward_impedance_real', 'common_forward_impedance_real')


class ForwardPairDesignDocument:
    """Two ordered template/material variables and two explicit real targets.

    The nested study/3 or /4 supplies paired z_diff_forward inputs, one fixed
    positive frequency and corners sampling with exactly two positive-bounded
    variables. It is an input contract only: no preliminary quasi-static
    study runs. Fixed pitch, total stack height and material leaves retain
    their existing study rules. Targets and tolerances have exactly the keys
    differential_forward_impedance_real and common_forward_impedance_real.
    Both are in ohms and retain the full complex asymmetric coupling through
    separate forward-current launches, not uncoupled modal targets.

    Parsing checks nominal and four corner geometry/material inputs plus the
    explicit initial point (or midpoint), without meshing. Nominal and initial
    line construction also validate the fixed transmission-line/6 conductor.
    These checks do not establish validity throughout the domain, corner
    conductor validity, an extremum or a statistical assessment. Preflight
    is outside the solve attempt budget. Candidate failures during solving
    remain original failed attempts; no repair, clipping or resampling runs.

    The resulting zero-length line inputs use a 50-ohm network reference,
    which does not define either characteristic impedance target. Selected
    and refined snapshots, history and errors are the direct API's contract.
    Callbacks are not serialized. No prior saved schema is changed.
    """
    def __init__(self, study, *, conductor, targets, tolerances, initial=None,
                 max_evaluations=64):
        if isinstance(study, ImpedanceStudyDocument):
            study = study.to_dict()
        self._assign(dict(schema=_SCHEMA, study=study, conductor=conductor,
            targets_ohm=targets, tolerances_ohm=tolerances, initial=initial,
            max_evaluations=max_evaluations))

    def _assign(self, data):
        data = _copy(data)
        _keys(data, ('schema', 'study', 'conductor', 'targets_ohm',
                     'tolerances_ohm', 'initial', 'max_evaluations'), where='forward pair design')
        if data['schema'] != _SCHEMA:
            raise ValueError('unsupported forward-pair-design schema')
        for key in ('targets_ohm', 'tolerances_ohm'):
            _keys(data[key], _QUANTITIES, where=key)
            data[key] = {q: _scalar(data[key][q], positive=True) for q in _QUANTITIES}
        budget = _integer(data['max_evaluations'], 2, 10000)
        study = _source_study(data['study'], paired=True)
        sampling = study['sampling']
        if sampling['kind'] != 'corners' or len(sampling['variables']) != 2:
            raise ValueError('forward pair source requires corners with exactly two variables')
        bounds = []
        for variable in sampling['variables']:
            lower, upper = (_scalar(variable[key], positive=True) for key in ('lower', 'upper'))
            if lower >= upper:
                raise ValueError('lower parameter bound must be below upper')
            bounds.append((lower, upper))
        initial = data['initial']
        if initial is not None:
            if not isinstance(initial, list) or len(initial) != 2:
                raise ValueError('initial must be null or two ordered parameters')
            initial = [_scalar(x, positive=True) for x in initial]
            if any(x < lower or x > upper for x, (lower, upper) in zip(initial, bounds)):
                raise ValueError('initial must lie inside each variable bound')
        point = [lower+(upper-lower)/2 for lower, upper in bounds] if initial is None else initial
        nominal = _line_from_values(study, data['conductor'])
        conductor = nominal.to_dict()['conductor']
        _line_from_values(study, conductor, point)
        self._data = dict(schema=_SCHEMA, study=study, conductor=conductor,
            targets_ohm=data['targets_ohm'], tolerances_ohm=data['tolerances_ohm'],
            initial=initial, max_evaluations=budget)

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
        data = self.to_dict(); study = data['study']
        return seek_forward_pair_impedances(
            lambda a, b: _line_from_values(study, data['conductor'], [a, b]),
            [[v['lower'], v['upper']] for v in study['sampling']['variables']],
            [data['targets_ohm'][q] for q in _QUANTITIES],
            tolerances=[data['tolerances_ohm'][q] for q in _QUANTITIES],
            initial=data['initial'], max_evaluations=data['max_evaluations'])
