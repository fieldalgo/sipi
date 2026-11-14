# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Manufacturing samples with explicit shape currents on finite frequency grids."""
from dataclasses import dataclass
import json
from .document import _keys,_unique_object
from .line_input import _line_from_values
from .sampled_panel_pair_study import (SampledPanelForwardPairStudyDocument,
    SampledPanelForwardPairStudy,SampledPanelForwardPairStudyRow,
    _full_line,_sampled_study_line,_run_sampled_panel_study)
from .shape_panel_line import ShapePanelTransmissionLineDocument,ShapePanelLineError,shape_current_record

__all__ = ['ShapeSampledPanelForwardPairStudyDocument','ShapeSampledPanelForwardPairStudy',
           'ShapeSampledPanelForwardPairStudyRow']


@dataclass(frozen=True)
class ShapeSampledPanelForwardPairStudyRow(SampledPanelForwardPairStudyRow):
    cause_details_json: str | None = None

    @property
    def cause_details(self):
        return None if self.cause_details_json is None else json.loads(self.cause_details_json)

    def to_dict(self):
        out=super().to_dict()
        out['cause_details']=self.cause_details
        out['current_solver']=(None if self.result is None else
            shape_current_record(self.result.current_factors,self.result.panel_settings))
        return out


def _shape_sampled_row(*args,cause=None):
    details=json.dumps(cause.to_dict(),allow_nan=False) if isinstance(cause,ShapePanelLineError) else None
    return ShapeSampledPanelForwardPairStudyRow(*args,cause_details_json=details)


@dataclass(frozen=True)
class ShapeSampledPanelForwardPairStudy(SampledPanelForwardPairStudy):
    def to_dict(self):
        out=super().to_dict()
        out['scope']='stated-shape-current-paired-frequency-samples-descriptive-not-production-yield'
        return out


class ShapeSampledPanelForwardPairStudyDocument:
    """Keep one manufactured geometry/material sample across the whole grid.

    A failed grid is one unresolved row, not a set of resampled frequencies.
    Every original row remains in order and any failure suppresses all summaries.
    This explicit wrapper leaves original saved methods and defaults unchanged.
    """
    def __init__(self,study,*,step_fraction=1e-3):
        if not isinstance(study,SampledPanelForwardPairStudyDocument):
            raise TypeError('study must be a SampledPanelForwardPairStudyDocument')
        self._data=self._validate(dict(schema='sipi.shape-sampled-panel-forward-pair-study/1',
            study=study.to_dict(),step_fraction=step_fraction))

    @staticmethod
    def _validate(data):
        _keys(data,('schema','study','step_fraction'),where='shape sampled panel pair study')
        if data['schema']!='sipi.shape-sampled-panel-forward-pair-study/1':
            raise ValueError('unsupported shape-sampled-panel-forward-pair-study schema')
        study=SampledPanelForwardPairStudyDocument.from_dict(data['study']);raw=study.to_dict()
        layered=raw['schema']=='sipi.sampled-panel-forward-pair-study/2'
        options=dict(line_schema='sipi.transmission-line/7') if layered else {}
        nominal=ShapePanelTransmissionLineDocument(_full_line(
            _line_from_values(raw['study'],raw['conductor'],**options),raw['frequency_hz'],
            raw['panel'],layered=layered),step_fraction=data['step_fraction'])
        return dict(schema=data['schema'],study=study.to_dict(),
                    step_fraction=nominal.to_dict()['step_fraction'])

    @classmethod
    def from_dict(cls,data):
        out=cls.__new__(cls);out._data=cls._validate(data);return out

    @classmethod
    def loads(cls,text):
        def reject(value):raise ValueError('nonfinite JSON number: '+value)
        return cls.from_dict(json.loads(text,object_pairs_hook=_unique_object,parse_constant=reject))

    def dumps(self):
        return json.dumps(self._data,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)

    def to_dict(self):
        return json.loads(self.dumps())

    @property
    def study(self):
        return SampledPanelForwardPairStudyDocument.from_dict(self.to_dict()['study'])

    def samples(self):
        return self.study.samples()

    def analyze(self,*,max_evaluations=128):
        fraction=self.to_dict()['step_fraction']
        return _run_sampled_panel_study(self.study,max_evaluations=max_evaluations,
            make_line=lambda data,p,e:ShapePanelTransmissionLineDocument(
                _sampled_study_line(data,p,e),step_fraction=fraction),
            physical_line=lambda doc:doc.line.line,row_factory=_shape_sampled_row,
            result_factory=ShapeSampledPanelForwardPairStudy,input_text=self.dumps)
