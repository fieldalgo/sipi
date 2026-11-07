# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Internal shared scalar geometry/material source construction, without solves."""
from .document import CrossSectionDocument
from .study import ImpedanceStudyDocument, _TEMPLATES, _parameters
from .impedance_material import _models, _sample_material
from .line_model import TransmissionLineDocument
from .network import _scalar


def _source_study(value):
    study = ImpedanceStudyDocument.from_dict(value).to_dict()
    if study['schema'] not in ('sipi.impedance-study/3', 'sipi.impedance-study/4'):
        raise ValueError('line source requires study/3 or /4 with fixed material evaluation frequency')
    if study['quantity'] != 'z0':
        raise ValueError('line source must specify a scalar z0 template')
    _scalar('frequency_hz', study['material_evaluation']['frequency_hz'])
    return study


def _line_from_inputs(study, conductor, parameters, evaluation):
    section = _TEMPLATES[study['template']](**parameters)
    if sum(not trace.ground for trace in section.traces) != 1:
        raise ValueError('line source requires exactly one signal')
    return TransmissionLineDocument(CrossSectionDocument(section, mesh=study['mesh']),
        [evaluation['frequency_hz']], materials=_models(evaluation), conductor=conductor,
        length=0., z_ref=50., schema='sipi.transmission-line/6')


def _line_from_values(study, conductor, values=None):
    parameters = study['parameters'] if values is None else _parameters(study, values)
    evaluation = (study['material_evaluation'] if values is None else
                  _sample_material(study, values))
    return _line_from_inputs(study, conductor, parameters, evaluation)
