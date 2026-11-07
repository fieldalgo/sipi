# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Static capacitance in an explicitly bounded tetrahedral domain, in farads."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.sparse.linalg import splu
from galerkin.mesh3d import Mesh3D
from galerkin.assembly3d import assemble_stiffness_3d

from .constants import epsilon_0

__all__ = ['Capacitance3D', 'extract_capacitance_3d']


def _readonly(value):
    result = np.array(value, copy=True)
    result.setflags(write=False)
    return result


@dataclass(frozen=True)
class Capacitance3D:
    """Unit-voltage basis and total C[F]; not a per-length line parameter set.

    Column j drives conductor j at one volt, with all other conductors and
    ground at zero. ``potentials`` follows the input node order. Ground charge
    is in coulombs for these one-volt drives. Arrays are read-only snapshots.
    No inductance, radiation, loss, impedance or S-parameters are inferred.
    """
    names: tuple[str, ...]
    C: np.ndarray
    energy_C: np.ndarray
    potentials: np.ndarray
    ground_charge: np.ndarray
    free_residual_relative: float
    charge_balance_relative: float
    energy_charge_relative: float
    symmetry_relative: float
    num_tets: int


def _snapshot(mesh):
    if not isinstance(mesh, Mesh3D):
        raise ValueError('mesh must be a conforming galerkin Mesh3D in metres')
    nodes, tets = np.asarray(mesh.nodes), np.asarray(mesh.tets)
    if (nodes.ndim != 2 or nodes.shape[1] != 3 or len(nodes) < 4
            or nodes.dtype.kind not in 'fiu' or not np.isfinite(nodes).all()):
        raise ValueError('mesh nodes must be finite real (N, 3) coordinates')
    if (tets.ndim != 2 or tets.shape[1] != 4 or not len(tets)
            or tets.dtype.kind not in 'iu' or tets.min() < 0 or tets.max() >= len(nodes)):
        raise ValueError('mesh tets must be nonempty integer (T, 4) node indices')
    ordered = np.sort(tets, axis=1)
    if np.any(np.diff(ordered, axis=1) == 0) or len(np.unique(ordered, axis=0)) != len(tets):
        raise ValueError('mesh must not contain repeated vertices or duplicate tetrahedra')
    if len(np.unique(tets)) != len(nodes):
        raise ValueError('mesh must not contain unused nodes')
    mesh.check()
    result = Mesh3D(np.array(nodes, dtype=float, copy=True), np.array(tets, copy=True))
    with np.errstate(over='ignore', invalid='ignore'):
        volumes = result.volumes()
    if not np.isfinite(volumes).all() or np.any(volumes <= 0):
        raise ValueError('tetrahedra must have finite positive volume')
    faces = np.concatenate([result.tets[:, ids] for ids in ((0,1,2),(0,1,3),(0,2,3),(1,2,3))])
    _, counts = np.unique(np.sort(faces, axis=1), axis=0, return_counts=True)
    if np.any(counts > 2):
        raise ValueError('mesh contains a nonmanifold face')
    return result


def _node_set(value, count, name):
    nodes = np.asarray(value)
    if (nodes.ndim != 1 or not len(nodes) or nodes.dtype.kind not in 'iu'
            or nodes.min() < 0 or nodes.max() >= count or len(np.unique(nodes)) != len(nodes)):
        raise ValueError(f'{name} must be nonempty distinct integer node indices in the mesh')
    return np.array(nodes, dtype=int, copy=True)


def _prepare_inputs(mesh, eps_r, conductors, ground):
    """Validate detached inputs without assembling or solving the field."""
    mesh = _snapshot(mesh)
    relative = np.asarray(eps_r)
    if (relative.dtype.kind not in 'fiu' or relative.shape not in ((), (len(mesh.tets),))
            or not np.isfinite(relative).all() or np.any(relative <= 0)):
        raise ValueError('eps_r must be finite positive real scalar or one value per tetrahedron')
    relative = np.array(relative, dtype=float, copy=True)
    if not isinstance(conductors, Mapping) or not conductors:
        raise ValueError('conductors must be a nonempty ordered name-to-node mapping')
    names = tuple(conductors)
    if not all(isinstance(name, str) and name.strip() for name in names):
        raise ValueError('conductor names must be nonempty strings')
    signals = [_node_set(conductors[name], mesh.num_nodes, name) for name in names]
    ground = _node_set(ground, mesh.num_nodes, 'ground')
    fixed = np.concatenate([ground, *signals])
    if len(np.unique(fixed)) != len(fixed):
        raise ValueError('conductor and ground node sets must be disjoint')
    tets = mesh.tets
    graph = coo_matrix((np.ones(3*len(tets)),
        (np.repeat(tets[:,0],3), tets[:,1:].ravel())), shape=(mesh.num_nodes,mesh.num_nodes)).tocsr()
    components, labels = connected_components(graph, directed=False)
    if len(np.unique(labels[ground])) != components:
        raise ValueError('every connected mesh component must contain ground')
    return mesh, relative, names, signals, ground, fixed


def extract_capacitance_3d(mesh, *, eps_r=1., conductors, ground):
    """Extract static Maxwell C[F] using the shared galerkin P1 3D assembler.

    ``eps_r`` is finite positive real, scalar or one value per tetrahedron.
    ``conductors`` is an ordered name -> node-index mapping; all prescribed
    node sets must be disjoint. Every connected mesh component needs ground.
    Unprescribed exterior faces are insulating (zero normal displacement).
    The caller supplies a conforming mesh and chooses/refines the boundary;
    an arbitrary enclosing box is not automatically an open-space model.
    Geometric overlap/T-junction detection and meshing are not provided here.
    """
    mesh, relative, names, signals, ground, fixed = _prepare_inputs(mesh, eps_r, conductors, ground)
    tets = mesh.tets
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        k = assemble_stiffness_3d(mesh, eps=epsilon_0*relative)
    if not np.isfinite(k.data).all():
        raise ValueError('mesh and permittivity produced a nonfinite operator')
    free = np.setdiff1d(np.arange(mesh.num_nodes), fixed)
    potentials = np.zeros((mesh.num_nodes, len(names)))
    for j, nodes in enumerate(signals):
        potentials[nodes,j] = 1.
    if len(free):
        try:
            potentials[free] = splu(k[free][:,free].tocsc()).solve(-(k[free][:,fixed]@potentials[fixed]))
        except (RuntimeError, ValueError) as exc:
            raise ValueError('grounded electrostatic operator could not be solved') from exc
    charge = k@potentials
    c = np.array([charge[nodes].sum(axis=0) for nodes in signals])
    energy = potentials.T@charge
    ground_charge = charge[ground].sum(axis=0)
    scale = float(np.max(np.abs(c)))
    if not (np.isfinite(potentials).all() and np.isfinite(charge).all()
            and np.isfinite(energy).all() and np.isfinite(c).all() and np.isfinite(scale) and scale > 0):
        raise ValueError('extraction did not produce finite nonzero capacitance')
    residual = float(np.max(np.abs(charge[free]), initial=0)/scale)
    balance = float(np.max(np.abs(c.sum(axis=0)+ground_charge))/scale)
    agreement = float(np.max(np.abs(c-energy))/scale)
    symmetry = float(np.max(np.abs(c-c.T))/scale)
    # Diagnose the raw matrix; never repair it by symmetrizing or clipping.
    normalized = c/scale
    off_diagonal = normalized-np.diag(np.diag(normalized))
    if (max(residual, balance, agreement, symmetry) > 1e-8
            or np.min(np.linalg.eigvalsh(normalized)) <= 0
            or np.max(off_diagonal) > 1e-8 or np.max(ground_charge/scale) > 1e-8):
        raise ValueError('mesh or solve failed capacitance energy, charge or Maxwell-matrix checks')
    return Capacitance3D(names, _readonly(c), _readonly(energy), _readonly(potentials),
        _readonly(ground_charge), residual, balance, agreement, symmetry, len(tets))
