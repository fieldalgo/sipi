# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Passive two-port series R-L-C branches, exp(+j omega t), SI units."""
from __future__ import annotations

import json
import numpy as np

from .document import _keys, _unique_object
from .network import LineNetwork, _frequencies, _references, _scalar

__all__ = ['lumped_network', 'LumpedNetworkDocument']


def _parameters(frequency, resistance, inductance, capacitance, placement, z_ref, port_names):
    f = _frequencies(frequency)
    r = _scalar('resistance', resistance, zero=True)
    l = _scalar('inductance', inductance, zero=True)
    c = None if capacitance is None else _scalar('capacitance', capacitance)
    if not isinstance(placement, str) or placement not in ('series', 'shunt'):
        raise ValueError('placement must be series or shunt')
    if isinstance(port_names, str):
        raise ValueError('port_names must contain two explicit names')
    try:
        names = tuple(port_names)
    except TypeError as exc:
        raise ValueError('port_names must contain two explicit names') from exc
    if (len(names) != 2 or any(not isinstance(p, str) or not p.strip() or '\n' in p or '\r' in p
                               for p in names) or len(set(names)) != 2):
        raise ValueError('port_names must contain two unique nonempty single-line strings')
    return f, r, l, c, placement, _references(z_ref, 2), names


def _reactance(f, value, *, capacitive=False):
    # Split exponents to avoid overflowing/underflowing an intermediate f*value.
    fm, fe = np.frexp(f)
    vm, ve = np.frexp(value)
    with np.errstate(over='ignore', under='ignore', divide='ignore', invalid='ignore'):
        product = (2*np.pi)*fm*vm
        result = np.ldexp(1/product, -fe-ve) if capacitive else np.ldexp(product, fe+ve)
    if np.any(~np.isfinite(result)) or np.any(result < np.finfo(float).tiny):
        raise ValueError('positive-frequency reactance must be representable as a normal finite float')
    return result


def lumped_network(frequency, *, resistance=0., inductance=0., capacitance=None,
                   placement='series', z_ref=50., port_names=('near', 'far')):
    """A series R-L-C branch placed inline or from a through node to ground.

    R [ohm] and L [H] are constant finite nonnegative scalars; C [F] is positive
    or None (omitted). Frequencies [Hz] are increasing, nonnegative samples.
    Port references are positive real constants. DC with a capacitor is an
    exact open branch, without one Z=R. Subnormal/nonfinite positive-frequency
    reactances are rejected; pure resistance supports subnormal values.
    This is an ideal lumped circuit, not a geometric or distributed extraction.
    """
    f, r, l, c, placement, refs, names = _parameters(
        frequency, resistance, inductance, capacitance, placement, z_ref, port_names)
    positive = f > 0
    x = np.zeros(len(f))
    if l:
        x[positive] = _reactance(f[positive], l)
    if c is not None:
        x[positive] -= _reactance(f[positive], c, capacitive=True)
    r1, r2 = refs
    rmax, rmin = max(refs), min(refs)
    a, b = refs/rmax
    rho = (b-a)/(a+b)
    tau = 2*(np.sqrt(r1)/np.sqrt(rmax))*(np.sqrt(r2)/np.sqrt(rmax))/(a+b)
    through = np.array([[rho, tau], [tau, -rho]])
    reference = rmax if placement == 'series' else rmin
    scale = np.maximum(np.maximum(reference, r), abs(x))
    # Divide real components separately: complex division by subnormal scales
    # can overflow internally even when the quotient is representable.
    zn = r/scale + 1j*(x/scale)
    rn = r1/scale+r2/scale if placement == 'series' else (rmin/scale)/(1+rmin/rmax)
    denominator = zn+rn
    if placement == 'series':
        s = (rn/denominator)[:, None, None]*through + (zn/denominator)[:, None, None]*np.eye(2)
    else:
        s = (zn/denominator)[:, None, None]*through - (rn/denominator)[:, None, None]*np.eye(2)
    if c is not None:
        s[~positive] = np.eye(2) if placement == 'series' else through
    return LineNetwork(f, s, refs, names)


class LumpedNetworkDocument:
    """Strict sipi.lumped-network/1 snapshot; no I/O, expressions or meshing."""
    def __init__(self, frequency, *, resistance=0., inductance=0., capacitance=None,
                 placement='series', z_ref=50., port_names=('near', 'far')):
        self._assign(dict(schema='sipi.lumped-network/1', frequency_hz=frequency,
            branch=dict(resistance_ohms=resistance, inductance_h=inductance, capacitance_f=capacitance),
            placement=placement, reference_ohms=z_ref, port_names=port_names))

    def _assign(self, data):
        _keys(data, ('schema', 'frequency_hz', 'branch', 'placement', 'reference_ohms', 'port_names'),
              where='lumped network')
        if data['schema'] != 'sipi.lumped-network/1':
            raise ValueError('unsupported lumped-network schema')
        branch = data['branch']
        _keys(branch, ('resistance_ohms', 'inductance_h', 'capacitance_f'), where='RLC branch')
        f, r, l, c, placement, refs, names = _parameters(data['frequency_hz'],
            branch['resistance_ohms'], branch['inductance_h'], branch['capacitance_f'],
            data['placement'], data['reference_ohms'], data['port_names'])
        # Algebraic validation is cheap and ensures invalid numeric scales fail
        # before an enclosing geometry-backed assembly can create a mesh.
        lumped_network(f, resistance=r, inductance=l, capacitance=c, placement=placement,
                       z_ref=refs, port_names=names)
        self._data = dict(schema=data['schema'], frequency_hz=f.tolist(),
            branch=dict(resistance_ohms=r, inductance_h=l, capacitance_f=c),
            placement=placement, reference_ohms=refs.tolist(), port_names=list(names))

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

    def analyze(self):
        data = self._data
        branch = data['branch']
        return lumped_network(data['frequency_hz'], resistance=branch['resistance_ohms'],
            inductance=branch['inductance_h'], capacitance=branch['capacitance_f'],
            placement=data['placement'], z_ref=data['reference_ohms'], port_names=data['port_names'])
