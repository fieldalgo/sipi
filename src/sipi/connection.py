# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit near/far network composition and removal of known fixtures."""
from __future__ import annotations

import numpy as np

from .network import LineNetwork, _cascade

__all__ = ['cascade_networks', 'deembed_network']


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
