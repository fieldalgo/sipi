# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Real-reference incident/reflected power waves from explicit startup samples."""
from dataclasses import dataclass

import numpy as np

from .network import _real
from .startup import LosslessLineResponse, _times
from .rlgc_startup import RLGCLadderResponse
from .norton_startup import NortonReactiveRLGCLadderResponse
from .mixed_startup import MixedSourceRLGCLadderResponse
from .debye_startup import DebyeRLGCLadderResponse
from .coupled_debye_startup import CoupledDebyeRLGCLadderResponse
from .psd_debye_startup import PSDCoupledDebyeRLGCLadderResponse
from .debye_capacitive_startup import DebyeCapacitiveLadderResponse
from .debye_reactive_startup import DebyeReactiveLadderResponse
from .multiconductor_startup import MulticonductorRLGCLadderResponse
from .multiconductor_boundary_startup import MixedBoundaryMulticonductorRLGCLadderResponse
from .multiconductor_debye_startup import MulticonductorDebyeRLGCLadderResponse
from .psd_multiconductor_debye_startup import PSDMulticonductorDebyeRLGCLadderResponse
from .multiconductor_debye_capacitive_startup import MulticonductorDebyeCapacitiveLadderResponse
from .multiconductor_debye_reactive_startup import MulticonductorDebyeReactiveLadderResponse
from .multiconductor_debye_norton_startup import NortonMulticonductorDebyeReactiveLadderResponse
from .multiconductor_debye_mixed_startup import MixedSourceMulticonductorDebyeReactiveLadderResponse

__all__ = ['StartupPortWaves', 'startup_port_waves']


def _relative_columns(error, scale):
    numerator = np.max(abs(error), axis=0)
    denominator = np.max(abs(scale), axis=0)
    values = np.zeros_like(numerator)
    nonzero = denominator > 0
    values[nonzero] = numerator[nonzero]/denominator[nonzero]
    values[~nonzero] = np.where(numerator[~nonzero] == 0, 0., np.inf)
    return float(np.max(values))


@dataclass(frozen=True)
class StartupPortWaves:
    """Copied read-only real power waves [sqrt(W)], with currents into the line.

    Positive real port references are explicit, constant in time, single-ended
    and diagonal. They are not inferred characteristic/modal impedances.
    """
    time: np.ndarray
    voltage: np.ndarray
    current: np.ndarray
    z_ref: np.ndarray
    incident: np.ndarray
    reflected: np.ndarray
    port_power: np.ndarray
    port_names: tuple[str, ...]
    source_kind: str
    voltage_reconstruction_relative_error: float
    current_reconstruction_relative_error: float
    power_balance_relative_error: float

    def __post_init__(self):
        for name in ('time', 'voltage', 'current', 'z_ref', 'incident', 'reflected', 'port_power'):
            value = np.array(getattr(self, name), dtype=float, copy=True)
            if not np.all(np.isfinite(value)):
                raise ValueError('startup wave output must remain finite')
            value.setflags(write=False)
            object.__setattr__(self, name, value)
        object.__setattr__(self, 'port_names', tuple(self.port_names))

    def to_dict(self):
        return dict(scope='explicit-real-reference-startup-port-waves',
            source_kind=self.source_kind, basis='single-ended',
            time_s=self.time.tolist(), port_names=list(self.port_names), z_ref_ohm=self.z_ref.tolist(),
            voltage_v=self.voltage.tolist(), current_into_line_a=self.current.tolist(),
            incident_sqrt_w=self.incident.tolist(), reflected_sqrt_w=self.reflected.tolist(),
            port_power_w=self.port_power.tolist(),
            voltage_reconstruction_relative_error=self.voltage_reconstruction_relative_error,
            current_reconstruction_relative_error=self.current_reconstruction_relative_error,
            power_balance_relative_error=self.power_balance_relative_error)


def startup_port_waves(response, *, z_ref):
    """Decompose qualified scalar through four-signal startup V/I at explicit real Zref.

    Accept LosslessLineResponse or RLGCLadderResponse (including its coupled,
    mixed and reactive subclasses), or NortonReactiveRLGCLadderResponse/MixedSourceRLGCLadderResponse,
    or explicit DebyeRLGCLadderResponse/CoupledDebyeRLGCLadderResponse,
    or PSDCoupledDebyeRLGCLadderResponse/DebyeCapacitiveLadderResponse/DebyeReactiveLadderResponse.
    MulticonductorRLGCLadderResponse, MulticonductorDebyeRLGCLadderResponse and
    PSDMulticonductorDebyeRLGCLadderResponse/MulticonductorDebyeCapacitiveLadderResponse
    and MulticonductorDebyeReactiveLadderResponse/NortonMulticonductorDebyeReactiveLadderResponse
    or MixedSourceMulticonductorDebyeReactiveLadderResponse/MixedBoundaryMulticonductorRLGCLadderResponse
    explicitly permit six/eight ports; all
    original types retain their two/four-port shapes.
    Terminal currents are distinct from injected currents or typed mixed drives;
    wave power is terminal V*I, excluding external source series/shunt losses.
    z_ref must be a vector of positive finite
    real ohms, one per port; no scalar broadcasting or complex references.
    Preserve the response's exact times, port order, voltage and into-line
    currents. No propagation, FFT, resampling or frequency/DC inference.

    a=(V/sqrt(Z)+I*sqrt(Z))/2 and b=(V/sqrt(Z)-I*sqrt(Z))/2 in sqrt(W).
    V/I reconstruction per port must pass relative1e-10, normalized by that
    port's maximum original V/I. Power a**2-b**2=V*I uses the maximum wave-power
    scale per port, not net power near cancellation. Zero signals stay zero;
    nonrepresentable arithmetic/cancellation is rejected, not clipped.

    These are real-reference port waves, not extracted line eigenmodes or a
    general TDR inversion. No b/a, V/I, delay alignment, gating or frequency-
    dependent impedance is inferred. Far-port incident/outgoing directions
    reverse the +z/-z traveling-wave convention of a lossless scalar line.
    """
    if not isinstance(response, (LosslessLineResponse, RLGCLadderResponse, NortonReactiveRLGCLadderResponse, MixedSourceRLGCLadderResponse, DebyeRLGCLadderResponse, CoupledDebyeRLGCLadderResponse, PSDCoupledDebyeRLGCLadderResponse, DebyeCapacitiveLadderResponse, DebyeReactiveLadderResponse, MulticonductorRLGCLadderResponse, MulticonductorDebyeRLGCLadderResponse, PSDMulticonductorDebyeRLGCLadderResponse, MulticonductorDebyeCapacitiveLadderResponse, MulticonductorDebyeReactiveLadderResponse, NortonMulticonductorDebyeReactiveLadderResponse, MixedSourceMulticonductorDebyeReactiveLadderResponse, MixedBoundaryMulticonductorRLGCLadderResponse)):
        raise ValueError('response must be a lossless or RLGC startup response')
    time = _times('time', response.time)
    voltage = _real('voltage', response.voltage); current = _real('current', response.current)
    names = tuple(response.port_names); ports = len(names)
    allowed_ports = (6, 8) if isinstance(response, (MulticonductorRLGCLadderResponse, MulticonductorDebyeRLGCLadderResponse, PSDMulticonductorDebyeRLGCLadderResponse, MulticonductorDebyeCapacitiveLadderResponse, MulticonductorDebyeReactiveLadderResponse, NortonMulticonductorDebyeReactiveLadderResponse, MixedSourceMulticonductorDebyeReactiveLadderResponse, MixedBoundaryMulticonductorRLGCLadderResponse)) else (2, 4)
    if (ports not in allowed_ports or len(set(names)) != ports
            or any(not isinstance(name, str) or not name for name in names)
            or voltage.shape != (len(time), ports) or current.shape != voltage.shape):
        raise ValueError('startup port names and voltage/current shapes must agree')
    z = _real('z_ref', z_ref)
    if z.shape != (ports,) or np.any(z <= 0):
        raise ValueError('z_ref needs one explicit positive real value per port')
    with np.errstate(over='ignore', invalid='ignore', divide='ignore', under='ignore'):
        root = np.sqrt(z)
        v = voltage/root; i = current*root
        incident = .5*v+.5*i; reflected = .5*v-.5*i
        recovered_v = root*(incident+reflected)
        recovered_i = (incident-reflected)/root
        power = voltage*current
        incident_power = incident**2; reflected_power = reflected**2
        wave_power = incident_power-reflected_power
        power_scale = np.maximum(incident_power+reflected_power, abs(power))
    arrays = (incident, reflected, recovered_v, recovered_i, power, wave_power, power_scale)
    if not all(np.all(np.isfinite(a)) for a in arrays):
        raise ValueError('startup wave arithmetic exceeds finite scales')
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        ve = _relative_columns(recovered_v-voltage, voltage)
        ie = _relative_columns(recovered_i-current, current)
        pe = _relative_columns(wave_power-power, power_scale)
    if not all(np.isfinite(e) and e <= 1e-10 for e in (ve, ie, pe)):
        raise ValueError('startup wave reconstruction or power balance exceeds relative 1e-10')
    return StartupPortWaves(time, voltage, current, z, incident, reflected, power, names,
        type(response).__name__, ve, ie, pe)
