# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Versioned opt-in panel currents with matching dielectric extraction."""
from dataclasses import dataclass
from types import MappingProxyType
from collections.abc import Mapping
import json
import numpy as np
from .document import CrossSectionDocument
from .document import _keys, _unique_object
from .line_model import TransmissionLineDocument, TransmissionLineResult, _conductor
from .panel_conductor import (PanelCurrentFactors, panel_surface_current_factors,
                              panel_conductor_loss_by_boundary)
from .dielectric import dielectric_from_dict, _material_samples, _dispersive_from_mesh
from .network import rlgc_network
from .sampling import _integer


__all__ = ['PanelTransmissionLineDocument', 'PanelTransmissionLineResult']


@dataclass(frozen=True)
class PanelTransmissionLineResult(TransmissionLineResult):
    """Matched RLGC with retained panel controls and complete input snapshot."""
    current_factors: PanelCurrentFactors
    panel_settings: Mapping

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self,'panel_settings',MappingProxyType(dict(self.panel_settings)))


class PanelTransmissionLineDocument:
    """Strict sipi.panel-transmission-line/1 with a canonical nested line.

    The nested line must select perfect or surface-boundaries conductors.
    Panel currents supply the matching vacuum capacitance and external L;
    the existing dielectric solver supplies C/G on one saved volume mesh.
    Normalization performs no field solve. Shared geometric admission and
    numerical refinement still occur when analyze() is called.
    """
    def __init__(self,line,*,panels_per_edge=32,ground_modes=512,interpolation_degree=10):
        if not isinstance(line,TransmissionLineDocument):
            raise TypeError('line must be a TransmissionLineDocument')
        self._data=self._validate(dict(schema='sipi.panel-transmission-line/1',line=line.to_dict(),
            panel=dict(panels_per_edge=panels_per_edge,ground_modes=ground_modes,interpolation_degree=interpolation_degree)))

    @staticmethod
    def _validate(data):
        _keys(data,('schema','line','panel'),where='panel transmission line')
        if data['schema']!='sipi.panel-transmission-line/1':raise ValueError('unsupported panel-transmission-line schema')
        if (not isinstance(data['line'], dict) or data['line'].get('schema') not in
                tuple(f'sipi.transmission-line/{v}' for v in (1, 2, 3, 4, 5, 6))):
            raise ValueError('panel line requires a nested transmission-line/1 through /6')
        line=TransmissionLineDocument.from_dict(data['line']);value=line.to_dict();section=line.cross_section.section
        if value['conductor']['kind'] not in ('perfect','surface-boundaries'):
            raise ValueError('panel line requires perfect or surface-boundaries conductor')
        if (section.bottom,section.top,section.sides)!=('ground','open','open'):
            raise ValueError('panel line requires bottom ground and open top/sides')
        if any(t.thickness<=0 for t in section.traces):raise ValueError('panel line requires positive conductor thickness')
        _keys(data['panel'],('panels_per_edge','ground_modes','interpolation_degree'),where='panel controls')
        opts=dict(data['panel']);opts['panels_per_edge']=_integer(opts['panels_per_edge'],1,256)
        opts['ground_modes']=_integer(opts['ground_modes'],64,4096)
        degree=_integer(opts['interpolation_degree'],10,16)
        if degree not in (10,12,14,16):raise ValueError('interpolation_degree must be 10,12,14 or16')
        if len(section.traces)>16 or sum(len(t.corners()) for t in section.traces)*opts['panels_per_edge']>2048:
            raise ValueError('panel line exceeds shared conductor or panel count limit')
        return dict(schema=data['schema'],line=value,panel=opts)

    @classmethod
    def from_dict(cls,data):
        out=cls.__new__(cls);out._data=cls._validate(data);return out

    @classmethod
    def loads(cls,text):
        def reject(value):raise ValueError('nonfinite JSON number: '+value)
        return cls.from_dict(json.loads(text,object_pairs_hook=_unique_object,parse_constant=reject))

    def dumps(self):return json.dumps(self._data,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)
    def to_dict(self):return json.loads(self.dumps())
    @property
    def line(self):return TransmissionLineDocument.from_dict(self.to_dict()['line'])
    @property
    def panel_options(self):return dict(self._data['panel'])

    def analyze(self):
        data=self.to_dict();line=data['line'];doc=CrossSectionDocument.from_dict(line['cross_section']);section=doc.section
        materials={k:dielectric_from_dict(v) for k,v in line['materials'].items()}
        f,samples=_material_samples(section,line['frequency_hz'],materials)
        _,metal_samples=_conductor(line['conductor'],section,f,line['schema'])
        if metal_samples is None:
            loss=None;factors=panel_surface_current_factors(section,**data['panel'])
        else:
            names,_,metals,_,_,_=metal_samples
            loss=panel_conductor_loss_by_boundary(section,f,conductors=dict(zip(names,metals[:-1])),reference=metals[-1],ground_thickness=line['conductor']['ground_thickness'],**data['panel'])
            factors=loss.factors
        meshed=section.mesh(**doc.mesh_options)
        if tuple(meshed.signals)!=factors.names:raise ValueError('dielectric mesh changed panel signal order')
        dielectric=_dispersive_from_mesh(meshed,f,samples,c0=factors.C0)
        R=np.zeros_like(dielectric.C) if loss is None else loss.R
        L=dielectric.L if loss is None else dielectric.L+loss.L_internal
        network=rlgc_network(f,R=R,L=L,G=dielectric.G,C=dielectric.C,length=line['length_m'],z_ref=line['reference_ohms'],names=dielectric.names)
        return PanelTransmissionLineResult(dielectric,loss,network,self.dumps(),doc.mesh_options,factors,data['panel'])
