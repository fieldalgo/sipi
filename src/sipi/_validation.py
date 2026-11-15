# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Internal standard-library validation shared by domain and product documents.

No geometry, solver, document registry or host dependencies. Historical error
messages (including the circuit-labelled JSON-copy message) are retained for
compatibility. Domain semantics and byte-budget checks stay with their callers.
"""
import json
import math
from numbers import Real


def _keys(value, required, optional=(), *, where):
    if not isinstance(value, dict):
        raise ValueError(f'{where} must be an object')
    if set(value) - set(required) - set(optional) or set(required) - set(value):
        raise ValueError(f'{where} has missing or unknown fields')


def _number(value, where):
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(f'{where} must be a finite real number')
    return float(value)


def _name(value, where):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{where} must be a nonempty string')
    return value


def _unique_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f'duplicate JSON field: {key}')
        out[key] = value
    return out


def _json_copy(value):
    try:
        text = json.dumps(value, allow_nan=False)
        def check_keys(item):
            if isinstance(item, dict):
                if any(not isinstance(key, str) for key in item):
                    raise ValueError('JSON object keys must be strings')
                for child in item.values():
                    check_keys(child)
            elif isinstance(item, (list, tuple)):
                for child in item:
                    check_keys(child)
        check_keys(value)
        return json.loads(text)
    except (TypeError, ValueError) as exc:
        raise ValueError('circuit input must contain only finite JSON values') from exc


def _integer(name, value, minimum, maximum=None):
    if (isinstance(value, bool) or not isinstance(value, int) or value < minimum
            or (maximum is not None and value > maximum)):
        raise ValueError(f'{name} must be an integer >= {minimum}'
                         + ('' if maximum is None else f' and <= {maximum}'))
    return value


def _reject_number(value):
    raise ValueError(f'nonfinite JSON number: {value}')


def _float(value):
    result = float(value)
    if not math.isfinite(result):
        _reject_number(value)
    return result
