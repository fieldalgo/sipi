# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Bounded static paired finite-thickness traces and square ground-grid volumes."""
from dataclasses import dataclass
import json
import numpy as np
from galerkin.mesh3d import Mesh3D, box_mesh
from .capacitance3d import Capacitance3D
from .partitioned_capacitance import extract_partitioned_capacitance_3d
from .network import _scalar
from .sampling import _integer

__all__ = ['VolumeGridPairCell', 'VolumeGridPairCapacitance', 'volume_grid_pair_cell',
           'extract_volume_grid_pair_capacitance']

_INPUT_KEYS = ('pitch_m', 'grid_width_m', 'trace_width_m', 'height_m',
    'top_clearance_m', 'backside_depth_m', 'eps_substrate', 'eps_above', 'eps_below',
    'transverse_periods', 'cells_per_pitch', 'cells_substrate', 'cells_above', 'cells_below', 'ground_thickness_m', 'cells_grid', 'trace_thickness_m', 'cells_trace', 'trace_gap_m')


@dataclass(frozen=True)
class VolumeGridPairCell:
    """Detached bounded pair geometry with explicit left/right/ground surfaces.

    Equal-width traces occupy height..height+trace_thickness, symmetrically
    separated by trace_gap. Ground bars occupy -ground_thickness..0. Other
    exterior faces are insulating. Inputs use SI dimensions and positive eps.
    """
    input_json: str
    resolved_grid_width: float
    resolved_trace_width: float
    grid_edge_cells: int
    trace_edge_cells: int
    gap_edge_cells: int
    resolved_trace_gap: float
    nodes: np.ndarray
    tets: np.ndarray
    left_nodes: np.ndarray
    right_nodes: np.ndarray
    ground_nodes: np.ndarray
    relative_permittivity: np.ndarray
    mesh_volume_relative_error: float
    uncut_num_nodes: int
    uncut_num_tets: int
    ground_metal_volume: float
    trace_metal_volume: float
    dielectric_volume: float

    def __post_init__(self):
        for name in ('nodes', 'tets', 'left_nodes', 'right_nodes', 'ground_nodes', 'relative_permittivity'):
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
        out = dict(scope='bounded-volume-grid-pair-cell', input=self.inputs,
            resolved_grid_width_m=self.resolved_grid_width,
            resolved_trace_width_m=self.resolved_trace_width,
            grid_edge_cells=self.grid_edge_cells, trace_edge_cells=self.trace_edge_cells,
            gap_edge_cells=self.gap_edge_cells, resolved_trace_gap_m=self.resolved_trace_gap,
            num_nodes=len(self.nodes), num_tets=len(self.tets),
            mesh_volume_relative_error=self.mesh_volume_relative_error,
            mesh_included=include_mesh, uncut_num_nodes=self.uncut_num_nodes,
            uncut_num_tets=self.uncut_num_tets,
            removed_num_nodes=self.uncut_num_nodes-len(self.nodes),
            removed_num_tets=self.uncut_num_tets-len(self.tets),
            ground_metal_volume_m3=self.ground_metal_volume,
            trace_metal_volume_m3=self.trace_metal_volume, dielectric_volume_m3=self.dielectric_volume)
        if include_mesh:
            out.update(nodes_m=self.nodes.tolist(), tetrahedra=self.tets.tolist(),
                left_nodes=self.left_nodes.tolist(), right_nodes=self.right_nodes.tolist(),
                ground_nodes=self.ground_nodes.tolist(),
                relative_permittivity=self.relative_permittivity.tolist())
        return out


@dataclass(frozen=True)
class VolumeGridPairCapacitance:
    """Total bounded-cell2x2 Maxwell C[F] in left/right electrode order."""
    cell: VolumeGridPairCell
    field: Capacitance3D

    @property
    def capacitance_matrix_f(self):
        return np.array(self.field.C, copy=True)

    @property
    def inputs(self):
        return self.cell.inputs

    def to_dict(self, *, include_fields=False):
        if type(include_fields) is not bool:
            raise ValueError('include_fields must be a boolean')
        f = self.field
        out = dict(scope='bounded-volume-grid-pair-capacitance',
            cell=self.cell.to_dict(include_mesh=include_fields),
            names=list(f.names), capacitance_matrix_f=self.capacitance_matrix_f.tolist(),
            energy_capacitance_matrix_f=f.energy_C.tolist(),
            ground_charge_c_per_basis=f.ground_charge.tolist(),
            free_residual_relative=f.free_residual_relative,
            charge_balance_relative=f.charge_balance_relative,
            energy_charge_relative=f.energy_charge_relative,
            symmetry_relative=f.symmetry_relative, fields_included=include_fields)
        if include_fields:
            out['potential_v_per_basis'] = f.potentials.tolist()
        return out


def _volume_grid_pair_input(*, pitch, grid_width, trace_width, height, top_clearance, backside_depth,
                    eps_substrate, eps_above, eps_below, transverse_periods, cells_per_pitch,
                    cells_substrate, cells_above, cells_below, ground_thickness, cells_grid, trace_thickness, cells_trace, trace_gap):
    p = _scalar('pitch', pitch); g = _scalar('grid_width', grid_width)
    w = _scalar('trace_width', trace_width); h = _scalar('height', height)
    a = _scalar('top_clearance', top_clearance); d = _scalar('backside_depth', backside_depth)
    es = _scalar('eps_substrate', eps_substrate); ea = _scalar('eps_above', eps_above)
    eb = _scalar('eps_below', eps_below)
    t = _scalar('ground_thickness', ground_thickness)
    ng = _integer(cells_grid, 1, 128)
    u = _scalar('trace_thickness', trace_thickness)
    gap = _scalar('trace_gap', trace_gap)
    nt = _integer(cells_trace, 1, 128)
    m = _integer(transverse_periods, 1, 9); n = _integer(cells_per_pitch, 4, 32)
    ns = _integer(cells_substrate, 1, 128)
    na = _integer(cells_above, 1, 128); nb = _integer(cells_below, 1, 128)
    if m % 2 != 1 or n % 2 or g > p or 2*w+gap > m*p or t >= d:
        raise ValueError('require odd periods, even pitch cells, grid<=pitch, 2*width+gap<=box and thickness<backside')
    def edge(value, limit):
        index = n*(value/p)/2
        resolved = int(round(index))
        if not 1 <= resolved <= limit or abs(index-resolved) > 1e-12*max(1, abs(index)):
            raise ValueError('half width must align with the mesh within relative 1e-12')
        return resolved
    ge = edge(g, n//2); te = edge(w, m*n//2); ce = edge(gap, m*n//2)
    nz = nb+ng+ns+nt+na; ny = m*n
    nodes = (n+1)*(ny+1)*(nz+1); tets = 6*n*ny*nz
    if nodes > 100000 or tets > 500000:
        raise ValueError('cell mesh exceeds 100000 nodes or 500000 tetrahedra')
    volume = p*(m*p)*(h+u+a+d)
    if not np.isfinite(volume) or volume <= 0 or not np.isfinite(h+u+a) or h+u <= h or h+u+a <= h+u:
        raise ValueError('geometry exceeds finite positive box or top-clearance scales')
    return p, g, w, h, a, d, es, ea, eb, m, n, ns, na, nb, t, ng, u, nt, gap, ge, te, ce, volume


def volume_grid_pair_cell(*, pitch, grid_width, trace_width, height, top_clearance, backside_depth,
                    eps_substrate, eps_above, eps_below, transverse_periods, cells_per_pitch,
                    cells_substrate, cells_above, cells_below, ground_thickness, cells_grid, trace_thickness, cells_trace, trace_gap):
    """Prepare two finite PEC traces over a finite square ground-grid volume.

    One pitch in x and odd M pitches in y. Each trace has width w; their inner
    edges are separated by a positive gap about y=M*p/2. Both occupy h..h+u;
    grid bars occupy -t..0. Three explicit eps regions lie below0,0..h,aboveh.
    Outer faces are insulating, not inferred open boundaries.

    Positive SI dimensions;0<t<d,g<=p,2*w+gap<=M*p; odd M1..9, even n4..32.
    Half widths and half gap align within relative1e-12 roundoff. Five vertical
    counts1..128 and uncut100000node/500000tet budgets apply before allocation.
    Metal volumes and unused nodes are removed; no field solve or mirror repair.
    """
    values = _volume_grid_pair_input(pitch=pitch, grid_width=grid_width, trace_width=trace_width, height=height,
        top_clearance=top_clearance, backside_depth=backside_depth,
        eps_substrate=eps_substrate, eps_above=eps_above, eps_below=eps_below,
        transverse_periods=transverse_periods, cells_per_pitch=cells_per_pitch,
        cells_substrate=cells_substrate, cells_above=cells_above, cells_below=cells_below,
        ground_thickness=ground_thickness, cells_grid=cells_grid,
        trace_thickness=trace_thickness, cells_trace=cells_trace, trace_gap=trace_gap)
    p, g, w, h, a, d, es, ea, eb, m, n, ns, na, nb, t, ng, u, nt, gap, ge, te, ce, box_volume = values
    nz = nb+ng+ns+nt+na; ny = m*n
    base = box_mesh(1., 1., 1., n, ny, nz)
    ix = np.rint(base.nodes[:, 0]*n).astype(int)
    iy = np.rint(base.nodes[:, 1]*ny).astype(int)
    iz = np.rint(base.nodes[:, 2]*nz).astype(int)
    xaxis = np.arange(n+1)/n*p; yaxis = np.arange(ny+1)/n*p
    zaxis = np.r_[np.linspace(-d, -t, nb+1), np.linspace(-t, 0., ng+1)[1:],
                  np.linspace(0., h, ns+1)[1:], np.linspace(h, h+u, nt+1)[1:],
                  np.linspace(h+u, h+u+a, na+1)[1:]]
    coordinates = np.column_stack([xaxis[ix], yaxis[iy], zaxis[iz]])
    cx = np.mean(ix[base.tets], axis=1); cy = np.mean(iy[base.tets], axis=1)
    cz = np.mean(iz[base.tets], axis=1)
    grid = (cx < ge) | (cx > n-ge) | (cy % n < ge) | (cy % n > n-ge)
    ground_metal = grid & (cz > nb) & (cz < nb+ng)
    trace_metal = (abs(cy-ny/2) > ce) & (abs(cy-ny/2) < ce+2*te) & (cz > nb+ng+ns) & (cz < nb+ng+ns+nt)
    metal = ground_metal | trace_metal
    expected_removed = 6*(n*ny-m*(n-2*ge)**2)*ng+6*n*(4*te)*nt
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
    slab = (iz >= nb+ng+ns) & (iz <= nb+ng+ns+nt)
    left = np.flatnonzero((slab & (iy >= ny//2-ce-2*te) & (iy <= ny//2-ce))[used])
    right = np.flatnonzero((slab & (iy >= ny//2+ce) & (iy <= ny//2+ce+2*te))[used])
    relative = np.where(cz[~metal] < nb+ng, eb, np.where(cz[~metal] > nb+ng+ns, ea, es))
    resolved_g = float(2*xaxis[ge])
    ground_volume = (p*(m*p)-m*(p-resolved_g)**2)*t
    trace_volume = p*float(yaxis[ny//2-ce]-yaxis[ny//2-ce-2*te]+yaxis[ny//2+ce+2*te]-yaxis[ny//2+ce])*u
    dielectric_volume = box_volume-ground_volume-trace_volume
    volumes = mesh.volumes()
    error = float(abs(np.sum(volumes)/dielectric_volume-1))
    if (np.any(~np.isfinite(volumes)) or np.any(volumes <= 0)
            or not np.isfinite(error) or error > 1e-12):
        raise ValueError('dielectric tetrahedra do not match finite positive geometry')
    if len(np.unique(mesh.tets)) != len(mesh.nodes):
        raise ValueError('unused mesh nodes remain after removing metal')
    for signal in (left, right):
        if not np.all((mesh.nodes[signal, 2] >= h) & (mesh.nodes[signal, 2] <= h+u)):
            raise ValueError('trace changed its prescribed slab')
        if len(np.intersect1d(signal, ground)):
            raise ValueError('signal and ground surfaces overlap')
    if len(np.intersect1d(left, right)):
        raise ValueError('left and right signal surfaces overlap')
    data = dict(zip(_INPUT_KEYS, values[:19], strict=True))
    return VolumeGridPairCell(json.dumps(data, sort_keys=True, allow_nan=False),
        resolved_g, float(2*te/n*p), ge, te, ce, float(2*ce/n*p),
        mesh.nodes, mesh.tets, left, right, ground, relative, error,
        len(coordinates), len(base.tets), ground_volume, trace_volume, dielectric_volume)


def extract_volume_grid_pair_capacitance(*, pitch, grid_width, trace_width, height, top_clearance, backside_depth,
                    eps_substrate, eps_above, eps_below, transverse_periods, cells_per_pitch,
                    cells_substrate, cells_above, cells_below, ground_thickness, cells_grid, trace_thickness, cells_trace, trace_gap):
    """Extract the bounded pair's2x2 Maxwell capacitance in left/right order.

    Each column excites one trace to1V with the other trace and grid at0V.
    Reuse partitioned3D P1 extraction and unchanged raw1e-8 acceptance gates.
    Check mesh and each exterior separately. Finite-mesh mirror symmetry is
    not imposed. No return-current inductance, line impedance/RLGC, propagation,
    frequency validity or measured accuracy is inferred from this static cell.
    """
    cell = volume_grid_pair_cell(pitch=pitch, grid_width=grid_width, trace_width=trace_width, height=height,
        top_clearance=top_clearance, backside_depth=backside_depth,
        eps_substrate=eps_substrate, eps_above=eps_above, eps_below=eps_below,
        transverse_periods=transverse_periods, cells_per_pitch=cells_per_pitch,
        cells_substrate=cells_substrate, cells_above=cells_above, cells_below=cells_below,
        ground_thickness=ground_thickness, cells_grid=cells_grid,
        trace_thickness=trace_thickness, cells_trace=cells_trace, trace_gap=trace_gap)
    field = extract_partitioned_capacitance_3d(cell.to_mesh(), eps_r=cell.relative_permittivity,
        conductors={'left': cell.left_nodes, 'right': cell.right_nodes}, ground=cell.ground_nodes)
    if (type(field) is not Capacitance3D or field.names != ('left', 'right')
            or field.num_tets != len(cell.tets) or field.C.shape != (2, 2)
            or field.energy_C.shape != (2, 2) or field.ground_charge.shape != (2,)
            or field.potentials.shape != (len(cell.nodes), 2)):
        raise ValueError('field solve changed cell identity or result shapes')
    arrays = (field.C, field.energy_C, field.ground_charge, field.potentials)
    diagnostics = (field.free_residual_relative, field.charge_balance_relative,
                   field.energy_charge_relative, field.symmetry_relative)
    if (not all(np.isfinite(v) and 0 <= v <= 1e-8 for v in diagnostics)
            or not all(np.all(np.isfinite(v)) for v in arrays)
            or np.min(np.linalg.eigvalsh(field.C)) <= 0
            or np.min(np.linalg.eigvalsh(field.energy_C)) <= 0
            or np.any(field.C-np.diag(np.diag(field.C)) > 0)
            or np.any(field.ground_charge >= 0)
            or not np.all(field.potentials[cell.left_nodes] == [1., 0.])
            or not np.all(field.potentials[cell.right_nodes] == [0., 1.])
            or not np.all(field.potentials[cell.ground_nodes] == 0)):
        raise ValueError('field solve changed finite cell results or prescribed potentials')
    return VolumeGridPairCapacitance(cell, field)
