# Mixed voltage and current boundaries

[Periodic mixed sources](periodic_mixed.md) apply real voltage/current waveforms and retain time/harmonic power.

`terminate_mixed_network(network, boundaries)` chooses a Thevenin or Norton
boundary independently at each port. An ideal voltage source or short can
therefore coexist with an open terminal or ideal current source. The existing
[Thevenin](termination.md) and [Norton](norton_termination.md) APIs retain their
original contracts and defaults.

`boundaries` names **every** port of the network's actual basis. Each entry has
exactly one of these shapes; values are finite complex scalars or F samples:

| kind | source | passive load | terminal relation |
|---|---|---|---|
| `thevenin` | `source_voltage` [V] | `impedance` [ohm], Re Z≥0 | V+ZI=Vs |
| `norton` | `source_current` [A] | `admittance` [S], Re Y≥0 | I+YV=Is |

Z=0 is an ideal voltage source (a short if Vs=0); Y=0 is an ideal current
source (an open if Is=0). No omitted-port default, infinite value or large-load
approximation is used. Unknown fields/ports, missing fields, booleans, negative
real loads and incorrect array shapes are rejected. No port topology or source
location is inferred. Arbitrary frequency grids use the original network order.

```python
import numpy as np
from sipi import rlgc_network, terminate_mixed_network

f = np.array([0., 1e8, 2e8])
network = rlgc_network(f, R=[[0.]], G=[[0.]],
    L=[[250e-9]], C=[[100e-12]], length=.1)
result = terminate_mixed_network(network, {
    'near:1': dict(kind='thevenin', source_voltage=1., impedance=0.),
    'far:1': dict(kind='norton', source_current=0., admittance=0.)})
theta = 2*np.pi*f*.1*5e-9
np.testing.assert_allclose(result.voltage[:, 0], 1., atol=1e-12, rtol=0)
np.testing.assert_allclose(result.voltage[:, 1], 1/np.cos(theta), atol=1e-12, rtol=0)
np.testing.assert_allclose(result.current[:, 1], 0., atol=1e-12, rtol=0)
```

## Feedback, residuals and retained data

For positive real reference Zr, solve `a=Gamma*b+drive`, `b=S*a`:

- Thevenin: `Gamma=(Z-Zr)/(Z+Zr)`, `drive=Vs*sqrt(Zr)/(Z+Zr)`;
- Norton: `Gamma=(1-Y*Zr)/(1+Y*Zr)`, `drive=Is*sqrt(Zr)/(1+Y*Zr)`.

The implementation uses equivalent ratio expressions, rejects nonfinite
intermediates/results and feedback condition numbers above 1e12. Both normalized
boundary and wave residuals must be at most 1e-10. Floating networks or
inconsistent ideal constraints are errors, even with zero source values.

KVL residuals [V] and KCL residuals [A] are normalized **per port**, never in a
shared dimensional norm. Each denominator is the maximum source, primary,
load-drop and incident/reflected contribution in the same units, with a
float-tiny floor. Contributions are `sqrt(Zr)*a,b` for KVL and `a,b/sqrt(Zr)`
for KCL. Including pre-cancellation waves avoids normalizing an open terminal's
roundoff current by that same current. This is a backward-error test; the
independent absolute V/I acceptance remains separate.

`MixedTerminatedNetwork` snapshots the original `network`, port-ordered `kinds`,
`source_voltages` [V], `series_impedances` [ohm], `source_currents` [A],
`shunt_admittances` [S], `a,b` [sqrt(W)], `voltage` [V], inward `current` [A],
`condition_number` [F], `boundary_residual` [F,P] and `wave_residual` [F].
Unused source/load columns are zero. Computed arrays are read-only. Final
reference impedances, port names, frequency and basis remain available.

## Power and acceptance scope

Per-frequency `network_power`, `termination_power` and `source_power` are W.
DC has weight 1, positive-frequency peak phasors weight 1/2. Source power uses
Vs·conj(I) for Thevenin ports and V·conj(Is) for Norton ports. Load power uses
ZI·conj(I) or V·conj(YV), respectively. Real source power equals network plus
load power for the tested circuits. Nonfinite products or sums raise errors.
Unrelated frequency powers are not summed into a time average.

Equivalent finite Thevenin/Norton circuits agree in external V/I, waves and
network power; their internal source/load powers need not agree because their
topologies differ. All-one-kind cases agree with the existing API's powers too.

Acceptance covers an ideal-voltage/open lossless line including DC, a resistor
bridge with a short, actual coupled RLGC in conductor and mixed bases, changed
references, superposition, snapshots, strict boundaries, ill-conditioning and
overflow. SciPy 1.18.1 (BSD-3-Clause) analytical RLC nodal equations and scikit-rf
2.2.0 (BSD-3-Clause) S→Y nodal equations independently solve a fixed-voltage node
with an open/current/shunt free node. Maximum V/I differences are
2.289e-16 V / 2.454e-17 A, below the absolute 1e-12 gate.

Saved inputs use [mixed-circuit/1](mixed_circuit.md). This API adds no time transform.
It establishes no new field accuracy, measured-board accuracy, supplied-network
passivity, causality, startup behavior or application/Windows acceptance.

[한국어](../../locales/ko/pages/packages/sipi/mixed_termination.md)
