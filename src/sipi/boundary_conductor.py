# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Distinct signal/reference metals in the PEC surface-current perturbation."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from .conductor import SurfaceCurrentFactors, _metal_samples, _readonly, surface_current_factors
from .network import _scalar, _frequencies, rlgc_network
from .roughness import CausalHuray, CannonballHuray, GroissRMS

__all__ = ['SurfaceMetal', 'BoundaryConductorLoss', 'surface_conductor_loss_by_boundary']


@dataclass(frozen=True)
class SurfaceMetal:
    """One uniform good-conductor surface law; geometry is checked separately.

    Conductivity is S/m, relative permeability dimensionless, RMS roughness m.
    Use either RMS Hammerstad correction or one explicit existing roughness
    model. No conversion between Ra, Rq and ten-point Rz is inferred.
    """
    conductivity: float
    relative_permeability: float = 1.
    roughness_rms: float = 0.
    roughness: CausalHuray | CannonballHuray | GroissRMS | None = None

    def __post_init__(self):
        for key in ('conductivity', 'relative_permeability', 'roughness_rms'):
            object.__setattr__(self, key, _scalar(key, getattr(self, key), zero=key == 'roughness_rms'))
        if self.roughness is not None:
            if not isinstance(self.roughness, (CausalHuray, CannonballHuray, GroissRMS)):
                raise TypeError('roughness must be a supported explicit roughness model')
            if self.roughness_rms != 0:
                raise ValueError('choose either roughness_rms or a roughness model')

    def _samples(self, frequency):
        return _metal_samples(frequency, self.conductivity, self.relative_permeability,
                              self.roughness_rms, self.roughness)


@dataclass(frozen=True)
class BoundaryConductorLoss:
    """R and internal L with separate metal columns: signals, then reference.

    ``skin_depth``, ``roughness_factor`` and ``surface_impedance`` have shape
    (frequencies, signals+1). Reference combines all ground surfaces, whose
    material must be identical. This is not independent top/bottom foil data.
    """
    frequency: np.ndarray
    R: np.ndarray
    L_internal: np.ndarray
    skin_depth: np.ndarray
    roughness_factor: np.ndarray
    surface_impedance: np.ndarray
    metals: tuple[SurfaceMetal, ...]
    factors: SurfaceCurrentFactors

    def __post_init__(self):
        f = _frequencies(self.frequency); n = len(self.factors.names)
        metals = tuple(self.metals)
        if len(metals) != n+1 or not all(isinstance(m, SurfaceMetal) for m in metals):
            raise ValueError('metals must follow signal order then reference')
        object.__setattr__(self, 'metals', metals)
        for key, shape in (('frequency', f.shape), ('R', (len(f), n, n)),
            ('L_internal', (len(f), n, n)), ('skin_depth', (len(f), n+1)),
            ('roughness_factor', (len(f), n+1)), ('surface_impedance', (len(f), n+1))):
            value = _readonly(getattr(self, key), dtype=complex if key == 'surface_impedance' else float)
            if value.shape != shape:
                raise ValueError(f'{key} has incorrect shape')
            object.__setattr__(self, key, value)

    @property
    def boundary_labels(self):
        return tuple('signal:'+name for name in self.factors.names)+('reference',)

    @property
    def resistance_parts(self):
        """Each boundary's R contribution, shape (frequency,boundary,N,N)."""
        return _readonly(self.surface_impedance.real[:, :, None, None]*self.factors.parts[None])

    def network(self, *, C, G, length, z_ref=50.):
        """Combine matched-geometry dielectric C/G with R and external+internal L."""
        return rlgc_network(self.frequency, R=self.R, L=self.factors.L_external+self.L_internal,
                            C=C, G=G, length=length, z_ref=z_ref, names=self.factors.names)


def _boundary_samples(section, frequency, conductors, reference, ground_thickness):
    names = tuple(t.name for t in section.traces if not t.ground)
    if not isinstance(conductors, Mapping) or set(conductors) != set(names) or not names:
        raise ValueError('conductors must map exactly every signal name to a SurfaceMetal')
    metals = tuple(conductors[name] for name in names)+(reference,)
    if not all(isinstance(m, SurfaceMetal) for m in metals):
        raise ValueError('all signal and reference metals must be SurfaceMetal objects')
    thickness = _scalar('ground_thickness', ground_thickness)
    dimensions = [min(t.minimum_dimension, section.width) for t in section.traces if not t.ground]
    dimensions.append(min([thickness, section.width]+[t.minimum_dimension for t in section.traces if t.ground]))
    f = _frequencies(frequency)
    samples = [metal._samples(f) for metal in metals]
    depth = np.column_stack([s[1] for s in samples])
    for index, minimum in enumerate(dimensions):
        if minimum <= 0 or np.max(depth[:, index]) > minimum/5:
            label = 'signal '+names[index] if index < len(names) else 'reference'
            raise ValueError(f'{label}: surface loss requires finite conductors and skin depth <= minimum conductor dimension / 5')
    return names, f, metals, depth, np.column_stack([s[2] for s in samples]), np.column_stack([s[3] for s in samples])


def _boundary_from_factors(factors, f, metals, depth, correction, zs):
    if factors.current_error > .05:
        raise ValueError(f'surface-current flux error {factors.current_error:.3%} exceeds 5%; refine the mesh')
    resistance = np.einsum('fb,bij->fij', zs.real, factors.parts)
    internal = np.einsum('fb,bij->fij', zs.imag/(2*np.pi*f[:, None]), factors.parts)
    return BoundaryConductorLoss(f, resistance, internal, depth, correction, zs, metals, factors)


def _boundary_from_mesh(meshed, names, f, metals, depth, correction, zs):
    factors = surface_current_factors(meshed.mesh, meshed.signals, meshed.ground)
    if factors.names != names:
        raise ValueError('meshing changed the signal boundary order')
    return _boundary_from_factors(factors, f, metals, depth, correction, zs)


def surface_conductor_loss_by_boundary(section, frequency, *, conductors, reference,
                                        ground_thickness, **mesh_options):
    """One SurfaceMetal per named signal, plus one common reference metal.

    Reuse one PEC vacuum current solve. For each boundary b, add Re(Zs_b) Q_b
    to R and Im(Zs_b) Q_b/omega to internal L. Each skin depth must be at most
    its own conductor's minimum dimension/5, checked before meshing. Reference
    uses ground_thickness, section width and every explicit ground trace.
    Current flux error above 5% is rejected; loss/outer convergence is separate.
    This is first-order surface perturbation, not finite-metal diffusion,
    independent foil-face assignment or proof of a roughness model's validity.
    """
    samples = _boundary_samples(section, frequency, conductors, reference, ground_thickness)
    return _boundary_from_mesh(section.mesh(**mesh_options), *samples)
