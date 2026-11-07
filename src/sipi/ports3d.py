# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Bounded homogeneous Maxwell fields with two local TEM-admittance ports.

Explicit conforming tetrahedra, planar annular ports and PEC remaining walls;
exp(+j omega t). This boundary model is not a multimode radiation condition.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.sparse.linalg import splu
from galerkin.edge3d import EdgeSpace3D, assemble_curlcurl_3d, assemble_edge_mass_3d
from galerkin.core.spaces import edge_ids

from .capacitance3d import _snapshot, _node_set, _readonly
from .constants import epsilon_0, mu_0
from .network import LineNetwork, _frequencies, _scalar

__all__ = ['TEMPort3D', 'TEMNetwork3D', 'solve_tem_ports_3d']


@dataclass(frozen=True)
class TEMPort3D:
    """Exterior triangles and complete signal/ground perimeter node loops.

    Indices follow the supplied volume mesh. Signal is one volt and ground
    zero in the port's scalar Laplace mode. Arrays are detached snapshots;
    mesh membership and annular topology are checked when solving.
    """
    name: str
    faces: np.ndarray
    signal: np.ndarray
    ground: np.ndarray

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip() or any(c in self.name for c in '\r\n'):
            raise ValueError('port name must be a nonempty single-line string')
        for key in ('faces', 'signal', 'ground'):
            if any(isinstance(x, (bool, np.bool_)) for x in np.asarray(getattr(self, key), dtype=object).flat):
                raise ValueError('port indices must not contain booleans')
            object.__setattr__(self, key, _readonly(getattr(self, key)))


@dataclass(frozen=True)
class TEMNetwork3D:
    """Power-normalized TEM projection, with raw per-frequency diagnostics.

    ``unprojected_port_power[f,q]`` is total outgoing boundary power minus
    projected TEM power, divided by incident power at q; it is not material
    loss. ``power_balance`` uses the full boundary field, not just S.
    """
    network: LineNetwork
    port_norm: np.ndarray
    linear_residual: np.ndarray
    power_balance: np.ndarray
    reciprocity: np.ndarray
    projected_unitarity: np.ndarray
    unprojected_port_power: np.ndarray
    num_tets: int
    num_edges: int


def _graph(edges, count):
    return coo_matrix((np.ones(len(edges)), (edges[:, 0], edges[:, 1])),
                      shape=(count, count)).tocsr()


def _surface_geometry(nodes, faces):
    xyz = nodes[faces]
    v1, v2 = xyz[:, 1]-xyz[:, 0], xyz[:, 2]-xyz[:, 0]
    area = np.linalg.norm(np.cross(v1, v2), axis=1)/2
    jac = np.stack([v1, v2], axis=2)
    g12 = np.linalg.solve(jac.transpose(0, 2, 1)@jac, jac.transpose(0, 2, 1))
    grad = np.concatenate([-g12.sum(axis=1)[:, None, :], g12], axis=1)
    return area, grad


def _prepare_port(mesh, port, exterior):
    faces = np.asarray(port.faces)
    if (faces.ndim != 2 or faces.shape[1] != 3 or not len(faces)
            or faces.dtype.kind not in 'iu' or faces.min() < 0 or faces.max() >= mesh.num_nodes):
        raise ValueError('port faces must be nonempty integer (F, 3) mesh node indices')
    faces = np.sort(faces, axis=1)
    keys = {tuple(face) for face in faces}
    if len(keys) != len(faces) or not keys.issubset(exterior):
        raise ValueError('port faces must be distinct exterior triangles')
    nodes = np.unique(faces)
    signal = _node_set(port.signal, mesh.num_nodes, 'port signal')
    ground = _node_set(port.ground, mesh.num_nodes, 'port ground')
    edges, counts = np.unique(np.sort(np.concatenate([faces[:, [0, 1]],
        faces[:, [0, 2]], faces[:, [1, 2]]]), axis=1), axis=0, return_counts=True)
    local_edges = np.searchsorted(nodes, edges)
    if np.any(counts > 2) or connected_components(_graph(local_edges, len(nodes)), directed=False)[0] != 1:
        raise ValueError('port must be a connected manifold annulus')
    rim = edges[counts == 1]
    rim_nodes, degrees = np.unique(rim, return_counts=True)
    if not len(rim) or np.any(degrees != 2) or len(nodes)-len(edges)+len(faces) != 0:
        raise ValueError('port must have annular topology with closed perimeter loops')
    components, labels = connected_components(_graph(np.searchsorted(rim_nodes, rim), len(rim_nodes)), directed=False)
    loops = [set(rim_nodes[labels == i]) for i in range(components)]
    if (components != 2 or set(signal) not in loops or set(ground) not in loops
            or set(signal) == set(ground)):
        raise ValueError('signal and ground must each cover one complete distinct port perimeter loop')
    points = mesh.nodes[nodes]-mesh.nodes[nodes[0]]
    _, singular, axes = np.linalg.svd(points, full_matrices=False)
    if singular[1] <= 0 or np.max(abs(points@axes[-1])) > 1e-10*singular[0]:
        raise ValueError('port triangles must be planar')
    area, grad = _surface_geometry(mesh.nodes, faces)
    if not np.isfinite(area).all() or np.any(area <= 0) or not np.isfinite(grad).all():
        raise ValueError('port triangles must have finite positive area and gradients')
    return faces, nodes, signal, ground, edges, rim, area, grad


def _port_mode(space, data):
    faces, nodes, signal, ground, edges, _, area, grad = data
    local_faces = np.searchsorted(nodes, faces)
    values = area[:, None, None]*(grad@grad.transpose(0, 2, 1))
    k = coo_matrix((values.ravel(), (np.repeat(local_faces, 3, axis=1).ravel(),
        np.tile(local_faces, (1, 3)).ravel())), shape=(len(nodes), len(nodes))).tocsr()
    fixed = np.searchsorted(nodes, np.r_[signal, ground])
    free = np.setdiff1d(np.arange(len(nodes)), fixed)
    potential = np.zeros(len(nodes)); potential[np.searchsorted(nodes, signal)] = 1.
    if len(free):
        potential[free] = splu(k[free][:, free].tocsc()).solve(-(k[free][:, fixed]@potential[fixed]))
    scale = float(potential@k@potential)
    if (not np.isfinite(potential).all() or not np.isfinite(scale) or scale <= 0
            or np.max(abs((k@potential)[free]), initial=0)/scale > 1e-8):
        raise ValueError('port Laplace mode failed its finite-energy or free-residual check')
    electric = np.zeros(space.num_edges)
    electric[edge_ids(space, edges)] = (potential[np.searchsorted(nodes, edges[:, 0])]
                                      - potential[np.searchsorted(nodes, edges[:, 1])])
    local = [(0, 1), (0, 2), (1, 2)]
    mass = np.empty((len(faces), 3, 3))
    for e, (i, j) in enumerate(local):
        for f, (k, l) in enumerate(local):
            def dot(a, b):
                return np.einsum('ti,ti->t', grad[:, a], grad[:, b])
            mass[:, e, f] = area/12*((1+(i == k))*dot(j, l)-(1+(i == l))*dot(j, k)
                -(1+(j == k))*dot(i, l)+(1+(j == l))*dot(i, k))
    ids = edge_ids(space, faces[:, np.array(local)].reshape(-1, 2)).reshape(-1, 3)
    boundary = coo_matrix((mass.ravel(), (np.repeat(ids, 3, axis=1).ravel(),
        np.tile(ids, (1, 3)).ravel())), shape=(space.num_edges, space.num_edges)).tocsr()
    return electric, boundary


def solve_tem_ports_3d(mesh, *, ports, frequency, eps_r=1.):
    """Solve the explicit bounded two-port local-admittance Maxwell problem.

    Uniform positive real eps_r, mu_r=1, positive increasing Hz. Exactly two
    disjoint planar annular TEMPort3D objects; all other exterior faces PEC.
    The caller supplies conforming geometry. No overlap/hanging-node search,
    meshing, material loss, full multimode ports or radiation model is provided.
    Numerical consistency gates do not establish physical mesh/port accuracy.
    """
    mesh = _snapshot(mesh)
    relative = _scalar('eps_r', eps_r)
    frequencies = _frequencies(frequency)
    if frequencies[0] <= 0:
        raise ValueError('frequency must be strictly positive for the Maxwell solve')
    ports = tuple(ports)
    if len(ports) != 2 or not all(isinstance(p, TEMPort3D) for p in ports):
        raise ValueError('exactly two TEMPort3D objects are required')
    if ports[0].name == ports[1].name:
        raise ValueError('port names must be unique')
    volume_edges = np.column_stack([np.repeat(mesh.tets[:, 0], 3), mesh.tets[:, 1:].ravel()])
    if connected_components(_graph(volume_edges, mesh.num_nodes), directed=False)[0] != 1:
        raise ValueError('volume mesh must be connected')
    exterior = np.sort(mesh.boundary_faces(), axis=1)
    keys = {tuple(face) for face in exterior}
    prepared = [_prepare_port(mesh, port, keys) for port in ports]
    if np.intersect1d(prepared[0][1], prepared[1][1]).size:
        raise ValueError('ports must have disjoint nodes and faces')
    port_keys = {tuple(face) for data in prepared for face in data[0]}
    walls = np.array([face for face in exterior if tuple(face) not in port_keys], dtype=int).reshape(-1, 3)
    wall_edges = np.unique(np.sort(np.concatenate([walls[:, [0, 1]], walls[:, [0, 2]],
                                                   walls[:, [1, 2]]]), axis=1), axis=0)
    wall_keys = {tuple(edge) for edge in wall_edges}
    for data in prepared:
        if ({tuple(edge) for edge in data[4]} & wall_keys) != {tuple(edge) for edge in data[5]}:
            raise ValueError('PEC walls must meet each port exactly on its perimeter')
    space = EdgeSpace3D(mesh)
    pec = edge_ids(space, wall_edges)
    free = np.setdiff1d(np.arange(space.num_edges), pec)
    try:
        modes, boundaries = zip(*[_port_mode(space, data) for data in prepared])
        norms = np.array([float(e@b@e) for e, b in zip(modes, boundaries)])
        stiffness, mass = assemble_curlcurl_3d(space), assemble_edge_mass_3d(space)
    except (RuntimeError, np.linalg.LinAlgError) as exc:
        raise ValueError('volume or port operator could not be assembled/solved') from exc
    if (not np.isfinite(norms).all() or np.any(norms <= 0)
            or not all(np.isfinite(m.data).all() for m in (stiffness, mass, *boundaries))):
        raise ValueError('mesh and ports produced a nonfinite operator or invalid mode norm')
    drives = np.column_stack([b@e for b, e in zip(boundaries, modes)])
    results = []; residuals = []; balances = []; reciprocities = []; defects = []; unprojected = []
    for f in frequencies:
        beta = 2*np.pi*f*np.sqrt(mu_0*epsilon_0*relative)
        system = stiffness-beta**2*mass+1j*beta*(boundaries[0]+boundaries[1])
        rhs = 2j*beta*drives
        if not np.isfinite(system.data).all() or not np.isfinite(rhs).all():
            raise ValueError('frequency and mesh produced a nonfinite Maxwell system')
        try:
            fields = np.zeros((space.num_edges, 2), complex)
            fields[free] = splu(system[free][:, free].tocsc()).solve(rhs[free])
        except (RuntimeError, ValueError) as exc:
            raise ValueError(f'Maxwell system could not be solved at {f:g} Hz') from exc
        s = np.array([[modes[p]@(boundaries[p]@fields[:, q])/norms[p]-(p == q)
                       for q in range(2)] for p in range(2)])
        s *= np.sqrt(norms[:, None]/norms[None, :])
        residual = float(np.linalg.norm((system@fields-rhs)[free])/np.linalg.norm(rhs[free]))
        powers = []
        for q in range(2):
            total = 0.
            for p, boundary in enumerate(boundaries):
                outgoing = fields[:, q]-(modes[p] if p == q else 0)
                total += float(np.vdot(outgoing, boundary@outgoing).real)
            powers.append(total/norms[q])
        balance = float(np.max(abs(np.array(powers)-1)))
        reciprocity = float(np.max(abs(s-s.T)))
        defect = float(np.max(abs(s.conj().T@s-np.eye(2))))
        remainder = np.array(powers)-np.sum(abs(s)**2, axis=0)
        if (not np.isfinite(fields).all() or not np.isfinite(s).all()
                or not np.isfinite([residual, balance, reciprocity, defect, *remainder]).all()
                or max(residual, balance, reciprocity) > 1e-8):
            raise ValueError(f'Maxwell solve failed residual, power or reciprocity checks at {f:g} Hz')
        # Keep raw projected power deficits; never clip, symmetrize or repair S.
        results.append(s); residuals.append(residual); balances.append(balance)
        reciprocities.append(reciprocity); defects.append(defect); unprojected.append(remainder)
    network = LineNetwork(frequencies, results, np.sqrt(mu_0/(epsilon_0*relative))/norms,
                          tuple(port.name for port in ports))
    return TEMNetwork3D(network, *map(_readonly, (norms, residuals, balances, reciprocities,
        defects, unprojected)), len(mesh.tets), space.num_edges)
