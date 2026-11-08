# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict saved inputs for bounded finite-thickness trace and ground-grid volumes."""
import json
import numpy as np
from .capacitance3d import Capacitance3D
from .document import _keys, _unique_object
from .sampling import _copy, _integer
from .asymmetric_volume_grid_pair import (AsymmetricVolumeGridPairCell, AsymmetricVolumeGridPairCapacitance, _INPUT_KEYS,
                        _asymmetric_volume_grid_pair_input, extract_asymmetric_volume_grid_pair_capacitance)

__all__ = ['AsymmetricVolumeGridPairCapacitanceDocument']
_SCHEMA = 'sipi.asymmetric-volume-grid-pair-capacitance/1'
_ARGUMENTS = ('pitch', 'grid_width', 'left_trace_width', 'right_trace_width', 'height', 'top_clearance',
    'backside_depth', 'eps_substrate', 'eps_above', 'eps_below', 'transverse_periods',
    'cells_per_pitch', 'cells_substrate', 'cells_above', 'cells_below', 'ground_thickness', 'cells_grid', 'trace_thickness', 'cells_trace', 'trace_gap')


class AsymmetricVolumeGridPairCapacitanceDocument:
    """Preserve twenty explicit geometry/material/count inputs and one solve.

    Canonicalization checks the original geometry, alignment and resource
    limits without generating a mesh or solving a field. Direct solve budgets
    count one field evaluation separately from cell/node/tetrahedron limits.
    """
    def __init__(self, *, pitch, grid_width, left_trace_width, right_trace_width, height, top_clearance,
                 backside_depth, eps_substrate, eps_above, eps_below,
                 transverse_periods, cells_per_pitch, cells_substrate,
                 cells_above, cells_below, ground_thickness, cells_grid, trace_thickness, cells_trace, trace_gap):
        self._assign_inputs(dict(pitch=pitch, grid_width=grid_width,
            left_trace_width=left_trace_width, right_trace_width=right_trace_width, height=height, top_clearance=top_clearance,
            backside_depth=backside_depth, eps_substrate=eps_substrate,
            eps_above=eps_above, eps_below=eps_below, transverse_periods=transverse_periods,
            cells_per_pitch=cells_per_pitch, cells_substrate=cells_substrate,
            cells_above=cells_above, cells_below=cells_below,
            ground_thickness=ground_thickness, cells_grid=cells_grid,
            trace_thickness=trace_thickness, cells_trace=cells_trace, trace_gap=trace_gap))

    def _assign_inputs(self, arguments):
        values = _asymmetric_volume_grid_pair_input(**arguments)[:20]
        self._data = dict(schema=_SCHEMA, **dict(zip(_INPUT_KEYS, values, strict=True)))

    @classmethod
    def from_dict(cls, data):
        data = _copy(data)
        _keys(data, ('schema', *_INPUT_KEYS), where='asymmetric-volume-grid-pair capacitance')
        if data['schema'] != _SCHEMA:
            raise ValueError('unsupported asymmetric-volume-grid-pair-capacitance schema')
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
        result = extract_asymmetric_volume_grid_pair_capacitance(**{
            arg: data[key] for key, arg in zip(_INPUT_KEYS, _ARGUMENTS, strict=True)})
        expected = {key: value for key, value in data.items() if key != 'schema'}
        if (type(result) is not AsymmetricVolumeGridPairCapacitance or type(result.cell) is not AsymmetricVolumeGridPairCell
                or type(result.field) is not Capacitance3D or result.inputs != expected):
            raise ValueError('asymmetric-volume-grid-pair solve changed saved input or result identity')
        cell = result.cell; field = result.field
        n = data['cells_per_pitch']; m = data['transverse_periods']
        ng = data['cells_grid']; nt = data['cells_trace']
        nz = data['cells_substrate']+data['cells_above']+data['cells_below']+ng+nt; ny = m*n
        xy = (n+1)*(ny+1)
        uncut_nodes = xy*(nz+1); uncut_tets = 6*n*ny*nz
        p = data['pitch_m']; h = data['height_m']
        ge = round(n*(data['grid_width_m']/p)/2)
        te = round(n*(data['left_trace_width_m']/p)/2)
        tr = round(n*(data['right_trace_width_m']/p)/2)
        ce = round(n*(data['trace_gap_m']/p)/2)
        touches_left = ce+2*te == ny//2
        touches_right = ce+2*tr == ny//2
        xaxis = np.arange(n+1)/n*p; yaxis = np.arange(ny+1)/n*p
        k = n-2*ge
        open_nodes = m*(k+1)**2 if k else 0
        trace_interior = (n+1)*(2*te-1+int(touches_left)+2*tr-1+int(touches_right))
        nodes = uncut_nodes-(ng-1)*(xy-open_nodes)-(nt-1)*trace_interior
        tets = uncut_tets-6*(n*ny-m*k*k)*ng-6*n*(2*te+2*tr)*nt
        ground = 2*(xy-m*max(k-1, 0)**2)+(ng-1)*4*m*k
        ground_volume = (p*(m*p)-m*(p-2*xaxis[ge])**2)*data['ground_thickness_m']
        trace_volume = p*float(yaxis[ny//2-ce]-yaxis[ny//2-ce-2*te]+yaxis[ny//2+ce+2*tr]-yaxis[ny//2+ce])*data['trace_thickness_m']
        top = h+data['trace_thickness_m']+data['top_clearance_m']
        volume = p*(m*p)*(top+data['backside_depth_m'])-ground_volume-trace_volume
        left_count = 2*(n+1)*(2*te+1)+(nt-1)*(2-int(touches_left))*(n+1)
        right_count = 2*(n+1)*(2*tr+1)+(nt-1)*(2-int(touches_right))*(n+1)
        if (cell.uncut_num_nodes != uncut_nodes or cell.uncut_num_tets != uncut_tets
                or cell.ground_metal_volume != ground_volume or cell.trace_metal_volume != trace_volume
                or cell.dielectric_volume != volume
                or not np.isfinite(cell.mesh_volume_relative_error)
                or not 0 <= cell.mesh_volume_relative_error <= 1e-12
                or cell.grid_edge_cells != ge or cell.left_trace_edge_cells != te or cell.right_trace_edge_cells != tr or cell.gap_edge_cells != ce
                or cell.resolved_trace_gap != 2*ce/n*p
                or cell.resolved_grid_width != 2*xaxis[ge]
                or cell.resolved_left_trace_width != 2*te/n*p or cell.resolved_right_trace_width != 2*tr/n*p
                or cell.nodes.shape != (nodes, 3) or cell.tets.shape != (tets, 4)
                or cell.left_nodes.shape != (left_count,) or cell.right_nodes.shape != (right_count,)
                or cell.ground_nodes.shape != (ground,)
                or cell.relative_permittivity.shape != (tets,)
                or field.names != ('left', 'right') or field.num_tets != tets
                or field.C.shape != (2, 2) or field.energy_C.shape != (2, 2)
                or field.ground_charge.shape != (2,) or field.potentials.shape != (nodes, 2)):
            raise ValueError('asymmetric-volume-grid-pair solve changed saved geometry or field shape')
        if (not np.all(np.isfinite(cell.nodes))
                or any(np.any(a < 0) or np.any(a >= nodes)
                       for a in (cell.tets, cell.left_nodes, cell.right_nodes, cell.ground_nodes))
                or not np.array_equal(cell.nodes.min(axis=0), [0., 0., -data['backside_depth_m']])
                or not np.array_equal(cell.nodes.max(axis=0), [p, m*p, top])):
            raise ValueError('asymmetric-volume-grid-pair solve changed saved coordinate extent or indices')
        x, y, z = cell.nodes.T
        tolerance = 1e-12*p
        near_y_grid = np.min(abs(y[:, None]-p*np.arange(m+1)), axis=1)
        grid = (np.minimum(x, p-x) <= cell.resolved_grid_width/2+tolerance) | (
            near_y_grid <= cell.resolved_grid_width/2+tolerance)
        expected_ground = np.flatnonzero(grid & (z >= -data['ground_thickness_m']) & (z <= 0))
        slab = (z >= h) & (z <= h+data['trace_thickness_m'])
        mid = m*p/2; half_gap = cell.resolved_trace_gap/2; width = cell.resolved_left_trace_width
        expected_left = np.flatnonzero(slab & (y >= mid-half_gap-width-tolerance) & (y <= mid-half_gap+tolerance))
        expected_right = np.flatnonzero(slab & (y >= mid+half_gap-tolerance) & (y <= mid+half_gap+cell.resolved_right_trace_width+tolerance))
        if (not np.array_equal(cell.left_nodes, expected_left)
                or not np.array_equal(cell.right_nodes, expected_right)
                or not np.array_equal(cell.ground_nodes, expected_ground)
                or not np.array_equal(np.unique(cell.tets), np.arange(nodes))):
            raise ValueError('asymmetric-volume-grid-pair solve changed saved electrode labels or node usage')
        centres = cell.nodes[cell.tets, 2].mean(axis=1)
        relative = np.where(centres < 0, data['eps_below'],
            np.where(centres > h, data['eps_above'], data['eps_substrate']))
        if not np.array_equal(cell.relative_permittivity, relative):
            raise ValueError('asymmetric-volume-grid-pair solve changed saved dielectric regions')
        return result
