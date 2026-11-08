# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict saved inputs for a bounded static three-region thin strip/grid cell."""
import json
import numpy as np
from .capacitance3d import Capacitance3D
from .document import _keys, _unique_object
from .sampling import _copy, _integer
from .strip_grid import (StripGridCell, StripGridCapacitance, _INPUT_KEYS,
                        _strip_grid_input, extract_strip_grid_capacitance)

__all__ = ['StripGridCapacitanceDocument']
_SCHEMA = 'sipi.strip-grid-capacitance/1'
_ARGUMENTS = ('pitch', 'grid_width', 'trace_width', 'height', 'top_clearance',
    'backside_depth', 'eps_substrate', 'eps_above', 'eps_below', 'transverse_periods',
    'cells_per_pitch', 'cells_substrate', 'cells_above', 'cells_below')


class StripGridCapacitanceDocument:
    """Preserve fourteen explicit geometry/material/count inputs and one solve.

    Canonicalization checks the original geometry, alignment and resource
    limits without generating a mesh or solving a field. Direct solve budgets
    count one field evaluation separately from cell/node/tetrahedron limits.
    """
    def __init__(self, *, pitch, grid_width, trace_width, height, top_clearance,
                 backside_depth, eps_substrate, eps_above, eps_below,
                 transverse_periods, cells_per_pitch, cells_substrate,
                 cells_above, cells_below):
        self._assign_inputs(dict(pitch=pitch, grid_width=grid_width,
            trace_width=trace_width, height=height, top_clearance=top_clearance,
            backside_depth=backside_depth, eps_substrate=eps_substrate,
            eps_above=eps_above, eps_below=eps_below, transverse_periods=transverse_periods,
            cells_per_pitch=cells_per_pitch, cells_substrate=cells_substrate,
            cells_above=cells_above, cells_below=cells_below))

    def _assign_inputs(self, arguments):
        values = _strip_grid_input(**arguments)[:14]
        self._data = dict(schema=_SCHEMA, **dict(zip(_INPUT_KEYS, values, strict=True)))

    @classmethod
    def from_dict(cls, data):
        data = _copy(data)
        _keys(data, ('schema', *_INPUT_KEYS), where='strip-grid capacitance')
        if data['schema'] != _SCHEMA:
            raise ValueError('unsupported strip-grid-capacitance schema')
        out = cls.__new__(cls)
        out._assign_inputs({arg: data[key] for key, arg in zip(_INPUT_KEYS, _ARGUMENTS, strict=True)})
        return out

    @classmethod
    def loads(cls, text):
        def reject(value):
            raise ValueError(f'nonfinite JSON number: {value}')
        return cls.from_dict(json.loads(text, object_pairs_hook=_unique_object, parse_constant=reject))

    def dumps(self):
        return json.dumps(self._data, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)

    def to_dict(self):
        return json.loads(self.dumps())

    def analyze(self, *, max_evaluations=1):
        _integer(max_evaluations, 1, 10000)
        data = self.to_dict()
        result = extract_strip_grid_capacitance(**{
            arg: data[key] for key, arg in zip(_INPUT_KEYS, _ARGUMENTS, strict=True)})
        expected = {key: value for key, value in data.items() if key != 'schema'}
        if (type(result) is not StripGridCapacitance or type(result.cell) is not StripGridCell
                or type(result.field) is not Capacitance3D or result.inputs != expected):
            raise ValueError('strip-grid solve changed saved input or result identity')
        cell = result.cell; field = result.field
        n = data['cells_per_pitch']; m = data['transverse_periods']
        nz = data['cells_substrate']+data['cells_above']+data['cells_below']; ny = m*n
        nodes = (n+1)*(ny+1)*(nz+1); tets = 6*n*ny*nz
        p = data['pitch_m']; h = data['height_m']
        ge = round(n*(data['grid_width_m']/p)/2)
        te = round(n*(data['trace_width_m']/p)/2)
        xaxis = np.arange(n+1)/n*p; yaxis = np.arange(ny+1)/n*p
        ground = (n+1)*(ny+1)-m*max(n-2*ge-1, 0)**2
        trace = (n+1)*(2*te+1)
        if (cell.grid_edge_cells != ge or cell.trace_edge_cells != te
                or cell.resolved_grid_width != 2*xaxis[ge]
                or cell.resolved_trace_width != yaxis[ny//2+te]-yaxis[ny//2-te]
                or cell.nodes.shape != (nodes, 3) or cell.tets.shape != (tets, 4)
                or cell.trace_nodes.shape != (trace,) or cell.ground_nodes.shape != (ground,)
                or cell.relative_permittivity.shape != (tets,)
                or field.names != ('trace',) or field.num_tets != tets
                or field.C.shape != (1, 1) or field.energy_C.shape != (1, 1)
                or field.ground_charge.shape != (1,) or field.potentials.shape != (nodes, 1)):
            raise ValueError('strip-grid solve changed saved geometry or field shape')
        if (not np.all(np.isfinite(cell.nodes))
                or any(np.any(a < 0) or np.any(a >= nodes)
                       for a in (cell.tets, cell.trace_nodes, cell.ground_nodes))
                or not np.array_equal(cell.nodes.min(axis=0), [0., 0., -data['backside_depth_m']])
                or not np.array_equal(cell.nodes.max(axis=0), [p, m*p, h+data['top_clearance_m']])):
            raise ValueError('strip-grid solve changed saved coordinate extent or indices')
        if (not np.all(cell.nodes[cell.trace_nodes, 2] == h)
                or not np.all(cell.nodes[cell.ground_nodes, 2] == 0)):
            raise ValueError('strip-grid solve changed saved electrode planes')
        centres = cell.nodes[cell.tets, 2].mean(axis=1)
        relative = np.where(centres < 0, data['eps_below'],
            np.where(centres > h, data['eps_above'], data['eps_substrate']))
        if not np.array_equal(cell.relative_permittivity, relative):
            raise ValueError('strip-grid solve changed saved dielectric regions')
        return result
