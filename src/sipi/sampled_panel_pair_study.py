# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit paired panel-current sampling with complete failed rows."""
from dataclasses import dataclass
import json
from types import MappingProxyType

import numpy as np

from sipi.document import _keys, _unique_object
from sipi.study import ImpedanceStudyDocument, _parameters
from sipi.sampling import _copy, _integer
from sipi.network import _frequencies
from sipi.line_model import TransmissionLineDocument
from sipi.impedance_material import _sample_material
from sipi.line_input import _source_study, _line_from_values, _line_from_inputs
from sipi.line_study import _json, _summary
from sipi.panel_line import PanelTransmissionLineDocument

__all__ = ['SampledPanelForwardPairStudyDocument', 'SampledPanelForwardPairStudy', 'SampledPanelForwardPairStudyRow']

_QUANTITIES = ('differential_forward_impedance_real', 'common_forward_impedance_real')
_SCHEMA = 'sipi.sampled-panel-forward-pair-study/1'


def _full_line(line, frequencies, panel):
    raw = line.to_dict()
    raw['frequency_hz'] = frequencies
    return PanelTransmissionLineDocument(TransmissionLineDocument.from_dict(raw), **panel)


@dataclass(frozen=True)
class SampledPanelForwardPairStudyRow:
    index: int
    sample_values: tuple[float, ...]
    parameters_json: str | None
    material_evaluation_json: str | None
    input_json: str | None
    values: tuple[tuple[float, float], ...] | None
    phase: str
    error_type: str | None
    error: str | None
    result: object | None = None

    @property
    def complete(self):
        return self.error is None

    def to_dict(self):
        return dict(index=self.index, sample_values=list(self.sample_values),
            values_ohm=None if self.values is None else [list(row) for row in self.values],
            phase=self.phase, error_type=self.error_type, error=self.error,
            parameters=None if self.parameters_json is None else json.loads(self.parameters_json),
            material_evaluation=(None if self.material_evaluation_json is None else
                                 json.loads(self.material_evaluation_json)),
            input=None if self.input_json is None else json.loads(self.input_json))


@dataclass(frozen=True)
class SampledPanelForwardPairStudy:
    input_json: str
    frequencies: tuple[float, ...]
    variable_names: tuple[str, ...]
    rows: tuple[SampledPanelForwardPairStudyRow, ...]
    summary: object | None

    def __post_init__(self):
        object.__setattr__(self, 'frequencies', tuple(self.frequencies))
        object.__setattr__(self, 'variable_names', tuple(self.variable_names))
        object.__setattr__(self, 'rows', tuple(self.rows))
        if self.summary is not None:
            object.__setattr__(self, 'summary', MappingProxyType(
                {k: tuple(MappingProxyType(dict(s)) for s in v) for k, v in self.summary.items()}))

    @property
    def failed(self):
        return sum((not row.complete for row in self.rows))

    def to_dict(self):
        return dict(quantities=list(_QUANTITIES), unit='ohm', frequencies_hz=list(self.frequencies), variable_names=list(self.variable_names),
            count=len(self.rows), failed=self.failed,
            summary=None if self.summary is None else {k: [dict(s) for s in v] for k, v in self.summary.items()},
            rows=[row.to_dict() for row in self.rows],
            scope='stated-paired-frequency-samples-descriptive-not-production-yield')


class SampledPanelForwardPairStudyDocument:
    """Preserve one manufactured sample across a finite full frequency grid.

    Study frequency anchors the first sample; full-grid material and diagnostic
    checks apply to every attempted row. Atomic failed batches and later rows
    remain in order. All-or-none per-frequency summaries are descriptive only.
    Mesh/panel controls remain fixed; no automatic per-row convergence runs.
    """

    def __init__(self, study, *, conductor, frequencies, panels_per_edge=32, ground_modes=512, interpolation_degree=10):
        if isinstance(study, ImpedanceStudyDocument):
            study = study.to_dict()
        self._assign(dict(schema=_SCHEMA, study=study, conductor=conductor, frequency_hz=frequencies,
            panel=dict(panels_per_edge=panels_per_edge, ground_modes=ground_modes,
                       interpolation_degree=interpolation_degree)))

    def _assign(self, data):
        data = _copy(data)
        _keys(data, ('schema', 'study', 'conductor', 'panel', 'frequency_hz'), where='sampled panel forward pair study')
        if data['schema'] != _SCHEMA:
            raise ValueError('unsupported panel-forward-pair-study schema')
        study = _source_study(data['study'], paired=True)
        frequencies = _frequencies(data['frequency_hz'])
        if not 2 <= len(frequencies) <= 64 or np.any(frequencies <= 0):
            raise ValueError('frequencies must contain 2..64 increasing positive values')
        if study['material_evaluation']['frequency_hz'] != frequencies[0]:
            raise ValueError('study frequency must equal first requested frequency')
        frequencies = frequencies.tolist()
        _keys(data['panel'], ('panels_per_edge', 'ground_modes', 'interpolation_degree'), where='panel controls')
        nominal = _full_line(_line_from_values(study, data['conductor']), frequencies, data['panel'])
        self._data = dict(schema=_SCHEMA, study=study, frequency_hz=frequencies,
            conductor=nominal.line.to_dict()['conductor'], panel=nominal.panel_options)

    @classmethod
    def from_dict(cls, data):
        out = cls.__new__(cls)
        out._assign(data)
        return out

    @classmethod
    def loads(cls, text):
        def reject(value):
            raise ValueError('nonfinite JSON number: ' + value)
        return cls.from_dict(json.loads(text, object_pairs_hook=_unique_object, parse_constant=reject))

    def dumps(self):
        return json.dumps(self._data, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)

    def to_dict(self):
        return json.loads(self.dumps())

    def samples(self):
        return ImpedanceStudyDocument.from_dict(self._data['study']).samples()

    def analyze(self, *, max_evaluations=128):
        budget = _integer(max_evaluations, 2, 10000)
        data = self.to_dict()
        study = data['study']
        samples = self.samples()
        if len(samples) > budget:
            raise ValueError('sample count exceeds max_evaluations before any solve')
        rows = []
        for index, values in enumerate(samples):
            parameters_json = material_json = input_json = None
            line = None
            quantities = None
            phase = 'parameters'
            error_type = error = None
            try:
                parameters = _parameters(study, values)
                parameters_json = _json(parameters)
                phase = 'materials'
                evaluation = _sample_material(study, values)
                material_json = _json(evaluation)
                phase = 'input'
                doc = _full_line(_line_from_inputs(study, data['conductor'], parameters, evaluation),
                                 data['frequency_hz'], data['panel'])
                input_json = doc.dumps()
                phase = 'extraction'
                line = doc.analyze()
                names = tuple((t.name for t in doc.line.cross_section.section.traces if not t.ground))
                if (len(names) != 2 or tuple(line.names) != names
                        or tuple(line.frequency) != tuple(data['frequency_hz'])):
                    raise ValueError('extraction changed signal names or frequency')
                phase = 'diagnostic'
                characteristic = line.characteristic()
                if (characteristic.basis != 'single-ended' or tuple(characteristic.names) != names
                        or tuple(characteristic.frequency) != tuple(line.frequency)):
                    raise ValueError('characteristic changed signal coordinates or frequency')
                mixed = characteristic.mixed_mode()
                if (mixed.basis != 'mixed-mode' or tuple(mixed.names) != ('differential', 'common')
                        or tuple(mixed.frequency) != tuple(line.frequency)):
                    raise ValueError('mixed characteristic changed coordinates or frequency')
                matrix = np.asarray(mixed.z_characteristic)
                if matrix.shape != (len(data['frequency_hz']), 2, 2) or not np.all(np.isfinite(matrix)):
                    raise ValueError('mixed characteristic must contain one finite 2-by-2 matrix per frequency')
                quantities = tuple(tuple(float(x) for x in row) for row in np.diagonal(matrix, axis1=1, axis2=2).real)
                if np.any(np.asarray(quantities) <= 0) or not np.all(np.isfinite(quantities)):
                    raise ValueError('solver returned invalid forward impedances')
                phase = 'complete'
            except Exception as exc:
                quantities = None
                error_type = type(exc).__name__
                error = str(exc)
            rows.append(SampledPanelForwardPairStudyRow(index, tuple(map(float, values)), parameters_json,
                material_json, input_json, quantities, phase, error_type, error, line))
        summary = ({q: tuple(_summary([row.values[f][i] for row in rows])
                            for f in range(len(data['frequency_hz']))) for i, q in enumerate(_QUANTITIES)}
                   if all((row.complete for row in rows)) else None)
        return SampledPanelForwardPairStudy(self.dumps(), tuple(data['frequency_hz']),
            tuple((v['name'] for v in study['sampling']['variables'])), tuple(rows), summary)
