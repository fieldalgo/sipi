# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Coupled startup with explicit parallel capacitance and a series RL branch."""
from dataclasses import dataclass

import numpy as np

from .coupled_startup import _passive_matrix
from .coupled_boundary_startup import _coupled_boundary_response
from .coupled_capacitive_startup import CapacitiveRLGCLadderResponse

__all__ = ['ReactiveRLGCLadderResponse', 'coupled_reactive_ladder_response']


def _branch_input(load_capacitance, load_branch_resistance, load_branch_inductance):
    cap = _passive_matrix('load_capacitance', load_capacitance)
    resistance = _passive_matrix('load_branch_resistance', load_branch_resistance)
    inductance = _passive_matrix('load_branch_inductance', load_branch_inductance)
    scale = np.max(abs(inductance))
    eigen = np.linalg.eigvalsh(inductance/scale) if scale else np.zeros(2)
    if eigen[0] <= 1e-12*eigen[-1]:
        raise ValueError('load_branch_inductance must be positive definite with eigenvalue ratio above 1e-12')
    return cap, resistance, inductance


@dataclass(frozen=True)
class ReactiveRLGCLadderResponse(CapacitiveRLGCLadderResponse):
    """Separate internal line, external capacitor and external RL branch terms.

    Branch current leaves the line toward the external series RL load. The
    inherited load_resistor_loss concerns only the parallel termination R;
    load_branch_resistor_loss is separate. All energies sum both conductors.
    """
    load_branch_current: np.ndarray
    load_branch_energy: np.ndarray
    load_branch_energy_rate: np.ndarray
    load_branch_resistor_loss: np.ndarray

    def __post_init__(self):
        super().__post_init__()
        for name in ('load_branch_current', 'load_branch_energy',
                     'load_branch_energy_rate', 'load_branch_resistor_loss'):
            value = np.array(getattr(self, name), dtype=float, copy=True)
            if not np.all(np.isfinite(value)):
                raise ValueError('load branch output must remain finite')
            value.setflags(write=False)
            object.__setattr__(self, name, value)
        if not np.all(np.isfinite(self.total_energy_rate)):
            raise ValueError('total energy rate must remain finite')

    @property
    def total_energy(self):
        with np.errstate(over='ignore', invalid='ignore'):
            value = self.energy+self.load_capacitor_energy+self.load_branch_energy
        value.setflags(write=False)
        return value

    @property
    def total_energy_rate(self):
        with np.errstate(over='ignore', invalid='ignore'):
            value = self.energy_rate+self.load_capacitor_power+self.load_branch_energy_rate
        value.setflags(write=False)
        return value

    def to_dict(self, *, include_states=False):
        out = super().to_dict(include_states=include_states)
        out.update(scope='finite-passive-two-signal-reactive-load-rlgc-startup',
            load_branch_current_a=self.load_branch_current.tolist(),
            load_branch_energy_j=self.load_branch_energy.tolist(),
            load_branch_energy_rate_w=self.load_branch_energy_rate.tolist(),
            load_branch_resistor_loss_w=self.load_branch_resistor_loss.tolist())
        return out


def coupled_reactive_ladder_response(time, source_voltages, *, R, L, G, C,
                                     length, cells, source_resistance,
                                     load_resistance, load_capacitance,
                                     load_branch_resistance, load_branch_inductance):
    """Initially unenergized constant two-signal line with a passive RL branch.

    Each external matrix is real finite exactly symmetric2x2. Cload[F] and
    Rbranch[ohm] are PSD; Lbranch[H] is SPD with eigenvalue ratio above1e-12.
    Zero/rank-one Cload/Rbranch are allowed without eigenvalue repair. Zero or
    singular Lbranch is rejected; no implicit missing branch is inferred.

    The series RL branch and capacitor are parallel to the existing per-port
    resistive/open/short loads. Lbranch*di/dt=Vfar-Rbranch*i, with zero initial
    current. Mixed boundary, explicit cells1..128, zero-first PWL drives and
    uniform2..10000 samples follow the capacitive API. Current into each line
    port includes full endpoint C/G flux, including prescribed short nodes.

    Internal line, external capacitor and branch energy/loss remain separate;
    both line and combined RHS power balances must pass relative1e-10.
    Finite circuit only, with input-specific spatial/source/time convergence;
    no arbitrary RLC topology, frequency dispersion or Maxwell time solver.
    """
    cap, rb, lb = _branch_input(load_capacitance, load_branch_resistance, load_branch_inductance)
    line, ci, ce, cp, error, bi, be, br, bl = _coupled_boundary_response(time, source_voltages,
        R=R, L=L, G=G, C=C, length=length, cells=cells,
        source_resistance=source_resistance, load_resistance=load_resistance,
        load_capacitance=cap, load_branch_resistance=rb, load_branch_inductance=lb)
    return ReactiveRLGCLadderResponse(**line.__dict__, load_capacitor_current=ci,
        load_capacitor_energy=ce, load_capacitor_power=cp,
        total_power_balance_relative_error=error, load_branch_current=bi,
        load_branch_energy=be, load_branch_energy_rate=br, load_branch_resistor_loss=bl)
