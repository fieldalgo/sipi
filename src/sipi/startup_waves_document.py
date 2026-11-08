# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict nested startup inputs and explicit real port-wave references."""
import json

import numpy as np

from .document import _keys, _unique_object
from .sampling import _copy
from .network import _real
from .startup_document import LosslessStartupDocument
from .rlgc_startup_document import RLGCLadderDocument
from .coupled_startup_document import CoupledRLGCLadderDocument
from .coupled_boundary_startup_document import MixedBoundaryRLGCLadderDocument
from .coupled_capacitive_startup_document import CapacitiveRLGCLadderDocument
from .coupled_reactive_startup_document import ReactiveRLGCLadderDocument
from .startup_waves import StartupPortWaves, startup_port_waves

__all__ = ['StartupPortWavesDocument']

_SCHEMA = 'sipi.startup-port-waves/1'
_STARTUPS = {
    'sipi.lossless-startup/1': LosslessStartupDocument,
    'sipi.rlgc-startup/1': RLGCLadderDocument,
    'sipi.coupled-rlgc-startup/1': CoupledRLGCLadderDocument,
    'sipi.coupled-rlgc-startup/2': MixedBoundaryRLGCLadderDocument,
    'sipi.coupled-rlgc-startup/3': CapacitiveRLGCLadderDocument,
    'sipi.coupled-rlgc-startup/4': ReactiveRLGCLadderDocument,
}


def _startup(data):
    if not isinstance(data, dict) or not isinstance(data.get('schema'), str):
        raise ValueError('startup must be a supported saved startup object')
    cls = _STARTUPS.get(data['schema'])
    if cls is None:
        raise ValueError('unsupported nested startup schema')
    return cls.from_dict(data)


class StartupPortWavesDocument:
    """Preserve a supported startup document and one real reference per port.

    The caller's budget retains its underlying meaning: actual forward delay
    terms for lossless startup, actual time rows for finite RLGC startup.
    Nested parsing validates without propagation; no recursive wave documents.
    """
    def __init__(self, startup, *, z_ref):
        if not isinstance(startup, tuple(_STARTUPS.values())):
            raise ValueError('startup must be a supported startup document')
        self._assign(startup.to_dict(), z_ref)

    def _assign(self, startup, z_ref):
        doc = _startup(startup)
        ports = 2 if isinstance(doc, (LosslessStartupDocument, RLGCLadderDocument)) else 4
        z = _real('z_ref', z_ref)
        if z.shape != (ports,) or np.any(z <= 0):
            raise ValueError('z_ref needs one explicit positive real value per startup port')
        self._data = dict(schema=_SCHEMA, startup=doc.to_dict(), z_ref_ohm=z.tolist())

    @classmethod
    def from_dict(cls, data):
        data = _copy(data)
        _keys(data, ('schema', 'startup', 'z_ref_ohm'), where='startup port waves')
        if data['schema'] != _SCHEMA:
            raise ValueError('unsupported startup-port-waves schema')
        out = cls.__new__(cls)
        out._assign(data['startup'], data['z_ref_ohm'])
        return out

    @classmethod
    def loads(cls, text):
        def reject(value):
            raise ValueError(f'nonfinite JSON number: {value}')
        return cls.from_dict(json.loads(text, object_pairs_hook=_unique_object, parse_constant=reject))

    def dumps(self):
        return json.dumps(self._data, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)

    def to_dict(self):
        return json.loads(self.dumps())

    def analyze(self, *, max_evaluations=128):
        data = self.to_dict()
        response = _startup(data['startup']).analyze(max_evaluations=max_evaluations)
        result = startup_port_waves(response, z_ref=data['z_ref_ohm'])
        shape = response.voltage.shape
        if (not isinstance(result, StartupPortWaves)
                or not np.array_equal(result.time, response.time)
                or not np.array_equal(result.voltage, response.voltage)
                or not np.array_equal(result.current, response.current)
                or not np.array_equal(result.z_ref, data['z_ref_ohm'])
                or result.port_names != response.port_names
                or result.source_kind != type(response).__name__
                or result.incident.shape != shape or result.reflected.shape != shape
                or result.port_power.shape != shape):
            raise ValueError('port-wave analysis changed saved response or reference identity')
        return result
