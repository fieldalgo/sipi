# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Private, bounded mesh snapshots inside one synchronous two-ground request."""
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy

import numpy as np

from . import crosssection

_SCOPE = ContextVar('sipi_two_ground_mesh_scope', default=None)
_LIMIT = 2
_ARRAY_BYTES = 64 * 1024 * 1024


@contextmanager
def _mesh_reuse_scope():
    cache = OrderedDict()
    token = _SCOPE.set(cache)
    try:
        yield cache
    finally:
        cache.clear()
        _SCOPE.reset(token)


def _array_bytes(meshed):
    """Count retained ndarray payload, not Python overhead or peak memory."""
    seen = set()

    def count(value):
        if id(value) in seen:
            return 0
        seen.add(id(value))
        if isinstance(value, np.ndarray):
            return value.nbytes
        if isinstance(value, dict):
            return sum(count(v) for v in value.values())
        if isinstance(value, (tuple, list)):
            return sum(count(v) for v in value)
        return 0

    return count((vars(meshed.mesh), meshed.eps_r, meshed.tan_delta,
                  meshed.signals, meshed.ground))


def _reuse_mesh(cross, section):
    cache = _SCOPE.get()
    options = cross.mesh_options
    if cache is None:
        return section.mesh(**options)
    # Admission remains before lookup, including when this exact key is warm.
    section.mesh_settings(**options)
    producers = (type(section).mesh, crosssection.generate, crosssection.from_mesher)
    key = (cross.dumps(), tuple(id(p) for p in producers))
    if key in cache:
        cache.move_to_end(key)
        try:
            return deepcopy(cache[key][1])
        except MemoryError:
            # Cache allocation cannot turn a possible direct solve into a refusal.
            return section.mesh(**options)
    result = section.mesh(**options)
    size = _array_bytes(result)
    if size <= _ARRAY_BYTES:
        while cache and (len(cache) >= _LIMIT
                         or sum(row[2] for row in cache.values()) + size > _ARRAY_BYTES):
            cache.popitem(last=False)
        try:
            snapshot = deepcopy(result)
        except MemoryError:
            return result
        # Strong producer references prevent identity recycling within this scope.
        cache[key] = (producers, snapshot, size)
    return result
