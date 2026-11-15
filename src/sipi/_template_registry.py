# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Internal section factories shared by documents and impedance studies.

Keep this explicit catalog independent of study execution and product dispatch.
Order and factory identity are retained for existing consumers; this is not a
plugin registry or a declaration of qualified UI/host capabilities.
"""
from . import templates

_TEMPLATES = {name: getattr(templates, name) for name in
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
