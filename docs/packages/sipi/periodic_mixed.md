# Periodic mixed voltage and current sources

`periodic_mixed_response(network, boundaries)` combines real source waveforms
with [mixed terminal boundaries](mixed_termination.md). Ideal voltage/short and
current/open terminals can coexist. Every actual-basis port explicitly selects
Thevenin (`kind`, `source_voltage`, `impedance`) or Norton (`kind`,
`source_current`, `admittance`) fields; there are no inferred loads or sources.

Source values are finite real scalar DC constants or N real time samples [V or
A according to kind]. Loads remain finite passive complex scalar or F-frequency
samples [ohm or S], with **exactly real DC**. Z=0 or Y=0 retains its ideal
boundary meaning. Complex time samples, booleans, wrong shapes, unknown/missing
fields and negative real loads are rejected.

The [periodic grid contract](periodic.md) requires uniformly spaced harmonics
from exactly real DC S, F≥2, odd N=2F−1, period 1/df and dt=1/(N·df).
No Nyquist bin, interpolation, window, missing-DC inference or causal repair is
added. Existing single-kind periodic APIs retain their contracts.

```python
import numpy as np
from sipi import rlgc_network, periodic_mixed_response

network = rlgc_network(np.arange(5)*1e8, R=[[0.]], G=[[0.]],
    L=[[250e-9]], C=[[100e-12]], length=.1)
t = np.arange(9)/9
drive = .3+.2*np.cos(2*np.pi*t)+.1*np.sin(4*np.pi*t)
result = periodic_mixed_response(network, {
    'near:1': dict(kind='thevenin', source_voltage=drive, impedance=0.),
    'far:1': dict(kind='norton', source_current=0., admittance=0.)})
np.testing.assert_allclose(result.response.voltage[:, 0], drive, atol=1e-12, rtol=0)
np.testing.assert_allclose(result.response.current[:, 1], 0., atol=1e-12, rtol=0)
np.testing.assert_allclose(np.mean(np.sum(result.response.voltage*result.response.current, axis=1)),
    result.frequency_solution.network_power.sum(), atol=1e-12, rtol=0)
```

## Harmonics, load response and power

The real sources are transformed to DC means and positive-frequency peak
phasors. The mixed boundary solver applies its original condition, per-port
boundary residual and wave residual gates to every harmonic. Inverse synthesis
returns all port incident/reflected waves, V/I, series drop Z(f)I(f) and shunt
current Y(f)V(f). Frequency-dependent loads are not pointwise time multipliers:
an R+L series drop is RI+L·dI/dt; a G+C shunt current is GV+C·dV/dt.

`PeriodicMixedResponse` contains read-only snapshots:

- `source_voltages`, `termination_voltages`: N×P real V at Thevenin ports;
- `source_currents`, `termination_currents`: N×P real A at Norton ports;
- `response`: `PeriodicResponse` with time, period, dt, waves, V/I and metadata;
- `frequency_solution`: the complete `MixedTerminatedNetwork`, including
  port-ordered kinds, original loads, peak harmonics, diagnostics and powers.

Unused-kind columns in the four source/load arrays are zero. At Thevenin ports,
Vs=V+drop; at Norton ports, Is=I+shunt. Time-average powers are:

- network: mean Σ(V·I);
- terminations: mean Σ(drop·I+V·shunt);
- sources: mean Σ(Vs·I+V·Is).

Each equals the sum of its frequency-solution harmonic powers (DC weight 1,
positive peak weight 1/2). This sum is justified by the explicit periodic grid;
it does not change the general mixed circuit's unrelated-frequency semantics.
Internal powers follow the selected source topology.

## Acceptance and scope

Tests cover analytic ideal-voltage/open line phasors including DC, reactive-load
time derivatives, all-Thevenin/all-Norton agreement with the existing periodic
APIs, actual coupled RLGC in conductor/mixed bases, direct finite synthesis,
superposition, circular shift, zero drive, snapshots and time/harmonic power.
Strict shape/load/grid/DC, floating-terminal and overflow guards remain explicit.

SciPy 1.18.1 (BSD-3-Clause) analytical RLC nodal equations and scikit-rf 2.2.0
(BSD-3-Clause) S→Y nodal equations independently solve a fixed-voltage/free-current
two-port using explicit finite DFT and synthesis. Maximum time V/I differences
are 3.886e-16 V / 1.388e-17 A, below the absolute 1e-12 gate. Feedback condition
above 1e12 and normalized residual above 1e-10 remain errors.

This is sampled **periodic steady state**, not switching startup or an isolated
pulse. Circular wrapping, finite bandwidth and inherited network-model limits
remain. No causality/stability, new field or measured-board accuracy is claimed.
This API adds no saved schema (45 remain) or application/Windows acceptance.

[Thevenin waveforms](periodic_termination.md) · [Norton waveforms](periodic_norton.md) · [한국어](../../locales/ko/pages/packages/sipi/periodic_mixed.md)
