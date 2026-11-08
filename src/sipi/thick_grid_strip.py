# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Bounded static thin trace over a finite-thickness square ground grid."""
from dataclasses import dataclass
import json
import numpy as np
from galerkin.mesh3d import Mesh3D, box_mesh
from .capacitance3d import Capacitance3D, extract_capacitance_3d
from .network import _scalar
from .sampling import _integer

__all__ = ['ThickGridStripCell', 'ThickGridStripCapacitance', 'thick_grid_strip_cell',
           'extract_thick_grid_strip_capacitance']

_INPUT_KEYS = ('pitch_m', 'grid_width_m', 'trace_width_m', 'height_m',
    'top_clearance_m', 'backside_depth_m', 'eps_substrate', 'eps_above', 'eps_below',
    'transverse_periods', 'cells_per_pitch', 'cells_substrate', 'cells_above', 'cells_below', 'ground_thickness_m', 'cells_grid')


@dataclass(frozen=True)
class ThickGridStripCell:
    """Detached explicitly bounded geometry and piecewise dielectric values.

    Grid0V occupies -ground_thickness<=z<=0; thin trace1V lies at z=height. Other
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
    uncut_num_nodes: int
    uncut_num_tets: int
    metal_volume: float
    dielectric_volume: float

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
        out = dict(scope='bounded-thick-ground-grid-strip-cell', input=self.inputs,
            resolved_grid_width_m=self.resolved_grid_width,
            resolved_trace_width_m=self.resolved_trace_width,
            grid_edge_cells=self.grid_edge_cells, trace_edge_cells=self.trace_edge_cells,
            num_nodes=len(self.nodes), num_tets=len(self.tets),
            mesh_volume_relative_error=self.mesh_volume_relative_error,
            mesh_included=include_mesh, uncut_num_nodes=self.uncut_num_nodes,
            uncut_num_tets=self.uncut_num_tets,
            removed_num_nodes=self.uncut_num_nodes-len(self.nodes),
            removed_num_tets=self.uncut_num_tets-len(self.tets),
            metal_volume_m3=self.metal_volume, dielectric_volume_m3=self.dielectric_volume)
        if include_mesh:
            out.update(nodes_m=self.nodes.tolist(), tetrahedra=self.tets.tolist(),
                trace_nodes=self.trace_nodes.tolist(), ground_nodes=self.ground_nodes.tolist(),
                relative_permittivity=self.relative_permittivity.tolist())
        return out


@dataclass(frozen=True)
class ThickGridStripCapacitance:
    """Total bounded-cell C[F] and unit-voltage field, not a line RLGC model."""
    cell: ThickGridStripCell
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
        out = dict(scope='bounded-thick-ground-grid-strip-capacitance',
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


def _thick_grid_strip_input(*, pitch, grid_width, trace_width, height, top_clearance, backside_depth,
                    eps_substrate, eps_above, eps_below, transverse_periods, cells_per_pitch,
                    cells_substrate, cells_above, cells_below, ground_thickness, cells_grid):
    p = _scalar('pitch', pitch); g = _scalar('grid_width', grid_width)
    w = _scalar('trace_width', trace_width); h = _scalar('height', height)
    a = _scalar('top_clearance', top_clearance); d = _scalar('backside_depth', backside_depth)
    es = _scalar('eps_substrate', eps_substrate); ea = _scalar('eps_above', eps_above)
    eb = _scalar('eps_below', eps_below)
    t = _scalar('ground_thickness', ground_thickness)
    ng = _integer(cells_grid, 1, 128)
    m = _integer(transverse_periods, 1, 9); n = _integer(cells_per_pitch, 4, 32)
    ns = _integer(cells_substrate, 1, 128)
    na = _integer(cells_above, 1, 128); nb = _integer(cells_below, 1, 128)
    if m % 2 != 1 or n % 2 or g > p or w > m*p or t >= d:
        raise ValueError('require odd periods, even pitch cells, grid<=pitch, trace<=box and thickness<backside')
    def edge(value, limit):
        index = n*(value/p)/2
        resolved = int(round(index))
        if not 1 <= resolved <= limit or abs(index-resolved) > 1e-12*max(1, abs(index)):
            raise ValueError('half width must align with the mesh within relative 1e-12')
        return resolved
    ge = edge(g, n//2); te = edge(w, m*n//2)
    nz = nb+ng+ns+na; ny = m*n
    nodes = (n+1)*(ny+1)*(nz+1); tets = 6*n*ny*nz
    if nodes > 100000 or tets > 500000:
        raise ValueError('cell mesh exceeds 100000 nodes or 500000 tetrahedra')
    volume = p*(m*p)*(h+a+d)
    if not np.isfinite(volume) or volume <= 0 or not np.isfinite(h+a) or h+a <= h:
        raise ValueError('geometry exceeds finite positive box or top-clearance scales')
    return p, g, w, h, a, d, es, ea, eb, m, n, ns, na, nb, t, ng, ge, te, volume


def thick_grid_strip_cell(*, pitch, grid_width, trace_width, height, top_clearance, backside_depth,
                    eps_substrate, eps_above, eps_below, transverse_periods, cells_per_pitch,
                    cells_substrate, cells_above, cells_below, ground_thickness, cells_grid):
    """Prepare a thin trace above a finite-thickness PEC square ground grid.

    x spans one pitch p; y spans odd M pitches. The centred trace has width w
    at z=h. Ground grid bars have width g along integer pitch lines and occupy
    -t<=z<=0. Explicit dielectric regions are below0,0..h,aboveh. Other exterior
    faces are insulating/reflection; no inferred open or periodic-wave boundary.

    Positive SI dimensions/eps,0<t<d,g<=p,w<=M*p; odd M1..9, even n4..32.
    Half-widths align within relative1e-12 roundoff; requested/resolved widths
    remain separate. Four vertical counts1..128 cover -d..-t,-t..0,0..h,h..h+a.
    Uncut node100000/tet500000 budgets apply before allocation. Remove all PEC
    volume tetrahedra and unused nodes, retaining explicit surface ground nodes.
    This prepares geometry only, without finite trace thickness or a field solve.
    """
    values = _thick_grid_strip_input(pitch=pitch, grid_width=grid_width, trace_width=trace_width, height=height,
        top_clearance=top_clearance, backside_depth=backside_depth,
        eps_substrate=eps_substrate, eps_above=eps_above, eps_below=eps_below,
        transverse_periods=transverse_periods, cells_per_pitch=cells_per_pitch,
        cells_substrate=cells_substrate, cells_above=cells_above, cells_below=cells_below,
        ground_thickness=ground_thickness, cells_grid=cells_grid)
    p, g, w, h, a, d, es, ea, eb, m, n, ns, na, nb, t, ng, ge, te, box_volume = values
    nz = nb+ng+ns+na; ny = m*n
    base = box_mesh(1., 1., 1., n, ny, nz)
    ix = np.rint(base.nodes[:, 0]*n).astype(int)
    iy = np.rint(base.nodes[:, 1]*ny).astype(int)
    iz = np.rint(base.nodes[:, 2]*nz).astype(int)
    xaxis = np.arange(n+1)/n*p; yaxis = np.arange(ny+1)/n*p
    zaxis = np.r_[np.linspace(-d, -t, nb+1), np.linspace(-t, 0., ng+1)[1:],
                  np.linspace(0., h, ns+1)[1:], np.linspace(h, h+a, na+1)[1:]]
    coordinates = np.column_stack([xaxis[ix], yaxis[iy], zaxis[iz]])
    cx = np.mean(ix[base.tets], axis=1); cy = np.mean(iy[base.tets], axis=1)
    cz = np.mean(iz[base.tets], axis=1)
    grid = (cx < ge) | (cx > n-ge) | (cy % n < ge) | (cy % n > n-ge)
    metal = grid & (cz > nb) & (cz < nb+ng)
    expected_removed = 6*(n*ny-m*(n-2*ge)**2)*ng
    if np.count_nonzero(metal) != expected_removed:
        raise ValueError('metal tetrahedron count changed')
    remaining = base.tets[~metal]
    used = np.unique(remaining)
    remap = np.full(len(coordinates), -1, dtype=int)
    remap[used] = np.arange(len(used))
    mesh = Mesh3D(coordinates[used], remap[remaining])
    mesh.check()
    node_grid = (ix <= ge) | (ix >= n-ge) | (iy % n <= ge) | (iy % n >= n-ge)
    ground = np.flatnonzero(((iz >= nb) & (iz <= nb+ng) & node_grid)[used])
    trace = np.flatnonzero(((iz == nb+ng+ns) & (abs(iy-ny//2) <= te))[used])
    relative = np.where(cz[~metal] < nb+ng, eb, np.where(cz[~metal] > nb+ng+ns, ea, es))
    resolved_g = float(2*xaxis[ge])
    metal_volume = (p*(m*p)-m*(p-resolved_g)**2)*t
    dielectric_volume = box_volume-metal_volume
    volumes = mesh.volumes()
    error = float(abs(np.sum(volumes)/dielectric_volume-1))
    if (np.any(~np.isfinite(volumes)) or np.any(volumes <= 0)
            or not np.isfinite(error) or error > 1e-12):
        raise ValueError('dielectric tetrahedra do not match finite positive geometry')
    if len(np.unique(mesh.tets)) != len(mesh.nodes):
        raise ValueError('unused mesh nodes remain after removing metal')
    if not np.all(mesh.nodes[trace, 2] == h):
        raise ValueError('trace changed its prescribed plane')
    data = dict(zip(_INPUT_KEYS, values[:16], strict=True))
    return ThickGridStripCell(json.dumps(data, sort_keys=True, allow_nan=False),
        resolved_g, float(yaxis[ny//2+te]-yaxis[ny//2-te]), ge, te,
        mesh.nodes, mesh.tets, trace, ground, relative, error,
        len(coordinates), len(base.tets), metal_volume, dielectric_volume)


def extract_thick_grid_strip_capacitance(*, pitch, grid_width, trace_width, height, top_clearance, backside_depth,
                    eps_substrate, eps_above, eps_below, transverse_periods, cells_per_pitch,
                    cells_substrate, cells_above, cells_below, ground_thickness, cells_grid):
    """Extract total C[F] of the explicit three-region bounded static cell.

    For thickness comparisons preserve a common below-grid spacing/FE space;
    changing independent segment counts can obscure the small thickness effect.
    No monotonicity across arbitrary remeshing is promised.

    Reuse shared3D P1 extraction with trace1V/grid0V and unchanged rawfield
    energy/charge/Maxwell gates. Refine mesh, transverse extent, top and bottom
    separately. This does not infer line impedance, return-current inductance,
    propagation, frequency validity, radiation or measured accuracy.
    """
    cell = thick_grid_strip_cell(pitch=pitch, grid_width=grid_width, trace_width=trace_width, height=height,
        top_clearance=top_clearance, backside_depth=backside_depth,
        eps_substrate=eps_substrate, eps_above=eps_above, eps_below=eps_below,
        transverse_periods=transverse_periods, cells_per_pitch=cells_per_pitch,
        cells_substrate=cells_substrate, cells_above=cells_above, cells_below=cells_below,
        ground_thickness=ground_thickness, cells_grid=cells_grid)
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
    return ThickGridStripCapacitance(cell, field)
