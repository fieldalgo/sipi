# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict nested startup inputs and explicit real port-wave references."""
import json

import numpy as np

from .document import _keys, _unique_object
from .sampling import _copy, _integer
from .network import _real
from .startup_document import LosslessStartupDocument
from .rlgc_startup_document import RLGCLadderDocument
from .coupled_startup_document import CoupledRLGCLadderDocument
from .coupled_boundary_startup_document import MixedBoundaryRLGCLadderDocument
from .coupled_capacitive_startup_document import CapacitiveRLGCLadderDocument
from .coupled_reactive_startup_document import ReactiveRLGCLadderDocument
from .startup_waves import StartupPortWaves, startup_port_waves
from .norton_startup_document import NortonReactiveRLGCLadderDocument
from .mixed_startup_document import MixedSourceRLGCLadderDocument
from .debye_startup_document import DebyeRLGCLadderDocument
from .coupled_debye_startup_document import CoupledDebyeRLGCLadderDocument
from .psd_debye_startup_document import PSDCoupledDebyeRLGCLadderDocument
from .debye_capacitive_startup_document import DebyeCapacitiveLadderDocument
from .debye_reactive_startup_document import DebyeReactiveLadderDocument
from .multiconductor_startup_document import MulticonductorRLGCLadderDocument
from .multiconductor_debye_startup_document import MulticonductorDebyeRLGCLadderDocument
from .psd_multiconductor_debye_startup_document import PSDMulticonductorDebyeRLGCLadderDocument
from .multiconductor_debye_capacitive_startup_document import MulticonductorDebyeCapacitiveLadderDocument
from .multiconductor_debye_reactive_startup_document import MulticonductorDebyeReactiveLadderDocument
from .multiconductor_debye_norton_startup_document import NortonMulticonductorDebyeReactiveLadderDocument
from .multiconductor_debye_mixed_startup_document import MixedSourceMulticonductorDebyeReactiveLadderDocument

__all__ = ['StartupPortWavesDocument']

_SCHEMAS = {f'sipi.startup-port-waves/{v}': v for v in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15)}
_STARTUPS = {
    'sipi.lossless-startup/1': LosslessStartupDocument,
    'sipi.rlgc-startup/1': RLGCLadderDocument,
    'sipi.coupled-rlgc-startup/1': CoupledRLGCLadderDocument,
    'sipi.coupled-rlgc-startup/2': MixedBoundaryRLGCLadderDocument,
    'sipi.coupled-rlgc-startup/3': CapacitiveRLGCLadderDocument,
    'sipi.coupled-rlgc-startup/4': ReactiveRLGCLadderDocument,
}

_STARTUPS_V2 = {**_STARTUPS, 'sipi.norton-rlgc-startup/1': NortonReactiveRLGCLadderDocument}
_STARTUPS_V3 = {**_STARTUPS_V2, 'sipi.mixed-rlgc-startup/1': MixedSourceRLGCLadderDocument}
_STARTUPS_V4 = {**_STARTUPS_V3, 'sipi.debye-rlgc-startup/1': DebyeRLGCLadderDocument}
_STARTUPS_V5 = {**_STARTUPS_V4, 'sipi.coupled-debye-rlgc-startup/1': CoupledDebyeRLGCLadderDocument}
_STARTUPS_V6 = {**_STARTUPS_V5, 'sipi.psd-coupled-debye-rlgc-startup/1': PSDCoupledDebyeRLGCLadderDocument}
_STARTUPS_V7 = {**_STARTUPS_V6, 'sipi.debye-capacitive-startup/1': DebyeCapacitiveLadderDocument}
_STARTUPS_V8 = {**_STARTUPS_V7, 'sipi.debye-reactive-startup/1': DebyeReactiveLadderDocument}
_STARTUPS_V9 = {**_STARTUPS_V8, 'sipi.multiconductor-rlgc-startup/1': MulticonductorRLGCLadderDocument}
_STARTUPS_V10 = {**_STARTUPS_V9, 'sipi.multiconductor-debye-rlgc-startup/1': MulticonductorDebyeRLGCLadderDocument}
_STARTUPS_V11 = {**_STARTUPS_V10, 'sipi.psd-multiconductor-debye-rlgc-startup/1': PSDMulticonductorDebyeRLGCLadderDocument}
_STARTUPS_V12 = {**_STARTUPS_V11, 'sipi.multiconductor-debye-capacitive-startup/1': MulticonductorDebyeCapacitiveLadderDocument}
_STARTUPS_V13 = {**_STARTUPS_V12, 'sipi.multiconductor-debye-reactive-startup/1': MulticonductorDebyeReactiveLadderDocument}
_STARTUPS_V14 = {**_STARTUPS_V13, 'sipi.multiconductor-debye-norton-startup/1': NortonMulticonductorDebyeReactiveLadderDocument}
_STARTUPS_V15 = {**_STARTUPS_V14, 'sipi.multiconductor-debye-mixed-startup/1': MixedSourceMulticonductorDebyeReactiveLadderDocument}
_BY_VERSION = {1: _STARTUPS, 2: _STARTUPS_V2, 3: _STARTUPS_V3, 4: _STARTUPS_V4, 5: _STARTUPS_V5, 6: _STARTUPS_V6, 7: _STARTUPS_V7, 8: _STARTUPS_V8, 9: _STARTUPS_V9, 10: _STARTUPS_V10, 11: _STARTUPS_V11, 12: _STARTUPS_V12, 13: _STARTUPS_V13, 14: _STARTUPS_V14, 15: _STARTUPS_V15}


def _startup(data, *, version=1):
    if not isinstance(data, dict) or not isinstance(data.get('schema'), str):
        raise ValueError('startup must be a supported saved startup object')
    cls = _BY_VERSION[version].get(data['schema'])
    if cls is None:
        raise ValueError('unsupported nested startup schema')
    return cls.from_dict(data)


class StartupPortWavesDocument:
    """Preserve a supported startup document and one real reference per port.

    The caller's budget retains its underlying meaning: actual forward delay
    terms for lossless startup, actual time rows for finite RLGC startup.
    Nested parsing validates without propagation; no recursive wave documents.
    Default version1 retains its six original voltage-driven schemas. Explicit
    version2 also permits Norton current inputs; version3 adds typed mixed sources.
    Explicit version4 additionally permits scalar Debye startup inputs.
    Explicit version5 additionally permits coupled Debye startup inputs.
    Explicit version6 additionally permits PSD coupled Debye startup inputs.
    Explicit version7 additionally permits external capacitive Debye inputs.
    Explicit version8 additionally permits external series RL Debye inputs.
    Explicit version9 additionally permits three/four-signal constant RLGC
    inputs with six/eight real port references, determined by explicit signals.
    Explicit version10 additionally permits three/four-signal positive-strength
    Debye inputs with the same explicit six/eight reference requirement.
    Explicit version11 additionally permits three/four-signal PSD Debye
    inputs, preserving singular matrices and their canonical null directions.
    Explicit version12 additionally permits three/four-signal PSD Debye
    inputs with external capacitive load storage and current.
    Explicit version13 additionally permits three/four-signal PSD Debye
    inputs with external capacitance and series RL branch storage/current.
    Explicit version14 additionally permits three/four-signal PSD Debye
    Norton current inputs with source shunts and external C/series RL loads.
    Explicit version15 additionally permits three/four-signal PSD Debye
    typed voltage/current inputs with external C/series RL loads.
    No nested version is upgraded.
    """
    def __init__(self, startup, *, z_ref, version=1):
        version = _integer(version, 1, 15)
        registry = _BY_VERSION[version]
        if not isinstance(startup, tuple(registry.values())):
            raise ValueError('startup must be a supported startup document')
        self._assign(startup.to_dict(), z_ref, version=version)

    def _assign(self, startup, z_ref, *, version):
        doc = _startup(startup, version=version)
        if isinstance(doc, (MulticonductorRLGCLadderDocument, MulticonductorDebyeRLGCLadderDocument, PSDMulticonductorDebyeRLGCLadderDocument, MulticonductorDebyeCapacitiveLadderDocument, MulticonductorDebyeReactiveLadderDocument, NortonMulticonductorDebyeReactiveLadderDocument, MixedSourceMulticonductorDebyeReactiveLadderDocument)):
            ports = 2*doc.to_dict()['signals']
        else:
            ports = 2 if isinstance(doc, (LosslessStartupDocument, RLGCLadderDocument, DebyeRLGCLadderDocument)) else 4
        z = _real('z_ref', z_ref)
        if z.shape != (ports,) or np.any(z <= 0):
            raise ValueError('z_ref needs one explicit positive real value per startup port')
        self._data = dict(schema=f'sipi.startup-port-waves/{version}', startup=doc.to_dict(), z_ref_ohm=z.tolist())

    @classmethod
    def from_dict(cls, data):
        data = _copy(data)
        _keys(data, ('schema', 'startup', 'z_ref_ohm'), where='startup port waves')
        if not isinstance(data['schema'], str) or data['schema'] not in _SCHEMAS:
            raise ValueError('unsupported startup-port-waves schema')
        out = cls.__new__(cls)
        out._assign(data['startup'], data['z_ref_ohm'], version=_SCHEMAS[data['schema']])
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
        response = _startup(data['startup'], version=_SCHEMAS[data['schema']]).analyze(max_evaluations=max_evaluations)
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
