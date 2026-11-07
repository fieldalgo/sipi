# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict saved explicit-mesh inputs for bounded static capacitance in farads."""
from __future__ import annotations

import json
import math
from numbers import Real

from galerkin.mesh3d import Mesh3D

from .capacitance3d import _prepare_inputs, extract_capacitance_3d
from .document import _unique_object

__all__ = ['Capacitance3DDocument']


def _keys(data, keys, where):
    if not isinstance(data, dict) or set(data) != set(keys):
        raise ValueError(f'{where} requires exactly {tuple(keys)}')


def _real(value):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError('coordinates and permittivity must be finite real numbers')
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError('number is outside the finite float range') from exc
    if not math.isfinite(result):
        raise ValueError('coordinates and permittivity must be finite real numbers')
    return result


def _indices(values, count):
    # Mesh3D coerces indices to integers, so validate the raw input first.
    if (not isinstance(values, list) or not values
            or any(type(x) is not int or not 0 <= x < count for x in values)):
        raise ValueError('node indices must be a nonempty list of in-range integers')
    return values


class Capacitance3DDocument:
    """Detached sipi.capacitance-3d/1 mesh, material and explicit boundary input.

    Coordinates are metres, C is total farads. Unprescribed faces are
    insulating. Normalization validates topology but does not solve a field.
    The caller is responsible for a conforming mesh and physical convergence.
    """

    def __init__(self, mesh, *, eps_r=1., conductors, ground):
        mesh, relative, names, signals, ground, _ = _prepare_inputs(mesh, eps_r, conductors, ground)
        self._data = dict(schema='sipi.capacitance-3d/1', length_unit='m',
            unprescribed_boundary='insulating',
            mesh=dict(nodes=mesh.nodes.tolist(), tetrahedra=mesh.tets.tolist()),
            eps_r=relative.tolist(),
            conductors=[dict(name=name, nodes=nodes.tolist()) for name, nodes in zip(names, signals)],
            ground=ground.tolist())

    @classmethod
    def from_dict(cls, data):
        _keys(data, ('schema', 'length_unit', 'unprescribed_boundary', 'mesh',
                     'eps_r', 'conductors', 'ground'), '3D capacitance')
        if (data['schema'] != 'sipi.capacitance-3d/1' or data['length_unit'] != 'm'
                or data['unprescribed_boundary'] != 'insulating'):
            raise ValueError('unsupported 3D capacitance schema, units or unprescribed boundary')
        _keys(data['mesh'], ('nodes', 'tetrahedra'), 'mesh')
        nodes, tets = data['mesh']['nodes'], data['mesh']['tetrahedra']
        if (not isinstance(nodes, list) or len(nodes) < 4
                or any(not isinstance(row, list) or len(row) != 3 for row in nodes)):
            raise ValueError('mesh nodes must have shape (N, 3), N >= 4')
        nodes = [[_real(x) for x in row] for row in nodes]
        if (not isinstance(tets, list) or not tets
                or any(not isinstance(row, list) or len(row) != 4 for row in tets)):
            raise ValueError('tetrahedra must have nonempty shape (T, 4)')
        tets = [_indices(row, len(nodes)) for row in tets]
        rows = data['conductors']
        if not isinstance(rows, list) or not rows:
            raise ValueError('conductors must be a nonempty ordered list')
        conductors = {}
        for row in rows:
            _keys(row, ('name', 'nodes'), 'conductor')
            name = row['name']
            if not isinstance(name, str) or not name.strip() or name in conductors:
                raise ValueError('conductor names must be nonempty unique strings')
            conductors[name] = _indices(row['nodes'], len(nodes))
        ground = _indices(data['ground'], len(nodes))
        eps = data['eps_r']
        eps = [_real(x) for x in eps] if isinstance(eps, list) else _real(eps)
        return cls(Mesh3D(nodes, tets), eps_r=eps, conductors=conductors, ground=ground)

    @classmethod
    def loads(cls, text):
        if not isinstance(text, str):
            raise TypeError('saved input must be JSON text')
        def reject(value):
            raise ValueError(f'nonfinite JSON number: {value}')
        def number(value):
            return _real(float(value))
        return cls.from_dict(json.loads(text, object_pairs_hook=_unique_object,
                                        parse_constant=reject, parse_float=number))

    def dumps(self):
        return json.dumps(self._data, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)

    def to_dict(self):
        return json.loads(self.dumps())

    def analyze(self):
        data = self._data
        return extract_capacitance_3d(Mesh3D(data['mesh']['nodes'], data['mesh']['tetrahedra']),
            eps_r=data['eps_r'], conductors={row['name']: row['nodes'] for row in data['conductors']},
            ground=data['ground'])
