# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved finite-domain shape currents with separate whole reference metals."""
import json
from .document import CrossSectionDocument, _keys, _unique_object
from .dielectric import dielectric_from_dict, dielectric_to_dict, _material_samples, _dispersive_from_mesh
from .line_model import _surface_metal, _reference_metal
from .network import _frequencies, _scalar, rlgc_network
from .panel_shape_conductor import _prepare
from .shape_reference_conductor import _shape_reference_samples, panel_shape_conductor_loss_with_reference_metals
from .shape_panel_line import ShapePanelTransmissionLineResult, ShapePanelLineError

__all__ = ['ShapeReferencePanelTransmissionLineDocument']
_SCHEMA = 'sipi.shape-reference-panel-transmission-line/1'


def _metals(data):
    if not isinstance(data['conductors'],dict):
        raise ValueError('conductors must be an object keyed by signal name')
    conductors={name:_surface_metal(value,'sipi.transmission-line/7')
                for name,value in data['conductors'].items()}
    ref=data['reference']
    if not isinstance(ref,dict) or ref.get('kind')!='surfaces':
        raise ValueError('reference must explicitly select separate surfaces')
    reference,record=_reference_metal(ref,faces=True,schema='sipi.transmission-line/7')
    return ({name:pair[0] for name,pair in conductors.items()},reference,
            {name:pair[1] for name,pair in conductors.items()},record)


class ShapeReferencePanelTransmissionLineDocument:
    """Explicit SI input; open top/sides, finite convex conductors, bottom ground.

    Each signal, bottom plane and grounded trace selects one whole-boundary
    bulk/rough or coated surface law. No face-specific or perfect model is
    implicit. All local metal/core and shape-offset admission precedes fields.
    The existing current solver supplies C0/L_external, while one saved volume
    mesh supplies C/G. This input does not certify outer-domain convergence.
    """
    def __init__(self,cross_section,frequency,*,materials,conductors,reference,
                 ground_thickness,length,z_ref=50.,panels_per_edge=32,
                 ground_modes=512,interpolation_degree=16,step_fraction=1e-3):
        if not isinstance(cross_section,CrossSectionDocument):
            raise TypeError('cross_section must be a CrossSectionDocument')
        self._data=self._validate(dict(schema=_SCHEMA,cross_section=cross_section.to_dict(),
            frequency_hz=_frequencies(frequency).tolist(),
            materials={name:dielectric_to_dict(value) for name,value in materials.items()},
            conductors=conductors,reference=reference,ground_thickness_m=ground_thickness,
            length_m=length,reference_ohms=z_ref,panel=dict(panels_per_edge=panels_per_edge,
                ground_modes=ground_modes,interpolation_degree=interpolation_degree),step_fraction=step_fraction))

    @staticmethod
    def _validate(data):
        _keys(data,('schema','cross_section','frequency_hz','materials','conductors','reference',
                   'ground_thickness_m','length_m','reference_ohms','panel','step_fraction'),where='reference shape line')
        if data['schema']!=_SCHEMA:raise ValueError('unsupported shape-reference-panel-transmission-line schema')
        cross=CrossSectionDocument.from_dict(data['cross_section']);section=cross.section
        if not isinstance(data['materials'],dict):raise ValueError('materials must be an object')
        materials={name:dielectric_from_dict(value) for name,value in data['materials'].items()}
        f,_=_material_samples(section,data['frequency_hz'],materials)
        conductors,reference,records,ref_record=_metals(data)
        thickness=_scalar('ground_thickness_m',data['ground_thickness_m'])
        _shape_reference_samples(section,f,conductors,reference,thickness)
        _keys(data['panel'],('panels_per_edge','ground_modes','interpolation_degree'),where='panel controls')
        _prepare(section,step_fraction=data['step_fraction'],**data['panel'])
        return dict(schema=_SCHEMA,cross_section=cross.to_dict(),frequency_hz=f.tolist(),
            materials={name:dielectric_to_dict(value) for name,value in materials.items()},
            conductors=records,reference=ref_record,ground_thickness_m=thickness,
            length_m=_scalar('length_m',data['length_m'],zero=True),
            reference_ohms=_scalar('reference_ohms',data['reference_ohms']),
            panel={name:int(value) for name,value in data['panel'].items()},step_fraction=float(data['step_fraction']))

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
    def cross_section(self):return CrossSectionDocument.from_dict(self.to_dict()['cross_section'])
    @property
    def current_options(self):return dict(self._data['panel'],step_fraction=self._data['step_fraction'])

    def analyze(self):
        data=self.to_dict();cross=self.cross_section;section=cross.section;options=self.current_options
        factors=None;stage='material-admission'
        try:
            materials={name:dielectric_from_dict(value) for name,value in data['materials'].items()}
            f,samples=_material_samples(section,data['frequency_hz'],materials)
            stage='conductor-admission'
            conductors,reference,_,_=_metals(data)
            _shape_reference_samples(section,f,conductors,reference,data['ground_thickness_m'])
            stage='current'
            loss=panel_shape_conductor_loss_with_reference_metals(section,f,conductors=conductors,
                reference=reference,ground_thickness=data['ground_thickness_m'],**options)
            factors=loss.factors
            stage='mesh';meshed=section.mesh(**cross.mesh_options)
            if tuple(meshed.signals)!=factors.names:raise ValueError('dielectric mesh changed shape-current signal order')
            stage='dielectric';dielectric=_dispersive_from_mesh(meshed,f,samples,c0=factors.C0)
            stage='network'
            network=rlgc_network(f,R=loss.R,L=dielectric.L+loss.L_internal,G=dielectric.G,C=dielectric.C,
                length=data['length_m'],z_ref=data['reference_ohms'],names=dielectric.names)
            return ShapePanelTransmissionLineResult(dielectric,loss,network,self.dumps(),cross.mesh_options,factors,options)
        except Exception as exc:
            raise ShapePanelLineError(exc,stage=stage,input_json=self.dumps(),factors=factors,settings=options) from exc
