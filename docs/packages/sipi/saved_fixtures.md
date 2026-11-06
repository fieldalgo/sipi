# Saved cascades and known-fixture removal

Explicit `sipi.network-transforms/2` adds saved `cascade` and `deembed` operations
to [network transformations](network_document.md). It uses the existing
[connection APIs](connection.md) and numeric gates. Version 1 remains the default,
preserves old canonical inputs and rejects the new operations. Older readers
reject version 2.

```python
from sipi import LumpedNetworkDocument, NetworkTransformDocument

frequency = [0, 1e6, 1e9]
def branch(resistance, names):
    model = LumpedNetworkDocument(frequency, resistance=resistance, port_names=names)
    return dict(kind='lumped-network', document=model.to_dict())

dut = branch(7, ('near', 'far'))
fixture = branch(100, ('outside', 'inside'))
plan = NetworkTransformDocument(dut, schema='sipi.network-transforms/2', operations=[
    dict(kind='cascade', side='left', network=fixture, port_names=['input', 'output']),
    dict(kind='deembed', left=fixture, right=None, port_names=['near', 'far']),
    dict(kind='renormalize', reference_ohms=[25, 85]),
])
result = NetworkTransformDocument.loads(plan.dumps()).analyze()
assert result.network.port_names == ('near', 'far')
assert len(result.fixture_networks) == 2
assert result.fixture_extractions == (None, None)
```

## Input contract

Both versions have exactly `schema`, `network`, `operations`, with 1–32 ordered
steps. Version 2 also accepts v1 `renormalize` and `terminate-ports` steps.

| `kind` | Required fields | Optional field |
|---|---|---|
| `cascade` | `side` (`left`/`right`), `network` (fixture input) | `port_names` |
| `deembed` | `left`, `right` (fixture input or null; at least one non-null) | `port_names` |

Fixtures are complete base `rlgc`, inline `touchstone`, `transmission-line`,
`volume-line` or `lumped-network` inputs. Fixtures cannot contain assemblies or
transformations. The initial source may still be `network-assembly`. There is no
recursive plan, file lookup, interpolation or executable input.

At each new operation, current network and fixtures need equal **2N single-ended
ports, all near then all far**, and identical frequency samples. Ordering is the
caller's explicit contract, not inferred from names. Cascade joins left far to
right near in conductor order, with exactly matching connected references.
`side='left'` prepends, `right` appends. Defaults are left near names/references
followed by right far. Deembedding removes known `left -> DUT -> right` fixtures;
their outer references must match current network ends. Output references and
default names come from fixture inner ports, or unchanged current ends.

Optional `port_names` explicitly names every output with unique nonempty
single-line strings. Supply it when defaults collide. Canonical v2 JSON saves the
full resolved name array. Renormalization is explicit. References and retained
names are tracked after **every** previous step. Odd port counts after reduction
cannot enter a fixture operation. Invalid fields, frequencies, names, references
and counts fail before any geometry mesh, including errors in the last step.
Singularity/conditioning requiring computed S is checked during analysis.
Explicit algebraic/RLGC/Touchstone parsing can construct numeric networks.

## Results, validation and limits

`frequency` and `z_ref` return read-only copies of final metadata; `port_names`
is the final tuple. Dictionaries are copied. Results retain `source_network`,
canonical `input_json` and the original `extraction`. Added `fixture_networks`
and `fixture_extractions` tuples follow operation order, left before right for
two-sided removal. Repeated documents have one entry per occurrence. Supplied
networks have `None` extraction; every geometry occurrence is extracted once.
V1 results have empty fixture tuples; the old four-argument result constructor
remains valid. Final frequency/ports/references are checked against metadata.

`CircuitDocument` accepts v2 through the existing `network-transform` kind.
Sources/loads use final names and are checked before meshing; fixture diagnostics
remain reachable in the circuit's transformation result.

Existing feedback/wave-chain condition limit `1e12` and residual gates remain.
A singular S can be removable: a series 100-ohm resistor at 50-ohm references
is one example. Zero forward transmission, such as a series capacitor at DC,
cannot be removed. No samples are dropped, result is regularized, passivity is
repaired or partial result is returned. This does not estimate fixtures,
calibrate measurements or recover lost/noisy information. Passing a numerical
guard is not an uncertainty certificate.

Checks compare two-port RLC composition/removal and nonsymmetric four-port
composition with scikit-rf at `1e-10` absolute S tolerance. Analytic resistance
totals, DUT recovery and loaded voltage use `1e-12`. Both geometry fixture kinds
retain diagnostics and extract once per occurrence. Tests cover intermediate
metadata, old JSON byte compatibility, snapshots and zero-transmission failure.
Geometry accuracy and mesh/domain convergence remain the component's own
responsibility. No new physical model, measured accuracy, dependency or platform
support is added.

[한국어](../../locales/ko/pages/packages/sipi/saved_fixtures.md)
