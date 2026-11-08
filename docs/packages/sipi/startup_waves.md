# Real-reference startup port waves

`startup_port_waves(response, z_ref=...)` converts existing startup terminal V/I
samples to incident/reflected real power waves. It accepts `LosslessLineResponse`
and `RLGCLadderResponse`, including coupled, mixed, capacitive and reactive
subclasses, and returns copied read-only `StartupPortWaves`. It does no propagation,
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
