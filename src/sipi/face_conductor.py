# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Separate signal-face surface laws on one PEC current distribution."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from .boundary_conductor import SurfaceMetal
from .conductor import SurfaceCurrentFactors, _readonly, _surface_current_data
from .crosssection import CrossSection, Trace
from .network import _frequencies, _scalar, rlgc_network

__all__ = ['TraceFaceMetals', 'FaceCurrentFactors', 'FaceConductorLoss',
           'surface_conductor_loss_by_face']

_FACES = ('bottom', 'top', 'left', 'right')


@dataclass(frozen=True)
class TraceFaceMetals:
    """Four explicit surface laws in global section coordinates.

    Left/right follow the sloping faces for a tapered Trace. These are local
    high-frequency surface impedances, not a bulk coating/diffusion model.
    """
    bottom: SurfaceMetal
    top: SurfaceMetal
    left: SurfaceMetal
    right: SurfaceMetal

    def __post_init__(self):
        if not all(isinstance(m, SurfaceMetal) for m in self.metals):
            raise ValueError('every trace face must have a SurfaceMetal')

    @property
    def metals(self):
        return tuple(getattr(self, name) for name in _FACES)

    @classmethod
    def uniform(cls, metal):
        return cls(metal, metal, metal, metal)


@dataclass(frozen=True)
class FaceCurrentFactors:
    """Partitioned Ki*Kj integrals: four faces per signal, then common reference.

    Whole-boundary factors retain the original current-flux diagnostic and C0.
    Partitioned integrals must sum back to each original boundary integral.
    """
    base: SurfaceCurrentFactors
    parts: np.ndarray
    current_integrals: np.ndarray

    def __post_init__(self):
        if not isinstance(self.base, SurfaceCurrentFactors):
            raise ValueError('base must contain whole-boundary surface-current factors')
        n = len(self.base.names)
        for key, shape in (('parts', (4*n+1, n, n)), ('current_integrals', (4*n+1, n))):
            values = _readonly(getattr(self, key))
            if values.shape != shape:
                raise ValueError(f'{key} has incorrect shape')
            grouped = np.concatenate([values[:-1].reshape(n, 4, *shape[1:]).sum(axis=1), values[-1:]])
            if not np.allclose(grouped, getattr(self.base, key), rtol=1e-12, atol=1e-12):
                raise ValueError('face partition does not preserve whole-boundary integrals')
            object.__setattr__(self, key, values)

    @property
    def names(self): return self.base.names

    @property
    def labels(self):
        return tuple('signal:'+name+':'+face for name in self.names for face in _FACES)+('reference',)

    @property
    def C0(self): return self.base.C0

    @property
    def L_external(self): return self.base.L_external

    @property
    def current_error(self): return self.base.current_error


@dataclass(frozen=True)
class FaceConductorLoss:
    """Face-resolved R/internal L; all reference surfaces share one law."""
    frequency: np.ndarray
    R: np.ndarray
    L_internal: np.ndarray
    skin_depth: np.ndarray
    roughness_factor: np.ndarray
    surface_impedance: np.ndarray
    metals: tuple[SurfaceMetal, ...]
    factors: FaceCurrentFactors

    def __post_init__(self):
        f = _frequencies(self.frequency); n = len(self.factors.names); count = 4*n+1
        metals = tuple(self.metals)
        if len(metals) != count or not all(isinstance(m, SurfaceMetal) for m in metals):
            raise ValueError('metals must follow bottom/top/left/right per signal, then reference')
        object.__setattr__(self, 'metals', metals)
        for key, shape in (('frequency', f.shape), ('R', (len(f), n, n)),
            ('L_internal', (len(f), n, n)), ('skin_depth', (len(f), count)),
            ('roughness_factor', (len(f), count)), ('surface_impedance', (len(f), count))):
            values = _readonly(getattr(self, key), dtype=complex if key == 'surface_impedance' else float)
            if values.shape != shape:
                raise ValueError(f'{key} has incorrect shape')
            object.__setattr__(self, key, values)

    @property
    def boundary_labels(self): return self.factors.labels

    @property
    def resistance_parts(self):
        return _readonly(self.surface_impedance.real[:, :, None, None]*self.factors.parts[None])

    def network(self, *, C, G, length, z_ref=50.):
        return rlgc_network(self.frequency, R=self.R, L=self.factors.L_external+self.L_internal,
                            C=C, G=G, length=length, z_ref=z_ref, names=self.factors.names)


def _face_samples(section, frequency, conductors, reference, ground_thickness):
    if not isinstance(section, CrossSection):
        raise ValueError('face surface loss requires a CrossSection')
    traces = tuple(t for t in section.traces if not t.ground)
    names = tuple(t.name for t in traces)
    if not traces or any(not isinstance(t, Trace) or t.thickness <= 0 for t in traces):
        raise ValueError('signal faces require finite rectangular or tapered Trace conductors')
    if not isinstance(conductors, Mapping) or set(conductors) != set(names):
        raise ValueError('conductors must map exactly every signal name to TraceFaceMetals')
    if not all(isinstance(conductors[name], TraceFaceMetals) for name in names):
        raise ValueError('every signal must have TraceFaceMetals')
    if not isinstance(reference, SurfaceMetal):
        raise ValueError('reference must be a SurfaceMetal')
    metals = tuple(m for name in names for m in conductors[name].metals)+(reference,)
    thickness = _scalar('ground_thickness', ground_thickness)
    dimensions = [min(t.minimum_dimension, section.width) for t in traces for _ in _FACES]
    dimensions.append(min([thickness, section.width]+[t.minimum_dimension for t in section.traces if t.ground]))
    f = _frequencies(frequency)
    samples = [m._samples(f) for m in metals]
    depth = np.column_stack([s[1] for s in samples])
    for i, minimum in enumerate(dimensions):
        if minimum <= 0 or np.max(depth[:, i]) > minimum/5:
            label = names[i//4]+':'+_FACES[i%4] if i < 4*len(names) else 'reference'
            raise ValueError(f'{label}: skin depth must be <= minimum conductor dimension / 5')
    tolerance = 1e-9*float(np.hypot(section.width, section.height))
    return traces, tolerance, f, metals, depth, np.column_stack([s[2] for s in samples]), np.column_stack([s[3] for s in samples])


def _face_from_mesh(meshed, traces, tolerance, f, metals, depth, correction, zs):
    base, edges, owners, lengths, currents = _surface_current_data(meshed.mesh, meshed.signals, meshed.ground)
    if base.names != tuple(t.name for t in traces):
        raise ValueError('meshing changed signal order')
    if base.current_error > .05:
        raise ValueError(f'surface-current flux error {base.current_error:.3%} exceeds 5%; refine the mesh')
    n = len(traces)
    groups = np.full(len(edges), 4*n, dtype=int)
    for i, trace in enumerate(traces):
        selected = np.flatnonzero(owners == i)
        xy = meshed.mesh.nodes[edges[selected]]
        x, y = xy[:, :, 0], xy[:, :, 1]
        hits = np.column_stack([np.all(abs(y-trace.y) <= tolerance, axis=1),
                                np.all(abs(y-trace.y1) <= tolerance, axis=1),
                                np.all(abs(x-(trace.x-trace.width_at(y)/2)) <= tolerance, axis=1),
                                np.all(abs(x-(trace.x+trace.width_at(y)/2)) <= tolerance, axis=1)])
        if np.any(hits.sum(axis=1) != 1) or not np.all(hits.any(axis=0)):
            raise ValueError('signal edges must partition uniquely into four nonempty trace faces')
        groups[selected] = 4*i+np.argmax(hits, axis=1)
    parts, integrated = [], []
    for label in range(4*n+1):
        selected = groups == label
        weights, values = lengths[selected], currents[selected]
        parts.append(values.T@(weights[:, None]*values))
        integrated.append(np.sum(weights[:, None]*values, axis=0))
    factors = FaceCurrentFactors(base, parts, integrated)
    resistance = np.einsum('fb,bij->fij', zs.real, factors.parts)
    internal = np.einsum('fb,bij->fij', zs.imag/(2*np.pi*f[:, None]), factors.parts)
    return FaceConductorLoss(f, resistance, internal, depth, correction, zs, metals, factors)


def surface_conductor_loss_by_face(section, frequency, *, conductors, reference,
                                   ground_thickness, **mesh_options):
    """Separate four signal-face laws; one common law for all reference surfaces.

    All local metal/skin-depth gates run before meshing. One vacuum PEC current
    solve is partitioned without missing/duplicated edges. The whole-conductor
    5% current-flux gate is unchanged; resistance/box convergence is separate.
    Signal polygons, zero-thickness strips and separate reference-face laws are
    unsupported. This first-order surface model is not finite-metal diffusion.
    """
    samples = _face_samples(section, frequency, conductors, reference, ground_thickness)
    return _face_from_mesh(section.mesh(**mesh_options), *samples)
