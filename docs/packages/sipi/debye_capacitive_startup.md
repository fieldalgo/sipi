# PSD Debye startup with an external capacitive load

`psd_coupled_debye_capacitive_ladder_response` combines the explicit
[PSD Debye circuit](psd_debye_startup.md) with a parallel external two-signal
capacitor. It is a separate API and response class; existing saved/wave input
contracts are unchanged.

## Input and circuit meaning

The required `load_capacitance` is in F, a real exactly symmetric PSD2x2 matrix.
Zero/rank-one matrices are allowed; negative eigenvalues and asymmetry reject
without repair. It is an external lumped load, distinct from per-unit-length
C_inf and DeltaC in F/m. Add it to the far-node mass, preserving half-end line
shunts. The original1..2PSD strengths,positive relaxation Hz, R/G PSD,L/C_inf SPD,
1..128cells,uniform2..10000times starting0 and zero-first PWL voltage drive hold.
Two finite positive source/load resistances remain required. No ideal/open/
short/current-source boundary or external inductive branch is introduced.

Into-line far current is `-Vfar/Rload-Cload*dVfar/dt`. Only resistor current
contributes to `load_resistor_loss=sum(Vfar**2/Rload)`; using Rload times total
terminal current squared would incorrectly count reactive current as loss.
The external capacitor stores .5*Vfar.T*Cload*Vfar and its signed power is
Vfar.T*Cload*dVfar/dt. Negative capacitor power represents returned energy.

## Separate line and full-circuit energies

`energy`/`energy_rate` retain instantaneous C_inf/L terms; `polarization_energy`
and its rate retain internal Debye storage. `line_energy`/`line_energy_rate`
sum these internal terms. `total_energy`/`total_energy_rate` additionally include
the external capacitor. Line terminal power balances line energy rate plus
series/shunt/relaxation loss. Source supplied power balances total energy rate
plus those losses and both source/load resistor losses. Each balance must pass
relative1e-10. All storage/loss terms must be finite and nonnegative, with no
clipping. Unrepresentable coefficients or invalid propagated states reject.

```python
from sipi import psd_coupled_debye_capacitive_ladder_response
import numpy as np

time = np.linspace(0., 12e-9, 121)
r = psd_coupled_debye_capacitive_ladder_response(time,
    np.minimum(time/2e-9, 1.)[:, None]*[1., -.4],
    R=[[20., 3.], [3., 20.]], L=np.array([[500., 100.], [100., 500.]])*1e-9,
    G=[[.002, -.0003], [-.0003, .002]], C_inf=np.array([[220., -40.], [-40., 220.]])*1e-12,
    delta_C=np.array([[[150., -150.], [-150., 150.]]])*1e-12,
    relaxation_hz=[1e9], length=.1, cells=16,
    source_resistance=[25., 25.], load_resistance=[100., 100.],
    load_capacitance=np.array([[30., -5.], [-5., 30.]])*1e-12)
assert r.voltage.shape == (121, 4) and r.load_capacitor_current.shape == (121, 2)
np.testing.assert_allclose(r.line_power,
    r.line_energy_rate + r.series_loss + r.shunt_loss + r.relaxation_loss,
    rtol=1e-10, atol=1e-12)
np.testing.assert_allclose(r.source_power,
    r.total_energy_rate + r.series_loss + r.shunt_loss + r.relaxation_loss
    + r.source_resistor_loss + r.load_resistor_loss, rtol=1e-10, atol=1e-12)
assert r.power_balance_relative_error <= 1e-10
assert r.total_power_balance_relative_error <= 1e-10
```

`DebyeCapacitiveLadderResponse` adds read-only copied `load_capacitor_current`
(time,2), `load_capacitor_energy` and `load_capacitor_power` (time,) alongside
four terminals and the original internal state arrays. JSON uses scope
`finite-passive-two-signal-psd-debye-capacitive-startup` and explicit SI keys
for both line and total energy and external load diagnostics. Internal node/
segment/polarization arrays require `include_states=True`. This independent
class is not implicitly accepted by current wave/saved adapters.

## Verification and limits

Zero external capacitance recovers the original PSD circuit; zero Debye
strengths recover the original constant coupled capacitive circuit at the
same finite resistive boundaries. Independent noncommuting charge-state KCL
with a separate far-node Cload mass is integrated by DOP853; terminal gates
are1e-8V/1e-9A. Continuous modal ABCD uses Yload=1/Rload+j*omega*Cload.
32/64/128cell errors decrease at100MHz/500MHz/1GHz and finest errors stay below
1mV for the documented fixture.100MHz uses8cycles/1024samples per cycle;
500MHz/1GHz use20cycles/256samples.100MHz256/512/1024sample finite-pi errors
also decrease, and7/8/9cycle phasor differences stay below1e-8V.

Zero/rank-one/full-PSD loads, ramp/pulse discharge, null states, scaling and
permutations, strict inputs, copies and original exceptions are checked.
Thirty-two original strict-SPD/PSD cases preserve full physical/saved/wave
JSON hashes. These are finite-circuit and fixture-specific convergence checks,
not measured-board accuracy or general meshing/horizon guarantees. Existing
reference versions/licenses are reused; no new dependency, geometry/material
extraction, browser/Windows integration or automatic resampling is introduced.

[한국어](../../locales/ko/pages/packages/sipi/debye_capacitive_startup.md)

[Saved external capacitive inputs](debye_capacitive_startup_document.md) distinguish F from F/m.
