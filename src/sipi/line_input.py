# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Internal shared geometry/material source construction, without solves."""
from .document import CrossSectionDocument
from .study import ImpedanceStudyDocument, _TEMPLATES, _parameters
from .impedance_material import _models, _sample_material
from .line_model import TransmissionLineDocument
from .network import _scalar


def _source_study(value, *, paired=False):
    study = ImpedanceStudyDocument.from_dict(value).to_dict()
    if study['schema'] not in ('sipi.impedance-study/3', 'sipi.impedance-study/4'):
        raise ValueError('line source requires study/3 or /4 with fixed material evaluation frequency')
    expected = 'z_diff_forward' if paired else 'z0'
    if study['quantity'] != expected:
        raise ValueError(f'line source must specify quantity={expected}')
    _scalar('frequency_hz', study['material_evaluation']['frequency_hz'])
    return study


def _line_from_inputs(study, conductor, parameters, evaluation, *, line_schema='sipi.transmission-line/6'):
    section = _TEMPLATES[study['template']](**parameters)
    count = 2 if study['quantity'] == 'z_diff_forward' else 1
    if sum(not trace.ground for trace in section.traces) != count:
        raise ValueError(f'line source requires exactly {count} signal(s)')
    return TransmissionLineDocument(CrossSectionDocument(section, mesh=study['mesh']),
        [evaluation['frequency_hz']], materials=_models(evaluation), conductor=conductor,
        length=0., z_ref=50., schema=line_schema)


def _line_from_values(study, conductor, values=None, *, line_schema='sipi.transmission-line/6'):
    parameters = study['parameters'] if values is None else _parameters(study, values)
    evaluation = (study['material_evaluation'] if values is None else
                  _sample_material(study, values))
    options = {} if line_schema == 'sipi.transmission-line/6' else dict(line_schema=line_schema)
    return _line_from_inputs(study, conductor, parameters, evaluation, **options)
