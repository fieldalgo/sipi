# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Internal field-free template/material construction for explicit two-ground face-metal consumers."""
from ._template_registry import _TEMPLATES
from ._validation import _keys
from .document import CrossSectionDocument
from .impedance_material import _models, _sample_material
from .line_input import _source_study
from .study import _parameters
from .two_ground_corner_face_panel_line import TwoGroundCornerFacePanelTransmissionLineDocument


def _line_from_inputs(data, parameters, evaluation):
    study = data['study']
    section = _TEMPLATES[study['template']](**parameters)
    count = 2 if study['quantity'] == 'z_diff_forward' else 1
    if sum(not trace.ground for trace in section.traces) != count:
        message = ('two-ground paired source requires exactly two signals' if count == 2
                   else 'two-ground scalar source requires exactly one signal')
        raise ValueError(message)
    return TwoGroundCornerFacePanelTransmissionLineDocument(
        CrossSectionDocument(section, mesh=study['mesh']), [evaluation['frequency_hz']],
        materials=_models(evaluation), conductors=data['conductors'],
        reference=data['reference'], ground_thickness=data['ground_thickness_m'],
        length=0., z_ref=50., **data['panel'])


def _line_from_values(data, values=None):
    study = data['study']
    parameters = study['parameters'] if values is None else _parameters(study, values)
    evaluation = study['material_evaluation'] if values is None else _sample_material(study, values)
    return _line_from_inputs(data, parameters, evaluation)


def _source_inputs(data, *, paired=True):
    _keys(data['panel'], ('panels_per_edge', 'ground_modes', 'interpolation_degree'), where='panel controls')
    source = dict(study=_source_study(data['study'], paired=paired),
                  conductors=data['conductors'], reference=data['reference'],
                  ground_thickness_m=data['ground_thickness_m'], panel=data['panel'])
    nominal = _line_from_values(source).to_dict()
    return dict(study=source['study'], **{key:nominal[key] for key in
                ('conductors', 'reference', 'ground_thickness_m', 'panel')})
