# Real-reference startup port waves

`startup_port_waves(response, z_ref=...)` converts existing startup terminal V/I
samples to incident/reflected real power waves. It accepts `LosslessLineResponse`
and `RLGCLadderResponse`, including coupled, mixed, capacitive and reactive
subclasses, plus the separate `NortonReactiveRLGCLadderResponse` and
`MixedSourceRLGCLadderResponse`, and returns
copied read-only `StartupPortWaves`. It does no propagation,
FFT, resampling, delay alignment, periodic extension or missing-DC inference.

```python
import numpy as np
from sipi import lossless_line_response, startup_port_waves

time = np.linspace(0., 8e-9, 801)
response = lossless_line_response(time,
    source_times=[0., 1e-9], source_voltages=[0., 1.],
    z0_ohm=50., delay_s=1e-9, source_resistance=50., load_resistance=None)
waves = startup_port_waves(response, z_ref=[50., 50.])
assert waves.port_names == ('source', 'load')
assert waves.incident.shape == (801, 2)
assert waves.power_balance_relative_error <= 1e-10
np.testing.assert_allclose(waves.incident[:, 1], waves.reflected[:, 1], atol=1e-12)
np.testing.assert_array_equal(waves.port_power[:, 1], 0.)
# Reference changes preserve V/I and physical port power, not wave amplitudes.
changed = startup_port_waves(response, z_ref=[35., 75.])
np.testing.assert_array_equal(changed.voltage, waves.voltage)
np.testing.assert_array_equal(changed.current, waves.current)
np.testing.assert_array_equal(changed.port_power, waves.port_power)
```

## Explicit references and directions

`z_ref` is an explicit vector with one finite positive real resistance [ohm] per
port. Scalar broadcasting, zero/negative, bool, complex and nonfinite references
are rejected. The exact response time grid, voltage/current and port names remain.
Nonuniform observation times and one sample are allowed if valid for the source
response. The supported responses have two or four single-ended ports.

With current **into the line**, `a=(V/sqrt(Z)+I*sqrt(Z))/2` is incident and
`b=(V/sqrt(Z)-I*sqrt(Z))/2` is reflected/outgoing, both in sqrt(W). At the source
of a scalar line, incident/reflected match forward/backward traveling voltage
waves divided by sqrt(Z) when the reference equals the characteristic impedance.
At the far port, these directions reverse: incident is backward, outgoing is
forward. An open far end has equal incoming/outgoing waves and zero net power;
a short has opposite waves and zero voltage.

These constant real diagonal references are a declared algebraic choice. They
are not inferred modal impedances and do not diagonalize coupled propagation.
Changing reference preserves V/I and terminal power, while changing wave values.
It does not perform general TDR impedance inversion or establish a frequency-
dependent/causal reference. No `b/a`, `V/I`, reflection gating or threshold is
inferred at zero or small signals.

## Numerical acceptance and output

The implementation computes scaled V/I before the half-sum/difference. It
reconstructs both physical V and I and requires error<=1e-10 relative to each
port's maximum original V or I across the supplied times. If an original column
is zero, reconstruction must be exactly zero. This rejects destructive numerical
cancellation instead of silently discarding a small current/voltage.

`a²-b²=V*I` must also pass relative1e-10 per port, normalized by that port's
maximum of `a²+b²` and `abs(V*I)`, not by net power near cancellation. This is a
wave-scale balance, not a claim of relative accuracy of arbitrarily small net
power. Nonfinite intermediate/results or unrepresentable scales reject; values
are never clipped. Returned `port_power` is directly `V*I`, including negatives.

The response retains read-only `time`, `voltage`, `current`, `z_ref`, `incident`,
`reflected`, `port_power`, names, source class name and three reconstruction/
power diagnostics. `to_dict()` emits finite SI JSON with scope
`explicit-real-reference-startup-port-waves` and basis `single-ended`. It does
not change the original physical response or its energy terms.

Independent tests cover matched/open/short/resistive delayed scalar reflections,
a finite unmatched-source reflection series, and 2-/4-port scikit-rf power-wave
Z-to-S conversion with independently solved phasor V=ZI. The latter is an
explicit passive impedance sample fixture, not a claim that it is a propagated
line. Further tests cover every supported response subtype, line-power sums,
reference changes, superposition, reference/port permutation, impedance scaling,
zero/nonuniform/single samples, copies, strict inputs and finite/cancellation
failures. This diagnostic does not certify source convergence, line accuracy,
general TDR/eye/BER or browser/Windows integration.

[Lossless startup](startup.md) · [Reactive startup](coupled_reactive_startup.md) ·
[한국어](../../locales/ko/pages/packages/sipi/startup_waves.md)

[Saved startup port waves](startup_waves_document.md)

## Current-driven terminal waves

The [Norton response](norton_startup.md) has four terminal ports. Use its
`current`, not its two injected `source_currents`. Near terminal power is
source supplied power minus the external source-shunt loss. At the far ports,
into-line power is the negative sum of parallel-load resistor loss, external
capacitor power, branch inductor energy rate and branch resistor loss.

Finite positive shunts have a Thevenin equivalent with Vs=Iinj*Rsh. Equal line
V/I therefore give equal waves at the same references, although supplied source
power and resistor losses differ. Ideal current/open shunts, shorts and mixed
boundaries need no singular source conversion. The response class name remains
`NortonReactiveRLGCLadderResponse` in `source_kind`.

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

from sipi import startup_port_waves
waves = startup_port_waves(response, z_ref=[35., 45., 55., 65.])
assert waves.source_kind == 'NortonReactiveRLGCLadderResponse'
assert waves.incident.shape == (121, 4)
np.testing.assert_allclose(waves.port_power[:, :2].sum(axis=1),
    response.source_power - response.source_shunt_resistor_loss, rtol=1e-10, atol=1e-12)
```

Checks cover ramp/pulse Norton–Thevenin equivalence, six mixed-boundary cases,
zero/rank-one external terms, zero input, reference changes, detached read-only
results and rejection of injected-current shapes. The original reconstruction
and power gates remain unchanged. The saved startup-port-waves/1 wrapper still
rejects Norton inputs; [saved version2](startup_waves_document.md) explicitly adds Norton while preserving version1.

## Mixed-source terminal waves

[Mixed voltage/current startup](mixed_startup.md) is accepted explicitly. Its
`source_values` columns may have different V/A units and must never substitute
for the four terminal voltage/current columns. The diagnostic preserves terminal
samples and the source class name `MixedSourceRLGCLadderResponse`.

Near wave power equals supplied source power minus **both** voltage-source
series loss and current-source shunt loss. Far into-line wave power is the negative
external capacitor/branch/resistor power. Finite mixed-source circuits and their
Thevenin equivalents have the same terminal waves at equal references, although
supplied powers and individual source losses differ. Homogeneous source-kind
limits match the earlier voltage-only/current-only wave results.

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

from sipi import startup_port_waves
waves = startup_port_waves(response, z_ref=[35., 45., 55., 65.])
assert waves.source_kind == 'MixedSourceRLGCLadderResponse'
assert waves.incident.shape == (121, 4)
np.testing.assert_allclose(waves.port_power[:, :2].sum(axis=1),
    response.source_power - response.source_series_resistor_loss
    - response.source_shunt_resistor_loss, rtol=1e-10, atol=1e-12)
```

Six mixed boundaries,ramp/pulse equivalents,homogeneous limits,zero/rank-one
loads,zero inputs,reference changes,readonly copies and rejection of two-column
mixed drive data are checked. The reconstruction/power gates and propagation
remain unchanged. Saved startup-port-waves version1 and2 still reject the mixed
input schema; [saved version3](startup_waves_document.md) explicitly adds mixed inputs.

## Explicit Debye terminal waves

`DebyeRLGCLadderResponse` is also accepted explicitly. It contributes the two
terminal voltages and into-line currents; polarization currents are internal
states and cannot substitute for terminal current. The same reconstruction
and power gates apply. Wave power at the near port equals source power minus
source resistor loss, and far-port power is minus load resistor loss. Their
sum equals instantaneous plus polarization energy rate and series, leakage
and relaxation loss. A reference change preserves terminal power.

```python
from sipi import debye_rlgc_ladder_response, startup_port_waves
import numpy as np

time = np.linspace(0., 12e-9, 121)
response = debye_rlgc_ladder_response(time, np.minimum(time/2e-9, 1.),
    R=20., L=500e-9, G=.002, C_inf=200e-12,
    delta_C=[150e-12, 50e-12], relaxation_hz=[1e9, 1e8],
    length=.1, cells=16, source_resistance=25., load_resistance=100.)
waves = startup_port_waves(response, z_ref=[35., 75.])
assert waves.source_kind == 'DebyeRLGCLadderResponse'
np.testing.assert_allclose(waves.port_power.sum(axis=1),
    response.total_energy_rate + response.series_loss + response.shunt_loss
    + response.relaxation_loss, rtol=1e-10, atol=1e-12)
```

Six boundaries with ramp/pulse, independent one-cell relaxation/inductor
analytic waves, zero-strength constant-RLGC limits, four-pole splitting,
zero inputs, copies, strict references and internal-array rejection are checked.
This is terminal decomposition, not a dispersive eigenmode or TDR inversion.
Saved wave schemas v1/v2/v3 still reject the Debye input document.
[Debye physical inputs](debye_startup.md) and [saved inputs](debye_startup_document.md)
retain their explicit time, cell and pole contracts.

[Explicit saved version4](startup_waves_document.md) includes Debye inputs.

## Explicit two-signal Debye terminal waves

[Coupled Debye startup](coupled_debye_startup.md) is accepted explicitly as
`CoupledDebyeRLGCLadderResponse`. Use its four terminal V/I columns in order
near_0, near_1, far_0, far_1. Two source voltages or four-dimensional internal
polarization currents are not terminal currents. Supply four finite positive
real references; the original reconstruction and power gates remain unchanged.
Near-pair wave power equals source power minus source resistor loss. Far-pair
power is minus load resistor loss. Their sum includes both instantaneous and
polarization energy rate plus R/G/relaxation loss. Changing references preserves
terminal power, while changing wave values.

```python
from sipi import coupled_debye_rlgc_ladder_response, startup_port_waves
import numpy as np

time = np.linspace(0., 12e-9, 121)
response = coupled_debye_rlgc_ladder_response(time,
    np.minimum(time/2e-9, 1.)[:, None]*[1., -.4],
    R=[[20., 3.], [3., 20.]], L=np.array([[500., 100.], [100., 500.]])*1e-9,
    G=[[.002, -.0003], [-.0003, .002]], C_inf=np.array([[220., -40.], [-40., 220.]])*1e-12,
    delta_C=np.array([[[150., -25.], [-25., 150.]]])*1e-12,
    relaxation_hz=[1e9], length=.1, cells=16,
    source_resistance=[25., 25.], load_resistance=[100., 100.])
waves = startup_port_waves(response, z_ref=[35., 45., 55., 65.])
assert waves.source_kind == 'CoupledDebyeRLGCLadderResponse'
assert waves.port_names == ('near_0', 'near_1', 'far_0', 'far_1')
np.testing.assert_allclose(waves.port_power.sum(axis=1),
    response.total_energy_rate + response.series_loss + response.shunt_loss
    + response.relaxation_loss, rtol=1e-10, atol=1e-12)
```

Diagonal and exchange-symmetric scalar-mode wave limits, noncommuting matrices,
ramp/pulse, zero-strength original coupled limits, pole/conductor permutations,
zero drive, copies and strict references are checked. This adapter does not
infer dispersive eigenmodes or TDR impedance. Saved wave v1..4 still reject the
[coupled Debye document](coupled_debye_startup_document.md); no implicit version upgrade.

[Explicit saved version5](startup_waves_document.md) adds coupled Debye inputs.

## Explicit four-terminal waves for PSD strengths

[PSD Debye responses](psd_debye_startup.md) are accepted explicitly as
`PSDCoupledDebyeRLGCLadderResponse`. Use terminal V/I ordered near_0,near_1,
far_0,far_1 and four positive real references; the original reconstruction and
power gates remain unchanged. Two source voltages and internal polarization
currents cannot replace terminal currents. A canonical null-direction auxiliary
voltage is not a separate traveling wave or loss contribution.

Near-pair power is source_power-source_resistor_loss; far-pair power is
-load_resistor_loss. The total is total_energy_rate+series_loss+shunt_loss+
relaxation_loss, including observable polarization storage and loss only.

```python
from sipi import psd_coupled_debye_rlgc_ladder_response, startup_port_waves
import numpy as np

time = np.linspace(0., 12e-9, 121)
response = psd_coupled_debye_rlgc_ladder_response(time,
    np.minimum(time/2e-9, 1.)[:, None]*[1., -.4],
    R=[[20., 3.], [3., 20.]], L=np.array([[500., 100.], [100., 500.]])*1e-9,
    G=[[.002, -.0003], [-.0003, .002]], C_inf=np.array([[220., -40.], [-40., 220.]])*1e-12,
    delta_C=np.array([[[150., -150.], [-150., 150.]]])*1e-12,
    relaxation_hz=[1e9], length=.1, cells=16,
    source_resistance=[25., 25.], load_resistance=[100., 100.])
waves = startup_port_waves(response, z_ref=[35., 45., 55., 65.])
assert waves.source_kind == 'PSDCoupledDebyeRLGCLadderResponse'
np.testing.assert_allclose(waves.port_power.sum(axis=1),
    response.total_energy_rate + response.series_loss + response.shunt_loss
    + response.relaxation_loss, rtol=1e-10, atol=1e-12)
```

Checks cover rank-one diagonal/exchange scalar modes, noncommuting ramp/pulse,
zero-strength and original strict-SPD wave limits, null-mode constant-line
limits, nearly singular strengths, pole/conductor permutations, copies,
strict references and internal-array rejection. Saved wave v1..5 still reject
PSD saved inputs. This does not establish dispersive eigenmode/TDR inference,
measured accuracy or browser/Windows integration.

[Explicit saved version6](startup_waves_document.md) adds PSD Debye inputs.

## Explicit four-terminal waves with external capacitive loads

[External-load Debye responses](debye_capacitive_startup.md) are accepted
explicitly as `DebyeCapacitiveLadderResponse`. Four terminal voltages and
into-line currents use four positive real references. All numerical wave
calculations and gates are unchanged. Source voltages, polarization currents
and external capacitor currents cannot replace terminal currents.

Near-pair power is source_power-source_resistor_loss; far-pair power is
-load_resistor_loss-load_capacitor_power. Their sum is line_energy_rate+
series_loss+shunt_loss+relaxation_loss, distinct from total_energy_rate that
includes external storage. Capacitor power can change sign during charging
and discharging; capacitor energy and resistor loss remain nonnegative.

```python
from sipi import psd_coupled_debye_capacitive_ladder_response, startup_port_waves
import numpy as np

time = np.linspace(0., 12e-9, 121)
response = psd_coupled_debye_capacitive_ladder_response(time,
    np.minimum(time/2e-9, 1.)[:, None]*[1., -.4],
    R=[[20., 3.], [3., 20.]], L=np.array([[500., 100.], [100., 500.]])*1e-9,
    G=[[.002, -.0003], [-.0003, .002]], C_inf=np.array([[220., -40.], [-40., 220.]])*1e-12,
    delta_C=np.array([[[150., -150.], [-150., 150.]]])*1e-12,
    relaxation_hz=[1e9], length=.1, cells=16,
    source_resistance=[25., 25.], load_resistance=[100., 100.],
    load_capacitance=np.array([[30., -5.], [-5., 30.]])*1e-12)
waves = startup_port_waves(response, z_ref=[35., 45., 55., 65.])
assert waves.source_kind == 'DebyeCapacitiveLadderResponse'
np.testing.assert_allclose(waves.port_power.sum(axis=1),
    response.line_energy_rate + response.series_loss + response.shunt_loss
    + response.relaxation_loss, rtol=1e-10, atol=1e-12)
np.testing.assert_allclose(waves.port_power[:, 2:].sum(axis=1),
    -response.load_resistor_loss-response.load_capacitor_power, rtol=1e-10, atol=1e-12)
```

Checks cover independent scalar modes and original PSD waves at CL0,
constant capacitive-line waves at zero strength, noncommuting ramp/pulse,
zero/rank-one/full external capacitance, null/nearly singular strengths,
permutations, reference power, copies and internal-array rejection. Saved
wave v1–6 still reject [external capacitive saved inputs](debye_capacitive_startup_document.md).
This does not establish dispersive eigenmode/TDR inference, measured accuracy
or browser/Windows integration.

[Explicit saved version7](startup_waves_document.md) adds external capacitive Debye inputs.
