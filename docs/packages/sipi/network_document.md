# Saved network transformations

Explicit [version 2](saved_fixtures.md) also saves cascade and known-fixture removal.
Version 1 below remains the constructor default and keeps its canonical inputs.

`NetworkTransformDocument` stores one network input and an ordered sequence of
reference changes and passive port reductions. Existing line extraction and
network APIs perform the calculations; saving a sequence adds no new physics.

```python
from sipi import NetworkTransformDocument
source = dict(kind='rlgc', frequency_hz=[0, 1e9, 5e9],
              R=[[0]], L=[[250e-9]], G=[[0]], C=[[100e-12]],
              length_m=.01, reference_ohms=50, names=['trace'])
plan = NetworkTransformDocument(source, operations=[
    dict(kind='renormalize', reference_ohms=[75, 120]),
    dict(kind='terminate-ports', loads={'far:trace': 'open'}),
])
result = NetworkTransformDocument.loads(plan.dumps()).analyze()
# result.network has one port, near:trace, referenced to 75 ohms.
```

The strict schema `sipi.network-transforms/1` has exactly `schema`, `network`
and `operations`. The base network uses the existing [circuit network input
contracts](circuit_document.md): `rlgc`, inline `touchstone`,
`transmission-line`, `volume-line`, [lumped-network](lumped_network.md), or [network-assembly](network_assembly.md).
Their complete input and validity
requirements are preserved. A transformation cannot itself be a base network;
there are no recursive plans, file paths, URLs, expressions or network access.

`operations` contains 1–32 objects, in execution order:

| `kind` | Other required fields | Meaning |
|---|---|---|
| `renormalize` | `reference_ohms` | Positive real scalar or one reference per current port; canonical JSON saves the full vector |
| `terminate-ports` | `loads` | Nonempty map from current port names to open, short or finite passive impedances; at least one port must remain |

An open/short load uses the literal string `"open"`/`"short"`. Finite loads
use a real number or `{ "real": ..., "imag": ... }`, with both components
scalar or both arrays of length F. Canonical JSON saves both components even
for real values. Negative resistance is rejected. No omitted port is loaded.
Names and reference-vector sizes are checked **after each preceding step**.
There is no automatic reorder, interpolation, model selection or port mapping.

Unknown/missing fields, duplicate JSON keys, nonfinite values, boolean numbers,
unsupported versions and malformed intermediate port selections are errors.
Inputs and accessor outputs are copied; `frequency` and final `z_ref` are read-only and
`port_names` is a tuple for the final network. `to_dict` returns a fresh map.
Parsing validates input metadata without a geometry mesh. Existing explicit
RLGC/Touchstone parsing may perform numerical network construction.

`analyze()` extracts the base network once, then applies
`LineNetwork.renormalized` and `terminate_ports` in order. The returned
`NetworkTransformResult` holds `network`, `source_network`, exact canonical
`input_json`, and `extraction` (the original line or assembly result, or None for
an explicit network). Singular feedback, conditioning, mesh and material errors propagate;
there is no partial-success result or silent step removal.

Existing `CircuitDocument` accepts
`network={"kind":"network-transform", "document":plan.to_dict()}`. Its
source/load names address the **final** ports; removed ports are rejected
before extraction. `CircuitResult.extraction` then holds the transformation
result, whose `extraction` holds the original line or assembly result.
Existing circuit schema/version semantics remain unchanged. Older readers
reject the new kind; record the SIPI version with saved inputs.

`tests/sipi/test_network_document.py` checks lossless open/short line reflection,
unequal-reference transformations in both valid orders and independently
derived driven terminal voltages/currents to absolute 1e-12. A nonreciprocal
Touchstone source with complex load and repeated reference changes must agree
with scikit-rf 2.2.0 renormalize/connect to absolute 1e-10. Both geometry source
kinds must mesh/extract once, while parsing must not mesh. Snapshot/replay,
budgets, malformed inputs, removed names and analysis failure are tested.
These are composition checks; they do not add geometry accuracy, 3D via/stub
physics, time-domain support, GUI linkage or new platform validation.

[Port reduction](port_reduction.md) · [Reference changes](network.md) ·
[한국어](../../locales/ko/pages/packages/sipi/network_document.md)
