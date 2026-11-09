# Frozen saved execution requests

[한국어](../../locales/ko/pages/packages/sipi/execution_request.md) · [Saved execution](execution.md)

`sipi.execution_request.SavedExecutionRequest` freezes saved JSON text and the
generic controls `max_input_bytes`, `max_evaluations`, and `diagnostics`. It
validates through the existing strict document loader without running fields.
Some existing validators perform small algebraic calculations. Diagnostics are
limited to the existing top-level line contracts and stored as a sorted tuple.
Per-model budget admission still happens when running; preparation is not a
promise that a model fits its budget, time, memory or a particular platform.

`source_text` retains the original immutable text for execution admission.
`input_json` is the existing document's canonical JSON. This distinction matters:
pretty canonical text can exceed a byte limit even when the submitted compact
text fits. Running passes the original text and frozen options to `execute_saved`
without inflating its input-byte count, clamping a model budget or rerouting work.
Controls and `to_dict()` return detached snapshots; changing them does not alter
the request.

`input_sha256` hashes the exact UTF-8 canonical document text. `request_id` hashes
a UTF-8 JSON envelope containing `schema="sipi.execution-request/1"`, the parsed
canonical `input`, and all `controls`. This envelope is serialized with sorted
keys, compact separators, literal Unicode and no nonfinite values. Equivalent
saved formatting/key order therefore has the same identity after normalization.
Changing input or a control changes the identified request. Diagnostic order is
normalized because it selects the same computations. This does not claim that
every mathematically equivalent model has identical canonical JSON.

`run()` returns `sipi.execution-receipt/1` with `request` and `execution`. The
request descriptor contains schema, request_id, input_sha256, canonical input
and controls. Execution is the existing unchanged `sipi.execution/1` result,
including complete/incomplete/failed state, histories and causes. Its input must
match the frozen canonical input. Existing raised exceptions propagate unchanged;
a receipt is not fabricated for a raised failure. Request and receipt descriptors
are output contracts, not new registered engine input schemas.

## Example

```python
from sipi import LumpedNetworkDocument
from sipi.execution_request import SavedExecutionRequest

document = LumpedNetworkDocument([0.0, 1e9], resistance=10.0, inductance=2e-9)
request = SavedExecutionRequest(document.dumps(), max_evaluations=128)
expected_request_id = request.request_id
receipt = request.run()
assert receipt["schema"] == "sipi.execution-receipt/1"
assert receipt["request"]["request_id"] == expected_request_id
assert receipt["request"]["input"] == document.to_dict()
assert receipt["execution"]["schema"] == "sipi.execution/1"
assert receipt["execution"]["status"] == "complete"
assert receipt["execution"]["input"] == receipt["request"]["input"]
```

## Host responsibilities

The hashes identify semantic inputs/options, not a unique invocation. Two runs
of the same request have the same request_id. A host must also use its own run
token when rejecting late responses after cancellation, restart or a repeated
run. These helpers do not create processes, cancel jobs, operate files, launch
servers, upload data or update a screen. A future UI can compare the frozen
request identity with the current edited input, but stale-response handling
still needs host tests.

The identity does not include or authenticate engine/dependency artifacts.
Retain exact artifact hashes, method/settings and relevant validation with the
receipt before reproducing or caching results across builds. Package versions
alone may identify multiple development builds. SHA-256 is not a signature,
physical-accuracy certificate or browser/Windows capability declaration.

## Validation

Every currently registered saved schema prepares without field solves. Tests
independently reconstruct the hash envelope, check formatting and option identity,
immutable/detached snapshots, Unicode byte limits, canonical text expansion,
strict malformed inputs and original model-budget refusal. Existing success,
incomplete study rows, all four failed goal stages and raised exceptions retain
their output/cause/history. A real two-signal uniform lossy-material panel line
gives exactly the direct execution output; its analytic material characteristic
matrix agrees within 1e-10, capacitance within 1e-12, and S reciprocity/passivity
within 1e-10. The analytic check shares C0 and adds no independent geometry or
convergence claim. Existing input schemas and numerical execution are unchanged.
