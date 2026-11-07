# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Local electrostatic matrices for round conductors in a grounded ellipse."""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
from numbers import Integral

import numpy as np
from shapely.geometry import Point, Polygon
from meshine import Domain, generate
from galerkin import from_mesher

from .document import _keys, _number, _unique_object
from .quasistatic import capacitance_matrix

__all__ = ['RoundConductor', 'EllipticalAperture', 'MeshedAperture', 'ApertureSectionDocument']


@dataclass(frozen=True)
class RoundConductor:
    """A named PEC circle, with diameter and centre coordinates in metres."""
    name: str
    diameter: float
    x: float = 0.
    y: float = 0.

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip() or '\n' in self.name or '\r' in self.name:
            raise ValueError('conductor name must be a nonempty single-line string')
        if self.name == 'ground':
            raise ValueError('ground is reserved for the aperture boundary')
        for name in ('diameter', 'x', 'y'):
            object.__setattr__(self, name, _number(getattr(self, name), name))
        if self.diameter <= 0:
            raise ValueError('conductor diameter must be positive')


@dataclass(frozen=True)
class MeshedAperture:
    """Inspectable shared mesh, ordered signal node sets and ground nodes."""
    mesh: object
    signals: dict
    ground: np.ndarray


@dataclass(frozen=True)
class EllipticalAperture:
    """One or two round conductors inside an axis-aligned grounded ellipse.

    width/height are full axis lengths in metres. The ellipse centre is zero.
    C' is a local per-length electrostatic matrix, not a 3D transition model.
    Explicit mesh preflight checks disk containment against the inscribed
    outer polygon; insufficient angular resolution is rejected.
    """
    width: float
    height: float
    conductors: tuple[RoundConductor, ...]
    eps_r: float = 1.
    tan_delta: float = 0.

    def __post_init__(self):
        for name in ('width', 'height', 'eps_r', 'tan_delta'):
            object.__setattr__(self, name, _number(getattr(self, name), name))
        if self.width <= 0 or self.height <= 0 or self.eps_r <= 0 or self.tan_delta < 0:
            raise ValueError('axis lengths and eps_r must be positive; tan_delta nonnegative')
        if not math.isfinite(self.eps_r*self.tan_delta):
            raise ValueError('complex permittivity must remain finite')
        try:
            conductors = tuple(self.conductors)
        except TypeError as exc:
            raise ValueError('conductors must contain one or two RoundConductor objects') from exc
        if len(conductors) not in (1, 2) or any(not isinstance(c, RoundConductor) for c in conductors):
            raise ValueError('conductors must contain one or two RoundConductor objects')
        if len({c.name for c in conductors}) != len(conductors):
            raise ValueError('conductor names must be unique')
        object.__setattr__(self, 'conductors', conductors)
        # Cheap necessary bounds; polygon half-plane tests complete containment
        # validation when the angular resolution is explicitly known.
        for c in conductors:
            if not (abs(c.x/self.width)+c.diameter/self.width/2 < .5
                    and abs(c.y/self.height)+c.diameter/self.height/2 < .5):
                raise ValueError('conductor must fit strictly inside the aperture bounds')
        if len(conductors) == 2:
            a, b = conductors
            scale = max(self.width, self.height)
            distance = math.hypot(a.x/scale-b.x/scale, a.y/scale-b.y/scale)
            if distance <= a.diameter/scale/2+b.diameter/scale/2:
                raise ValueError('round conductors must not touch or overlap')

    @property
    def names(self):
        return tuple(c.name for c in self.conductors)

    def _curves(self, n):
        scale = max(self.width, self.height)
        theta = np.arange(n)*2*np.pi/n
        direction = np.column_stack([np.cos(theta), np.sin(theta)])
        outer = direction*np.array([self.width/scale, self.height/scale])/2
        # Geometry order is independent of conductor names or requested output
        # order, so relabelling does not select a different triangulation.
        ordered = sorted(self.conductors, key=lambda c: (c.x, c.y, c.diameter))
        holes = [np.array([c.x/scale, c.y/scale])+c.diameter/scale/2*direction for c in ordered]
        return outer, ordered, holes

    def mesh_settings(self, *, size=None, angular_divisions=128):
        scale = max(self.width, self.height)
        size = scale/48 if size is None else _number(size, 'size')
        if size <= 0 or not 0 < size/scale < math.inf:
            raise ValueError('size must be positive and representable relative to the aperture')
        if (isinstance(angular_divisions, (bool, np.bool_)) or not isinstance(angular_divisions, Integral)
                or angular_divisions < 16):
            raise ValueError('angular_divisions must be an integer >= 16')
        n = int(angular_divisions)
        outer, ordered, _ = self._curves(n)
        edges = np.roll(outer, -1, axis=0)-outer
        lengths = np.linalg.norm(edges, axis=1)
        if not np.isfinite(lengths).all() or np.any(lengths == 0):
            raise ValueError('aperture polygon edges must be representable')
        for c in ordered:
            delta = np.array([c.x/scale, c.y/scale])-outer
            signed = (edges[:, 0]*delta[:, 1]-edges[:, 1]*delta[:, 0])/lengths
            if np.min(signed)-c.diameter/scale/2 <= 32*np.finfo(float).eps:
                raise ValueError('conductor disk does not fit inside the aperture polygon; check geometry or angular resolution')
        return dict(size=float(size), angular_divisions=n)

    def mesh(self, *, size=None, angular_divisions=128):
        options = self.mesh_settings(size=size, angular_divisions=angular_divisions)
        scale = max(self.width, self.height)
        outer, ordered, holes = self._curves(options['angular_divisions'])
        shapes = [Polygon(p) for p in [outer, *holes]]
        domain = Domain(size=options['size']/scale)
        domain.add_region('dielectric', outer, holes=holes)

        def boundary(point):
            p = Point(point)
            index = min(range(len(shapes)), key=lambda i: shapes[i].exterior.distance(p))
            return 'ground' if index == 0 else ordered[index-1].name

        mesh = from_mesher(generate(domain, boundary))
        mesh.nodes *= scale
        with np.errstate(over='ignore', under='ignore', invalid='ignore'):
            areas = mesh.areas()
        if not np.isfinite(areas).all() or np.any(areas < np.finfo(float).tiny):
            raise ValueError('dimensional mesh areas must be positive, finite and normally representable')
        return MeshedAperture(mesh, {name: mesh.boundary[name] for name in self.names}, mesh.boundary['ground'])

    def capacitance(self, *, size=None, angular_divisions=128):
        """Complex Maxwell C' [F/m] in the input conductor order."""
        meshed = self.mesh(size=size, angular_divisions=angular_divisions)
        c0 = capacitance_matrix(meshed.mesh, 1., meshed.signals, meshed.ground)
        with np.errstate(over='ignore', under='ignore', invalid='ignore'):
            value = c0*self.eps_r-1j*(c0*(self.eps_r*self.tan_delta))
        if not np.isfinite(value).all() or np.any(np.linalg.eigvalsh(value.real) <= 0):
            raise ValueError('capacitance must be finite with a positive definite real part')
        return value

    def mixed_capacitance(self, *, size=None, angular_divisions=128):
        """Two-conductor C' in (differential, common) power-dual coordinates.

        Vd=V1-V2, Vc=(V1+V2)/2; Qd=(Q1-Q2)/2, Qc=Q1+Q2.
        Off-diagonal terms remain; these coordinates need not be eigenmodes.
        """
        if len(self.conductors) != 2:
            raise ValueError('mixed capacitance requires two conductors')
        transform = np.array([[.5, 1.], [-.5, 1.]])
        return transform.T@self.capacitance(size=size, angular_divisions=angular_divisions)@transform


class ApertureSectionDocument:
    """Strict sipi.aperture-section/1 snapshot, separate from circular-aperture/1."""
    def __init__(self, section: EllipticalAperture, *, mesh=None):
        if not isinstance(section, EllipticalAperture):
            raise TypeError('section must be an EllipticalAperture')
        self._assign(dict(schema='sipi.aperture-section/1', length_unit='m',
            aperture=dict(width=section.width, height=section.height),
            conductors=[dict(name=c.name, diameter=c.diameter, x=c.x, y=c.y) for c in section.conductors],
            dielectric=dict(eps_r=section.eps_r, tan_delta=section.tan_delta), mesh={} if mesh is None else mesh))

    def _assign(self, data):
        _keys(data, ('schema', 'length_unit', 'aperture', 'conductors', 'dielectric', 'mesh'), where='aperture section')
        if data['schema'] != 'sipi.aperture-section/1' or data['length_unit'] != 'm':
            raise ValueError('unsupported aperture-section schema or units')
        _keys(data['aperture'], ('width', 'height'), where='aperture axes')
        _keys(data['dielectric'], ('eps_r', 'tan_delta'), where='dielectric')
        _keys(data['mesh'], (), ('size', 'angular_divisions'), where='aperture mesh')
        if not isinstance(data['conductors'], list):
            raise ValueError('conductors must be an array')
        conductors = []
        for row in data['conductors']:
            _keys(row, ('name', 'diameter', 'x', 'y'), where='round conductor')
            conductors.append(RoundConductor(**row))
        section = EllipticalAperture(**data['aperture'], conductors=conductors, **data['dielectric'])
        options = section.mesh_settings(**data['mesh'])
        self._data = dict(schema=data['schema'], length_unit='m',
            aperture=dict(width=section.width, height=section.height),
            conductors=[dict(name=c.name, diameter=c.diameter, x=c.x, y=c.y) for c in section.conductors],
            dielectric=dict(eps_r=section.eps_r, tan_delta=section.tan_delta), mesh=options)

    @classmethod
    def from_dict(cls, data):
        out = cls.__new__(cls)
        out._assign(data)
        return out

    @classmethod
    def loads(cls, text):
        def reject(value):
            raise ValueError(f'nonfinite JSON number: {value}')
        return cls.from_dict(json.loads(text, object_pairs_hook=_unique_object, parse_constant=reject))

    def dumps(self):
        return json.dumps(self._data, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)

    def to_dict(self):
        return json.loads(self.dumps())

    @property
    def section(self):
        return EllipticalAperture(**self._data['aperture'],
            conductors=[RoundConductor(**c) for c in self._data['conductors']], **self._data['dielectric'])

    @property
    def mesh_options(self):
        return dict(self._data['mesh'])

    def analyze(self):
        return self.section.capacitance(**self.mesh_options)
