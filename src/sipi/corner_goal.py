# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit corner-controlled bounded impedance design."""
from .design import _positive, _seek_impedance
from .document import CrossSectionDocument
from .corner_document import CornerCrossSectionDocument

__all__ = ['seek_corner_impedance']


def _snapshot(section, *, mesh):
    options = dict(mesh)
    corner = options.pop('corner_size')
    return CornerCrossSectionDocument(CrossSectionDocument(section, mesh=options), corner)


def seek_corner_impedance(factory, bounds, target, *, corner_size, quantity='z0',
                          tolerance=.1, mesh=None, max_evaluations=40,
                          frequency=None, materials=None, material_factory=None,
                          return_line=False, search_tolerance=None):
    """Use the bounded impedance search with an explicit corner snapshot.

    All original goal, material, budget and return-line contracts apply.
    The selected geometry and material are frozen for a final solve with
    corner_size, edge_size, far_size and grade each halved. The requested and
    refined impedances must both meet the target tolerance. This finite check
    does not certify absolute accuracy or any arbitrary factory's convergence.

    Pass corner_size separately in metres, not inside mesh. It must be finite,
    positive and no larger than the resolved edge_size at each evaluation.
    The result and a typed mesh-limit failure retain the corner snapshot.
    """
    corner = _positive('corner_size', corner_size)
    options = {} if mesh is None else dict(mesh)
    if 'corner_size' in options:
        raise ValueError('supply corner_size separately, not inside mesh')
    options['corner_size'] = corner
    return _seek_impedance(factory, bounds, target, quantity=quantity, tolerance=tolerance,
        mesh=options, max_evaluations=max_evaluations, frequency=frequency, materials=materials,
        material_factory=material_factory, return_line=return_line, search_tolerance=search_tolerance,
        document_factory=_snapshot, refinement_keys=('edge_size','far_size','grade','corner_size'))
