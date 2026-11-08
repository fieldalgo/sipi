# Real-reference startup port waves

`startup_port_waves(response, z_ref=...)` converts existing startup terminal V/I
samples to incident/reflected real power waves. It accepts `LosslessLineResponse`
and `RLGCLadderResponse`, including coupled, mixed, capacitive and reactive
subclasses, plus the separate `NortonReactiveRLGCLadderResponse`, and returns
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
rejects Norton inputs; this direct adapter does not change its closed registry.
