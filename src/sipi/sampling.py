# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Shared strict sampling inputs and deterministic read-only sample generation."""
import json
from itertools import product
import numpy as np
from .document import _keys

def _numbers(value):
    raw = np.asarray(value)
    if (raw.dtype.kind not in 'iuf' or not np.all(np.isfinite(raw))
            or any(isinstance(x, (bool, np.bool_)) for x in np.asarray(value, dtype=object).flat)):
        raise ValueError('expected finite real numbers, not booleans')
    return np.array(raw, dtype=float)


def _scalar(value, *, positive=False):
    raw = _numbers(value)
    if raw.ndim or (positive and raw <= 0):
        raise ValueError('expected a finite scalar' + (' > 0' if positive else ''))
    return float(raw)


def _integer(value, lo, hi):
    if type(value) is not int or not lo <= value <= hi:
        raise ValueError(f'expected an integer in [{lo}, {hi}]')
    return value


def _copy(value):
    try:
        text = json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError('study input must contain finite JSON values') from exc
    return json.loads(text)


def _validate_sampling(sampling, parameter_names, *, forbidden=()):
    sampling = _copy(sampling)
    if not isinstance(sampling, dict):
        raise ValueError('sampling must be an object')
    kind = sampling.get('kind')
    if kind not in ('sweep', 'corners', 'uniform', 'normal'):
        raise ValueError('unsupported sampling kind')
    required = ['kind', 'variables']
    if kind != 'corners':
        required.append('count')
    if kind in ('uniform', 'normal'):
        required.append('seed')
    if kind == 'normal':
        required.append('correlation')
    _keys(sampling, required, where='sampling')
    variables = sampling['variables']
    if not isinstance(variables, list) or not 1 <= len(variables) <= 8:
        raise ValueError('use 1 to 8 independent variables')
    if kind == 'sweep' and len(variables) != 1:
        raise ValueError('sweep needs exactly one variable')
    names = []
    for variable in variables:
        fields = ('name', 'mean', 'std') if kind == 'normal' else ('name', 'lower', 'upper')
        _keys(variable, fields, where='variable')
        name = variable['name']
        if not isinstance(name, str) or name not in parameter_names or name in names:
            raise ValueError('variables must be distinct template parameter names')
        if name in forbidden:
            raise ValueError('material-evaluated studies sample geometry parameters only')
        names.append(name)
        for key in fields[1:]:
            variable[key] = _scalar(variable[key], positive=key == 'std')
        if kind != 'normal' and variable['lower'] >= variable['upper']:
            raise ValueError('variable lower must be below upper')
    if kind != 'corners':
        sampling['count'] = _integer(sampling['count'], 2, 10000)
    if kind in ('uniform', 'normal'):
        sampling['seed'] = _integer(sampling['seed'], 0, 2**32-1)
    if kind == 'normal':
        c = _numbers(sampling['correlation'])
        n = len(names)
        if (c.shape != (n, n) or np.max(abs(c-c.T)) > 1e-12
                or np.max(abs(c.diagonal()-1)) > 1e-12 or np.max(abs(c)) > 1+1e-12):
            raise ValueError('correlation must be symmetric with unit diagonal')
        c = (c+c.T)/2
        if np.linalg.eigvalsh(c)[0] < -1e-12:
            raise ValueError('correlation must be positive semidefinite')
        sampling['correlation'] = c.tolist()
    return sampling


def _sample_values(s):
    """Generate values from a validated spec, preserving the original algorithm."""
    variables = s['variables']
    if s['kind'] == 'normal':
        mean = np.array([v['mean'] for v in variables])
        std = np.array([v['std'] for v in variables])
        eigenvalues, vectors = np.linalg.eigh(s['correlation'])
        # Only accepted roundoff negatives (>=-1e-12) are clipped.
        root = (vectors*np.sqrt(np.maximum(eigenvalues, 0)))@vectors.T
        rng = np.random.Generator(np.random.PCG64(s['seed']))
        samples = mean+(rng.standard_normal((s['count'], len(variables)))@root.T)*std
    else:
        low, high = np.array([(v['lower'], v['upper']) for v in variables]).T
        if s['kind'] == 'corners':
            samples = np.array(list(product(*zip(low, high))))
        elif s['kind'] == 'sweep':
            samples = np.linspace(low, high, s['count'])
        else:
            rng = np.random.Generator(np.random.PCG64(s['seed']))
            samples = rng.uniform(low, high, size=(s['count'], len(variables)))
    if not np.all(np.isfinite(samples)):
        raise ValueError('sampling overflow; rescale distribution parameters')
    samples.setflags(write=False)
    return samples

