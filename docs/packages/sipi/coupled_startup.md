# Two-signal finite RLGC startup circuit

[Mixed boundaries](coupled_boundary_startup.md) provide a separate API for per-conductor ideal/open/short ends.

[Saved inputs](coupled_startup_document.md) preserve these matrices and connect to common execution.

`coupled_rlgc_ladder_response` propagates a uniform **finite two-signal circuit**
from zero stored energy. Full constant scalar-conductor matrices retain mutual
inductance, capacitance, series resistance and shunt conductance. It extends
neither the number of conductors nor the boundary types implicitly.

```python
import numpy as np
from sipi import coupled_rlgc_ladder_response

t = np.linspace(0., 12e-9, 121)
drive = np.column_stack((np.minimum(t/2e-9, 1.), np.zeros(len(t))))
r = coupled_rlgc_ladder_response(t, drive,
    R=[[20., 3.], [3., 20.]], L=np.array([[500., 100.], [100., 500.]])*1e-9,
    G=[[.002, -.0003], [-.0003, .002]],
    C=np.array([[220., -40.], [-40., 220.]])*1e-12,
    length=.1, cells=32, source_resistance=[25., 25.], load_resistance=[100., 100.])
assert r.voltage.shape == (121, 4) and r.node_voltage.shape == (121, 33, 2)
assert r.port_names == ('near_0', 'near_1', 'far_0', 'far_1')
assert r.power_balance_relative_error <= 1e-10 and np.all(r.energy >= 0)
record = r.to_dict(include_states=True)
assert record['scope'] == 'finite-passive-two-signal-rlgc-ladder-startup'
```

## Passive input and bounds

R [ohm/m], L [H/m], G [S/m], C [F/m] are finite real exactly symmetric 2x2
matrices. R/G must be positive semidefinite; negative normalized eigenvalues
are rejected, without clipping or passivity repair. L/C must be positive
definite with normalized minimum/maximum eigenvalue ratio strictly above
1e-12. This is a numerical eligibility condition, not a material accuracy claim.
Near-symmetric inputs are not silently symmetrized. Zero R/G and rank-one
semidefinite loss matrices are permitted.

Length [m] is finite positive; `cells` is explicitly 1..128. Time is 2..10000
finite strictly increasing samples starting at zero, uniformly spaced within
relative 1e-10 (zero absolute tolerance). The source is `(samples,2)`, with
finite real entries and a zero first row; interpolate linearly and hold the
last row. Booleans are rejected. Both source and load resistances are explicit
length-two vectors of finite **positive** ohms. They are diagonal external
terminations, with no scalar broadcasting, zero, null or infinity shortcut.
Ideal sources and open/short/reactive ends are outside this coupled API.

Each dx segment uses full R*dx/L*dx matrices. Nodes use G*dx/C*dx, with half
weights at both ends. Existing SciPy `lsim` propagates the resulting PWL
state-space circuit; this is not a new Maxwell FDTD solver. Unrepresentable
cell matrices, slopes, coefficients, states or energy diagnostics raise.
The limits are not accuracy, elapsed-time or memory guarantees. Check spatial,
source bandwidth and time-grid convergence for the particular input.

## Ports, states and energy

`voltage` and `current` have four columns: near_0, near_1, far_0, far_1.
All port currents enter the line. `node_voltage` is `(samples,cells+1,2)`;
`segment_current` is `(samples,cells,2)` and points from near to far.
The response reuses the scalar circuit's copied/read-only arrays, detached
unit-labelled `inputs` and optional `to_dict(include_states=True)` serializer.
Its scope and port names explicitly identify the two-signal circuit. Default
JSON omits internal states; this is a result, not a saved-input version.

Energy and power records sum both conductors; individual port power is V*I.
Energy uses the full quadratic forms, including mutual terms. Validated PSD/SPD
eigenbasis squares evaluate stored energy and R/G dissipation without subtracting
nearly equal terms or clamping negative eigenvalues. `energy_rate` comes from
the circuit RHS. The residual E_dot - line_power + series_loss + shunt_loss,
normalized by the largest magnitude of those rate/input/total-loss terms,
must be <=1e-10. An exactly zero response has zero relative residual.
Stored energy and internal losses must remain nonnegative. Source and terminal
resistor losses remain separate; negative returned port power is retained.
This algebraic balance alone does not establish continuum convergence.

## Independent acceptance

Use the example's matrices and length, first-conductor 0..2 ns ramp to 1 V,
other conductor zero, and 1201 outputs over 0..12 ns. Setting R=G=0 allows
orthogonal common/differential diagonalization. The exact lossless delay
solutions of both modes, recombined in physical conductor coordinates, give
32/64/128-cell maximum voltage errors .004970/.002842/.001908 V and current
errors .000073341/.000028412/.000019071 A. Both decrease and meet .02 V/.0005 A
at 128 cells. This checks mutual coupling and finite spatial dispersion.

For the full lossy matrices, independent scikit-rf 2.2.0 modal distributed-line
ABCD at 500 MHz is recombined in physical coordinates. Twenty sinusoidal cycles,
256 samples/cycle and the final four-cycle phasor (no repeated endpoint) give
32/64/128-cell errors .000897/.000227/.0000681 V, decreasing and below 1e-3 V.
PWL interpolation error is included. The modal comparison requires exchange
symmetry; it does not claim an arbitrary-matrix modal decomposition.

A separately formulated KCL/inductor DOP853 integration checks asymmetric
positive-definite/semidefinite matrices and unequal resistive ends at 16 cells.
The maximum voltage difference is below 1e-8 V (rtol1e-10, atol1e-12, maximum
step min modal delay/(5*cells)). This compares propagation algorithms for the
same finite circuit, not independent spatial discretizations. SciPy 1.18.1
is an existing BSD-3-Clause runtime dependency; scikit-rf 2.2.0 remains a
BSD-3-Clause test-only reference. No dependency is added.

Zero coupling reduces to two different scalar circuits. Other checks cover
exact resistive DC limits, conductor permutation, superposition, time/impedance
scaling, rank-one losses, zero drive, returned pulse energy, copies and strict
inputs. Existing scalar startup and saved-circuit checks remain unchanged.
These criteria do not establish real-board material accuracy, arbitrary
dispersion, general TDR/eye/BER, or browser/Windows support.

[Scalar finite circuit](rlgc_startup.md) · [Frequency networks](network.md) ·
[한국어](../../locales/ko/pages/packages/sipi/coupled_startup.md)
