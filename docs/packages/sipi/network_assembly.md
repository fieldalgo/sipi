# Saved network assembly

`NetworkAssemblyDocument` stores a starting component and ordered connections to
new components. It reuses [named wiring and ideal junctions](named_connections.md),
existing line extraction, and the strict input contracts of supplied networks.

```python
from sipi import NetworkAssemblyDocument, NetworkTransformDocument

frequency = [0, 1e9, 5e9, 10e9]
node = dict(kind='ideal-junction', frequency_hz=frequency,
            port_names=['input', 'output', 'branch'], reference_ohms=50)
stub = dict(kind='rlgc', frequency_hz=frequency,
            R=[[0]], L=[[250e-9]], G=[[0]], C=[[100e-12]],
            length_m=.01, reference_ohms=50, names=['stub'])
assembly = NetworkAssemblyDocument(node, connections=[
    dict(network=stub, ports=[['branch', 'near:stub']]),
])
loaded = NetworkTransformDocument(
    dict(kind='network-assembly', document=assembly.to_dict()),
    operations=[dict(kind='terminate-ports', loads={'far:stub': 'open'})],
)
result = NetworkTransformDocument.loads(loaded.dumps()).analyze()
# result.network: input/output ports with a 1 cm open shunt stub.
```

## Contract

The schema is `sipi.network-assembly/1`, with exactly `schema`, `network` and
`connections`. A component is an existing `rlgc`, inline `touchstone`,
`transmission-line`, `volume-line` or [lumped-network](lumped_network.md)
[network input](circuit_document.md), or an
`ideal-junction` with exactly `kind`, `frequency_hz`, `port_names` and
`reference_ohms`. A junction needs an explicit array of at least two unique names;
the positive real reference is a scalar or per-port array, saved as a full array.
Components cannot contain another assembly or transformation. No file paths,
URLs, expressions, inferred geometry or recursive plans are accepted.

`connections` has 1–32 objects. Each requires `network` for the new component and
`ports`, a nonempty array of `[current_port, new_component_port]` pairs. Optional
`port_names` explicitly renames **all** remaining outputs. No port can appear in
two pairs; at least one external port must remain after every join. Current ports
mean the output of all previous joins. Consumed names cannot be used again.
Output order is remaining current ports, then remaining new-component ports.
Canonical JSON always saves that entire output name array, including defaults.
Provide names when the defaults collide. This is ordered network construction,
not implicit name matching or a global netlist with automatic port inference.

All frequency samples must match exactly. Each connected pair must have identical
positive real references. There is no interpolation or automatic renormalization.
Invalid wiring, reference mismatch and final circuit port names fail before
meshing. Explicit RLGC and Touchstone parsing may construct numerical networks.
Duplicate JSON keys, unknown/missing fields, unsupported versions, nonfinite
numbers and boolean numbers are rejected. Inputs are copied. `to_dict()` returns
a fresh map; `frequency` and `z_ref` return read-only copies; `port_names` is the
final tuple. Record the exact commit and wheel hash for unreleased builds.

`analyze()` extracts each geometry component once per invocation, then applies
the existing connection solver. The result holds `network`, canonical `input_json`,
and tuples `source_networks` and `extractions` in input order: starting component,
then each added component. A supplied network or junction has `None` extraction;
a geometry input retains its original diagnostic result. Failures propagate
without returning a partial assembly or changing numerical/model gates.

Both `CircuitDocument` and `NetworkTransformDocument` accept
`{"kind":"network-assembly", "document":assembly.to_dict()}`. An assembly may
therefore be reduced or renormalized, then driven through the existing circuit
schema. Conversely, an assembly component cannot be a transformed network.
The circuit result retains the assembly (or transformation containing it) in
`extraction`. Older readers reject the new kind. Existing schemas keep their
previous field meanings; this is an input format, not persistent results.

## Checks and limits

Saved open/short shunt stubs reproduce analytic driven voltages and currents at
DC, quarter-wave and half-wave with absolute tolerance `1e-12`. A two-stub circuit
with finite complex loads is compared against scikit-rf 2.2.0 ideal media and
connections at maximum absolute S error `1e-10`. Tests cover crossed Touchstone
wiring, explicit renaming, snapshots, 32/33-join bounds, invalid metadata, singular
analysis and exact JSON replay. For both geometry input kinds, parsing uses zero
meshes and analysis meshes each component once, retaining diagnostic results.

These checks validate composition of established models. Ideal nodes contribute
no physical junction, via, pad or three-dimensional stub-transition parasitics.
The underlying line material/quasi-TEM limits and connection conditioning guards
remain in force. There is no additional measured-board, time-domain, FEM mesh
convergence or new-platform accuracy claim.

[Transforms](network_document.md) · [Driven circuits](circuit_document.md) ·
[한국어](../../locales/ko/pages/packages/sipi/network_assembly.md)
