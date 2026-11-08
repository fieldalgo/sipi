# Mixed boundaries for two-signal startup

[Explicit saved v2](coupled_boundary_startup_document.md) connects mixed ends to strict JSON and common execution.

`coupled_boundary_ladder_response` solves the finite passive two-signal RLGC
circuit with independently selected ideal/resistive sources and resistive,
open or short loads. It is a separate API from the
[positive-resistance circuit](coupled_startup.md); that API and its saved v1
contract keep their original termination restrictions.

```python
import numpy as np
from sipi import coupled_boundary_ladder_response

t = np.linspace(0., 12e-9, 121)
drive = np.column_stack((np.minimum(t/2e-9, 1.), -.4*np.minimum(t/3e-9, 1.)))
r = coupled_boundary_ladder_response(t, drive,
    R=[[25., 2.], [2., 17.]], L=np.array([[510., 70.], [70., 430.]])*1e-9,
    G=[[.003, -.0002], [-.0002, .0015]],
    C=np.array([[230., -30.], [-30., 190.]])*1e-12,
    length=.1, cells=32, source_resistance=[0., 37.], load_resistance=[0., None])
np.testing.assert_array_equal(r.voltage[:, 0], drive[:, 0])
assert np.all(r.voltage[:, 2] == 0) and np.all(r.current[:, 3] == 0)
assert r.power_balance_relative_error <= 1e-10
assert r.to_dict()['input']['load_resistance_ohm'] == [0., None]
```

## Explicit boundary contract

Both resistance arguments contain exactly two entries. Source entries are
finite nonnegative ohms, with zero for an ideal voltage source. Each load entry
is finite nonnegative ohms (zero for short) or `None` for open. Numeric booleans,
scalar broadcasting, infinity and string boundary names are rejected. The
example has an ideal source on conductor 0, finite source on conductor 1,
a short on far conductor 0 and an open on far conductor 1.

The shared two-signal core contract is unchanged: exactly symmetric real 2x2
PSD R/G without negative-eigenvalue repair; SPD L/C with normalized eigenvalue
ratio above 1e-12; positive finite length; explicit 1..128 cells; 2..10000 time
samples starting at zero, strictly increasing and uniform within relative
1e-10. The PWL `(samples,2)` drive starts with a zero row and holds its last
value. No initial energy or capacitor impulse is inferred. All values use SI.

## Why the mass matrix matters

Each segment has full R*dx/L*dx and each node has G*dx/C*dx, with half end
weights. Prescribed ideal/short voltages are removed from the dynamic unknowns.
Simply dropping rows and columns of the already inverted state matrix would
lose mutual-capacitance derivative terms when only one voltage is prescribed.

Start with M*x_dot=K*x+B*u. Partition free and prescribed values xf,xp and set
T=Mff^-1*Mfp and z=xf+T*xp. Then
z_dot=Mff^-1*Kff*z + Mff^-1*(Kfp-Kff*T)*xp + Mff^-1*Bf*u.
Here xp is a fixed selection of the PWL drive or zero, so existing SciPy lsim
can propagate z without interpolating discontinuous source slopes. Recover
xf=z-T*xp and its derivative afterwards. All initial values are zero.

Ideal-source current is C_end*V_dot+G_end*V+first_segment_current.
Short-load current is C_end*V_dot+G_end*V-last_segment_current. These are full
matrix products, including the other conductor's voltage derivative. Finite
source current is (drive-V)/Rs; finite load current is -V/Rl; open current is
zero. Derivatives use right PWL slopes and zero slope at the final sample.
At the initial instant, a partial ideal source sees the Schur capacitance
(C00-C01*C10/C11)*dx/2, not simply C00*dx/2, when the other source is finite.

## Results and acceptance

`MixedBoundaryRLGCLadderResponse` reuses the two-signal response storage and
serializer, with an explicit mixed-boundary scope and null load entries retained.
Ports are near_0,near_1,far_0,far_1; every port current points into the line.
Node/segment states retain their conductor axis. Arrays are copied/read-only;
`to_dict(include_states=True)` optionally includes internal states. Energy and
power diagnostics sum both conductors and preserve negative return power.
The full quadratic energy, RHS energy rate and internal R/G losses use the same
nonnegative/finite and relative power-balance <=1e-10 gates. Source/load resistor
losses remain separate; ideal/short/open ends dissipate no resistor power.
Singular free mass matrices or unrepresentable coefficients/states raise.

Independent one-cell coupled RL ramp formulas check both segment currents and
full endpoint capacitive source currents. A partial ideal-source initial-current
check uses the Schur expression above. Positive finite ends reproduce the older
32-cell circuit within 1e-10 V and 1e-12 A. Zero coupling reduces to the scalar
mixed-boundary API; permutation, time/impedance scaling, zero drive, returned
pulse power and strict inputs are also checked.

For the exchange-symmetric matrices in the positive-resistance API example,
R=G=0, length .1 m, a first-conductor 0..2 ns ramp to 1 V, other conductor zero
and 1201 samples over 0..12 ns, compare physical voltages/currents to recombined
exact common/differential delay solutions. Six combinations Rs=0 or25 ohm and
Rl=0,open or100 ohm use32/64/128 cells. Errors decrease and meet .02 V/.0005 A
at128 cells. The largest finest-grid voltage error is .007831 V (ideal/open);
current error is .000231 A (ideal/short). This fixture does not guarantee that
128 cells suffice for every source, line or horizon.

A separate per-node KCL/DOP853 integration checks the asymmetric matrices and
mixed ends in the code example at16 cells, rtol1e-10/atol1e-12 and maximum step
min modal delay/(5*cells). Its maximum differences are below1e-8 V/1e-9 A.
It explicitly includes prescribed-voltage derivatives in free-node equations;
this is a separate propagation algorithm for the same finite circuit, not a
second spatial discretization. SciPy1.18.1 is the existing BSD-3-Clause dependency.

This remains a constant two-signal finite circuit, without reactive external
loads, arbitrary material dispersion, additional conductors, general TDR/eye/BER,
measured-board accuracy or automatic convergence. No new dependency is introduced.
Saved-input integration and browser/Windows support require separate validation.

[Positive resistive circuit](coupled_startup.md) · [Scalar mixed ends](rlgc_startup.md) ·
[한국어](../../locales/ko/pages/packages/sipi/coupled_boundary_startup.md)
