# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict SI saved inputs for a bounded static thin-grid/broad-plate cell."""
import json

import numpy as np

from .capacitance3d import Capacitance3D
from .document import _keys, _unique_object
from .sampling import _copy, _integer
from .grid_plate import (GridPlateCell, GridPlateCapacitance, _grid_plate_input,
                         extract_grid_plate_capacitance)

__all__ = ['GridPlateCapacitanceDocument']

_SCHEMA = 'sipi.grid-plate-capacitance/1'
_NAMES = dict(pitch_m='pitch', width_m='width', height_m='height',
    backside_depth_m='backside_depth', eps_r='eps_r', cells_xy='cells_xy',
    cells_above='cells_above', cells_below='cells_below')


class GridPlateCapacitanceDocument:
    """Preserve bounded geometry and one static field evaluation.

    Canonicalization validates scalars, alignment and mesh budgets without
    generating a mesh or solving a field. The solve budget counts one actual
    field evaluation, separately from the declared cell/node/tetrahedron limits.
    """
    def __init__(self, *, pitch, width, height, backside_depth, eps_r,
                 cells_xy, cells_above, cells_below):
        self._assign_inputs(dict(pitch=pitch, width=width, height=height,
            backside_depth=backside_depth, eps_r=eps_r, cells_xy=cells_xy,
            cells_above=cells_above, cells_below=cells_below))

    def _assign_inputs(self, arguments):
        values = _grid_plate_input(**arguments)[:8]
        self._data = dict(schema=_SCHEMA, **dict(zip(_NAMES, values, strict=True)))

    @classmethod
    def from_dict(cls, data):
        data = _copy(data)
        _keys(data, ('schema', *_NAMES), where='grid-plate capacitance')
        if data['schema'] != _SCHEMA:
            raise ValueError('unsupported grid-plate-capacitance schema')
        out = cls.__new__(cls)
        out._assign_inputs({api: data[saved] for saved, api in _NAMES.items()})
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
        result = extract_grid_plate_capacitance(**{api: data[saved] for saved, api in _NAMES.items()})
        expected = {k: v for k, v in data.items() if k != 'schema'}
        if (type(result) is not GridPlateCapacitance or type(result.cell) is not GridPlateCell
                or type(result.field) is not Capacitance3D or result.inputs != expected):
            raise ValueError('grid-plate solve changed saved input or result identity')
        n = data['cells_xy']; na = data['cells_above']; nb = data['cells_below']
        nodes = (n+1)**2*(na+nb+1); tets = 6*n*n*(na+nb)
        edge = round(n*(data['width_m']/data['pitch_m'])/2)
        resolved = 2*np.linspace(0., data['pitch_m'], n+1)[edge]
        ground = (n+1)**2-max(n-2*edge-1, 0)**2
        cell = result.cell; field = result.field
        if (cell.edge_cells != edge or cell.resolved_width != resolved
                or cell.nodes.shape != (nodes, 3) or cell.tets.shape != (tets, 4)
                or cell.plate_nodes.shape != ((n+1)**2,) or cell.ground_nodes.shape != (ground,)
                or field.names != ('plate',) or field.num_tets != tets
                or field.C.shape != (1, 1) or field.energy_C.shape != (1, 1)
                or field.ground_charge.shape != (1,) or field.potentials.shape != (nodes, 1)):
            raise ValueError('grid-plate solve changed saved geometry or field shape')
        return result
