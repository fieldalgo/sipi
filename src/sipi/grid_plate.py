# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Bounded static capacitance of a broad plate above a thin square ground grid."""
from dataclasses import dataclass
import json

import numpy as np
from galerkin.mesh3d import Mesh3D, box_mesh

from .capacitance3d import Capacitance3D, extract_capacitance_3d
from .network import _scalar
from .sampling import _integer

__all__ = ['GridPlateCell', 'GridPlateCapacitance', 'grid_plate_cell',
           'extract_grid_plate_capacitance']


@dataclass(frozen=True)
class GridPlateCell:
    """Detached mesh and prescribed electrode nodes for one explicit static cell.

    Coordinates are metres. The ground sheet is at z=0; the top plate is at
    z=height. Unprescribed exterior faces are insulating. Inputs and resolved
    width are both retained; there is no inferred open or wave boundary.
    """
    input_json: str
    resolved_width: float
    edge_cells: int
    nodes: np.ndarray
    tets: np.ndarray
    plate_nodes: np.ndarray
    ground_nodes: np.ndarray
    mesh_volume_relative_error: float

    def __post_init__(self):
        for name in ('nodes', 'tets', 'plate_nodes', 'ground_nodes'):
            value = np.array(getattr(self, name), dtype=float if name == 'nodes' else int, copy=True)
            value.setflags(write=False)
            object.__setattr__(self, name, value)

    @property
    def inputs(self):
        return json.loads(self.input_json)

    def to_mesh(self):
        """Return a new shared Mesh3D; pass the explicit electrode node sets.

        This export has no exterior face tags. Its connectivity and coordinates
        are detached from the cell; no field solve or boundary inference occurs.
        """
        return Mesh3D(np.array(self.nodes, copy=True), np.array(self.tets, copy=True))

    def to_dict(self, *, include_mesh=False):
        if type(include_mesh) is not bool:
            raise ValueError('include_mesh must be a boolean')
        out = dict(scope='bounded-thin-grid-plate-cell', input=self.inputs,
            resolved_width_m=self.resolved_width, edge_cells=self.edge_cells,
            num_nodes=len(self.nodes), num_tets=len(self.tets),
            mesh_volume_relative_error=self.mesh_volume_relative_error,
            mesh_included=include_mesh)
        if include_mesh:
            out.update(nodes_m=self.nodes.tolist(), tetrahedra=self.tets.tolist(),
                plate_nodes=self.plate_nodes.tolist(), ground_nodes=self.ground_nodes.tolist())
        return out


@dataclass(frozen=True)
class GridPlateCapacitance:
    """Total cell C[F] and unit-voltage field; not a per-length line model."""
    cell: GridPlateCell
    field: Capacitance3D

    @property
    def capacitance_f(self):
        return float(self.field.C[0, 0])

    @property
    def inputs(self):
        return self.cell.inputs

    def to_dict(self, *, include_fields=False):
        if type(include_fields) is not bool:
            raise ValueError('include_fields must be a boolean')
        field = self.field
        out = dict(scope='bounded-thin-grid-plate-capacitance',
            cell=self.cell.to_dict(include_mesh=include_fields),
            capacitance_f=self.capacitance_f,
            energy_capacitance_f=float(field.energy_C[0, 0]),
            stored_energy_j_at_one_volt=float(.5*field.energy_C[0, 0]),
            ground_charge_c_at_one_volt=float(field.ground_charge[0]),
            free_residual_relative=field.free_residual_relative,
            charge_balance_relative=field.charge_balance_relative,
            energy_charge_relative=field.energy_charge_relative,
            symmetry_relative=field.symmetry_relative,
            fields_included=include_fields)
        if include_fields:
            out['potential_v_at_one_volt'] = field.potentials[:, 0].tolist()
        return out


def _grid_plate_input(*, pitch, width, height, backside_depth, eps_r,
                       cells_xy, cells_above, cells_below):
    p = _scalar('pitch', pitch); w = _scalar('width', width)
    h = _scalar('height', height); d = _scalar('backside_depth', backside_depth)
    eps = _scalar('eps_r', eps_r)
    n = _integer(cells_xy, 4, 64)
    na = _integer(cells_above, 1, 64); nb = _integer(cells_below, 1, 128)
    if n % 2 or w > p:
        raise ValueError('cells_xy must be even and width must not exceed pitch')
    with np.errstate(over='ignore', under='ignore', invalid='ignore', divide='ignore'):
        edge_index = n*(w/p)/2
        box_volume = p*p*(h+d)
    edge = int(round(edge_index))
    if not 1 <= edge <= n//2 or abs(edge_index-edge) > 1e-12*max(1, abs(edge_index)):
        raise ValueError('half width must align with the lateral mesh within relative 1e-12')
    nodes = (n+1)**2*(na+nb+1); tets = 6*n*n*(na+nb)
    if nodes > 100000 or tets > 500000:
        raise ValueError('cell mesh exceeds 100000 nodes or 500000 tetrahedra')
    if not np.isfinite(box_volume) or box_volume <= 0:
        raise ValueError('geometry exceeds finite positive volume scales')
    return p, w, h, d, eps, n, na, nb, edge, box_volume


def grid_plate_cell(*, pitch, width, height, backside_depth, eps_r,
                     cells_xy, cells_above, cells_below):
    """Construct an explicitly bounded square thin-grid/plate static mesh.

    Positive SI pitch/width/height/backside_depth and real eps_r are required;
    width<=pitch. The grid consists of intersecting strips centred on the
    cell's four lateral edges, at z=0, with zero thickness. The entire upper
    face at z=height is the plate. Bottom z=-backside_depth and lateral faces
    are insulating; lateral reflection symmetry assumes a uniform broad plate.

    Explicit even cells_xy=4..64 and cells_above=1..64/cells_below=1..128
    control the mesh. Each half strip width must resolve to integer lateral
    cells within relative1e-12 roundoff. Record requested and resolved widths;
    reject off-grid geometry. Node/tetrahedron budgets apply before allocation.
    The shared box connectivity is retained with a two-part vertical grid.
    No field solve, line impedance, return-current model or frequency is inferred.
    """
    p, w, h, d, eps, n, na, nb, edge, expected_volume = _grid_plate_input(
        pitch=pitch, width=width, height=height, backside_depth=backside_depth,
        eps_r=eps_r, cells_xy=cells_xy, cells_above=cells_above, cells_below=cells_below)
    base = box_mesh(1., 1., 1., n, n, na+nb)
    ix = np.rint(base.nodes[:, 0]*n).astype(int)
    iy = np.rint(base.nodes[:, 1]*n).astype(int)
    iz = np.rint(base.nodes[:, 2]*(na+nb)).astype(int)
    axis = np.linspace(0., p, n+1)
    zaxis = np.r_[np.linspace(-d, 0., nb+1), np.linspace(0., h, na+1)[1:]]
    coords = np.column_stack((axis[ix], axis[iy], zaxis[iz]))
    mesh = Mesh3D(coords, base.tets, boundary=base.boundary, tagged_faces=base.tagged_faces)
    mesh.check()
    grounded = (ix <= edge) | (ix >= n-edge) | (iy <= edge) | (iy >= n-edge)
    ground = np.flatnonzero((iz == nb) & grounded)
    plate = np.flatnonzero(iz == na+nb)
    volumes = mesh.volumes()
    if not np.all(np.isfinite(volumes)) or np.any(volumes <= 0):
        raise ValueError('geometry exceeds finite positive tetrahedron scales')
    volume_error = float(abs(np.sum(volumes)/expected_volume-1))
    if volume_error > 1e-12:
        raise ValueError('mesh volume does not match the explicit box')
    if not np.all(mesh.nodes[ground, 2] == 0) or not np.all(mesh.nodes[plate, 2] == h):
        raise ValueError('electrodes changed their prescribed planes')
    data = dict(pitch_m=p, width_m=w, height_m=h, backside_depth_m=d, eps_r=eps,
        cells_xy=n, cells_above=na, cells_below=nb)
    return GridPlateCell(json.dumps(data, sort_keys=True, allow_nan=False),
        float(2*axis[edge]), edge, mesh.nodes, mesh.tets, plate, ground, volume_error)


def extract_grid_plate_capacitance(*, pitch, width, height, backside_depth, eps_r,
                                    cells_xy, cells_above, cells_below):
    """Extract total C[F] for the declared bounded static grid/plate cell.

    Reuse shared 3D P1 extraction with plate1V and grid0V. Its raw energy,
    charge and Maxwell checks remain unchanged. The finite insulating bottom
    must be refined independently of the mesh. Cell counts and conservation
    checks do not establish physical accuracy or an open-space boundary.
    This excludes finite sheet/trace thickness, RLGC, wave ports and radiation.
    """
    cell = grid_plate_cell(pitch=pitch, width=width, height=height,
        backside_depth=backside_depth, eps_r=eps_r, cells_xy=cells_xy,
        cells_above=cells_above, cells_below=cells_below)
    field = extract_capacitance_3d(cell.to_mesh(), eps_r=cell.inputs['eps_r'],
        conductors={'plate': cell.plate_nodes}, ground=cell.ground_nodes)
    if (type(field) is not Capacitance3D or field.names != ('plate',)
            or field.num_tets != len(cell.tets)
            or field.C.shape != (1, 1) or field.energy_C.shape != (1, 1)
            or field.ground_charge.shape != (1,)
            or field.potentials.shape != (len(cell.nodes), 1)):
        raise ValueError('field solve changed cell identity or result shapes')
    arrays = (field.C, field.energy_C, field.ground_charge, field.potentials)
    diagnostics = (field.free_residual_relative, field.charge_balance_relative,
                   field.energy_charge_relative, field.symmetry_relative)
    if (not all(np.isfinite(value) and 0 <= value <= 1e-8 for value in diagnostics)
            or not all(np.all(np.isfinite(value)) for value in arrays)
            or field.C[0, 0] <= 0 or field.energy_C[0, 0] <= 0
            or not np.all(field.potentials[cell.plate_nodes, 0] == 1)
            or not np.all(field.potentials[cell.ground_nodes, 0] == 0)):
        raise ValueError('field solve changed finite cell results or prescribed potentials')
    return GridPlateCapacitance(cell, field)
