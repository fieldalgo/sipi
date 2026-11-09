# Saved execution results

[한국어](../../locales/ko/pages/packages/sipi/execution_record.md) · [Immutable requests](execution_request.md) · [Shared execution](execution.md)

`SavedExecutionRecord` stores one execution receipt together with its exact
original input text, a host run identifier and declared build artifacts. Loading
and preparing a record never execute its calculation. This is an output envelope,
not an engine input, a multi-design project or a filesystem persistence API.

```python
import hashlib
from sipi import LumpedNetworkDocument
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord

request = SavedExecutionRequest(
    LumpedNetworkDocument([0, 1e9], resistance=10,
                          port_names=('input', 'output')).dumps())
receipt = request.run()
# Demonstration metadata only. A real host supplies its build artifact digests.
artifacts = [dict(component='sipi', version='example-only', kind='wheel',
                  sha256=hashlib.sha256(b'demonstration artifact').hexdigest())]
record = SavedExecutionRecord(request, receipt,
    run_id='demo:run-1', artifacts=artifacts)
saved = record.dumps()
restored = SavedExecutionRecord.loads(saved)
assert restored.receipt == receipt
assert restored.prepare().to_dict() == request.to_dict()
assert restored.artifacts['verification'] == 'host-declared'
```

`sipi.execution-record/1` has exactly `schema`, `run_id`, `source_text`, `receipt`,
`artifacts` and `content_sha256`. The receipt keeps its existing
`sipi.execution-receipt/1` request/execution objects. Its canonical input, semantic
request ID and controls must match a request reconstructed from `source_text`.
The exact original text is retained because canonical expansion can exceed the
input byte limit under which the original text was admitted. Reopening does not
silently enlarge that original limit or replace its controls.

The execution must use its existing `sipi.execution/1` shape and the same
canonical input. Complete or incomplete executions retain a result object and
null error; failed executions retain null result and an error with type/message,
including additional failure history. Above-limit fits keep their own
`accepted=False` separately from execution completion. Failed study rows and
incomplete summaries are not dropped. Structural validation does not certify the
numerical meaning or physical plausibility of an arbitrary supplied result.

## Declared artifacts and integrity

Artifacts use `sipi.artifact-declaration/1` with exactly `schema`,
`verification: "host-declared"` and `items`. Supply 1–64 items containing exactly
`component`, `version`, `kind` and `sha256`. Component names are lowercase ASCII
letters/digits/dot/underscore/hyphen, begin with a letter/digit and have at most
64 characters. Versions use ASCII letters/digits/plus/dot/underscore/hyphen and
have 1–128 characters. Kinds are `wheel`, `source-archive`, `wasm`, `executable`
or `runtime`; digests are 64 lowercase hexadecimal characters. Component/kind
pairs are unique, at least one component is `sipi`, and items are stored in
component/kind order. Loaded records must retain this order. Paths and URLs are
not artifact fields.

These are explicit **host declarations**, not verified installed artifacts or a
complete dependency inventory. The engine does not scan the machine, download
packages or certify that the declared bytes were executed. The host must obtain
and check real build/runtime identities. The example digest above is intentionally
synthetic and must not be used as deployment provenance.

`content_sha256` hashes canonical UTF-8 JSON of every record field except that
digest. Canonical JSON sorts keys, uses compact separators and emits Unicode
without ASCII escaping. A mismatch rejects; it is never silently repaired on
load. Anyone who changes the content can also recompute its checksum, so it is
not a signature, authenticity certificate or proof of execution. The declared
artifact digests have the same trust boundary.

## Reopen, then explicitly run

```python
prepared = restored.prepare()  # validates and reconstructs; no calculation
new_receipt = prepared.run()   # explicit new execution
new_record = SavedExecutionRecord(prepared, new_receipt,
    run_id='demo:run-2', artifacts=artifacts)
assert new_record.receipt == restored.receipt
assert new_record.run_id != restored.run_id
assert new_record.to_dict()['content_sha256'] != restored.to_dict()['content_sha256']
```

The host supplies `run_id`: 1–128 ASCII letters/digits/dot/underscore/colon/hyphen.
It must ensure uniqueness and compare its current run token before displaying a
response. Two equal semantic requests may belong to different runs. This record
does not implement cancellation, job scheduling or stale-response suppression.
A new execution should receive the host's current artifact declarations; copying
old declarations is not runtime verification.

Snapshots are immutable; `to_dict`, `receipt` and `artifacts` return detached
objects. `dumps()` returns canonical compact text and never writes a file.
`loads`/`from_dict` reject unknown/duplicate fields, nonfinite JSON values and
mismatched requests, receipts, metadata or checksums. The default record cap is
8 MiB, configurable through `max_record_bytes` from 1 byte through 64 MiB. It
applies to raw loaded UTF-8 text and the canonical stored text. Calculation input
limits remain separate inside the original request. Unknown versions raise; a
host should preserve the original file for a compatible reader.

```sh
python -m pytest -q tests/sipi/test_execution_record.py tests/sipi/test_execution_request.py tests/sipi/test_tensor_dielectric_fit_document.py
```

Checks cover actual accepted/above-limit fit receipts, incomplete studies and
failed goals; exact input/controls, original UTF-8 byte admission, declaration
limits, tampering, detached data and preparation without execution. All registered
engine inputs can be structurally reopened without fields. These checks do not
add physical accuracy, automatic persistence/recovery, UI integration, artifact
authentication or platform support.
