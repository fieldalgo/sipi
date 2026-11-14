# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved iid acceptance comparison over explicit, physically identical resolutions."""
import json
from .document import _keys, _unique_object
from .sampling import _copy, _integer
from .panel_pair_study import PanelForwardPairStudyDocument
from .panel_pair_yield import _acceptance
from .panel_resolution_yield import _resolution_documents, assess_panel_pair_resolution_yield

__all__ = ['PanelResolutionYieldDocument']
_SCHEMA = 'sipi.panel-resolution-yield/1'


class PanelResolutionYieldDocument:
    """Save 2..8 explicit iid studies; no automatic resolution or physics changes.

    Only volume mesh and panel controls differ. Every study retains its full
    sample plan, metal laws and current method. The total budget counts all
    planned whole-line rows, including failed rows, across all resolutions.
    This does not bound internal field solves, time or discretization error.
    """
    def __init__(self,studies,*,acceptance,confidence=.95,minimum_yield=None):
        if not isinstance(studies,(list,tuple)) or any(
                not isinstance(doc,PanelForwardPairStudyDocument) for doc in studies):
            raise TypeError('studies must be a list or tuple of PanelForwardPairStudyDocument')
        self._assign(dict(schema=_SCHEMA,studies=[doc.to_dict() for doc in studies],
            acceptance=acceptance,confidence=confidence,minimum_yield=minimum_yield))

    def _assign(self,data):
        data=_copy(data)
        _keys(data,('schema','studies','acceptance','confidence','minimum_yield'),where='panel resolution yield')
        if data['schema']!=_SCHEMA:raise ValueError('unsupported panel-resolution-yield schema')
        if not isinstance(data['studies'],list) or not 2<=len(data['studies'])<=8:
            raise ValueError('resolution comparison requires 2..8 paired studies')
        documents=_resolution_documents(tuple(PanelForwardPairStudyDocument.from_dict(d) for d in data['studies']))
        sources=[doc.to_dict() for doc in documents]
        sampling=sources[0]['study']['sampling']
        if sampling['kind'] not in ('uniform','normal'):
            raise ValueError('resolution yield requires iid uniform or normal samples')
        if sampling['count']*len(sources)>10000:
            raise ValueError('resolution plan exceeds 10000 whole-line evaluations')
        limits,level,target=_acceptance(data['acceptance'],data['confidence'],data['minimum_yield'])
        self._data=dict(schema=_SCHEMA,studies=sources,acceptance=limits,confidence=level,minimum_yield=target)

    @classmethod
    def from_dict(cls,data):
        out=cls.__new__(cls);out._assign(data);return out

    @classmethod
    def loads(cls,text):
        def reject(value):raise ValueError('nonfinite JSON number: '+value)
        return cls.from_dict(json.loads(text,object_pairs_hook=_unique_object,parse_constant=reject))

    def dumps(self):return json.dumps(self._data,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)
    def to_dict(self):return json.loads(self.dumps())
    @property
    def studies(self):return tuple(PanelForwardPairStudyDocument.from_dict(d) for d in self.to_dict()['studies'])
    @property
    def required_evaluations(self):
        return self._data['studies'][0]['study']['sampling']['count']*len(self._data['studies'])

    def analyze(self,*,max_evaluations=128):
        budget=_integer(max_evaluations,2,10000)
        if self.required_evaluations>budget:
            raise ValueError('resolution plan exceeds max_evaluations before any solve')
        documents=self.studies
        count=self._data['studies'][0]['study']['sampling']['count']
        # All sources have the same complete sampling specification. Validate its
        # generation before the first field; each source retains its original order.
        if len(documents[0].samples())!=count:
            raise ValueError('sample plan changed before any solve')
        studies=[doc.analyze(max_evaluations=count) for doc in documents]
        data=self.to_dict()
        return assess_panel_pair_resolution_yield(studies,**{key:data[key] for key in
            ('acceptance','confidence','minimum_yield')})
