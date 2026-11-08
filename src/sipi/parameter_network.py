# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit physical Z/Y samples to positive-real-reference power waves."""
import numpy as np

from .network import LineNetwork, _frequencies, _references

__all__ = ['impedance_network', 'admittance_network']


def _parameter_network(frequency, parameters, z_ref, names, *, admittance):
    frequency = _frequencies(frequency)
    raw = np.asarray(parameters)
    if (raw.dtype.kind not in 'iufc' or not np.all(np.isfinite(raw))
            or any(isinstance(x, (bool, np.bool_))
                   for x in np.asarray(parameters, dtype=object).flat)):
        raise ValueError('parameters must contain finite numbers, not booleans')
    if (raw.ndim != 3 or raw.shape[0] != len(frequency)
            or raw.shape[1] == 0 or raw.shape[1] != raw.shape[2]):
        raise ValueError('parameters need exact shape (frequencies,ports,ports)')
    values = np.array(raw, dtype=complex, copy=True)
    n = values.shape[1]
    reference = _references(z_ref, n)
    if isinstance(names, str):
        raise ValueError('names must be a sequence of port names, not a string')
    names = tuple(f'port{i+1}' for i in range(n)) if names is None else tuple(names)
    if (len(names) != n or any(not isinstance(x, str) or not x.strip()
            or '\n' in x or '\r' in x for x in names) or len(set(names)) != n):
        raise ValueError('names must give one unique nonempty single-line name per port')
    root = np.sqrt(reference)
    with np.errstate(over='ignore', under='ignore', invalid='ignore', divide='ignore'):
        if admittance:
            normalized = (root[None, :, None]*values)*root[None, None, :]
        else:
            normalized = (values/root[None, :, None])/root[None, None, :]
    if not np.all(np.isfinite(normalized)):
        raise ValueError('parameter normalization exceeds finite numeric scales')
    eye = np.eye(n)
    scattering = np.empty_like(normalized)
    for index, a in enumerate(normalized):
        # Scale before addition, including huge finite components. No inverse
        # of Z or Y is needed: rank-deficient physical matrices are allowed.
        scale = max(1., float(np.max(abs(a.real))), float(np.max(abs(a.imag))))
        u, v = a/scale, eye/scale
        denominator = u+v
        numerator = v-u if admittance else u-v
        try:
            singular = np.linalg.svd(denominator, compute_uv=False)
            if (not np.all(np.isfinite(singular))
                    or singular[-1] <= 1e-12*max(1., float(singular[0]))):
                raise ValueError('singular or cancellation-sensitive wave conversion (limit=1e-12)')
            # Right solve; transpose is not a complex conjugate transpose.
            s = np.linalg.solve(denominator.T, numerator.T).T
        except np.linalg.LinAlgError as exc:
            raise ValueError('singular wave conversion') from exc
        with np.errstate(over='ignore', invalid='ignore'):
            reconstructed = s @ denominator
            error = reconstructed-numerator
        if not all(np.all(np.isfinite(x)) for x in (s, reconstructed, error)):
            raise ValueError('wave conversion produced nonfinite results')
        norm = max(float(np.max(abs(reconstructed))), float(np.max(abs(numerator))),
                   np.finfo(float).tiny)
        if np.max(abs(error))/norm > 1e-10:
            raise ValueError('wave conversion residual exceeds 1e-10')
        scattering[index] = s
    return LineNetwork(frequency, scattering, reference, names)


def impedance_network(frequency, impedance, *, z_ref, names=None):
    """Convert explicit complex Z[ohm] samples to a single-ended LineNetwork.

    Require exact (F,N,N) samples, finite nonnegative increasing Hz and an
    explicit positive real scalar/per-port reference. Currents point into
    the network; phasors use exp(+j omega t). No constant-matrix broadcasting,
    physical port pairing, passivity, reciprocity or causality is inferred.

    With D=sqrt(diag(z_ref)), A=D^-1 Z D^-1 and S=(A-I)(A+I)^-1.
    Use a scaled right solve, never invert Z. Reject scaled denominator
    singular values <=1e-12*max(1,s_max), nonfinite intermediate/results or
    normalized solve residual >1e-10; no repair or pseudoinverse. Scaling is
    max(1,max(abs(Re(A))),max(abs(Im(A)))) separately at each frequency.
    Zero Z gives exact short ports; singular Z can still have valid S.
    Returned arrays are detached/read-only. Units are physical, not normalized
    Touchstone values; this function parses no file format.
    """
    return _parameter_network(frequency, impedance, z_ref, names, admittance=False)


def admittance_network(frequency, admittance, *, z_ref, names=None):
    """Convert explicit complex Y[siemens] samples to a single-ended LineNetwork.

    The shape, frequency, reference, numerical gates and scope are those of
    impedance_network. With D=sqrt(diag(z_ref)), A=D Y D and
    S=(I-A)(I+A)^-1. No inverse of Y is taken; zero Y gives exact open ports
    and rank-deficient admittance matrices remain admissible when the wave
    denominator is well conditioned. No infinite impedances are fabricated.
    """
    return _parameter_network(frequency, admittance, z_ref, names, admittance=True)
