# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Separate signal-face and reference surface laws on one PEC current field."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np

from .boundary_conductor import SurfaceMetal
from .conductor import SurfaceCurrentFactors, _readonly, _surface_current_data
from .crosssection import CrossSection, Trace
from .network import _frequencies, _scalar, rlgc_network

__all__ = ['TraceFaceMetals', 'ReferenceSurfaceMetals', 'FaceCurrentFactors', 'FaceConductorLoss',
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
class ReferenceSurfaceMetals:
    """Explicit laws for grounded planes/walls and complete ground traces.

    An open bottom/top/sides boundary must be None. Both side walls share one
    law. ``conductors`` maps exactly the grounded trace names to surface laws;
    each such trace shares one law over its complete perimeter. These local
    perturbative laws do not model coatings or current diffusion inside metal.
    """
    bottom: SurfaceMetal | None
    top: SurfaceMetal | None
    sides: SurfaceMetal | None
    conductors: Mapping[str, SurfaceMetal]

    def __post_init__(self):
        if any(m is not None and not isinstance(m, SurfaceMetal)
               for m in (self.bottom, self.top, self.sides)):
            raise ValueError('reference boundary must be a SurfaceMetal or None')
        if (not isinstance(self.conductors, Mapping)
                or any(not isinstance(k, str) or not k or not isinstance(m, SurfaceMetal)
                       for k, m in self.conductors.items())):
            raise ValueError('reference conductors must map names to SurfaceMetal objects')
        object.__setattr__(self, 'conductors', MappingProxyType(dict(self.conductors)))


@dataclass(frozen=True)
class FaceCurrentFactors:
    """Partitioned Ki*Kj integrals: four faces per signal, then reference groups.

    Whole-boundary factors retain the original current-flux diagnostic and C0.
    Partitioned integrals must sum back to each original boundary integral.
    """
    base: SurfaceCurrentFactors
    parts: np.ndarray
    current_integrals: np.ndarray
    reference_labels: tuple[str, ...] = ('reference',)

    def __post_init__(self):
        if not isinstance(self.base, SurfaceCurrentFactors):
            raise ValueError('base must contain whole-boundary surface-current factors')
        n = len(self.base.names)
        labels = tuple(self.reference_labels)
        if not labels or any(not isinstance(s, str) or not s for s in labels) or len(set(labels)) != len(labels):
            raise ValueError('reference labels must be nonempty and unique')
        object.__setattr__(self, 'reference_labels', labels)
        count = 4*n+len(labels)
        for key, shape in (('parts', (count, n, n)), ('current_integrals', (count, n))):
            values = _readonly(getattr(self, key))
            if values.shape != shape:
                raise ValueError(f'{key} has incorrect shape')
            grouped = np.concatenate([values[:4*n].reshape(n, 4, *shape[1:]).sum(axis=1),
                                      values[4*n:].sum(axis=0, keepdims=True)])
            if not np.allclose(grouped, getattr(self.base, key), rtol=1e-12, atol=1e-12):
                raise ValueError('face partition does not preserve whole-boundary integrals')
            object.__setattr__(self, key, values)

    @property
    def names(self): return self.base.names

    @property
    def labels(self):
        return tuple('signal:'+name+':'+face for name in self.names for face in _FACES)+self.reference_labels

    @property
    def C0(self): return self.base.C0

    @property
    def L_external(self): return self.base.L_external

    @property
    def current_error(self): return self.base.current_error


@dataclass(frozen=True)
class FaceConductorLoss:
    """Face-resolved R/internal L with retained reference group assignments."""
    frequency: np.ndarray
    R: np.ndarray
    L_internal: np.ndarray
    skin_depth: np.ndarray
    roughness_factor: np.ndarray
    surface_impedance: np.ndarray
    metals: tuple[SurfaceMetal, ...]
    factors: FaceCurrentFactors

    def __post_init__(self):
        f = _frequencies(self.frequency); n = len(self.factors.names); count = len(self.factors.labels)
        metals = tuple(self.metals)
        if len(metals) != count or not all(isinstance(m, SurfaceMetal) for m in metals):
            raise ValueError('metals must follow bottom/top/left/right per signal, then reference groups')
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


def _reference_parts(section, reference, thickness):
    grounded = tuple(t for t in section.traces if t.ground)
    if isinstance(reference, SurfaceMetal):
        minimum = min([thickness, section.width]+[t.minimum_dimension for t in grounded])
        return (reference,), [minimum], None
    if not isinstance(reference, ReferenceSurfaceMetals):
        raise ValueError('reference must be a SurfaceMetal or ReferenceSurfaceMetals')
    if set(reference.conductors) != {t.name for t in grounded}:
        raise ValueError('reference conductors must map exactly every ground trace name')
    metals, dimensions, surfaces = [], [], []
    for name, coordinate in (('bottom', 0.), ('top', section.height), ('sides', section.width/2)):
        metal = getattr(reference, name)
        if (metal is not None) != (getattr(section, name) == 'ground'):
            raise ValueError(f'reference {name} needs a metal exactly when that boundary is ground')
        if metal is not None:
            metals.append(metal)
            dimensions.append(min(thickness, section.width, section.height))
            surfaces.append(('reference:'+name, name, coordinate))
    for trace in grounded:
        metals.append(reference.conductors[trace.name]); dimensions.append(trace.minimum_dimension)
        surfaces.append(('reference:ground:'+trace.name, 'trace', trace))
    return tuple(metals), dimensions, tuple(surfaces)


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
    thickness = _scalar('ground_thickness', ground_thickness)
    reference_metals, reference_dimensions, surfaces = _reference_parts(section, reference, thickness)
    metals = tuple(m for name in names for m in conductors[name].metals)+reference_metals
    dimensions = [min(t.minimum_dimension, section.width) for t in traces for _ in _FACES]
    dimensions.extend(reference_dimensions)
    f = _frequencies(frequency)
    samples = [m._samples(f) for m in metals]
    depth = np.column_stack([s[1] for s in samples])
    for i, minimum in enumerate(dimensions):
        if minimum <= 0 or np.max(depth[:, i]) > minimum/5:
            label = (names[i//4]+':'+_FACES[i%4] if i < 4*len(names) else
                     'reference' if surfaces is None else surfaces[i-4*len(names)][0])
            raise ValueError(f'{label}: skin depth must be <= minimum conductor dimension / 5')
    tolerance = 1e-9*float(np.hypot(section.width, section.height))
    return (traces, tolerance, f, metals, depth, np.column_stack([s[2] for s in samples]),
            np.column_stack([s[3] for s in samples]), surfaces)


def _face_from_mesh(meshed, traces, tolerance, f, metals, depth, correction, zs, reference_surfaces=None):
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
    labels = ('reference',)
    if reference_surfaces is not None:
        selected = np.flatnonzero(owners == n)
        xy = meshed.mesh.nodes[edges[selected]]
        x, y = xy[:, :, 0], xy[:, :, 1]
        masks = []
        for _, kind, geometry in reference_surfaces:
            if kind in ('bottom', 'top'):
                mask = np.all(abs(y-geometry) <= tolerance, axis=1)
            elif kind == 'sides':
                mask = np.all(abs(abs(x)-geometry) <= tolerance, axis=1)
            else:
                mask = np.all(geometry.distance(x, y) <= tolerance, axis=1)
            masks.append(mask)
        hits = np.column_stack(masks)
        if np.any(hits.sum(axis=1) != 1) or not np.all(hits.any(axis=0)):
            raise ValueError('ground edges must partition uniquely into nonempty reference surfaces')
        groups[selected] = 4*n+np.argmax(hits, axis=1)
        labels = tuple(s[0] for s in reference_surfaces)
    parts, integrated = [], []
    for label in range(4*n+len(labels)):
        selected = groups == label
        weights, values = lengths[selected], currents[selected]
        parts.append(values.T@(weights[:, None]*values))
        integrated.append(np.sum(weights[:, None]*values, axis=0))
    factors = FaceCurrentFactors(base, parts, integrated, labels)
    resistance = np.einsum('fb,bij->fij', zs.real, factors.parts)
    internal = np.einsum('fb,bij->fij', zs.imag/(2*np.pi*f[:, None]), factors.parts)
    return FaceConductorLoss(f, resistance, internal, depth, correction, zs, metals, factors)


def surface_conductor_loss_by_face(section, frequency, *, conductors, reference,
                                   ground_thickness, **mesh_options):
    """Separate four signal-face laws and common or explicit reference laws.

    All local metal/skin-depth gates run before meshing. One vacuum PEC current
    solve is partitioned without missing/duplicated edges. The whole-conductor
    5% current-flux gate is unchanged; resistance/box convergence is separate.
    ReferenceSurfaceMetals selects active planes/walls and named ground traces;
    each ground trace still has one law for its entire perimeter. Plane/wall skin
    depth uses ground_thickness and box dimensions; a ground trace uses its own
    minimum dimension. Signal polygons and zero-thickness strips are unsupported.
    This first-order surface model is not finite-metal diffusion.
    """
    samples = _face_samples(section, frequency, conductors, reference, ground_thickness)
    return _face_from_mesh(section.mesh(**mesh_options), *samples)
