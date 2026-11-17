# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Ordered scalar or launched-pair quantities with explicit two-ground fields."""
from dataclasses import dataclass

from ._two_ground_mesh_reuse import _mesh_reuse_scope
from ._two_ground_current_reuse import _current_reuse_scope

from ._validation import _json_copy, _keys
from .two_ground_line_study import TwoGroundLineQuantityStudyDocument as _WholeStudy
from .study import ImpedanceStudyDocument
from .fem_shape_study import (FEMShapeLineQuantityStudy, FEMShapeLineQuantityStudyRow,
                              _analyze_fem_shape_study, _QUANTITIES, _PAIR)
from ._two_ground_linear_corner_face_input import _source_inputs, _line_from_inputs
from .two_ground_linear_corner_face_panel_line import TwoGroundLinearCornerFacePanelLineError

__all__ = ['TwoGroundLinearCornerFaceLineQuantityStudyDocument', 'TwoGroundLinearCornerFaceLineQuantityStudy',
           'TwoGroundLinearCornerFaceLineQuantityStudyRow']
_SCHEMA = 'sipi.two-ground-linear-corner-face-line-quantity-study/1'


@dataclass(frozen=True)
class TwoGroundLinearCornerFaceLineQuantityStudyRow(FEMShapeLineQuantityStudyRow):
    def to_dict(self):
        out = super().to_dict()
        out['dielectric_mesh'] = None if self.result is None else self.result.mesh_record()
        return out


@dataclass(frozen=True)
class TwoGroundLinearCornerFaceLineQuantityStudy(FEMShapeLineQuantityStudy):
    def to_dict(self):
        out = super().to_dict()
        out['scope'] = 'stated-two-ground-linear-corner-face-line-quantity-samples-descriptive-not-yield'
        return out


class TwoGroundLinearCornerFaceLineQuantityStudyDocument(_WholeStudy):
    """Sample one full-complex lossy quantity with fixed physical-face metal laws.

    Scalar z0 sources select impedance_real or attenuation. Paired
    z_diff_forward sources select differential_forward_impedance_real or
    common_forward_impedance_real. All ordered geometry/material samples and
    failed rows remain intact; summaries require every row to succeed.
    """
    def __init__(self, study, *, quantity, conductors, reference, ground_thickness,
                 panels_per_edge=32, ground_modes=256, interpolation_degree=24):
        if isinstance(study, ImpedanceStudyDocument): study = study.to_dict()
        self._data = self._validate(dict(schema=_SCHEMA, study=study, quantity=quantity,
            conductors=conductors, reference=reference, ground_thickness_m=ground_thickness,
            panel=dict(panels_per_edge=panels_per_edge, ground_modes=ground_modes,
                       interpolation_degree=interpolation_degree)))

    @staticmethod
    def _validate(data):
        data = _json_copy(data)
        _keys(data, ('schema','study','quantity','conductors','reference','ground_thickness_m','panel'),
              where='two-ground-linear-corner-face line quantity study')
        if data['schema'] != _SCHEMA: raise ValueError('unsupported two-ground-linear-corner-face-line-quantity-study schema')
        if not isinstance(data['quantity'],str) or data['quantity'] not in _QUANTITIES:
            raise ValueError('unsupported two-ground-linear-corner-face line quantity')
        source = _source_inputs(data, paired=data['quantity'] in _PAIR)
        return dict(schema=_SCHEMA, quantity=data['quantity'], **source)

    def analyze(self, *, max_evaluations=128):
        with _mesh_reuse_scope(), _current_reuse_scope():
            return _analyze_fem_shape_study(self, max_evaluations=max_evaluations,
                line_factory=lambda study,parameters,evaluation,data:_line_from_inputs(data,parameters,evaluation),
                row_type=TwoGroundLinearCornerFaceLineQuantityStudyRow, result_type=TwoGroundLinearCornerFaceLineQuantityStudy,
                cause_class=TwoGroundLinearCornerFacePanelLineError)
