# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Local homogeneous circular-aperture electrostatics, exp(+j omega t)."""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
from numbers import Integral

import numpy as np
from galerkin import Mesh
from galerkin.mesh import annulus_mesh

from .document import _keys, _number, _unique_object
from .quasistatic import capacitance_matrix

__all__ = ['CircularAperture', 'ApertureDocument']


@dataclass(frozen=True)
class CircularAperture:
    """Round PEC conductor inside a circular grounded aperture.

    All lengths are metres and both sizes are diameters. The outer circle is
    centred at (0, 0); offsets locate the inner conductor centre. The entire
    dielectric is homogeneous with eps_r*(1-j*tan_delta). This local 2D model
    returns capacitance per length, not total pad capacitance, inductance,
    impedance, a discrete-plane via model or a three-dimensional transition.
    """
    conductor_diameter: float
    aperture_diameter: float
    offset_x: float = 0.
    offset_y: float = 0.
    eps_r: float = 1.
    tan_delta: float = 0.

    def __post_init__(self):
        for name in self.__dataclass_fields__:
            object.__setattr__(self, name, _number(getattr(self, name), name))
        if self.conductor_diameter <= 0 or self.aperture_diameter <= 0:
            raise ValueError('diameters must be positive')
        if self.eps_r <= 0 or self.tan_delta < 0:
            raise ValueError('eps_r must be positive and tan_delta nonnegative')
        if not math.isfinite(self.eps_r*self.tan_delta):
            raise ValueError('complex permittivity must be finite')
        # Normalized lengths avoid squaring extreme dimensional inputs.
        ratio = self.conductor_diameter/self.aperture_diameter
        eccentricity = math.hypot(self.offset_x/self.aperture_diameter,
                                 self.offset_y/self.aperture_diameter)
        if not 0 < ratio < 1 or not eccentricity < (1-ratio)/2:
            raise ValueError('conductor must lie strictly inside the aperture')

    def mesh_settings(self, *, radial_divisions=32, angular_divisions=128):
        options = dict(radial_divisions=radial_divisions, angular_divisions=angular_divisions)
        for name, minimum in [('radial_divisions', 2), ('angular_divisions', 16)]:
            value = options[name]
            if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral) or value < minimum:
                raise ValueError(f'{name} must be an integer >= {minimum}')
            options[name] = int(value)
        # The circular outer boundary is approximated by an inscribed polygon.
        # Require the whole inner disk to fit inside its incircle, for every
        # offset orientation. This conservative guard precedes mesh allocation.
        radius = .5*self.conductor_diameter/self.aperture_diameter
        offset = math.hypot(self.offset_x/self.aperture_diameter,
                            self.offset_y/self.aperture_diameter)
        polygon_radius = .5*math.cos(math.pi/options['angular_divisions'])
        if polygon_radius-radius-offset <= 32*np.finfo(float).eps:
            raise ValueError('angular resolution cannot resolve the clearance; increase angular_divisions')
        return options

    def mesh(self, *, radial_divisions=32, angular_divisions=128):
        """Return a shared Galerkin mesh with inner/outer Dirichlet boundaries.

        Radial and angular refinement are independent controls. Curves are
        polygonized, so refine angular resolution as well as the field mesh.
        The outer conductor is a physical boundary, not a truncated open box.
        """
        options = self.mesh_settings(radial_divisions=radial_divisions,
                                     angular_divisions=angular_divisions)
        nr, nt = options['radial_divisions'], options['angular_divisions']
        radius = .5*self.conductor_diameter/self.aperture_diameter
        base = annulus_mesh(radius, .5, nr, nt)
        t = np.repeat(np.linspace(0., 1., nr+1), nt)
        offset = np.array([self.offset_x, self.offset_y])/self.aperture_diameter
        normalized = base.nodes+(1-t[:, None])*offset
        nodes = normalized*self.aperture_diameter
        if not np.isfinite(nodes).all():
            raise ValueError('mesh coordinates must remain finite')
        # Shared element kernels form dimensional areas: reject scales at
        # which those areas underflow/overflow, even if normalized cells fit.
        triangles = nodes[base.triangles]
        u, v = triangles[:, 1]-triangles[:, 0], triangles[:, 2]-triangles[:, 0]
        with np.errstate(over='ignore', under='ignore', invalid='ignore'):
            areas = .5*(u[:, 0]*v[:, 1]-u[:, 1]*v[:, 0])
        if not np.isfinite(areas).all() or np.any(areas < np.finfo(float).tiny):
            raise ValueError('mesh cell areas must be positive, finite and normally representable')
        return Mesh(nodes, base.triangles, base.boundary, base.boundary_edges)

    def capacitance(self, *, radial_divisions=32, angular_divisions=128):
        """Complex C' [F/m], with negative imaginary part for dielectric loss.

        For a supplied frequency f, G'=2*pi*f*(-Im(C')). Frequency dispersion,
        conductor loss and total finite-height capacitance are not inferred.
        """
        mesh = self.mesh(radial_divisions=radial_divisions, angular_divisions=angular_divisions)
        # A uniform scalar coefficient does not change the harmonic field.
        # Scale the vacuum result after solving to avoid overflowing stiffness
        # entries for otherwise representable capacitances at large eps_r.
        c0 = float(capacitance_matrix(mesh, 1., {'inner': mesh.boundary['inner']},
                                      mesh.boundary['outer'])[0, 0])
        value = complex(c0*self.eps_r, -c0*(self.eps_r*self.tan_delta))
        if not math.isfinite(value.real) or not math.isfinite(value.imag) or value.real <= 0:
            raise ValueError('capacitance must have a positive finite real part and finite loss')
        return value


class ApertureDocument:
    """Strict sipi.circular-aperture/1 input snapshot; outputs are not stored."""
    def __init__(self, section: CircularAperture, *, mesh=None):
        if not isinstance(section, CircularAperture):
            raise TypeError('section must be a CircularAperture')
        self._assign(dict(schema='sipi.circular-aperture/1', length_unit='m',
            geometry={name: getattr(section, name) for name in
                      ('conductor_diameter', 'aperture_diameter', 'offset_x', 'offset_y')},
            dielectric=dict(eps_r=section.eps_r, tan_delta=section.tan_delta),
            mesh={} if mesh is None else mesh))

    def _assign(self, data):
        _keys(data, ('schema', 'length_unit', 'geometry', 'dielectric', 'mesh'), where='aperture')
        if data['schema'] != 'sipi.circular-aperture/1' or data['length_unit'] != 'm':
            raise ValueError('unsupported aperture schema or length unit')
        names = ('conductor_diameter', 'aperture_diameter', 'offset_x', 'offset_y')
        _keys(data['geometry'], names, where='aperture geometry')
        _keys(data['dielectric'], ('eps_r', 'tan_delta'), where='aperture dielectric')
        _keys(data['mesh'], (), ('radial_divisions', 'angular_divisions'), where='aperture mesh')
        section = CircularAperture(**data['geometry'], **data['dielectric'])
        options = section.mesh_settings(**data['mesh'])
        self._data = dict(schema=data['schema'], length_unit='m',
            geometry={name: getattr(section, name) for name in names},
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
        return CircularAperture(**self._data['geometry'], **self._data['dielectric'])

    @property
    def mesh_options(self):
        return dict(self._data['mesh'])

    def analyze(self):
        return self.section.capacitance(**self.mesh_options)
