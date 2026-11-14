# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Separate whole-boundary return metals on explicit shape-current factors."""
from collections.abc import Mapping
from dataclasses import dataclass
import numpy as np

from .boundary_conductor import SurfaceMetal, _remaining_dimension
from .face_conductor import ReferenceSurfaceMetals, _reference_parts
from .crosssection import CrossSection
from .network import _frequencies, _scalar, rlgc_network
from .panel_shape_conductor import PanelShapeCurrentFactors, panel_shape_current_factors

__all__ = ['ShapeReferenceConductorLoss','panel_shape_conductor_loss_with_reference_metals']


def _snapshot(value, dtype=float):
    array = np.asarray(value,dtype=dtype)
    if not np.all(np.isfinite(array)):
        raise ValueError('nonfinite separate-reference loss result')
    return np.frombuffer(array.tobytes(),dtype=array.dtype).reshape(array.shape)


@dataclass(frozen=True)
class ShapeReferenceConductorLoss:
    """Whole signal boundaries, bottom plane, then named grounded traces.

    The original factors retain grouped reference currents and all shape
    samples. boundary_parts retains the ungrouped energy matrices in the
    same order as metals, labels, depth, roughness and surface impedance.
    """
    frequency: np.ndarray
    R: np.ndarray
    L_internal: np.ndarray
    skin_depth: np.ndarray
    roughness_factor: np.ndarray
    surface_impedance: np.ndarray
    metals: tuple[SurfaceMetal,...]
    factors: PanelShapeCurrentFactors
    boundary_labels: tuple[str,...]
    boundary_parts: np.ndarray

    def __post_init__(self):
        if not isinstance(self.factors,PanelShapeCurrentFactors):
            raise TypeError('factors must contain explicit shape currents')
        f=_frequencies(self.frequency);n=len(self.factors.names)
        labels=tuple(self.boundary_labels)
        expected=(tuple('signal:'+s for s in self.factors.names)+('reference:bottom',)+
                  tuple('reference:ground:'+s for s in self.factors.ground_trace_names))
        if labels!=expected:
            raise ValueError('boundary labels must follow signals, bottom plane and grounded traces')
        metals=tuple(self.metals);count=len(labels)
        if len(metals)!=count or not all(isinstance(m,SurfaceMetal) for m in metals):
            raise ValueError('one SurfaceMetal is required for every ordered boundary')
        object.__setattr__(self,'metals',metals);object.__setattr__(self,'boundary_labels',labels)
        for key,shape in (('frequency',f.shape),('R',(len(f),n,n)),('L_internal',(len(f),n,n)),
            ('skin_depth',(len(f),count)),('roughness_factor',(len(f),count)),
            ('surface_impedance',(len(f),count)),('boundary_parts',(count,n,n))):
            array=_snapshot(getattr(self,key),complex if key=='surface_impedance' else float)
            if array.shape!=shape:raise ValueError(key+' has incorrect shape')
            object.__setattr__(self,key,array)
        regrouped=np.concatenate((self.boundary_parts[n+1:],self.boundary_parts[n:n+1])).sum(axis=0)
        if (not np.array_equal(self.boundary_parts[:n],self.factors.parts[:n])
                or not np.array_equal(regrouped,self.factors.parts[-1])):
            raise ValueError('separate boundary parts must preserve original grouped current factors')

    @property
    def resistance_parts(self):
        return _snapshot(self.surface_impedance.real[:,:,None,None]*self.boundary_parts[None])

    def network(self, *, C, G, length, z_ref=50.):
        return rlgc_network(self.frequency,R=self.R,L=self.factors.L_external+self.L_internal,
            C=C,G=G,length=length,z_ref=z_ref,names=self.factors.names)


def _shape_reference_samples(section, frequency, conductors, reference, ground_thickness):
    if not isinstance(section,CrossSection):raise TypeError('section must be a CrossSection')
    if (section.bottom,section.top,section.sides)!=('ground','open','open'):
        raise ValueError('separate-reference shape loss requires bottom ground and open top/sides')
    signals=tuple(t for t in section.traces if not t.ground);names=tuple(t.name for t in signals)
    if not names or not isinstance(conductors,Mapping) or set(conductors)!=set(names):
        raise ValueError('conductors must map exactly every signal name to a SurfaceMetal')
    if not all(isinstance(conductors[n],SurfaceMetal) for n in names):
        raise ValueError('every signal boundary must have a SurfaceMetal')
    if not isinstance(reference,ReferenceSurfaceMetals):
        raise TypeError('reference must explicitly be ReferenceSurfaceMetals')
    if any(not isinstance(m,SurfaceMetal) for m in reference.conductors.values()):
        raise ValueError('grounded trace metals must apply to whole perimeters, not individual faces')
    thickness=_scalar('ground_thickness',ground_thickness)
    ref_metals,ref_dimensions,surfaces=_reference_parts(section,reference,thickness)
    metals=tuple(conductors[n] for n in names)+ref_metals
    labels=tuple('signal:'+n for n in names)+tuple(s[0] for s in surfaces)
    dimensions=[min(t.minimum_dimension,section.width) for t in signals]+ref_dimensions
    f=_frequencies(frequency);samples=[m._samples(f) for m in metals]
    depth=np.column_stack([s[1] for s in samples])
    for i,minimum in enumerate(dimensions):
        remaining=_remaining_dimension(metals[i],minimum)
        if remaining<=0 or np.max(depth[:,i])>remaining/5:
            raise ValueError(labels[i]+': skin depth must be <= minimum remaining conductor dimension / 5')
    correction=np.column_stack([s[2] for s in samples]);zs=np.column_stack([s[3] for s in samples])
    return names,metals,labels,f,depth,correction,zs


def panel_shape_conductor_loss_with_reference_metals(section, frequency, *, conductors, reference,
        ground_thickness, panels_per_edge=32, ground_modes=512, interpolation_degree=16,
        step_fraction=1e-3):
    """Weight each whole boundary's shape-current energy by its own surface law.

    conductors maps all signal names to SurfaceMetal. reference must explicitly
    be ReferenceSurfaceMetals, with a bottom plane and one whole-perimeter
    SurfaceMetal per grounded trace. Top/sides are open and face-specific laws
    are unsupported. Existing local bulk/coating/roughness and individual
    remaining-core skin-depth gates apply before fields. The common-reference
    API and its grouped outputs are unchanged.

    No new PDE/current approximation is selected: existing full shape factors
    provide the ungrouped matrices. R=sum(Re(Zs_b)*Q_b), and internal inductance
    is sum(Im(Zs_b)*Q_b/omega). Geometry, two-step and finite-domain limitations
    remain; local coatings do not resolve metal corners or interior diffusion.
    """
    names,metals,labels,f,depth,correction,zs=_shape_reference_samples(
        section,frequency,conductors,reference,ground_thickness)
    factors=panel_shape_current_factors(section,panels_per_edge=panels_per_edge,
        ground_modes=ground_modes,interpolation_degree=interpolation_degree,step_fraction=step_fraction)
    grounded=tuple(t.name for t in section.traces if t.ground)
    if factors.names!=names or factors.ground_trace_names!=grounded:
        raise ValueError('shape extraction changed boundary order')
    by_name={t.name:i for i,t in enumerate(section.traces)}
    indices=[by_name[n] for n in names]+[len(section.traces)]+[by_name[n] for n in grounded]
    parts=factors.boundary_step_parts[-1,indices]
    resistance=np.einsum('fb,bij->fij',zs.real,parts)
    internal=np.einsum('fb,bij->fij',zs.imag/(2*np.pi*f[:,None]),parts)
    return ShapeReferenceConductorLoss(f,resistance,internal,depth,correction,zs,metals,
        factors,labels,parts)
