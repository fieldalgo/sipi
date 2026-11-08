# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit physical two-port hybrid equations to positive-real power waves."""
import numpy as np
from .network import LineNetwork, _frequencies, _references


__all__ = ['hybrid_network', 'inverse_hybrid_network']


def _hybrid_network(frequency, parameters, *, z_ref, names=None, inverse=False):
    frequency = _frequencies(frequency)
    raw = np.asarray(parameters)
    if (raw.dtype.kind not in 'iufc' or not np.all(np.isfinite(raw))
            or any(isinstance(x, (bool, np.bool_))
                   for x in np.asarray(parameters, dtype=object).flat)):
        raise ValueError('parameters must contain finite numbers, not booleans')
    if raw.shape != (len(frequency), 2, 2):
        raise ValueError('hybrid parameters need exact shape (frequencies,2,2)')
    values = np.array(raw, dtype=complex, copy=True)
    reference = _references(z_ref, 2)
    if isinstance(names, str):
        raise ValueError('names must be a sequence of port names, not a string')
    names = ('port1', 'port2') if names is None else tuple(names)
    if (len(names) != 2 or any(not isinstance(x, str) or not x.strip()
            or '\n' in x or '\r' in x for x in names) or len(set(names)) != 2):
        raise ValueError('names must give two unique nonempty single-line names')
    d1, d2 = np.sqrt(reference)
    normalized = np.empty_like(values)
    with np.errstate(over='ignore', under='ignore', invalid='ignore', divide='ignore'):
        if inverse:
            normalized[:, 0, 0] = (values[:, 0, 0]*d1)*d1
            normalized[:, 1, 1] = (values[:, 1, 1]/d2)/d2
            normalized[:, 0, 1] = (values[:, 0, 1]*d1)/d2
            normalized[:, 1, 0] = (values[:, 1, 0]*d1)/d2
        else:
            normalized[:, 0, 0] = (values[:, 0, 0]/d1)/d1
            normalized[:, 1, 1] = (values[:, 1, 1]*d2)*d2
            normalized[:, 0, 1] = (values[:, 0, 1]*d2)/d1
            normalized[:, 1, 0] = (values[:, 1, 0]*d2)/d1
    if not np.all(np.isfinite(normalized)):
        raise ValueError('hybrid normalization exceeds finite numeric scales')
    scattering = np.empty_like(normalized)
    for index, matrix in enumerate(normalized):
        scale = max(1., float(np.max(abs(matrix.real))), float(np.max(abs(matrix.imag))))
        q = matrix/scale; identity = 1./scale
        if inverse:
            a = np.array([[identity-q[0, 0], -q[0, 1]],
                          [-q[1, 0], identity-q[1, 1]]])
            b = np.array([[-identity-q[0, 0], q[0, 1]],
                          [-q[1, 0], identity+q[1, 1]]])
        else:
            a = np.array([[identity-q[0, 0], -q[0, 1]],
                          [-q[1, 0], identity-q[1, 1]]])
            b = np.array([[identity+q[0, 0], -q[0, 1]],
                          [q[1, 0], -identity-q[1, 1]]])
        try:
            singular = np.linalg.svd(b, compute_uv=False)
            if (not np.all(np.isfinite(singular))
                    or singular[-1] <= 1e-12*max(1., float(singular[0]))):
                raise ValueError('singular or cancellation-sensitive wave conversion (limit=1e-12)')
            s = np.linalg.solve(b, -a)
        except np.linalg.LinAlgError as exc:
            raise ValueError('singular hybrid wave conversion') from exc
        with np.errstate(over='ignore', invalid='ignore'):
            reconstructed = b@s
            error = reconstructed+a
        if not all(np.all(np.isfinite(x)) for x in (s, reconstructed, error)):
            raise ValueError('hybrid wave conversion produced nonfinite results')
        norm = max(float(np.max(abs(reconstructed))), float(np.max(abs(a))),
                   np.finfo(float).tiny)
        if np.max(abs(error))/norm > 1e-10:
            raise ValueError('hybrid wave conversion residual exceeds1e-10')
        scattering[index] = s
    return LineNetwork(frequency, scattering, reference, names)


def hybrid_network(frequency, hybrid, *, z_ref, names=None):
    """Convert explicit physical H samples satisfying[V1,I2]=H[I1,V2].

    Currents enter both ports and phasors use exp(+j omega t). H11 is ohms,
    H22 siemens and H12/H21 dimensionless. Require exact(F,2,2) finite numeric
    samples without booleans, finite nonnegative increasing Hz, explicit
    positive-real scalar/two-port references and two unique port names.
    No constant broadcasting or normalized-file interpretation is inferred.

    Normalize mixed units with positive square-root references, then form
    B*b+A*a=0 for power waves. Scale each frequency by max(1,max(abs(Re(Hn))),
    max(abs(Im(Hn)))) before addition and use a left solve; never invert H or
    divide by one of its entries. Reject nonfinite intermediates/results,
    scaled s_min<=1e-12*max(1,s_max) or normalized residual>1e-10. No repair
    or pseudoinverse is used. Zero H means short port1/open port2.
    Returned LineNetwork arrays are detached/read-only. No passivity,
    reciprocity, causality, physical extraction or file parsing is inferred.
    """
    return _hybrid_network(frequency, hybrid, z_ref=z_ref, names=names, inverse=False)


def inverse_hybrid_network(frequency, inverse_hybrid, *, z_ref, names=None):
    """Convert physical G samples satisfying[I1,V2]=G[V1,I2].

    G11 is siemens, G22 ohms and G12/G21 dimensionless. Shape, frequencies,
    positive-real references, names and numerical gates match hybrid_network.
    Form the G wave equations directly without inverting G or constructing H,
    Z or Y. Singular G can define a valid wave relation; zero G means open
    port1/short port2. Singularity of the wave denominator is still rejected.
    """
    return _hybrid_network(frequency, inverse_hybrid, z_ref=z_ref, names=names, inverse=True)
