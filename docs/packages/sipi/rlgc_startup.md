# Finite passive RLGC startup circuit

`rlgc_ladder_response` propagates an initially unenergized, uniform scalar
RLGC **finite circuit** with explicit cells and piecewise-linear source samples.
It uses the existing SciPy state-space propagator. This is not an exact
continuous distributed-line solution or a Maxwell FDTD solver.

```python
import numpy as np
from sipi import rlgc_ladder_response

t = np.linspace(0., 12e-9, 1201)
r = rlgc_ladder_response(t, np.minimum(t/2e-9, 1.),
    R=20., L=500e-9, G=.002, C=200e-12, length=.1, cells=128,
    source_resistance=25., load_resistance=100.)
assert r.voltage.shape == (1201, 2)
assert r.node_voltage.shape == (1201, 129)
assert np.all(r.energy >= 0) and r.power_balance_relative_error <= 1e-10
assert not r.voltage.flags.writeable
assert 'node_voltage_v' not in r.to_dict()
assert 'node_voltage_v' in r.to_dict(include_states=True)
```

## Inputs and boundary conditions

Use SI scalars R [ohm/m] and G [S/m] >= 0, L [H/m], C [F/m] and length [m] > 0.
All must be finite real numbers; booleans are rejected. `cells` is explicitly
1..256, with no default or automatic accuracy claim. `time` has 2..10000 finite,
strictly increasing samples starting exactly at zero. Spacing must be uniform
within relative 1e-10 (zero absolute tolerance). `source_voltages` has the same
shape and starts exactly at zero. It is linear between samples and holds its
last value afterwards. Nonzero initial steps would require a capacitor impulse
at an ideal source and are not accepted by this model.

Source and load resistances are finite and nonnegative. Zero source resistance
means ideal voltage source; zero load means short; `None` load means open.
No infinite resistance, initial stored energy, frequency table, skin law,
coupled conductors or reactive/nonlinear external loads are inferred.

For dx=length/cells, each segment has series R*dx and L*dx; each node has
shunt G*dx and C*dx, with half values at both end nodes. Ideal-source and short
node voltages are prescribed and removed from the dynamic state. Their half
capacitor energy and leakage remain included. The ideal-source current includes
C_end*dV/dt + G_end*V in addition to the first segment current. At source knots,
the derivative uses the right PWL slope, with zero slope at the final sample.

## Results and energy checks

`voltage` and `current` are `(samples,2)` arrays in source/load order. Both port
currents enter the line, so delivered load power is minus load V*I.
`node_voltage` has cells+1 columns; `segment_current` has cells columns and
points from source to load. Arrays are copied/read-only; `inputs` is a detached
unit-labelled dictionary. `to_dict()` includes ports, input and energy/power
records; `include_states=True` also includes node/segment positions and states.
It is a result record, not a versioned saved-input schema.

Stored energy is sum(C_node*V**2 + L_segment*I**2)/2. `energy_rate` uses the
circuit right-hand side, not differences of sampled energies. `series_loss`,
`shunt_loss`, `line_power`, `source_power`, `source_resistor_loss` and
`load_resistor_loss` retain their physical signs; returned port power is not
clamped. The residual E_dot - line_power + series_loss + shunt_loss is divided
by the largest time-sample magnitude of E_dot, line_power or total internal
loss (zero for an exactly zero result). Relative residual above 1e-10, nonfinite
coefficients, states or diagnostics raise without a partial result.

That algebraic power check does not prove spatial or source/time convergence.
Check all three for each input, especially undamped reflections or sharp drives.
The cell/sample limits are not runtime, memory or accuracy guarantees.

## Independent criteria and scope

One-cell ideal-source RL/short and LC/open ramp responses match independent
closed forms, including half-end capacitance current and energy. Separate
DOP853 integration of the same 32-cell circuit differs from state-space
propagation by less than 1e-8 V; this compares propagation algorithms, not two
independent spatial discretizations. Time and impedance scaling, zero input,
open/short/matched ends, negative returned power and strict inputs are checked.

For L=500 nH/m, C=200 pF/m, length=.1 m, R=G=0, 0..2 ns ramp to 1 V and
1201 samples over 0..12 ns, the exact lossless delay solution is the independent
continuous-line reference. Rs=25 ohm/Rl=100 ohm errors at 32/64/128 cells are
.006821/.004185/.002662 V. Six resistive/ideal/open/short combinations must
meet .02 V and .0005 A at the finest tested grid, with decreasing errors.
**Ideal source/open load failed the .02 V criterion at 128 cells** (.022030 V).
Keeping that failed result and the same criterion, 256 cells gives .013921 V
and .000288 A. This is fixture-specific convergence, not blanket 256-cell accuracy.

For R=20 ohm/m, G=.002 S/m and otherwise the same line and Rs=25/Rl=100,
scikit-rf 2.2.0 distributed-line ABCD is the independent 500 MHz reference.
Use 20 sinusoidal cycles, 256 samples/cycle, and phasors over the final four
cycles excluding the duplicate endpoint. Complex port-voltage errors at
32/64/128 cells are .000803/.000205/.0000644 V, decreasing and below 1e-3 V
at 128; source interpolation error is included. Energy-rate residuals must
remain <=1e-10 and stored energy nonnegative for lossless and lossy cases.
SciPy 1.18.1 and scikit-rf 2.2.0 retain their existing BSD-3-Clause use; no new
runtime dependency is introduced and scikit-rf remains test-only.

Constant scalar RLGC do not model arbitrary material dispersion, skin effect,
multimode/coupled lines, general TDR inference, eye/BER, or measured-board
accuracy. Browser and Windows integration require separate validation.

[Exact lossless response](startup.md) · [Periodic response](periodic.md) ·
[한국어](../../locales/ko/pages/packages/sipi/rlgc_startup.md)
