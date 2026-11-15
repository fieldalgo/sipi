# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Ordered scalar or launched-pair quantities with explicit two-ground fields."""
from dataclasses import dataclass
import json

from ._two_ground_current_reuse import _current_reuse_scope
from ._two_ground_mesh_reuse import _mesh_reuse_scope

from ._validation import _json_copy, _keys, _unique_object
from .study import ImpedanceStudyDocument
from .fem_shape_study import (FEMShapeLineQuantityStudy, FEMShapeLineQuantityStudyRow,
                              _analyze_fem_shape_study, _QUANTITIES, _PAIR)
from .two_ground_input import _source_inputs, _line_from_inputs
from .two_ground_panel_line import TwoGroundPanelLineError

__all__ = ['TwoGroundLineQuantityStudyDocument', 'TwoGroundLineQuantityStudy',
           'TwoGroundLineQuantityStudyRow']
_SCHEMA = 'sipi.two-ground-line-quantity-study/1'


@dataclass(frozen=True)
class TwoGroundLineQuantityStudyRow(FEMShapeLineQuantityStudyRow):
    def to_dict(self):
        out = super().to_dict()
        out['dielectric_mesh'] = None if self.result is None else self.result.mesh_record()
        return out


@dataclass(frozen=True)
class TwoGroundLineQuantityStudy(FEMShapeLineQuantityStudy):
    def to_dict(self):
        out = super().to_dict()
        out['scope'] = 'stated-two-ground-line-quantity-samples-descriptive-not-yield'
        return out


class TwoGroundLineQuantityStudyDocument:
    """Sample one full-complex lossy quantity with fixed whole-surface metals.

    Scalar z0 sources select impedance_real or attenuation. Paired
    z_diff_forward sources select differential_forward_impedance_real or
    common_forward_impedance_real. All ordered geometry/material samples and
    failed rows remain intact; summaries require every row to succeed.
    """
    def __init__(self, study, *, quantity, conductors, reference, ground_thickness,
                 panels_per_edge=32, ground_modes=128, interpolation_degree=12):
        if isinstance(study, ImpedanceStudyDocument): study = study.to_dict()
        self._data = self._validate(dict(schema=_SCHEMA, study=study, quantity=quantity,
            conductors=conductors, reference=reference, ground_thickness_m=ground_thickness,
            panel=dict(panels_per_edge=panels_per_edge, ground_modes=ground_modes,
                       interpolation_degree=interpolation_degree)))

    @staticmethod
    def _validate(data):
        data = _json_copy(data)
        _keys(data, ('schema','study','quantity','conductors','reference','ground_thickness_m','panel'),
              where='two-ground line quantity study')
        if data['schema'] != _SCHEMA: raise ValueError('unsupported two-ground-line-quantity-study schema')
        if not isinstance(data['quantity'],str) or data['quantity'] not in _QUANTITIES:
            raise ValueError('unsupported two-ground line quantity')
        source = _source_inputs(data, paired=data['quantity'] in _PAIR)
        return dict(schema=_SCHEMA, quantity=data['quantity'], **source)

    @classmethod
    def from_dict(cls, data):
        result = cls.__new__(cls)
        result._data = cls._validate(data)
        return result

    @classmethod
    def loads(cls, text):
        def reject(value):raise ValueError('nonfinite JSON number: '+value)
        return cls.from_dict(json.loads(text, object_pairs_hook=_unique_object, parse_constant=reject))

    def dumps(self):
        return json.dumps(self._data,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)

    def to_dict(self):return json.loads(self.dumps())
    def samples(self):return ImpedanceStudyDocument.from_dict(self._data['study']).samples()

    def analyze(self, *, max_evaluations=128):
        with _current_reuse_scope(), _mesh_reuse_scope():
            return _analyze_fem_shape_study(self, max_evaluations=max_evaluations,
                line_factory=lambda study,parameters,evaluation,data:_line_from_inputs(data,parameters,evaluation),
                row_type=TwoGroundLineQuantityStudyRow, result_type=TwoGroundLineQuantityStudy,
                cause_class=TwoGroundPanelLineError)
