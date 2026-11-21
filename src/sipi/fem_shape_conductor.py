# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit vacuum P1 geometry-energy current factors with derivative checks."""
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np
from galerkin import Mesh, element_gradient
from galerkin.kernels import assemble_stiffness, solve_dirichlet
from galerkin.electrostatics import capacitance_matrix

from .constants import epsilon_0
from .conductor import SurfaceCurrentFactors, _surface_current_basis, surface_current_factors
from .quasistatic import _node_set
from .panel_shape_conductor import _frozen, _relative

__all__ = ['FEMShapeSample', 'FEMShapeCurrentFactors', 'FEMShapeCurrentError',
           'fem_shape_current_factors']


@dataclass(frozen=True)
class FEMShapeSample:
    """One vacuum matrix at a fixed-connectivity geometry perturbation."""
    extension: int
    group: int
    level: int
    sign: int
    displacement_m: float
    capacitance_per_permittivity: np.ndarray

    def __post_init__(self):
        if (self.extension not in (0, 1) or self.level not in (0, 1)
                or self.sign not in (-1, 1) or not 0 <= self.group <= 4
                or not np.isfinite(self.displacement_m) or self.displacement_m <= 0):
            raise ValueError('invalid FEM shape sample address')
        matrix = _frozen(self.capacitance_per_permittivity)
        if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
            raise ValueError('FEM shape capacitance must be square')
        object.__setattr__(self, 'capacitance_per_permittivity', matrix)


def _partial_array(value):
    if value is None:
        return None
    array = np.asarray(value, dtype=float)
    return np.frombuffer(array.tobytes(), dtype=float).reshape(array.shape)


class FEMShapeCurrentError(ValueError):
    """Retain completed observations when a field or numerical check fails."""
    def __init__(self, message, *, stage, base=None, extension_parts=None,
                 finite_difference_parts=None, samples=(), request=None, diagnostics=None):
        super().__init__(message)
        self.stage = stage
        self.base = base
        self.extension_parts = _partial_array(extension_parts)
        self.finite_difference_parts = _partial_array(finite_difference_parts)
        self.samples = tuple(samples)
        self.request = request
        self.diagnostics = MappingProxyType(dict(diagnostics or {}))


@dataclass(frozen=True)
class FEMShapeCurrentFactors:
    """Whole-group energies in 1/m; original gradient flux is kept separately.

    The first extension supplies parts. Neither extension is a signed-current
    reconstruction. base retains the original gradient energies and fluxes;
    current_error refers to that original gradient diagnostic. All reference
    surfaces share the final group, including disconnected grounded metals.
    """
    base: SurfaceCurrentFactors
    extension_parts: np.ndarray
    finite_difference_parts: np.ndarray
    step_m: float
    samples: tuple
    diagnostics: object

    def __post_init__(self):
        if not isinstance(self.base, SurfaceCurrentFactors):
            raise TypeError('base must retain the original surface-current factors')
        n = len(self.base.names)
        if not 1 <= n <= 4 or not np.isfinite(self.step_m) or self.step_m <= 0:
            raise ValueError('invalid FEM shape-current dimensions or step')
        for name, shape in [('extension_parts', (2, n+1, n, n)),
                            ('finite_difference_parts', (2, n+1, 2, n, n))]:
            value = _frozen(getattr(self, name))
            if value.shape != shape:
                raise ValueError('incomplete FEM shape-current observations')
            object.__setattr__(self, name, value)
        samples = tuple(self.samples)
        expected = [(e, g, l, s) for e in range(2) for g in range(n+1)
                    for l in range(2) for s in (-1, 1)]
        if len(samples) != len(expected) or any(not isinstance(s, FEMShapeSample) for s in samples):
            raise ValueError('all FEM shape samples are required')
        if [(s.extension, s.group, s.level, s.sign) for s in samples] != expected:
            raise ValueError('FEM shape samples must retain request order')
        if any(s.capacitance_per_permittivity.shape != (n, n)
               or s.displacement_m != self.step_m/(2**s.level) for s in samples):
            raise ValueError('FEM shape samples do not match the basis and steps')
        object.__setattr__(self, 'samples', samples)
        object.__setattr__(self, 'diagnostics', MappingProxyType(dict(self.diagnostics)))

    @property
    def names(self): return self.base.names
    @property
    def C0(self): return self.base.C0
    @property
    def L_external(self): return self.base.L_external
    @property
    def parts(self): return self.extension_parts[0]
    @property
    def total(self): return _frozen(self.parts.sum(axis=0))
    @property
    def current_integrals(self): return self.base.current_integrals
    @property
    def current_error(self): return self.base.current_error


def _signed_areas(nodes, triangles):
    p = nodes[triangles]
    a, b = p[:, 1]-p[:, 0], p[:, 2]-p[:, 0]
    return a[:, 0]*b[:, 1]-a[:, 1]*b[:, 0]


def _boundary_motion(mesh, signals, ground):
    """Preflight the boundary and prescribe coordinate-invariant normal motion."""
    if not isinstance(mesh, Mesh):
        raise TypeError('mesh must be a galerkin Mesh')
    if (not 1 <= len(signals) <= 4 or any(not isinstance(s, str) or not s for s in signals)):
        raise ValueError('FEM shape currents need 1..4 named signals')
    if not 3 <= mesh.num_nodes <= 300000 or not 1 <= mesh.num_triangles <= 600000:
        raise ValueError('FEM shape mesh exceeds the node or triangle budget')
    if mesh.nodes.shape != (mesh.num_nodes, 2) or not np.isfinite(mesh.nodes).all():
        raise ValueError('FEM shape coordinates must be finite planar points')
    if not np.all(_signed_areas(mesh.nodes, mesh.triangles) > 0):
        raise ValueError('FEM shape elements must have positive signed area')
    sets = [_node_set(name, nodes, mesh.num_nodes) for name, nodes in signals.items()]
    sets.append(_node_set('reference', ground, mesh.num_nodes))
    labels = np.full(mesh.num_nodes, -1, dtype=int)
    for i, nodes in enumerate(sets):
        if np.any(labels[nodes] >= 0):
            raise ValueError('conductor node sets overlap')
        labels[nodes] = i
    all_edges = mesh.triangles[:, [[0, 1], [1, 2], [2, 0]]].reshape(-1, 2)
    _, first, count = np.unique(np.sort(all_edges, axis=1), axis=0,
                                return_index=True, return_counts=True)
    if count.max() > 2:
        raise ValueError('FEM shape mesh must be manifold')
    edges = all_edges[first[count == 1]]
    group = labels[edges[:, 0]]
    group = np.where(group == labels[edges[:, 1]], group, -1)
    for i, nodes in enumerate(sets):
        if not np.array_equal(np.unique(edges[group == i]), nodes):
            raise ValueError('every conductor node must bound its dielectric metal edges')
    tangent = mesh.nodes[edges[:, 1]]-mesh.nodes[edges[:, 0]]
    normal = np.column_stack((tangent[:, 1], -tangent[:, 0]))/np.linalg.norm(tangent, axis=1)[:, None]
    fixed = np.unique(edges)
    incidence = [[] for _ in range(mesh.num_nodes)]
    for i, (a, b) in enumerate(edges):
        incidence[a].append(i); incidence[b].append(i)
    if any(len(incidence[node]) != 2 for node in fixed):
        raise ValueError('boundary nodes must have exactly two incident edges')
    values = np.zeros((len(sets), mesh.num_nodes, 2)); error = 0.
    for g, nodes in enumerate(sets):
        for node in nodes:
            hit = incidence[node]; a = normal[hit]; rhs = (group[hit] == g).astype(float)
            if rhs[0] == rhs[1]:
                denominator = 1+float(a[0]@a[1])
                if denominator <= 0:
                    raise ValueError('opposite boundary normals cannot define a shape motion')
                v = rhs[0]*(a[0]+a[1])/denominator
            else:
                v = np.linalg.solve(a, rhs)
            values[g, node] = v
            error = max(error, float(np.max(abs(a@v-rhs))))
    if not np.isfinite(values).all() or error > 1e-12:
        raise ValueError('FEM shape boundary normal residual exceeded')
    step = float(np.linalg.norm(mesh.nodes[all_edges[:, 1]]-mesh.nodes[all_edges[:, 0]], axis=1).min())*.001
    if not np.isfinite(step) or step <= 0:
        raise ValueError('FEM shape step must be positive and representable')
    return fixed, values, step, error


def fem_shape_current_factors(mesh, signals, ground):
    """Opt-in whole-boundary currents from a fixed-mesh vacuum energy derivative.

    Uses the unchanged public galerkin P1 assembly, Dirichlet and capacitance
    APIs. A harmonic boundary motion and a second, positive radial-weighted
    extension independently contract the field energy derivative. The primary
    extension supplies parts; no averaging, flux rescaling or PSD projection.

    Both extensions are checked against central capacitance differences at
    min_edge*1e-3 and half that step, entrywise to 1e-4 without a floor. All
    perturbed triangles are checked before any deformed solve. This needs
    8*(signals+1) capacitance requests plus two original voltage-basis calls
    and 4*(signals+1) scalar velocity solves. Open boundaries are insulating;
    all reference metals move together and share the last energy group.

    Extension agreement (1e-3 per whole matrix), reciprocity/PSD (1e-10), and
    finite-difference agreement are numerical consistency checks, not mesh,
    outer-domain or absolute/small-mutual accuracy bounds. The original
    gradient factors and flux diagnostics remain in base. Existing APIs and
    their numerical criteria are unchanged. No dielectric, skin or roughness
    law is applied by this vacuum-current function.
    """
    fixed, prescribed, h, normal_error = _boundary_motion(mesh, signals, ground)
    n = len(signals); base = None; parts = None; fd = None; samples = []; request = None
    diagnostics = dict(normal_velocity_error=normal_error, nodes=mesh.num_nodes,
                       triangles=mesh.num_triangles)
    stage = 'basis'
    try:
        _, _, _, _, stiffness, potential, c0, inverse = _surface_current_basis(mesh, signals, ground)
        base = surface_current_factors(mesh, signals, ground)
        if not np.array_equal(base.C0, c0):
            raise ValueError('original vacuum basis changed')
        if not np.isfinite(potential).all() or np.linalg.eigvalsh(c0).min() <= 0:
            raise ValueError('vacuum basis must be finite and positive definite')
        stage = 'extensions'
        gradient = np.stack([element_gradient(mesh, potential[:, j]) for j in range(n)], axis=-1)@(epsilon_0*inverse)
        area = mesh.areas(); center = mesh.nodes[mesh.triangles].mean(axis=1)
        origin = mesh.nodes[0]+(mesh.nodes-mesh.nodes[0]).mean(axis=0)
        radius2 = float(np.max(np.sum((mesh.nodes-origin)**2, axis=1)))
        weighted = assemble_stiffness(mesh, 1+.5*np.sum((center-origin)**2, axis=1)/radius2)
        free = np.setdiff1d(np.arange(mesh.num_nodes), fixed)
        velocities = []; energies = []; residuals = []
        gg = np.einsum('tdi,tdj->tij', gradient, gradient)
        for matrix in (stiffness, weighted):
            vs = []; qs = []
            for values in prescribed:
                v = np.column_stack([solve_dirichlet(matrix, np.zeros(mesh.num_nodes),
                    {tuple(fixed): values[fixed, j]}) for j in range(2)])
                residual = matrix@v
                denominator = max(1., float(np.max(abs(matrix[free][:, fixed]@v[fixed]), initial=0.)))
                residuals.append(float(np.max(abs(residual[free]), initial=0.)/denominator))
                dv = np.stack([element_gradient(mesh, v[:, j]) for j in range(2)], axis=1)
                div = np.trace(dv, axis1=1, axis2=2)
                stretch = np.einsum('tdi,tde,tej->tij', gradient, dv+dv.swapaxes(1, 2), gradient)
                qs.append(-np.einsum('t,tij->ij', area, div[:, None, None]*gg-stretch)); vs.append(v)
            velocities.append(vs); energies.append(qs)
        velocities = np.array(velocities); parts = np.array(energies)
        if not np.isfinite(parts).all() or not np.isfinite(velocities).all():
            raise ValueError('nonfinite FEM shape extension')
        diagnostics['velocity_residual'] = max(residuals)
        if max(residuals) > 1e-10:
            raise ValueError('FEM shape velocity residual exceeded')
        stage = 'offset-preflight'
        for e in range(2):
            for g in range(n+1):
                for level, delta in enumerate((h, h/2)):
                    for sign in (-1, 1):
                        request = (e, g, level, sign, delta)
                        nodes = mesh.nodes+sign*delta*velocities[e, g]
                        if not np.isfinite(nodes).all() or not np.all(_signed_areas(nodes, mesh.triangles) > 0):
                            raise ValueError('FEM shape offset inverts or degenerates a triangle')
        stage = 'capacitance-differences'; p = epsilon_0*inverse
        fd = np.zeros((2, n+1, 2, n, n))
        for e in range(2):
            for g in range(n+1):
                for level, delta in enumerate((h, h/2)):
                    for sign in (-1, 1):
                        request = (e, g, level, sign, delta)
                        moved = Mesh(mesh.nodes+sign*delta*velocities[e, g], mesh.triangles.copy(), mesh.boundary)
                        cap = np.asarray(capacitance_matrix(moved, relative_permittivity=1., conductors=signals, ground=ground))/epsilon_0
                        sample = FEMShapeSample(e, g, level, sign, delta, cap); samples.append(sample)
                        fd[e, g, level] += -sign*(p.T@cap@p)/(2*delta)
        request = None; stage = 'checks'
        diagnostics['finite_difference_errors'] = tuple(_relative(fd[:, :, i], parts) for i in (0, 1))
        diagnostics['step_error'] = _relative(fd[:, :, 0], fd[:, :, 1])
        scale = np.max(abs(parts), axis=(-1, -2))
        if np.any(scale <= 0):
            raise ValueError('each FEM shape boundary needs nonzero energy')
        diagnostics['extension_errors'] = tuple(float(np.max(abs(a-b))/np.max(abs(b))) for a, b in zip(parts[0], parts[1]))
        diagnostics['reciprocity_error'] = float(np.max(abs(parts-parts.swapaxes(-1, -2))/scale[:, :, None, None]))
        diagnostics['minimum_scaled_eigenvalue'] = float(np.min(np.linalg.eigvalsh(parts)/scale[:, :, None]))
        if max(diagnostics['finite_difference_errors']) > 1e-4 or diagnostics['step_error'] > 1e-4:
            raise ValueError('FEM shape finite-difference or step agreement exceeded')
        if max(diagnostics['extension_errors']) > .001:
            raise ValueError('FEM shape interior-extension agreement exceeded')
        if diagnostics['reciprocity_error'] > 1e-10 or diagnostics['minimum_scaled_eigenvalue'] < -1e-10:
            raise ValueError('FEM shape energies fail reciprocity or positive semidefiniteness')
        if any(np.linalg.eigvalsh(q.sum(axis=0)).min() <= 0 for q in parts):
            raise ValueError('total FEM shape energy must be positive definite')
        return FEMShapeCurrentFactors(base, parts, fd, h, tuple(samples), diagnostics)
    except Exception as exc:
        # Never turn KeyboardInterrupt/SystemExit into a failed numerical result.
        raise FEMShapeCurrentError(str(exc), stage=stage, base=base,
            extension_parts=parts, finite_difference_parts=fd, samples=samples,
            request=request, diagnostics=diagnostics) from exc
