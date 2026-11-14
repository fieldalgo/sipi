# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit surface laws on retained straight-face shape-current energies."""
from dataclasses import dataclass
import numpy as np

from .boundary_conductor import SurfaceMetal
from .crosssection import CrossSection, Trace
from .face_conductor import ReferenceSurfaceMetals, _face_samples, _FACES
from .network import _frequencies, rlgc_network
from .panel_shape_face_conductor import PanelShapeFaceCurrentFactors, panel_shape_face_current_factors
from .shape_reference_conductor import _snapshot

__all__ = ['ShapeFaceConductorLoss', 'panel_shape_conductor_loss_by_face']


def _assigned_parts(factors, labels):
    """Admit only complete signal faces, bottom, then complete ground groups."""
    expected=tuple('signal:'+n+':'+face for n in factors.names for face in _FACES)+('reference:bottom',)
    if labels[:len(expected)]!=expected:
        raise ValueError('boundary labels must preserve signal faces followed by the bottom plane')
    trace_indices={name:i for i,name in enumerate(factors.trace_names)}
    values=[]
    for name in factors.names:
        i=trace_indices[name];values.extend(factors.parts[4*i:4*i+4])
    values.append(factors.parts[-1]);position=len(expected)
    for name in factors.base.ground_trace_names:
        whole='reference:ground:'+name;i=trace_indices[name]
        parts=factors.parts[4*i:4*i+4]
        if labels[position:position+1]==(whole,):
            values.append(parts.sum(axis=0));position+=1
        elif labels[position:position+4]==tuple(whole+':'+face for face in _FACES):
            values.extend(parts);position+=4
        else:raise ValueError('every grounded trace needs one whole boundary or all four ordered faces')
    if position!=len(labels) or len(set(labels))!=len(labels):
        raise ValueError('boundary labels must partition the retained energy exactly once')
    return np.array(values)


@dataclass(frozen=True)
class ShapeFaceConductorLoss:
    """Local face-weighted loss, retaining full shape and whole-current evidence.

    Ordered boundaries are four faces per signal, the bottom plane, then each
    grounded trace's whole perimeter or four faces, as explicitly requested.
    These energies do not provide signed face current integrals.
    """
    frequency: np.ndarray
    R: np.ndarray
    L_internal: np.ndarray
    skin_depth: np.ndarray
    roughness_factor: np.ndarray
    surface_impedance: np.ndarray
    metals: tuple
    factors: PanelShapeFaceCurrentFactors
    boundary_labels: tuple
    boundary_parts: np.ndarray

    def __post_init__(self):
        if not isinstance(self.factors,PanelShapeFaceCurrentFactors):
            raise TypeError('factors must retain explicit face shape-current evidence')
        f=_frequencies(self.frequency);n=len(self.factors.names)
        labels=tuple(self.boundary_labels);metals=tuple(self.metals);count=len(labels)
        expected=_assigned_parts(self.factors,labels)
        if len(metals)!=count or not all(isinstance(m,SurfaceMetal) for m in metals):
            raise ValueError('one SurfaceMetal is required for every ordered boundary')
        object.__setattr__(self,'boundary_labels',labels);object.__setattr__(self,'metals',metals)
        for key,shape in (('frequency',f.shape),('R',(len(f),n,n)),('L_internal',(len(f),n,n)),
                ('skin_depth',(len(f),count)),('roughness_factor',(len(f),count)),
                ('surface_impedance',(len(f),count)),('boundary_parts',(count,n,n))):
            array=_snapshot(getattr(self,key),complex if key=='surface_impedance' else float)
            if array.shape!=shape:raise ValueError(key+' has incorrect shape')
            object.__setattr__(self,key,array)
        if not np.array_equal(self.boundary_parts,expected):
            raise ValueError('boundary parts must preserve the assigned face-energy matrices')

    @property
    def resistance_parts(self):
        return _snapshot(self.surface_impedance.real[:,:,None,None]*self.boundary_parts[None])

    def network(self, *, C, G, length, z_ref=50.):
        return rlgc_network(self.frequency,R=self.R,L=self.factors.L_external+self.L_internal,
            C=C,G=G,length=length,z_ref=z_ref,names=self.factors.names)


def _shape_face_samples(section,frequency,conductors,reference,ground_thickness):
    if not isinstance(section,CrossSection):raise TypeError('section must be a CrossSection')
    if (section.bottom,section.top,section.sides)!=('ground','open','open'):
        raise ValueError('shape face loss requires bottom ground and open top/sides')
    if not 1<=len(section.traces)<=4 or any(not isinstance(t,Trace) for t in section.traces):
        raise ValueError('shape face loss requires 1..4 finite rectangular or tapered Trace conductors')
    if not isinstance(reference,ReferenceSurfaceMetals):
        raise TypeError('reference must explicitly be ReferenceSurfaceMetals')
    traces,_,f,metals,depth,correction,zs,surfaces=_face_samples(
        section,frequency,conductors,reference,ground_thickness)
    labels=tuple('signal:'+t.name+':'+face for t in traces for face in _FACES)+tuple(s[0] for s in surfaces)
    return tuple(t.name for t in traces),labels,f,metals,depth,correction,zs


def panel_shape_conductor_loss_by_face(section,frequency,*,conductors,reference,
        ground_thickness,panels_per_edge=32,ground_modes=512,interpolation_degree=16,
        step_fraction=1e-3):
    """Weight explicit straight-face shape energies by independent surface laws.

    conductors maps each signal to TraceFaceMetals. reference must explicitly
    give the bottom plane and each grounded trace's SurfaceMetal (whole) or
    TraceFaceMetals. Local bulk/coating/roughness laws and individual remaining
    core/skin-depth admission run before fields. Shape extraction keeps its
    original geometry, resource, two-step, reciprocity and PSD gates.

    R=sum(Re(Zs_b)*Q_b); internal L=sum(Im(Zs_b)*Q_b/omega). A whole ground
    assignment sums its four face energies, not the separately differentiated
    whole perimeter. Their agreement retains the existing 1e-4 face-sum gate.
    No rescaling, signed face flux, finite metal interior, coating corners,
    new default or automatic field-method fallback is introduced.
    """
    names,labels,f,metals,depth,correction,zs=_shape_face_samples(
        section,frequency,conductors,reference,ground_thickness)
    factors=panel_shape_face_current_factors(section,panels_per_edge=panels_per_edge,
        ground_modes=ground_modes,interpolation_degree=interpolation_degree,step_fraction=step_fraction)
    if (factors.names!=names or factors.trace_names!=tuple(t.name for t in section.traces)
            or factors.trace_ground!=tuple(t.ground for t in section.traces)):
        raise ValueError('shape extraction changed trace order')
    parts=_assigned_parts(factors,labels)
    resistance=np.einsum('fb,bij->fij',zs.real,parts)
    internal=np.einsum('fb,bij->fij',zs.imag/(2*np.pi*f[:,None]),parts)
    return ShapeFaceConductorLoss(f,resistance,internal,depth,correction,zs,metals,factors,labels,parts)
