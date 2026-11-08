# Mixed voltage/current startup sources

`coupled_mixed_source_ladder_response(time, sources, ...)` accepts two explicitly
typed sources for a constant passive two-signal line with the existing external
C and series-RL load topology. It returns a separate `MixedSourceRLGCLadderResponse`.
The earlier voltage-only and current-only APIs keep their contracts.

```python
import numpy as np
from sipi import coupled_mixed_source_ladder_response

time = np.linspace(0., 12e-9, 121)
sources = [dict(kind='voltage', voltage_v=np.minimum(time/2e-9, 1.),
                series_resistance_ohm=0.),
           dict(kind='current', current_a=-.008*np.minimum(time/3e-9, 1.),
                shunt_resistance_ohm=None)]
response = coupled_mixed_source_ladder_response(time, sources,
    R=[[25., 2.], [2., 17.]], L=np.array([[510., 70.], [70., 430.]])*1e-9,
    G=[[.003, -.0002], [-.0002, .0015]], C=np.array([[230., -30.], [-30., 190.]])*1e-12,
    length=.1, cells=16, load_resistance=[91., None],
    load_capacitance=np.array([[20., -4.], [-4., 30.]])*1e-12,
    load_branch_resistance=[[13., 1.], [1., 9.]],
    load_branch_inductance=np.array([[12., 2.], [2., 8.]])*1e-9)
assert response.source_kinds == ('voltage', 'current')
assert response.source_units == ('V', 'A')
np.testing.assert_array_equal(response.voltage[:, 0], sources[0]['voltage_v'])
np.testing.assert_array_equal(response.current[:, 1], sources[1]['current_a'])
assert response.total_power_balance_relative_error <= 1e-10
assert not response.to_dict()['states_included']
assert np.all(response.source_series_resistor_loss == 0.)
assert np.all(response.source_shunt_resistor_loss == 0.)
```

## Typed inputs and boundaries

`sources` is a list/tuple of exactly two dictionaries. Each has exactly three keys:

| kind | Waveform key and unit | Resistance key and meaning |
|---|---|---|
| voltage | `voltage_v`, V | `series_resistance_ohm`, finite>=0;0 is prescribed near voltage |
| current | `current_a`, A | `shunt_resistance_ohm`, finite>=0 or None;0 shorts the near node, None removes the shunt |

Each waveform is a real finite one-dimensional array matching the time rows,
with first value0. Wrong-kind, extra/missing keys, ambiguous units, booleans,
complex/nonfinite values and scalar broadcasting reject. Voltage resistance
cannot be None. Both homogeneous kinds and either mixed ordering are supported.

All original line/load conditions apply: time starts0 with2..10000 uniform rows,
PWL input and final-value hold; explicit1..128 cells and positive length; real
exactly symmetric PSD line R/G, conditioned SPD line L/C; PSD lumped Cload[F]
and Rbranch[ohm], conditioned SPD Lbranch[H] with eigenvalue ratio>1e-12.
Zero/rank-one C/R are allowed without negative-eigenvalue repair. Per-conductor
load resistances are finite>=0 or None. This is the existing parallel C/seriesRL/
resistor topology, with zero initial stored energy, not an arbitrary netlist.

Mixed ideal voltage/current boundaries retain mutual endpoint C. Prescribed
voltages are eliminated with a transformed mass state; terminal currents include
endpoint C*dV/dt+G*V and series flux. Reconstruction uses right PWL slopes and
final slope0. A current source with shunt0 can inject into its short without
entering the line; its supplied power is0. No singular Thevenin/Norton conversion
is required for ideal boundaries.

## Units, power and result

`source_values` is `(times,2)` with explicit `source_kinds` and `source_units`
(`V` or `A`) for each column. Canonical `inputs['sources']` retains typed waveform
and resistance keys. There is no ambiguous source-voltage/current alias.
All four terminal `current` columns point into the line.

Source supplied power sums `Vs*Iterminal` for voltage sources and `Iinj*Vterminal`
for current sources. `source_series_resistor_loss` contains only voltage-source
series R*Iterminal²; `source_shunt_resistor_loss` contains only current-source
Vterminal²/Rsh for positive finite shunts. These are nonnegative and separate.
Equivalent finite source transformations preserve terminal V/I and net delivered
power but generally change supplied power and individual source losses.

Line energy/rate, series/shunt loss, external capacitor current/energy/power,
branch current/inductor energy/rate/resistor loss and parallel-load resistor
loss remain separate. `total_energy`/`total_energy_rate` add line and external
C/L contributions. Line and combined source/loss/RHS balances require relative
1e-10. They check finite-circuit conservation, not spatial/time/settling accuracy.

All arrays and derived energy arrays are detached read-only finite values.
`to_dict()` omits internal line states by default; `include_states=True` includes
them. Scope is `finite-passive-two-signal-mixed-source-reactive-startup`.
[Saved inputs](mixed_startup_document.md) retain typed sources in a separate schema.
The port-wave adapter remains a separate pending connection.

## Independent checks and limitations

A decoupled one-cell ideal voltage/current ramp/hold has independent series-L
and LC solutions checked at rtol1e-10/atol1e-12. Full asymmetric direct node KCL
with DOP853, without reusing assembled candidate matrices, checks ideal source
permutations and finite25/37ohm sources at V<=1e-8V, terminal/branch I<=1e-9A.
Finite source equivalence checks V<=1e-10V/I<=1e-12A and power partition.

Continuous scikit-rf modal ABCD is converted to a four-port admittance with the
same mixed finite sources and external loads. At500MHz,20cycles/256samples per
cycle, final-four-cycle phasor voltage errors at32/64/128cells decrease from
1.753mV to.449mV to.120mV, meeting the finest1mV gate. This is one qualified
finite-source case; ideal-current settling is not inferred from it.

Homogeneous limits, six mixed boundaries, lossless post-pulse energy, zero/rank-one
loads, zero input, linear/time/impedance/permutation invariants, copies and strict
inputs supplement the independent references. Original seven APIs retain exact
full-state/JSON output on38 ramp/pulse/boundary fixtures. No automatic horizon or
mesh change, frequency dispersion, initial energy, nonlinear devices, general
TDR/eye/BER, measured-board accuracy or browser/Windows parity is implied.

[Voltage-source reactive startup](coupled_reactive_startup.md) ·
[Current-source startup](norton_startup.md) · [한국어](../../locales/ko/pages/packages/sipi/mixed_startup.md)
