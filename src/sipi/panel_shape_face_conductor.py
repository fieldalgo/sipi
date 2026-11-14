# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit straight-face current energy from capacitance shape derivatives."""
from dataclasses import dataclass
from types import MappingProxyType
import numpy as np
from .crosssection import CrossSection,Layer,Trace
from .polygons import PolygonTrace
from .panel_shape_conductor import (PanelShapeRequest,PanelShapeSample,PanelShapeCurrentFactors,
    panel_shape_current_factors,_prepare,_offset_velocity,_relative,_frozen,_DIAGNOSTICS)
from .panel_conductor import _panel_solver

__all__=['PanelShapeFaceCurrentFactors','PanelShapeFaceCurrentError','panel_shape_face_current_factors']
_FACES=('bottom','top','left','right')
_EDGES=(0,2,3,1)


class PanelShapeFaceCurrentError(ValueError):
    """Retain whole currents and all completed face requests on failure."""
    def __init__(self,message,*,base,samples,request=None,step_parts=None):
        super().__init__(message)
        self.base=base;self.samples=tuple(samples);self.request=request
        self.step_parts=None if step_parts is None else _frozen(step_parts)


@dataclass(frozen=True)
class PanelShapeFaceCurrentFactors:
    """Ki*Kj energy per straight face, retaining original whole-current evidence.

    Each trace's bottom/top/left/right faces follow geometry order; the bottom
    plane is last. These energy matrices do not determine signed face currents.
    Use base.current_integrals for the original grouped conservation diagnostic.
    """
    base: PanelShapeCurrentFactors
    trace_names: tuple
    trace_ground: tuple
    step_parts: np.ndarray
    samples: tuple
    diagnostics: object

    def __post_init__(self):
        if not isinstance(self.base,PanelShapeCurrentFactors):raise TypeError('base must retain whole shape-current evidence')
        names=tuple(self.trace_names);ground=tuple(self.trace_ground);n=len(self.base.names)
        if (not 1<=len(names)<=4 or len(names)!=len(ground) or len(set(names))!=len(names)
            or not all(isinstance(v,bool) for v in ground)
            or tuple(name for name,g in zip(names,ground) if not g)!=self.base.names
            or tuple(name for name,g in zip(names,ground) if g)!=self.base.ground_trace_names):
            raise ValueError('trace metadata must preserve original signal and ground order')
        parts=_frozen(self.step_parts)
        if parts.shape!=(2,4*len(names)+1,n,n):raise ValueError('two complete face-energy observations are required')
        samples=tuple(self.samples)
        if len(samples)!=16*len(names) or not all(isinstance(s,PanelShapeSample) for s in samples):
            raise ValueError('all face derivative samples must be retained')
        object.__setattr__(self,'trace_names',names);object.__setattr__(self,'trace_ground',ground)
        object.__setattr__(self,'step_parts',parts);object.__setattr__(self,'samples',samples)
        object.__setattr__(self,'diagnostics',MappingProxyType(dict(self.diagnostics)))

    @property
    def names(self):return self.base.names
    @property
    def C0(self):return self.base.C0
    @property
    def L_external(self):return self.base.L_external
    @property
    def parts(self):return self.step_parts[-1]
    @property
    def total(self):return _frozen(self.parts.sum(axis=0))
    @property
    def labels(self):
        return tuple(('reference:ground:' if g else 'signal:')+name+':'+face
            for name,g in zip(self.trace_names,self.trace_ground) for face in _FACES)+('reference:bottom',)
    @property
    def whole_boundary_step_parts(self):
        n=len(self.names)
        return _frozen(np.concatenate((self.step_parts[:,:-1].reshape(2,len(self.trace_names),4,n,n).sum(axis=2),
                                       self.step_parts[:,-1:]),axis=1))


def _face_velocity(points,edge):
    """Continuous vertex motion: unit inward normal on one edge, zero on others."""
    points,_,lengths=_offset_velocity(points)
    tangent=(np.roll(points,-1,axis=0)-points)/lengths[:,None]
    normal=np.column_stack((tangent[:,1],-tangent[:,0]));velocity=[]
    for i in range(len(points)):
        previous=(i-1)%len(points)
        velocity.append(np.linalg.solve(normal[[previous,i]],-np.array([float(previous==edge),float(i==edge)])))
    return points,np.array(velocity)


def _prepare_faces(section,panels_per_edge,ground_modes,interpolation_degree,step_fraction):
    if not isinstance(section,CrossSection):raise TypeError('section must be a CrossSection')
    if not 1<=len(section.traces)<=4 or any(not isinstance(t,Trace) for t in section.traces):
        raise ValueError('face shape currents require 1..4 rectangular or tapered Trace conductors')
    checked,h,original=_prepare(section,panels_per_edge,ground_modes,interpolation_degree,step_fraction)
    points=original[0].polygons;motions=[[_face_velocity(p,e)[1] for e in _EDGES] for p in points];requests=[]
    for level,delta in enumerate((h,h/2)):
        for i,trace in enumerate(checked.traces):
            for face,velocity in zip(_FACES,motions[i]):
                for sign in (-1,1):
                    moved=[p.copy() for p in points];moved[i]+=sign*delta*velocity
                    traces=[PolygonTrace(t.name,p-[checked.width/2,0.],ground=t.ground) for t,p in zip(checked.traces,moved)]
                    CrossSection([Layer('vacuum',checked.height,1.)],traces,checked.width)
                    for p in moved:_offset_velocity(p)
                    requests.append(PanelShapeRequest(f'face-step-{level}/trace-{i}/{face}/sign-{sign}',tuple(moved),
                        checked.width,checked.height,original[0].panels_per_edge,original[0].ground_modes,original[0].interpolation_degree))
    return checked,h,tuple(requests)


def panel_shape_face_current_factors(section,*,panels_per_edge=32,ground_modes=512,
                                    interpolation_degree=16,step_fraction=1e-3):
    """Opt-in finite-domain energy matrices for individual straight faces.

    Supports 1..4 finite rectangular/tapered Trace conductors, bottom ground
    and open top/sides. Uses 20*n+5 public shared solves (at most 85), retaining
    existing whole-boundary results plus 16 face samples per trace. Every
    offset is preflighted before fields. Existing whole-current failures retain
    their original type/evidence; later failures retain the completed base.

    Two step sizes and face-to-whole sums must agree entrywise to 1e-4 with no
    denominator floor. Reciprocity/PSD use 1e-10. No PSD projection, flux-based
    correction, fallback or existing default change is performed. These checks
    are not a panel/outer convergence or absolute/small-entry accuracy bound.
    """
    checked,h,requests=_prepare_faces(section,panels_per_edge,ground_modes,interpolation_degree,step_fraction)
    base=panel_shape_current_factors(checked,panels_per_edge=panels_per_edge,ground_modes=ground_modes,
        interpolation_degree=interpolation_degree,step_fraction=step_fraction)
    solver=_panel_solver();samples=[]
    for request in requests:
        try:
            result=solver(**request.arguments())
            samples.append(PanelShapeSample(request,result.capacitance_per_permittivity,
                {key:getattr(result,key) for key in _DIAGNOSTICS}))
        except Exception as exc:
            raise PanelShapeFaceCurrentError(f'{request.stage}: {type(exc).__name__}: {exc}',
                base=base,samples=samples,request=request) from exc
    signal=[i for i,t in enumerate(checked.traces) if not t.ground]
    cap=base.samples[0].capacitance_per_permittivity;potential=np.zeros((len(checked.traces),len(signal)))
    potential[signal]=np.linalg.inv(cap[np.ix_(signal,signal)])
    rows=[];position=0
    for level,delta in enumerate((h,h/2)):
        parts=[]
        for _ in range(4*len(checked.traces)):
            minus,plus=samples[position:position+2];position+=2
            value=potential.T@(-(plus.capacitance_per_permittivity-minus.capacitance_per_permittivity)/(2*delta))@potential
            if not np.all(np.isfinite(value)):
                raise PanelShapeFaceCurrentError('face derivative is nonfinite',base=base,samples=samples)
            if _relative(value,value.T)>1e-10:
                raise PanelShapeFaceCurrentError('face matrix reciprocity residual exceeded',base=base,samples=samples)
            parts.append((value+value.T)/2)
        parts.append(base.boundary_step_parts[level,-1]);rows.append(parts)
    rows=np.array(rows);evidence=dict(base=base,samples=samples,step_parts=rows)
    difference=max(_relative(rows[0],rows[1]),_relative(rows[0].sum(axis=0),rows[1].sum(axis=0)))
    if not np.isfinite(difference) or difference>1e-4:raise PanelShapeFaceCurrentError('face difference steps did not agree',**evidence)
    n=len(signal);whole=np.concatenate((rows[:,:-1].reshape(2,len(checked.traces),4,n,n).sum(axis=2),rows[:,-1:]),axis=1)
    sum_error=_relative(whole,base.boundary_step_parts)
    if not np.isfinite(sum_error) or sum_error>1e-4:raise PanelShapeFaceCurrentError('face sums did not agree with whole-boundary derivatives',**evidence)
    if np.any(np.linalg.eigvalsh(rows).min(axis=-1)<-1e-10*np.max(abs(rows),axis=(-1,-2))):
        raise PanelShapeFaceCurrentError('face matrix is not positive semidefinite',**evidence)
    if np.linalg.eigvalsh(rows.sum(axis=1)).min()<=0:
        raise PanelShapeFaceCurrentError('face total is not positive definite',**evidence)
    diagnostics=dict(base.diagnostics,solve_count=len(base.samples)+len(samples),face_solve_count=len(samples),
        face_step_relative_change=difference,whole_sum_relative_change=sum_error)
    return PanelShapeFaceCurrentFactors(base,tuple(t.name for t in checked.traces),tuple(t.ground for t in checked.traces),
        rows,tuple(samples),diagnostics)
