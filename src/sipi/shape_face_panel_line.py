# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved finite-domain shape currents with explicit straight-face metals."""
import json
from .document import CrossSectionDocument, _keys, _unique_object
from .dielectric import dielectric_from_dict, dielectric_to_dict, _material_samples, _dispersive_from_mesh
from .line_model import _surface_metal, _reference_metal
from .network import _frequencies, _scalar, rlgc_network
from dataclasses import dataclass
from types import MappingProxyType
from .face_conductor import TraceFaceMetals
from .line_model import TransmissionLineResult
from .panel_shape_conductor import PanelShapeCurrentError
from .panel_shape_face_conductor import _prepare_faces, PanelShapeFaceCurrentError, PanelShapeFaceCurrentFactors
from .shape_face_conductor import _shape_face_samples, panel_shape_conductor_loss_by_face
from .shape_panel_line import shape_current_record, _sample_record

__all__ = ['ShapeFacePanelTransmissionLineDocument', 'ShapeFacePanelTransmissionLineResult', 'ShapeFacePanelLineError']
_SCHEMA = 'sipi.shape-face-panel-transmission-line/1'


def _metals(data):
    if not isinstance(data['conductors'],dict):
        raise ValueError('conductors must be an object keyed by signal name')
    faces=('bottom','top','left','right');conductors={};records={}
    for name,record in data['conductors'].items():
        _keys(record,faces,where='signal face metals')
        parsed={face:_surface_metal(record[face],'sipi.transmission-line/7') for face in faces}
        conductors[name]=TraceFaceMetals(**{face:pair[0] for face,pair in parsed.items()})
        records[name]={face:pair[1] for face,pair in parsed.items()}
    ref=data['reference']
    if not isinstance(ref,dict) or ref.get('kind')!='surfaces':
        raise ValueError('reference must explicitly select separate surfaces')
    reference,ref_record=_reference_metal(ref,faces=True,schema='sipi.transmission-line/7')
    return conductors,reference,records,ref_record


def shape_face_current_record(factors,settings):
    """SI face energies and complete original whole-current evidence."""
    return dict(kind='grounded-rectangle-face-capacitance-shape',settings=dict(settings),
        names=list(factors.names),trace_names=list(factors.trace_names),trace_ground=list(factors.trace_ground),
        labels=list(factors.labels),surface_current_factors_per_m=factors.parts.tolist(),
        step_factors_per_m=factors.step_parts.tolist(),diagnostics=dict(factors.diagnostics),
        samples=[_sample_record(s) for s in factors.samples],
        whole_current=shape_current_record(factors.base,settings))


class ShapeFacePanelLineError(ValueError):
    """Staged face-line failure, retaining completed and partial current work."""
    def __init__(self,cause,*,stage,input_json,factors,settings):
        super().__init__(str(cause));self.stage=stage;self.cause_type=type(cause).__name__
        self.input_json=input_json;self.current_factors=factors
        current=None if factors is None else shape_face_current_record(factors,settings)
        partial=None
        if isinstance(cause,(PanelShapeCurrentError,PanelShapeFaceCurrentError)):
            partial=dict(kind='faces' if isinstance(cause,PanelShapeFaceCurrentError) else 'whole',
                cause_type=type(cause.__cause__).__name__ if cause.__cause__ is not None else type(cause).__name__,
                samples=[_sample_record(s) for s in cause.samples],
                failed_request=None if cause.request is None else dict(stage=cause.request.stage,request=cause.request.arguments()),
                step_factors_per_m=None if cause.step_parts is None else cause.step_parts.tolist())
            if isinstance(cause,PanelShapeFaceCurrentError):
                partial['whole_current']=shape_current_record(cause.base,settings)
            else:
                partial['boundary_step_factors_per_m']=(None if cause.boundary_step_parts is None
                    else cause.boundary_step_parts.tolist())
        self._record=json.dumps(dict(type=type(self).__name__,message=str(self),stage=stage,cause_type=self.cause_type,
            input=json.loads(input_json),current_solver=current,partial_current=partial),allow_nan=False)

    def to_dict(self):return json.loads(self._record)


@dataclass(frozen=True)
class ShapeFacePanelTransmissionLineResult(TransmissionLineResult):
    """Matched RLGC and retained face/whole current records on the same basis."""
    current_factors: PanelShapeFaceCurrentFactors
    panel_settings: object

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self,'panel_settings',MappingProxyType(dict(self.panel_settings)))


class ShapeFacePanelTransmissionLineDocument:
    """Explicit SI input; open top/sides, finite rectangular/tapered traces, bottom ground.

    Each signal has four explicit bulk/rough or coated surface laws. The
    bottom plane and whole/face grounded traces are explicit. All local
    metal/core and shape-offset admission precedes fields.
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
                   'ground_thickness_m','length_m','reference_ohms','panel','step_fraction'),where='face shape line')
        if data['schema']!=_SCHEMA:raise ValueError('unsupported shape-face-panel-transmission-line schema')
        cross=CrossSectionDocument.from_dict(data['cross_section']);section=cross.section
        if not isinstance(data['materials'],dict):raise ValueError('materials must be an object')
        materials={name:dielectric_from_dict(value) for name,value in data['materials'].items()}
        f,_=_material_samples(section,data['frequency_hz'],materials)
        conductors,reference,records,ref_record=_metals(data)
        thickness=_scalar('ground_thickness_m',data['ground_thickness_m'])
        _shape_face_samples(section,f,conductors,reference,thickness)
        _keys(data['panel'],('panels_per_edge','ground_modes','interpolation_degree'),where='panel controls')
        _prepare_faces(section,step_fraction=data['step_fraction'],**data['panel'])
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
            _shape_face_samples(section,f,conductors,reference,data['ground_thickness_m'])
            stage='current'
            loss=panel_shape_conductor_loss_by_face(section,f,conductors=conductors,
                reference=reference,ground_thickness=data['ground_thickness_m'],**options)
            factors=loss.factors
            stage='mesh';meshed=section.mesh(**cross.mesh_options)
            if tuple(meshed.signals)!=factors.names:raise ValueError('dielectric mesh changed shape-current signal order')
            stage='dielectric';dielectric=_dispersive_from_mesh(meshed,f,samples,c0=factors.C0)
            stage='network'
            network=rlgc_network(f,R=loss.R,L=dielectric.L+loss.L_internal,G=dielectric.G,C=dielectric.C,
                length=data['length_m'],z_ref=data['reference_ohms'],names=dielectric.names)
            return ShapeFacePanelTransmissionLineResult(dielectric,loss,network,self.dumps(),cross.mesh_options,factors,options)
        except Exception as exc:
            raise ShapeFacePanelLineError(exc,stage=stage,input_json=self.dumps(),factors=factors,settings=options) from exc
