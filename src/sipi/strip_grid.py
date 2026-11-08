# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Bounded static thin trace and square ground-grid cells with three dielectrics."""
from dataclasses import dataclass
import json
import numpy as np
from galerkin.mesh3d import Mesh3D, box_mesh
from .capacitance3d import Capacitance3D, extract_capacitance_3d
from .network import _scalar
from .sampling import _integer

__all__ = ['StripGridCell', 'StripGridCapacitance', 'strip_grid_cell',
           'extract_strip_grid_capacitance']

_INPUT_KEYS = ('pitch_m', 'grid_width_m', 'trace_width_m', 'height_m',
    'top_clearance_m', 'backside_depth_m', 'eps_substrate', 'eps_above', 'eps_below',
    'transverse_periods', 'cells_per_pitch', 'cells_substrate', 'cells_above', 'cells_below')


@dataclass(frozen=True)
class StripGridCell:
    """Detached explicitly bounded geometry and piecewise dielectric values.

    Thin grid0V lies at z=0; thin finite-width trace1V at z=height. Other
    exterior faces are insulating. Inputs use metres and relative permittivity.
    Direct construction does not replace the factory's geometric validation.
    """
    input_json: str
    resolved_grid_width: float
    resolved_trace_width: float
    grid_edge_cells: int
    trace_edge_cells: int
    nodes: np.ndarray
    tets: np.ndarray
    trace_nodes: np.ndarray
    ground_nodes: np.ndarray
    relative_permittivity: np.ndarray
    mesh_volume_relative_error: float

    def __post_init__(self):
        for name in ('nodes', 'tets', 'trace_nodes', 'ground_nodes', 'relative_permittivity'):
            value = np.array(getattr(self, name),
                dtype=float if name in ('nodes', 'relative_permittivity') else int, copy=True)
            value.setflags(write=False)
            object.__setattr__(self, name, value)

    @property
    def inputs(self):
        return json.loads(self.input_json)

    def to_mesh(self):
        """Export a detached shared Mesh3D without inferred face tags.

        Pass relative_permittivity and the explicit electrode node sets when
        solving. Export does not assemble a field or infer an open boundary.
        """
        return Mesh3D(np.array(self.nodes, copy=True), np.array(self.tets, copy=True))

    def to_dict(self, *, include_mesh=False):
        if type(include_mesh) is not bool:
            raise ValueError('include_mesh must be a boolean')
        out = dict(scope='bounded-thin-strip-grid-cell', input=self.inputs,
            resolved_grid_width_m=self.resolved_grid_width,
            resolved_trace_width_m=self.resolved_trace_width,
            grid_edge_cells=self.grid_edge_cells, trace_edge_cells=self.trace_edge_cells,
            num_nodes=len(self.nodes), num_tets=len(self.tets),
            mesh_volume_relative_error=self.mesh_volume_relative_error,
            mesh_included=include_mesh)
        if include_mesh:
            out.update(nodes_m=self.nodes.tolist(), tetrahedra=self.tets.tolist(),
                trace_nodes=self.trace_nodes.tolist(), ground_nodes=self.ground_nodes.tolist(),
                relative_permittivity=self.relative_permittivity.tolist())
        return out


@dataclass(frozen=True)
class StripGridCapacitance:
    """Total bounded-cell C[F] and unit-voltage field, not a line RLGC model."""
    cell: StripGridCell
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
        f = self.field
        out = dict(scope='bounded-thin-strip-grid-capacitance',
            cell=self.cell.to_dict(include_mesh=include_fields),
            capacitance_f=self.capacitance_f, energy_capacitance_f=float(f.energy_C[0, 0]),
            stored_energy_j_at_one_volt=float(.5*f.energy_C[0, 0]),
            ground_charge_c_at_one_volt=float(f.ground_charge[0]),
            free_residual_relative=f.free_residual_relative,
            charge_balance_relative=f.charge_balance_relative,
            energy_charge_relative=f.energy_charge_relative,
            symmetry_relative=f.symmetry_relative, fields_included=include_fields)
        if include_fields:
            out['potential_v_at_one_volt'] = f.potentials[:, 0].tolist()
        return out


def _strip_grid_input(*, pitch, grid_width, trace_width, height, top_clearance, backside_depth,
                    eps_substrate, eps_above, eps_below, transverse_periods, cells_per_pitch,
                    cells_substrate, cells_above, cells_below):
    p = _scalar('pitch', pitch); g = _scalar('grid_width', grid_width)
    w = _scalar('trace_width', trace_width); h = _scalar('height', height)
    a = _scalar('top_clearance', top_clearance); d = _scalar('backside_depth', backside_depth)
    es = _scalar('eps_substrate', eps_substrate); ea = _scalar('eps_above', eps_above)
    eb = _scalar('eps_below', eps_below)
    m = _integer(transverse_periods, 1, 9); n = _integer(cells_per_pitch, 4, 32)
    ns = _integer(cells_substrate, 1, 128)
    na = _integer(cells_above, 1, 128); nb = _integer(cells_below, 1, 128)
    if m % 2 != 1 or n % 2 or g > p or w > m*p:
        raise ValueError('require odd transverse periods, even pitch cells, grid<=pitch and trace<=box')
    def edge(value, limit):
        index = n*(value/p)/2
        resolved = int(round(index))
        if not 1 <= resolved <= limit or abs(index-resolved) > 1e-12*max(1, abs(index)):
            raise ValueError('half width must align with the mesh within relative 1e-12')
        return resolved
    ge = edge(g, n//2); te = edge(w, m*n//2)
    nz = nb+ns+na; ny = m*n
    nodes = (n+1)*(ny+1)*(nz+1); tets = 6*n*ny*nz
    if nodes > 100000 or tets > 500000:
        raise ValueError('cell mesh exceeds 100000 nodes or 500000 tetrahedra')
    volume = p*(m*p)*(h+a+d)
    if not np.isfinite(volume) or volume <= 0 or not np.isfinite(h+a) or h+a <= h:
        raise ValueError('geometry exceeds finite positive box or top-clearance scales')
    return p, g, w, h, a, d, es, ea, eb, m, n, ns, na, nb, ge, te, volume


def strip_grid_cell(*, pitch, grid_width, trace_width, height, top_clearance, backside_depth,
                    eps_substrate, eps_above, eps_below, transverse_periods, cells_per_pitch,
                    cells_substrate, cells_above, cells_below):
    """Construct a bounded finite-width thin trace over a thin square grid.

    x spans one pitch p; y spans odd M pitches with a centred trace of width w
    along all x at z=h. Ground strips of width g at z=0 intersect at integer
    pitch lines. x ends lie on grid-centre reflection planes. All unprescribed
    exterior faces are insulating; no automatic open or periodic-wave boundary.
    Below z=0, between0..h and aboveh use the three required relative eps values.

    Require positive SI dimensions/eps, g<=p, w<=M*p, odd M=1..9 and even
    n=4..32 cells per pitch. Half-widths must align within relative1e-12 roundoff.
    Each vertical segment has explicit1..128 cells. Node100000/tet500000 limits
    apply before allocation. Requested/resolved widths are retained separately.
    This prepares geometry only; it excludes finite metal thickness and fields.
    """
    values = _strip_grid_input(pitch=pitch, grid_width=grid_width, trace_width=trace_width, height=height,
        top_clearance=top_clearance, backside_depth=backside_depth,
        eps_substrate=eps_substrate, eps_above=eps_above, eps_below=eps_below,
        transverse_periods=transverse_periods, cells_per_pitch=cells_per_pitch,
        cells_substrate=cells_substrate, cells_above=cells_above, cells_below=cells_below)
    p, g, w, h, a, d, es, ea, eb, m, n, ns, na, nb, ge, te, expected_volume = values
    nz = nb+ns+na; ny = m*n
    base = box_mesh(1., 1., 1., n, ny, nz)
    ix = np.rint(base.nodes[:, 0]*n).astype(int)
    iy = np.rint(base.nodes[:, 1]*ny).astype(int)
    iz = np.rint(base.nodes[:, 2]*nz).astype(int)
    xaxis = np.arange(n+1)/n*p; yaxis = np.arange(ny+1)/n*p
    zaxis = np.r_[np.linspace(-d, 0., nb+1), np.linspace(0., h, ns+1)[1:],
                  np.linspace(h, h+a, na+1)[1:]]
    mesh = Mesh3D(np.column_stack([xaxis[ix], yaxis[iy], zaxis[iz]]), base.tets,
                  boundary=base.boundary, tagged_faces=base.tagged_faces)
    mesh.check()
    modulo = iy % n
    grid = (ix <= ge) | (ix >= n-ge) | (modulo <= ge) | (modulo >= n-ge)
    ground = np.flatnonzero((iz == nb) & grid)
    trace = np.flatnonzero((iz == nb+ns) & (abs(iy-ny//2) <= te))
    meanz = np.mean(iz[base.tets], axis=1)
    relative = np.where(meanz < nb, eb, np.where(meanz > nb+ns, ea, es))
    volumes = mesh.volumes()
    if np.any(~np.isfinite(volumes)) or np.any(volumes <= 0):
        raise ValueError('geometry exceeds finite positive tetrahedron scales')
    error = float(abs(np.sum(volumes)/expected_volume-1))
    if error > 1e-12:
        raise ValueError('mesh volume does not match the explicit box')
    if not np.all(mesh.nodes[ground, 2] == 0) or not np.all(mesh.nodes[trace, 2] == h):
        raise ValueError('electrodes changed their prescribed planes')
    data = dict(zip(_INPUT_KEYS, values[:14], strict=True))
    return StripGridCell(json.dumps(data, sort_keys=True, allow_nan=False),
        float(2*xaxis[ge]), float(yaxis[ny//2+te]-yaxis[ny//2-te]), ge, te,
        mesh.nodes, mesh.tets, trace, ground, relative, error)


def extract_strip_grid_capacitance(*, pitch, grid_width, trace_width, height, top_clearance, backside_depth,
                    eps_substrate, eps_above, eps_below, transverse_periods, cells_per_pitch,
                    cells_substrate, cells_above, cells_below):
    """Extract total C[F] of the explicit three-region bounded static cell.

    Reuse shared3D P1 extraction with trace1V/grid0V and unchanged rawfield
    energy/charge/Maxwell gates. Refine mesh, transverse extent, top and bottom
    separately. This does not infer line impedance, return-current inductance,
    propagation, frequency validity, radiation or measured accuracy.
    """
    cell = strip_grid_cell(pitch=pitch, grid_width=grid_width, trace_width=trace_width, height=height,
        top_clearance=top_clearance, backside_depth=backside_depth,
        eps_substrate=eps_substrate, eps_above=eps_above, eps_below=eps_below,
        transverse_periods=transverse_periods, cells_per_pitch=cells_per_pitch,
        cells_substrate=cells_substrate, cells_above=cells_above, cells_below=cells_below)
    field = extract_capacitance_3d(cell.to_mesh(), eps_r=cell.relative_permittivity,
        conductors={'trace': cell.trace_nodes}, ground=cell.ground_nodes)
    if (type(field) is not Capacitance3D or field.names != ('trace',)
            or field.num_tets != len(cell.tets) or field.C.shape != (1, 1)
            or field.energy_C.shape != (1, 1) or field.ground_charge.shape != (1,)
            or field.potentials.shape != (len(cell.nodes), 1)):
        raise ValueError('field solve changed cell identity or result shapes')
    arrays = (field.C, field.energy_C, field.ground_charge, field.potentials)
    diagnostics = (field.free_residual_relative, field.charge_balance_relative,
                   field.energy_charge_relative, field.symmetry_relative)
    if (not all(np.isfinite(v) and 0 <= v <= 1e-8 for v in diagnostics)
            or not all(np.all(np.isfinite(v)) for v in arrays)
            or field.C[0, 0] <= 0 or field.energy_C[0, 0] <= 0 or field.ground_charge[0] >= 0
            or not np.all(field.potentials[cell.trace_nodes, 0] == 1)
            or not np.all(field.potentials[cell.ground_nodes, 0] == 0)):
        raise ValueError('field solve changed finite cell results or prescribed potentials')
    return StripGridCapacitance(cell, field)
