# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Traveling-wave propagation and dissipated-power attenuation, SI units."""
from dataclasses import dataclass

import numpy as np

from .network import _frequencies, _matrix

__all__ = ['LinePropagation', 'rlgc_propagation']


def _freeze(value):
    out = np.array(value, copy=True)
    out.setflags(write=False)
    return out


@dataclass(frozen=True)
class LinePropagation:
    """Samples shaped (frequency, mode); gamma in 1/m and impedance in ohms.

    Attenuation contributions are Np/m from exact traveling-wave power loss,
    not insertion losses of separate finite-length networks. No material or
    quasi-TEM validity is inferred. Differential/common normalization uses
    Vd=V1-V2, Id=(I1-I2)/2; Vc=(V1+V2)/2, Ic=I1+I2.
    """
    frequency: np.ndarray
    modes: tuple[str, ...]
    gamma: np.ndarray
    z_characteristic: np.ndarray
    alpha_conductor: np.ndarray
    alpha_dielectric: np.ndarray

    def __post_init__(self):
        f = _frequencies(self.frequency)
        modes = tuple(self.modes)
        if np.any(f <= 0) or modes not in (('single',), ('differential','common')):
            raise ValueError('propagation requires positive frequency and supported modes')
        for name in ('gamma','z_characteristic','alpha_conductor','alpha_dielectric'):
            dtype = complex if name in ('gamma','z_characteristic') else float
            raw = np.asarray(getattr(self,name))
            if dtype is float and np.iscomplexobj(raw):
                raise ValueError(f'{name} must be real')
            value = np.asarray(raw,dtype=dtype)
            if value.shape != (len(f),len(modes)) or not np.all(np.isfinite(value)):
                raise ValueError(f'{name} must be finite with shape (frequency,mode)')
            if name.startswith('alpha') and np.any(value < 0):
                raise ValueError('attenuation contributions must be nonnegative')
            object.__setattr__(self,name,_freeze(value))
        if np.any(self.gamma.real < 0) or np.any(self.gamma.imag <= 0):
            raise ValueError('gamma must have nonnegative attenuation and positive phase constant')
        if np.any(self.z_characteristic.real <= 0):
            raise ValueError('characteristic impedance must have positive real part')
        object.__setattr__(self,'frequency',_freeze(f))
        object.__setattr__(self,'modes',modes)

    @property
    def alpha(self):
        """Amplitude attenuation in Np/m (real gamma)."""
        return _freeze(self.gamma.real)

    @property
    def beta(self):
        """Phase constant in rad/m for exp(+j omega t)."""
        return _freeze(self.gamma.imag)

    @property
    def attenuation_db_per_m(self):
        return _freeze(20/np.log(10)*self.alpha)

    @property
    def conductor_db_per_m(self):
        return _freeze(20/np.log(10)*self.alpha_conductor)

    @property
    def dielectric_db_per_m(self):
        return _freeze(20/np.log(10)*self.alpha_dielectric)

    @property
    def phase_velocity(self):
        """omega/beta in m/s; not group or information velocity."""
        return _freeze(2*np.pi*self.frequency[:,None]/self.beta)


def rlgc_propagation(frequency, *, R, L, G, C):
    """Single or exchange-symmetric paired line propagation from passive RLGC.

    Inputs follow rlgc_network's real symmetric PSD R/G and PD L/C contract.
    Frequencies must be strictly positive. Pair diagonal equality is required
    to 1e-12 relative matrix scale at every frequency for every matrix; general
    asymmetric/coupled modes and implicit approximate symmetrization are absent.

    z=R+j*omega*L, y=G+j*omega*C, gamma=sqrt(z*y), Zc=sqrt(z/y).
    Exact power balance partitions alpha as R/(2*Re Zc) and
    G*abs(Zc)**2/(2*Re Zc). They sum to Re gamma, including high loss, and are
    not separate conductor-only/dielectric-only S21 calculations. This does
    not fit a material, infer valid RLGC or recover DC traveling-wave limits.
    """
    f = _frequencies(frequency)
    if np.any(f <= 0):
        raise ValueError('propagation requires strictly positive frequency; DC is excluded')
    l = _matrix('L',L,len(f))
    n = l.shape[1]
    if n not in (1,2):
        raise ValueError('propagation supports one conductor or an exchange-symmetric pair')
    r,g,c = (_matrix(name,value,len(f),n) for name,value in (('R',R),('G',G),('C',C)))
    modal = []
    for name,matrix in zip(('R','L','G','C'),(r,l,g,c)):
        if n == 1:
            modal.append(matrix[:,0,:])
            continue
        scale = np.max(abs(matrix),axis=(1,2))
        if np.any(abs(matrix[:,0,0]-matrix[:,1,1]) > 1e-12*scale):
            raise ValueError(f'{name} must be exchange-symmetric; no approximate mode projection')
        diagonal = (matrix[:,0,0]+matrix[:,1,1])/2
        odd,even = diagonal-matrix[:,0,1],diagonal+matrix[:,0,1]
        factors = (2,.5) if name in ('R','L') else (.5,2)
        modal.append(np.stack((factors[0]*odd,factors[1]*even),axis=1))
    r,l,g,c = modal
    omega = 2*np.pi*f[:,None]
    with np.errstate(over='ignore',invalid='ignore',divide='ignore'):
        z,y = r+1j*omega*l,g+1j*omega*c
        # One complex square root preserves exactly zero loss in z*y.
        # Multiplying separate roots can introduce signed cancellation noise.
        gamma,zchar = np.sqrt(z*y),np.sqrt(z/y)
        conductor = r/(2*zchar.real)
        dielectric = g*abs(zchar)**2/(2*zchar.real)
    return LinePropagation(f,('single',) if n==1 else ('differential','common'),
                           gamma,zchar,conductor,dielectric)
