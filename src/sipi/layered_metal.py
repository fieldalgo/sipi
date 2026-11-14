# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Planar, perfectly contacted conductive layers on a bulk MQS half-space."""
from dataclasses import dataclass

import numpy as np

from .conductor import _metal_samples, _readonly
from .network import _frequencies, _scalar

__all__ = ['MetalLayer', 'LayeredSurfaceImpedance', 'layered_surface_impedance']


@dataclass(frozen=True)
class MetalLayer:
    """A uniform isotropic layer: thickness [m], sigma [S/m], real relative mu.

    Zero thickness is an explicit removable layer. No magnetic dispersion,
    hysteresis, surface roughness or interfacial contact resistance is inferred.
    """
    thickness_m: float
    conductivity: float
    relative_permeability: float = 1.

    def __post_init__(self):
        for key in ('thickness_m', 'conductivity', 'relative_permeability'):
            object.__setattr__(self, key, _scalar(key, getattr(self, key), zero=key == 'thickness_m'))


@dataclass(frozen=True)
class LayeredSurfaceImpedance:
    """E/H at the outer finished surface, exp(+j omega t), ohm/square.

    Layers and skin-depth columns run from outside inward, followed by the
    half-space base. These are material penetration scales, not a certificate
    of curvature, finite-conductor thickness or a 2D line approximation.
    """
    frequency: np.ndarray
    impedance: np.ndarray
    skin_depth: np.ndarray
    layers: tuple[MetalLayer, ...]
    conductivity: float
    relative_permeability: float

    def __post_init__(self):
        f = _frequencies(self.frequency)
        layers = tuple(self.layers)
        if not 1 <= len(f) <= 1024 or f[0] <= 0 or len(layers) > 32:
            raise ValueError('layered surface needs 1..1024 positive frequencies and at most 32 layers')
        if not all(isinstance(layer, MetalLayer) for layer in layers):
            raise TypeError('layers must contain MetalLayer objects from outside inward')
        z = _readonly(self.impedance, dtype=complex)
        depth = _readonly(self.skin_depth)
        if z.shape != f.shape or np.any(z.real <= 0) or np.any(z.imag <= 0):
            raise ValueError('layered impedance must have matching finite positive real and imaginary parts')
        if depth.shape != (len(f), len(layers)+1) or np.any(depth <= 0):
            raise ValueError('skin depths must match frequency and layers followed by base')
        object.__setattr__(self, 'frequency', _readonly(f))
        object.__setattr__(self, 'layers', layers)
        object.__setattr__(self, 'impedance', z)
        object.__setattr__(self, 'skin_depth', depth)
        for key in ('conductivity', 'relative_permeability'):
            object.__setattr__(self, key, _scalar(key, getattr(self, key)))


def layered_surface_impedance(frequency, *, conductivity, relative_permeability=1., layers=()):
    """Planar MQS surface impedance of 0..32 finite layers on a bulk half-space.

    Every material obeys the existing sigma/(omega*eps0)>=1000 gate. Layers
    are ordered outside inward, have perfect electrical contact, and use
    frequency-independent positive real sigma/mu. Recursion at each layer is
    eta*(Zback+eta*tanh(k*d))/(eta+Zback*tanh(k*d)), k=(1+j)/delta.

    No exterior-air field is included: the reference plane is the outer metal
    surface. This standalone local law does not mesh coatings or automatically
    attach a half-space approximation to finite/cornered 2D conductors.
    """
    f = _frequencies(frequency)
    if not 1 <= len(f) <= 1024 or f[0] <= 0:
        raise ValueError('layered surface needs 1..1024 positive frequency samples')
    try:
        layers = tuple(layers)
    except TypeError as exc:
        raise TypeError('layers must contain MetalLayer objects') from exc
    if len(layers) > 32 or not all(isinstance(layer, MetalLayer) for layer in layers):
        raise ValueError('layers must contain at most 32 MetalLayer objects from outside inward')
    base = _metal_samples(f, conductivity, relative_permeability, 0.)
    samples = [_metal_samples(f, layer.conductivity, layer.relative_permeability, 0.) for layer in layers]
    z = base[3].copy()
    for layer, sample in reversed(list(zip(layers, samples))):
        if layer.thickness_m == 0:
            continue
        delta, eta = sample[1], sample[3]
        log_ratio = np.log(layer.thickness_m)-np.log(delta)
        # tanh approaches one before exp(-2*d/delta) underflows. Avoid forming
        # an overflowing d/delta or a meaningless infinite imaginary phase.
        t = np.ones(len(f), dtype=complex)
        resolved = log_ratio < np.log(350.)
        ratio = np.exp(log_ratio[resolved])
        if np.any(ratio <= 0):
            raise ValueError('nonzero layer thickness/skin depth cannot be represented')
        t[resolved] = np.tanh((1+1j)*ratio)
        scale = np.maximum(abs(eta), abs(z))
        es, zs = eta/scale, z/scale
        with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
            z = eta*((zs+es*t)/(es+zs*t))
        if not np.all(np.isfinite(z)) or np.any(z.real <= 0) or np.any(z.imag <= 0):
            raise ValueError('layered surface impedance cannot be represented as passive MQS samples')
    depth = np.column_stack([sample[1] for sample in samples]+[base[1]])
    return LayeredSurfaceImpedance(f, z, depth, layers, conductivity, relative_permeability)
