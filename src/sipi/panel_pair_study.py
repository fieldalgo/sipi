# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit paired panel-current sampling with complete failed rows."""
from dataclasses import dataclass
import json
from types import MappingProxyType

import numpy as np

from .document import _keys, _unique_object
from .study import ImpedanceStudyDocument, _parameters
from .sampling import _copy, _integer
from .impedance_material import _sample_material
from .line_input import _source_study, _line_from_values, _line_from_inputs
from .line_study import _json, _summary
from .panel_line import PanelTransmissionLineDocument

__all__ = ['PanelForwardPairStudyDocument', 'PanelForwardPairStudy', 'PanelForwardPairStudyRow']

_QUANTITIES = ('differential_forward_impedance_real', 'common_forward_impedance_real')
_SCHEMA = 'sipi.panel-forward-pair-study/1'


@dataclass(frozen=True)
class PanelForwardPairStudyRow:
    index: int
    sample_values: tuple[float, ...]
    parameters_json: str | None
    material_evaluation_json: str | None
    input_json: str | None
    values: tuple[float, float] | None
    phase: str
    error_type: str | None
    error: str | None
    result: object | None = None

    @property
    def complete(self):
        return self.error is None

    def to_dict(self):
        return dict(index=self.index, sample_values=list(self.sample_values),
            values_ohm=None if self.values is None else list(self.values),
            phase=self.phase, error_type=self.error_type, error=self.error,
            parameters=None if self.parameters_json is None else json.loads(self.parameters_json),
            material_evaluation=(None if self.material_evaluation_json is None else
                                 json.loads(self.material_evaluation_json)),
            input=None if self.input_json is None else json.loads(self.input_json))


@dataclass(frozen=True)
class PanelForwardPairStudy:
    input_json: str
    variable_names: tuple[str, ...]
    rows: tuple[PanelForwardPairStudyRow, ...]
    summary: object | None

    def __post_init__(self):
        object.__setattr__(self, 'variable_names', tuple(self.variable_names))
        object.__setattr__(self, 'rows', tuple(self.rows))
        if self.summary is not None:
            object.__setattr__(self, 'summary', MappingProxyType(
                {k: MappingProxyType(dict(v)) for k, v in self.summary.items()}))

    @property
    def failed(self):
        return sum((not row.complete for row in self.rows))

    def to_dict(self):
        return dict(quantities=list(_QUANTITIES), unit='ohm', variable_names=list(self.variable_names),
            count=len(self.rows), failed=self.failed,
            summary=None if self.summary is None else {k: dict(v) for k, v in self.summary.items()},
            rows=[row.to_dict() for row in self.rows],
            scope='stated-paired-samples-descriptive-not-production-yield')


class PanelForwardPairStudyDocument:
    """Sample both full-complex forward impedances from one panel extraction.

    The nested paired study/3 or /4 supplies the fixed positive frequency,
    ordered geometry/material variables and existing sampling/constraint rules.
    Its z_diff_forward label selects source inputs; no quasi-static study runs.
    Each row creates an explicit zero-length panel line, retaining asymmetric
    coupling. The two real mixed characteristic diagonals describe separate
    Ic=0 and Id=0 current launches, not independent propagation modes.

    All samples are generated and their count checked before field work.
    Every row is attempted in order, including duplicates and later rows after
    failures. Resolved inputs, failure stages and available extracted results
    are preserved. Both values succeed or fail together. Descriptive summaries
    exist only when every row succeeds; no rows are clipped, dropped, resampled
    or reweighted. These summaries are not production-yield confidence bounds.

    Nominal resolved mesh and panel settings are fixed across rows; this is not
    a reused geometric mesh or an automatic per-row convergence guarantee.
    The existing panel geometry, resource and skin-depth gates still apply.
    """

    def __init__(self, study, *, conductor, panels_per_edge=32, ground_modes=512, interpolation_degree=10):
        if isinstance(study, ImpedanceStudyDocument):
            study = study.to_dict()
        self._assign(dict(schema=_SCHEMA, study=study, conductor=conductor,
            panel=dict(panels_per_edge=panels_per_edge, ground_modes=ground_modes,
                       interpolation_degree=interpolation_degree)))

    def _assign(self, data):
        data = _copy(data)
        _keys(data, ('schema', 'study', 'conductor', 'panel'), where='panel forward pair study')
        if data['schema'] != _SCHEMA:
            raise ValueError('unsupported panel-forward-pair-study schema')
        study = _source_study(data['study'], paired=True)
        _keys(data['panel'], ('panels_per_edge', 'ground_modes', 'interpolation_degree'), where='panel controls')
        nominal = PanelTransmissionLineDocument(_line_from_values(study, data['conductor']), **data['panel'])
        self._data = dict(schema=_SCHEMA, study=study,
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
                doc = PanelTransmissionLineDocument(
                    _line_from_inputs(study, data['conductor'], parameters, evaluation), **data['panel'])
                input_json = doc.dumps()
                phase = 'extraction'
                line = doc.analyze()
                names = tuple((t.name for t in doc.line.cross_section.section.traces if not t.ground))
                if (len(names) != 2 or tuple(line.names) != names
                        or tuple(line.frequency) != (evaluation['frequency_hz'],)):
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
                if matrix.shape != (1, 2, 2) or not np.all(np.isfinite(matrix)):
                    raise ValueError('mixed characteristic must be one finite 2-by-2 matrix')
                quantities = tuple((float(x) for x in np.diag(matrix[0]).real))
                if any((x <= 0 or not np.isfinite(x) for x in quantities)):
                    raise ValueError('solver returned invalid forward impedances')
                phase = 'complete'
            except Exception as exc:
                quantities = None
                error_type = type(exc).__name__
                error = str(exc)
            rows.append(PanelForwardPairStudyRow(index, tuple(map(float, values)), parameters_json,
                material_json, input_json, quantities, phase, error_type, error, line))
        summary = ({q: _summary([row.values[i] for row in rows]) for i, q in enumerate(_QUANTITIES)}
                   if all((row.complete for row in rows)) else None)
        return PanelForwardPairStudy(self.dumps(),
            tuple((v['name'] for v in study['sampling']['variables'])), tuple(rows), summary)
