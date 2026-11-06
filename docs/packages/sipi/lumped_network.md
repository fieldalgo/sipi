# Passive lumped RLC networks

`lumped_network` constructs a two-port network from one **series R-L-C branch**.
Place it inline (`series`) or between an ideal through node and common ground
(`shunt`). Both use `exp(+j omega t)`, SI units and power-normalized waves.
Component values and parasitics are supplied, never inferred from geometry.

```python
from sipi import LumpedNetworkDocument, NetworkTransformDocument
from sipi.circuit_document import CircuitDocument

branch = LumpedNetworkDocument(
    [0, 1e6, 1e9, 10e9], resistance=.23, inductance=1.2e-9,
    capacitance=2.2e-12, placement='series', z_ref=[25, 85],
    port_names=('input', 'output'),
)
restored = LumpedNetworkDocument.loads(branch.dumps())
network = restored.analyze()
circuit = CircuitDocument(
    dict(kind='lumped-network', document=restored.to_dict()),
    excitation=dict(kind='sources', voltages={'input': 1}),
    terminations={'input': 37, 'output': 83},
)
response = circuit.analyze().response
assert abs(response.voltage[0, 1]) < 1e-12  # Series capacitor blocks DC.
reduced = NetworkTransformDocument(
    dict(kind='lumped-network', document=restored.to_dict()),
    operations=[dict(kind='terminate-ports', loads={'output': 83})],
).analyze().network
```

## Contract and saved input

At positive frequency, `Z = R + j 2 pi f L + 1/(j 2 pi f C)`.
`resistance` (ohm) and `inductance` (H) are finite nonnegative scalar constants,
defaulting to zero. `capacitance` (F) is finite positive or `None`, which **omits**
the capacitor. It does not mean zero capacitance or an open branch. A parallel
RLC combination is not implicit.

`frequency` is a nonempty, strictly increasing 1-D array of finite Hz >= 0.
`z_ref` is one positive real constant or two per-port constants, not complex or
frequency-dependent. Two unique nonempty single-line `port_names` define near,
then far order; defaults are `near`, `far`. Both currents point into the network.
The returned single-ended `LineNetwork` owns read-only array copies.

At DC, a capacitor gives an exact open branch: disconnected open ports for
series placement, or a through connection for shunt placement. Without a
capacitor, Z=R. Zero R then gives a through series branch or a grounded shunt
short. No large finite substitute for infinity is used.

The strict `sipi.lumped-network/1` object contains exactly:

| Field | Value |
|---|---|
| `schema` | `sipi.lumped-network/1` |
| `frequency_hz` | Increasing sample array |
| `branch` | Exactly `resistance_ohms`, `inductance_h`, `capacitance_f` (C number or null) |
| `placement` | `series` or `shunt` |
| `reference_ohms` | Positive scalar or two-element array; canonical output is the full array |
| `port_names` | Two explicit names; canonical output is an array |

`from_dict`, `loads`, `to_dict` and `dumps` preserve copied canonical input.
Unknown/missing fields, duplicate JSON keys, unsupported versions, boolean
numbers and nonfinite inputs are errors. `analyze()` returns a `LineNetwork`.
Parsing validates numeric scales without meshing or file I/O.

Use `{"kind":"lumped-network", "document":branch.to_dict()}` in
[circuits](circuit_document.md), [assemblies](network_assembly.md) and
[transformations](network_document.md). Existing field meanings and old canonical
inputs are unchanged; older readers reject the new kind. Circuit and assembly
extraction slots are `None` for lumped components. Geometry components retain
their diagnostics and are extracted once per analysis.

## Numerical scope and checks

Normalized scattering factors avoid products of large references and division
by an absolute parallel resistance. Real and imaginary components are scaled
separately, supporting pure-R networks even at subnormal R/reference values.
Reactive products use binary exponent splitting. Each nonzero positive-frequency
inductive/capacitive reactance must be a **normal finite binary64** value;
subnormal, underflowed or overflowed reactances raise `ValueError`. Exact finite
L/C cancellation remains valid; near-resonant relative impedance accuracy depends
on cancellation conditioning. There is no regularization or passivity repair.

Independent scikit-rf 2.2.0 (test-only, BSD-3-Clause) builds ABCD directly at the
actual unequal references. Max absolute S, KCL/KVL, balanced Ohm-law and power
residuals must be below `1e-10`. Raw voltage-law residuals also meet `1e-10 V`
for the tested >= 1 MHz range; the balanced law covers high-impedance 1 kHz cases.
100-digit Decimal arithmetic checks 2,000 pure-R combinations from the minimum
positive float through `1e300`: absolute S error and relative non-subnormal
transmission error each below `1e-12`. These are parameter cases, not 2,000 test
functions. Other checks cover DC limits, LC resonance, passivity/unitarity,
reciprocity, reference/impedance scaling, analytic Thevenin V/I and power,
JSON replay and geometry/circuit composition.

Existing cascade/deembedding accepts these networks. A singular S can still be
a removable fixture. A zero-transmission fixture (such as a series capacitor at
DC) cannot be deembedded at that sample; existing conditioning gates reject it
without dropping samples. No FEM convergence study applies to this algebraic
branch; geometry-backed components retain their own convergence requirements.

This is not a multi-terminal mutual-element model, frequency-dependent component
fit, nonlinear/temperature-dependent device, distributed AC plane, physical
via/pad/antipad transition or time-domain solver. No measured component accuracy
or new platform execution is implied. No runtime dependency is added.

[한국어](../../locales/ko/pages/packages/sipi/lumped_network.md)
