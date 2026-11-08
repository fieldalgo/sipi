# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict saved inputs for a bounded thin trace over a finite-thickness ground grid."""
import json
import numpy as np
from .capacitance3d import Capacitance3D
from .document import _keys, _unique_object
from .sampling import _copy, _integer
from .thick_grid_strip import (ThickGridStripCell, ThickGridStripCapacitance, _INPUT_KEYS,
                        _thick_grid_strip_input, extract_thick_grid_strip_capacitance)

__all__ = ['ThickGridStripCapacitanceDocument']
_SCHEMA = 'sipi.thick-grid-strip-capacitance/1'
_ARGUMENTS = ('pitch', 'grid_width', 'trace_width', 'height', 'top_clearance',
    'backside_depth', 'eps_substrate', 'eps_above', 'eps_below', 'transverse_periods',
    'cells_per_pitch', 'cells_substrate', 'cells_above', 'cells_below', 'ground_thickness', 'cells_grid')


class ThickGridStripCapacitanceDocument:
    """Preserve sixteen explicit geometry/material/count inputs and one solve.

    Canonicalization checks the original geometry, alignment and resource
    limits without generating a mesh or solving a field. Direct solve budgets
    count one field evaluation separately from cell/node/tetrahedron limits.
    """
    def __init__(self, *, pitch, grid_width, trace_width, height, top_clearance,
                 backside_depth, eps_substrate, eps_above, eps_below,
                 transverse_periods, cells_per_pitch, cells_substrate,
                 cells_above, cells_below, ground_thickness, cells_grid):
        self._assign_inputs(dict(pitch=pitch, grid_width=grid_width,
            trace_width=trace_width, height=height, top_clearance=top_clearance,
            backside_depth=backside_depth, eps_substrate=eps_substrate,
            eps_above=eps_above, eps_below=eps_below, transverse_periods=transverse_periods,
            cells_per_pitch=cells_per_pitch, cells_substrate=cells_substrate,
            cells_above=cells_above, cells_below=cells_below,
            ground_thickness=ground_thickness, cells_grid=cells_grid))

    def _assign_inputs(self, arguments):
        values = _thick_grid_strip_input(**arguments)[:16]
        self._data = dict(schema=_SCHEMA, **dict(zip(_INPUT_KEYS, values, strict=True)))

    @classmethod
    def from_dict(cls, data):
        data = _copy(data)
        _keys(data, ('schema', *_INPUT_KEYS), where='thick-grid-strip capacitance')
        if data['schema'] != _SCHEMA:
            raise ValueError('unsupported thick-grid-strip-capacitance schema')
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
        result = extract_thick_grid_strip_capacitance(**{
            arg: data[key] for key, arg in zip(_INPUT_KEYS, _ARGUMENTS, strict=True)})
        expected = {key: value for key, value in data.items() if key != 'schema'}
        if (type(result) is not ThickGridStripCapacitance or type(result.cell) is not ThickGridStripCell
                or type(result.field) is not Capacitance3D or result.inputs != expected):
            raise ValueError('thick-grid-strip solve changed saved input or result identity')
        cell = result.cell; field = result.field
        n = data['cells_per_pitch']; m = data['transverse_periods']
        ng = data['cells_grid']
        nz = data['cells_substrate']+data['cells_above']+data['cells_below']+ng; ny = m*n
        xy = (n+1)*(ny+1)
        uncut_nodes = xy*(nz+1); uncut_tets = 6*n*ny*nz
        p = data['pitch_m']; h = data['height_m']
        ge = round(n*(data['grid_width_m']/p)/2)
        te = round(n*(data['trace_width_m']/p)/2)
        xaxis = np.arange(n+1)/n*p; yaxis = np.arange(ny+1)/n*p
        k = n-2*ge
        open_nodes = m*(k+1)**2 if k else 0
        nodes = uncut_nodes-(ng-1)*(xy-open_nodes)
        tets = uncut_tets-6*(n*ny-m*k*k)*ng
        ground = 2*(xy-m*max(k-1, 0)**2)+(ng-1)*4*m*k
        metal = (p*(m*p)-m*(p-2*xaxis[ge])**2)*data['ground_thickness_m']
        volume = p*(m*p)*(h+data['top_clearance_m']+data['backside_depth_m'])-metal
        trace = (n+1)*(2*te+1)
        if (cell.uncut_num_nodes != uncut_nodes or cell.uncut_num_tets != uncut_tets
                or cell.metal_volume != metal or cell.dielectric_volume != volume
                or not np.isfinite(cell.mesh_volume_relative_error)
                or not 0 <= cell.mesh_volume_relative_error <= 1e-12
                or cell.grid_edge_cells != ge or cell.trace_edge_cells != te
                or cell.resolved_grid_width != 2*xaxis[ge]
                or cell.resolved_trace_width != yaxis[ny//2+te]-yaxis[ny//2-te]
                or cell.nodes.shape != (nodes, 3) or cell.tets.shape != (tets, 4)
                or cell.trace_nodes.shape != (trace,) or cell.ground_nodes.shape != (ground,)
                or cell.relative_permittivity.shape != (tets,)
                or field.names != ('trace',) or field.num_tets != tets
                or field.C.shape != (1, 1) or field.energy_C.shape != (1, 1)
                or field.ground_charge.shape != (1,) or field.potentials.shape != (nodes, 1)):
            raise ValueError('thick-grid-strip solve changed saved geometry or field shape')
        if (not np.all(np.isfinite(cell.nodes))
                or any(np.any(a < 0) or np.any(a >= nodes)
                       for a in (cell.tets, cell.trace_nodes, cell.ground_nodes))
                or not np.array_equal(cell.nodes.min(axis=0), [0., 0., -data['backside_depth_m']])
                or not np.array_equal(cell.nodes.max(axis=0), [p, m*p, h+data['top_clearance_m']])):
            raise ValueError('thick-grid-strip solve changed saved coordinate extent or indices')
        x, y, z = cell.nodes.T
        tolerance = 1e-12*p
        near_y_grid = np.min(abs(y[:, None]-p*np.arange(m+1)), axis=1)
        grid = (np.minimum(x, p-x) <= cell.resolved_grid_width/2+tolerance) | (
            near_y_grid <= cell.resolved_grid_width/2+tolerance)
        expected_ground = np.flatnonzero(grid & (z >= -data['ground_thickness_m']) & (z <= 0))
        expected_trace = np.flatnonzero((z == h) & (
            abs(y-m*p/2) <= cell.resolved_trace_width/2+tolerance))
        if (not np.array_equal(cell.trace_nodes, expected_trace)
                or not np.array_equal(cell.ground_nodes, expected_ground)
                or not np.array_equal(np.unique(cell.tets), np.arange(nodes))):
            raise ValueError('thick-grid-strip solve changed saved electrode labels or node usage')
        centres = cell.nodes[cell.tets, 2].mean(axis=1)
        relative = np.where(centres < 0, data['eps_below'],
            np.where(centres > h, data['eps_above'], data['eps_substrate']))
        if not np.array_equal(cell.relative_permittivity, relative):
            raise ValueError('thick-grid-strip solve changed saved dielectric regions')
        return result
