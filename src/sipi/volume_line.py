# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Matched finite-metal and finite-dielectric-box RLGC, with reproducible JSON.

The electric exterior has zero normal D; the magnetic exterior fixes Az=0.
Both use the same physical metal surfaces. Domain convergence remains required.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
from galerkin import Mesh

from .conductor_diffusion import ConductorDiffusion, _indices, _snapshot
from .conductor_mesh import MeshedConductors, mesh_conductor_section
from .dielectric import ConstantDielectric, dielectric_from_dict, dielectric_to_dict
from .document import CrossSectionDocument, _keys, _unique_object
from .network import LineNetwork, _frequencies, _scalar
from .quasistatic import capacitance_matrix

__all__ = ['VolumeLineDocument', 'VolumeLineResult', 'volume_line', 'dielectric_view']


def dielectric_view(volume):
    """Remove metal triangles and compact nodes, preserving exact metal surfaces.

    Return (mesh, signal nodes, reference nodes, original nonmetal triangle ids).
    Exterior nodes have no imposed electric potential. They retain the natural
    zero-normal-D condition of capacitance_matrix.
    """
    if not isinstance(volume,MeshedConductors):
        raise TypeError('volume must be MeshedConductors')
    mesh = volume.mesh
    groups = [*volume.signals.values(),volume.ground]
    metal = np.zeros(mesh.num_triangles,dtype=bool)
    for ids in groups:
        ids = _indices('metal',ids,mesh.num_triangles)
        if np.any(metal[ids]):
            raise ValueError('metal groups must not overlap')
        metal[ids] = True
    nonmetal = np.flatnonzero(~metal)
    if not len(nonmetal):
        raise ValueError('a dielectric region is required')
    used = np.unique(mesh.triangles[nonmetal])
    renumber = np.full(mesh.num_nodes,-1,dtype=int)
    renumber[used] = np.arange(len(used))
    def boundary(ids):
        nodes = np.unique(mesh.triangles[ids])
        return renumber[nodes[renumber[nodes] >= 0]]
    signals = {name:boundary(ids) for name,ids in volume.signals.items()}
    ground = boundary(volume.ground)
    regions = None if mesh.regions is None else mesh.regions[nonmetal]
    electric = Mesh(mesh.nodes[used].copy(),renumber[mesh.triangles[nonmetal]],{},
                    regions=regions,region_names=mesh.region_names)
    return electric,signals,ground,nonmetal


@dataclass(frozen=True)
class VolumeLineResult:
    """Series R/total L plus matched C/G; all matrices use signal order."""
    conductor: ConductorDiffusion
    C_complex: np.ndarray
    network: LineNetwork
    input_json: str | None = None

    def __post_init__(self):
        c = np.asarray(self.C_complex,dtype=complex)
        if c.shape != self.conductor.Z.shape or not np.all(np.isfinite(c)):
            raise ValueError('complex capacitance shape or values are invalid')
        object.__setattr__(self,'C_complex',_snapshot(c))

    @property
    def frequency(self):
        return self.conductor.frequency

    @property
    def names(self):
        return self.conductor.names

    @property
    def R(self):
        return self.conductor.R

    @property
    def L(self):
        return self.conductor.L

    @property
    def C(self):
        return self.C_complex.real

    @property
    def G(self):
        return -2*np.pi*self.frequency[:,None,None]*self.C_complex.imag

    def propagation(self):
        """Report existing RLGC for positive-frequency single/symmetric modes.

        DC and asymmetric pairs require different analysis and are rejected.
        """
        from .propagation import rlgc_propagation
        return rlgc_propagation(self.frequency,R=self.R,L=self.L,G=self.G,C=self.C)

    def characteristic(self):
        """Full conductor-coordinate forward-wave matrices; no new field solve."""
        from .characteristic import rlgc_characteristic
        return rlgc_characteristic(self.frequency,R=self.R,L=self.L,G=self.G,C=self.C,names=self.names)

    def modes(self):
        """Distinct tracked forward modes and power losses; no new field solve."""
        from .modes import rlgc_modes
        return rlgc_modes(self.frequency,R=self.R,L=self.L,G=self.G,C=self.C,names=self.names)


def _material_samples(frequency,materials,names):
    if not isinstance(materials,Mapping) or set(materials) != set(names):
        raise ValueError('materials must specify every dielectric layer exactly once')
    samples = {}
    for name,model in materials.items():
        dielectric_to_dict(model)
        values = model.permittivity(frequency)
        if not np.all(np.isfinite(values)):
            raise ValueError('dielectric samples must be finite')
        samples[name] = values
    return samples


def volume_line(volume,frequency,*,materials,conductivity,length,z_ref=50.0,
                relative_permeability=1.0,keep_fields=False):
    """Extract matched RLGC on one metal/layer conforming volume mesh.

    volume must carry layer_triangles, from dielectric_interfaces=True or an
    explicit mesh-level construction. Every nonmetal triangle absent from this
    mapping is vacuum. materials must include exactly every mapped layer.
    Conductivity on the full volume mesh and uniform permeability follow
    conductor_impedance limits. Saved v1 documents retain scalar conductivity.
    """
    if not isinstance(volume,MeshedConductors) or volume.layer_triangles is None:
        raise ValueError('volume must resolve and identify dielectric interfaces')
    f = _frequencies(frequency)
    length,z_ref = _scalar('length',length,zero=True),_scalar('z_ref',z_ref)
    samples = _material_samples(f,materials,volume.layer_triangles)
    mesh,signals,ground,nonmetal = dielectric_view(volume)
    layer_ids = {}
    seen = np.zeros(volume.mesh.num_triangles,dtype=bool)
    for name,indices in volume.layer_triangles.items():
        if np.asarray(indices).size == 0:
            layer_ids[name] = np.array([],dtype=int)
            continue
        ids = _indices(name,indices,volume.mesh.num_triangles)
        if np.any(seen[ids]) or not np.all(np.isin(ids,nonmetal)):
            raise ValueError('dielectric layers must be disjoint and outside metal')
        seen[ids] = True
        layer_ids[name] = ids
    # This call retains all volume solver skin-resolution and conservation gates.
    series = volume.impedance(f,conductivity=conductivity,
        relative_permeability=relative_permeability,keep_fields=keep_fields)
    complex_c = []
    tensor = any(value.ndim == 3 for value in samples.values())
    for index in range(len(f)):
        eps = (np.tile(np.eye(2,dtype=complex),(volume.mesh.num_triangles,1,1))
               if tensor else np.ones(volume.mesh.num_triangles,dtype=complex))
        for name,ids in layer_ids.items():
            value = samples[name][index]
            eps[ids] = value*np.eye(2) if tensor and samples[name].ndim == 1 else value
        complex_c.append(capacitance_matrix(mesh,eps[nonmetal],signals,ground))
    complex_c = np.asarray(complex_c)
    conductance = -2*np.pi*f[:,None,None]*complex_c.imag
    network = series.network(C=complex_c.real,G=conductance,length=length,z_ref=z_ref)
    return VolumeLineResult(series,complex_c,network)


_MESH_KEYS = ('ground_thickness','padding','metal_size','far_size','grade','min_angle')


class VolumeLineDocument:
    """Strict saved volume line: scalar v1 or named conductor conductivity v2.

    The cross-section document must have empty dielectric-only mesh options;
    all volume mesh settings are explicit here. Accessors return fresh inputs.
    """
    def __init__(self,cross_section,frequency,*,materials,mesh,conductivity,length,
                 relative_permeability=1.0,z_ref=50.0):
        if not isinstance(cross_section,CrossSectionDocument):
            raise TypeError('cross_section must be CrossSectionDocument')
        if not isinstance(materials,Mapping):
            raise ValueError('materials must map layer names to dielectric models')
        schema = 'sipi.volume-line/2' if isinstance(conductivity,Mapping) else 'sipi.volume-line/1'
        self._data = self._validate(dict(schema=schema,
            cross_section=cross_section.to_dict(),frequency_hz=_frequencies(frequency).tolist(),
            materials={name:dielectric_to_dict(model) for name,model in materials.items()},
            mesh=mesh,conductor=dict(conductivity=conductivity,relative_permeability=relative_permeability),
            length_m=length,reference_ohms=z_ref))

    @staticmethod
    def _validate(data):
        _keys(data,('schema','cross_section','frequency_hz','materials','mesh','conductor',
                    'length_m','reference_ohms'),where='volume line')
        if data['schema'] not in ('sipi.volume-line/1','sipi.volume-line/2'):
            raise ValueError('unsupported volume-line schema')
        doc = CrossSectionDocument.from_dict(data['cross_section'])
        if doc.mesh_options:
            raise ValueError('cross_section mesh must be empty; use explicit volume mesh settings')
        if any(trace.thickness <= 0 for trace in doc.section.traces):
            raise ValueError('volume line requires finite-thickness traces')
        _keys(data['mesh'],_MESH_KEYS,where='volume mesh')
        mesh = {key:_scalar(key,data['mesh'][key],zero=key == 'grade') for key in _MESH_KEYS}
        if mesh['far_size'] < mesh['metal_size'] or mesh['min_angle'] >= 34:
            raise ValueError('need far_size >= metal_size and 0 < min_angle < 34')
        _keys(data['conductor'],('conductivity','relative_permeability'),where='conductor')
        if data['schema'] == 'sipi.volume-line/1':
            conductor = {key:_scalar(key,value) for key,value in data['conductor'].items()}
        else:
            sigma = data['conductor']['conductivity']
            _keys(sigma,('signals','ground'),where='named conductivity')
            names = [trace.name for trace in doc.section.traces if not trace.ground]
            _keys(sigma['signals'],names,where='signal conductivities')
            conductor = dict(conductivity=dict(
                signals={name:_scalar('signal conductivity',sigma['signals'][name]) for name in names},
                ground=_scalar('ground conductivity',sigma['ground'])),
                relative_permeability=_scalar('relative_permeability',data['conductor']['relative_permeability']))
        f = _frequencies(data['frequency_hz'])
        if not isinstance(data['materials'],dict):
            raise ValueError('materials must be an object')
        supplied = {name:dielectric_from_dict(value) for name,value in data['materials'].items()}
        layers = {layer.name:layer for layer in doc.section.materials}
        if not set(supplied) <= set(layers):
            raise ValueError('unknown dielectric layer')
        materials = {name:supplied.get(name,ConstantDielectric(layer.eps_r,layer.tan_delta))
                     for name,layer in layers.items()}
        _material_samples(f,materials,layers)
        return dict(schema=data['schema'],cross_section=doc.to_dict(),frequency_hz=f.tolist(),
            mesh=mesh,materials={name:dielectric_to_dict(model) for name,model in materials.items()},
            conductor=conductor,length_m=_scalar('length_m',data['length_m'],zero=True),
            reference_ohms=_scalar('reference_ohms',data['reference_ohms']))

    @classmethod
    def from_dict(cls,data):
        out = cls.__new__(cls)
        out._data = cls._validate(data)
        return out

    @classmethod
    def loads(cls,text):
        def reject(value):
            raise ValueError(f'nonfinite JSON number: {value}')
        return cls.from_dict(json.loads(text,object_pairs_hook=_unique_object,parse_constant=reject))

    def dumps(self):
        return json.dumps(self._data,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)

    def to_dict(self):
        return json.loads(self.dumps())

    @property
    def cross_section(self):
        return CrossSectionDocument.from_dict(self.to_dict()['cross_section'])

    def analyze(self,*,keep_fields=False):
        data = self.to_dict()
        if type(keep_fields) is not bool:
            raise ValueError('keep_fields must be boolean')
        section = CrossSectionDocument.from_dict(data['cross_section']).section
        volume = mesh_conductor_section(section,**data['mesh'],dielectric_interfaces=True)
        conductor = data['conductor']
        if data['schema'] == 'sipi.volume-line/2':
            named = conductor['conductivity']
            sigma = np.zeros(volume.mesh.num_triangles)
            for name,indices in volume.signals.items():
                sigma[indices] = named['signals'][name]
            sigma[volume.ground] = named['ground']
            conductor = dict(conductor,conductivity=sigma)
        result = volume_line(volume,data['frequency_hz'],
            materials={name:dielectric_from_dict(value) for name,value in data['materials'].items()},
            **conductor,length=data['length_m'],z_ref=data['reference_ohms'],
            keep_fields=keep_fields)
        return VolumeLineResult(result.conductor,result.C_complex,result.network,self.dumps())
