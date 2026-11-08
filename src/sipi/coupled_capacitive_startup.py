# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Finite coupled RLGC startup with an explicit passive far-load capacitance."""
from dataclasses import dataclass

import numpy as np

from .coupled_startup import _passive_matrix
from .coupled_boundary_startup import MixedBoundaryRLGCLadderResponse, _coupled_boundary_response

__all__ = ['CapacitiveRLGCLadderResponse', 'coupled_capacitive_ladder_response']


@dataclass(frozen=True)
class CapacitiveRLGCLadderResponse(MixedBoundaryRLGCLadderResponse):
    """Internal line energy and separate external capacitor energy/current.

    Load capacitor current leaves the line into the external capacitor matrix.
    The inherited four port currents still enter the line. Capacitor energy
    and power are totals across both load terminals, including mutual terms.
    """
    load_capacitor_current: np.ndarray
    load_capacitor_energy: np.ndarray
    load_capacitor_power: np.ndarray
    total_power_balance_relative_error: float

    def __post_init__(self):
        super().__post_init__()
        for name in ('load_capacitor_current', 'load_capacitor_energy', 'load_capacitor_power'):
            value = np.array(getattr(self, name), dtype=float, copy=True)
            if not np.all(np.isfinite(value)):
                raise ValueError('load capacitor output must remain finite')
            value.setflags(write=False)
            object.__setattr__(self, name, value)
        if not np.all(np.isfinite(self.total_energy)):
            raise ValueError('total stored energy must remain finite')

    @property
    def total_energy(self):
        with np.errstate(over='ignore', invalid='ignore'):
            value = self.energy+self.load_capacitor_energy
        value.setflags(write=False)
        return value

    @property
    def total_energy_rate(self):
        value = self.energy_rate+self.load_capacitor_power
        value.setflags(write=False)
        return value

    def to_dict(self, *, include_states=False):
        out = super().to_dict(include_states=include_states)
        out.update(scope='finite-passive-two-signal-capacitive-load-rlgc-startup',
            load_capacitor_current_a=self.load_capacitor_current.tolist(),
            load_capacitor_energy_j=self.load_capacitor_energy.tolist(),
            load_capacitor_power_w=self.load_capacitor_power.tolist(),
            total_stored_energy_j=self.total_energy.tolist(),
            total_energy_rate_w=self.total_energy_rate.tolist(),
            total_power_balance_relative_error=self.total_power_balance_relative_error)
        return out


def coupled_capacitive_ladder_response(time, source_voltages, *, R, L, G, C,
                                      length, cells, source_resistance,
                                      load_resistance, load_capacitance):
    """Explicit far-load C[F] in parallel with mixed resistive terminations.

    load_capacitance is a finite real exactly symmetric PSD2x2 matrix in farads,
    distinct from the line C[F/m]. Zero/rank-one are allowed without negative
    eigenvalue repair. All line, grid and ideal/resistive/open/short controls
    follow coupled_boundary_ladder_response. Initially unenergized, constant
    passive finite circuit only; no arbitrary reactive/inductive/active load.

    Preserve internal line energy and separate external capacitor charge/power.
    Finite/open port currents include external capacitive current; a short's
    line-port current retains full internal endpoint C/G and segment flux.
    Resistive load loss uses V**2/R, not total capacitive port current squared.
    Both line and combined energy balances must pass relative1e-10. Cell/time/
    source convergence remains input-specific, not guaranteed by1..128cells.
    """
    cap = _passive_matrix('load_capacitance', load_capacitance)
    line, current, energy, power, error = _coupled_boundary_response(time, source_voltages,
        R=R, L=L, G=G, C=C, length=length, cells=cells,
        source_resistance=source_resistance, load_resistance=load_resistance,
        load_capacitance=cap)
    return CapacitiveRLGCLadderResponse(**line.__dict__, load_capacitor_current=current,
        load_capacitor_energy=energy, load_capacitor_power=power,
        total_power_balance_relative_error=error)
