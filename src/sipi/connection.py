# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit port wiring, ideal nodes, near/far composition and known fixtures."""
from __future__ import annotations

import numpy as np

from .network import LineNetwork, _cascade, _frequencies, _references

__all__ = ['cascade_networks', 'deembed_network', 'connect_networks', 'ideal_junction']


def ideal_junction(frequency, *, port_names, z_ref=50.0):
    """Zero-length common-voltage node with two or more single-ended ports.

    All ports share one electrical reference ground. Currents sum to zero;
    positive real reference impedances may differ. No parasitic inductance,
    capacitance, delay or physical junction geometry is inferred.
    """
    if not isinstance(port_names, (tuple, list)) or len(port_names) < 2:
        raise ValueError('port_names must list at least two junction ports')
    f = _frequencies(frequency)
    z = _references(z_ref, len(port_names))
    # Scale before normalization: 1/z can overflow for finite tiny references.
    u = np.sqrt(z.min())/np.sqrt(z)
    u /= np.linalg.norm(u)
    s = 2*np.outer(u, u)-np.eye(len(u))
    return LineNetwork(f, np.broadcast_to(s, (len(f), *s.shape)), z, tuple(port_names))


def _connection_layout(left_ports, left_refs, right_ports, right_refs, connections, port_names):
    """Validate named wiring without constructing S or extracting geometry."""
    if not isinstance(connections, (list, tuple)) or not connections:
        raise ValueError('connections must list at least one pair of port names')
    na, nb = len(left_ports), len(right_ports)
    internal = []
    for pair in connections:
        if (not isinstance(pair, (list, tuple)) or len(pair) != 2
                or any(not isinstance(p, str) for p in pair)
                or pair[0] not in left_ports or pair[1] not in right_ports):
            raise ValueError('each connection needs a known left and right port name')
        a, b = left_ports.index(pair[0]), right_ports.index(pair[1])
        if a in internal or na+b in internal:
            raise ValueError('a port cannot participate in more than one connection')
        _references_match(left_refs[a], right_refs[b])
        internal.extend((a, na+b))
    external = [i for i in range(na+nb) if i not in internal]
    if not external:
        raise ValueError('at least one external port must remain')
    names = left_ports+right_ports
    try:
        names = tuple(names[i] for i in external) if port_names is None else tuple(port_names)
    except TypeError as exc:
        raise ValueError('port_names must contain one name per external port') from exc
    if (len(names) != len(external) or any(not isinstance(p, str) or not p.strip()
            or '\n' in p or '\r' in p for p in names) or len(set(names)) != len(names)):
        raise ValueError('port_names must contain one unique single-line name per external port')
    return internal, external, names, np.r_[left_refs, right_refs][external]


def connect_networks(left, right, connections, *, port_names=None):
    """Join explicit (left port, right port) pairs in two single-ended networks.

    Frequencies and references at connected ports must match exactly. Each
    port may occur once; at least one connection and one external port remain.
    Output order is retained left ports, then retained right ports. Supply
    unique port_names if those names collide. No implicit renormalization,
    interpolation, same-network wiring or physical interconnect model.

    Connected outgoing waves become the partner's incident waves. Reject a
    feedback condition number above 1e12, normalized residual above 1e-10,
    singular loops and nonfinite results, without regularization.
    """
    for label, network in (('left', left), ('right', right)):
        if not isinstance(network, LineNetwork):
            raise TypeError(f'{label} must be a LineNetwork')
        if network.basis != 'single-ended':
            raise ValueError('connections require single-ended networks')
    if not np.array_equal(left.frequency, right.frequency):
        raise ValueError('networks must have identical frequency samples')
    na, nb = len(left.port_names), len(right.port_names)
    internal, external, names, references = _connection_layout(
        left.port_names, left.z_ref, right.port_names, right.z_ref, connections, port_names)
    swap = np.arange(len(internal)).reshape(-1, 2)[:, ::-1].ravel()
    result = []
    for a, b in zip(left.s, right.s):
        s = np.zeros((na+nb, na+nb), dtype=complex)
        s[:na, :na], s[na:, na:] = a, b
        ii, ie = s[np.ix_(internal, internal)], s[np.ix_(internal, external)]
        ei, ee = s[np.ix_(external, internal)], s[np.ix_(external, external)]
        system, drive = np.eye(len(internal))-ii[swap], ie[swap]
        _checked(system, 'named connection feedback')
        try:
            incident = np.linalg.solve(system, drive)
        except np.linalg.LinAlgError as exc:
            raise ValueError('named connection feedback is singular') from exc
        with np.errstate(over='ignore', invalid='ignore'):
            reconstructed = system @ incident
            error = reconstructed-drive
            reduced = ee+ei @ incident
        if not all(np.all(np.isfinite(x)) for x in (incident, reconstructed, error, reduced)):
            raise ValueError('nonfinite connected network')
        scale = max(*(np.max(abs(part)) for part in
                      (reconstructed.real, reconstructed.imag, drive.real, drive.imag)),
                    np.finfo(float).tiny)
        if np.max(abs(error/scale)) > 1e-10:
            raise ValueError('named connection feedback residual exceeds 1e-10')
        result.append(reduced)
    return LineNetwork(left.frequency, result, references, names)


def _network(value, label):
    if not isinstance(value, LineNetwork):
        raise TypeError(f'{label} must be a LineNetwork')
    if value.basis != 'single-ended' or len(value.port_names) % 2:
        raise ValueError(f'{label} requires single-ended 2N ports ordered near then far')
    return len(value.port_names)//2


def _compatible(a, b):
    if len(a.port_names) != len(b.port_names):
        raise ValueError('networks must have the same port count')
    if not np.array_equal(a.frequency, b.frequency):
        raise ValueError('networks must have identical frequency samples')


def _references_match(a, b):
    if not np.array_equal(a, b):
        raise ValueError('port references must match; renormalize explicitly first')


def _checked(matrix, label):
    """Conservative numerical guard, not an uncertainty/error certificate."""
    if not np.all(np.isfinite(matrix)):
        raise ValueError(f'{label} contains nonfinite values')
    try:
        condition = np.linalg.cond(matrix)
    except np.linalg.LinAlgError as exc:
        raise ValueError(f'{label} conditioning could not be evaluated') from exc
    if not np.isfinite(condition) or condition > 1e12:
        raise ValueError(f'{label} is singular or ill-conditioned (limit 1e12)')
    return matrix


def _chain(s):
    # [a_near; b_near] = T [b_far; a_far]. Do not invert S itself:
    # a removable series resistance of twice the reference has singular S.
    n = len(s)//2
    s11, s12, s21, s22 = s[:n,:n], s[:n,n:], s[n:,:n], s[n:,n:]
    x = np.linalg.solve(_checked(s21, 'forward transmission'),
                        np.hstack((np.eye(n), -s22)))
    t11, t12 = x[:,:n], x[:,n:]
    return _checked(np.block([[t11,t12],[s11@t11,s12+s11@t12]]), 'wave-chain matrix')


def _scattering(t):
    n = len(t)//2
    t11, t12, t21, t22 = t[:n,:n], t[:n,n:], t[n:,:n], t[n:,n:]
    x = np.linalg.solve(_checked(t11, 'recovered incident block'),
                        np.hstack((np.eye(n), -t12)))
    s21, s22 = x[:,:n], x[:,n:]
    return np.block([[t21@s21,t22+t21@s22],[s21,s22]])


def cascade_networks(left, right, *, port_names=None):
    """Connect left's far ports to right's near ports, in conductor order.

    Both single-ended 2N-port inputs must use all-near then all-far order,
    identical frequency samples and matching references at connected ports.
    No interpolation, renormalization or port-name matching is implicit.
    Output names default to left near + right far; supply unique port_names
    if those names collide. Singular feedback is rejected, not regularized.
    """
    n = _network(left, 'left')
    _network(right, 'right')
    _compatible(left, right)
    _references_match(left.z_ref[n:], right.z_ref[:n])
    names = left.port_names[:n]+right.port_names[n:] if port_names is None else port_names
    result = []
    try:
        with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
            for a, b in zip(left.s, right.s):
                feedback = np.eye(n)-b[:n,:n]@a[n:,n:]
                _checked(feedback, 'connection feedback')
                result.append(_cascade(a, b))
    except np.linalg.LinAlgError as exc:
        raise ValueError('connection feedback is singular') from exc
    return LineNetwork(left.frequency, result,
                       np.r_[left.z_ref[:n],right.z_ref[n:]], names)


def deembed_network(measured, *, left=None, right=None, port_names=None):
    """Remove supplied known fixtures from left -> DUT -> right samples.

    All inputs use single-ended all-near/all-far ordering. Fixture outer
    references and frequency samples must exactly match measured. Output
    references/names come from the fixtures' inner ports (or measured ends).
    At least one fixture is required. No fixture estimation, calibration,
    interpolation, passivity correction or noise recovery is performed.

    Forward transmission and wave-chain systems must be nonsingular with
    2-norm condition <= 1e12. This numerical guard is not an accuracy bound;
    attenuation and measurement uncertainty can make a result unusable even
    below the limit. Deeply attenuated/singular networks are rejected.
    """
    n = _network(measured, 'measured')
    if left is None and right is None:
        raise ValueError('at least one known fixture is required')
    for label, fixture in (('left',left),('right',right)):
        if fixture is not None:
            _network(fixture, label)
            _compatible(measured, fixture)
    if left is not None:
        _references_match(measured.z_ref[:n], left.z_ref[:n])
    if right is not None:
        _references_match(measured.z_ref[n:], right.z_ref[n:])
    near_z = measured.z_ref[:n] if left is None else left.z_ref[n:]
    far_z = measured.z_ref[n:] if right is None else right.z_ref[:n]
    near_names = measured.port_names[:n] if left is None else left.port_names[n:]
    far_names = measured.port_names[n:] if right is None else right.port_names[:n]
    names = near_names+far_names if port_names is None else port_names
    result = []
    try:
        with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
            for i, s in enumerate(measured.s):
                t = _chain(s)
                if left is not None:
                    t = np.linalg.solve(_chain(left.s[i]), t)
                if right is not None:
                    t = np.linalg.solve(_chain(right.s[i]).T, t.T).T
                result.append(_scattering(_checked(t, 'recovered wave-chain matrix')))
    except np.linalg.LinAlgError as exc:
        raise ValueError('fixture removal is singular') from exc
    return LineNetwork(measured.frequency, result, np.r_[near_z,far_z], names)
