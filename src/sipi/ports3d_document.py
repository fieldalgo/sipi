# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict explicit-mesh local TEM-port Maxwell input, independent of transport."""
from __future__ import annotations

import json

from galerkin.mesh3d import Mesh3D

from .document import _unique_object
from .capacitance3d_document import _keys, _real, _indices
from .ports3d import TEMPort3D, _prepare_tem_inputs, solve_tem_ports_3d

__all__ = ['TEMPorts3DDocument']


class TEMPorts3DDocument:
    """Detached sipi.tem-ports-3d/1 mesh, two annular ports and uniform material.

    Normalization checks geometry and topology without a port/volume field
    solve. Local TEM-admittance ports and PEC remaining walls are explicit;
    the schema does not imply a full multimode or radiation boundary.
    """

    def __init__(self, mesh, *, ports, frequency, eps_r=1.):
        mesh, relative, frequencies, ports, prepared, _ = _prepare_tem_inputs(
            mesh, ports, frequency, eps_r)
        self._data = dict(schema='sipi.tem-ports-3d/1', length_unit='m',
            unprescribed_boundary='pec', port_boundary='local-tem-admittance',
            mesh=dict(nodes=mesh.nodes.tolist(), tetrahedra=mesh.tets.tolist()),
            eps_r=relative, frequency_hz=frequencies.tolist(),
            ports=[dict(name=p.name, faces=d[0].tolist(), signal=d[2].tolist(), ground=d[3].tolist())
                   for p, d in zip(ports, prepared)])

    @classmethod
    def from_dict(cls, data):
        _keys(data, ('schema', 'length_unit', 'unprescribed_boundary', 'port_boundary',
                     'mesh', 'eps_r', 'frequency_hz', 'ports'), '3D TEM ports')
        if (data['schema'] != 'sipi.tem-ports-3d/1' or data['length_unit'] != 'm'
                or data['unprescribed_boundary'] != 'pec'
                or data['port_boundary'] != 'local-tem-admittance'):
            raise ValueError('unsupported 3D TEM schema, units or boundary model')
        _keys(data['mesh'], ('nodes', 'tetrahedra'), 'mesh')
        nodes, tets = data['mesh']['nodes'], data['mesh']['tetrahedra']
        if (not isinstance(nodes, list) or len(nodes) < 4
                or any(not isinstance(row, list) or len(row) != 3 for row in nodes)):
            raise ValueError('mesh nodes must have shape (N, 3), N >= 4')
        nodes = [[_real(x) for x in row] for row in nodes]
        if (not isinstance(tets, list) or not tets
                or any(not isinstance(row, list) or len(row) != 4 for row in tets)):
            raise ValueError('tetrahedra must have nonempty shape (T, 4)')
        tets = [_indices(row, len(nodes)) for row in tets]
        frequency = data['frequency_hz']
        if not isinstance(frequency, list) or not frequency:
            raise ValueError('frequency_hz must be a nonempty list')
        frequency = [_real(x) for x in frequency]
        rows = data['ports']
        if not isinstance(rows, list) or len(rows) != 2:
            raise ValueError('ports must be an ordered list of exactly two ports')
        ports = []
        for row in rows:
            _keys(row, ('name', 'faces', 'signal', 'ground'), 'port')
            faces = row['faces']
            if (not isinstance(faces, list) or not faces
                    or any(not isinstance(face, list) or len(face) != 3 for face in faces)):
                raise ValueError('port faces must have nonempty shape (F, 3)')
            ports.append(TEMPort3D(row['name'], [_indices(face, len(nodes)) for face in faces],
                _indices(row['signal'], len(nodes)), _indices(row['ground'], len(nodes))))
        return cls(Mesh3D(nodes, tets), ports=ports, frequency=frequency, eps_r=_real(data['eps_r']))

    @classmethod
    def loads(cls, text):
        if not isinstance(text, str):
            raise TypeError('saved input must be JSON text')
        def reject(value):
            raise ValueError(f'nonfinite JSON number: {value}')
        return cls.from_dict(json.loads(text, object_pairs_hook=_unique_object,
            parse_constant=reject, parse_float=lambda value: _real(float(value))))

    def dumps(self):
        return json.dumps(self._data, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)

    def to_dict(self):
        return json.loads(self.dumps())

    def analyze(self):
        data = self._data
        return solve_tem_ports_3d(Mesh3D(data['mesh']['nodes'], data['mesh']['tetrahedra']),
            ports=[TEMPort3D(**row) for row in data['ports']],
            frequency=data['frequency_hz'], eps_r=data['eps_r'])
