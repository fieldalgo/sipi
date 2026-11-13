# PSD Debye startup with external capacitive and series RL loads

`psd_coupled_debye_reactive_ladder_response` extends the explicit
[PSD Debye circuit](psd_debye_startup.md) with a parallel load capacitor and a
series RL branch in parallel with the two load resistances. It has a separate
`DebyeReactiveLadderResponse` type. Existing physical, saved and wave input
contracts remain unchanged.

Each external input is a required exactly symmetric real 2x2 matrix:
`load_capacitance` [F] and `load_branch_resistance` [ohm] are PSD, including
zero and rank-one; `load_branch_inductance` [H] is SPD with eigenvalue ratio
above1e-12. No absent branch, scalar broadcasting, eigenvalue repair or rank
clipping is inferred. A zero inductance is not an implicit resistive branch.

Original line contracts hold: R/G PSD; L/C_inf SPD with ratio above1e-12;
1–2 PSD Debye strengths in F/m and matching positive frequencies in Hz;
positive length,1–128 cells,2–10000 uniform time samples starting0 and
zero-first two-column PWL source voltages. Both source and parallel load
resistances remain two finite positive values; this API does not enable
ideal/open/short/current-source boundaries.

For branch current i leaving the line, Lb*di/dt=Vfar-Rb*i with zero initial
state. Current into the far line is -Vfar/Rload-Cload*dVfar/dt-i. Parallel
load resistor loss is sum(Vfar**2/Rload); branch loss i.T*Rb*i is separate.
Internal instantaneous and polarization energy form `line_energy`; external
C energy and branch L energy additionally enter `total_energy`. Their rate
properties follow the same partition. Branch energy=.5*i.T*Lb*i;
branch energy rate=i.T*Lb*di/dt; resistor loss is nonnegative, while storage
rates can change sign during discharge. Line and combined source power
balances must both pass relative1e-10. Finite, nonnegative storage/loss checks
reject unrepresentable values without clipping.

```python
import numpy as np
from sipi import psd_coupled_debye_reactive_ladder_response

time = np.linspace(0., 12e-9, 121)
r = psd_coupled_debye_reactive_ladder_response(time,
    np.minimum(time/2e-9, 1.)[:, None]*[1., -.4],
    R=[[20., 3.], [3., 20.]], L=np.array([[500., 100.], [100., 500.]])*1e-9,
    G=[[.002, -.0003], [-.0003, .002]], C_inf=np.array([[220., -40.], [-40., 220.]])*1e-12,
    delta_C=np.array([[[150., -150.], [-150., 150.]], [[50., 50.], [50., 50.]]])*1e-12,
    relaxation_hz=[1e9, 1e8], length=.1, cells=16,
    source_resistance=[25., 25.], load_resistance=[100., 100.],
    load_capacitance=np.array([[30., -5.], [-5., 30.]])*1e-12,
    load_branch_resistance=[[150., 20.], [20., 150.]],
    load_branch_inductance=np.array([[200., 30.], [30., 200.]])*1e-9)
np.testing.assert_allclose(r.line_power,
    r.line_energy_rate+r.series_loss+r.shunt_loss+r.relaxation_loss,
    rtol=1e-10, atol=1e-12)
np.testing.assert_allclose(r.source_power,
    r.total_energy_rate+r.series_loss+r.shunt_loss+r.relaxation_loss
    +r.source_resistor_loss+r.load_resistor_loss+r.load_branch_resistor_loss,
    rtol=1e-10, atol=1e-12)
assert r.load_branch_current.shape == (121, 2)
assert r.to_dict()['scope'] == 'finite-passive-two-signal-psd-debye-reactive-startup'
```

`load_branch_current` has shape(time,2); `load_branch_energy`,
`load_branch_energy_rate` and `load_branch_resistor_loss` have shape(time,).
These fields and capacitor diagnostics are copied/read-only and included in
ordinary JSON with explicit units. Internal node/segment/polarization arrays
require `include_states=True`. The independent response is not implicitly
admitted to existing terminal-wave or saved adapters.

Validation separates code agreement and convergence. Zero strengths recover
the existing constant reactive circuit. Explicit1e6 H diagonal branch
inductance approaches the capacitive circuit within1e-10 V/1e-12 A for the
stated finite12ns fixture; it does not remove the branch. A separately written
noncommuting charge-state KCL integration uses DOP853 with1e-8 V/1e-9 A gates.
Continuous scalar modal scikit-rf ABCD uses load admittance
1/R+j*omega*C+1/(Rb+j*omega*Lb). For the documented exchange fixture,
32/64/128-cell errors decrease at100MHz,500MHz and1GHz, with finest voltage
error below1mV. The100MHz case uses8cycles/1024samples per cycle; higher
frequencies use20cycles/256samples. At100MHz,256/512/1024 temporal refinement
improves agreement with the finite-pi frequency reference, and7/8/9-cycle
phasor differences remain below1e-8 V. These are fixture-specific bounds,
not automatic sampling or horizon rules.

PSD external matrices, strict branch inductance, pulse energy/loss partitions,
scaling/permutation/null directions, copies and original failures are checked.
Forty-eight existing strict-SPD/PSD/capacitive full physical/saved/wave outputs
preserve their JSON hashes. Existing NumPy/SciPy and test-only scikit-rf
versions and notices are reused; no new dependency. No geometry/material
extraction, arbitrary RLC topology, Maxwell time solver, measured accuracy or
browser/Windows integration is established.

[Capacitive API](debye_capacitive_startup.md) ·
[한국어](../../locales/ko/pages/packages/sipi/debye_reactive_startup.md)

[Saved external RL inputs](debye_reactive_startup_document.md) distinguish external ohm/H/F from per-length line inputs.

[Terminal waves](startup_waves.md) now explicitly accept this response while separating internal line and external C/L power. Saved wave v1–7 keep their original input kinds.

## State scales during propagation

The two-signal PSD Debye reactive solver propagates `x = S u`, with the diagonal
`S_ii = 1/sqrt(D_ii)`, then restores physical voltage/current states before
computing outputs and power diagnostics. Here `D` uses the circuit mass diagonal
for node voltages, segment currents
and external branch currents. Auxiliary polarization voltages use their
corresponding node-voltage scales instead of their algebraic identity mass.
This is an invertible change of coordinates, not a change to the branch, its inductance,
input units, time grid or material model. Unrepresentable transformed systems
are rejected; no states or eigenvalues are clipped. Other propagation entry
points retain their existing choice of state coordinates.

This prevents tiny branch currents from acquiring an absolute numerical floor
when the explicit branch inductance is large. With zero branch resistance,
`Lb I(t) = integral(Vfar dt)` and branch energy approaches a `1/Lb` limit as the
branch approaches an open circuit. Regression checks use 1e6, 1e7 and 1e8 H,
ramp/pulse drives and independent quadrature of the no-branch reference, with
separate time refinement. These extreme values probe numerical conditioning;
they are not suggested PCB component values. Existing energy, passivity, full
state and independent charge-equation acceptance gates remain unchanged.
