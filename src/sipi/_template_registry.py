# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Internal section factories shared by documents and impedance studies.

Keep this explicit catalog independent of study execution and product dispatch.
Order and factory identity are retained for existing consumers; this is not a
plugin registry or a declaration of qualified UI/host capabilities.
"""
from functools import wraps

from . import templates


def _pinned_v1(factory):
    """Build with the v1 default boxes, whatever box rule the caller has set.

    Every saved document that rebuilds a template from this catalog (template
    section /1, design and study documents) recorded v1 geometry, so it keeps
    v1 boxes; the rule is set on each call, also in new threads and processes.
    """
    @wraps(factory)
    def pinned(*args, **kwargs):
        with templates.box_rule('v1'):
            return factory(*args, **kwargs)
    return pinned


def _pinned_v2(factory):
    """Build with the v2 default boxes (template section /2)."""
    @wraps(factory)
    def pinned(*args, **kwargs):
        with templates.box_rule('v2'):
            return factory(*args, **kwargs)
    return pinned


_TEMPLATES = {name: _pinned_v1(getattr(templates, name)) for name in
              ('layered_conformal_coated_grounded_coplanar', 'coupled_layered_conformal_coated_grounded_coplanar', 'asymmetric_coupled_layered_conformal_coated_grounded_coplanar', 'layered_conformal_coated_unbacked_coplanar', 'coupled_layered_conformal_coated_unbacked_coplanar', 'asymmetric_coupled_layered_conformal_coated_unbacked_coplanar',
               'layered_conformal_coated_microstrip', 'coupled_layered_conformal_coated_microstrip', 'asymmetric_coupled_layered_conformal_coated_microstrip',
               'layered_coated_grounded_coplanar', 'coupled_layered_coated_grounded_coplanar', 'asymmetric_coupled_layered_coated_grounded_coplanar', 'layered_coated_unbacked_coplanar', 'coupled_layered_coated_unbacked_coplanar', 'asymmetric_coupled_layered_coated_unbacked_coplanar',
               'layered_coated_microstrip', 'coupled_layered_coated_microstrip', 'asymmetric_coupled_layered_coated_microstrip',
               'layered_unbacked_coplanar', 'coupled_layered_unbacked_coplanar', 'asymmetric_coupled_layered_unbacked_coplanar',
               'layered_grounded_coplanar', 'coupled_layered_grounded_coplanar', 'asymmetric_coupled_layered_grounded_coplanar',
               'microstrip', 'stripline', 'coupled_microstrip', 'asymmetric_coupled_microstrip', 'grounded_coplanar',
               'layered_microstrip', 'coupled_layered_microstrip', 'asymmetric_coupled_layered_microstrip',
               'asymmetric_coupled_stripline',
               'asymmetric_coupled_layered_stripline',
               'asymmetric_coupled_layered_coplanar_stripline',
               'asymmetric_coupled_grounded_coplanar',
               'asymmetric_coupled_unbacked_coplanar',
               'asymmetric_coupled_coated_grounded_coplanar',
               'asymmetric_coupled_coated_unbacked_coplanar',
               'asymmetric_coupled_coated_microstrip',
               'asymmetric_coupled_conformal_coated_microstrip',
               'asymmetric_coupled_conformal_coated_grounded_coplanar',
               'asymmetric_coupled_conformal_coated_unbacked_coplanar',
               'asymmetric_coupled_coplanar_stripline',
               'coated_microstrip', 'offset_stripline', 'coupled_stripline', 'broadside_stripline',
               'coupled_grounded_coplanar', 'layered_stripline', 'coupled_layered_stripline',
               'layered_broadside_stripline', 'asymmetric_layered_broadside_stripline', 'tapered_layered_broadside_stripline', 'split_gap_broadside_stripline',
               'coplanar_stripline', 'coupled_coplanar_stripline',
               'layered_coplanar_stripline', 'coupled_layered_coplanar_stripline',
               'coupled_coated_microstrip', 'coated_grounded_coplanar',
               'coupled_coated_grounded_coplanar', 'unbacked_coplanar',
               'coupled_unbacked_coplanar', 'coated_unbacked_coplanar',
               'coupled_coated_unbacked_coplanar', 'conformal_coated_microstrip',
               'coupled_conformal_coated_microstrip', 'conformal_coated_grounded_coplanar',
               'coupled_conformal_coated_grounded_coplanar', 'conformal_coated_unbacked_coplanar',
               'coupled_conformal_coated_unbacked_coplanar')}

# The same catalog with the v2 default boxes, for documents that record them.
_TEMPLATES_V2 = {name: _pinned_v2(getattr(templates, name)) for name in _TEMPLATES}
