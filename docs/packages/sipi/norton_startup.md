# Current-driven coupled startup with passive reactive loads

`coupled_norton_reactive_ladder_response` drives two explicit Norton current
sources into a constant passive two-signal RLGC line and the existing parallel
capacitor/series-RL/parallel-resistor load topology. It returns a separate
`NortonReactiveRLGCLadderResponse` with current units and shunt-source loss names.
Existing [voltage-source APIs](coupled_reactive_startup.md) retain their contracts.

```python
import numpy as np
from sipi import coupled_norton_reactive_ladder_response

time = np.linspace(0., 12e-9, 121)
current = np.column_stack((.02*np.minimum(time/2e-9, 1.), -.01*np.minimum(time/3e-9, 1.)))
response = coupled_norton_reactive_ladder_response(time, current,
    R=[[25., 2.], [2., 17.]], L=np.array([[510., 70.], [70., 430.]])*1e-9,
    G=[[.003, -.0002], [-.0002, .0015]], C=np.array([[230., -30.], [-30., 190.]])*1e-12,
    length=.1, cells=32, source_shunt_resistance=[None, 37.], load_resistance=[91., None],
    load_capacitance=np.array([[20., -4.], [-4., 30.]])*1e-12,
    load_branch_resistance=[[13., 1.], [1., 9.]],
    load_branch_inductance=np.array([[12., 2.], [2., 8.]])*1e-9)
assert response.voltage.shape == (121, 4)
np.testing.assert_array_equal(response.current[:, 0], current[:, 0])
assert response.total_power_balance_relative_error <= 1e-10
assert np.all(response.source_shunt_resistor_loss >= 0)
assert 'source_currents_a' in response.inputs and 'source_voltages_v' not in response.inputs
assert not response.to_dict()['states_included']
```

## Current-source boundary contract

`source_currents` is a real finite `(times,2)` array in **A**, with a zero first
row. Time starts at0 and has2..10000 uniform rows (relative spacing1e-10), with
PWL currents and final-value hold. Initial internal/external stored energy is0.
`source_shunt_resistance` has two explicit entries: finite>=0 or None. None
removes the shunt, leaving an ideal current source;0 shorts the near node.
Infinity, booleans, complex values, scalar broadcasting and wrong shapes reject.

For a finite positive shunt, near line-port current is `Iinj-Vnear/Rsh`; for no
shunt it is exactly `Iinj`. At a near short, voltage is0 and line current follows
internal endpoint C/G plus series flux. Injected current can flow through the
short without entering the line; its supplied power is0. Shared mass-matrix
propagation retains mutual endpoint capacitance and fixed short nodes.

All line and load contracts follow the reactive API: real exactly symmetric
2x2 PSD line R/G, conditioned SPD line L/C, positive length, explicit1..128 cells,
PSD lumped Cload[F]/Rbranch[ohm] and conditioned SPD Lbranch[H] (eigenvalue ratio
>1e-12). Per-load resistance is finite>=0 or None;0 is a short. Negative
eigenvalues are not repaired, and singular branch L is rejected. These are
explicit lumped loads, not arbitrary RLC topology or frequency dispersion.

## Separate source power and loss

All four port currents enter the line, and `source_currents` are injected source
currents. Source supplied power is `sum(Vnear*Iinj)`. The separate
`source_shunt_resistor_loss` is `sum(Vnear²/Rsh)` over positive finite shunts.
It is not the series-resistor loss of a Thevenin source. The response deliberately
has no `source_voltages` or `source_resistor_loss` alias with ambiguous units.

For finite positive shunts, the equivalent voltage-source drive is `Vs=Iinj*Rsh`
and series resistance is Rsh. Line V/I and internal/load energy agree, but supplied
source power and source resistor losses generally differ. Only their net delivered
power is equal. Open/short shunts are handled directly without singular conversion.

Line `energy/energy_rate`, internal R/G losses, load-capacitor energy/current/power,
load-branch energy/rate/resistor loss and original parallel-load resistor loss stay
separate. `total_energy`/`total_energy_rate` include line, Cload and Lbranch.
Source power minus all source/internal/load losses equals combined energy rate.
Line and combined RHS balances require relative1e-10, with nonnegative passive
energy/loss and finite arithmetic. Source and terminal power may be negative.

All state/diagnostic arrays are copied read-only. `inputs` returns copied SI data
with `source_currents_a` and `source_shunt_resistance_ohm`. Default finite JSON
omits interior line states, while `to_dict(include_states=True)` includes them.
Scope is `finite-passive-two-signal-norton-reactive-startup`. This API currently
has no saved-input schema and is not yet accepted by the separate startup
port-wave wrapper; those adapters require explicit subsequent contracts.

## Independent acceptance and settling limits

Finite25/37ohm source equivalence checks line V<=1e-10V/I<=1e-12A and energy.
An ideal current-driven one-cell LC ramp/hold has an independent closed form
checked at rtol1e-10/atol1e-12. Asymmetric per-node KCL/DOP853 checks V<=1e-8V,
I<=1e-9A with near[None,37] and far[91,None].

Continuous scikit-rf modal ABCD checks500MHz final-four-cycle phasors. The finite
50ohm shunt case uses20cycles/256samples per cycle:32/64/128cell errors decrease
to about81uV. The ideal current case requires a separately qualified longer
observation:64cycles/128samples per cycle,8193rows, with32/64/128cell errors
1.506/.545/.291mV. At128cells,20/40/64cycle errors3.335/1.045/.291mV decrease;
only the final interval meets1mV. An independent finite pi-cell ABCD product
separates spatial error, decreasing to93.2uV at128cells against the continuous
reference. The original20cycle/256sample ideal-source case failed1mV (3.357mV),
and36cycles failed monotonic spatial refinement despite a sub-1mV finest result.
Those failures are retained; no automatic grid/horizon change is performed.

A DC test with near[None,37],far[91,113],G0 and8cells failed the original strict
voltage criterion at500ns (3.109nV). Fixed.2ns samples at600/800/1000ns compare
all101samples in each last20ns window. Voltage/current window maxima decrease,
and both800/1000ns windows meet the same rtol1e-10/atol1e-12 DC gates. The slowest
circuit decay time is about34.6ns. This is case-specific settling evidence, not
a universal horizon recommendation or relaxed tolerance.

Other checks cover mixed shunts/loads, zero/rank-one terms, lossless post-pulse
energy, DC, time/impedance/permutation/superposition invariants, copies and strict
controls. No mixed V/I source kinds, initial energy, general TDR/eye/BER, measured
board accuracy, browser/Windows parity or latest-head full validation is inferred.

[Voltage-driven reactive startup](coupled_reactive_startup.md) ·
[한국어](../../locales/ko/pages/packages/sipi/norton_startup.md)
