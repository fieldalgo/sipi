# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Bounded, private current reuse inside one synchronous paired goal request."""
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar

_SCOPE = ContextVar('sipi_two_ground_current_scope', default=None)
_LIMIT = 8


@contextmanager
def _current_reuse_scope():
    cache = OrderedDict()
    token = _SCOPE.set(cache)
    try:
        yield cache
    finally:
        cache.clear()
        _SCOPE.reset(token)


def _reuse_current_factors(section, polygons, controls, solver, compute):
    cache = _SCOPE.get()
    if cache is None:
        return compute()
    key = (id(solver), section.width, section.height, controls,
           tuple((trace.name, trace.ground) for trace in section.traces),
           tuple((p.shape, p.dtype.str, p.tobytes(order='C')) for p in polygons))
    if key in cache:
        cache.move_to_end(key)
        return cache[key][1]
    result = compute()
    # Retain the callable itself so its identity cannot be recycled in this scope.
    # Exceptions never enter the cache; every caller still performs admission.
    cache[key] = (solver, result)
    if len(cache) > _LIMIT:
        cache.popitem(last=False)
    return result
