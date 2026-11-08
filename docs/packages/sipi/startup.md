# Lossless scalar line startup

[Finite passive RLGC circuit](rlgc_startup.md) covers explicit constant-loss circuit cells.

[Saved inputs](startup_document.md) connect this model to strict JSON and common execution.

`lossless_line_response` evaluates an **initially unenergized, uniform,
nondispersive, lossless scalar line**. Specify real positive characteristic
impedance and one-way delay, a piecewise-linear Thevenin drive and resistive
boundaries. It returns source/load voltages, currents and traveling waves.

```python
import numpy as np
from sipi import lossless_line_response

response = lossless_line_response(np.array([0., 1., 2., 3.])*1e-9,
    source_times=[0.], source_voltages=[1.], z0_ohm=50., delay_s=1e-9,
    source_resistance=50., load_resistance=None, max_terms=1)
np.testing.assert_allclose(response.voltage[:, 1], [0., 1., 1., 1.], rtol=0, atol=1e-14)
np.testing.assert_allclose(response.voltage[:, 0], [.5, .5, 1., 1.], rtol=0, atol=1e-14)
np.testing.assert_array_equal(response.current[:, 1], np.zeros(4))
assert response.terms == 1 and response.port_names == ('source', 'load')
assert not response.voltage.flags.writeable
record = response.to_dict()
```

The open load doubles the incident voltage after one delay. Its return reaches
the source after two delays and is absorbed by the matched source.

## Inputs, coordinates and records

`time` and `source_times` are nonempty, strictly increasing finite real arrays
of nonnegative seconds; one sample is allowed. `source_voltages` has one finite
real voltage per source knot. Booleans are rejected. The drive is zero before
its first knot, linear between knots and held at its final value afterwards.
A nonzero first value is an explicit right-continuous step, including a
one-knot drive. A pulse needs explicit return-to-zero knots. No periodic
extension, stored initial energy or missing DC is inferred.

`z0_ohm` and `delay_s` are positive finite scalars. `source_resistance` is
finite and nonnegative; zero is an ideal voltage source. `load_resistance` is
finite and nonnegative, with zero for short and **None for open**. Infinity is
rejected. A large finite resistance remains finite even when its reflection
coefficient rounds to one.

`voltage` and `current` have shape `(times,2)` in source/load order, volts and
amperes. **Both currents enter the line**: delivered load power is
`-voltage[:,1]*current[:,1]`. `forward_voltage` and `backward_voltage` are
right- and left-traveling voltage waves at these two planes; `drive_voltage`
is the ideal source sampled at output times. Arrays are detached/read-only.
`to_dict()` returns detached finite JSON-compatible data with units, original
inputs and term count. This result record is not a versioned saved-input
schema; common execution and application forms are separate work.

For explicitly lossless, frequency-independent scalar L', C' and length ell,
`Z0=sqrt(L'/C')` and `delay=ell*sqrt(L'*C')`. This assumes R=G=0. The API does
not silently discard loss or dispersion from an arbitrary extracted line.

## Finite delay sum and budget

For `gs=(Rs-Z0)/(Rs+Z0)`, `gl=(Rl-Z0)/(Rl+Z0)` (one for open),
`k=Z0/(Rs+Z0)` and `tau=delay`, the source outgoing voltage wave is
`a(t)=k*sum((gs*gl)**n * Vs(t-2*n*tau))`. Its return is
`b(t)=gl*a(t-2*tau)`; the load incident is `a(t-tau)`.

Zero prehistory makes the sum finite at every finite horizon. This also covers
undamped ideal-source cases with `gs*gl=+1` or `-1`, without approximating a
geometric tail. Normalized resistance sums evaluate port boundary equations
directly, retaining tiny finite-load current that would be lost in `1-gl`
or cancellation between traveling waves.

`max_terms` is an integer in 1..10000, checked before waveform evaluation.
`terms` counts potentially active **forward round-trip terms**, including
zero-valued drive contributions. It is not the sample count, every wave at
both ports, or a CPU/memory guarantee. Exactly zero round-trip coefficient
needs at most one forward term while still retaining the returning load wave.
The count can be zero before the first source knot. Exceeding the budget
raises without clamping the horizon or discarding later terms.

Shifted source knots must remain finite and distinct at floating-point time
resolution. Unresolved knots or nonfinite output raise. Wavefronts use the
right-continuous convention at the represented shifted knots.

## Acceptance and limits

Focused checks cover matched/open/short first arrivals and returns, resistive
steady limits, both boundary equations, pulse prehistory, superposition,
time/impedance scaling, undamped sums, budgets, input rejection and copies.
Extreme finite resistance retains nonzero current and its boundary equation.
Port power integrates to exact final electric/magnetic energy for matched,
open and short steps; source power balances source-resistor loss and line input.

Independent SciPy 1.18.1 DOP853 integrates series inductors and node capacitors
with half capacitors at the ends. Z0=50 ohm, delay=1 ns, Rs=25 ohm, Rl=100 ohm,
zero initial energy and a 0..2 ns ramp to 1 V are matched. At 1201 samples over
0..12 ns, maximum source/load errors for 32/64/128 cells are
0.006821/0.004185/0.002662 V. The gate is 0.02 V at 128 cells with decreasing
error at both refinements; ODE rtol/atol are 1e-10/1e-12 and max step is
`.2*delay/cells`. This spatial circuit is a separate converging numerical
reference, test-only with no new dependency. Existing network, termination
and periodic regressions retain their original gates.

Reactive/nonlinear loads, loss, dispersion, coupled lines, arbitrary measured
frequency reconstruction and general TDR/eye/BER interpretation are outside
this scope. This does not validate actual board materials/geometry or an
instrument. Browser/Windows support needs separate integration and exact-build
validation.

[Periodic response](periodic.md) · [Network](network.md) ·
[한국어](../../locales/ko/pages/packages/sipi/startup.md)

[Explicit port-wave diagnostics](startup_waves.md)
